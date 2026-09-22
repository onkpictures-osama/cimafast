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
from theme import brand, flag, glass, mobile, tokens  # noqa: E402

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
    assert round(C.ratio("#FECA05", "#FECA05"), 2) == 1.0
    # قيم مرجعية من بالتة البراند
    assert round(C.ratio("#FFFFFF", "#0F1B45"), 2) == 16.63
    assert round(C.ratio("#FECA05", "#1A2860"), 2) == 9.01


@test
def test_ratios_match_the_official_guidelines_table():
    """جدول التباين في دليل البراند (ص 08) مش وصف — ده اختبار.

    لو حد غيّر قيمة لون في ‎BRAND‎ بالسهو، الأرقام دي بتقع فورًا. القيم
    منقولة حرف بحرف من الدليل الرسمي v1.0 — بعضها مكتوب فيه بخانة عشرية
    واحدة (14.9 / 13.3 / 12.1)، فالسماحية 0.06 هي تقريب الدليل نفسه مش
    تساهل في الحساب.
    """
    B = tokens.BRAND
    expected = [
        ("Ink on Yellow", B["ink"], B["yellow"], 9.67),
        ("Navy on Yellow", B["navy"], B["yellow"], 8.01),
        ("Royal on Yellow", B["royal"], B["yellow"], 6.24),
        ("Red on Yellow", B["red"], B["yellow"], 3.35),
        ("Ink on White", B["ink"], B["white"], 14.9),
        ("Ink on Cream", B["ink"], B["cream"], 13.3),
        ("Ink on Sand", B["ink"], B["sand"], 12.1),
        ("White on Red", B["white"], B["red"], 5.15),
        ("Yellow on Midnight", B["yellow"], B["midnight"], 10.8),
        ("Yellow on Navy Surface", B["yellow"], B["navy_surface"], 9.0),
        ("White on Midnight", B["white"], B["midnight"], 16.6),
        ("Mist on Midnight", B["mist_dark"], B["midnight"], 9.1),
    ]
    for name, fg, bg, want in expected:
        got = round(C.ratio(fg, bg), 2)
        assert abs(got - want) <= 0.06, f"{name}: الدليل بيقول {want}، طلع {got}"


@test
def test_yellow_field_is_the_brand_not_a_surface():
    """قاعدتين من الدليل ص 08، مقفولين هنا عشان ميتكسروش بالسهو:
    الحقل الأصفر نفس القيمة في الوضعين، والحروف فوقه Ink في الوضعين."""
    assert tokens.DARK["gold_glass"] == tokens.LIGHT["gold_glass"]
    assert tokens.DARK["on_brand"] == tokens.LIGHT["on_brand"] == tokens.BRAND["ink"]
    # الأحمر ممنوع يبقى لون نص صغير على الأصفر (3.35:1) — ولا مرة
    assert C.ratio(tokens.BRAND["red"], tokens.BRAND["yellow"]) < C.BODY_FLOOR


@test
def test_palette_values_are_the_official_ones():
    """التوكنز الدلالية لازم تكون خام البراند نفسه، مش تقريب ليه."""
    B = tokens.BRAND
    assert tokens.DARK["ground_base"] == B["midnight"]
    assert tokens.DARK["glass_opaque"] == B["navy_surface"]
    assert tokens.DARK["accent"] == B["yellow"]
    assert tokens.DARK["text"] == B["white"]
    assert tokens.DARK["text_dim"] == B["mist_dark"]
    assert tokens.DARK["danger"] == tokens.DARK["play"] == B["red"]
    assert tokens.LIGHT["ground_base"] == B["cream"]
    assert tokens.LIGHT["accent"] == B["navy"]
    assert tokens.LIGHT["text"] == B["ink"]


@test
def test_css_vars_expose_the_raw_brand_tokens():
    """اللوجو والحقل الأصفر بيلمسوا الخام، فلازم ‎--cf-yellow‎ و‎--cf-ink‎
    يبقوا موجودين في الصفحة فعلًا — مش في ‎tokens.py‎ بس."""
    css = tokens.css_vars("dark")
    for name in ("--cf-yellow", "--cf-navy", "--cf-ink", "--cf-red", "--cf-royal",
                 "--cf-midnight", "--cf-white", "--cf-on-brand", "--cf-font"):
        assert name in css, name
    assert "#FECA05" in css and "#1B254B" in css


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
        ("sidebar-body/gold-glass", p["on_brand"], gold, C.BODY_FLOOR),
        ("sidebar-heading/gold-glass", p["on_brand"], gold, C.LARGE_FLOOR),
        ("info/glass-regular", p["info"], reg, C.LARGE_FLOOR),
        ("on-info/info-fill", p["on_info"], p["info"], C.BODY_FLOOR),
        ("on-accent/accent-fill", p["on_accent"], p["accent"], C.BODY_FLOOR),
        # الحقل الأصفر هو نفسه في الوضعين، فالزوج ده مبيتغيرش بين الوضعين
        ("on-brand/yellow-field", p["on_brand"], tokens.BRAND["yellow"], C.BODY_FLOOR),
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
    navy = tokens.DARK["on_brand"]

    at_60 = C.ratio(navy, C.over("rgba(254,202,5,0.60)", ground))
    at_72 = C.ratio(navy, C.over("rgba(254,202,5,0.72)", ground))
    assert at_60 < C.BODY_FLOOR, f"60% المفروض يفشل، طلع {at_60:.2f}"
    assert at_72 >= C.BODY_FLOOR, f"72% المفروض يعدّي، طلع {at_72:.2f}"
    assert tokens.DARK["gold_glass"] == "rgba(254, 202, 5, 0.72)"
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
def test_only_registered_surfaces_declare_blur():
    """كل سيليكتور بيعلن ‎backdrop-filter‎ لازم يكون مسجّل في
    ‎glass.blur_surfaces()‎.

    ليه ده مهم: حارس التداخل بيتبني من نفس القايمة دي. لو حد ضاف بلور على
    عنصر مش مسجّل، الحارس مش هيشوفه والعمق ممكن يعدّي الاتنين من غير ما
    حد يلاحظ — الاختبار ده بيمنع الحالة دي قبل ما توصل للمتصفح.
    """
    css = "\n".join([glass.base_css(), glass.login_css(), glass.main_css("rtl")])
    allowed = set(glass.blur_surfaces())
    offenders = []
    for selector, body in _css_blocks(css):
        if "backdrop-filter" not in body:
            continue
        # القواعد اللي بتطفي البلور مش محتاجة تسجيل
        values = [
            line.split(":", 1)[1]
            for line in body.split(";")
            if "backdrop-filter" in line and ":" in line
        ]
        if all("none" in v for v in values):
            continue
        for part in selector.split(","):
            part = part.strip()
            if part.startswith(".stApp "):
                part = part[len(".stApp "):].strip()
            if part and part not in allowed:
                offenders.append(part)
    assert not offenders, "بلور على أسطح مش مسجّلة: " + ", ".join(sorted(set(offenders)))


@test
def test_blur_guard_caps_nesting_at_two():
    """الحارس نفسه لازم يكون موجود ويغطي كل الأسطح المسجّلة.

    ده الجزء اللي بيخلي الحد الأقصى مثبت بنيويًا: أي عنصر فوقه سطحين
    بلور بيتقفل عليه البلور، فالعمق محصور في ٢ مهما اتداخل الـ DOM.
    """
    css = glass.base_css()
    surfaces = glass.blur_surfaces()
    guard = None
    for selector, body in _css_blocks(css):
        if selector.count(":is(") == 3 and "backdrop-filter" in body and "none" in body:
            guard = selector
            break
    assert guard, "قاعدة حارس التداخل (ثلاث مستويات) مش موجودة"
    for sel in surfaces:
        assert sel in guard, f"سطح مسجّل مش داخل الحارس: {sel}"


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
    # بندوّر على سيليكتورات المادة (‎.cf-glass…‎) مش على النص ‎cf-glass‎:
    # من بعد ما ألوان البراند دخلت، بلوك الـ ‎:root‎ بيتحقن في المسارين،
    # وجواه توكنز اسمها ‎--cf-glass-regular‎ — دي قيم، مش مادة.
    assert ".cf-glass" not in joined
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


# --------------------------------------------------------------------------
# 4) طبقة الموبايل — الحد اللي بيحمي التابلت وسطح المكتب
# --------------------------------------------------------------------------

@test
def test_mobile_css_is_entirely_inside_one_media_query():
    """أهم حد في الخطة: صفر فرق على التابلت وسطح المكتب.

    الضمانة دي بنيوية مش بالنية: لو كل قاعدة جوه ‎@media (max-width: 767px)‎
    يبقى مستحيل تتطبق على 834px أو 1440px. الاختبار ده بيقفل الباب على قاعدة
    تتكتب بالغلط بره البلوك.
    """
    css = mobile.mobile_css().strip()
    assert css.startswith("@media (max-width: 767px) {"), css[:80]
    assert css.endswith("}")
    # أي قوس بيقفل بدري معناه قاعدة خرجت بره الـ @media
    body = css[css.index("{") + 1: css.rindex("}")]
    depth = 0
    for ch in body:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            assert depth >= 0, "قوس زيادة — في قاعدة خرجت بره الـ @media"
    assert depth == 0


@test
def test_mobile_layer_carries_no_direction_placeholders():
    """‎inject_base‎ مبتعملش ‎_template‎، فأي ‎__ALIGN__‎ في طبقة الموبايل
    هيوصل للصفحة كنص حرفي جوه قاعدة مكسورة على شاشة الدخول. الطبقة دي لازم
    تفضل مستقلة عن اتجاه اللغة — وهي فعلاً كده: حتى تدرّج الجدول على اليمين
    في اللغتين لأن الشبكة جواها ‎ltr‎ دايمًا."""
    for token in ("__DIR__", "__ALIGN__", "__ROWDIR__"):
        assert token not in mobile.mobile_css(), f"{token} في طبقة الموبايل"


@test
def test_mobile_breakpoint_is_below_the_tablet_viewport():
    """767px مش رقم اعتباطي: هو ‎breakpoints.md - 1‎ بتاع Streamlit نفسه،
    ولازم يفضل أقل من أضيق شاشة في الهارنس (tablet = 834px)."""
    assert mobile.BREAKPOINT == 767
    assert mobile.BREAKPOINT < 834


@test
def test_mobile_touch_target_matches_the_existing_standard():
    from theme import classic  # noqa: PLC0415

    assert mobile.TOUCH == 44
    assert "44px" in classic.MAIN_CSS, "الرقم المرجعي اتغير في classic.py"
    assert mobile.mobile_css().count("44px") >= 2


@test
def test_mobile_tab_bar_wraps_instead_of_scrolling():
    """المرحلة 1: التبويبات بتلفّ أسطر. لو حد رجّع ‎nowrap‎ أو سكرول أفقي،
    تبويب أو أكتر هيختفي على 390px تاني."""
    css = mobile.mobile_css()
    assert 'role="tablist"' in css
    assert "flex-wrap: wrap" in css
    assert "nowrap" not in css


@test
def test_mobile_inputs_are_at_least_16px():
    """أقل من 16px في خانة إدخال = Safari على iOS بيزوّم الصفحة كلها أول ما
    المستخدم يدوس عليها، وبيسيبها مزوّمة بعد كده. الرقم ده سلوك متصفح مش
    ذوق، فمينفعش ينزل تحته."""
    css = mobile.mobile_css()
    assert ".stApp input," in css
    block = css[css.index(".stApp input,"):]
    assert "font-size: 16px" in block[:300], "حقول الإدخال نزلت تحت 16px"


@test
def test_mobile_text_never_drops_below_the_body_contrast_floor():
    """المرحلة 3 بتصغّر العناوين على التليفون، والنص الصغير في WCAG بيتحاسب
    على الحد الأعلى (4.5) مش حد النص الكبير (3.0). فبنتأكد إن كل زوج في
    التصميم بيعدّي 4.5 كمان — يعني التصغير مبيوقعش أي زوج تحت الحد."""
    for mode in ("dark", "light"):
        rows, _ = C.audit([(n, f, b, C.BODY_FLOOR) for (n, f, b, _fl) in _pairs(mode)])
        bad = [r["pair"] for r in rows if not r["pass"]]
        assert not bad, f"{mode}: {bad} تحت 4.5 — التصغير على التليفون مش آمن"


# --------------------------------------------------------------------------
# 5) اللوجو — قواعد الدليل اللي سهل تتكسر بالسهو
# --------------------------------------------------------------------------

@test
def test_wordmark_is_never_restyled():
    """الدليل ص 01: كلمة واحدة، C و F كابيتال. ممنوع "Cima Fast" ولا
    "CIMAFAST" ولا "Cimafast". الاختبار ده بيقفل على الإملا نفسها."""
    assert brand.WORDMARK == "CimaFast"
    assert brand.DESCRIPTOR == "STUDIO", "نسخة الاستوديو بتستبدل MEDIA بـ STUDIO"
    for surface in ("dark", "light"):
        html = brand.lockup(surface)
        assert "Cima Fast" not in html
        assert "CIMAFAST" not in html
        assert "Cimafast" not in html


@test
def test_logo_assets_exist_and_are_the_right_variant():
    """نسخة اللوجو الصح للسطح الصح: صفرا على الغامق، كحلي على الأصفر/الفاتح
    (الدليل ص 03 · Colour rule). وبنتأكد إن مثلث التشغيل أحمر في الاتنين —
    المونو للطباعة بس."""
    for name, figure in ((brand.MARK_DARK, tokens.BRAND["yellow"]),
                         (brand.MARK_LIGHT, tokens.BRAND["navy"])):
        with open(brand.asset_path(name), encoding="utf-8") as fh:
            svg = fh.read()
        assert figure in svg, f"{name}: لون الشخصية مش {figure}"
        assert tokens.BRAND["red"] in svg, f"{name}: مثلث التشغيل مش أحمر"
    assert os.path.exists(brand.asset_path(brand.APP_ICON))


@test
def test_logo_is_embedded_not_fetched():
    """البريفيو شغال تحت ‎/v1/‎، والرابط النسبي بيتكسر لو المستخدم فتح
    ‎/v1‎ من غير الشرطة الأخيرة. اللوجو لازم يبقى مضمّن في الصفحة."""
    html = brand.lockup("dark")
    assert html.count("data:image/svg+xml;base64,") == 1
    assert "src=\"app/static" not in html and "http" not in html


@test
def test_logo_direction_is_locked_to_ltr():
    """الـ lockup شكل مرسوم مش جملة: لو اتقلب مع العربي، العلامة بتروح
    الناحية الغلط والووردمارك بيتقلب معاها."""
    assert 'dir="ltr"' in brand.lockup("dark")
    assert "direction: ltr;" in brand.LOGO_CSS


@test
def test_arabic_name_sits_beside_the_lockup_in_cairo():
    """الدليل ص 04: الاسم العربي جنب الـ lockup بخط Cairo Bold — عمره ما
    يدخل جوه الووردمارك ولا يتكتب ترجمة حرفية جواه."""
    with_ar = brand.lockup("dark", arabic=True)
    assert brand.ARABIC_NAME in with_ar
    assert brand.ARABIC_NAME not in brand.lockup("dark", arabic=False)
    # الاسم العربي بره العنصر اللي فيه الووردمارك
    word_block = with_ar[with_ar.index("cf-logo__word"):with_ar.index("cf-logo__ar")]
    assert brand.ARABIC_NAME not in word_block
    assert 'font-family: "Cairo"' in brand.LOGO_CSS


def _strip_comments(css):
    """شيل تعليقات ‎/* … */‎ — التعليقات بتلزق في نص السيليكتور وقت التقسيم."""
    out = []
    i = 0
    while i < len(css):
        if css[i:i + 2] == "/*":
            end = css.find("*/", i + 2)
            i = len(css) if end == -1 else end + 2
            continue
        out.append(css[i])
        i += 1
    return "".join(out)


def _css_blocks(css):
    """تقسيم بسيط لبلوكات ‎selector { body }‎ — كفاية للتأكيدات البنيوية."""
    css = _strip_comments(css)
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
