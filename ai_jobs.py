"""واجهة التطبيق لتحليل السيناريو بالذكاء الاصطناعي.

التطبيق بيشتغل بمستخدم cimafast والـ worker بيشتغل root (عشان بيانات دخول
claude في /root/.claude). التسليم بينهم عن طريق ملفات في
/var/lib/cimafast/ai-jobs — التطبيق بيكتب في inbox بس، والـ worker بيكتب في
status و outbox بس، فمفيش ملف بيتكتب من الاتنين.

الملف ده بيضيف اللي يخص التطبيق: تقدير التكلفة قبل ما نبدأ، وسقف للمصروف،
ومنع تشغيل أكتر من تحليل لنفس المشروع في نفس الوقت.
"""
import os
import re
import sys

sys.path.insert(0, "/opt/cimafast-ai")
import spool  # noqa: E402

SCENE_HEADER_RE = re.compile(r'^\s*(?:##\s*)?(?:مشهد|المشهد|سين|السين)\s*[:\-–—]?\s*\d+',
                             re.IGNORECASE | re.MULTILINE)

# مقاس من تشغيل حقيقي: مشهدين بـ 0.1739 دولار، يعني ~0.087 للمشهد. الرقم ده
# تقديري: المشهد الطويل بحوار كتير بيكلف أكتر، والقايمة المرجعية بتتوزع على كل
# المشاهد فبتقل مع السكريبت الكبير.
COST_PER_SCENE_USD = 0.09
MIN_ESTIMATE_USD = 0.20
CEILING_MULTIPLIER = 2.0      # سقف المصروف = ضعف التقدير
TERMINAL = spool.TERMINAL


def count_scenes(markdown_text):
    return len(SCENE_HEADER_RE.findall(markdown_text or ""))


def estimate(markdown_text):
    """(عدد المشاهد، التكلفة المتوقعة، السقف) — بيتعرضوا لليوزر قبل التأكيد."""
    n = count_scenes(markdown_text)
    cost = max(MIN_ESTIMATE_USD, round(n * COST_PER_SCENE_USD, 2))
    return n, cost, round(cost * CEILING_MULTIPLIER, 2)


def active_job(project_id):
    """رقم أي تحليل شغال دلوقتي للمشروع ده، عشان ما نشغّلش اتنين مع بعض
    (وكمان عشان لو اليوزر قفل التاب يرجع يلاقيه)."""
    for name in sorted(os.listdir(spool.STATUS)) if os.path.isdir(spool.STATUS) else []:
        if not name.endswith(".json"):
            continue
        jid = name[:-5]
        if not jid.startswith(f"{project_id}-"):
            continue
        if spool.read_status(jid).get("state") not in TERMINAL:
            return jid
    return None


def start(markdown_text, project_id, filename, known_characters=None, max_cost_usd=None):
    if active_job(project_id):
        raise RuntimeError("فيه تحليل شغال بالفعل لنفس المشروع.")
    if max_cost_usd is None:
        max_cost_usd = estimate(markdown_text)[2]
    return spool.submit(markdown_text, project_id, filename,
                        known_characters=known_characters, max_cost_usd=max_cost_usd)


def status(job_id):
    return spool.read_status(job_id)


def result(job_id):
    return spool.read_result(job_id)
