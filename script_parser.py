"""
تحليل ملفات السيناريو (Word أو نصي) واستخراج المشاهد والحوار منها
بشكل مبدئي تلقائي، يراجعه المستخدم ويعدله بعد كده.

بيدعم أكتر من شكل لكتابة السيناريو:
1) جدول عنوان مشهد جوه الـ Word (4 أعمدة: "مشهد N" | المكان | ن/ل | د/خ) -
   الشكل ده بيدي بيانات دقيقة 100% لرقم المشهد والمكان وداخلي/خارجي ونهار/ليل.
2) عنوان نصي صريح لكل مشهد زي "مشهد 1 - داخلي - نهار - المكان".
3) الشكل الأدبي المصري من غير عناوين مشاهد صريحة: الفصل بين المشاهد بعلامة
   "_ قطع _"، وأسماء الشخصيات بتتكتب وسط الصفحة (Bold أو بنقطتين أو بقوس أداء).

في كل الحالات، أسماء الشخصيات والحوار بيتعرف عليهم من تنسيق فقرات الـ Word
(التوسيط)، مش من الجدول.
"""
import re
import json
from io import BytesIO
from location_matcher import (
    extract_base_location,
    detect_state_change,
    find_matching_locations,
    suggest_variant_name
)

try:
    import docx
    from docx.enum.text import WD_ALIGN_PARAGRAPH
except ImportError:
    docx = None
    WD_ALIGN_PARAGRAPH = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

SCENE_HEADER_RE = re.compile(r'^\s*(?:مشهد|المشهد|سين|السين)\s*[:\-–—]?\s*(\d+)', re.IGNORECASE)
NUMERIC_HEADER_RE = re.compile(r'^\s*(\d+)\s*[\.\-–—\)]\s*(.+)$')
INT_RE = re.compile(r'داخلي|(?<![A-Za-z])INT\.?(?![A-Za-z])', re.IGNORECASE)
EXT_RE = re.compile(r'خارجي|(?<![A-Za-z])EXT\.?(?![A-Za-z])', re.IGNORECASE)

# علامة قطع المشهد في الأسلوب الأدبي، زي "_ قطع _" أو "-- قطع --" أو "قطع" لوحدها
CUT_RE = re.compile(r'^[\s_\-–—]*قطع[\s_\-–—]*$')

CHARACTER_TRAILING_PAREN_RE = re.compile(r'\s*\([^)]*\)\s*$')

DAY_NIGHT_KEYWORDS = [
    ('فجر', 'فجر'),
    ('غروب', 'غروب'),
    ('ليلاً', 'ليل'),
    ('ليلا', 'ليل'),
    ('ليل', 'ليل'),
    ('مساء', 'ليل'),
    ('صباح', 'نهار'),
    ('نهار', 'نهار'),
]

DIALOGUE_LINE_RE = re.compile(r'^\s*([؀-ۿA-Za-z][؀-ۿ\sA-Za-z\.]{0,24}?)\s*[:：]\s*(.+)$')
SEPARATORS_RE = re.compile(r'[\-–—:：،,\.]+')

# الرمز المختصر لعمود نهار/ليل وعمود داخلي/خارجي في جدول عنوان المشهد
DAY_NIGHT_CODE_MAP = {'ن': 'نهار', 'ل': 'ليل', 'غ': 'غروب', 'ف': 'فجر'}
INT_EXT_CODE_MAP = {'د': 'INT', 'خ': 'EXT'}


def _detect_day_night(text):
    for kw, norm in DAY_NIGHT_KEYWORDS:
        if kw in text:
            return norm
    return None


def _detect_int_ext(text):
    if INT_RE.search(text):
        return 'INT'
    if EXT_RE.search(text):
        return 'EXT'
    return None


def _clean_location(text, scene_num_str):
    cleaned = text
    cleaned = re.sub(r'مشهد|المشهد|سين|السين', '', cleaned)
    if scene_num_str:
        cleaned = cleaned.replace(scene_num_str, '', 1)
    cleaned = INT_RE.sub('', cleaned)
    cleaned = EXT_RE.sub('', cleaned)
    for kw, _ in DAY_NIGHT_KEYWORDS:
        cleaned = cleaned.replace(kw, '')
    cleaned = SEPARATORS_RE.sub(' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned or None


def _match_scene_header(text):
    m = SCENE_HEADER_RE.match(text)
    if m:
        return m.group(1)
    m2 = NUMERIC_HEADER_RE.match(text)
    if m2 and (_detect_int_ext(text) or _detect_day_night(text)):
        return m2.group(1)
    return None


def _clean_character_name(text):
    name = text.strip()
    name = re.sub(r'[:：\s]+$', '', name)
    name = CHARACTER_TRAILING_PAREN_RE.sub('', name).strip()
    return name


def _has_strong_cue_signal(text):
    """إشارة قوية إن السطر اسم شخصية (بينتهي بنقطتين أو بقوس أداء زي "(بعصبية)")
    - إشارة قوية بما فيه الكفاية إنها تشتغل حتى لو إحنا وسط سطور حوار متتالية."""
    t = text.strip()
    if not t or len(t) > 60:
        return False
    return t.endswith((':', '：', ')', '）'))


def _looks_like_bare_name(text):
    """اسم من غير أي علامة ترقيم في الآخر - نعتمد عليه بس لو السطر ده أول سطر متوسط
    بعد سطر وصف عادي (مش وسط حوار شغال، عشان منلخبطش سطر حوار متقسم على أكتر من فقرة)."""
    t = text.strip()
    if not t or len(t) > 60:
        return False
    if re.search(r'[؟!\.,،…:：\)）]\s*$', t):
        return False
    return True


def _new_scene(number, default_int_ext=None, default_day_night=None):
    return {
        'scene_number': number,
        'int_ext': default_int_ext,
        'day_night': default_day_night,
        'location_name': None,
        'weather': None,
        'characters': [],
        'body_lines': [],
    }


# الحروف العربية، عشان نعرف نحدد حدود الكلمة. \b مش بتنفع هنا لأن كل
# الحروف دي "حروف كلمة" فمش بتفرّق بين "الدرج" و"الدرجة".
_AR_LETTERS = '\u0621-\u064A\u0640\u0671-\u06D3'
# سوابق شائعة: ال التعريف، وحروف العطف والجر الملتصقة (و/ف/ب/ك/ل)
_AR_PREFIX = r'(?:[وفبكل])?(?:ال)?'


def _arabic_word_pattern(word):
    """بيطابق الكلمة كوحدة كاملة مع السوابق الملتصقة، ومش بيطابقها كجزء من
    كلمة أطول. من غير الـ lookarounds دي كان 'الدرجة' بيطلّع 'درج'،
    و'الكوبري' بيطلّع 'كوب'."""
    return (rf'(?<![{_AR_LETTERS}])' + _AR_PREFIX
            + re.escape(word) + rf'(?![{_AR_LETTERS}])')


def _extract_props_from_text(text, speaker_roster):
    props_lexicon = {
        'جهاز': 'جهاز', 'موبايل': 'موبايل', 'هاتف': 'هاتف', 'كتاب': 'كتاب',
        'سيجارة': 'سيجارة', 'فنجان': 'فنجان', 'كوب': 'كوب', 'سلاح': 'سلاح',
        'مسدس': 'مسدس', 'سكين': 'سكين', 'سيف': 'سيف', 'مفتاح': 'مفتاح',
        'درج': 'درج', 'رسالة': 'رسالة', 'صورة': 'صورة', 'خريطة': 'خريطة',
    }
    found_props = []
    for prop_key, prop_name in props_lexicon.items():
        if re.search(_arabic_word_pattern(prop_key), text):
            if prop_name not in found_props:
                found_props.append(prop_name)
    return found_props


def _detect_silent_characters(action_text, scene_speakers, roster):
    """الشخصيات الصامتة = اللي اتذكرت في سطور الوصف بس ملهاش حوار في المشهد ده.

    النسخة القديمة كانت بتاخد قايمة المتكلمين نفسها وتدوّر عليهم، فكانت بتطلّع
    شخصيات ليها حوار — عكس المطلوب تمامًا — ونتيجتها كانت بتتحط في قايمة
    موجودين فيها أصلًا، يعني الكود كله كان بيلف على الفاضي.

    بنستعمل قايمة كل المتكلمين في السيناريو كله (roster)، عشان شخصية بتتكلم في
    مشهد وبتظهر ساكتة في مشهد تاني تتحسب صح — وده اللي بيهم الإنتاج فعلًا
    (الشخصية لازم تتحجز وتتلبس حتى لو مش بتتكلم)."""
    speakers = set(scene_speakers or [])
    silent = []
    for name in (roster or []):
        if not name or name in speakers or name in silent:
            continue
        if re.search(_arabic_word_pattern(name), action_text or ''):
            silent.append(name)
    return silent


def _apply_silent_characters(scenes, known_characters=None):
    """بنعملها بعد ما كل المشاهد تتقرا، عشان نبني قايمة المتكلمين الكاملة الأول.

    known_characters هي شخصيات المشروع المسجلة قبل كده. من غيرها مش هنعرف
    نكتشف شخصية عمرها ما بتتكلم في السيناريو كله، لأن مفيش مصدر تاني لاسمها."""
    roster = []
    for name in (known_characters or []):
        if name and name not in roster:
            roster.append(name)
    for scene in scenes:
        for name in (scene.get('characters') or []):
            if name not in roster:
                roster.append(name)
    for scene in scenes:
        speakers = list(scene.get('characters') or [])
        action_text = scene.pop('_action_text', None)
        if action_text is None:
            action_text = scene.get('notes', '')
        # لو الـ AI قال صراحة مين اللي بيتكلم في المشهد ده (characters_speaking)،
        # الساكت هو الفرق بين الاتنين بالظبط — أدق بكتير من تخمينه من نص الحركة.
        explicit = scene.pop('_speaking', None)
        if explicit is not None:
            silent = [n for n in scene.get('characters') or [] if n not in explicit]
        else:
            silent = _detect_silent_characters(action_text, speakers, roster)
        scene['silent_characters'] = silent
        for name in silent:
            if name not in scene['characters']:
                scene['characters'].append(name)
    return scenes


def _finalize_scene(scene):
    seen = []
    for name in scene['characters']:
        if name not in seen:
            seen.append(name)
    scene['characters'] = seen

    notes_text = '\n'.join(scene['body_lines'])
    scene['notes'] = notes_text

    # سطور الحوار متخزنة بصيغة "اسم: كلام"، فبنشيلها عشان ندوّر على الشخصيات
    # الصامتة في الوصف بس، مش في كلام حد تاني عنها.
    dialogue_prefixes = tuple(f"{name}: " for name in seen)
    scene['_action_text'] = '\n'.join(
        line for line in scene['body_lines']
        if not (dialogue_prefixes and line.startswith(dialogue_prefixes))
    )

    scene['props'] = _extract_props_from_text(notes_text, seen)

    del scene['body_lines']
    return scene


# ---------------- الشكل النصي / الاحترافي (يعتمد على كلمات المفتاح فقط) ----------------

def _extract_txt_lines(file_bytes):
    text = file_bytes.decode('utf-8-sig', errors='ignore')
    return [line.strip() for line in text.splitlines() if line.strip()]


def _extract_pdf_lines(file_bytes):
    if PdfReader is None:
        raise RuntimeError('مكتبة قراءة ملفات PDF غير مثبتة (pypdf)')
    reader = PdfReader(BytesIO(file_bytes))
    lines = []
    for page in reader.pages:
        text = page.extract_text() or ''
        lines.extend(line.strip() for line in text.splitlines() if line.strip())
    return lines


def _parse_line_based(lines):
    warnings = []
    scenes = []
    current = None
    auto_number = 0

    for text in lines:
        if CUT_RE.match(text):
            if current:
                scenes.append(current)
            auto_number += 1
            current = _new_scene(auto_number, 'INT', 'نهار')
            continue

        scene_num = _match_scene_header(text)
        if scene_num:
            if current:
                scenes.append(current)
            auto_number += 1
            current = _new_scene(auto_number, 'INT', 'نهار')
            current['int_ext'] = _detect_int_ext(text) or 'INT'
            current['day_night'] = _detect_day_night(text) or 'نهار'
            current['location_name'] = _clean_location(text, scene_num)
            continue

        if current is None:
            auto_number += 1
            current = _new_scene(auto_number, 'INT', 'نهار')
            warnings.append(f'تمت إضافة نص قبل أي عنوان مشهد، تم وضعه في مشهد رقم {auto_number} تلقائيًا')

        dm = DIALOGUE_LINE_RE.match(text)
        if dm:
            name = dm.group(1).strip()
            dialogue = dm.group(2).strip()
            if name and len(name) <= 25:
                current['characters'].append(name)
                current['body_lines'].append(f'{name}: {dialogue}')
                continue
        current['body_lines'].append(text)

    if current:
        scenes.append(current)

    if not scenes:
        warnings.append('لم يتم التعرف على أي مشاهد في الملف')

    scenes = [_finalize_scene(sc) for sc in scenes]
    return scenes, warnings


# ---------------- شكل ملفات Word (بيستخدم التنسيق: Bold + توسيط، وجدول عنوان المشهد لو موجود) ----------------

def _iter_docx_items(document):
    """بيمشي على فقرات وجداول ملف الـ Word بترتيب ظهورها في المستند (مش الفقرات
    لوحدها ثم الجداول لوحدها) عشان نقدر نمسك جدول عنوان المشهد في مكانه الصح."""
    items = []
    for el in document.iter_inner_content():
        if isinstance(el, docx.table.Table):
            scene_info = _parse_scene_table(el)
            if scene_info:
                items.append({'type': 'scene_table', **scene_info})
            # جدول مش بشكل عنوان المشهد المعروف (4 أعمدة) - بيتجاهل
        else:
            text = el.text.strip()
            if not text:
                continue
            is_bold = bool(el.runs) and all(run.bold for run in el.runs if run.text.strip())
            is_center = el.alignment == WD_ALIGN_PARAGRAPH.CENTER
            items.append({'type': 'paragraph', 'text': text, 'bold': is_bold, 'center': is_center})
    return items


def _parse_scene_table(table):
    """جدول عنوان مشهد قياسي: صف واحد و4 أعمدة زي
    ["مشهد 10", "سطح يخت \"عروسة البحر\" غروب", "ل", "د"]"""
    if len(table.rows) < 1 or len(table.columns) != 4:
        return None
    cells = [c.text.strip() for c in table.rows[0].cells]
    if len(cells) != 4:
        return None

    m = SCENE_HEADER_RE.match(cells[0]) or re.match(r'^(\d+)$', cells[0])
    if not m:
        return None
    scene_number = int(m.group(1))

    location_text = cells[1]
    day_night = _detect_day_night(location_text)
    if day_night:
        for kw, _ in DAY_NIGHT_KEYWORDS:
            if kw in location_text:
                location_text = location_text.replace(kw, '')
                break
    else:
        day_night = DAY_NIGHT_CODE_MAP.get(cells[2])

    int_ext = _detect_int_ext(cells[1]) or INT_EXT_CODE_MAP.get(cells[3])

    location_text = SEPARATORS_RE.sub(' ', location_text)
    location_text = re.sub(r'\s+', ' ', location_text).strip() or None

    return {
        'scene_number': scene_number,
        'location_name': location_text,
        'day_night': day_night,
        'int_ext': int_ext,
    }


def _parse_docx_with_tables(items):
    """يستخدم جداول عنوان المشهد كحدود مشاهد رسمية (رقم/مكان/داخلي-خارجي/نهار-ليل
    دقيقة 100%)، ويحلل الفقرات اللي بينها بنفس منطق الحوار والشخصيات."""
    scenes = []
    current = None
    last_speaker = None
    prev_centered = False

    def start_scene(info):
        nonlocal current
        if current and (current['body_lines'] or current['characters']):
            scenes.append(current)
        current = _new_scene(info['scene_number'], info['int_ext'], info['day_night'])
        current['location_name'] = info['location_name']

    for item in items:
        if item['type'] == 'scene_table':
            start_scene(item)
            last_speaker = None
            prev_centered = False
            continue

        if current is None:
            # نص قبل أول جدول مشهد (عادة صفحة عنوان) - بيتجاهل
            continue

        text = item['text']

        if CUT_RE.match(text):
            # علامة "قطع" جوه نفس المشهد (تقسيم إيقاعي بس) - رقم المشهد
            # الحقيقي بييجي من الجدول، فبنسيب العلامة دي من غير ما تبدأ مشهد جديد
            last_speaker = None
            prev_centered = False
            continue

        if not item['center']:
            last_speaker = None
            prev_centered = False
            current['body_lines'].append(text)
            continue

        is_cue = _has_strong_cue_signal(text) or (not prev_centered and _looks_like_bare_name(text))
        if is_cue:
            name = _clean_character_name(text)
            if name:
                last_speaker = name
                current['characters'].append(name)
                prev_centered = True
                continue

        if last_speaker:
            current['body_lines'].append(f"{last_speaker}: {text}")
        else:
            current['body_lines'].append(text)
        prev_centered = True

    if current and (current['body_lines'] or current['characters']):
        scenes.append(current)

    warnings = []
    if not scenes:
        warnings.append('لم يتم التعرف على أي مشاهد في الملف')
    else:
        missing_meta = sum(1 for sc in scenes if not sc['day_night'] or not sc['int_ext'])
        if missing_meta:
            warnings.append(
                f'{missing_meta} من أصل {len(scenes)} مشهد ناقصه بيانات (داخلي/خارجي أو نهار/ليل) '
                'من جدول العنوان، راجعها يدويًا في تبويب السكريبت.'
            )

    scenes = [_finalize_scene(sc) for sc in scenes]
    return scenes, warnings


def _extract_docx_paragraphs(file_bytes):
    document = docx.Document(BytesIO(file_bytes))
    paragraphs = []
    for p in document.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        is_bold = bool(p.runs) and all(run.bold for run in p.runs if run.text.strip())
        is_center = p.alignment == WD_ALIGN_PARAGRAPH.CENTER
        paragraphs.append({'text': text, 'bold': is_bold, 'center': is_center})
    return paragraphs


FRONT_MATTER_KEYWORDS_RE = re.compile(
    r'تأليف|إخراج|بطولة|سيناريو|إنتاج|إعداد|THE\s|^فيلم$|^مسلسل$', re.IGNORECASE
)


def _looks_like_front_matter_line(text):
    """سطر من صفحة العنوان (اسم الفيلم، المخرج، المؤلف...) - مش جزء فعلي من
    المشهد الأول، حتى لو مكنش Bold أو متوسط."""
    return bool(FRONT_MATTER_KEYWORDS_RE.search(text))


def _skip_front_matter(paragraphs, cap=60):
    for i, p in enumerate(paragraphs[:cap]):
        if not p['bold'] and not p['center'] and not _looks_like_front_matter_line(p['text']):
            return paragraphs[i:]
    return paragraphs


def _parse_docx_paragraphs(paragraphs):
    paragraphs = _skip_front_matter(paragraphs)

    scenes = []
    current = None
    scene_number = 0
    last_speaker = None
    prev_centered = False

    def start_new_scene():
        nonlocal current, scene_number
        if current and (current['body_lines'] or current['characters']):
            scenes.append(current)
        scene_number += 1
        current = _new_scene(scene_number)

    start_new_scene()

    for p in paragraphs:
        text = p['text']

        if CUT_RE.match(text):
            start_new_scene()
            last_speaker = None
            prev_centered = False
            continue

        header_num = _match_scene_header(text)
        if header_num:
            current['int_ext'] = _detect_int_ext(text) or current['int_ext']
            current['day_night'] = _detect_day_night(text) or current['day_night']
            loc = _clean_location(text, header_num)
            if loc:
                current['location_name'] = loc
            continue

        # الوصف/الحركة دايمًا من غير توسيط في الأسلوب ده؛ التوسيط بيتحجز
        # لاسم الشخصية والحوار بس (سواء الاسم Bold أو له نقطتين أو قوس أداء)
        if not p['center']:
            last_speaker = None
            prev_centered = False
            current['body_lines'].append(text)
            continue

        # اسم الشخصية بيتحدد إما بإشارة قوية (نقطتين/قوس) تشتغل في أي وقت، أو
        # اسم من غير علامة ترقيم بس لو ده أول سطر متوسط بعد سطر وصف (مش وسط حوار
        # شغال، عشان منلخبطش سطر حوار اتقسم على أكتر من فقرة)
        is_cue = _has_strong_cue_signal(text) or (not prev_centered and _looks_like_bare_name(text))
        if is_cue:
            name = _clean_character_name(text)
            if name:
                last_speaker = name
                current['characters'].append(name)
                prev_centered = True
                continue

        if last_speaker:
            current['body_lines'].append(f"{last_speaker}: {text}")
        else:
            current['body_lines'].append(text)
        prev_centered = True

    if current and (current['body_lines'] or current['characters']):
        scenes.append(current)

    warnings = []
    if not scenes:
        warnings.append('لم يتم التعرف على أي مشاهد في الملف')
    else:
        missing_meta = sum(1 for sc in scenes if not sc['int_ext'] and not sc['location_name'])
        if missing_meta:
            warnings.append(
                f'{missing_meta} من أصل {len(scenes)} مشهد متعرفش على المكان أو داخلي/خارجي أو نهار/ليل تلقائيًا '
                '(السكريبت مكتوب بدون عناوين مشاهد صريحة). راجع وكمّل البيانات دي يدويًا في تبويب السكريبت.'
            )

    scenes = [_finalize_scene(sc) for sc in scenes]
    return scenes, warnings


# ---------------- استيراد JSON جاهز (اتحضر بمعرفة أي AI زي Claude/ChatGPT/Gemini) ----------------

VALID_DAY_NIGHT = {'نهار', 'ليل', 'غروب', 'فجر'}
INT_EXT_ALIASES = {
    'int': 'INT', 'interior': 'INT', 'داخلي': 'INT', 'د': 'INT',
    'ext': 'EXT', 'exterior': 'EXT', 'خارجي': 'EXT', 'خ': 'EXT',
}


def _normalize_int_ext(value):
    if not value:
        return None
    v = str(value).strip()
    if v.upper() in ('INT', 'EXT'):
        return v.upper()
    return INT_EXT_ALIASES.get(v.lower()) or INT_EXT_ALIASES.get(v)


def _normalize_day_night(value):
    if not value:
        return None
    v = str(value).strip()
    return v if v in VALID_DAY_NIGHT else None


def parse_json_script(file_bytes, known_characters=None):
    """بيقرا ملف JSON جاهز (مجهز بمعرفة أي AI حلل السكريبت) وبيحوله لنفس شكل
    المشاهد اللي بترجعه parse_script، عشان يعدي على نفس خطوات المراجعة والدمج
    والاستيراد. الصيغة المتوقعة موصوفة في app.py مع البرومبت الجاهز للمستخدم."""
    warnings = []
    try:
        text = file_bytes.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise RuntimeError('الملف مش UTF-8 صالح. احفظه كـ JSON بترميز UTF-8.')

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f'الملف مش JSON صحيح: {e}')

    if isinstance(data, list):
        raw_scenes = data
    elif isinstance(data, dict):
        raw_scenes = data.get('scenes')
        if not isinstance(raw_scenes, list):
            raise RuntimeError('الملف لازم يحتوي على مفتاح "scenes" وقيمته قايمة مشاهد.')
    else:
        raise RuntimeError('شكل الملف غير متوقع - لازم يكون JSON فيه قايمة مشاهد.')

    scenes = []
    # حقول البرومبت المطور اللي لسه مالهاش مسار استيراد — بنبلّغ عنها في الآخر
    # بدل ما نبلعها في صمت واليوزر يفتكر إنها اتسجلت.
    unsupported = set()
    for i, raw in enumerate(raw_scenes):
        if not isinstance(raw, dict):
            warnings.append(f'العنصر رقم {i + 1} اتجاهل لأنه مش عنصر بيانات صحيح.')
            continue

        try:
            scene_number = int(raw.get('scene_number'))
        except (TypeError, ValueError):
            warnings.append(f'العنصر رقم {i + 1} اتجاهل لأنه من غير رقم مشهد صحيح (scene_number).')
            continue

        int_ext = _normalize_int_ext(raw.get('int_ext'))
        day_night = _normalize_day_night(raw.get('day_night'))
        if raw.get('day_night') and not day_night:
            warnings.append(
                f'مشهد {scene_number}: قيمة day_night "{raw.get("day_night")}" مش من ضمن '
                '(نهار، ليل، غروب، فجر) فاتجاهلت.'
            )

        location_name = raw.get('location_name')
        location_name = str(location_name).strip() or None if location_name else None

        characters = raw.get('characters') or []
        if not isinstance(characters, list):
            characters = []
        characters = [str(c).strip() for c in characters if str(c).strip()]

        weather = raw.get('weather')
        weather = str(weather).strip() or None if weather else None

        props = raw.get('props') or []
        if not isinstance(props, list):
            props = []
        props = [str(p).strip() for p in props if str(p).strip()]

        # حرف المشهد المقسوم بيعدي زي ما هو لو الـ AI رجّعه، عشان يوصل
        # للاستيراد. 35A غير 35، ولازم يفضلوا متفرقين.
        suffix = raw.get('scene_suffix')
        suffix = str(suffix).strip()[:2] if isinstance(suffix, str) and suffix.strip() else None

        # البرومبت المطور بيطلب قايمة المتكلمين صراحة. لو موجودة، الساكت هو
        # الفرق بينها وبين كل الحاضرين — بدل ما نخمّنه من نص الحركة.
        speaking = raw.get('characters_speaking')
        if isinstance(speaking, list):
            speaking = [str(c).strip() for c in speaking if str(c).strip()]
        else:
            speaking = None

        notes = str(raw.get('notes') or '')
        look_change = raw.get('look_change_notes')
        look_change = str(look_change).strip() if look_change else ''
        if look_change:
            # مكانش ليه عمود في قاعدة البيانات، فبيتسجل في الملاحظات بعنوان
            # واضح بدل ما يضيع — التغيير ده بيفرق في الماكياج والملابس.
            notes = f"{notes}\n\n[تغيير في الشكل] {look_change}".strip()

        try:
            episode_number = int(raw.get('episode_number'))
        except (TypeError, ValueError):
            episode_number = None

        shot_size = raw.get('suggested_shot_size')
        shot_size = str(shot_size).strip() or None if shot_size else None
        camera_movement = raw.get('suggested_camera_movement')
        camera_movement = str(camera_movement).strip() or None if camera_movement else None
        if episode_number is not None:
            unsupported.add('episode_number')
        if shot_size or camera_movement:
            unsupported.add('shots')

        scenes.append({
            'scene_number': scene_number,
            'scene_suffix': suffix,
            'int_ext': int_ext,
            'day_night': day_night,
            'location_name': location_name,
            'weather': weather,
            'characters': characters,
            'props': props,
            'notes': notes,
            'episode_number': episode_number,
            'suggested_shot_size': shot_size,
            'suggested_camera_movement': camera_movement,
            'look_change_notes': str(raw.get('look_change_notes') or '').strip(),
            '_speaking': speaking,
        })

    if not scenes:
        warnings.append('لم يتم العثور على أي مشهد صالح في ملف الـ JSON.')
    if 'episode_number' in unsupported:
        warnings.append(
            'الملف فيه أرقام حلقات (episode_number)، بس الاستيراد لسه مابيوزعش المشاهد '
            'على الحلقات تلقائيًا — هتحتاج تظبط الحلقة لكل مشهد يدويًا بعد الاستيراد.'
        )
    if 'shots' in unsupported:
        warnings.append(
            'الملف فيه اقتراحات لحجم الكادر وحركة الكاميرا، بس دي بتتحط على اللقطات '
            'مش المشاهد — مش هتتستورد دلوقتي، هتفضل اقتراح تقدر ترجعله من الملف.'
        )

    return {'scenes': _apply_silent_characters(scenes, known_characters), 'warnings': warnings}


def looks_like_screenplay(lines):
    """بيقيس لو النص ده سيناريو فعلًا ولا لأ، وبيرجّع (نسبة الثقة، الأدلة).

    ليه ده مهم: البرومبت بيطلب من الـ AI تفريغ مشاهد، والـ schema بتفرض إنه
    يرجّع قايمة مشاهد — يعني لو اتبعتله بيان صحفي أو أي مستند مش سيناريو،
    مش قدامه غير إنه **يخترع** مشاهد وأرقام. ده حصل فعلًا: مستند دعائي طلع
    منه 13 مشهد بترقيم متخترع بالكامل، والنظام قال "تم بنجاح".

    فبنقيس الأدلة الأول ونقول للمستخدم قبل ما يصرف فلوس."""
    text = "\n".join(lines)
    total = max(1, len([l for l in lines if l.strip()]))
    evidence = {
        'scene_headers': sum(1 for l in lines if SCENE_HEADER_RE.match(l)),
        'int_ext': len(INT_RE.findall(text)) + len(EXT_RE.findall(text)),
        'day_night': len(re.findall(r'\b(?:نهار|ليل|غروب|فجر)\b', text)),
        'dialogue_lines': sum(1 for l in lines if DIALOGUE_LINE_RE.match(l)),
        'cut_markers': sum(1 for l in lines if CUT_RE.match(l)),
    }
    score = 0.0
    if evidence['scene_headers']:
        score += 0.5
    if evidence['int_ext'] >= 2:
        score += 0.2
    if evidence['day_night'] >= 2:
        score += 0.1
    if evidence['dialogue_lines'] / total > 0.08:
        score += 0.2
    if evidence['cut_markers']:
        score += 0.1
    return min(1.0, round(score, 2)), evidence


def extract_lines(filename, file_bytes):
    """بترجّع سطور النص الخام من غير أي تحليل.

    اتفصلت عن parse_script عشان التطبيق يقدر يطلّع النص وينضفه ويحوّله ماركداون
    قبل ما يبعته للـ AI. مهم برضه لأمان: قراءة ملفات Word/PDF (اللي اليوزر رفعها)
    بتفضل هنا في التطبيق بمستخدم cimafast، والـ worker اللي شغال root عمره ما
    بيشوف غير نص عادي."""
    lower = filename.lower()
    if lower.endswith('.docx'):
        if docx is None:
            raise RuntimeError('مكتبة قراءة ملفات Word غير مثبتة (python-docx)')
        document = docx.Document(BytesIO(file_bytes))
        out = []
        for it in _iter_docx_items(document):
            if it.get('type') == 'scene_table':
                # عناوين المشاهد في سكريبتات Word كتير بتكون جداول مش فقرات.
                # النسخة الأولى كانت بتاخد الفقرات بس، فكل أرقام المشاهد
                # والداخلي/خارجي والأماكن كانت بتضيع قبل ما توصل للـ AI —
                # فالـ AI كان بيخترع ترقيم من عنده. بنرجّعهم هنا كسطر عنوان.
                bits = [f"مشهد {it['scene_number']}"]
                if it.get('int_ext'):
                    bits.append({'INT': 'داخلي', 'EXT': 'خارجي',
                                 'INT/EXT': 'داخلي/خارجي'}.get(it['int_ext'], it['int_ext']))
                if it.get('day_night'):
                    bits.append(it['day_night'])
                if it.get('location_name'):
                    bits.append(it['location_name'])
                # نفس الكلمة ممكن تتقري من أكتر من عمود (المكان فيه "داخلي"
                # والعمود التاني كمان) — منكررهاش في سطر العنوان
                seen, uniq = set(), []
                for b in bits:
                    key = (b or '').strip()
                    if key and key not in seen:
                        seen.add(key)
                        uniq.append(key)
                out.append(' - '.join(uniq))
            elif it.get('type') == 'paragraph' and it.get('text'):
                out.append(it['text'])
        return out
    if lower.endswith('.txt'):
        return _extract_txt_lines(file_bytes)
    if lower.endswith('.pdf'):
        return _extract_pdf_lines(file_bytes)
    if lower.endswith('.json'):
        raise RuntimeError('ملف JSON جاهز بالفعل — مش محتاج تحليل بالذكاء الاصطناعي.')
    raise RuntimeError('صيغة الملف غير مدعومة. استخدم .docx أو .txt أو .pdf')


def parse_script(filename, file_bytes, known_characters=None):
    lower = filename.lower()
    if lower.endswith('.docx'):
        if docx is None:
            raise RuntimeError('مكتبة قراءة ملفات Word غير مثبتة (python-docx)')
        document = docx.Document(BytesIO(file_bytes))
        items = _iter_docx_items(document)
        has_scene_tables = any(it['type'] == 'scene_table' for it in items)
        if has_scene_tables:
            scenes, warnings = _parse_docx_with_tables(items)
        else:
            paragraphs = [it for it in items if it['type'] == 'paragraph']
            scenes, warnings = _parse_docx_paragraphs(paragraphs)
    elif lower.endswith('.txt'):
        lines = _extract_txt_lines(file_bytes)
        scenes, warnings = _parse_line_based(lines)
    elif lower.endswith('.pdf'):
        lines = _extract_pdf_lines(file_bytes)
        scenes, warnings = _parse_line_based(lines)
    elif lower.endswith('.json'):
        return parse_json_script(file_bytes, known_characters)
    else:
        raise RuntimeError('صيغة الملف غير مدعومة. استخدم .docx أو .txt أو .pdf أو .json')

    return {'scenes': _apply_silent_characters(scenes, known_characters), 'warnings': warnings}


# ---------------- تجميع أسماء متشابهة (شخصيات زي "سويسي"/"السويسي"، أو أماكن زي "سطح اليخت"/"سطح اليخت بعد لحظات") ----------------

def _find_similar_groups(names):
    """بيرجع مجموعات من الأسماء اللي ممكن تكون نفس الحاجة (شخصية أو مكان)،
    بناءً على احتواء نصي (اسم جوه اسم تاني)، عشان المستخدم يراجعها ويقرر
    يدمجها ولا لأ قبل ما نضيف المشاهد للمشروع فعليًا."""
    groups = []
    used = set()
    for i, a in enumerate(names):
        if a in used:
            continue
        cluster = [a]
        for b in names[i + 1:]:
            if b in used:
                continue
            # احتواء نصي بس، وبشرط الاسم الأقصر يكون 3 حروف على الأقل عشان
            # منلخبطش أسماء مختلفة بينها حروف مشتركة قليلة
            if min(len(a), len(b)) >= 3 and (a in b or b in a):
                cluster.append(b)
        if len(cluster) > 1:
            groups.append(cluster)
            used.update(cluster)
    return groups


def find_similar_name_groups(scenes):
    """مجموعات أسماء الشخصيات المتشابهة (زي "سويسي" / "السويسي" / "سيد السويسي")."""
    all_names = []
    for sc in scenes:
        for name in sc.get('characters', []):
            if name not in all_names:
                all_names.append(name)
    return _find_similar_groups(all_names)


def find_similar_location_groups(scenes):
    """مجموعات أسماء الأماكن المتشابهة (زي "سطح اليخت" / "سطح اليخت بعد لحظات") -
    غالبًا دي حالات مختلفة لنفس المكان مش أماكن منفصلة."""
    all_names = []
    for sc in scenes:
        loc = sc.get('location_name')
        if loc and loc not in all_names:
            all_names.append(loc)
    return _find_similar_groups(all_names)




def find_location_matches_with_states(scenes, project_locations=None):
    """
    يجد تطابقات الأماكن مع كشف الحالات الدرامية
    يرجع: [(similar_locations, state_changes, suggested_variant)]
    """
    all_locations = []
    for sc in scenes:
        loc = sc.get('location_name')
        if loc and loc not in all_locations:
            all_locations.append({'name': loc, 'scene_id': sc.get('id')})
    
    if not project_locations:
        project_locations = []
    
    matches = []
    for new_loc in all_locations:
        # كشف التغيرات الدرامية
        state_changes = detect_state_change(new_loc['name'])
        
        # البحث عن تطابقات
        matching = find_matching_locations(new_loc, project_locations, threshold=0.75)
        
        if matching or state_changes:
            matches.append({
                'location': new_loc['name'],
                'state_changes': state_changes,
                'matching_locations': matching,
                'suggested_variant': suggest_variant_name(
                    extract_base_location(new_loc['name']),
                    state_changes
                )
            })
    
    return matches


def apply_location_merges(scenes, merge_map):
    """بيطبق قرار دمج الأماكن (اسم قديم -> اسم المكان الرئيسي المعتمد).
    الاسم الأصلي قبل الدمج بيتحفظ كـ location_variant_hint عشان يستخدم
    كاسم لحالة (Variant) المكان بدل ما يضيع."""
    if not merge_map:
        return scenes
    for sc in scenes:
        original = sc.get('location_name')
        if original and original in merge_map:
            canonical = merge_map[original]
            if canonical != original:
                sc['location_variant_hint'] = original
            sc['location_name'] = canonical
    return scenes


def apply_character_merges(scenes, merge_map):
    """بيطبق قرار الدمج (اسم قديم -> الاسم المعتمد) على قوائم الشخصيات وعلى
    نص الحوار في الملاحظات كمان."""
    if not merge_map:
        return scenes

    for sc in scenes:
        sc['characters'] = list(dict.fromkeys(
            merge_map.get(name, name) for name in sc.get('characters', [])
        ))
        notes = sc.get('notes', '')
        if notes:
            lines = notes.split('\n')
            new_lines = []
            for line in lines:
                m = re.match(r'^([^:：\n]{1,40})([:：])(.*)$', line)
                if m and m.group(1).strip() in merge_map:
                    canonical = merge_map[m.group(1).strip()]
                    new_lines.append(f"{canonical}{m.group(2)}{m.group(3)}")
                else:
                    new_lines.append(line)
            sc['notes'] = '\n'.join(new_lines)

    return scenes
