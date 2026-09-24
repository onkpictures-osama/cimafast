"""
تصدير تفريغ اللقطات (Shot List / Breakdown) لملف Excel أو Word أو PDF بفورمات
سينمائي احترافي قابل للطباعة.
"""
import os
import textwrap
from datetime import date
from io import BytesIO

from database import scene_label
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins

import docx
from docx.shared import Pt, Cm, RGBColor
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

from theme.brand import MASTER_ASPECT, lockup_master_path
from theme.tokens import BRAND

# --------------------------------------------------------------------------
# ألوان التقارير — بتتقرا من بالتة البراند نفسها (‎theme/tokens.py‎) مش من
# قيم مكتوبة بالإيد قريبة منها. الملف ده اتكتب قبل ما نظام الهوية يتعمل،
# فكان فيه كحلي وأصفر بتوعه هو (12203D / E8B923) قريبين من الرسمي بس مش
# هو. دلوقتي مصدر واحد للحقيقة: الواجهة والورق بيشربوا من نفس البئر.
#
# قاعدة الدليل الذهبية محفوظة هنا برضو: الحروف فوق الحقل الأصفر دايمًا
# Ink (9.67:1) مش كحلي، والأبيض فوق Navy (12.31:1).
#
# openpyxl عايز الهكس من غير "#"، و reportlab عايزه بيها — فبنخزّن الصيغة
# القصيرة وبنضيف "#" عند الرسم.
# --------------------------------------------------------------------------


def _hex6(token):
    """لون براند بصيغة ‎RRGGBB‎ (الصيغة اللي openpyxl بيفهمها)."""
    return BRAND[token].lstrip("#").upper()


NAVY = _hex6("navy")        # #212F70 — شريط أسماء الأعمدة، الحروف البارزة
INK = _hex6("ink")          # #1B254B — الحروف فوق الحقل الأصفر ونص الجدول
YELLOW = _hex6("yellow")    # #FECA05 — بانر العنوان (الحقل الأصفر)
WHITE = _hex6("white")
CREAM = _hex6("cream")      # #F3F3ED — الصف المظلل في الجدول المتبدّل
MIST = _hex6("mist")        # #D9D9D4 — حدود الخانات والخطوط الفاصلة

# python-docx بياخد ‎RGBColor‎ مش سترنج، فبنحوّل مرة واحدة هنا
_WORD_INK = RGBColor.from_string(INK)
_WORD_NAVY = RGBColor.from_string(NAVY)
_WORD_WHITE = RGBColor.from_string(WHITE)

# --------------------------------------------------------------------------
# اللوجو على الورق — نفس ماستر الـ lockup الرسمي اللي الواجهة بتستخدمه، من
# ‎static/brand/‎ زي ما هو. الدليل (ص 06 · Logo rules) بيمنع إعادة التلوين
# أو التنميط أو القص: إحنا بنغيّر المقاس بس وبنختار النسخة حسب السطح —
#   ورق أبيض أو الحقل الأصفر  →  الشخصية كحلي  →  النسخة "light"
#   شريط كحلي/غامق            →  الشخصية صفرا  →  النسخة "dark"
# --------------------------------------------------------------------------


def _logo_file(surface="light"):
    """مسار ماستر الـ lockup، أو ‎None‎ لو الأصل مش موجود.

    التقرير نفسه أهم من اللوجو: لو الأصل ناقص لأي سبب بنكمّل التصدير من
    غيره بدل ما شغل المستخدم كله يقع على استيراد صورة.
    """
    path = lockup_master_path(surface)
    return path if os.path.exists(path) else None

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
        SELECT s.id as scene_id, s.scene_number, s.scene_suffix, s.episode_number, s.int_ext, s.day_night,
               s.notes as scene_notes, l.name as location_name, lv.variant_name
        FROM scenes s
        LEFT JOIN location_variants lv ON s.location_variant_id = lv.id
        LEFT JOIN locations l ON lv.location_id = l.id
        WHERE s.project_id = ?
        ORDER BY """ + _EPISODE_ORDER + """
    """, (project_id,))

    rows = []
    for sc in scenes:
        shots = fetch_all(
            "SELECT * FROM shots WHERE scene_id=? ORDER BY shot_number", (sc["scene_id"],)
        )
        location_label = sc["location_name"] or ""
        # «الشكل الأساسي» هي الحالة الافتراضية اللي الاستيراد بيعملها — مش
        # بتضيف أي معلومة للتقرير، فبنكتب اسم المكان لوحده.
        if sc["variant_name"] and sc["variant_name"] != "الشكل الأساسي":
            location_label = f"{location_label} - {sc['variant_name']}" if location_label else sc["variant_name"]

        if not shots:
            rows.append({
                "scene_number": scene_label(sc),
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
                "scene_number": scene_label(sc),
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
# خانات بتحتوي اسم علم (شخصية/مكان/ديكور) - المستخدم عايزها بولد زي الأرقام
_BOLD_NAME_KEYS = {
    "name", "location", "decor", "characters", "main_characters",
    "secondary_characters", "locations",
}
_THIN_BORDER = Border(*(Side(style="thin", color=MIST) for _ in range(4)))

# ارتفاع اللوجو جوه البانر الأصفر بالبكسل — البانر نفسه 60px (26+20+14)،
# فبنسيب هامش بسيط فوق وتحت بدل ما يلزق في حرف الجدول
_EXCEL_LOGO_H_PX = 46


def _place_excel_logo(ws):
    """بيحط ماستر اللوجو فوق البانر الأصفر في أول الورقة.

    الورقة ‎rightToLeft‎، يعني إكسل بيقلب الشبكة نفسها وعمود A بيبقى في
    أقصى اليمين — فالمرساة ‎A1‎ بتوقّع اللوجو في ركن البداية بالنسبة للقارئ
    العربي، بعيد عن العنوان المتوسّط. والنسخة "light" لأن الحقل الأصفر
    بياخد الشخصية الكحلي (الدليل ص 06).

    الصورة عائمة فوق الخانات المدموجة، فمش بتزق أي صف ولا بتكسر تنسيق
    الجدول تحتها.
    """
    path = _logo_file("light")
    if not path:
        return
    try:
        from openpyxl.drawing.image import Image as XLImage
        img = XLImage(path)
    except Exception:
        # openpyxl بيحتاج Pillow عشان يقرا أبعاد الصورة — لو مش متسطّب
        # بنكمّل من غير لوجو بدل ما التصدير كله يفشل
        return
    img.height = _EXCEL_LOGO_H_PX
    img.width = round(_EXCEL_LOGO_H_PX * MASTER_ASPECT)
    img.anchor = "A1"
    ws.add_image(img)


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
    # فوق الحقل الأصفر الحروف Ink مش Navy — ده نص الدليل (ص 05)، وبيدي
    # 9.67:1 بدل 7.4:1
    title_font = Font(color=INK, bold=True, size=16)
    subtitle_font = Font(color=INK, bold=True, size=12)
    version_font = Font(color=INK, size=8, italic=True)
    title_fill = PatternFill(start_color=YELLOW, end_color=YELLOW, fill_type="solid")

    n_cols = len(columns)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)
    # الإيموجي بيتحول لعلامة استفهام في إكسل لأن خط Calibri مش بيدعمه، فبنسيبه للواجهة بس
    title_cell = ws.cell(row=1, column=1, value=report_name)
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

    _place_excel_logo(ws)

    header_row = 5
    for col_idx, (key, label, width) in enumerate(columns, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=label)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = _THIN_BORDER
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
            cell.border = _THIN_BORDER
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
            elif key in _BOLD_NAME_KEYS:
                cell.alignment = Alignment(horizontal="right", vertical="top", wrap_text=True)
                cell.font = Font(bold=True)
            else:
                cell.alignment = Alignment(horizontal="right", vertical="top", wrap_text=True)
            # صفوف متبدلة الألوان (كريم البراند / أبيض) عشان العين تتابع
            # السطر بسهولة في الأوراق الطويلة
            if r % 2 == 0:
                cell.fill = PatternFill(start_color=CREAM, end_color=CREAM, fill_type="solid")
            else:
                cell.fill = PatternFill(start_color=WHITE, end_color=WHITE, fill_type="solid")

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
    import repo  # متأخر: التصدير بيتنادى من غير Streamlit في الاختبارات
    characters = fetch_all(
        "SELECT * FROM characters WHERE project_id=? ORDER BY id", (project_id,)
    )
    # الرقم = رقم الكاست لو متحط (نفس رقم التفريغ والجدول)؛ الترشيح = الممثل/ة
    # المتعاقد أو المرشحين؛ عدد الأيام = أيام الشغل من جدول التصوير.
    cast = repo.cast_by_character(project_id)
    work_days = {r["character_id"]: r["work_days"] for r in repo.day_out_of_days(project_id)["rows"]}
    order = {cid: i for i, cid in enumerate(cast)}
    characters = sorted(characters, key=lambda c: order.get(c["id"], len(order)))
    rows = []
    for idx, ch in enumerate(characters, start=1):
        ce = cast.get(ch["id"], {})
        if ce.get("actor"):
            nomination = ce["actor"]["name"]
        else:
            nomination = "، ".join(p["name"] for p in ce.get("shortlist", []))
            if nomination:
                nomination += " (مرشح)"
        scene_rows = fetch_all("""
            SELECT DISTINCT s.scene_number, s.scene_suffix, s.episode_number, l.name AS location_name
            FROM scene_characters sch
            JOIN scenes s ON sch.scene_id = s.id
            LEFT JOIN location_variants lv ON s.location_variant_id = lv.id
            LEFT JOIN locations l ON lv.location_id = l.id
            WHERE sch.character_id = ?
            ORDER BY s.scene_number
        """, (ch["id"],))
        scene_numbers = _scene_labels(scene_rows)   # 3/12 في المسلسل
        location_names = sorted({r["location_name"] for r in scene_rows if r["location_name"]})
        rows.append({
            "number": ce.get("cast_number") or idx,
            "name": ch["name"],
            "description": ch["personality_notes"] or "",
            "nomination": nomination,
            "scene_count": len(scene_numbers),
            "scene_numbers": "، ".join(str(n) for n in scene_numbers),
            "day_count": work_days.get(ch["id"], ""),
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


def _scene_labels(rows):
    """أرقام المشاهد بالترتيب ومن غير تكرار، بنفس scene_label (3/12 في
    المسلسل). العد بالمشهد نفسه مش بالرقم بس: مشهد 1 في الحلقة 1 ومشهد 1 في
    الحلقة 2 مشهدين."""
    ordered = sorted(rows, key=lambda r: (r["episode_number"] is None, r["episode_number"] or 0,
                                          r["scene_number"], r["scene_suffix"] or ""))
    return list(dict.fromkeys(scene_label(r) for r in ordered))


_EPISODE_ORDER = "CASE WHEN s.episode_number IS NULL THEN 1 ELSE 0 END, s.episode_number, s.scene_number"


def _numbered_names(rows):
    """"1- سلمى"، "4- سامي"... بترتيب رقم الكاست، واللي مالوش رقم بالاسم آخر
    القايمة - نفس الأرقام اللي في جدول التصوير والكول شيت."""
    rows = {(r["name"], r["cast_number"]) for r in rows}
    ordered = sorted(rows, key=lambda r: (r[1] is None, r[1] or 0, r[0]))
    return [f"{n}- {name}" if n else name for name, n in ordered]


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
        WHERE s.project_id=? ORDER BY """ + _EPISODE_ORDER + """
    """, (project_id,))
    rows = []
    for idx, sc in enumerate(scenes, start=1):
        # المصدر الأساسي لشخصيات وإكسسوارات المشهد هو scene_characters/
        # scene_props (مسجلة من وقت الاستيراد أو الإضافة اليدوية في تبويب
        # السكريبت) - ده اللي بيخلي التقرير ده يتملى بالداتا فعليًا حتى لو
        # لسه مفيش لقطات مفرّغة للمشهد
        char_rows = fetch_all("""
            SELECT DISTINCT ch.name, ch.role_type, ch.cast_number
            FROM scene_characters sch
            JOIN characters ch ON sch.character_id = ch.id
            WHERE sch.scene_id = ?
        """, (sc["id"],))
        main_chars = _numbered_names(r for r in char_rows if r["role_type"] in _MAIN_ROLE_TYPES)
        secondary_chars = _numbered_names(r for r in char_rows if r["role_type"] not in _MAIN_ROLE_TYPES)
        prop_rows = fetch_all("""
            SELECT DISTINCT p.name
            FROM scene_props sp
            JOIN props p ON sp.prop_id = p.id
            WHERE sp.scene_id = ?
        """, (sc["id"],))
        accessories = sorted({r["name"] for r in prop_rows})
        location_label = sc["location_name"] or ""
        # «الشكل الأساسي» هي الحالة الافتراضية اللي الاستيراد بيعملها — مش
        # بتضيف أي معلومة للتقرير، فبنكتب اسم المكان لوحده.
        if sc["variant_name"] and sc["variant_name"] != "الشكل الأساسي":
            location_label = f"{location_label} - {sc['variant_name']}" if location_label else sc["variant_name"]
        rows.append({
            "number": idx,
            "decor": "",
            "location": location_label,
            "scene": scene_label(sc),
            "day_night": sc["day_night"] or "",
            "pages": "",
            "situation": sc["notes"] or "",
            "main_characters": "، ".join(main_chars),
            "secondary_characters": "، ".join(secondary_chars),
            "accessories": "، ".join(accessories),
            "notes": "",
        })
    return _build_generic_excel("التفريغ العام", "التفريغ العام", project, GENERAL_BREAKDOWN_COLUMNS, rows)


# ---------- كشف الملابس (P10) ----------
WARDROBE_SHEET_COLUMNS = [
    ("character", "الشخصية", 18),
    ("actor", "الممثل/ة", 18),
    ("change", "الغيار", 16),
    ("item", "القطعة", 20),
    ("category", "النوع", 12),
    ("color", "اللون", 10),
    ("material", "الخامة", 10),
    ("size", "المقاس", 8),
    ("source", "المصدر", 10),
    ("multiples", "النسخ", 7),
    ("story_state", "الحالة في الحكاية", 14),
    ("cost", "التكلفة", 10),
    ("status", "التجهيز", 12),
    ("scenes", "المشاهد", 26),
    ("notes", "ملاحظات", 22),
]


def build_wardrobe_sheet_excel(project, project_id, fetch_all):
    """كشف الملابس: كل قطعة بغيارها وشخصيتها وممثلها، والمشاهد اللي الغيار
    متحدد فيها (3/12 في المسلسل). الغيار اللي لسه مالوش قطع بيطلع سطر لوحده
    عشان يبان إنه ناقص، مش يختفي."""
    import repo  # متأخر زي كشف الشخصيات
    cast = repo.cast_by_character(project_id)
    scenes_by_look = {}
    for r in fetch_all("""
        SELECT x.look_id, s.scene_number, s.scene_suffix, s.episode_number
        FROM scene_character_looks x JOIN scenes s ON s.id = x.scene_id
        WHERE s.project_id = ?
    """, (project_id,)):
        scenes_by_look.setdefault(r["look_id"], []).append(r)
    items_by_look = {}
    for it in repo.wardrobe_items_of_project(project_id):
        items_by_look.setdefault(it["look_id"], []).append(it)
    changes = sorted(repo.wardrobe_changes(project_id), key=lambda c: (
        c["cast_number"] is None, c["cast_number"] or 0, c["character_id"], c["change_number"] or 0))
    rows = []
    for ch in changes:
        ce = cast.get(ch["character_id"]) or {}
        base = {
            "character": (f"#{ch['cast_number']} " if ch["cast_number"] else "") + ch["character_name"],
            "actor": (ce.get("actor") or {}).get("name", ""),
            "change": repo.change_label(ch),
            "scenes": "، ".join(_scene_labels(scenes_by_look.get(ch["id"], []))),
        }
        items = items_by_look.get(ch["id"]) or [None]
        for it in items:
            row = dict(base)
            if it:
                row.update({
                    "item": it["item_name"], "category": it["category"] or "", "color": it["color"] or "",
                    "material": it["material"] or "", "size": it["size"] or "", "source": it["source"] or "",
                    "multiples": it["multiples"] or 1, "story_state": it["story_state"] or "",
                    "cost": it["cost"] if it["cost"] is not None else "", "status": it["status"] or "",
                    "notes": it["notes"] or "",
                })
            else:
                row.update({"item": "— لسه مفيش قطع —"})
            rows.append(row)
    return _build_generic_excel("كشف الملابس", "كشف الملابس", project, WARDROBE_SHEET_COLUMNS, rows)


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
            SELECT s.scene_number, s.scene_suffix, s.episode_number
            FROM scenes s
            JOIN location_variants lv ON s.location_variant_id = lv.id
            WHERE lv.location_id = ?
        """, (loc["id"],))
        scene_numbers = _scene_labels(scene_rows)
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


# ---------- كشف الإكسسوار ----------
PROPS_SHEET_COLUMNS = [
    ("number", "الرقم", 8),
    ("name", "الإكسسوار", 24),
    ("owner_character", "تابع لشخصية", 22),
    ("continuity", "حساس للاستمرارية", 16),
    ("scene_count", "عدد المشاهد", 12),
    ("scene_numbers", "ارقام المشاهد", 30),
]


def build_props_sheet_excel(project, project_id, fetch_all):
    """كشف الإكسسوار: ورقة واحدة لكل إكسسوار، بعدد وأرقام المشاهد اللي
    ظاهر فيها (من ربط scene_props)، والشخصية التابع لها لو محدد، وعلامة
    لو الإكسسوار حساس للاستمرارية (يحتاج انتباه خاص وقت التصوير)."""
    props = fetch_all(
        "SELECT * FROM props WHERE project_id=? ORDER BY id", (project_id,)
    )
    character_name_by_id = {
        c["id"]: c["name"]
        for c in fetch_all("SELECT id, name FROM characters WHERE project_id=?", (project_id,))
    }
    rows = []
    for idx, prop in enumerate(props, start=1):
        scene_rows = fetch_all("""
            SELECT s.scene_number, s.scene_suffix, s.episode_number FROM scene_props sp
            JOIN scenes s ON sp.scene_id = s.id
            WHERE sp.prop_id = ?
        """, (prop["id"],))
        scene_numbers = _scene_labels(scene_rows)
        rows.append({
            "number": idx,
            "name": prop["name"],
            "owner_character": character_name_by_id.get(prop["character_id"], ""),
            "continuity": "نعم" if prop["continuity_sensitive"] else "",
            "scene_count": len(scene_numbers),
            "scene_numbers": "، ".join(str(n) for n in scene_numbers),
        })
    return _build_generic_excel("كشف الإكسسوار", "كشف الإكسسوار", project, PROPS_SHEET_COLUMNS, rows)


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


def _shade_cell(cell, hex6):
    """تظليل خانة في وورد. python-docx مفيهوش API للتظليل، فبنحقن عنصر
    ‎w:shd‎ في خصائص الخانة بنفسنا زي ما بنعمل مع ‎w:bidi‎."""
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex6)
    cell._tc.get_or_add_tcPr().append(shd)


def _brand_table_borders(table, hex6):
    """حدود الجدول بلون البراند بدل الأسود اللي ‎Table Grid‎ بيجي بيه.

    نفس السُمك (نص نقطة = 4 ثُمن النقطة في وحدة وورد) في الست نواحي عشان
    الشبكة تبقى موحّدة زي جدول الإكسل بالظبط."""
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement("w:%s" % edge)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), hex6)
        borders.append(el)
    table._tbl.tblPr.append(borders)


def _add_word_logo(document):
    """ماستر اللوجو متوسّط فوق عنوان المستند، على الورق الأبيض — يعني
    النسخة "light" (الشخصية كحلي). الارتفاع 1.1 سم، والعرض بيتحسب من نسبة
    الماستر لوحده عشان ميتمطّش."""
    path = _logo_file("light")
    if not path:
        return
    logo_p = document.add_paragraph()
    logo_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    logo_p.add_run().add_picture(path, height=Cm(1.1))


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

    _add_word_logo(document)

    title = document.add_paragraph()
    _set_rtl_center(title)
    # اتشال الإيموجي 🎬: اللوجو الرسمي بقى فوق العنوان، والدليل بيمنع أي
    # علامة بديلة تقف جنبه
    run = title.add_run("تفريغ اللقطات (Shooting List)")
    run.bold = True
    run.font.size = Pt(20)
    run.font.color.rgb = _WORD_INK

    subtitle = document.add_paragraph()
    _set_rtl_center(subtitle)
    sub_run = subtitle.add_run(_project_type_name_line(project))
    sub_run.bold = True
    sub_run.font.size = Pt(13)
    sub_run.font.color.rgb = _WORD_INK

    version_p = document.add_paragraph()
    _set_rtl_center(version_p)
    v_run = version_p.add_run(_version_line(project))
    v_run.italic = True
    v_run.font.size = Pt(8)
    v_run.font.color.rgb = _WORD_NAVY

    document.add_paragraph()

    headers = [label for _key, label, _width in COLUMNS]
    table = document.add_table(rows=1, cols=len(headers))
    # كان ‎Light Grid Accent 1‎ — ستايل أوفيس الجاهز بلونه الأزرق الفاتح،
    # وده كان بيخلي نسخة الوورد هي التقرير الوحيد اللي مش بلون البراند جنب
    # الإكسل والـ PDF. ‎Table Grid‎ ستايل محايد، والألوان بنحطها بنفسنا من
    # نفس التوكنز: شريط كحلي بحروف بيضا، وصفوف متبدلة بالكريم.
    table.style = "Table Grid"
    _brand_table_borders(table, MIST)
    for i, label in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = label
        _shade_cell(cell, NAVY)
        for p in cell.paragraphs:
            _set_rtl(p)
            for r in p.runs:
                r.bold = True
                r.font.color.rgb = _WORD_WHITE

    for row_idx, row in enumerate(rows):
        cells = table.add_row().cells
        for i, (key, _label, _width) in enumerate(COLUMNS):
            value = row.get(key, "")
            cells[i].text = str(value) if value != "" else "—"
            if row_idx % 2 == 1:
                _shade_cell(cells[i], CREAM)
            is_bold_cell = key in {"scene_number", "shot_number"} | _DIALOGUE_KEYS
            for p in cells[i].paragraphs:
                _set_rtl(p)
                for r in p.runs:
                    r.font.color.rgb = _WORD_INK
                    if is_bold_cell:
                        r.bold = True

    buf = BytesIO()
    document.save(buf)
    return buf.getvalue()


# ---------- تصدير PDF ----------
# النص العربي في مكتبة reportlab محتاج إعادة تشكيل الحروف (ligation) وترتيب
# ثنائي الاتجاه (bidi) يدويًا قبل الرسم، لأن reportlab أصلًا مبني للغات LTR.
# وبرضو محتاج خط يدعم العربي فعليًا - كنا قبل كده بنفتش على Tahoma/Arial في
# مسارات ويندوز (C:\Windows\Fonts)، وده كان شغال بس على جهاز المطور بويندوز؛
# على السيرفر (لينكس) المسارات دي مش موجودة خالص، فالتسجيل كان بيفشل بصمت
# ويرجع Helvetica اللي مفيهوش حرف عربي واحد - يعني كل تصدير PDF فيه عربي كان
# طالع فاضي أو حروف مش مفهومة.
#
# الحل: نستضيف خط عربي كامل جوه الريبو نفسه (زي ما إحنا مستضيفين Cairo و
# Readex Pro لواجهة الموقع في static/fonts) بدل ما نفتش على مسارات نظام
# التشغيل. اخترنا Amiri (SIL OFL 1.1 - مرخّص للتوزيع الحر) لأنه، على عكس
# نسخة Cairo المتغيّرة (variable font) المستضافة للويب، بيغطي حروف "أشكال
# العرض العربية" (Arabic Presentation Forms، النطاقات FB50-FDFF و FE70-FEFF)
# اللي مكتبة arabic_reshaper بترجّع بيها النص بعد التشكيل - وده بالظبط اللي
# reportlab محتاجه لأنه بيرسم كل حرف بالـ code point بتاعه من غير أي معالجة
# OpenType shaping (HarfBuzz) زي المتصفح. جرّبنا Cairo الأول ولقيناه ناقص
# غطاء كبير من النطاقات دي (حروف زي الألف والراء المنفصلة بتطلع فاضية)،
# فمكانه فضل مع خطوط الويب وده ملف مستقل مخصوص للتصدير.
_ARABIC_FONT_DIR = os.path.join(os.path.dirname(__file__), "static", "fonts")
_ARABIC_FONT_PATH = os.path.join(_ARABIC_FONT_DIR, "Amiri-Regular.ttf")
_ARABIC_BOLD_FONT_PATH = os.path.join(_ARABIC_FONT_DIR, "Amiri-Bold.ttf")
_ARABIC_FONT_NAME = None
_ARABIC_BOLD_FONT_NAME = None


def _register_arabic_font():
    """بيسجل خط Amiri (عادي وبولد) المستضاف جوه الريبو في static/fonts عشان
    التصدير يشتغل صح على أي سيرفر - من غير ما نعتمد على خطوط نظام تشغيل معين،
    ومن غير fallback صامت لخط زي Helvetica مفيهوش عربي أصلًا."""
    global _ARABIC_FONT_NAME, _ARABIC_BOLD_FONT_NAME
    if _ARABIC_FONT_NAME:
        return _ARABIC_FONT_NAME, _ARABIC_BOLD_FONT_NAME

    if not os.path.exists(_ARABIC_FONT_PATH):
        raise FileNotFoundError(
            f"خط العربي الأساسي مش موجود: {_ARABIC_FONT_PATH} - "
            "من غيره تصدير PDF فيه نص عربي هيطلع فاضي أو تالف."
        )
    pdfmetrics.registerFont(TTFont("CFArabic", _ARABIC_FONT_PATH))
    _ARABIC_FONT_NAME = "CFArabic"

    if os.path.exists(_ARABIC_BOLD_FONT_PATH):
        pdfmetrics.registerFont(TTFont("CFArabicBold", _ARABIC_BOLD_FONT_PATH))
        _ARABIC_BOLD_FONT_NAME = "CFArabicBold"
    else:
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
    logo_height = 30  # نقطة — جوه بلوك العنوان، مش بيزوّده

    buf = BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=(page_w, page_h))

    def draw_logo():
        """اللوجو في بلوك العنوان، ناحية اليمين — بداية القراءة بالعربي.
        reportlab بياخد مسار الملف على طول (مش محتاج ‎data:‎ URI زي
        المتصفح)، و‎mask="auto"‎ بيخلي الشفافية في الـ PNG تفضل شفافة بدل
        ما تطلع مربع أسود."""
        path = _logo_file("light")   # الصفحة بيضا → الشخصية كحلي
        if not path:
            return
        w = logo_height * MASTER_ASPECT
        c.drawImage(
            path, page_w - margin - w, page_h - margin - logo_height - 6,
            width=w, height=logo_height, mask="auto",
        )

    def draw_title_block():
        draw_logo()
        c.setFillColor(colors.HexColor(f"#{INK}"))
        c.setFont(bold_font_name, 15)
        c.drawCentredString(page_w / 2, page_h - margin - 14, _ar("تفريغ اللقطات (Shooting List)"))
        c.setFont(bold_font_name, 10.5)
        c.drawCentredString(page_w / 2, page_h - margin - 29, _ar(_project_type_name_line(project)))
        c.setFillColor(colors.HexColor(f"#{NAVY}"))
        c.setFont(font_name, 7.5)
        c.drawCentredString(page_w / 2, page_h - margin - 42, _ar(_version_line(project)))

    def draw_header_row(top_y):
        c.setFillColor(colors.HexColor(f"#{NAVY}"))
        c.rect(margin, top_y - header_height, usable_w, header_height, stroke=0, fill=1)
        c.setFillColor(colors.HexColor(f"#{WHITE}"))
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
            c.setFillColor(colors.HexColor(f"#{CREAM}"))
            c.rect(margin, y - row_height, usable_w, row_height, stroke=0, fill=1)

        # نص الجدول Ink مش أسود خام — 14.86:1 على الأبيض، وبيخلي الورقة
        # كلها في نفس عيلة اللون بتاعة البراند
        c.setFillColor(colors.HexColor(f"#{INK}"))
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

        c.setStrokeColor(colors.HexColor(f"#{MIST}"))
        c.line(margin, y - row_height, page_w - margin, y - row_height)
        y -= row_height

    c.save()
    return buf.getvalue()


# ---------- تقرير البناء الدرامي (dramaturgy.py) ----------
# المحتوى كله جاي جاهز ومترجم من dramaturgy.to_sections() — هنا الشكل بس.
# reportlab و python-docx مابيرسموش SVG، فمنحنى التوتر بيترسم تاني كصورة PNG
# (PIL) بنفس منطق dramaturgy.render_svg، ونفس الصورة بتدخل الوورد والـ PDF.

_DRAMA_CURVE_W, _DRAMA_CURVE_H = 1800, 560


def dramaturgy_curve_png(report, lang="ar"):
    """منحنى التوتر كـ PNG: في العربي بداية القصة (العرض) على اليمين. بنرسم بـ
    BASIC layout ونشكّل العربي بـ _ar() بنفسنا — لو سبنا raqm يشكّله كمان
    النص هيتقلب مرتين."""
    from PIL import Image, ImageDraw, ImageFont
    import dramaturgy

    width, height = _DRAMA_CURVE_W, _DRAMA_CURVE_H
    curve = report.get("tension_curve") or []
    n = len(curve)
    img = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    rtl = lang == "ar"
    pad_l, pad_r, pad_t, pad_b = 30, 30, 30, 70
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b

    def x_of(i):
        frac = i / (n - 1) if n > 1 else 0.5
        return pad_l + ((1 - frac) if rtl else frac) * plot_w

    def y_of(v):
        return pad_t + (1 - float(v) / 100) * plot_h

    try:
        font = ImageFont.truetype(_ARABIC_BOLD_FONT_PATH if os.path.exists(_ARABIC_BOLD_FONT_PATH)
                                  else _ARABIC_FONT_PATH, 26, layout_engine=ImageFont.Layout.BASIC)
    except OSError:
        font = ImageFont.load_default()
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    labels = []
    stage_colors = getattr(dramaturgy, "_STAGE_COLORS", {})
    for st_ in (report.get("stages") or []) if n else []:
        # حدود الشريط في نص المسافة بين المشهدين، عشان المراحل تلزق في بعض
        # من غير فراغات، ومرحلة المشهد الواحد تبقى شريط باين مش خط
        half = (plot_w / (n - 1) / 2) if n > 1 else plot_w / 2
        x1, x2 = x_of(st_["from_index"] - 1), x_of(st_["to_index"] - 1)
        left = max(pad_l, min(x1, x2) - half)
        right = min(pad_l + plot_w, max(x1, x2) + half)
        hexc = stage_colors.get(st_["stage"], "#888888").lstrip("#")
        rgb = tuple(int(hexc[i:i + 2], 16) for i in (0, 2, 4))
        od.rectangle([left, pad_t, right, pad_t + plot_h], fill=rgb + (38,))
        labels.append(((left + right) / 2, rgb, st_.get("label_ar") if rtl else st_.get("label_en")))
    img = Image.alpha_composite(img, overlay)
    d = ImageDraw.Draw(img)
    mist = tuple(int(MIST[i:i + 2], 16) for i in (0, 2, 4))
    for v in (0, 50, 100):
        d.line([(pad_l, y_of(v)), (pad_l + plot_w, y_of(v))], fill=mist, width=1)
    pts = [(x_of(i), y_of(pt["value"])) for i, pt in enumerate(curve)]
    if len(pts) > 1:
        d.line(pts, fill=(192, 70, 60), width=5, joint="curve")
    for x, y in pts:
        d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(192, 70, 60))
    for cx, rgb, label in labels:
        text = _ar(label) if rtl else str(label or "")
        tw = d.textlength(text, font=font)
        x = min(max(cx - tw / 2, 4), width - tw - 4)      # الاسم مايتقصّش على الحافة
        d.text((x, height - pad_b + 18), text, font=font, fill=rgb)
    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _drama_title(lang):
    return "تقرير البناء الدرامي" if lang == "ar" else "Dramatic-Structure Report"


def _drama_script_title(script_name):
    """اسم السيناريو من غير امتداد الملف: ‎"الحلقة الاولى.pdf"‎ في سطر عربي
    بيتعرض ‎"pdf.الحلقة الاولى"‎ وده بيلخبط القارئ."""
    name = str(script_name or "").strip()
    stem, dot, ext = name.rpartition(".")
    if dot and stem and ext.lower() in ("pdf", "docx", "doc", "txt", "json", "fdx", "md"):
        name = stem
    return name or "—"


def _drama_blocks(report, lang):
    """(عنوان، [فقرات]) — نقطة الضعف بتتكتب في سطور (المشكلة / ليه مهم /
    إزاي نقويه) بدل سطر واحد طويل متقسّم بـ "|"، أسهل في القراية على الورق."""
    import dramaturgy
    out = []
    for sec in dramaturgy.to_sections(report, lang=lang):
        paras = [p.replace(" | ", "\n") for p in sec["paragraphs"]]
        out.append((sec["heading"], paras))
    return out


def build_dramatic_structure_pdf(report, script_name, lang="ar"):
    font_name, bold_font_name = _register_arabic_font()
    rtl = lang == "ar"
    page_w, page_h = A4
    margin = 40
    usable_w = page_w - 2 * margin
    body_size, head_size, line_h = 10.5, 13, 15
    wrap_chars = 88 if rtl else 95

    buf = BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=(page_w, page_h))
    y = page_h - margin

    def text_at(txt, font, size, color=INK):
        c.setFont(font, size)
        c.setFillColor(colors.HexColor(f"#{color}"))
        if rtl:
            c.drawRightString(page_w - margin, y, txt)
        else:
            c.drawString(margin, y, txt)

    def need(h):
        nonlocal y
        if y - h < margin:
            c.showPage()
            y = page_h - margin

    # بلوك العنوان: اللوجو ناحية بداية القراءة، والعنوان واسم السيناريو في النص
    path = _logo_file("light")
    if path:
        w = 28 * MASTER_ASPECT
        c.drawImage(path, (page_w - margin - w) if rtl else margin, y - 28,
                    width=w, height=28, mask="auto")
    c.setFillColor(colors.HexColor(f"#{INK}"))
    c.setFont(bold_font_name, 16)
    c.drawCentredString(page_w / 2, y - 16, _ar(_drama_title(lang)))
    c.setFont(bold_font_name, 11)
    c.drawCentredString(page_w / 2, y - 32, _ar(_drama_script_title(script_name)))
    c.setFillColor(colors.HexColor(f"#{NAVY}"))
    c.setFont(font_name, 8)
    c.drawCentredString(page_w / 2, y - 45, _ar(_drama_meta_line(report, lang)))
    y -= 62

    # منحنى التوتر بعرض الصفحة
    from reportlab.lib.utils import ImageReader
    img_h = usable_w * _DRAMA_CURVE_H / _DRAMA_CURVE_W
    c.drawImage(ImageReader(BytesIO(dramaturgy_curve_png(report, lang))), margin, y - img_h,
                width=usable_w, height=img_h)
    y -= img_h + 18

    for heading, paras in _drama_blocks(report, lang):
        need(head_size + line_h * 2)
        c.setFillColor(colors.HexColor(f"#{YELLOW}"))
        c.rect(margin, y - 5, usable_w, head_size + 8, stroke=0, fill=1)
        text_at(_ar(heading), bold_font_name, head_size)
        y -= head_size + 12
        for para in paras:
            lines = []
            for part in para.split("\n"):
                lines.extend(_wrap_lines(part, wrap_chars, max_lines=40))
            for j, ln in enumerate(lines):
                need(line_h)
                # النص بعد _ar مترتب بصريًا: آخر حرف في السترنج هو أقصى
                # اليمين، فالبولت في العربي بيتحط في الآخر مش الأول
                if j == 0:
                    ln = f"{ln} •" if rtl else f"• {ln}"
                text_at(ln, font_name, body_size)
                y -= line_h
            y -= 4
        y -= 6
        c.setStrokeColor(colors.HexColor(f"#{MIST}"))
        c.line(margin, y + 4, page_w - margin, y + 4)

    c.save()
    return buf.getvalue()


def _drama_meta_line(report, lang):
    meta = report.get("meta") or {}
    when = (meta.get("generated_at") or "")[:10] or date.today().isoformat()
    n = report.get("scene_count") or 0
    if lang == "ar":
        return f"{n} مشهد · اتعمل {when} · CimaFast STUDIO"
    return f"{n} scenes · generated {when} · CimaFast STUDIO"


def build_dramatic_structure_word(report, script_name, lang="ar"):
    rtl = lang == "ar"
    document = docx.Document()
    section = document.sections[0]
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, side, Cm(1.8))

    def align(p, center=False):
        if rtl:
            (_set_rtl_center if center else _set_rtl)(p)
        elif center:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    _add_word_logo(document)
    for text, size, bold, color in ((_drama_title(lang), 20, True, _WORD_INK),
                                    (_drama_script_title(script_name), 13, True, _WORD_INK),
                                    (_drama_meta_line(report, lang), 8, False, _WORD_NAVY)):
        p = document.add_paragraph()
        align(p, center=True)
        r = p.add_run(text)
        r.bold, r.font.size, r.font.color.rgb = bold, Pt(size), color

    pic = document.add_paragraph()
    pic.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pic.add_run().add_picture(BytesIO(dramaturgy_curve_png(report, lang)), width=Cm(17))

    for heading, paras in _drama_blocks(report, lang):
        # العنوان على شريط أصفر بحروف Ink — نفس قاعدة الدليل في الـ PDF
        table = document.add_table(rows=1, cols=1)
        table.style = "Table Grid"
        _brand_table_borders(table, YELLOW)
        cell = table.rows[0].cells[0]
        cell.text = heading
        _shade_cell(cell, YELLOW)
        for p in cell.paragraphs:
            align(p)
            for r in p.runs:
                r.bold, r.font.size, r.font.color.rgb = True, Pt(13), _WORD_INK
        for para in paras:
            for i, part in enumerate(para.split("\n")):
                p = document.add_paragraph()
                align(p)
                r = p.add_run(("• " if i == 0 else "") + part)
                r.font.size, r.font.color.rgb = Pt(10.5), _WORD_INK
                if i == 0 and len(para.split("\n")) > 1:
                    r.bold = True
        document.add_paragraph()

    buf = BytesIO()
    document.save(buf)
    return buf.getvalue()
