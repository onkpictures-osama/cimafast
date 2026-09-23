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

    /* رابط "الرئيسية" - صف كامل العرض بدل الشكل المتوسط القديم، عشان
       يبقى أول عنصر ملموس في الشريط زي الموك أب */
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
'''
