"""اختبارات جولة الواجهة التانية — أسيرشن عادي، مفيش pytest.

    venv/bin/python tests/test_ux_round2.py
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_results = []


def test(fn):
    _results.append(fn)
    return fn


def _app():
    """كل كود الواجهة: app.py + i18n + ui + views/*. اتقسم من app.py واحد."""
    import glob
    files = [os.path.join(ROOT, f) for f in ("app.py", "i18n.py", "ui.py")]
    files += sorted(glob.glob(os.path.join(ROOT, "views", "*.py")))
    return "\n".join(open(f, encoding="utf-8").read() for f in files)


def _view(name):
    return open(os.path.join(ROOT, "views", f"{name}.py"), encoding="utf-8").read()


@test
def test_exports_are_built_on_click_not_cached_by_counts():
    src = _app()
    assert "_export_cache_key" not in src, "count-keyed export cache is back — edits would download stale"
    assert 't("🔄 تحديث الملفات")' not in src, "the manual refresh button only existed to work around that cache"
    lazy = re.findall(r"data=_lazy\((\w+)\)", src)
    assert sorted(lazy) == sorted([
        "build_shot_list_excel", "build_shot_list_word", "build_shot_list_pdf",
        "build_characters_sheet_excel", "build_general_breakdown_excel",
        "build_locations_sheet_excel", "build_props_sheet_excel",
    ]), lazy


@test
def test_every_export_builder_accepts_the_lazy_signature():
    import inspect
    import export
    for name in re.findall(r"data=_lazy\((\w+)\)", _app()):
        params = list(inspect.signature(getattr(export, name)).parameters)
        assert params[:3] == ["project", "project_id", "fetch_all"], (name, params)


@test
def test_default_state_name_is_importable():
    # app.py strips it from labels; it used to be a local inside a function.
    import importer
    assert importer.DEFAULT_VARIANT == "الشكل الأساسي"


@test
def test_scene_edit_forms_are_not_all_rendered_by_default():
    tab = _view("scenes")
    assert 'selection_mode="multi-row"' in tab
    assert "_scenes_shown = []" in tab, "without a search or selection no edit forms should render"


@test
def test_each_library_has_search_before_its_add_row():
    for view, key in (("locations", "loc_search_"), ("characters", "char_search_"),
                      ("props", "prop_search_"), ("scenes", "scene_search_")):
        body = _view(view)
        assert key in body, f"{view}: no library search"
        assert body.index(key) < body.index("➕"), f"{view}: search should sit above the add row"


@test
def test_the_five_stage_cards_are_gone():
    src = _app()
    assert 'class="cf-stepper"' not in src
    assert 'class="cf-progress"' in src


@test
def test_library_editors_only_render_when_opened():
    # 556 forms were built on every click in production (16 s per rerun);
    # lazy expanders brought /v1 to 6 forms and 2.3 s.
    src = _app()
    for key in ("exp_loc_", "exp_char_", "exp_prop_", "exp_scene_", "exp_shot_"):
        i = src.index(f'key=f"{key}')
        line = src[src.rindex("\n", 0, i):src.index("\n", i)]
        assert 'on_change="rerun"' in line, f"{key} expander is not lazy"
        after = src[src.index("\n", i):src.index("\n", i) + 200]
        assert "if _lazy_exp.open:" in after, f"{key} body does not check .open"


@test
def test_app_is_split_into_views():
    # app.py was 2,959 lines holding every tab; each tab now has its own module
    # with one render(). If a tab creeps back into app.py this fails.
    app = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    assert len(app.splitlines()) < 900, len(app.splitlines())
    for view in ("import_tab", "locations", "characters", "props", "scenes", "shots", "reports", "project_settings"):
        # F2: rendered through _render(views.X, ...) so a refused write shows a message
        assert f"views.{view}.render(" in app or f"_render(views.{view}," in app, view
        assert "def render(" in _view(view), view


def main():
    failed = 0
    for fn in _results:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except Exception as exc:
            failed += 1
            print(f"  FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(_results) - failed}/{len(_results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
