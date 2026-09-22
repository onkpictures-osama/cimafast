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

from . import brand, classic, glass, mobile, tokens
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
    parts = [tokens.css_vars("dark"), brand.LOGO_CSS, classic.BASE_CSS, classic.LOGIN_CSS]
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
        "})();</script>",
        unsafe_allow_javascript=True,
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


def inject_main(st, variant=CLASSIC, dir_="rtl", align="right", rowdir="row-reverse"):
    """الستايل الكبير بعد الدخول — بياخد اتجاه اللغة الحالي.

    كل زاوية جراديينت وحرف مضيء وظل داخلي ليهم حالة معكوسة في RTL،
    فالقوالب ‎__DIR__‎ / ‎__ALIGN__‎ / ‎__ROWDIR__‎ بتتبدل في النسختين
    بنفس الطريقة.
    """
    parts = [classic.MAIN_CSS, _header_logo_css()]
    if variant == GLASS:
        parts.append(glass.main_css(dir_))
    # موبايل: طبقة CSS ثابتة جوه @media، بتتطبق لوحدها لما عرض الشاشة يضيق —
    # على أي متغيّر (classic أو glass) ومن غير أي فلاج أو منطق بايثون إضافي.
    parts.append(mobile.mobile_css())
    _emit(st, _template("\n".join(parts), dir_, align, rowdir))
    if variant == GLASS:
        glass.inject_runtime(st)
