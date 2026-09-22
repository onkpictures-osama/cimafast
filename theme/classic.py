"""نسخة الشكل الحالية (classic) — الـ CSS اللي الـ 12 مستخدم شايفينه دلوقتي.

منقول حرفيًا من ‎app.py‎ (تلات أماكن كانت بتحقن CSS: الجلوبال، شاشة الدخول،
والقالب الكبير) من غير أي تغيير بصري. أي تطوير في الشكل بيروح في ‎glass.py‎
تحت الـ flag، وده بيفضل زي ما هو عشان المسار الافتراضي ميتغيرش.

القوالب: ‎__DIR__‎ / ‎__ALIGN__‎ / ‎__ROWDIR__‎ بيتبدلوا في ‎inject.py‎.
"""

BASE_CSS = r'''
    /* The app is dark-only (config.toml base = "dark"), but the page never said
       so, and browsers drew scrollbars, autofill and native pickers in light
       mode on top of it. */
    :root { color-scheme: dark; }

    /* The document-attributes script (inject._document_attrs) is zero-height,
       but it still sits in Streamlit's flex column and takes a full 1rem gap
       - it pushed every page down 16px. Out of the flow entirely; the script
       has already run by the time this applies. */
    .stElementContainer:has(script[data-cf-doc]) { display: none; }

    /* Global RTL/LTR styling */
    * { box-sizing: border-box; }
    
    /* Form labels: RTL for Arabic, LTR for English */
    label { direction: auto; text-align: right; }
    
    /* Text areas and inputs: LTR by default */
    textarea, input { direction: ltr !important; text-align: left; }
    
    /* Paragraphs with Arabic: RTL */
    p[dir="rtl"], div[dir="rtl"] { direction: rtl; text-align: right; }
    p[dir="ltr"], div[dir="ltr"] { direction: ltr; text-align: left; }
    
    /* Error messages: auto-direction */
    .stError, .stWarning, .stSuccess, .stInfo { 
        direction: auto; 
        text-align: right;
    }
    
    /* Buttons: center alignment */
    button { text-align: center; }

    /* زرار أساسي (primary) = تعبئة اللكنة + حروف Ink، زي جدول الأزرار في
       الدليل ص 08. الحروف Ink مش أبيض: أبيض على الأصفر 1.54:1 وبيختفي.
       الشريط الجانبي ليه قاعدة أخص فوق (زرار الإعدادات Royal) فمبيتأثرش. */
    [data-testid="stBaseButton-primary"],
    [data-testid="stBaseButton-primaryFormSubmit"] {
        background-color: var(--cf-accent) !important;
        border-color: var(--cf-accent) !important;
        color: var(--cf-on-accent) !important;
        font-weight: 600;
    }
    [data-testid="stBaseButton-primary"] p,
    [data-testid="stBaseButton-primary"] span,
    [data-testid="stBaseButton-primaryFormSubmit"] p,
    [data-testid="stBaseButton-primaryFormSubmit"] span {
        color: var(--cf-on-accent) !important;
    }

    /* حلقة التركيز باللكنة على أي عنصر تفاعلي - شرط في الدليل (ص 06 ·
       Accessibility)، ومكانش موجود قبل كده غير على الروابط. */
    .stApp :focus-visible {
        outline: 2px solid var(--cf-accent);
        outline-offset: 2px;
    }
   '''

LOGIN_CSS = r'''
        /* شاشة تسجيل الدخول.
           الحاجة الوحيدة اللي اتغيرت عن النسخة اللي كانت في app.py: القواعد
           بقت متربطة بمفاتيح الخانتين (st-key-_login_username /
           st-key-_login_password) بدل stForm العام. ملحوظة: ‎st.form‎ نفسه
           مبياخدش كلاس ‎st-key-*‎ في Streamlit 1.64 — الخانات اللي بياخدوه.
           السبب إن البلوك ده بقى بيتحقن مرة واحدة في الأول مع باقي الستايل
           الجلوبال، عشان ميعملش حاوية Streamlit زيادة على شاشة الدخول —
           الحاوية الزيادة دي كانت بتزح الفورم كله ١٦ بكسل لتحت. الربط
           بالمفتاح بيخلي القواعد تفضل مأثرة على فورم الدخول بس، مش على كل
           الفورمات في البرنامج. */
        .cf-login h2 { text-align: center; margin-top: 12vh; }
        /* اللوجو الرسمي بدل العنوان النصي. بياخد نفس المسافة العلوية اللي
           كان العنوان بياخدها (12vh) عشان الفورم ميتزحش عن مكانه. */
        .cf-login__logo {
            display: flex;
            justify-content: center;
            margin-top: 12vh;
            margin-bottom: 12px;
        }
        .cf-login p { text-align: center; opacity: 0.75; margin-bottom: 0; }
        div[class*="st-key-_login_username"] label p,
        div[class*="st-key-_login_password"] label p { direction: rtl; text-align: right; }
        div[class*="st-key-_login_username"] input,
        div[class*="st-key-_login_password"] input { direction: ltr; text-align: left; }
'''

MAIN_CSS = r'''    
    
    /* اتجاه الواجهة: يمين-لشمال للعربي، شمال-ليمين للإنجليزي - بيتغير
       تلقائيًا مع زرار EN/AR، وبيخلي النص يترتب صح جوه نفسه */
    .stApp {
        direction: __DIR__;
    }
    /* شريط Deploy/القائمة بتاع Streamlit - بيتقلب للناحية المقابلة وقت
       العربي عشان ميتلخبطش مع الشريط الجانبي اللي بيبقى واقف في نفس الناحية */
    header[data-testid="stHeader"] [data-testid="stToolbar"] {
        flex-direction: __ROWDIR__;
    }
    .stApp .stTextInput input,
    .stApp .stTextArea textarea,
    .stApp .stNumberInput input {
        text-align: __ALIGN__;
    }
    /* عناصر لازم تفضل شمال-ليمين زي هي (كود إنجليزي، أرقام قوائم منسدلة) */
    .stApp code, .stApp pre {
        direction: ltr;
        text-align: left;
    }
    /* خطوط البراند: Inter للاتيني و Cairo للعربي (الدليل ص 06).
       الترتيب في الستاك هو كل الحيلة - Inter مفيهوش حرف عربي واحد، فأي
       حرف عربي بيقع تلقائيًا على Cairo من غير ما نفحص اللغة في بايثون ولا
       نلف العربي في عنصر لوحده. الاتنين مستضافين محليًا في static/fonts. */
    .stApp, [dir="rtl"], [dir="ltr"] {
        font-family: var(--cf-font);
    }
    /* سلّم الوزن من الدليل: العناوين 700، التسميات والأزرار 600 */
    .stApp h1, .stApp h2, .stApp h3 { font-weight: 700; }
    /* Streamlit نفسه بيحط text-align: left افتراضيًا على العناوين والنصوص
       التوضيحية (caption) وفقرات الـ markdown، من غير ما يهتم باتجاه
       الصفحة - فبنجبرها تتبع اتجاه اللغة الحالية (يمين للعربي، شمال
       للإنجليزي) عشان النص التوضيحي/العناوين تقرأ صح من نفس جهة القراءة.
       الحاجات اللي إحنا عايزينها في النص بالذات (زي اسم المشروع) ليها
       تنسيق inline خاص بيها بيغلب القاعدة العامة دي */
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
    .stApp [data-testid="stCaptionContainer"],
    .stApp [data-testid="stMarkdownContainer"] p {
        text-align: __ALIGN__;
    }
    /* اسم كل خانة يتحط فوق ومنتصف الخانة، باللون الأصفر (في المحتوى الرئيسي) */
    [data-testid="stWidgetLabel"] {
        width: 100%;
    }
    [data-testid="stWidgetLabel"] p,
    [data-testid="stWidgetLabel"] label {
        width: 100%;
        text-align: center;
        color: var(--cf-accent) !important;
        font-weight: 600;
    }
    /* عنوان أي قايمة قابلة للطي (expander) يفضل ثابت في مكانه لما تتفتح
       ومحتواها الطويل بيعمل scroll (زي وصف شخصية طويل) - عشان اليوزر يفضل
       شايف هو بيعدّل في إيه بالظبط حتى لو دخل عميق في النص. خلفية صلبة (مش
       شفافة) عشان النص اللي بيتعدّى تحته ميبانش وهو ماشي. */
    [data-testid="stExpander"] summary {
        position: sticky;
        top: 0;
        z-index: 2;
        background: var(--cf-glass-opaque);
    }
    /* الشريط الجانبي هو "الحقل الأصفر" بتاع البراند - نفس اتجاه الواجهة،
       وبيقلب مكانه (يمين للعربي، شمال للإنجليزي).

       كان تدرّج (E8B923 → C99A2E) عشان يهدّي حدة دهبي مش مضبوط. مع لون
       البراند الرسمي (CF Yellow #FECA05) رجع لون واحد مصمت زي ما الدليل
       بيقول بالنص: "الحقل الأصفر هو البراند، مش سطح - نفس القيمة في
       الوضعين". والتباين بقى أحسن كمان: Ink على الأصفر 9.67:1 (AAA) في كل
       نقطة، بدل 6.27:1 في قاع التدرّج القديم. */
    section[data-testid="stSidebar"] {
        direction: __DIR__;
        background: var(--cf-yellow);
    }
    section[data-testid="stSidebar"] * {
        color: var(--cf-on-brand) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] label {
        color: var(--cf-on-brand) !important;
    }
    /* لو الشريط الجانبي بيتقفل/بيتفتح (أنيميشن العرض بيتغير من صفر للكامل)،
       لازم النص ميلفش رأسي حرف تحت حرف - يفضل مقصوص بالعرض بس (…) */
    section[data-testid="stSidebar"] .cf-sidebar-header {
        overflow: hidden;
    }
    section[data-testid="stSidebar"] .cf-sidebar-header .cf-title {
        font-size: 22px;
        font-weight: 800;
        line-height: 1.3;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    section[data-testid="stSidebar"] .cf-sidebar-header .cf-subtitle {
        font-size: 13px;
        opacity: 0.85;
        margin-top: 2px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    section[data-testid="stSidebar"] {
        overflow-x: hidden !important;
    }
    /* صندوق صغير حوالين وصف البرنامج - بيوضح إنه مجرد تنويه، مش اختيار قابل للضغط */
    section[data-testid="stSidebar"] .cf-sidebar-header .cf-desc-box {
        font-size: 11px;
        line-height: 1.5;
        opacity: 0.9;
        margin-top: 10px;
        padding: 8px 10px;
        border: 1px solid rgba(27, 37, 75, 0.35);
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.18);
    }
    /* صندوق صغير لعرض بيانات المستخدم الحالي (الاسم والوظيفة) فوق الإعدادات -
       أبيض صريح، عشان يبقى مميز عن باقي عناصر الشريط الجانبي الأصفر */
    section[data-testid="stSidebar"] .cf-owner-box {
        font-size: 13px;
        font-weight: 600;
        line-height: 1.5;
        margin: 4px 0 10px 0;
        padding: 10px 12px;
        border: 1px solid rgba(27, 37, 75, 0.25);
        border-radius: 8px;
        background: var(--cf-white);
        color: var(--cf-on-brand);
    }
    /* نصوص جوه صناديق الإدخال والأزرار (خلفيتها غامقة من الثيم) لازم تفضل
       فاتحة عشان تتقرا فوق الخلفية الغامقة بتاعتها هي (مش الأصفر اللي حواليها) */
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] textarea,
    section[data-testid="stSidebar"] [data-baseweb="select"] *,
    section[data-testid="stSidebar"] .stButton button,
    section[data-testid="stSidebar"] .stButton button p,
    section[data-testid="stSidebar"] .stButton button span,
    section[data-testid="stSidebar"] .stDownloadButton button {
        color: var(--cf-text) !important;
    }
    /* خلفية غامقة صريحة لكل الأزرار في الشريط الجانبي، عشان النص الفاتح
       يفضل واضح فوقها مهما كان لون الثيم الافتراضي للزرار */
    section[data-testid="stSidebar"] .stButton button,
    section[data-testid="stSidebar"] .stDownloadButton button {
        background-color: var(--cf-on-brand) !important;
        border: 1px solid var(--cf-on-brand) !important;
    }
    section[data-testid="stSidebar"] .stButton button:hover,
    section[data-testid="stSidebar"] .stDownloadButton button:hover {
        background-color: var(--cf-navy-raised) !important;
        border-color: var(--cf-accent) !important;
        color: var(--cf-text) !important;
    }
    section[data-testid="stSidebar"] .stButton button:disabled,
    section[data-testid="stSidebar"] .stButton button:disabled p {
        color: var(--cf-mist-dark) !important;
        background-color: var(--cf-glass-opaque) !important;
        opacity: 0.7;
    }
    /* زرار الـ popover (ℹ️ بجانب اسم البرنامج) - نفس مشكلة الـ expander
       والـ segmented_control بالظبط: Streamlit بيديله خلفية غامقة
       افتراضية (مش .stButton فمابيلحقهاش القاعدة فوق)، والنص فوقها كحلي
       من القاعدة العامة - كحلي على غامق يختفي. */
    section[data-testid="stSidebar"] [data-testid="stPopoverButton"] {
        background-color: rgba(27, 37, 75, 0.1) !important;
        border: 1px solid rgba(27, 37, 75, 0.3) !important;
    }
    /* زرار الإعدادات - مربع وأزرق ومختلف شكلًا ولونًا عن باقي أزرار
       الشريط الجانبي (زي ما طلب المستخدم)، بترس أبيض في النص.
       الأزرق بقى CF Royal من بالتة البراند بدل الأزرق التقريبي: 6.24:1 على
       الحقل الأصفر (AA) والأبيض فوقه 8.6:1، ولسه مميز تمامًا عن الكحلي
       بتاع باقي الأزرار. */
    section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
        background-color: var(--cf-royal) !important;
        border: 1px solid var(--cf-royal) !important;
        color: var(--cf-white) !important;
        width: 44px !important;
        height: 44px !important;
        min-width: 44px !important;
        padding: 0 !important;
        font-size: 20px !important;
        border-radius: var(--cf-radius-md) !important;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:hover {
        background-color: var(--cf-navy) !important;
        border-color: var(--cf-white) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] p {
        color: var(--cf-white) !important;
        font-size: 20px !important;
    }
    .cf-settings-label {
        font-weight: 700;
        padding-top: 10px;
    }
    /* علامة ميكروفون خفيفة على كل خانة كتابة - مجرد تنويه إننا فاكرين
       ميزة الكتابة بالصوت وهنضيفها لاحقًا، مش شغالة فعليًا دلوقتي.
       بنستخدم أيقونة Material Symbols (نفس خط الأيقونات اللي Streamlit
       نفسه بيستخدمه) بدل الإيموجي، عشان تبقى شكلها بسيط وكلاسيكي وتقدر
       تتلوّن أبيض بدل ما تيجي بألوان الإيموجي الثابتة. */
    [data-testid="stTextInputRootElement"], [data-testid="stTextAreaRootElement"] {
        position: relative;
    }
    [data-testid="stTextInputRootElement"]::after,
    [data-testid="stTextAreaRootElement"]::after {
        content: "mic";
        font-family: "Material Symbols Rounded";
        font-weight: normal;
        font-style: normal;
        position: absolute;
        left: 10px;
        font-size: 14px;
        color: var(--cf-text);
        opacity: 0.55;
        pointer-events: none;
        z-index: 1;
    }
    /* في خانة سطر واحد بتتوسط رأسيًا جوه الصندوق؛ في الخانة الطويلة (Textarea)
       بتقف أعلى الصندوق من جوه عشان متتلخبطش مع النص وهو بيكبر لأسفل */
    [data-testid="stTextInputRootElement"]::after { top: 50%; transform: translateY(-50%); }
    [data-testid="stTextAreaRootElement"]::after { top: 8px; }
    /* نص المثال (placeholder) يفضل شفاف أكتر عشان يبان إنه نص مؤقت للتوضيح
       بس، ويختفي تمامًا وقت التركيز/الكتابة في الخانة عشان ميتزنقش مع أي
       تلميح تاني زي "Press Enter to..." - وبيرجع يظهر تاني لو رجعت الخانة فاضية */
    .stApp input::placeholder,
    .stApp textarea::placeholder {
        opacity: 0.4 !important;
    }
    .stApp input:focus::placeholder,
    .stApp textarea:focus::placeholder {
        opacity: 0 !important;
    }
    /* تلميح "Press Enter to apply/submit" بتاع Streamlit - نص إنجليزي قصير،
       فبيفضل من الشمال ولاتجاه LTR، وبخط أصغر، وبمسافة تبعده عن حواف
       الخانة عشان ميتداخلش مع أي نص جوه الخانة نفسها */
    [data-testid="InputInstructions"] {
        text-align: left !important;
        direction: ltr !important;
        font-size: 10px !important;
        opacity: 0.55 !important;
        top: auto !important;
        bottom: -20px !important;
        right: auto !important;
        left: 4px !important;
    }
    /* عنوان أي قسم قابل للطي (expander) في الشريط الجانبي - خلفية وحدود
       واضحة بشكل ثابت، عشان النص والسهم يفضلوا باينين في أي حالة (مقفول،
       مفتوح، عليه الماوس) من غير ما يعتمدوا على خلفية شفافة ممكن تختفي فيها */
    section[data-testid="stSidebar"] [data-testid="stExpander"] {
        background-color: rgba(27, 37, 75, 0.07);
        border: 1px solid rgba(27, 37, 75, 0.3);
        border-radius: 10px;
        margin-bottom: 6px;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary,
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary p,
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary span {
        color: var(--cf-on-brand) !important;
    }
    /* عنوان الـ expander ثابت (sticky) جوه الشريط الجانبي لازم خلفيته صلبة
       بلون الشريط نفسه (ذهبي) مش لون المحتوى الرئيسي الغامق - وإلا نص كحلي
       على خلفية كحلية بيختفي */
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary {
        background: var(--cf-accent) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover,
    section[data-testid="stSidebar"] [data-testid="stExpander"] details[open] summary {
        background-color: rgba(27, 37, 75, 0.14) !important;
        border-radius: 8px;
    }
    /* segmented_control (زرار اللغة AR/EN) - نفس مشكلة الـ expander بالظبط:
       Streamlit بيحط خلفية غامقة افتراضية على القطعة الغير مختارة، والقاعدة
       العامة فوق بتحط نص كحلي على أي حاجة في الشريط - نص كحلي على خلفية
       غامقة بيختفي. القطعة المختارة أصلاً خلفيتها فاتحة (تينت ذهبي) فمالهاش
       نفس المشكلة، بس بنثبّتها هنا برضو عشان الاتساق. */
    section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button[role="radio"] {
        background-color: rgba(27, 37, 75, 0.08) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button[role="radio"][aria-checked="true"] {
        background-color: rgba(254, 202, 5, 0.45) !important;
    }
    /* علامة "تم الحفظ" - نص رفيع بسيط على أرضية التصميم، مش شكل زرار،
       بتفضل ظاهرة بعد الحفظ لحد ما المستخدم يحفظ سجل تاني */
    .cf-saved-badge {
        font-size: 12px;
        font-weight: 400;
        color: var(--cf-text);
        opacity: 0.75;
        margin-top: -6px;
        margin-bottom: 8px;
    }
    /* فاصل بصري خفيف بين كل اقتراح دمج (شخصيات/أماكن متشابهة) وبعضه،
       عشان القايمة الطويلة متبقاش سايحة من غير حدود واضحة بين الأسئلة */
    hr.cf-soft-sep {
        border: none;
        border-top: 1px solid rgba(255, 255, 255, 0.16);
        margin: 18px 0;
    }
    /* بادج علامة الصح - أزرق دايمًا (مش أخضر) عشان يفضل متماشي مع بالتة
       البراند. الأزرق بقى CF Royal مرفوع لدرجة تتقرا على Midnight، والحرف
       فوقه Ink مش أبيض: الأبيض على الأزرق ده 2.51:1 (كان بيفشل من غير ما
       حد يقيسه)، و Ink عليه 5.91:1. */
    .cf-check-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 16px;
        height: 16px;
        border-radius: 4px;
        background: var(--cf-info);
        color: var(--cf-on-info);
        font-size: 11px;
        font-weight: 800;
        line-height: 1;
    }
    textarea {
        resize: vertical !important;
        min-height: 90px !important;
    }
    textarea::-webkit-resizer {
        background: repeating-linear-gradient(
            135deg,
            var(--cf-accent), var(--cf-accent) 3px,
            var(--cf-on-brand) 3px, var(--cf-on-brand) 6px
        );
    }
    .cf-stepper {
        display: flex;
        gap: 10px;
        margin: 10px 0 14px 0;
    }
    .cf-stage {
        flex: 1;
        text-align: center;
        padding: 14px 6px;
        border-radius: 14px;
        background: var(--cf-glass-opaque);
        border: 2px solid transparent;
    }
    .cf-stage-icon { font-size: 16px; margin-bottom: 5px; }
    .cf-stage-icon .cf-check-badge { width: 20px; height: 20px; font-size: 13px; border-radius: 6px; }
    .cf-stage-label { font-size: 12px; font-weight: 600; color: var(--cf-text); }
    .cf-stage-done { background: rgba(111, 168, 224, 0.14); border-color: var(--cf-info); }
    .cf-stage-current { border-color: var(--cf-accent); box-shadow: 0 0 0 1px rgba(254, 202, 5, 0.35); }
    .cf-stage-pending { opacity: 0.5; }
    /* سطر التقدّم اللي حل محل كروت المراحل: شريط رفيع + جملة واحدة. */
    .cf-progress { margin: 6px 0 14px 0; }
    /* روابط التنقّل في الـ sidebar (الرئيسية، الفريق، الجدول): شكل زرار، نفس التاب */
    a.cf-navlink {
        display: block; text-align: center; text-decoration: none; color: var(--cf-text);
        padding: 7px 12px; margin: 2px 0; border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.18); background: rgba(255, 255, 255, 0.04);
    }
    a.cf-navlink:hover, a.cf-navlink:focus-visible { border-color: var(--cf-accent); color: var(--cf-text); }
    .cf-progress-bar { display: flex; gap: 4px; margin-bottom: 6px; }
    .cf-progress-seg {
        flex: 1; height: 4px; border-radius: 2px;
        background: rgba(255, 255, 255, 0.14);
    }
    .cf-progress-seg--done { background: var(--cf-info); }
    .cf-progress-seg--current { background: var(--cf-accent); }
    .cf-progress-text { font-size: 0.9rem; color: rgba(255, 255, 255, 0.78); }
    .cf-progress-text strong { color: var(--cf-text); font-weight: 600; }
    .cf-copy-hint {
        font-weight: 700;
        color: var(--cf-accent);
        margin-bottom: 6px;
    }
    div[data-testid="stCodeBlock"] button[title="Copy to clipboard"],
    div[data-testid="stCodeBlock"] [data-testid="stCodeCopyButton"] {
        opacity: 1 !important;
        transform: scale(1.4);
        background: var(--cf-accent) !important;
        border-radius: 6px !important;
    }
    /* زرار الحذف الجماعي - بيبقى أحمر تحذيري في أي مكان مستخدم فيه
       (أي عنصر container بمفتاح بيبدأ بـ bulk_delete_) */
    [class*="st-key-bulk_delete_"] button {
        background-color: var(--cf-danger) !important;
        border-color: var(--cf-danger) !important;
    }
    [class*="st-key-bulk_delete_"] button p {
        color: var(--cf-white) !important;
    }
    '''
