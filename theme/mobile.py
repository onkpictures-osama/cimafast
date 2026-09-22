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
    /* زرار إظهار كلمة السر جوه الخانة: 16×32 بالقياس على ‎/v1‎ الحي — مالوش
       ‎data-testid‎ فالقواعد اللي فوق مكانتش بتلمسه، وهو أول حاجة بتتداس
       على التليفون لما حد يكتب كلمة السر غلط. الخانة نفسها 44px فالزرار
       بياخد ارتفاعها كله من غير ما يزوّد حاجة. */
    div[data-testid="stTextInput"] button {{
        min-height: {TOUCH}px !important;
        min-width: {TOUCH}px !important;
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


# ---------------------------------------------------------------------------
# المرحلة 2 — الفورمات والجداول ومختار الصور
# ---------------------------------------------------------------------------
# الرصّ في عمود واحد **مش محتاج CSS**: Streamlit نفسه بيرصّ الأعمدة تحت 768px،
# واتقاس على السبع تبويبات في اللغتين (صفر صف فيه أكتر من عمود،
# tests/visual/mobile_ui.py). فمش بنضيف قاعدة تعمل حاجة حاصلة أصلًا — الفحص
# هو اللي بيحرس الحالة دي لو Streamlit غيّر سلوكه في ترقية جاية.
#
# اللي محتاج شغل فعلًا حاجتين اتقاسوا: الصور بمقاس ثابت بالبكسل، وجدول
# ‎st.dataframe‎ اللي بيزحلق أفقي من غير ما حد يعرف.
LAYOUT_CSS = f"""
    /* الشاشات بتطلب صور بعرض ثابت بالبكسل (‎st.image(width=340)‎ في مختار
       الصور، و260 للستوري بورد، و220 للشخصيات). على 390px العمود 358px
       فالكبيرة فيهم بتعدّي؛ وعلى تليفون 320px (iPhone SE) بتعدّي بفرق أوضح.
       قاعدة وقائية: مفيش صورة في البيانات المزروعة عشان تتصوّر، بس الحد ده
       مبيأثرش على أي صورة أصغر من العمود. */
    [data-testid="stImage"] img {{
        max-width: 100% !important;
        height: auto !important;
    }}
    /* مصدر الصورة (رفع / كاميرا / توليد): الاختيارات كانت 22px بالقياس — نص
       الحد الأدنى للمس، وهي أكتر حاجة بتتداس في مختار الصور. اللفّ نفسه
       Streamlit بيعمله أصلًا (اتقاس: سطرين من غير أي CSS)، فمش بنكرره —
       بس بنقفّل الفراغ بين السطرين اللي بقى واسع بعد ما الاختيار كبر. */
    [data-testid="stRadio"] [role="radiogroup"] label {{
        min-height: {TOUCH}px !important;
        align-items: center !important;
    }}
    [data-testid="stRadio"] [role="radiogroup"] {{
        row-gap: 2px !important;
    }}
    /* الجدول ‎st.dataframe‎ شبكة على ‎canvas‎ (glide-data-grid) بتحسب
       تخطيطها بنفسها، فمفيش CSS في الصفحة يقدر يرصّها في عمود واحد — القرار
       والتفصيل في ‎MOBILE-REDESIGN-PLAN.md‎ تحت "المرحلة 2".

       واللي كان ناقص مش الرصّ أصلًا، ده إن حد يعرف إن فيه أعمدة تانية:
       بالقياس على 390px المحتوى 703px والمساحة 356px، و‎scrollLeft‎ بيبدأ
       من صفر وبيوصل 347.

       السكرول بار الظاهر مش حل: اتجرب بأربع صور (‎display:block‎،
       ‎-webkit-appearance:none‎، ‎scrollbar-width:auto‎، ‎overflow-x:scroll‎)
       والنتيجة ‎offsetHeight - clientHeight = 0‎ في كلهم — المتصفح (وكل
       متصفحات الموبايل) بيرسم السكرول بار كطبقة فوق المحتوى بتبان وقت السحب.

       فالعلامة تدرّج على الحرف اللي الأعمدة مخبّية وراه. الحرف ده **اليمين في
       اللغتين**: الشبكة جواها ‎direction: ltr‎ مهما كان اتجاه الصفحة (اتقاس:
       ‎ltr‎ في العربي والإنجليزي، و‎scrollLeft‎ موجب في الاتنين)، فمفيش داعي
       لأي منطق اتجاه هنا. */
    [data-testid="stDataFrame"] {{
        max-width: 100% !important;
        position: relative !important;
    }}
    [data-testid="stDataFrame"]::after {{
        content: "";
        position: absolute;
        top: 1px;
        bottom: 1px;
        right: 1px;
        width: 26px;
        pointer-events: none;
        z-index: 1;
        background: linear-gradient(to right,
                                    rgba(11, 18, 32, 0), rgba(11, 18, 32, 0.88));
    }}
"""


# ---------------------------------------------------------------------------
# المرحلة 3 — الخط والكثافة
# ---------------------------------------------------------------------------
# كل رقم هنا اتقاس الأول على 390px، مش اتخمّن. القياسات قبل التعديل:
#   نص عادي 14px/22.4 · caption 14px/22.4 · h2 36px · h3 28px
#   حقول الإدخال 14px · فراغ العمود 96px فوق و160px تحت · الهيدر 60px
TYPE_CSS = """
    /* الكثافة: 96 + 160 = 256px من 844px (تلت الشاشة) فاضية على التليفون —
       Streamlit بيصغّر الفراغ الجانبي لوحده (80→16) بس مبيلمسش الفوق والتحت.
       الهيدر 60px بالقياس، فـ72 فوق بتسيبله مكانه و12px تنفّس، و48 تحت
       كفاية لآخر عنصر. المكسب (~136px) أكبر من التمن اللي شريط التبويبات
       أخده في المرحلة 1، فالشاشة طلعت أكسب مش أخسر. */
    [data-testid="stMainBlockContainer"] {
        padding-top: 72px !important;
        padding-bottom: 48px !important;
    }
    /* 16px في حقول الإدخال مش مسألة ذوق: تحت 16px، Safari على iOS بيزوّم
       الصفحة كلها أول ما المستخدم يدوس على أي خانة، وبيسيبها مزوّمة بعد
       ما يخلص كتابة. ده أكتر حاجة بتخلي البرنامج يحس إنه مش متعمول
       للتليفون. (بيتحط على ‎.stApp‎ عشان يشمل الشريط الجانبي كمان.) */
    .stApp input,
    .stApp textarea,
    .stApp select {
        font-size: 16px !important;
    }
    /* النص: 14px على ذراع مفرودة صغير، والعربي محتاج سطر أوسع من
       الإنجليزي عشان النقط والحركات ماتلزقش في اللي تحتها. */
    [data-testid="stMain"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stMain"] [data-testid="stMarkdownContainer"] li,
    [data-testid="stMain"] [data-testid="stCaptionContainer"] p {
        font-size: 15px !important;
        line-height: 1.7 !important;
    }
    /* العناوين: 36px/28px مقاس شاشة كبيرة — على عمود 358px العنوان الواحد
       بياخد تلات سطور. الهرم زي ما هو، المقاس بس بقى مقاس الشاشة. */
    [data-testid="stMain"] h1 { font-size: 30px !important; line-height: 1.25 !important; }
    [data-testid="stMain"] h2 { font-size: 26px !important; line-height: 1.25 !important; }
    [data-testid="stMain"] h3 { font-size: 20px !important; line-height: 1.3 !important; }
    [data-testid="stMain"] h4 { font-size: 17px !important; line-height: 1.35 !important; }
"""


def _media(*blocks):
    body = "\n".join(b.rstrip() for b in blocks if b and b.strip())
    return f"@media (max-width: {BREAKPOINT}px) {{\n{body}\n}}\n"


MOBILE_CSS = _media(TOUCH_CSS, NAV_CSS, LAYOUT_CSS, TYPE_CSS)


def mobile_css():
    return MOBILE_CSS
