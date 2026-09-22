"""طبقة الشكل بتاعة CimaFast Studio.

الواجهة العامة:

    variant = theme.resolve_variant()            # "classic" أو "glass"
    theme.inject_base(st, variant)               # قبل بوابة الدخول
    theme.inject_login(st, variant)              # شاشة الدخول
    theme.inject_main(st, variant, dir_, align, rowdir)

    theme.glass_panel(...) / theme.glass_card(...)   # مساعدات المادة
    theme.contrast.ratio(fg, bg)                     # تدقيق التباين
    theme.tokens.BRAND / DARK / LIGHT                # ألوان البراند والأدوار
    theme.brand.lockup(...) / theme.brand.mark(...)  # اللوجو

الافتراضي ‎classic‎ دايمًا. مفيش حاجة هنا بتقلب الشكل من نفسها.
"""

from . import brand, classic, contrast, glass, tokens
from .components import glass_card, glass_panel, material_class
from .flag import CLASSIC, GLASS, is_glass, resolve_variant
from .inject import inject_base, inject_login, inject_main

__all__ = [
    "CLASSIC",
    "GLASS",
    "brand",
    "classic",
    "contrast",
    "glass",
    "glass_card",
    "glass_panel",
    "inject_base",
    "inject_login",
    "inject_main",
    "is_glass",
    "material_class",
    "resolve_variant",
    "tokens",
]
