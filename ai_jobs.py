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
import time

sys.path.insert(0, "/opt/cimafast-ai")
import spool  # noqa: E402

SCENE_HEADER_RE = re.compile(r'^\s*(?:##\s*)?(?:مشهد|المشهد|سين|السين)\s*[:\-–—]?\s*\d+',
                             re.IGNORECASE | re.MULTILINE)

# التقدير بيتحسب من حجم النص مش من عدد العناوين.
#
# السبب: أول نسخة كانت بتعد سطور "مشهد N" في الماركداون. ملف Word حقيقي
# عناوينه مش دايمًا بالشكل ده (ممكن تكون في جداول أو بصيغة تانية)، فطلع
# التقدير مشهدين بينما السكريبت كان 13 مشهد، والسقف طلع 0.40 دولار والتحليل
# كلف 0.63 — يعني السقف كان غلط من أوله.
#
# القياس من تشغيلين حقيقيين:
#   268 حرف    -> 0.1739 دولار
#   10,799 حرف -> 0.6294 دولار
# يديّنا تكلفة ثابتة تقريبًا (القايمة المرجعية) + تكلفة بالحرف.
BASE_COST_USD = 0.16          # القايمة المرجعية بتتدفع مرة واحدة
COST_PER_CHAR_USD = 0.0000433
CHARS_PER_SCENE = 830         # من نفس القياس: 10,799 / 13
MIN_ESTIMATE_USD = 0.20
CEILING_MULTIPLIER = 2.0      # سقف المصروف = ضعف التقدير
TERMINAL = spool.TERMINAL


def count_scenes(markdown_text):
    """عدد عناوين المشاهد المكتشفة — ممكن يقل عن الحقيقة حسب شكل الملف."""
    return len(SCENE_HEADER_RE.findall(markdown_text or ""))


def estimate(markdown_text):
    """(عدد المشاهد التقريبي، التكلفة المتوقعة، السقف).

    لو عد العناوين أقل بكتير من اللي حجم النص بيوحي بيه، بنعتمد على الحجم —
    أحسن ما نطلّع لليوزر رقم مطمّن وسقف بيقطع التحليل في نصه."""
    text = markdown_text or ""
    chars = len(text)
    detected = count_scenes(text)
    approx = max(1, chars // CHARS_PER_SCENE)
    scenes = detected if detected >= approx * 0.5 else approx
    cost = max(MIN_ESTIMATE_USD, round(BASE_COST_USD + chars * COST_PER_CHAR_USD, 2))
    return scenes, cost, round(cost * CEILING_MULTIPLIER, 2)


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


def latest_completed(project_id, within_hours=48):
    """آخر تحليل خلص للمشروع ده ولسه نتيجته موجودة على الديسك.

    من غير ده، أول ريفريش (أو إعادة تشغيل للبرنامج) بتضيّع تحليل اتدفع فيه
    فلوس، رغم إن ملف النتيجة لسه مكانه."""
    if not os.path.isdir(spool.STATUS):
        return None
    newest, newest_ts = None, 0
    cutoff = time.time() - within_hours * 3600
    for name in os.listdir(spool.STATUS):
        if not name.endswith(".json") or not name.startswith(f"{project_id}-"):
            continue
        jid = name[:-5]
        info = spool.read_status(jid)
        ts = info.get("heartbeat", 0)
        if info.get("state") == "done" and ts > cutoff and ts > newest_ts:
            if spool.read_result(jid) is not None:
                newest, newest_ts = jid, ts
    return newest


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
