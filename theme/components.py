"""مساعدات بايثون رفيعة لمادة الزجاج.

مقصودة تفضل رفيعة: كل الشكل في الـ CSS، والدوال دي بتبني HTML بكلاسات
صح بس. الفايدة إن درجة المادة بتتحدد صريحة في مكان الاستخدام، فمفيش حد
بيستخدم درجة غلط بالسهو.

الدرجات: ‎regular‎ (الافتراضي) · ‎clear‎ (فوق الصور بس) · ‎opaque‎
(النصوص الكثيفة — جداول، عربي طويل). في الشكل الكلاسيكي الدوال دي بترجّع
نفس الـ HTML بس الـ CSS بتاع الزجاج مش محقون، فبتظهر عادي من غير مادة.
"""

from __future__ import annotations

TIERS = ("regular", "clear", "opaque")
RADII = ("lg", "md", "sm")


def material_class(tier="regular", radius="lg", extra=""):
    if tier not in TIERS:
        raise ValueError(f"درجة مادة مش معروفة: {tier}")
    if radius not in RADII:
        raise ValueError(f"نصف قطر مش معروف: {radius}")
    parts = ["cf-glass", f"cf-glass--{tier}", f"cf-r-{radius}"]
    if extra:
        parts.append(extra)
    return " ".join(parts)


def glass_panel(body, tier="regular", radius="lg", dir_=None, extra=""):
    """لوح زجاج بسيط حوالين HTML جاهز."""
    attrs = f' class="{material_class(tier, radius, extra)}"'
    if dir_:
        attrs += f' dir="{dir_}"'
    return f"<div{attrs}>{body}</div>"


def glass_card(title, body, tier="regular", radius="lg", dir_=None, extra=""):
    """كارت زجاج بعنوان — العنوان بياخد لون اللكنة، والجسم لون الحروف العادي.

    ‎title‎ لازم يكون نص حقيقي بيوصف المحتوى؛ مفيش عناوين زينة هنا.
    """
    inner = ""
    if title:
        inner += f'<div class="cf-glass-title">{title}</div>'
    inner += f'<div class="cf-glass-body">{body}</div>'
    return glass_panel(inner, tier=tier, radius=radius, dir_=dir_, extra=extra)
