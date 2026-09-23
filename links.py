"""روابط مباشرة لشاشة معيّنة (H2): ‎/v1/?project=7&tab=scenes

الصفحة الرئيسية، التنبيهات، وبوستات الـ agents كلها بتفتح الشاشة المظبوطة بدل ما
اليوزر يدوّر. الملف ده مفيهوش Streamlit عشان يتختبر لوحده؛ app.py هو اللي بيطبّق
الرابط على الـ sidebar والتبويبات.
"""
from __future__ import annotations

from urllib.parse import urlencode

# ترتيب التبويبات في app.py، والمفتاح بتاع اسمها في i18n
TABS = {
    "import": "tab_import",
    "locations": "tab_locations",
    "characters": "tab_characters",
    "actors": "tab_actors",
    "props": "tab_props",
    "scenes": "tab_scenes",
    "shots": "tab_breakdown",
    "reports": "tab_dashboard",
    "settings": "tab_settings",
}


def _first(value):
    # st.query_params بيرجّع str؛ dict عادي من parse_qs بيرجّع list
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def parse(params):
    """(project_id أو None، tab أو None) — أي قيمة غلط بتتجاهل بدل ما توقّع الصفحة."""
    raw_project = _first(params.get("project"))
    raw_tab = _first(params.get("tab"))
    try:
        project_id = int(raw_project) if raw_project not in (None, "") else None
    except (TypeError, ValueError):
        project_id = None
    if project_id is not None and project_id <= 0:
        project_id = None
    tab = raw_tab if raw_tab in TABS else None
    return project_id, tab


def item(params):
    """H4: رقم العنصر اللي الرابط بيشاور عليه (‎&item=88‎)، أو None."""
    raw = _first(params.get("item"))
    try:
        value = int(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None
    return value if value and value > 0 else None


def screen(base, project_id=None, tab=None, item=None):
    """الرابط لشاشة: base هو عنوان التطبيق (مثلًا ‎/v1/ أو ‎../../).

    ‎item‎ (H4): عنصر واحد جوه التبويب — التبويب بيفتحه لوحده بدل ما اليوزر يدوّر."""
    query = {}
    if project_id is not None:
        query["project"] = int(project_id)
    if tab is not None:
        if tab not in TABS:
            raise ValueError(f"unknown tab: {tab}")
        query["tab"] = tab
    if item is not None and tab is not None:
        query["item"] = int(item)
    return f"{base}?{urlencode(query)}" if query else base
