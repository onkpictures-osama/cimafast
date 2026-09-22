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
    /* Readex Pro للعربي والإنجليزي */
    .stApp {
        font-family: "Readex Pro", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    [dir="rtl"] {
        font-family: "Readex Pro", -apple-system, BlinkMacSystemFont, sans-serif;
    }
    [dir="ltr"] {
        font-family: "Readex Pro", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
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
        color: #E8B923 !important;
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
        background: #16233F;
    }
    /* الشريط الجانبي بالكامل أصفر - نفس اتجاه الواجهة، وبيقلب مكانه
       (يمين للعربي، شمال للإنجليزي) */
    section[data-testid="stSidebar"] {
        direction: __DIR__;
        background-color: #E8B923;
    }
    section[data-testid="stSidebar"] * {
        color: #12203D !important;
    }
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] label {
        color: #12203D !important;
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
        border: 1px solid rgba(18, 32, 61, 0.35);
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
        border: 1px solid rgba(18, 32, 61, 0.25);
        border-radius: 8px;
        background: #FFFFFF;
        color: #12203D;
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
        color: #F5F1E6 !important;
    }
    /* خلفية غامقة صريحة لكل الأزرار في الشريط الجانبي، عشان النص الفاتح
       يفضل واضح فوقها مهما كان لون الثيم الافتراضي للزرار */
    section[data-testid="stSidebar"] .stButton button,
    section[data-testid="stSidebar"] .stDownloadButton button {
        background-color: #12203D !important;
        border: 1px solid #12203D !important;
    }
    section[data-testid="stSidebar"] .stButton button:hover,
    section[data-testid="stSidebar"] .stDownloadButton button:hover {
        background-color: #1B2E52 !important;
        border-color: #E8B923 !important;
        color: #F5F1E6 !important;
    }
    section[data-testid="stSidebar"] .stButton button:disabled,
    section[data-testid="stSidebar"] .stButton button:disabled p {
        color: #8A93A6 !important;
        background-color: #16233F !important;
        opacity: 0.7;
    }
    /* زرار الإعدادات - مربع وأزرق ومختلف شكلًا ولونًا عن باقي أزرار
       الشريط الجانبي (زي ما طلب المستخدم)، بترس أبيض في النص */
    section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
        background-color: #2D9CDB !important;
        border: 1px solid #2D9CDB !important;
        color: #FFFFFF !important;
        width: 44px !important;
        height: 44px !important;
        min-width: 44px !important;
        padding: 0 !important;
        font-size: 20px !important;
        border-radius: 10px !important;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:hover {
        background-color: #268BC4 !important;
        border-color: #FFFFFF !important;
    }
    section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] p {
        color: #FFFFFF !important;
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
        color: #F5F1E6;
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
        background-color: rgba(18, 32, 61, 0.07);
        border: 1px solid rgba(18, 32, 61, 0.3);
        border-radius: 10px;
        margin-bottom: 6px;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary,
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary p,
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary span {
        color: #12203D !important;
    }
    /* عنوان الـ expander ثابت (sticky) جوه الشريط الجانبي لازم خلفيته صلبة
       بلون الشريط نفسه (ذهبي) مش لون المحتوى الرئيسي الغامق - وإلا نص كحلي
       على خلفية كحلية بيختفي */
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary {
        background: #E8B923 !important;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover,
    section[data-testid="stSidebar"] [data-testid="stExpander"] details[open] summary {
        background-color: rgba(18, 32, 61, 0.14) !important;
        border-radius: 8px;
    }
    /* segmented_control (زرار اللغة AR/EN) - نفس مشكلة الـ expander بالظبط:
       Streamlit بيحط خلفية غامقة افتراضية على القطعة الغير مختارة، والقاعدة
       العامة فوق بتحط نص كحلي على أي حاجة في الشريط - نص كحلي على خلفية
       غامقة بيختفي. القطعة المختارة أصلاً خلفيتها فاتحة (تينت ذهبي) فمالهاش
       نفس المشكلة، بس بنثبّتها هنا برضو عشان الاتساق. */
    section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button[role="radio"] {
        background-color: rgba(18, 32, 61, 0.08) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button[role="radio"][aria-checked="true"] {
        background-color: rgba(232, 185, 35, 0.45) !important;
    }
    /* علامة "تم الحفظ" - نص رفيع بسيط على أرضية التصميم، مش شكل زرار،
       بتفضل ظاهرة بعد الحفظ لحد ما المستخدم يحفظ سجل تاني */
    .cf-saved-badge {
        font-size: 12px;
        font-weight: 400;
        color: #F5F1E6;
        opacity: 0.75;
        margin-top: -6px;
        margin-bottom: 8px;
    }
    /* فاصل بصري خفيف بين كل اقتراح دمج (شخصيات/أماكن متشابهة) وبعضه،
       عشان القايمة الطويلة متبقاش سايحة من غير حدود واضحة بين الأسئلة */
    hr.cf-soft-sep {
        border: none;
        border-top: 1px solid rgba(245, 241, 230, 0.16);
        margin: 18px 0;
    }
    /* بادج علامة الصح - أزرق فاتح دايمًا (مش أخضر) عشان يفضل متماشي مع
       بالتة ألوان البراند (أصفر / أزرق فاتح / كحلي غامق / أبيض / رمادي) */
    .cf-check-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 16px;
        height: 16px;
        border-radius: 4px;
        background: #2D9CDB;
        color: #FFFFFF;
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
            #E8B923, #E8B923 3px,
            #12203D 3px, #12203D 6px
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
        background: #16233F;
        border: 2px solid transparent;
    }
    .cf-stage-icon { font-size: 16px; margin-bottom: 5px; }
    .cf-stage-icon .cf-check-badge { width: 20px; height: 20px; font-size: 13px; border-radius: 6px; }
    .cf-stage-label { font-size: 12px; font-weight: 600; color: #F5F1E6; }
    .cf-stage-done { background: rgba(45, 156, 219, 0.14); border-color: #2D9CDB; }
    .cf-stage-current { border-color: #E8B923; box-shadow: 0 0 0 1px rgba(232, 185, 35, 0.35); }
    .cf-stage-pending { opacity: 0.5; }
    /* سطر التقدّم اللي حل محل كروت المراحل: شريط رفيع + جملة واحدة. */
    .cf-progress { margin: 6px 0 14px 0; }
    /* روابط التنقّل في الـ sidebar (الرئيسية، الفريق، الجدول): شكل زرار، نفس التاب */
    a.cf-navlink {
        display: block; text-align: center; text-decoration: none; color: #F5F1E6;
        padding: 7px 12px; margin: 2px 0; border-radius: 8px;
        border: 1px solid rgba(245, 241, 230, 0.18); background: rgba(245, 241, 230, 0.04);
    }
    a.cf-navlink:hover, a.cf-navlink:focus-visible { border-color: #E8B923; color: #F5F1E6; }
    .cf-progress-bar { display: flex; gap: 4px; margin-bottom: 6px; }
    .cf-progress-seg {
        flex: 1; height: 4px; border-radius: 2px;
        background: rgba(245, 241, 230, 0.14);
    }
    .cf-progress-seg--done { background: #2D9CDB; }
    .cf-progress-seg--current { background: #E8B923; }
    .cf-progress-text { font-size: 0.9rem; color: rgba(245, 241, 230, 0.78); }
    .cf-progress-text strong { color: #F5F1E6; font-weight: 600; }
    .cf-copy-hint {
        font-weight: 700;
        color: #E8B923;
        margin-bottom: 6px;
    }
    div[data-testid="stCodeBlock"] button[title="Copy to clipboard"],
    div[data-testid="stCodeBlock"] [data-testid="stCodeCopyButton"] {
        opacity: 1 !important;
        transform: scale(1.4);
        background: #E8B923 !important;
        border-radius: 6px !important;
    }
    /* زرار الحذف الجماعي - بيبقى أحمر تحذيري في أي مكان مستخدم فيه
       (أي عنصر container بمفتاح بيبدأ بـ bulk_delete_) */
    [class*="st-key-bulk_delete_"] button {
        background-color: #DC2626 !important;
        border-color: #DC2626 !important;
    }
    [class*="st-key-bulk_delete_"] button p {
        color: #FFFFFF !important;
    }
    '''
