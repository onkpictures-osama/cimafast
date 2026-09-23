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
    /* ستايل خلفية الشريط الجانبي وعناصره (اللوجو، الروابط، زرار إنشاء
       مشروع، صف الأفتار، حقل الدور...) بقى في theme/sidebar.py — سطح غامق
       دلوقتي (استثناء موثّق ومؤرّخ 2026-09-23 من قاعدة "الحقل الأصفر"،
       التفاصيل في theme/brand.py)، مش الحقل الأصفر القديم. القواعد اللي
       كانت هنا (تلوين كل حاجة يدوي عشان الحقل الأصفر) بقت غير لازمة: نفس
       ثيم Streamlit الغامق الافتراضي اللي باقي البرنامج شغال بيه بقى شغال
       هنا كمان من غير عكس. */
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
    /* ستايل الـ expander (زرار إنشاء مشروع) والـ segmented_control (اللغة)
       جوه الشريط الجانبي بقى في theme/sidebar.py مع باقي إعادة التصميم. */
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
    /* H4: قايمة التنبيهات جوه الجرس. الجديد بعلامة صفرا على ناحية بداية
       السطر (‎border-inline-start‎ بيقلب لوحده بين العربي والإنجليزي). كل صف
       رابط كامل ≥44px عشان يتمسك بالصباع على التليفون. */
    .cf-notif-list { display: flex; flex-direction: column; gap: 4px; max-height: 60vh; overflow-y: auto; }
    a.cf-notif {
        display: flex; flex-direction: column; gap: 2px; min-height: 44px; justify-content: center;
        padding: 6px 10px; border-radius: 8px; text-decoration: none; color: var(--cf-text);
        border-inline-start: 3px solid transparent; background: rgba(255, 255, 255, 0.03);
    }
    a.cf-notif:hover, a.cf-notif:focus-visible { background: rgba(255, 255, 255, 0.08); color: var(--cf-text); }
    a.cf-notif--new { border-inline-start-color: var(--cf-accent); }
    .cf-notif__text { font-weight: 600; font-size: 0.92rem; }
    .cf-notif__meta { font-size: 0.78rem; opacity: 0.75; }
    .cf-notif-badge {
        display: inline-block; min-width: 20px; height: 20px; padding: 0 6px; border-radius: 10px;
        background: var(--cf-accent); color: var(--cf-on-accent); font-size: 12px; font-weight: 700;
        line-height: 20px; text-align: center;
    }
    /* نسخة الرابط جوه الشريط الجانبي (سطح غامق دلوقتي، مش الحقل الأصفر)
       في theme/sidebar.py مع باقي ستايل الشريط الجانبي المُعاد تصميمه. */
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
