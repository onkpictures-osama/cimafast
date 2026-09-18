"""
تصدير تفريغ اللقطات (Shot List / Breakdown) لملف Excel أو Word أو PDF بفورمات
سينمائي احترافي قابل للطباعة.
"""
import os
import textwrap
from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins

import docx
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas

NAVY = "12203D"
YELLOW = "E8B923"
WHITE = "FFFFFF"

COLUMNS = [
    ("scene_number", "مشهد", 8),
    ("shot_number", "لقطة", 8),
    ("int_ext", "داخلي/خارجي", 12),
    ("day_night", "التوقيت", 10),
    ("location", "المكان", 26),
    ("shot_size", "حجم الكادر", 22),
    ("camera_movement", "حركة الكاميرا", 20),
    ("camera_angle", "زاوية الكاميرا", 18),
    ("duration", "المدة", 10),
    ("characters", "الشخصيات", 24),
    ("props", "الإكسسوارات", 20),
    ("action", "وصف الحركة", 30),
    ("dialogue", "الحوار", 40),
    ("emotion", "المشاعر", 16),
    ("visual_notes", "ملاحظات بصرية", 26),
    ("status", "الحالة", 12),
]


def _fetch_breakdown_rows(project_id, fetch_all):
    scenes = fetch_all("""
        SELECT s.id as scene_id, s.scene_number, s.int_ext, s.day_night, s.notes as scene_notes,
               l.name as location_name, lv.variant_name
        FROM scenes s
        LEFT JOIN location_variants lv ON s.location_variant_id = lv.id
        LEFT JOIN locations l ON lv.location_id = l.id
        WHERE s.project_id = ?
        ORDER BY s.scene_number
    """, (project_id,))

    rows = []
    for sc in scenes:
        shots = fetch_all(
            "SELECT * FROM shots WHERE scene_id=? ORDER BY shot_number", (sc["scene_id"],)
        )
        location_label = sc["location_name"] or ""
        if sc["variant_name"]:
            location_label = f"{location_label} - {sc['variant_name']}" if location_label else sc["variant_name"]

        if not shots:
            rows.append({
                "scene_number": sc["scene_number"],
                "shot_number": "",
                "int_ext": sc["int_ext"] or "",
                "day_night": sc["day_night"] or "",
                "location": location_label,
                "shot_size": "", "camera_movement": "", "camera_angle": "",
                "duration": "", "characters": "", "props": "", "action": "", "dialogue": "",
                "emotion": "", "visual_notes": sc["scene_notes"] or "", "status": "",
            })
            continue

        for sh in shots:
            chars = fetch_all("""
                SELECT ch.name, cl.look_name, sc.has_dialogue FROM shot_characters sc
                JOIN character_looks cl ON sc.look_id = cl.id
                JOIN characters ch ON cl.character_id = ch.id
                WHERE sc.shot_id = ?
            """, (sh["id"],))
            char_label = "، ".join(
                f"{c['name']} ({c['look_name']})" + ("" if c["has_dialogue"] else f" [{'بدون حوار'}]")
                for c in chars
            )
            prop_rows = fetch_all("""
                SELECT p.name FROM shot_props sp JOIN props p ON sp.prop_id = p.id
                WHERE sp.shot_id = ?
            """, (sh["id"],))
            props_label = "، ".join(p["name"] for p in prop_rows)
            emotion_label = sh["emotion_label"] or ""
            if sh["emotion_intensity"]:
                emotion_label = f"{emotion_label} ({sh['emotion_intensity']}/5)".strip()

            rows.append({
                "scene_number": sc["scene_number"],
                "shot_number": sh["shot_number"],
                "int_ext": sc["int_ext"] or "",
                "day_night": sh["day_night"] or sc["day_night"] or "",
                "location": location_label,
                "shot_size": sh["shot_size"] or "",
                "camera_movement": sh["camera_movement"] or "",
                "camera_angle": sh["camera_angle"] or "",
                "duration": sh["duration_seconds"] or "",
                "characters": char_label,
                "props": props_label,
                "action": sh["action_description"] or "",
                "dialogue": sh["dialogue_text"] or "",
                "emotion": emotion_label,
                "visual_notes": sh["visual_style_notes"] or "",
                "status": "تمت المراجعة" if sh["confirmed"] else "محتاجة مراجعة",
            })
    return rows


# خانات بتحتوي رقم واحد بس (عداد/كمية) - بتوسط ومن غير بولد إلا لو "index"
_NUMERIC_KEYS = {
    "scene_count", "day_count", "page_count", "scene", "duration",
    "shot_number", "scene_number",
}
# خانات بتحتوي أكتر من رقم مع بعض (زي "2، 5، 9") - دي مش تسلسل عداد،
# فبتتنسق من بداية الخانة (شمال) مش في النص
_LIST_NUMBER_KEYS = {"scene_numbers"}
# خانة الحوار - محتاجة فونت أصغر وبولد وعرض أوسع شوية عن باقي الخانات
_DIALOGUE_KEYS = {"dialogue"}


def _project_type_name_line(project):
    """بيرجع سطر بصيغة "فيلم | اسم العمل |" زي ما طلب المستخدم، لتمييز اسم
    العمل بشكل واضح وربطه بنوعه (فيلم/مسلسل/إعلان) في كل تقرير."""
    work_type = project["project_type"] or ""
    return f"{work_type} | {project['name']} |"


def _version_line(project):
    v = project["data_version"] if "data_version" in project.keys() else 1
    return f"نسخة {v or 1} — {date.today().isoformat()}"


def _build_generic_excel(sheet_title, report_name, project, columns, rows):
    """بناء ملف Excel عام بنفس الشكل البصري (بانر أصفر/كحلي، RTL، صفوف
    متبدلة الألوان) - مستخدم لكل تقارير التصدير (تفريغ اللقطات، كشف
    الشخصيات، التفريغ العام، كشف أماكن التصوير)، بنفس تنسيق كشف أماكن
    التصوير (الأفضل تصميمًا حسب المستخدم) في كل التقارير."""
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title
    ws.sheet_view.rightToLeft = True
    ws.page_margins = PageMargins(left=0.25, right=0.25, top=0.4, bottom=0.4, header=0.2, footer=0.2)

    header_fill = PatternFill(start_color=NAVY, end_color=NAVY, fill_type="solid")
    header_font = Font(color=WHITE, bold=True, size=10)
    title_font = Font(color=NAVY, bold=True, size=16)
    subtitle_font = Font(color=NAVY, bold=True, size=12)
    version_font = Font(color=NAVY, size=8, italic=True)
    title_fill = PatternFill(start_color=YELLOW, end_color=YELLOW, fill_type="solid")

    n_cols = len(columns)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)
    title_cell = ws.cell(row=1, column=1, value=f"🎬 {report_name}")
    title_cell.font = title_font
    title_cell.fill = title_fill
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 26

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=n_cols)
    subtitle_cell = ws.cell(row=2, column=1, value=_project_type_name_line(project))
    subtitle_cell.font = subtitle_font
    subtitle_cell.fill = title_fill
    subtitle_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 20

    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=n_cols)
    version_cell = ws.cell(row=3, column=1, value=_version_line(project))
    version_cell.font = version_font
    version_cell.fill = title_fill
    version_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[3].height = 14

    header_row = 5
    for col_idx, (key, label, width) in enumerate(columns, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=label)
        cell.font = header_font
        cell.fill = header_fill
        # النص متلف بس على حدود الكلمات (زي ما هو دايمًا في Excel) - مفيش
        # قطع لأي كلمة نفسها؛ لو اسم العمود كلمتين ممكن كل كلمة تقف في سطر
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        col_width = width + 6 if key in _DIALOGUE_KEYS else width
        ws.column_dimensions[get_column_letter(col_idx)].width = col_width
    ws.row_dimensions[header_row].height = 32
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)

    for r_offset, row in enumerate(rows):
        r = header_row + 1 + r_offset
        for col_idx, (key, _label, _width) in enumerate(columns, start=1):
            value = row.get(key, "")
            cell = ws.cell(row=r, column=col_idx, value=value)
            if key == "number":
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.font = Font(bold=True)
            elif key in _LIST_NUMBER_KEYS:
                # مش تسلسل، لكنها برضو أرقام - فتفضل بولد بس تتنسق من بداية
                # الخانة (شمال) مش في النص، عشان مالهاش ترتيب تسلسلي
                cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
                cell.font = Font(bold=True)
            elif key in _NUMERIC_KEYS:
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.font = Font(bold=True)
            elif key in _DIALOGUE_KEYS:
                cell.alignment = Alignment(horizontal="right", vertical="top", wrap_text=True)
                cell.font = Font(bold=True, size=9)
            else:
                cell.alignment = Alignment(horizontal="right", vertical="top", wrap_text=True)
            if r % 2 == 0:
                cell.fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_shot_list_excel(project, project_id, fetch_all):
    rows = _fetch_breakdown_rows(project_id, fetch_all)
    return _build_generic_excel("تفريغ اللقطات", "تفريغ اللقطات (Shooting List)", project, COLUMNS, rows)


# ---------- كشف الشخصيات الرئيسية ----------
CHARACTER_SHEET_COLUMNS = [
    ("number", "الرقم", 8),
    ("name", "الشخصية", 22),
    ("description", "الوصف", 34),
    ("nomination", "ترشيح", 20),
    ("scene_count", "عدد المشاهد", 12),
    ("scene_numbers", "أرقام المشاهد", 26),
    ("day_count", "عدد الايام", 12),
    ("locations", "أماكن التصوير", 30),
]


def build_characters_sheet_excel(project, project_id, fetch_all):
    """كشف الشخصيات الرئيسية بنفس فورمات الورقة القياسية المستخدمة في
    الإنتاج: رقم، اسم، وصف، ترشيح (يُملأ يدويًا)، عدد ومشاهد الظهور،
    عدد الأيام (يُملأ يدويًا حسب جدولة التصوير)، وأماكن التصوير المرتبطة.

    المصدر الأساسي لمشاهد كل شخصية هو ربط scene_characters (بيتسجل من وقت
    استيراد السكريبت، أو بالإضافة اليدوية من تبويب السكريبت)، عشان التقرير
    يبقى صحيح حتى لو المشاهد ديه لسه ملهاش لقطات مفرّغة."""
    characters = fetch_all(
        "SELECT * FROM characters WHERE project_id=? ORDER BY id", (project_id,)
    )
    rows = []
    for idx, ch in enumerate(characters, start=1):
        scene_rows = fetch_all("""
            SELECT DISTINCT s.scene_number, l.name AS location_name
            FROM scene_characters sch
            JOIN scenes s ON sch.scene_id = s.id
            LEFT JOIN location_variants lv ON s.location_variant_id = lv.id
            LEFT JOIN locations l ON lv.location_id = l.id
            WHERE sch.character_id = ?
            ORDER BY s.scene_number
        """, (ch["id"],))
        scene_numbers = sorted({r["scene_number"] for r in scene_rows})
        location_names = sorted({r["location_name"] for r in scene_rows if r["location_name"]})
        rows.append({
            "number": idx,
            "name": ch["name"],
            "description": ch["personality_notes"] or "",
            "nomination": "",
            "scene_count": len(scene_numbers),
            "scene_numbers": "، ".join(str(n) for n in scene_numbers),
            "day_count": "",
            "locations": "، ".join(location_names),
        })
    return _build_generic_excel(
        "كشف الشخصيات", "كشف الشخصيات الرئيسية", project,
        CHARACTER_SHEET_COLUMNS, rows,
    )


# ---------- التفريغ العام ----------
GENERAL_BREAKDOWN_COLUMNS = [
    ("number", "الرقم", 8),
    ("decor", "الديكور", 18),
    ("location", "المكان", 26),
    ("scene", "المشهد", 10),
    ("day_night", "ل/ن", 8),
    ("pages", "الصفحات", 10),
    ("situation", "الموقف", 40),
    ("main_characters", "الشخصيات الرئيسية", 26),
    ("secondary_characters", "الشخصيات الثانوية", 26),
    ("accessories", "الاكسسوار", 20),
    ("notes", "ملاحظات", 24),
]
_MAIN_ROLE_TYPES = {"بطل", "شرير"}


def build_general_breakdown_excel(project, project_id, fetch_all):
    """التفريغ العام: ورقة واحدة لكل مشهد بمعلومات الديكور والمكان والتوقيت
    والشخصيات المقسّمة لرئيسية/ثانوية حسب نوع الدور، زي الورقة القياسية
    المستخدمة في تنظيم التصوير. الديكور/الصفحات/الاكسسوار حقول بتتملى يدويًا
    وقت التحضير للتصوير الفعلي، مش موجودة في بيانات البرنامج."""
    scenes = fetch_all("""
        SELECT s.*, l.name AS location_name, lv.variant_name
        FROM scenes s
        LEFT JOIN location_variants lv ON s.location_variant_id = lv.id
        LEFT JOIN locations l ON lv.location_id = l.id
        WHERE s.project_id=? ORDER BY s.scene_number
    """, (project_id,))
    rows = []
    for idx, sc in enumerate(scenes, start=1):
        # المصدر الأساسي لشخصيات وإكسسوارات المشهد هو scene_characters/
        # scene_props (مسجلة من وقت الاستيراد أو الإضافة اليدوية في تبويب
        # السكريبت) - ده اللي بيخلي التقرير ده يتملى بالداتا فعليًا حتى لو
        # لسه مفيش لقطات مفرّغة للمشهد
        char_rows = fetch_all("""
            SELECT DISTINCT ch.name, ch.role_type
            FROM scene_characters sch
            JOIN characters ch ON sch.character_id = ch.id
            WHERE sch.scene_id = ?
        """, (sc["id"],))
        main_chars = sorted({r["name"] for r in char_rows if r["role_type"] in _MAIN_ROLE_TYPES})
        secondary_chars = sorted({r["name"] for r in char_rows if r["role_type"] not in _MAIN_ROLE_TYPES})
        prop_rows = fetch_all("""
            SELECT DISTINCT p.name
            FROM scene_props sp
            JOIN props p ON sp.prop_id = p.id
            WHERE sp.scene_id = ?
        """, (sc["id"],))
        accessories = sorted({r["name"] for r in prop_rows})
        location_label = sc["location_name"] or ""
        if sc["variant_name"]:
            location_label = f"{location_label} - {sc['variant_name']}" if location_label else sc["variant_name"]
        rows.append({
            "number": idx,
            "decor": "",
            "location": location_label,
            "scene": sc["scene_number"],
            "day_night": sc["day_night"] or "",
            "pages": "",
            "situation": sc["notes"] or "",
            "main_characters": "، ".join(main_chars),
            "secondary_characters": "، ".join(secondary_chars),
            "accessories": "، ".join(accessories),
            "notes": "",
        })
    return _build_generic_excel("التفريغ العام", "التفريغ العام", project, GENERAL_BREAKDOWN_COLUMNS, rows)


# ---------- كشف أماكن التصوير ----------
LOCATIONS_SHEET_COLUMNS = [
    ("number", "الرقم", 8),
    ("decor", "الديكور", 18),
    ("location", "المكان", 26),
    ("scene_count", "عدد المشاهد", 12),
    ("page_count", "عدد الصفحات", 12),
    ("day_count", "عدد الايام", 12),
    ("scene_numbers", "ارقام المشاهد", 30),
]


def build_locations_sheet_excel(project, project_id, fetch_all):
    """كشف أماكن التصوير: ورقة واحدة لكل مكان رئيسي، بعدد وأرقام المشاهد
    اللي بتصور فيه (بتجمع كل حالات/variants المكان مع بعض). الديكور وعدد
    الصفحات وعدد الأيام حقول تُملأ يدويًا وقت جدولة التصوير."""
    locations = fetch_all(
        "SELECT * FROM locations WHERE project_id=? ORDER BY id", (project_id,)
    )
    location_name_by_id = {l["id"]: l["name"] for l in locations}
    rows = []
    for idx, loc in enumerate(locations, start=1):
        scene_rows = fetch_all("""
            SELECT s.scene_number
            FROM scenes s
            JOIN location_variants lv ON s.location_variant_id = lv.id
            WHERE lv.location_id = ?
            ORDER BY s.scene_number
        """, (loc["id"],))
        scene_numbers = sorted({r["scene_number"] for r in scene_rows})
        # لو المكان ده ديكور/تكوين فرعي تابع لمكان رئيسي، نوضح ده في خانة
        # الديكور مع اسم المكان الرئيسي اللي بينتمي له
        if loc["parent_location_id"]:
            parent_name = location_name_by_id.get(loc["parent_location_id"], "")
            decor_label = f"ديكور فرعي - {parent_name}" if parent_name else "ديكور فرعي"
        else:
            decor_label = ""
        rows.append({
            "number": idx,
            "decor": decor_label,
            "location": loc["name"],
            "scene_count": len(scene_numbers),
            "page_count": "",
            "day_count": "",
            "scene_numbers": "، ".join(str(n) for n in scene_numbers),
        })
    return _build_generic_excel("كشف أماكن التصوير", "كشف اماكن التصوير", project, LOCATIONS_SHEET_COLUMNS, rows)


def _set_rtl(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    pPr = paragraph._p.get_or_add_pPr()
    bidi = OxmlElement('w:bidi')
    pPr.append(bidi)


def _set_rtl_center(paragraph):
    """زي _set_rtl بس بتوسط الفقرة - مستخدمة للعنوان الرئيسي وسطر النوع/الاسم
    وسطر النسخة في أول الصفحة."""
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pPr = paragraph._p.get_or_add_pPr()
    bidi = OxmlElement('w:bidi')
    pPr.append(bidi)


def build_shot_list_word(project, project_id, fetch_all):
    rows = _fetch_breakdown_rows(project_id, fetch_all)

    document = docx.Document()
    section = document.sections[0]
    section.orientation = 1  # WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    section.left_margin = Cm(1)
    section.right_margin = Cm(1)
    section.top_margin = Cm(1)
    section.bottom_margin = Cm(1)

    title = document.add_paragraph()
    _set_rtl_center(title)
    run = title.add_run("🎬 تفريغ اللقطات (Shooting List)")
    run.bold = True
    run.font.size = Pt(20)

    subtitle = document.add_paragraph()
    _set_rtl_center(subtitle)
    sub_run = subtitle.add_run(_project_type_name_line(project))
    sub_run.bold = True
    sub_run.font.size = Pt(13)

    version_p = document.add_paragraph()
    _set_rtl_center(version_p)
    v_run = version_p.add_run(_version_line(project))
    v_run.italic = True
    v_run.font.size = Pt(8)

    document.add_paragraph()

    headers = [label for _key, label, _width in COLUMNS]
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Light Grid Accent 1"
    for i, label in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = label
        for p in cell.paragraphs:
            _set_rtl(p)
            for r in p.runs:
                r.bold = True

    for row in rows:
        cells = table.add_row().cells
        for i, (key, _label, _width) in enumerate(COLUMNS):
            value = row.get(key, "")
            cells[i].text = str(value) if value != "" else "—"
            is_bold_cell = key in {"scene_number", "shot_number"} | _DIALOGUE_KEYS
            for p in cells[i].paragraphs:
                _set_rtl(p)
                if is_bold_cell:
                    for r in p.runs:
                        r.bold = True

    buf = BytesIO()
    document.save(buf)
    return buf.getvalue()


# ---------- تصدير PDF ----------
# النص العربي في مكتبة reportlab محتاج إعادة تشكيل الحروف (ligation) وترتيب
# ثنائي الاتجاه (bidi) يدويًا قبل الرسم، لأن reportlab أصلًا مبني للغات LTR.
# وبرضو محتاج خط يدعم العربي - بنستخدم خط Tahoma الموجود مع ويندوز لأنه
# بيغطي العربي كويس وموجود على أي جهاز ويندوز من غير الحاجة لتوزيع خط إضافي.
_ARABIC_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\tahoma.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
]
_ARABIC_BOLD_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\tahomabd.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
]
_ARABIC_FONT_NAME = None
_ARABIC_BOLD_FONT_NAME = None


def _register_arabic_font():
    """بيسجل نسخة عادية وبولد من نفس الخط (Tahoma) عشان نقدر نبين عناوين
    الأعمدة والخانات المهمة بالبولد فعليًا (مش بس تشبيه)."""
    global _ARABIC_FONT_NAME, _ARABIC_BOLD_FONT_NAME
    if _ARABIC_FONT_NAME:
        return _ARABIC_FONT_NAME, _ARABIC_BOLD_FONT_NAME
    for path in _ARABIC_FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("CFArabic", path))
                _ARABIC_FONT_NAME = "CFArabic"
                break
            except Exception:
                continue
    if not _ARABIC_FONT_NAME:
        _ARABIC_FONT_NAME = "Helvetica"

    for path in _ARABIC_BOLD_FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("CFArabicBold", path))
                _ARABIC_BOLD_FONT_NAME = "CFArabicBold"
                break
            except Exception:
                continue
    if not _ARABIC_BOLD_FONT_NAME:
        _ARABIC_BOLD_FONT_NAME = _ARABIC_FONT_NAME
    return _ARABIC_FONT_NAME, _ARABIC_BOLD_FONT_NAME


def _ar(text):
    """بيرتب أي نص (عربي أو إنجليزي أو مختلط) عشان يتعرض صح جوه ملف الـ PDF."""
    if text in (None, ""):
        return "—"
    text = str(text)
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def _wrap_lines(text, width_chars, max_lines=6):
    """بيقسم نص لسطور قصيرة (زي textwrap)، وبعدين يشكّل ويرتب كل سطر لوحده.

    ملاحظة مهمة: جربنا الأول نستخدم reportlab Paragraph جوه Table عشان يلف
    النص تلقائيًا، لكن اكتشفنا إن التلقيم التلقائي بتاعه بيتعارض مع النص
    المُشكّل والمُعاد ترتيبه (bidi) للعربي، وبيطلع أحيانًا ارتفاع خرافي للسطر
    (LayoutError) خصوصًا مع الجداول الطويلة. الحل: نلف النص إحنا بنفسنا قبل
    التشكيل (على النص الأصلي العادي)، وبعدين نرسم كل سطر بالـ canvas مباشرة
    بارتفاع صف ثابت محسوب مسبقًا - مفيش أي auto-sizing من reportlab نفسه.

    وبرضو بنحد أقصى عدد أسطر لكل خانة (مثلاً ملاحظات مشهد طويلة جدًا اتستوردت
    من السكريبت الأصلي) عشان صف واحد ميبقاش أطول من الصفحة نفسها - لو النص
    أطول من كده بنقطعه ونحط "…" في آخر سطر."""
    if text in (None, ""):
        return ["—"]
    text = str(text)
    lines = []
    for raw_line in text.split("\n"):
        if not raw_line.strip():
            lines.append("")
            continue
        # break_long_words=False: ممنوع نقطع كلمة نفسها على سطرين - لو الكلمة
        # نفسها أطول من عرض الخانة، تفضل في سطرها لوحدها وتطلع بره حدود
        # الخانة شوية، أحسن من ما نقطعها في النص
        lines.extend(textwrap.wrap(raw_line, width=width_chars, break_long_words=False) or [""])
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = (lines[-1].rstrip() + " …")[:width_chars]
    shaped = [_ar(line) if line else "" for line in lines]
    return shaped or ["—"]


def build_shot_list_pdf(project, project_id, fetch_all):
    """بيبني ملف PDF لتفريغ اللقطات بالرسم المباشر على الـ canvas (مش عن طريق
    Table/Paragraph بتوع reportlab)، عشان نتحكم في ارتفاع كل صف يدويًا
    ونتجنب مشكلة auto-sizing المعروفة مع النص العربي المُعاد ترتيبه."""
    rows = _fetch_breakdown_rows(project_id, fetch_all)
    font_name, bold_font_name = _register_arabic_font()

    page_w, page_h = landscape(A4)
    margin = 12  # مسافة أقل من حواف الصفحة عشان أسماء الأعمدة تلاقي مساحة أكتر
    usable_w = page_w - 2 * margin

    weight_sum = sum(w for _k, _l, w in COLUMNS)
    col_widths = [usable_w * (w / weight_sum) for _k, _l, w in COLUMNS]
    # حواف الأعمدة من اليمين لليسار (اتجاه القراءة العربي) - أول عمود
    # (رقم المشهد) بيبدأ من أقصى اليمين
    col_right_edges = []
    x = page_w - margin
    for w in col_widths:
        col_right_edges.append(x)
        x -= w
    col_centers = [right - w / 2 for right, w in zip(col_right_edges, col_widths)]
    wrap_chars = [max(6, int((w - 6) / 4.3)) for w in col_widths]
    # الأعمدة العددية (رقم مشهد/لقطة) بتوسط، وعمود الحوار بولد وفونت أصغر
    numeric_keys = {"scene_number", "shot_number"}
    col_keys = [key for key, _l, _w in COLUMNS]

    header_font_size = 8
    cell_font_size = 7.5
    dialogue_font_size = 7
    line_height = 9.5
    row_v_pad = 4
    header_height = 26
    title_block_height = 56

    buf = BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=(page_w, page_h))

    def draw_title_block():
        c.setFillColor(colors.HexColor(f"#{NAVY}"))
        c.setFont(bold_font_name, 15)
        c.drawCentredString(page_w / 2, page_h - margin - 14, _ar("تفريغ اللقطات (Shooting List)"))
        c.setFont(bold_font_name, 10.5)
        c.drawCentredString(page_w / 2, page_h - margin - 29, _ar(_project_type_name_line(project)))
        c.setFont(font_name, 7.5)
        c.drawCentredString(page_w / 2, page_h - margin - 42, _ar(_version_line(project)))

    def draw_header_row(top_y):
        c.setFillColor(colors.HexColor(f"#{NAVY}"))
        c.rect(margin, top_y - header_height, usable_w, header_height, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont(bold_font_name, header_font_size)
        for i, (_key, label, _w) in enumerate(COLUMNS):
            # اسم العمود بيتلف بس على حدود الكلمات (كل كلمة في سطر لو
            # لازم) - ممنوع قطع كلمة نفسها، وبيتوسط رأسيًا في ارتفاع الهيدر
            header_lines = _wrap_lines(label, max(4, wrap_chars[i]), max_lines=2)
            n = len(header_lines)
            start_y = top_y - (header_height - n * 9.5) / 2 - 7.5
            ly = start_y
            for hl in header_lines:
                c.drawCentredString(col_centers[i], ly, hl)
                ly -= 9.5
        return top_y - header_height

    def new_page(with_title):
        c.showPage()
        top = page_h - margin
        if with_title:
            draw_title_block()
            top -= title_block_height
        return draw_header_row(top)

    draw_title_block()
    y = draw_header_row(page_h - margin - title_block_height)

    for row_idx, row in enumerate(rows):
        cell_lines = [_wrap_lines(row.get(key, ""), wrap_chars[i]) for i, (key, _l, _w) in enumerate(COLUMNS)]
        n_lines = max(len(cl) for cl in cell_lines)
        row_height = row_v_pad * 2 + n_lines * line_height

        if y - row_height < margin:
            y = new_page(with_title=False)

        if row_idx % 2 == 1:
            c.setFillColor(colors.HexColor("#F2F2F2"))
            c.rect(margin, y - row_height, usable_w, row_height, stroke=0, fill=1)

        c.setFillColor(colors.black)
        for i, lines in enumerate(cell_lines):
            key = col_keys[i]
            is_numeric = key in numeric_keys
            is_dialogue = key in _DIALOGUE_KEYS
            c.setFont(
                bold_font_name if (is_numeric or is_dialogue) else font_name,
                dialogue_font_size if is_dialogue else cell_font_size,
            )
            ly = y - row_v_pad - cell_font_size
            for line in lines:
                if line:
                    if is_numeric:
                        c.drawCentredString(col_centers[i], ly, line)
                    else:
                        c.drawRightString(col_right_edges[i] - 3, ly, line)
                ly -= line_height

        c.setStrokeColor(colors.HexColor("#CCCCCC"))
        c.line(margin, y - row_height, page_w - margin, y - row_height)
        y -= row_height

    c.save()
    return buf.getvalue()
