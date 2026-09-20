"""اختبارات طبقة الشكل — أسيرشن عادي، مفيش pytest (زي باقي الاختبارات).

    venv/bin/python tests/test_theme.py

بيغطي تلات حاجات:
  1. حساب التباين نفسه صح (بنقارن بقيم WCAG معروفة)
  2. كل زوج (نص / أرضية) في التوكنز بيعدّي الحد الأدنى — في الوضعين
  3. الفلاج بيرجّع ‎classic‎ افتراضيًا، ومبيتقلبش من نفسه
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from theme import contrast as C  # noqa: E402
from theme import flag, glass, tokens  # noqa: E402

_results = []


def test(fn):
    _results.append(fn)
    return fn


# --------------------------------------------------------------------------
# 1) الحساب نفسه
# --------------------------------------------------------------------------

@test
def test_known_wcag_ratios():
    # أبيض على أسود = 21:1 بالتعريف
    assert round(C.ratio("#FFFFFF", "#000000"), 2) == 21.0
    # نفس اللون = 1:1
    assert round(C.ratio("#E8B923", "#E8B923"), 2) == 1.0
    # قيم مرجعية من بالتة البرنامج
    assert round(C.ratio("#F5F1E6", "#0B1220"), 2) == 16.59
    assert round(C.ratio("#E8B923", "#16233F"), 2) == 8.46


@test
def test_alpha_compositing():
    # 50% أبيض على أسود = رمادي نص
    assert C.over("rgba(255,255,255,0.5)", "#000000") == "#808080"
    # شفافية صفر = الأرضية زي ما هي
    assert C.over("rgba(255,255,255,0)", "#0B1220") == "#0B1220"
    # شفافية كاملة = اللون نفسه
    assert C.over("rgba(232,185,35,1)", "#0B1220") == "#E8B923"
    # الترميز بالـ hex بـ 8 خانات بيشتغل زي rgba
    assert C.over("#FFFFFF80", "#000000") == C.over("rgba(255,255,255,0.502)", "#000000")


@test
def test_background_must_be_opaque():
    try:
        C.ratio("rgba(255,255,255,0.5)", "#000000")
    except ValueError:
        return
    raise AssertionError("لازم يرفض يحسب تباين لون شفاف من غير تركيب")


# --------------------------------------------------------------------------
# 2) أزواج التصميم الفعلية
# --------------------------------------------------------------------------

def _pairs(mode):
    """كل زوج نص/أرضية في التصميم، محسوب بعد تركيب الزجاج على الأرضية.

    بناخد أغمق (أو أفتح) نقطة في الميش كأرضية عشان الحساب يبقى الحالة
    الأسوأ: الميش بيفتّح الأرضية في مناطق، فالتباين الحقيقي بيبقى أعلى أو
    مساوي لللي هنا.
    """
    p = tokens.MODES[mode]
    ground = p["ground_base"]
    reg = C.over(p["glass_regular"], ground)
    clear = C.over(p["glass_clear"], ground)
    opaque = p["glass_opaque"]
    gold = C.over(p["gold_glass"], ground)
    return [
        ("body/ground", p["text"], ground, C.BODY_FLOOR),
        ("body/glass-regular", p["text"], reg, C.BODY_FLOOR),
        ("body/glass-clear", p["text"], clear, C.BODY_FLOOR),
        ("body/glass-opaque", p["text"], opaque, C.BODY_FLOOR),
        ("dim/glass-regular", C.over(p["text_dim"], reg), reg, C.LARGE_FLOOR),
        ("label-accent/glass-regular", p["accent_ink"], reg, C.BODY_FLOOR),
        ("label-accent/glass-opaque", p["accent_ink"], opaque, C.BODY_FLOOR),
        ("heading/glass-regular", p["text"], reg, C.LARGE_FLOOR),
        ("sidebar-body/gold-glass", p["on_accent"], gold, C.BODY_FLOOR),
        ("sidebar-heading/gold-glass", p["on_accent"], gold, C.LARGE_FLOOR),
        ("info/glass-regular", p["info"], reg, C.LARGE_FLOOR),
        ("on-accent/accent-fill", p["on_accent"], p["accent"], C.BODY_FLOOR),
    ]


@test
def test_contrast_floors_dark():
    rows, failures = C.audit(_pairs("dark"))
    print("\n--- dark ---\n" + C.fmt(rows))
    assert failures == 0, f"{failures} زوج تحت الحد الأدنى في الوضع الغامق"


@test
def test_contrast_floors_light():
    rows, failures = C.audit(_pairs("light"))
    print("\n--- light ---\n" + C.fmt(rows))
    assert failures == 0, f"{failures} زوج تحت الحد الأدنى في الوضع الفاتح"


@test
def test_gold_sidebar_floor_is_72_percent():
    """الحد الأدنى 72% مش مسألة ذوق — تحته النص بيقع تحت AA.

    بنقيس على أغمق نقطة في الأرضية (اللون الأساسي) عشان الحالة الأسوأ.
    """
    ground = tokens.DARK["ground_base"]
    navy = tokens.DARK["on_accent"]

    at_60 = C.ratio(navy, C.over("rgba(232,185,35,0.60)", ground))
    at_72 = C.ratio(navy, C.over("rgba(232,185,35,0.72)", ground))
    assert at_60 < C.BODY_FLOOR, f"60% المفروض يفشل، طلع {at_60:.2f}"
    assert at_72 >= C.BODY_FLOOR, f"72% المفروض يعدّي، طلع {at_72:.2f}"
    assert tokens.DARK["gold_glass"] == "rgba(232, 185, 35, 0.72)"
    print(f"\n  gold sidebar: 60% -> {at_60:.2f} (fail)  ·  72% -> {at_72:.2f} (pass)")


# --------------------------------------------------------------------------
# 3) الفلاج والمادة
# --------------------------------------------------------------------------

class _FakeSt:
    """أبسط بديل لـ streamlit عشان نختبر منطق الفلاج من غير سيرفر."""

    def __init__(self, query=None):
        self.query_params = query if query is not None else {}
        self.session_state = {}


@test
def test_flag_defaults_to_classic():
    st = _FakeSt()
    os.environ.pop("CIMAFAST_THEME", None)
    assert flag.resolve_variant(st) == flag.CLASSIC
    assert not flag.is_glass(st)


@test
def test_flag_needs_explicit_glass():
    os.environ.pop("CIMAFAST_THEME", None)
    for value in ("", "Glass ", "GLASS", "glass"):
        st = _FakeSt({"theme": value})
        expected = flag.GLASS if value.strip().lower() == "glass" else flag.CLASSIC
        assert flag.resolve_variant(st) == expected, value
    for value in ("dark", "liquid", "true", "1", "classic"):
        st = _FakeSt({"theme": value})
        assert flag.resolve_variant(st) == flag.CLASSIC, value


@test
def test_flag_sticks_across_reruns():
    """rerun مش شايل الـ query param مينفعش يرجّع الشكل القديم في نص الشغل."""
    os.environ.pop("CIMAFAST_THEME", None)
    st = _FakeSt({"theme": "glass"})
    assert flag.resolve_variant(st) == flag.GLASS
    st.query_params = {}
    assert flag.resolve_variant(st) == flag.GLASS


@test
def test_opaque_tier_never_declares_blur():
    """الدرجة التالتة معتمة بحكم التعريف — ده اللي بيمنع تداخل البلور
    من إنه يزيد عن طبقتين، بدل ما نعتمد إننا فاكرين نبقى حريصين."""
    css = "\n".join([glass.base_css(), glass.login_css(), glass.main_css("rtl")])
    blocks = _css_blocks(css)
    for selector, body in blocks:
        if "cf-glass--opaque" in selector and "backdrop-filter" in body:
            raise AssertionError(f"الدرجة المعتمة فيها backdrop-filter: {selector}")


@test
def test_glass_css_is_empty_without_flag():
    """الشكل الافتراضي لازم يفضل نضيف: مفيش CSS زجاج بيتحقن من غير الفلاج."""
    from theme import inject  # noqa: PLC0415

    class Recorder:
        def __init__(self):
            self.blobs = []

        def markdown(self, body, **kw):
            self.blobs.append(body)

        def html(self, body, **kw):
            self.blobs.append(body)

    rec = Recorder()
    inject.inject_base(rec, flag.CLASSIC)
    inject.inject_login(rec, flag.CLASSIC)
    inject.inject_main(rec, flag.CLASSIC, "rtl", "right", "row-reverse")
    joined = "\n".join(rec.blobs)
    assert "cf-glass" not in joined
    assert "backdrop-filter" not in joined
    assert "__DIR__" not in joined, "قوالب الاتجاه لازم تكون اتبدلت"
    assert "direction: rtl" in joined


@test
def test_no_google_font_cdn_anywhere():
    """الخطوط مستضافة محليًا — أي رجوع لـ CDN بيرجّع طلب بيوقف الرسم."""
    from theme import classic  # noqa: PLC0415

    for name, css in (("BASE", classic.BASE_CSS), ("LOGIN", classic.LOGIN_CSS),
                      ("MAIN", classic.MAIN_CSS)):
        assert "fonts.googleapis.com" not in css, name
        assert "fonts.gstatic.com" not in css, name


def _css_blocks(css):
    """تقسيم بسيط لبلوكات ‎selector { body }‎ — كفاية للتأكيدات البنيوية."""
    out = []
    depth = 0
    buf = []
    sel = []
    for ch in css:
        if ch == "{":
            depth += 1
            if depth == 1:
                sel_text = "".join(sel).strip()
                sel = []
                buf = []
                continue
        elif ch == "}":
            depth -= 1
            if depth == 0:
                out.append((sel_text, "".join(buf)))
                continue
        if depth == 0:
            sel.append(ch)
        else:
            buf.append(ch)
    return out


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
