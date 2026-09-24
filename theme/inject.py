"""حقن الـ CSS — المكان الوحيد اللي بيكتب ستايل في الصفحة.

قبل كده كان في تلات أماكن في ‎app.py‎ بتحقن CSS (سطر 34 جلوبال، سطر 108
شاشة الدخول، وقالب 330 سطر في النص). بقوا تلات دوال هنا، والفرق إن كل
واحدة بتعرف النسخة (classic / glass) وبتزوّد طبقة المادة لو الفلاج شغال.

الترتيب مهم: ‎classic‎ هو الطبقة البنيوية (الاتجاه، RTL، مواضع العناصر)،
و‎glass‎ طبقة مادة فوقها. كده منطق RTL بيفضل في مكان واحد ومش متكرر.

ملحوظة مهمة عن الفراغ الرأسي: كل نداء ‎st.markdown‎ بيعمل حاوية عنصر في
شبكة Streamlit، والحاوية بتاخد فراغ رأسي حتى لو جواها ‎<style>‎ بس. فأي
حقن فاضي لازم ميحصلش خالص — ‎_emit‎ بترجع من غير ما تنادي Streamlit لو
مفيش CSS، وستايل شاشة الدخول بقى جوه البلوك الجلوبال لنفس السبب.
"""

from __future__ import annotations

from . import brand, classic, glass, mobile, sidebar, tokens
from .flag import CLASSIC, GLASS


def _template(css, dir_, align, rowdir):
    return (
        css.replace("__DIR__", dir_)
        .replace("__ALIGN__", align)
        .replace("__ROWDIR__", rowdir)
    )


def _emit(st, css):
    """بتحقن بلوك ستايل، وبتسكت خالص لو مفيش حاجة تتحقن."""
    if not css or not css.strip():
        return
    st.markdown("<style>\n%s\n</style>" % css, unsafe_allow_html=True)


def inject_base(st, variant=CLASSIC, lang="ar"):
    """الستايل الجلوبال — بيتحقن قبل بوابة الدخول، فلازم يبقى مستقل عن
    اللغة (لسه مش عارفين اختيار المستخدم في المرحلة دي).

    ستايل شاشة الدخول داخل معاه عن قصد: هو متربط بمفتاح فورم الدخول
    فمبيأثرش على أي حاجة تانية، وكده شاشة الدخول ماخدتش حاوية زيادة.
    """
    # التوكنز أول حاجة: من بعد ما ألوان البراند الرسمية بقت في ‎tokens.py‎،
    # الشكل الكلاسيكي بقى بيستهلك ‎var(--cf-*)‎ زي شكل الزجاج بالظبط. فلازم
    # بلوك الـ ‎:root‎ يتحقن في المسارين، مش في مسار الزجاج بس زي الأول.
    # ستايل الشريط الثابت هنا مش في ‎inject_main‎ بس: الشريط مبني بجافاسكريبت
    # جوه ‎body‎ بره React، فبيفضل موجود بعد تسجيل الخروج. من غير ستايله كانت
    # صورة اللوجو بتترسم بمقاسها الأصلي (2400×1000) وتغطي شاشة الدخول كلها
    # (بلاغ المالك 2026-09-23). وعلى شاشة الدخول نفسها مالوش لازمة خالص.
    parts = [tokens.css_vars("dark"), brand.LOGO_CSS, classic.BASE_CSS, classic.LOGIN_CSS,
             _sticky_bar_css(), "body:has(.cf-login) #cf-sticky-bar { display: none !important; }"]
    if variant == GLASS:
        parts.append(glass.base_css())
        parts.append(glass.login_css())
    # موبايل هنا كمان: شاشة الدخول أول حاجة اليوزر بيلمسها على الموبايل،
    # فلازم تاخد نفس قواعد الـ touch target زي باقي الشاشات (inject_main).
    parts.append(mobile.mobile_css())
    _emit(st, "\n".join(parts))
    _document_attrs(st, lang)


# لون شريط العنوان في الموبايل — نفس backgroundColor في config.toml
# (CF Midnight، صفحة الوضع الغامق في دليل البراند)
THEME_COLOR = tokens.BRAND["midnight"]


def _document_attrs(st, lang):
    """بيظبط ‎lang‎ على ‎<html>‎ وبيحط ‎theme-color‎ + أيقونة الشاشة الرئيسية.

    Streamlit بيسيب ‎<html lang="en">‎ ثابت، فقارئ الشاشة كان بيقرا العربي
    بصوت إنجليزي، والمتصفح بيختار قواعد التقطيع والخطوط على إنه إنجليزي.

    ‎dir‎ متحطش على ‎<html>‎ عن قصد: التخطيط كله مبني على إن الجذر LTR
    واتجاه العربي بيتطبق على العناصر نفسها (‎[dir=rtl]‎ في ‎classic.py‎).
    قلب الجذر كان هيعكس الشريط الجانبي وكل صف flex مرتين.

    ‎st.html‎ بالسكريبت بيشتغل في الصفحة نفسها من غير iframe. القيمة بتتحط في
    كل rerun، فلما اللغة تتغير ‎lang‎ بيتبعها.

    ‎apple-touch-icon‎ و‎manifest‎: ‎page_icon=‎ في ‎set_page_config‎ (app.py)
    بيظبط فافيكون التاب بس. من غيرهم، "إضافة للشاشة الرئيسية" على الموبايل
    بترجع لسلوك المتصفح الافتراضي: لقطة شاشة للصفحة مقصوصة وملزّقة — مش
    اللوجو. المسار نسبي (‎app/static/…‎) زي خطوط ‎config.toml‎ بالظبط؛ نفس
    النمط ده شغال فعلاً في الإنتاج تحت ‎/v1/‎ لأن Streamlit بيحوّل ‎/v1‎
    (من غير الشرطة) لـ ‎/v1/‎ دايمًا (307)، فالمستند بيتحمّل من مسار فيه
    الشرطة على طول والمسار النسبي بيتحل صح — العلامة موجودة في ‎data:‎ URI
    بس عشان محتاجينها جوه HTML متحقن، مش جوه ‎<link>‎ في الهيد.
    """
    lang = "en" if lang == "en" else "ar"
    st.html(
        "<script data-cf-doc>(function(){"
        f"var d=document.documentElement;if(d.lang!=='{lang}')d.lang='{lang}';"
        "var m=document.querySelector('meta[name=theme-color]');"
        "if(!m){m=document.createElement('meta');m.name='theme-color';"
        "document.head.appendChild(m);}"
        f"m.content='{THEME_COLOR}';"
        "if(!document.querySelector('link[rel=apple-touch-icon]')){"
        "var a=document.createElement('link');a.rel='apple-touch-icon';"
        "a.href='app/static/brand/apple-touch-icon.png';"
        "document.head.appendChild(a);}"
        "if(!document.querySelector('link[rel=manifest]')){"
        "var mf=document.createElement('link');mf.rel='manifest';"
        "mf.href='app/static/manifest.webmanifest';"
        "document.head.appendChild(mf);}"
        + _NO_AUTOCAPS_JS +
        "})();</script>",
        unsafe_allow_javascript=True,
    )


# كيبورد الموبايل بيكبّر أول حرف في أي خانة نص لوحده (وساعات بيصحّح الكلمة)،
# ومنها خانة الدخول - وعلى بعض الكيبوردات خانة كلمة السر كمان، فـ "Password1"
# مش "password1" والدخول بيفشل من غير ما اليوزر ياخد باله (بلاغ المالك
# 2026-09-24). اسم المستخدم أصلًا مش حساس للحروف (auth.normalize_username)،
# بس كلمة السر لازم تفضل حساسة - فالحل إن الكيبورد مايغيّرش حاجة من الأول.
# Streamlit مابيطلعش الخصائص دي، وبيبني الخانات من جديد مع كل rerun، فـ
# MutationObserver بيحطها على أي خانة تظهر. من غير أي حرف "أصغر من" في الكود:
# st.html بيمسح السكريبت كله بصمت لو لقى حاجة شبه تاج HTML.
_NO_AUTOCAPS_JS = (
    "if(!window.__cfNoCaps){window.__cfNoCaps=1;"
    "var fix=function(){"
    "document.querySelectorAll('div[class*=st-key-_login_username] input,input[type=password]')"
    ".forEach(function(i){if(i.dataset.cfNoCaps)return;i.dataset.cfNoCaps='1';"
    "i.setAttribute('autocapitalize','none');i.setAttribute('autocorrect','off');"
    "i.setAttribute('spellcheck','false');"
    # Streamlit بيحط autocomplete=new-password على كل خانة سر، فمدير كلمات
    # السر كان بيعرض "كلمة سر جديدة" بدل ما يملى المحفوظة في شاشة الدخول
    "if(i.type==='password'){if(i.closest('div[class*=st-key-_login_password]'))"
    "i.setAttribute('autocomplete','current-password');}"
    "else{i.setAttribute('autocomplete','username');}});};"
    "fix();new MutationObserver(fix).observe(document.body,{childList:true,subtree:true});}"
)


def inject_login(st, variant=CLASSIC):
    """موجودة عشان ‎app.py‎ بينادي عليها على شاشة الدخول.

    ستايل الدخول بقى بيتحقن مع البلوك الجلوبال في ‎inject_base‎، فالدالة
    دي مش بتحقن حاجة — ومهم إنها متناديش Streamlit خالص، لأن أي عنصر زيادة
    بياخد فراغ رأسي في الشبكة وبيزح الفورم لتحت.
    """
    return None


def _header_logo_css():
    """اللوجو (الماستر، سطح غامق) في هيدر Streamlit الثابت — فاضي خالص
    من غير ده، خصوصًا على الموبايل لما الشريط الجانبي يبقى مقفول ومفيش
    أي براند ظاهر فوق المحتوى الرئيسي. ‎background-image‎ مش ‎<img>‎ لأن
    الهيدر عنصر Streamlit جاهز مش حاوية بنتحكم في محتواها من بايثون."""
    height = 30
    width = round(height * brand._MASTER_W / brand._MASTER_H)
    src = brand.data_uri("cimafast-lockup-dark-transparent.png")
    # الكل ‎!important‎: زجاج الهيدر (glass.py، درجة المادة) وأرضيته
    # (‎_ground_rules‎) بيحطوا ‎background: … !important‎ (اختصار)، وده بيمسح
    # ‎background-image‎ ضمنيًا لو من غير ‎!important‎ برضه. والسيليكتور
    # مكرّر (‎[data-testid="stHeader"]‎ مرتين) عشان الخاصية تبقى أعلى من
    # نفس سيليكتور الأرضية، مش متساوية معاه — Streamlit بيعيد حقن نفس
    # ستايل الأرضية أكتر من مرة عبر الـ reruns، فترتيب الظهور في الـ DOM
    # مش مضمون، والاعتماد عليه وحده مش كفاية.
    sel = 'header[data-testid="stHeader"][data-testid="stHeader"]'
    return f"""
    {sel} {{
        background-image: url("{src}") !important;
        background-repeat: no-repeat !important;
        /* يمين الهيدر (RTL) بس بعيد عن زرار فتح/قفل الشريط الجانبي، اللي
           واقف في أقصى الحافة. */
        background-position: right 64px center !important;
        background-size: {width}px {height}px !important;
    }}
    @media (max-width: 640px) {{
        {sel} {{ background-position: right 56px center !important; }}
    }}
    """


def _sticky_bar_css():
    """شريط ثابت (خارج شجرة React بتاعة Streamlit — جوه ‎body‎ مباشرة، مبني
    بجافاسكريبت في ‎_sticky_bar_js‎) بيظهر بس لما المستخدم يسكرول: هيدر
    Streamlit شفاف أصلًا (‎_header_logo_css‎)، فمحتوى الصفحة بيبين من وراه
    وهو بيسكرول تحته — ده اللي كان شكله "اللوجو بيتراكب" في شكوى المستخدم.
    الشريط ده معتم ومخفي فوق حافة الشاشة (‎translateY(-100%)‎) لغاية ما
    يظهر، فمش بيغطي حاجة وهو واقف في أول الصفحة."""
    return """
    #cf-sticky-bar {
        position: fixed; top: 0; left: 0; right: 0; height: 56px;
        z-index: 1000001; /* فوق هيدر Streamlit (999990) */
        display: flex; align-items: center; justify-content: space-between;
        padding: 0 16px;
        background: var(--cf-midnight, #0F1B45);
        border-bottom: 1px solid rgba(255,255,255,.12);
        box-shadow: 0 4px 16px rgba(0,0,0,.35);
        transform: translateY(-100%);
        transition: transform .25s ease;
    }
    #cf-sticky-bar.cf-sticky-bar--visible { transform: translateY(0); }
    #cf-sticky-bar .cf-sticky-bar__logo { height: 28px; width: auto; display: block; }
    #cf-sticky-bar .cf-sticky-bar__burger {
        appearance: none; border: none; background: transparent;
        color: var(--cf-yellow, #FECA05); font-size: 22px; line-height: 1;
        width: 40px; height: 40px; border-radius: 10px; cursor: pointer;
    }
    #cf-sticky-bar .cf-sticky-bar__burger:hover,
    #cf-sticky-bar .cf-sticky-bar__burger:focus-visible {
        background: rgba(254,202,5,.14); outline: none;
    }
    """


def _sticky_bar_js(st, logo_src):
    """بتبني الشريط الثابت مرة واحدة بس (‎idempotent‎ — بتتفحص وجوده الأول)
    وتربط سكرول الحاوية الحقيقية اللي بتسكرول في Streamlit (مش ‎window‎ —
    شرح كامل في ‎glass.py:_ground_rules‎). زرار البرغر بيدوس على زرار فتح
    الشريط الجانبي الأصلي بتاع Streamlit (‎stExpandSidebarButton‎) بدل ما
    يبني قايمة تانية مكررة — الشريط الجانبي أصلًا فيه كل حاجة مطلوبة
    (الحساب، المشاريع، اللغة، تسجيل الخروج).

    العناصر متبنية بـ ‎createElement‎/‎setAttribute‎، مش ‎innerHTML = '<img …>'‎:
    ‎st.html‎ بيمسح محتوى الـ ‎<script>‎ كله بصمت (من غير استثناء ولا رسالة)
    لو فيه أي نص شبه تاج HTML (‎‎<img‎‎، ‎‎<button‎‎) جواه، حتى لو النص ده
    جوه string جافاسكريبت مش HTML حقيقي — اتأكدت منها بتجربة معزولة قبل
    الحل ده.

    ‎logo_src‎ جاي جاهز من ‎brand.data_uri("cimafast-lockup-dark-transparent.png")‎
    (نسخة اللوجو الصح للسطح الغامق — الشخصية صفرا، مش كحلي) بدل ما نقرأه
    وقت التشغيل من ‎.cf-logo-master‎ في الشريط الجانبي: ده كان بيدّي نسخة
    غلط (الكحلي، بتاعة الحقل الأصفر) على خلفية غامقة ⇐ تباين ضعيف، وكمان
    الشريط الجانبي أصلًا مالوش نسخة غامقة في الـ DOM يتقري منها. ‎data:‎
    URI بـ base64 معندوش حرف ‎<‎ خالص (مش من أبجدية base64) فمستحيل يشبه
    تاج HTML يوقع في نفس المصيدة اللي مانعة الـ ‎innerHTML‎ فوق.
    مفيش سباق هنا فمحتاجناش ‎setInterval‎ يعيد المحاولة زي قبل — الـ ‎src‎
    مضمون يتحط صح من أول مرة.
    """
    js = """
    (function(){
        function ensureBar(){
            var bar = document.getElementById('cf-sticky-bar');
            if (bar) return bar;
            bar = document.createElement('div');
            bar.id = 'cf-sticky-bar';
            var img = document.createElement('img');
            img.className = 'cf-sticky-bar__logo';
            img.alt = 'CimaFast';
            img.src = '%(logo_src)s';
            // المقاس inline كمان: لو الستايل اتأخر أو اتشال، الصورة متتفردش بمقاسها الأصلي
            img.style.height = '28px';
            img.style.width = 'auto';
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'cf-sticky-bar__burger';
            btn.setAttribute('aria-label', 'القائمة');
            btn.textContent = String.fromCharCode(9776);
            btn.addEventListener('click', function(){
                var t = document.querySelector('[data-testid="stExpandSidebarButton"]');
                if (t) t.click();
            });
            bar.appendChild(img);
            bar.appendChild(btn);
            document.body.appendChild(bar);
            return bar;
        }
        function bindScroll(){
            var container = document.querySelector('[data-testid="stMain"]');
            if (!container || container.dataset.cfScrollBound) return;
            container.dataset.cfScrollBound = '1';
            var bar = ensureBar();
            container.addEventListener('scroll', function(){
                bar.classList.toggle('cf-sticky-bar--visible', container.scrollTop > 40);
            }, {passive: true});
        }
        ensureBar();
        bindScroll();
        var tries = 0;
        var iv = setInterval(function(){
            tries++;
            bindScroll();
            var c = document.querySelector('[data-testid="stMain"]');
            if ((c && c.dataset.cfScrollBound) || tries > 20) clearInterval(iv);
        }, 250);
    })();
    """ % {"logo_src": logo_src}
    st.html("<script>%s</script>" % js, unsafe_allow_javascript=True)


def inject_main(st, variant=CLASSIC, dir_="rtl", align="right", rowdir="row-reverse"):
    """الستايل الكبير بعد الدخول — بياخد اتجاه اللغة الحالي.

    كل زاوية جراديينت وحرف مضيء وظل داخلي ليهم حالة معكوسة في RTL،
    فالقوالب ‎__DIR__‎ / ‎__ALIGN__‎ / ‎__ROWDIR__‎ بتتبدل في النسختين
    بنفس الطريقة.
    """
    # ‎collapse_slide_css‎ بترجع فاضي في الإنجليزي: اتجاه انزلاق الشريط
    # الجانبي وهو بيتفتح/بيتقفل بيتصلّح في العربي بس (الشرح في ‎sidebar.py‎).
    parts = [
        classic.MAIN_CSS,
        sidebar.SIDEBAR_CSS,
        sidebar.collapse_slide_css(dir_),
        _header_logo_css(),
    ]
    if variant == GLASS:
        parts.append(glass.main_css(dir_))
    # موبايل: طبقة CSS ثابتة جوه @media، بتتطبق لوحدها لما عرض الشاشة يضيق —
    # على أي متغيّر (classic أو glass) ومن غير أي فلاج أو منطق بايثون إضافي.
    parts.append(mobile.mobile_css())
    _emit(st, _template("\n".join(parts), dir_, align, rowdir))
    if variant == GLASS:
        glass.inject_runtime(st)
    # الشريط الثابت خلفيته غامقة (‎_sticky_bar_css‎ فوق) ⇒ لازم نسخة اللوجو
    # الصفرا (الدليل: سطح غامق → mark-dark)، مش الكحلي اللي في الشريط
    # الجانبي (سطح أصفر → mark-light).
    _sticky_bar_js(st, brand.data_uri("cimafast-lockup-dark-transparent.png"))
