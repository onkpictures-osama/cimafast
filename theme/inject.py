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

from . import classic, glass
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


def inject_base(st, variant=CLASSIC):
    """الستايل الجلوبال — بيتحقن قبل بوابة الدخول، فلازم يبقى مستقل عن
    اللغة (لسه مش عارفين اختيار المستخدم في المرحلة دي).

    ستايل شاشة الدخول داخل معاه عن قصد: هو متربط بمفتاح فورم الدخول
    فمبيأثرش على أي حاجة تانية، وكده شاشة الدخول ماخدتش حاوية زيادة.
    """
    parts = [classic.BASE_CSS, classic.LOGIN_CSS]
    if variant == GLASS:
        parts.append(glass.base_css())
        parts.append(glass.login_css())
    _emit(st, "\n".join(parts))


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
    _emit(st, _template("\n".join(parts), dir_, align, rowdir))
    if variant == GLASS:
        glass.inject_runtime(st)
