"""طبقة تكيّف الموبايل — CSS بس، جوه ‎@media‎ واحدة.

مفيش فلاج ومفيش session_state: المتصفح نفسه هو اللي بيقرر يطبّق الستايل ده
لما عرض الشاشة يبقى ضيق، فبيشتغل على أي جهاز موبايل من غير أي كود بايثون
إضافي ومن غير ما يلمس الباك إند خالص. التفاصيل والخطط في
‎MOBILE-REDESIGN-PLAN.md‎.

الطبقات هنا متقسمة على مراحل الخطة: ‎TOUCH_CSS‎ (مساحات اللمس 44px، نفس
الرقم المستخدم فعلاً لزرار الإعدادات في ‎classic.py‎) و‎NAV_CSS‎ (شريط
التبويبات بيلفّ بدل ما يزحلق). سطر المراحل القديم
(‎.cf-stepper‎) اتشال خالص من الشاشة في جولة تحسينات سابقة (شوف
‎test_the_five_stage_cards_are_gone‎) واتبدل بـ ‎.cf-progress‎ اللي شكله
كويس على الموبايل من غير أي تعديل، فمفيش داعي لستايل زيادة ليه.

نقطة الكسر (‎BREAKPOINT‎) متوافقة عمدًا مع ‎isMobile‎ بتاع Streamlit نفسها
(‎breakpoints.md = 768px‎ في ‎utils.BVKswTgl.js‎، الشرط ‎width < md‎) — مش
رقم اخترناه اعتباطي. لو الاتنين مش متطابقين، فيه عرض شاشات (موبايل كبير
بالعرض، أو تابلت صغير) بيدخل وضع الموبايل بتاع Streamlit نفسه (الشريط
الجانبي بيتحول overlay) من غير ما ستايلنا يتفعّل.
"""

from __future__ import annotations

BREAKPOINT = 767

# أقل ارتفاع للمس — نفس الرقم المستخدم لزرار الإعدادات في classic.py
TOUCH = 44

# ---------------------------------------------------------------------------
# المرحلة 0 — مساحات اللمس
# ---------------------------------------------------------------------------
TOUCH_CSS = f"""
    .stButton button,
    .stDownloadButton button,
    .stFormSubmitButton button,
    div[data-testid="stSelectbox"] > div,
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input {{
        min-height: {TOUCH}px !important;
    }}
"""

# ---------------------------------------------------------------------------
# المرحلة 1 — التنقل
# ---------------------------------------------------------------------------
# المشكلة: ‎[role=tablist]‎ بتاع Streamlit بيبقى ‎flex-wrap: nowrap‎ و
# ‎overflow-x: auto‎. على 390px التبويبات السبعة عايزة 711px، فخمسة منهم
# بيقعوا بره الشاشة ومكانش فيه غير سهم "‹" صغير يقول إن في حاجة ناقصة.
# القياس ده اتاخد من المتصفح نفسه (scrollWidth=711 / clientWidth=358).
#
# الحل: نخلي الشريط يلفّ أسطر بدل ما يزحلق. كده السبع تبويبات كلهم ظاهرين
# في تلات أسطر، ومفيش تبويب مخبّي.
#
# ليه ده مش بيكسر الخط اللي تحت التبويب المفتوح: في Streamlit 1.64 الخط ده
# عنصر ‎.react-aria-SelectionIndicator‎ **جوه التبويب نفسه**
# (‎position:absolute; left:0; bottom:0‎)، مش عنصر واحد فوق الشريط كله
# بيتحرك بالجافاسكريبت. اتأكدنا بالقياس: بعد اللفّ، فرق مكان الخط عن التبويب
# المفتوح = 0px في الاتجاهات التلاتة، للسبع تبويبات (tests/visual/mobile_ui.py).
NAV_CSS = f"""
    .stTabs [role="tablist"] {{
        flex-wrap: wrap !important;
        overflow: visible !important;
        column-gap: 10px !important;
        row-gap: 4px !important;
    }}
    .stTabs [data-testid="stTab"] {{
        min-height: {TOUCH}px !important;
    }}
    /* زرار فتح/قفل الشريط الجانبي كان 28×28 بالقياس. على التليفون ده الطريق
       الوحيد للشريط (تبديل المشروع، اللغة، روابط الرئيسية) لأن Streamlit
       بيقفل الشريط تحت 768px — فالزرار ده أهم زرار في الشاشة، ولازم يبقى في
       مقاس اللمس زي أي زرار تاني. */
    [data-testid="stExpandSidebarButton"],
    [data-testid="stSidebarCollapseButton"] {{
        width: {TOUCH}px !important;
        height: {TOUCH}px !important;
        min-width: {TOUCH}px !important;
        min-height: {TOUCH}px !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
    }}
"""


def _media(*blocks):
    body = "\n".join(b.rstrip() for b in blocks if b and b.strip())
    return f"@media (max-width: {BREAKPOINT}px) {{\n{body}\n}}\n"


MOBILE_CSS = _media(TOUCH_CSS, NAV_CSS)


def mobile_css():
    return MOBILE_CSS
