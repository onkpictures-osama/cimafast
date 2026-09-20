"""طبقة مادة "Liquid Glass" — كل ده تحت الفلاج ‎?theme=glass‎.

الزجاج مادة، مش بالتة ألوان. يعني طبقات شبه شفافة واقفة فوق أرضية بتنكسر
من خلالها، وعلى حرفها ضوء. النتيجة المهمة: **الزجاج محتاج أرضية تستحق
الانكسار.** خلفية لون واحد مسطح بتخلي الزجاج مجرد مستطيلات رمادية بحواف
ناعمة. فالأرضية بتتبني الأول (ميش جراديينت ثابت من بالتة البرنامج)،
والمحتوى بيسكرول فوقها — الفرق في الحركة بين الأرضية الواقفة والزجاج
الماشي هو اللي بيخلي المادة تقرا كزجاج مش كشفافية.

الترتيب:
  - ‎base_css‎  : التوكنز + الأرضية (بيتحقن قبل الدخول، فشاشة الدخول كمان
                 بتقعد على نفس الأرضية)
  - ‎login_css‎ : حاجات شاشة الدخول بس
  - ‎main_css‎  : كل الباقي، وبياخد اتجاه اللغة

ليه CSS ومش مفاتيح الثيم الأصلية بتاعة Streamlit: ‎.streamlit/config.toml‎
بيتقرا مرة واحدة وقت تشغيل الخدمة ومينفعش يتغير حسب الـ URL. الشكل الجديد
لازم يفضل خلف الفلاج، يعني نصف القطر والحدود والوضع الفاتح مينفعش يتحطوا
هناك — كانوا هيغيّروا الشكل الافتراضي لكل الـ 12 مستخدم.
"""

from __future__ import annotations

from . import tokens

# أغلب عناصر Streamlit اللي محتاجة نصف قطر موحّد
_MEDIUM_RADIUS_TARGETS = ", ".join(
    ".stApp " + sel for sel in (
        '[data-baseweb="input"]',
        '[data-baseweb="textarea"]',
        '[data-baseweb="select"] > div',
        '[data-baseweb="popover"] ul',
        '.stButton > button',
        '.stDownloadButton > button',
        '[data-testid="stBaseButton-secondary"]',
        '[data-testid="stBaseButton-secondaryFormSubmit"]',
        '[data-testid="stNumberInputContainer"]',
    )
)

_LARGE_RADIUS_TARGETS = ", ".join(
    ".stApp " + sel for sel in (
        '[data-testid="stForm"]',
        '[data-testid="stExpander"]',
        '[data-testid="stFileUploaderDropzone"]',
        '[data-testid="stNotification"]',
        '[data-testid="stAlert"]',
    )
)


def base_css():
    """كل الستايل المستقل عن اتجاه اللغة.

    بيتحقن قبل بوابة الدخول، فشاشة الدخول بتاخد نفس الأرضية ونفس المادة —
    مش لون مسطح وبعدين الشكل الحقيقي بعد الدخول.
    """
    return "\n".join([
        tokens.css_vars("dark"),
        _ground_rules("dark", "rtl"),
        _type_rules(),
        _radius_rules(),
        _material_rules(),
        _cf_surface_rules(),
        # لازم تفضل آخر حاجة: بتلغي البلور المتداخل الزيادة اللي القواعد
        # اللي فوق ممكن تكون أعلنته
        _blur_guard_rules(),
    ])


def login_css():
    return ""


def main_css(dir_="rtl"):
    """الحاجات اللي بتتغير مع اتجاه اللغة بس.

    الباقي كله في ‎base_css‎ عشان يشتغل على شاشة الدخول كمان.
    """
    return "\n".join([
        # الأرضية بتتعكس مع اتجاه اللغة، فبنعيد تعريفها هنا وإحنا عارفين
        # الاتجاه (وقت ‎base_css‎ لسه مش عارفينه — لغة الواجهة بتتقرا بعد
        # الدخول). شاشة الدخول دايمًا RTL فنسخة الـ base صح لها.
        _ground_rules("dark", dir_),
    ])


def inject_runtime(st):
    """أي جافاسكريبت لازمة للمادة (تتبع الماوس للسطوع) بتتحقن من هنا."""
    return None


# --------------------------------------------------------------------------
# المرحلة 1: الأرضية والتيبوغرافيا ونصف القطر
# --------------------------------------------------------------------------

def _ground_rules(mode, dir_):
    ground = tokens.ground_css(mode, dir_)
    return f"""
    /* الميش ثابت في الفيوبورت. ‎body‎ مش هو العنصر اللي بيسكرول في
       Streamlit (الحاوية الداخلية هي اللي بتسكرول)، فخلفيته بتفضل واقفة
       من نفسها والمحتوى بيعدّي فوقها. */
    body {{
        background: {ground} !important;
        background-attachment: fixed !important;
    }}
    /* خلفيات Streamlit نفسها لازم تبقى شفافة، وإلا هتغطي الأرضية. */
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    [data-testid="stBottomBlockContainer"],
    header[data-testid="stHeader"] {{
        background: transparent !important;
        background-color: transparent !important;
    }}
    """


def _type_rules():
    return """
    /* Readex Pro للعربي والإنجليزي في كل حتة (قرار صاحب المشروع) — مستضاف
       محليًا. خطوط النظام بس احتياطي لو الملف متحملش. */
    [dir="ltr"] {
        font-family: "Readex Pro", -apple-system, BlinkMacSystemFont,
                     "Segoe UI", sans-serif;
    }
    /* العناوين: أتقل شوية وبتقارب أحرف أضيق. العربي مبياخدش
       ‎letter-spacing‎ سالب — الحروف موصولة والتقريب بيبوّش الوصلات —
       فبنحصره على اللاتيني. */
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {
        font-weight: 700;
    }
    [dir="ltr"] h1, [dir="ltr"] h2, [dir="ltr"] h3 {
        letter-spacing: -0.012em;
    }
    """


def _radius_rules():
    """نصف قطر متداخل (concentric): الحاوية أكبر قوسًا من اللي جواها بفرق
    الحاشية، عشان الأقواس تبقى متمركزة حوالين بعضها."""
    return f"""
    {_MEDIUM_RADIUS_TARGETS} {{
        border-radius: var(--cf-radius-md) !important;
    }}
    {_LARGE_RADIUS_TARGETS} {{
        border-radius: var(--cf-radius-lg) !important;
    }}
    .stApp [data-testid="stCheckbox"] [data-baseweb="checkbox"] span:first-of-type,
    .stApp [data-testid="stTag"],
    .stApp .cf-check-badge {{
        border-radius: var(--cf-radius-sm) !important;
    }}
    """


# --------------------------------------------------------------------------
# المرحلة 2: مادة الزجاج — تلات درجات، وحد بنيوي لتداخل البلور
# --------------------------------------------------------------------------

# الأسطح اللي مسموح لها تعلن ‎backdrop-filter‎. أي حاجة مش في القايمتين
# دول مبتعملش بلور خالص — دي مش قاعدة أدب، دي اللي بتخلّي الحد الأقصى
# (طبقتين) قابل للإثبات بدل ما يبقى اتفاق بننساه.
#
# مهم: كل سيليكتور هنا لازم يقف بنفسه (من غير أب مشترك زي ‎.stApp‎)،
# لأن حارس التداخل بيركّبهم مع بعض كـ سلاسل نسب.
_BLUR_SURFACES = (
    ".cf-glass--regular",
    ".cf-glass--clear",
    '[data-testid="stForm"]',
    '[data-testid="stExpander"]',
    '[data-testid="stAlert"]',
    '[data-testid="stNotification"]',
    ".cf-stage",
)

# إطار البرنامج — سطح بلور من درجة تانية. بيتعامل لوحده عشان الشريط
# الجانبي بيغطي المحتوى على الموبايل، فأي بلور جوّاه بيبقى فوق بلور.
_CHROME_SURFACES = (
    'section[data-testid="stSidebar"]',
    'header[data-testid="stHeader"]',
)


def blur_surfaces():
    """كل سيليكتور مسموح له يعلن بلور — الاختبار بيقرا منها."""
    return tuple(_BLUR_SURFACES) + tuple(_CHROME_SURFACES)


def _is(selectors):
    return ":is(%s)" % ", ".join(selectors)


def _tier_decls(tier):
    """تصريحات درجة مادة واحدة — مصدر حقيقة واحد.

    بتتنادي من الكلاسات العامة (‎.cf-glass--*‎) ومن عناصر ‎cf-*‎ القديمة
    اللي اتنقلت على المادة، عشان الاتنين يفضلوا متطابقين بالتعريف.
    """
    if tier == "opaque":
        # الدرجة التالتة معتمة بحكم التعريف — مفيش ‎backdrop-filter‎ هنا
        # أبدًا. ده اللي بيخلي النص الكثيف (جداول، عربي طويل) يفضل حاد.
        return """
        background: var(--cf-glass-opaque);
        border: 1px solid var(--cf-edge);
        box-shadow: var(--cf-elevation-sm), var(--cf-edge-specular);
        """
    fill = "var(--cf-glass-%s)" % tier
    blur = "var(--cf-blur-regular)" if tier == "regular" else "var(--cf-blur-clear)"
    sat = "var(--cf-sat-regular)" if tier == "regular" else "var(--cf-sat-clear)"
    return f"""
        background: {fill};
        -webkit-backdrop-filter: blur({blur}) saturate({sat});
        backdrop-filter: blur({blur}) saturate({sat});
        border: 1px solid var(--cf-edge);
        box-shadow: var(--cf-elevation), var(--cf-edge-specular);
        """


def _material_rules():
    """الكلاسات العامة اللي ‎theme/components.py‎ بيطلّعها."""
    return f"""
    .stApp .cf-glass {{
        position: relative;
        color: var(--cf-text);
        padding: 16px 18px;
        border-radius: var(--cf-radius-lg);
    }}
    .stApp .cf-glass--regular {{{_tier_decls("regular")}}}
    .stApp .cf-glass--clear {{{_tier_decls("clear")}}}
    .stApp .cf-glass--opaque {{{_tier_decls("opaque")}}}
    .stApp .cf-r-lg {{ border-radius: var(--cf-radius-lg); }}
    .stApp .cf-r-md {{ border-radius: var(--cf-radius-md); }}
    .stApp .cf-r-sm {{ border-radius: var(--cf-radius-sm); }}
    .stApp .cf-glass-title {{
        font-weight: 700;
        color: var(--cf-accent-ink);
        margin-bottom: 6px;
    }}
    .stApp .cf-glass-body {{ color: var(--cf-text); }}
    """


def _cf_surface_rules():
    """عناصر ‎cf-*‎ اللي كانت بألوان مصمتة في ‎classic‎، بقت على المادة.

    السيليكتورز هنا بتطابق اللي في ‎classic.py‎ بالظبط في الطول، مش أقصر —
    لو قصّرناها الخصوصية (specificity) بتقل والقاعدة القديمة بتكسب.
    """
    return f"""
    /* بطاقة مرحلة في شريط المراحل — الدرجة العادية.
       الشكل النهائي للشريط في المرحلة 4؛ هنا بس بتتنقل على المادة. */
    .stApp .cf-stage {{{_tier_decls("regular")}}}
    .stApp .cf-stage-done {{
        background: var(--cf-glass-regular);
        border-color: var(--cf-info);
        box-shadow: var(--cf-elevation), var(--cf-edge-specular),
                    inset 0 0 0 1px rgba(45, 156, 219, 0.35);
    }}
    .stApp .cf-stage-current {{
        border-color: var(--cf-accent);
        box-shadow: var(--cf-elevation), var(--cf-edge-specular),
                    0 0 0 3px rgba(232, 185, 35, 0.22);
    }}
    .stApp .cf-stage-pending {{ opacity: 0.55; }}
    .stApp .cf-stage-label {{ color: var(--cf-text); }}

    /* صندوق وصف البرنامج في الشريط الجانبي: الشريط نفسه دهبي، فالصندوق
       بياخد تعبئة فاتحة خفيفة بدل زجاج تاني — مفيش بلور جوه بلور. */
    section[data-testid="stSidebar"] .cf-sidebar-header .cf-desc-box {{
        border: 1px solid rgba(18, 32, 61, 0.30);
        border-radius: var(--cf-radius-sm);
        background: rgba(255, 255, 255, 0.24);
    }}
    /* كارت المستخدم الحالي — الدرجة المعتمة: نص كثيف ولازم يفضل حاد. */
    section[data-testid="stSidebar"] .cf-owner-box {{
        background: #FFFFFF;
        border: 1px solid rgba(18, 32, 61, 0.22);
        border-radius: var(--cf-radius-md);
        box-shadow: var(--cf-elevation-sm);
    }}
    .stApp .cf-saved-badge {{ color: var(--cf-text-dim); opacity: 1; }}
    .stApp .cf-check-badge {{ background: var(--cf-info); color: #FFFFFF; }}
    .stApp .cf-copy-hint {{ color: var(--cf-accent-ink); }}
    .stApp hr.cf-soft-sep {{ border-top: 1px solid var(--cf-edge); }}
    """


def _blur_guard_rules():
    """الحد البنيوي: أقصى طبقتين بلور متداخلين، في أي مكان.

    بدل ما نفتكر نبقى حريصين، القاعدة دي بتطفي البلور على أي سطح ليه
    سطحين بلور فوقه في شجرة الـ DOM. يعني العمق محصور في ٢ رياضيًا مهما
    اتداخلت العناصر — والعنصر اللي بيتقفل عليه البلور بياخد تعبئة معتمة
    (الدرجة التالتة) بدل ما يفضل شفاف من غير مادة.

    ‎:is()‎ بتخلي دي قاعدة واحدة بدل ٣٤٣ سيليكتور، وخصوصيتها بتاخد أعلى
    عنصر في القايمة فبتكسب القواعد اللي فوق من غير حيل.
    """
    all_s = _is(blur_surfaces())
    inner = _is(_BLUR_SURFACES)
    return f"""
    {all_s} {all_s} {all_s} {{
        -webkit-backdrop-filter: none !important;
        backdrop-filter: none !important;
    }}
    [data-testid="stMain"] {all_s} {all_s} {all_s} {{
        background: var(--cf-glass-opaque) !important;
    }}
    /* جوه الشريط الجانبي الدهبي مفيش بلور تاني خالص: الشريط بيقف فوق
       المحتوى على الموبايل، فأي بلور جوّاه بيبقى بلور فوق بلور فوق
       المحتوى — والتكلفة دي على جهاز المستخدم مش علينا. */
    section[data-testid="stSidebar"] {inner} {{
        -webkit-backdrop-filter: none !important;
        backdrop-filter: none !important;
        background: rgba(18, 32, 61, 0.08) !important;
        border: 1px solid rgba(18, 32, 61, 0.28) !important;
        box-shadow: none !important;
    }}
    """
