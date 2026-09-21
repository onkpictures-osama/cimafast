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

from . import classic, glass, mobile
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
    parts = [classic.BASE_CSS, classic.LOGIN_CSS]
    if variant == GLASS:
        parts.append(glass.base_css())
        parts.append(glass.login_css())
    # موبايل هنا كمان: شاشة الدخول أول حاجة اليوزر بيلمسها على الموبايل،
    # فلازم تاخد نفس قواعد الـ touch target زي باقي الشاشات (inject_main).
    parts.append(mobile.mobile_css())
    _emit(st, "\n".join(parts))
    _document_attrs(st, lang)


# لون شريط العنوان في الموبايل — نفس backgroundColor في config.toml
THEME_COLOR = "#0B1220"


def _document_attrs(st, lang):
    """بيظبط ‎lang‎ على ‎<html>‎ وبيحط ‎theme-color‎.

    Streamlit بيسيب ‎<html lang="en">‎ ثابت، فقارئ الشاشة كان بيقرا العربي
    بصوت إنجليزي، والمتصفح بيختار قواعد التقطيع والخطوط على إنه إنجليزي.

    ‎dir‎ متحطش على ‎<html>‎ عن قصد: التخطيط كله مبني على إن الجذر LTR
    واتجاه العربي بيتطبق على العناصر نفسها (‎[dir=rtl]‎ في ‎classic.py‎).
    قلب الجذر كان هيعكس الشريط الجانبي وكل صف flex مرتين.

    ‎st.html‎ بالسكريبت بيشتغل في الصفحة نفسها من غير iframe. القيمة بتتحط في
    كل rerun، فلما اللغة تتغير ‎lang‎ بيتبعها.
    """
    lang = "en" if lang == "en" else "ar"
    st.html(
        "<script data-cf-doc>(function(){"
        f"var d=document.documentElement;if(d.lang!=='{lang}')d.lang='{lang}';"
        "var m=document.querySelector('meta[name=theme-color]');"
        "if(!m){m=document.createElement('meta');m.name='theme-color';"
        "document.head.appendChild(m);}"
        f"m.content='{THEME_COLOR}';"
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


def inject_main(st, variant=CLASSIC, dir_="rtl", align="right", rowdir="row-reverse"):
    """الستايل الكبير بعد الدخول — بياخد اتجاه اللغة الحالي.

    كل زاوية جراديينت وحرف مضيء وظل داخلي ليهم حالة معكوسة في RTL،
    فالقوالب ‎__DIR__‎ / ‎__ALIGN__‎ / ‎__ROWDIR__‎ بتتبدل في النسختين
    بنفس الطريقة.
    """
    parts = [classic.MAIN_CSS]
    if variant == GLASS:
        parts.append(glass.main_css(dir_))
    # موبايل: طبقة CSS ثابتة جوه @media، بتتطبق لوحدها لما عرض الشاشة يضيق —
    # على أي متغيّر (classic أو glass) ومن غير أي فلاج أو منطق بايثون إضافي.
    parts.append(mobile.mobile_css())
    _emit(st, _template("\n".join(parts), dir_, align, rowdir))
    if variant == GLASS:
        glass.inject_runtime(st)
