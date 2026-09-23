"""الشريط الجانبي — سطح غامق، استثناء موثّق من قاعدة "الحقل الأصفر".

القاعدة العامة لسه سارية على أي سطح تاني في البرنامج (‎brand.py‎: سطح فاتح
أو الحقل الأصفر → الشخصية كحلي، سطح غامق → الشخصية صفرا). الشريط الجانبي
بس استثناء *مقصود وموثّق*، معتمد من صاحب المنتج بتاريخ 2026-09-23 على موك
أب مرجعي (خلفية كحلي غامقة بدل الحقل الأصفر) — مش رجوع عن القاعدة ولا خطأ
يتصلّح في مرة جاية. التفاصيل الكاملة في ‎theme/brand.py‎ فوق تعريف
‎mark()‎/‎lockup()‎.

الفرق الجوهري عن نسخة الحقل الأصفر القديمة (كانت هنا في ‎classic.py‎): دلوقتي
الشريط الجانبي بيستخدم **نفس** ثيم Streamlit الغامق الافتراضي اللي باقي
البرنامج شغال بيه (‎.streamlit/config.toml‎: base=dark، الأرضية Midnight،
النص أبيض) بدل ما يعاكسه بالحقل الأصفر. فمعظم الـ !important اللي كانت لازمة
قبل كده (نص كحلي كان بيتفرض على خلفية غامقة ويختفي، زرارات كانت محتاجة تتلوّن
يدوي بالكامل) بقت مش لازمة أصلًا — نفس الأزرار والخانات اللي شغالة في باقي
البرنامج الغامق شغالة هنا كويس من غير تدخل.

التباين اتقاس فعليًا (مش بالعين) في ‎tests/test_theme.py‎
(‎test_sidebar_dark_surface_contrast‎) — كل زوج نص/أرضية هنا بيعدّي أرضًا
الحدود اللي ‎theme/contrast.py‎ بيفرضها (نص عادي ≥ 4.5:1، عناوين ≥ 3:1).
"""

from __future__ import annotations


SIDEBAR_CSS = r'''
    section[data-testid="stSidebar"] {
        direction: __DIR__;
        background: var(--cf-midnight);
        overflow-x: hidden !important;
    }
    /* ---- التوزيع الرأسي: تلات مجموعات (طلب المالك 2026-09-23) ----
       فوق: البراند. فوق النص بشوية: المشاريع. تحت خالص: الحساب.
       السلسلة من ‎stSidebarContent‎ لحد العمود الجذر لازم تبقى flex
       بطول الشريط كله، عشان ‎margin-top:auto‎ على مجموعة الحساب يزقها
       لتحت. الفراغ بين المجموعات هو المساحة اللي أي إضافة جديدة بتاكل
       منها. على شاشة قصيرة الفراغات بتقفل لحد الحد الأدنى والشريط بيتمرر
       عادي - مفيش حاجة بتتقص. */
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        display: flex;
        flex-direction: column;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
        flex: 1 0 auto;
        display: flex;
        flex-direction: column;
        padding-bottom: 20px;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] > div,
    section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] {
        flex: 1 0 auto;
        display: flex;
        flex-direction: column;
    }
    /* المشاريع: فوق النص بشوية - المسافة بتكبر مع طول الشاشة وليها حد */
    section[data-testid="stSidebar"] [data-testid="stLayoutWrapper"]:has(> .st-key-cf_sb_projects) {
        margin-top: clamp(20px, 12vh, 140px);
    }
    /* الحساب: آخر الشريط */
    section[data-testid="stSidebar"] [data-testid="stLayoutWrapper"]:has(> .st-key-cf_sb_account) {
        margin-top: auto;
        padding-top: 24px;
    }
    /* المحاذاة (تصحيح المالك 2026-09-23): الكلام العربي من اليمين -
       بداية السطر، فبيبقى شمال في الإنجليزي لوحده. في النص بس: اللوجو
       وتاجلاينه وأيقونة المعلومات، وصف اللغة. */
    section[data-testid="stSidebar"] .st-key-cf_sb_projects,
    section[data-testid="stSidebar"] .st-key-cf_sb_account {
        text-align: start;
    }
    section[data-testid="stSidebar"] .st-key-cf_sb_brand,
    section[data-testid="stSidebar"] .st-key-cf_sb_brand [data-testid="stElementContainer"],
    section[data-testid="stSidebar"] .st-key-cf_sb_brand .cf-sb-tagline {
        text-align: center !important;
    }
    section[data-testid="stSidebar"] .st-key-cf_sb_brand [data-testid="stElementContainer"]:has(.cf-sb-tagline) {
        width: 100% !important;
    }
    section[data-testid="stSidebar"] .st-key-cf_sb_brand .cf-sb-tagline {
        width: 100%;
    }
    section[data-testid="stSidebar"] .st-key-cf_sb_brand .cf-title {
        display: flex;
        justify-content: center;
    }
    section[data-testid="stSidebar"] .st-key-cf_sb_account hr.cf-sb-sep {
        width: 100%;
        margin-top: 0;
    }
    /* اسم المشروع/الحساب المختار جوه الخانة: من بداية السطر (يمين في
       العربي). في Streamlit 1.64 الخانة react-aria والقيمة نص ‎<input>‎،
       والـ input مابيورّثش الاتجاه من أبوه */
    section[data-testid="stSidebar"] .st-key-cf_sb_projects [data-testid="stSelectbox"] input[role="combobox"] {
        direction: __DIR__ !important;
        text-align: start !important;
    }
    /* تسمية "المشاريع": حاوية عناصر Streamlit بتفرض ‎text-align:left‎،
       فلازم تتقال على العنصر نفسه */
    section[data-testid="stSidebar"] .st-key-cf_sb_projects .cf-sb-section-label {
        text-align: start !important;
        margin-bottom: 8px;
    }
    /* صف الهوية: غلاف الأفتار ياخد الباقي (يمين)، والجرس بمقاسه على الطرف */
    section[data-testid="stSidebar"] .st-key-cf_sb_me > * {
        flex: 0 0 auto !important;
        width: auto !important;
    }
    section[data-testid="stSidebar"] .st-key-cf_sb_me > [data-testid="stElementContainer"]:has(.cf-sb-avatar-row) {
        flex: 1 1 auto !important;
        min-width: 0;
    }
    section[data-testid="stSidebar"] .st-key-cf_sb_me .cf-sb-avatar-row {
        justify-content: flex-start;
    }
    /* زرار الخروج بعرض المجموعة كامل */
    section[data-testid="stSidebar"] .st-key-cf_sb_account .stButton,
    section[data-testid="stSidebar"] .st-key-cf_sb_account [data-testid="stElementContainer"]:has(.stButton) {
        width: 100%;
    }

    /* اللوجو: الحاوية كانت بتتقاس 23px واللوجو أطول، فكان بيركب على
       التاجلاين تحته */
    section[data-testid="stSidebar"] .st-key-cf_sb_brand .cf-title {
        min-height: 44px;
        align-items: center;
        margin-bottom: 4px;
    }
    /* أيقونة المعلومات لوحدها زي الموك أب: من غير كارت ولا سهم ⌄ -
       السهم في ‎div[aria-hidden]‎ التاني جوه الزرار. هدف اللمس فاضل ٤٤. */
    section[data-testid="stSidebar"] .st-key-cf_sb_brand [data-testid="stPopover"] button {
        border: none !important;
        background: transparent !important;
        min-width: 44px;
        min-height: 44px;
        opacity: 0.8;
    }
    section[data-testid="stSidebar"] .st-key-cf_sb_brand [data-testid="stPopover"] button:hover {
        opacity: 1;
        color: var(--cf-yellow);
    }
    section[data-testid="stSidebar"] .st-key-cf_sb_brand [data-testid="stPopover"] button div[aria-hidden="true"] {
        display: none;
    }
    /* صف الأيقونات تحت: كل عنصر بمقاسه الطبيعي عشان الصف كله يتوسّط -
       غلاف جرس التنبيهات كان بياخد ‎flex-grow‎ ويزق الباقي للحرف */
    section[data-testid="stSidebar"] .st-key-cf_sb_account [data-testid="stHorizontalBlock"]:not(.st-key-cf_sb_me) > * {
        flex: 0 0 auto !important;
        width: auto !important;
    }


    /* الصفوف الأفقية في الشريط (اللوجو + ⓘ فوق، و🏠 🌐 AR/EN تحت) - كان
       فيهم شريط تمرير رأسي صغير بأسهم فوق/تحت، محمد صوّره (2026-09-23).
       السبب: Streamlit بيدي الحاوية الأفقية ‎overflow:auto‎، وأي
       ‎st.markdown‎ جواها صندوقه بيطلع 16px تحت العنصر (متعوّض بـ
       ‎margin-bottom:-16px‎ في التخطيط، بس المتصفح بيحسبه برضه "محتوى
       زيادة" يتمرر). فالصف بيبقى أعلى من مساحته بـ 8-13px ويطلعله شريط.
       الصفين دول قصيرين ومفيش فيهم حاجة محتاجة تمرير أصلًا، فـ ‎visible‎:
       لا شريط، ولا قص لحلقة الفوكس أو تكبير الهوفر بتاع 🏠. */
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
        overflow: visible !important;
    }
    /* فاصل رفيع بين المجموعات - كان Ink شفاف (مختفي على الغامق)، بقى
       نسخة الحد الغامق العامة (--cf-edge) زي باقي البرنامج */
    section[data-testid="stSidebar"] hr.cf-sb-sep {
        margin: 10px 0;
        border: none;
        border-top: 1px solid var(--cf-edge);
    }

    /* تاجلاين تحت اللوجو. من غير letter-spacing/uppercase عمدًا: الحيلتين
       دول بيكسروا اتصال الحروف العربي (كل حرف بيتقطع لوحده) - مقبولة على
       نص إنجليزي بس مش على "استوديو الإنتاج بالذكاء الاصطناعي". */
    section[data-testid="stSidebar"] .cf-sb-tagline {
        font-size: 11px;
        font-weight: 600;
        opacity: 0.65;
        margin: 2px 0 10px;
    }

    /* تسمية قسم غير قابلة للنقر ("المشاريع") - أخف وزنًا من رابط حقيقي
       ("الرئيسية") عشان الاتنين ميتلخبطوش بصريًا مع بعض */
    section[data-testid="stSidebar"] .cf-sb-section-label {
        font-size: 12px;
        font-weight: 700;
        opacity: 0.6;
        padding: 4px 4px 2px;
    }

    /* الشكل الأساسي لرابط التنقّل (القاعدة دي لسه بتخدم أي لينك بنص).
       رابط "الرئيسية" نفسه بقى أيقونة لوحدها في آخر الشريط - شوف
       ‎cf-navlink--icon‎ تحت. */
    section[data-testid="stSidebar"] a.cf-navlink {
        display: flex;
        align-items: center;
        gap: 8px;
        text-align: __ALIGN__;
        padding: 10px 12px;
        border-radius: var(--cf-radius-md);
        border: 1px solid var(--cf-edge);
        background: var(--cf-navy-raised);
        font-weight: 600;
    }
    section[data-testid="stSidebar"] a.cf-navlink:hover,
    section[data-testid="stSidebar"] a.cf-navlink:focus-visible {
        border-color: var(--cf-accent);
    }
    /* نسخة الأيقونة لوحدها (🏠 من غير كلمة "الرئيسية" - طلب محمد
       2026-09-23): أيقونة **عريانة من غير كارت** - لا حد ولا خلفية، نفس
       شكل الجلوب (🌐) اللي جنبها بالظبط. ده طلب محمد الصريح لما شاف الصف
       على الهوا ("شيل الكارت اللي حوالين الأيقونة")، فبنلغي هنا الحد
       والخلفية اللي القاعدة العامة فوق بتحطهم.

       الشكل هو اللي اتشال، مش هدف اللمس: المساحة فاضلة ٤٤×٤٤ بس شفافة،
       عشان الأيقونة تفضل تتمسك بالصباع على التليفون (theme/mobile.py:
       TOUCH=44، وقاعدتها بتمسك ‎.stButton button‎ مش ‎a‎ فبتتفرض هنا).
       ‎flex:0 0 auto‎ عشان الحاوية الأفقية بتاعة Streamlit متمططهاش. */
    section[data-testid="stSidebar"] a.cf-navlink--icon {
        flex: 0 0 auto;
        justify-content: center;
        min-width: 44px;
        min-height: 44px;
        padding: 0 6px;
        font-size: 17px;
        line-height: 1;
        border: none;
        background: transparent;
    }
    /* من غير كارت، الإشارة الوحيدة إنها بتتضغط هي الحركة عند الهوفر.
       والفوكس المرئي لازم يفضل للتنقّل بالكيبورد - بس ‎outline‎ بره العنصر
       بدل حد كارت راجع تاني. */
    section[data-testid="stSidebar"] a.cf-navlink--icon:hover {
        border: none;
        background: transparent;
        transform: scale(1.12);
    }
    section[data-testid="stSidebar"] a.cf-navlink--icon:focus-visible {
        border: none;
        outline: 2px solid var(--cf-accent);
        outline-offset: 2px;
        border-radius: var(--cf-radius-md);
    }

    /* أيقونة اللغة (🌐) - بقت الأيقونة بس من غير كلمة "اللغة" (نفس الطلب).
       مش تسمية Streamlit عشان تسمية المكوّن بتترسم فوقه في سطر لوحدها،
       وإحنا عايزينها جنبه في نفس السطر. الكلمة نفسها لسه في
       ‎aria-label‎ بتاع المفتاح (label_visibility="collapsed")، فدي زينة
       بحتة و‎aria-hidden‎ في الـ HTML. */
    section[data-testid="stSidebar"] .cf-sb-globe {
        flex: 0 0 auto;
        font-size: 15px;
        line-height: 44px;
        opacity: 0.75;
        padding: 0 2px;
    }

    /* زرار "إنشاء مشروع جديد" - تعبئة صفرا صريحة (اللكنة) بدل شكل
       الـ expander الرمادي الافتراضي، زي الزرار المصمت في الموك أب.
       الفورم اللي بيتفتح تحته (اسم المشروع، النوع...) نفسه زي ما هو -
       فرق شكل الغلاف بس، مش تغيير في الوظيفة. */
    section[data-testid="stSidebar"] [data-testid="stExpander"] {
        border: none;
        background: transparent;
        margin-bottom: 8px;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary {
        background: var(--cf-yellow) !important;
        border-radius: var(--cf-radius-md) !important;
        border: none !important;
        justify-content: center;
        padding: 10px 12px;
        /* هدف لمس ٤٤ بكسل - نفس رقم mobile.TOUCH (theme/mobile.py)، بس
           العنوان ده (summary) مش ‎.stButton button‎ فمبيتغطاش بقاعدة
           TOUCH_CSS العامة هناك، فلازم يتفرض هنا صراحةً */
        min-height: 44px;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary p,
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary span,
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary svg {
        color: var(--cf-ink) !important;
        font-weight: 700 !important;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover,
    section[data-testid="stSidebar"] [data-testid="stExpander"] details[open] summary {
        background: #FFD940 !important;
    }

    /* صف الأفتار: دايرة أحرف أولى بدل صورة حقيقية (مفيش ميزة رفع صور
       حسابات لسه - العنصر ده مكانه جاهز ليوم ما الميزة تتبني) - نفس لغة
       ألوان العلامة (صفرا/كحلي) بدل ما تخترع بالتة جديدة */
    section[data-testid="stSidebar"] .cf-sb-avatar-row {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 6px 2px;
    }
    section[data-testid="stSidebar"] .cf-sb-avatar {
        flex: 0 0 auto;
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: var(--cf-yellow);
        color: var(--cf-ink);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        font-size: 14px;
    }
    section[data-testid="stSidebar"] .cf-sb-avatar-name {
        font-weight: 700;
        font-size: 14px;
        line-height: 1.3;
    }
    section[data-testid="stSidebar"] .cf-sb-avatar-role {
        font-size: 12px;
        opacity: 0.7;
    }

    /* حقل "الدور" - عرض للقراءة بس (الدور بيتغيّر من صفحة الفريق، مش من
       هنا)، فمصمم عمدًا من غير شكل سهم/قابلية ضغط عشان ميوهمش إنه اختيار */
    section[data-testid="stSidebar"] .cf-sb-field {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        font-size: 13px;
        padding: 8px 10px;
        margin: 2px 0 10px;
        border: 1px solid var(--cf-edge);
        border-radius: var(--cf-radius-md);
        background: var(--cf-navy-surface);
    }
    section[data-testid="stSidebar"] .cf-sb-field__label { opacity: 0.6; }
    section[data-testid="stSidebar"] .cf-sb-field__value { font-weight: 700; }

    /* مفتاح اللغة (AR/EN) - شكل segmented_control الافتراضي بيطلع حبة
       واحدة ملزّقة (نصف قطر بس على الحرف البرّاني لكل زرار، الاتنين
       مشتركين في حد نص شفاف في النص، والمختار بحد صفرا مش تعبئة) - ده شكل
       المكوّن الجاهز في Streamlit 1.64، مش اللي في الموك أب المعتمد
       (حبتين مستقلتين مدوّرتين بالكامل، فاصل واضح بينهم، المختارة تعبئة
       صفرا صريحة + حروف كحلي، الغير مختارة حد خفيف + حروف عادية).
       ‎[class*="st-key-lang_toggle"]‎ بدل ‎key=‎ عادي عشان نضمن إن الستايل ده
       بيمسك مفتاح اللغة بس - لو ظهر segmented_control تاني في مكان تاني
       من البرنامج (مفيش حاليًا، اتفحص) مش هيتأثر. */
    section[data-testid="stSidebar"] [class*="st-key-lang_toggle"] [role="radiogroup"] {
        gap: 6px !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-lang_toggle"] button[role="radio"] {
        border-radius: var(--cf-radius-pill) !important;
        border: 1px solid var(--cf-edge) !important;
        background: var(--cf-navy-raised) !important;
        color: var(--cf-text) !important;
        font-weight: 700 !important;
        /* حبتين صغيرتين - محمد شافهم على الهوا وقال إنهم أكبر من اللازم
           (2026-09-23). دلوقتي المفتاح أيقونة صغيرة في آخر الشريط، مش أول
           تحكم كبير فيه، فالمقاس بقى ٢٨ بارتفاع وخط ١١ وحشو ضيق بدل
           الافتراضي. الحجم ده للماوس بس - على التليفون بيرجع ٤٤ في
           الميديا كويري تحت (هدف اللمس مش بيتفاوض عليه). */
        min-height: 28px !important;
        height: 28px !important;
        padding: 0 12px !important;
        font-size: 11px !important;
        line-height: 1 !important;
    }
    /* تحت ٧٦٨ بكسل (تليفون/تابلت صغير) هدف اللمس بيرجع ٤٤ زي
       theme/mobile.py بالظبط - المكوّن ده مش ‎.stButton button‎ فمبيتغطاش
       بقاعدتها العامة. */
    @media (max-width: 768px) {
        section[data-testid="stSidebar"] [class*="st-key-lang_toggle"] button[role="radio"] {
            min-height: 44px !important;
            height: 44px !important;
            font-size: 13px !important;
        }
    }
    section[data-testid="stSidebar"] [class*="st-key-lang_toggle"] button[role="radio"]:hover {
        border-color: var(--cf-yellow) !important;
    }
    section[data-testid="stSidebar"] [class*="st-key-lang_toggle"] button[role="radio"][aria-checked="true"] {
        background: var(--cf-yellow) !important;
        border-color: var(--cf-yellow) !important;
        color: var(--cf-ink) !important;
    }
'''


# ---------------------------------------------------------------------------
# اتجاه انزلاق الشريط وهو بيتفتح/بيتقفل (العربي بس)
# ---------------------------------------------------------------------------
def collapse_slide_css(dir_):
    """بتصلّح اتجاه حركة فتح/قفل الشريط الجانبي في العربي.

    المشكلة اللي بلّغ عنها صاحب المنتج (2026-09-23): في العربي الشريط
    "بيطلع من نص الشاشة" بدل ما يدخل من حرف اليمين. في الإنجليزي الحركة
    سليمة.

    السبب (اتقاس فعليًا بـ Playwright، مش تخمين): Streamlit نفسه بيقفل
    الشريط بحاجتين مع بعض في نفس الـ 300ms — العرض بيروح صفر
    (‎min-width/max-width‎)، و‎transform: translateX(-<عرض الشريط>px)‎
    بيزحلقه. الـ ‎translateX‎ ده **فيزيائي** (ناحية الشمال دايمًا) لأن
    Streamlit مفترض إن الشريط واقف على الشمال. إحنا بنحط
    ‎.stApp { direction: rtl }‎ في العربي، فالشريط بيقف على اليمين صح، بس
    الإزاحة فضلت للشمال ⇒ الشريط بيتقفل *لجوه* الشاشة بدل ما يخرج من
    حرف اليمين.

    القياس قبل الإصلاح (شاشة 1280، عرض الشريط 300):
      إنجليزي (سليم): الحرف الشمال 0 → -66 → -173 → -300 (بيخرج بره)
      عربي (غلط):     الحرف الشمال فاضل ~980 والحرف اليمين 1280 → 1003
                       → 980 ⇒ بيتقلّص ناحية نقطة جوه الشاشة (النص).

    الحل: نعكس إشارة الإزاحة في العربي بس. القاعدة دي أقوى في الأسبقية
    من كلاس emotion بتاع Streamlit (‎(0,2,1)‎ مقابل ‎(0,1,0)‎) فمش محتاجة
    ‎!important‎.

    عن الـ 300px: ده العرض الافتراضي للشريط في Streamlit (‎FS()‎ بيحصره
    بين 200 و600)، ومقبض تغيير العرض مخفي على الموبايل أصلًا
    (‎theme/mobile.py‎) — والموبايل هو اللي الحركة دي بتبان فيه. لو مستخدم
    على الديسكتوب غيّر العرض، الحركة تفضل في الاتجاه الصح (من اليمين
    لجوه) لأن الحرف الشمال بيفضل بيتحرك ناحية الشمال طول الحركة، بس
    المسافة مش هتبقى مطابقة بالظبط. والشريط وهو مقفول عرضه صفر
    و‎overflow-x: hidden‎ فوق، فمفيش أي جزء منه بيفضل ظاهر في أي حالة.
    ‎--cf-sidebar-width‎ سايبينها متغيّر عشان لو اتظبطت من مكان تاني في
    المستقبل تمشي من غير ما القاعدة دي تتغيّر.
    """
    if dir_ != "rtl":
        return ""
    return '''
    section[data-testid="stSidebar"][aria-expanded="false"] {
        transform: translateX(var(--cf-sidebar-width, 300px));
    }
    '''
