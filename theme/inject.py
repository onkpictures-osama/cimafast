"""حقن الـ CSS — المكان الوحيد اللي بيكتب ستايل في الصفحة.

قبل كده كان في تلات أماكن في ‎app.py‎ بتحقن CSS (سطر 34 جلوبال، سطر 108
شاشة الدخول، وقالب 330 سطر في النص). بقوا تلات دوال هنا، والفرق إن كل
واحدة بتعرف النسخة (classic / glass) وبتزوّد طبقة المادة لو الفلاج شغال.

الترتيب مهم: ‎classic‎ هو الطبقة البنيوية (الاتجاه، RTL، مواضع العناصر)،
و‎glass‎ طبقة مادة فوقها. كده منطق RTL بيفضل في مكان واحد ومش متكرر.
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


def _wrap(css):
    return "<style>\n%s\n</style>" % css


def inject_base(st, variant=CLASSIC):
    """الستايل الجلوبال — بيتحقن قبل بوابة الدخول، فلازم يبقى مستقل عن
    اللغة (لسه مش عارفين اختيار المستخدم في المرحلة دي)."""
    css = classic.BASE_CSS
    if variant == GLASS:
        css += "\n" + glass.base_css()
    st.markdown(_wrap(css), unsafe_allow_html=True)


def inject_login(st, variant=CLASSIC):
    """ستايل شاشة تسجيل الدخول."""
    css = classic.LOGIN_CSS
    if variant == GLASS:
        css += "\n" + glass.login_css()
    st.markdown(_wrap(css), unsafe_allow_html=True)


def inject_main(st, variant=CLASSIC, dir_="rtl", align="right", rowdir="row-reverse"):
    """الستايل الكبير بعد الدخول — بياخد اتجاه اللغة الحالي.

    كل زاوية جراديينت وحرف مضيء وظل داخلي ليهم حالة معكوسة في RTL،
    فالقوالب ‎__DIR__‎ / ‎__ALIGN__‎ / ‎__ROWDIR__‎ بتتبدل في النسختين
    بنفس الطريقة.
    """
    css = classic.MAIN_CSS
    if variant == GLASS:
        css += "\n" + glass.main_css()
    st.markdown(_wrap(_template(css, dir_, align, rowdir)), unsafe_allow_html=True)
    if variant == GLASS:
        glass.inject_runtime(st)
