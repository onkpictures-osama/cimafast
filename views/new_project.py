"""فورم "إنشاء مشروع جديد" (جوه الشريط الجانبي).

طلب المالك 2026-09-24: النوع هو **أول** اختيار، وكل نوع ليه أسئلته. المسلسل
لازم عدد حلقاته قبل أي حاجة تانية، والحلقات من 1 لـ N بتتعمل مع المشروع عشان
رفع السكريبت يبقى "لأنهي حلقة" من أول يوم. الدقة والاتجاه والنسبة بتتحدد
لوحدها حسب النوع وبتفضل مستخبية ورا مفتاح "إعدادات فنية" - Streamlit
مابيسمحش بـ expander جوه expander، والفورم نفسه جوه expander.
"""

import streamlit as st

import accounts
from database import FIELD_HELP
from i18n import t
from ui import go_to

from project_types import PLATFORMS, TYPE_ICONS, TYPES, technical_defaults

RESOLUTIONS = ["720p", "1080p", "2K", "4K"]
ORIENTATIONS = ["أفقي", "رأسي", "مربع"]
RATIOS = ["4:5", "16:9", "9:16", "1:1", "4:3", "21:9"]

AD_DURATIONS = ["15 ث", "30 ث", "45 ث", "60 ث"]


def render(current_user, company_id):
    """بيرجّع True لو المشروع اتعمل (الشاشة بتعمل rerun بعدها).

    المفاتيح كلها فيها عدّاد بيزيد بعد كل إنشاء: مسح session_state لوحده
    مابيفضّيش الخانات (المتصفح بيرجّع يبعت القيمة القديمة)، ومفاتيح جديدة =
    فورم فاضي."""
    n = st.session_state.setdefault("_new_proj_nonce", 0)

    def k(name):
        return f"new_proj_{name}_{n}"
    new_type = st.pills(
        t("نوع المشروع"), TYPES, key=k("type"), default="فيلم",
        format_func=lambda v: f"{TYPE_ICONS[v]} {t(v)}", help=FIELD_HELP["project_type"])
    new_type = new_type or "فيلم"
    new_name = st.text_input(t("اسم المشروع"), placeholder=t("مثال: عروسة البحر"), key=k("name"))

    details = {}
    episode_count = None
    platform = None
    if new_type == "مسلسل":
        episode_count = st.number_input(
            t("عدد الحلقات"), min_value=1, max_value=500, step=1, value=None,
            placeholder=t("مثال: 30"), key=k("episodes"),
            help=t("الحلقات من 1 للعدد ده بتتعمل مع المشروع، وتقدر تزودها بعدين من إعدادات المشروع."))
        minutes = st.number_input(t("مدة الحلقة التقريبية (دقيقة)"), min_value=1, max_value=240,
                                  value=45, step=5, key=k("ep_minutes"))
        details["episode_minutes"] = int(minutes)
    elif new_type == "فيلم":
        minutes = st.number_input(t("المدة التقريبية (دقيقة)"), min_value=1, max_value=400,
                                  value=90, step=5, key=k("film_minutes"))
        details["runtime_minutes"] = int(minutes)
    elif new_type == "إعلان":
        client = st.text_input(t("البراند / العميل"), key=k("client"))
        duration = st.pills(t("مدة الإعلان"), AD_DURATIONS, default="30 ث", key=k("ad_duration"),
                            format_func=t)
        details.update({"client": client.strip() or None, "duration": duration})
    else:
        platform = st.pills(t("المنصة"), PLATFORMS, default="ريلز", key=k("platform"), format_func=t)
        details["platform"] = platform

    res, orient, ratio = technical_defaults(new_type, platform)
    if st.toggle(t("إعدادات فنية (الدقة، الاتجاه، النسبة)"), key=k("tech"),
                 help=t("متظبطة لوحدها حسب نوع المشروع — افتحها بس لو عايز تغيّرها.")):
        # المفتاح فيه النوع والمنصة: لما يتغيّروا الاختيارات ترجع لافتراضيهم الجديد
        _k = f"{new_type}_{platform}"
        res = st.selectbox(t("الدقة الافتراضية"), RESOLUTIONS, index=RESOLUTIONS.index(res),
                           help=FIELD_HELP["default_resolution"], key=k(f"res_{_k}"))
        orient = st.selectbox(t("الاتجاه الافتراضي"), ORIENTATIONS, index=ORIENTATIONS.index(orient),
                              format_func=t, help=FIELD_HELP["default_orientation"], key=k(f"orient_{_k}"))
        ratio = st.selectbox(t("نسبة الأبعاد الافتراضية"), RATIOS, index=RATIOS.index(ratio),
                             key=k(f"ratio_{_k}"))
    else:
        st.caption(f"{t(res)} · {t(orient)} · {ratio}")

    # (أ) المشروع الجديد بيبدأ بمنشئه (والمديرين بيشوفوا الكل)؛ الاختيار ده
    # بيضيف كل أعضاء مساحة العمل مرة واحدة
    add_all = st.checkbox(t("ضيف كل فريق مساحة العمل للمشروع"), key=k("add_all"),
                          help=t("من غيرها المشروع بيبدأ بيك انت بس، وتضيف الأعضاء من ⚙️ إعدادات المشروع."))
    if not st.button(t("إنشاء المشروع"), key=k("create"), type="primary", use_container_width=True):
        return False
    if not new_name.strip():
        st.warning(t("اكتب اسم المشروع أولًا"))
        return False
    if new_type == "مسلسل" and not episode_count:
        st.warning(t("اكتب عدد حلقات المسلسل"))
        return False
    accounts.create_project(current_user, company_id, new_name.strip(), new_type, res, orient, ratio,
                            episode_count=episode_count, type_details=details, add_all_members=add_all)
    for old_key in [x for x in st.session_state if str(x).startswith("new_proj_")]:
        st.session_state.pop(old_key, None)
    st.session_state["_new_proj_nonce"] = n + 1
    # المشروع الجديد بيتفتح على طول على «إضافة سيناريو» والشريط بيتقفل -
    # قبل كده كنت بتفضل على المشروع القديم والشريط مفتوح (المالك 2026-09-24)
    st.session_state["_link_project_name"] = new_name.strip()
    go_to("import")
    st.toast(t("تم إنشاء المشروع"), icon="✅")
    return True
