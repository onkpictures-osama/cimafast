"""اللوجو ومكوّناته — "الرافع" (The Lifter) زي ما الدليل الرسمي ظابطه.

الأصول الأصلية (SVG + PNG + أيقونة البرنامج) في ‎static/brand/‎، منقولة زي
ما هي من مجلد البراند. ممنوع نعيد تلوينها أو نمطّها أو نقصّها — الدليل
(ص 06 · Logo rules) صريح في ده، فالدوال هنا بتغيّر **المقاس** بس وبتختار
النسخة الصح حسب السطح.

النسخة الصح:
  سطح غامق (Midnight / Navy Surface / صورة)  →  الشخصية صفرا  →  mark-dark
  سطح فاتح أو الحقل الأصفر                    →  الشخصية كحلي  →  mark-light

استثناء موثّق (2026-09-23): الشريط الجانبي (‎st.sidebar‎ في app.py، ستايله
في ‎theme/sidebar.py‎) بقى سطح غامق (Midnight) مش الحقل الأصفر — موافقة
صريحة من صاحب المنتج على موك أب مرجعي شاركه (خلفية كحلي غامقة، مش الحقل
الأصفر التقليدي). ده استثناء **للشريط الجانبي بس**، مش تراجع عن القاعدة
فوق ولا سبب يتغيّر بيه أي سطح تاني في البرنامج — أي محاولة "تصليح" الشريط
الجانبي يرجع أصفر تاني في مرة جاية غلط، القرار ده مقصود. الشريط الجانبي
بيستخدم ‎lockup(surface="dark")‎ (النسخة المركّبة تحت، مش ‎lockup_master()‎
الماستر الجامد) عشان يطلع "CimaFast STUDIO" زي كل سطح تاني في التطبيق، مش
الماستر الجامد. ‎surface="dark"‎ بيسحب ‎MARK_DARK‎
(‎cimafast-mark-dark-transparent.svg‎ — أصل موجود أصلًا، الشخصية صفرا)، نفس
لغة العلامة اللي الشريط الثابت (sticky bar) شغال بيها من ماستر مكافئ
(‎cimafast-lockup-dark-transparent.png‎) — مفيش أصل جديد اتعمل في الحالتين.
القرار مسجّل كمان في ‎PRODUCT-PLAN.md‎ (بند "قرارات المالك").

ليه ‎data:‎ URI مش ‎<img src="app/static/…">‎: البريفيو شغال تحت
‎/v1/‎ بـ ‎baseUrlPath‎، والرابط النسبي بيتكسر لو المستخدم فتح ‎/v1‎ من غير
الشرطة الأخيرة. الملف 1 كيلوبايت، فالتضمين أرخص من طلب شبكة أصلًا.

ليه الـ lockup مركّب (علامة + نص حي) مش صورة واحدة: الـ ‎<text>‎ جوه
‎<img>‎ مبياخدش خطوط الصفحة، فـ Inter كانت هتقع على Arial. النص الحي بيفضل
حاد في أي مقاس.

كلمة MEDIA اتشالت من البرنامج كله (قرار المالك 2026-09-23: "اسم برنامجنا
سيما فاست ستوديو وليس ميديا"). ماسترات الـ lockup (SVG + PNG) مكتوب فيها
STUDIO دلوقتي؛ الـ PNG اترسم تاني من الـ SVG بخط Inter بتاع ‎static/fonts‎
بنفس الهندسة بالظبط. ممنوع ترجع MEDIA في أي سطح.
"""

from __future__ import annotations

import base64
import functools
import os

ASSET_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "brand"
)

MARK_DARK = "cimafast-mark-dark-transparent.svg"    # شخصية صفرا — للأسطح الغامقة
MARK_LIGHT = "cimafast-mark-light-transparent.svg"  # شخصية كحلي — للفاتح والأصفر
APP_ICON = "app-icon-dark.png"                      # أيقونة البرنامج / الفافيكون

# اسم البراند: كلمة واحدة، C و F كابيتال. ممنوع "Cima Fast" أو "CIMAFAST".
WORDMARK = "CimaFast"
# نسخة الاستوديو: "STUDIO" - اسم البرنامج (الدليل ص 01 و04، وقرار المالك 2026-09-23)
DESCRIPTOR = "STUDIO"
# الاسم العربي بيقف **جنب** الـ lockup، مش جواه، وبخط Cairo (الدليل ص 04)
ARABIC_NAME = "سيما فاست ستوديو"


@functools.lru_cache(maxsize=8)
def data_uri(filename):
    """بترجّع الأصل كـ ‎data:‎ URI. الكاش لأن نفس الملف بيتطلب كل rerun."""
    path = os.path.join(ASSET_DIR, filename)
    with open(path, "rb") as fh:
        raw = fh.read()
    mime = "image/svg+xml" if filename.endswith(".svg") else "image/png"
    return "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode("ascii"))


def asset_path(filename):
    """المسار على الديسك — لـ ‎st.set_page_config(page_icon=…)‎ مثلًا."""
    return os.path.join(ASSET_DIR, filename)


def mark(surface="dark", px=40, extra_class=""):
    """العلامة لوحدها: أيقونة، أفاتار، علامة مائية. الرأس نقطة صلبة هنا."""
    src = data_uri(MARK_DARK if surface == "dark" else MARK_LIGHT)
    cls = ("cf-logo__mark " + extra_class).strip()
    return (
        '<img class="%s" src="%s" alt="" aria-hidden="true" '
        'style="height:%dpx;width:%dpx">' % (cls, src, px, px)
    )


# --------------------------------------------------------------------------
# هندسة الـ lockup — أرقام الدليل (ص 04) مترجمة لمربّع الماستر 1920×1920.
#
# الشخصية مش مالية المربّع: الحبر بيمتد رأسيًا من 179 لـ 1738 (أعلى إطار
# الشاشة ناقص نص الحد، لحد قاع الرجل زايد نص الحد) وأفقيًا من 494 لـ 1426.
# يعني 81.2% من ارتفاع المربّع و48.5% من عرضه — ولو حسبنا على المربّع بدل
# الحبر، العلامة بتطلع أصغر من نسبة الدليل بحوالي 20%، وده اللي كان باين
# في أول لقطة.
# --------------------------------------------------------------------------

_INK_H = (1738 - 179) / 1920      # 0.812 — ارتفاع الحبر جوه المربّع
_INK_W = (1426 - 494) / 1920      # 0.485 — عرض الحبر جوه المربّع
_PAD_R = (1920 - 1426) / 1920     # 0.257 — الفراغ على يمين الحبر جوه المربّع
_CAP = 0.727                      # ارتفاع الكابيتال في Inter بالنسبة للـ em
_MARK_TO_CAP = 2.6                # الدليل: ارتفاع العلامة = 2.6 × كابيتال الكلمة
_GAP_TO_MARK_W = 0.6              # الدليل: المسافة = 0.6 × عرض العلامة


def lockup(surface="dark", px=44, arabic=False, tm=True):
    """الـ lockup الأفقي: علامة على الشمال، ‎CimaFast‎ فوق ‎STUDIO‎.

    ‎px‎ = ارتفاع مربّع العلامة (مش الحبر). كل الباقي محسوب منه بنسب الدليل
    ص 04: ارتفاع العلامة = 2.6 × كابيتال الكلمة، كابيتال ‎STUDIO‎ = نص
    كابيتال الكلمة بتتبّع 10%، والمسافة بينهم = 0.6 × عرض العلامة.
    """
    word_px = round(px * _INK_H / (_MARK_TO_CAP * _CAP))
    desc_px = max(8, round(word_px * 0.5))
    # المسافة المطلوبة ناقص الفراغ اللي جوه المربّع أصلًا — من غير الطرح ده
    # العلامة بتبان بعيدة عن الكلمة بضعف المفروض.
    gap_px = max(0, round(px * (_GAP_TO_MARK_W * _INK_W - _PAD_R)))
    tm_html = '<sup class="cf-logo__tm">TM</sup>' if tm else ""
    arabic_html = (
        '<span class="cf-logo__ar">%s</span>' % ARABIC_NAME if arabic else ""
    )
    return (
        '<span class="cf-logo cf-logo--%s" dir="ltr" style="gap:%dpx">%s'
        '<span class="cf-logo__type">'
        '<span class="cf-logo__word" style="font-size:%dpx">%s%s</span>'
        '<span class="cf-logo__desc" style="font-size:%dpx">%s</span>'
        "</span>%s</span>"
    ) % (
        surface, gap_px, mark(surface, px), word_px, WORDMARK, tm_html,
        desc_px, DESCRIPTOR, arabic_html,
    )


_MASTER_W, _MASTER_H = 2400, 1000  # أبعاد ماستر الـ lockup الأصلي
MASTER_ASPECT = _MASTER_W / _MASTER_H  # النسبة مقفولة — ممنوع مط أو سحق
_LOCKUP_MASTER = "cimafast-lockup-%s-transparent.png"


def lockup_master_path(surface="light"):
    """مسار ماستر الـ lockup على الديسك.

    للمستهلكين اللي بياخدوا ملف مباشرةً بدل ‎data:‎ URI — التصدير
    (‎export.py‎) بيدّي المسار لـ openpyxl و python-docx و reportlab زي ما
    هو، فمحتاجش التضمين اللي المتصفح محتاجه.
    """
    return asset_path(_LOCKUP_MASTER % surface)


def lockup_master(surface="light", height=44, arabic=False):
    """اللوجو الرسمي الجامد (PNG، "CimaFast STUDIO") — مش النسخة المركّبة
    (mark + نص حي). للاستخدام لما المطلوب صورة ثابتة الشكل بالظبط.

    PNG مش SVG عمدًا: النص جوه ماستر الـ lockup مرسوم كـ ‎<text>‎، ولو
    اتحط كـ ‎<img src="data:image/svg+xml...">‎ مش هياخد خطوط الصفحة
    (Inter) — الـ SVG جوه ‎<img>‎ معزول عن CSS بتاع الصفحة. الـ PNG بكسلات
    جاهزة فمفيش اعتماد على خط خالص.
    """
    src = data_uri(_LOCKUP_MASTER % surface)
    width = round(height * MASTER_ASPECT)
    img = (
        '<img class="cf-logo-master" src="%s" alt="CimaFast" '
        'style="height:%dpx;width:%dpx;display:block;object-fit:contain">'
    ) % (src, height, width)
    if not arabic:
        return img
    arabic_html = '<span class="cf-logo__ar">%s</span>' % ARABIC_NAME
    return '<span class="cf-logo cf-logo--%s" dir="ltr">%s%s</span>' % (surface, img, arabic_html)


# --------------------------------------------------------------------------
# ستايل المكوّن — بيتحقن مع باقي الستايل الجلوبال في ‎inject.inject_base‎.
# المسافة الآمنة حوالين اللوجو = قطر الراس (8.75% من المربّع) على الأربع
# نواحي، ومفيش حاجة بتدخل فيها.
# --------------------------------------------------------------------------

LOGO_CSS = r'''
    .cf-logo {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        /* الاتجاه ثابت ltr: الـ lockup شكل مرسوم مش جملة، فمبيتقلبش مع
           العربي — العلامة على الشمال والكلمة على اليمين دايمًا. */
        direction: ltr;
        line-height: 1;
        /* المسافة الآمنة: قطر الراس ≈ 8.75% من ارتفاع المربّع */
        padding: 0.09em 0;
        text-decoration: none;
    }
    .cf-logo__mark {
        display: block;
        flex: 0 0 auto;
        /* ممنوع مطّ أو سحق: النسبة مقفولة 1:1 زي الماستر */
        object-fit: contain;
    }
    .cf-logo__type {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 0.18em;
        min-width: 0;
    }
    .cf-logo__word {
        font-family: "Inter", sans-serif;
        font-weight: 800;
        letter-spacing: -0.02em;
        line-height: 1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .cf-logo__tm {
        font-size: 32%;      /* الدليل ص 04: ™ = 32% من الكابيتال، متعلّق فوق */
        font-weight: 600;
        vertical-align: super;
        letter-spacing: 0;
        margin-inline-start: 0.12em;
    }
    .cf-logo__desc {
        font-family: "Inter", sans-serif;
        font-weight: 500;
        letter-spacing: 0.1em;   /* تتبّع 10% زي STUDIO في الماستر */
        line-height: 1;
        white-space: nowrap;
    }
    /* الاسم العربي بيقف جنب الـ lockup بخط Cairo — مش جواه أبدًا.
       خصائص فيزيائية (left) مش منطقية (inline-start) عن قصد: العنصر ده
       جوّاه ‎rtl‎، فـ ‎inline-start‎ بتترجم يمين وبتحط الفاصل في الناحية
       الغلط — بره الـ lockup بدل ما يكون بينه وبين الاسم. */
    .cf-logo__ar {
        font-family: "Cairo", sans-serif;
        font-weight: 700;
        margin-left: 0.7em;
        padding-left: 0.7em;
        border-left: 1px solid currentColor;
        opacity: 0.55;
        direction: rtl;
        font-size: 0.85em;
    }
    /* الألوان بتتبع السطح: صفرا على الغامق، كحلي على الفاتح/الأصفر.
       الأحمر (مثلث التشغيل) جوه الـ SVG ومبيتغيرش في أي نسخة. */
    .cf-logo--dark .cf-logo__word { color: var(--cf-yellow); }
    .cf-logo--dark .cf-logo__desc { color: var(--cf-white); }
    .cf-logo--light .cf-logo__word,
    .cf-logo--light .cf-logo__desc { color: var(--cf-ink); }
'''
