"""تنضيف نص السكريبت وتحويله لماركداون قبل ما يتبعت لـ Opus.

الملفات اللي بترفع (Word/PDF) بتيجي ومعاها كلام مش من السيناريو: أرقام صفحات،
ترويسة متكررة في كل صفحة، خطوط فاصلة، ومسافات وسطور فاضية كتير. ده كله بيتحسب
توكنز وبيتدفع فيه فلوس، وكمان بيلخبط التعرف على بداية المشاهد.

الطبقة دي بتشيل الزيادة دي بس — **مش بتلخص ولا بتشيل أي حوار أو وصف**. أي سطر
بيتشال بيتسجل في الإحصائيات عشان اليوزر يشوف بعينه اتشال إيه.

ملحوظة على التوفير: ده بيوفر في *المدخلات*. المطلوب من Opus إنه يرجّع الحوار
كامل في notes، فحجم *المخرجات* بيفضل تقريبًا بحجم السكريبت — وده هو المصروف
الأكبر. التنضيف بيساعد، بس مش بيقلل الفاتورة للنص.
"""
import re
from collections import Counter

SCENE_HEADER_RE = re.compile(r'^\s*(?:(?:مشهد|المشهد|سين|السين)\s*[:\-–—]?\s*|م\s*/\s*)(\d+)(.*)$', re.IGNORECASE)
DIALOGUE_RE = re.compile(r'^\s*([؀-ۿA-Za-z][؀-ۿ\sA-Za-z\.]{0,24}?)\s*[:：]\s*(.+)$')

# أرقام صفحات بكل الأشكال الشائعة
PAGE_NUM_RE = re.compile(
    r'^\s*(?:[\-–—_=\*\.\s]*)(?:صفحة|ص|page|pg)?\s*[\-–—_\.\s]*\d{1,4}\s*(?:/\s*\d{1,4})?\s*(?:[\-–—_=\*\.\s]*)$',
    re.IGNORECASE)
# خطوط زخرفية: ـــــ أو ----- أو ===== أو *****
RULE_RE = re.compile(r'^[\s\-–—_=\*\.\u0640\u2500-\u257F]{3,}$')

REPEAT_MIN = 5          # سطر بيتكرر كتير أوي = ترويسة صفحة، مش حوار
REPEAT_MAX_LEN = 60


# اختصارات رأس المشهد المصري: ل/د = ليل/داخلي، ن/خ = نهار/خارجي ... إلخ.
# بنفكّها لكلمات عشان الـ AI (وأي حد بيقرا الماركداون) يفهمها من غير تخمين.
_CODE_WORDS = {'ل': 'ليل', 'ن': 'نهار', 'د': 'داخلي', 'خ': 'خارجي',
               'غ': 'غروب', 'ف': 'فجر'}
_CODE_PAIR_RE = re.compile(r'^([لنغف])\s*/\s*([دخ])$|^([دخ])\s*/\s*([لنغف])$')


def _expand_header_codes(rest):
    """بيحوّل "ل/د" لـ "ليل - داخلي". لو مش كود معروف بيسيبه زي ما هو."""
    text = (rest or '').strip()
    m = _CODE_PAIR_RE.match(text)
    if not m:
        return text
    parts = [g for g in m.groups() if g]
    return ' - '.join(_CODE_WORDS[p] for p in parts)


def _is_furniture(line):
    s = line.strip()
    if not s:
        return False
    return bool(PAGE_NUM_RE.match(s) or RULE_RE.match(s))


def _running_headers(lines):
    """السطور اللي بتتكرر بشكل مش طبيعي وشكلها ترويسة صفحة، مش حوار.

    إعفاء "أي سطر فيه نقطتين ده حوار" كان غلط: ترويسة زي
    "سيناريو: الرحلة الأخيرة" فيها نقطتين، فكانت بتفضل وكمان بتتقري كأنها حوار
    لشخصية اسمها "سيناريو" — يعني شخصية وهمية بتدخل كل المشاهد.

    الفرق الحقيقي: الشخصية الحقيقية بتقول كلام **مختلف** كل مرة. الترويسة
    بتتكرر بنفس النص بالحرف. فبنشيل بس السطر اللي متكرر ومتكلمه عمره ما قال
    غير الجملة دي."""
    counts = Counter(l.strip() for l in lines if l.strip())
    speaker_texts = {}
    for raw in lines:
        d = DIALOGUE_RE.match(raw.strip())
        if d:
            speaker_texts.setdefault(d.group(1).strip(), set()).add(d.group(2).strip())

    # فين أرقام الصفحات؟ الترويسة بتلزق بيها، الحوار لأ. ده أقوى فرق بينهم:
    # شخصية ممكن تكرر نفس الجملة القصيرة كتير ("نعم.")، بس مش جنب رقم صفحة.
    page_lines = {i for i, l in enumerate(lines) if PAGE_NUM_RE.match(l.strip())}
    positions = {}
    for i, l in enumerate(lines):
        t = l.strip()
        if t:
            positions.setdefault(t, []).append(i)

    def near_page_number(text):
        hits = positions.get(text, [])
        if not hits or not page_lines:
            return False
        close = sum(1 for i in hits if any(abs(i - p) <= 2 for p in page_lines))
        return close >= 0.6 * len(hits)

    out = set()
    for text, n in counts.items():
        if n < REPEAT_MIN or len(text) > REPEAT_MAX_LEN:
            continue
        if SCENE_HEADER_RE.match(text):      # عنوان مشهد، سيبه
            continue
        d = DIALOGUE_RE.match(text)
        if d and len(speaker_texts.get(d.group(1).strip(), ())) > 1:
            continue                          # متكلم حقيقي بيقول كلام مختلف
        if not near_page_number(text):
            continue                          # مش لازق بأرقام الصفحات = مش ترويسة
        out.add(text)
    return out


def to_markdown(lines):
    """بتاخد سطور نص خام وبترجّع (markdown, stats)."""
    raw_chars = sum(len(l) for l in lines) + len(lines)
    headers = _running_headers(lines)
    removed = Counter()

    out, blank_pending = [], False
    for line in lines:
        s = line.rstrip()
        stripped = s.strip()

        if not stripped:
            blank_pending = bool(out)
            continue
        if _is_furniture(stripped):
            removed["page furniture"] += 1
            continue
        if stripped in headers:
            removed["repeated header"] += 1
            continue

        s = re.sub(r'[ \t\u00a0]+', ' ', stripped)

        m = SCENE_HEADER_RE.match(s)
        if m:
            rest = _expand_header_codes(re.sub(r'^[\s:\-–—]+', '', m.group(2)))
            if out:
                out.append("")
            out.append(f"## مشهد {m.group(1)}" + (f" — {rest}" if rest else ""))
            blank_pending = False
            continue

        d = DIALOGUE_RE.match(s)
        if d:
            if blank_pending:
                out.append("")
            out.append(f"**{d.group(1).strip()}:** {d.group(2).strip()}")
            blank_pending = False
            continue

        if blank_pending:
            out.append("")
        out.append(s)
        blank_pending = False

    md = "\n".join(out).strip() + "\n"
    return md, {
        "raw_chars": raw_chars,
        "md_chars": len(md),
        "saved_chars": max(0, raw_chars - len(md)),
        "saved_pct": round(100 * (raw_chars - len(md)) / raw_chars, 1) if raw_chars else 0.0,
        "removed": dict(removed),
        "removed_header_samples": sorted(headers)[:5],
    }
