"""اختبارات إصلاحات الواجهة السريعة — أسيرشن عادي، مفيش pytest.

    venv/bin/python tests/test_ux_quick_wins.py
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from database import next_free_number, scene_label  # noqa: E402

_results = []


def test(fn):
    _results.append(fn)
    return fn


def _app():
    return open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()


# --- الرقم الجاي --------------------------------------------------------------

@test
def test_empty_project_starts_at_one():
    assert next_free_number([]) == 1


@test
def test_suggests_one_past_the_highest():
    assert next_free_number([1, 2, 3]) == 4
    assert next_free_number(range(1, 166)) == 166


@test
def test_gaps_are_not_filled_in():
    # لو المستخدم مسح مشهد 2 من 1..3، الاقتراح 4 مش 2 — الرقم 2 ممكن يكون
    # متحجز في الورق عند الفريق.
    assert next_free_number([1, 3]) == 4


@test
def test_nulls_and_string_numbers_are_tolerated():
    assert next_free_number([None, "7", 2]) == 8


# --- رقم المشهد جوه النص العربي ------------------------------------------------

@test
def test_scene_label_itself_stays_free_of_bidi_marks():
    # export.py بيكتب ‎scene_label‎ في خلايا Excel و Word؛ علامات الاتجاه
    # المخفية هناك كانت هتبوّظ الترتيب والبحث.
    label = scene_label({"scene_number": 1, "scene_suffix": "A"})
    assert label == "1A"
    assert "⁦" not in label and "⁩" not in label


@test
def test_every_on_screen_scene_label_is_isolated():
    bare = re.findall(r"\{scene_label\(\w+\)\}", _app())
    assert not bare, f"scene_label shown without ltr(): {bare}"


# --- إنجليزي تايه في الواجهة العربي --------------------------------------------

@test
def test_no_multiselect_bypasses_the_arabic_placeholder():
    src = _app()
    direct = src.count("st.multiselect(")
    assert direct == 1, f"{direct} direct st.multiselect calls; only the wrapper may call it"


@test
def test_no_hardcoded_bilingual_sidebar_labels():
    assert "الحلقات | Episodes" not in _app()


# --- إعدادات الصفحة -------------------------------------------------------------

@test
def test_developer_toolbar_is_hidden():
    import tomllib
    cfg = tomllib.load(open(os.path.join(ROOT, ".streamlit", "config.toml"), "rb"))
    assert cfg.get("client", {}).get("toolbarMode") == "minimal"


@test
def test_dark_colour_scheme_is_declared():
    from theme import classic
    assert "color-scheme: dark" in classic.BASE_CSS


@test
def test_theme_colour_matches_the_configured_background():
    import tomllib
    from theme import inject
    cfg = tomllib.load(open(os.path.join(ROOT, ".streamlit", "config.toml"), "rb"))
    assert inject.THEME_COLOR.lower() == cfg["theme"]["backgroundColor"].lower()


class _Recorder:
    def __init__(self):
        self.blobs = []

    def markdown(self, body, **kw):
        self.blobs.append(body)

    def html(self, body, **kw):
        self.blobs.append((body, kw))


@test
def test_document_language_follows_the_interface():
    from theme import inject
    for lang in ("ar", "en"):
        rec = _Recorder()
        inject.inject_base(rec, "classic", lang=lang)
        scripts = [b for b in rec.blobs if isinstance(b, tuple)]
        assert len(scripts) == 1, "exactly one script element"
        body, kw = scripts[0]
        assert f"d.lang='{lang}'" in body
        assert kw.get("unsafe_allow_javascript") is True, "st.html drops scripts without it"


@test
def test_root_direction_is_left_alone():
    # Flipping <html dir> would mirror Streamlit's whole flex layout on top of
    # the per-element RTL rules — see _document_attrs.
    from theme import inject
    rec = _Recorder()
    inject.inject_base(rec, "classic", lang="ar")
    body = next(b for b in rec.blobs if isinstance(b, tuple))[0]
    assert ".dir" not in body and "setAttribute('dir'" not in body


@test
def test_unknown_language_falls_back_to_arabic():
    from theme import inject
    rec = _Recorder()
    inject.inject_base(rec, "classic", lang="fr';alert(1);'")
    body = next(b for b in rec.blobs if isinstance(b, tuple))[0]
    assert "d.lang='ar'" in body and "alert" not in body


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
