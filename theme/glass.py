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
    """التوكنز والأرضية. لازم تتحقن قبل الدخول عشان شاشة الدخول نفسها
    تقعد على الأرضية مش على لون مسطح."""
    return "\n".join([
        tokens.css_vars("dark"),
        _ground_rules("dark", "rtl"),
    ])


def login_css():
    return ""


def main_css(dir_="rtl"):
    return "\n".join([
        # الأرضية بتتعكس مع اتجاه اللغة، فبنعيد تعريفها هنا وإحنا عارفين
        # الاتجاه (وقت ‎base_css‎ لسه مش عارفينه — لغة الواجهة بتتقرا بعد
        # الدخول). شاشة الدخول دايمًا RTL فنسخة الـ base صح لها.
        _ground_rules("dark", dir_),
        _type_rules(),
        _radius_rules(),
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
    /* العربي بيتكتب بـ IBM Plex Sans Arabic (مستضاف محليًا).
       اللاتيني بيبدأ بـ ‎-apple-system‎ عشان iOS وmacOS يرسموا SF Pro
       الحقيقي — إحساس أصلي على أجهزة آبل من غير رخصة خط ولا ملف زيادة.
       باقي الأجهزة بترجع لـ IBM Plex Sans عادي. */
    [dir="ltr"] {
        font-family: -apple-system, BlinkMacSystemFont, "IBM Plex Sans",
                     "IBM Plex Sans Arabic", "Segoe UI", sans-serif;
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
