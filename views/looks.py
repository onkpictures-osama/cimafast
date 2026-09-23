"""P5 المظاهر والراكور: مظاهر الشخصية كحاجة أساسية في الكارت نفسه.

كل شخصية ليها مظهر أساسي واحد بالظبط (is_default) - بيتعمل أوتوماتيك مع
الشخصية (repo.add_character) ومبيتمسحش لو هو آخر مظهر. هنا الواجهة بس:
مين الأساسي، المظاهر التانية مع زرار "خليه الأساسي"، وفورم إضافة مظهر جديد
بيستعمله كارت الشخصية وتنبيه تغيير المظهر في المشهد الاتنين.
"""

import streamlit as st
from database import FIELD_HELP
from i18n import t
from ui import IMAGE_TYPES, save_uploaded_image
import permissions
import repo

MAKEUP_OPTIONS = ["طبيعي", "كامل", "بدون", "آثار إصابة", "مكياج شيخوخة"]


def can_edit():
    """المشاهد بس (viewer) بيشوف الزراير مقفولة. طبقة البيانات برضو بترفض
    أي كتابة منه (permissions.require في run_query) - ده بس عشان ميتلخبطش."""
    role = permissions.current_role()
    return role is None or permissions.can(role, "edit")


def look_label(look):
    # t(): "المظهر الافتراضي" اللي بيتعمل أوتوماتيك بيتترجم، والأسماء اللي
    # اليوزر كتبها بترجع زي ما هي
    return t(look["look_name"]) if look["look_name"] else t("مظهر من غير اسم")


def default_look(looks):
    """المظهر الأساسي من قايمة مظاهر شخصية (أو أول واحد لو مفيش علامة)."""
    return next((lk for lk in looks if lk.get("is_default")), looks[0] if looks else None)


def add_look_form(form_key, character_id, name_value="", desc_value="", after_save_label=None):
    """فورم مظهر جديد. بيرجّع (id المظهر الجديد، قيمة الاختيار الإضافي) لما يتحفظ،
    وإلا None. after_save_label: لو موجود بيظهر checkbox زيادة (زي "استعمله في
    المشهد ده") وقيمته بترجع مع الـ id."""
    with st.form(form_key, clear_on_submit=True):
        st.caption(t("المظهر بيمثل شكل تاني للشخصية في لحظة مختلفة من القصة (مثال: حلق دقنه، لابس نضارة، اتصاب وبقى في جبس)."))
        name = st.text_input(t("اسم المظهر"), value=name_value,
                             placeholder=t("مثال: بعد الحادثة - دراعه في جبس"))
        age = st.text_input(t("السن الظاهر"), placeholder=t("مثال: 30 سنة"), help=FIELD_HELP["apparent_age"])
        makeup = st.selectbox(t("حالة المكياج"), MAKEUP_OPTIONS, format_func=t, help=FIELD_HELP["makeup_state"])
        hair = st.text_input(t("حالة الشعر"), placeholder=t("مثال: شعر قصير أسود"))
        wardrobe = st.text_area(t("وصف الملابس والإكسسوارات"), placeholder=t("مثال: قميص أبيض وبنطلون جينز وساعة يد"))
        desc = st.text_area(
            t("وصف تفصيلي كامل للمظهر (يُستخدم كمرجع للتوليد)"), value=desc_value,
            placeholder=t("مثال: راجل في الثلاثينات، نحيف، شعره قصير أسود، لابس نضارة طبية..."),
        )
        image = st.file_uploader(t("صورة مرجعية (اختياري)"), type=IMAGE_TYPES, key=f"{form_key}_image")
        extra = st.checkbox(t(after_save_label), value=True) if after_save_label else None
        submitted = st.form_submit_button(t("➕ إضافة المظهر"), disabled=not can_edit())
    if not submitted:
        return None
    if not name.strip():
        st.warning(t("اكتب اسم للمظهر عشان تعرف تفرّقه عن الباقي"))
        return None
    image_path = save_uploaded_image(image, f"characters/{character_id}") if image is not None else None
    look_id = repo.add_character_look(character_id, name.strip(), age, makeup, hair, wardrobe, desc, image_path)
    return look_id, extra


def render_looks_summary(project_id, ch):
    """جوه كارت الشخصية: المظهر الرئيسي، المظاهر التانية، وإضافة مظهر."""
    looks = repo.looks_of_character(ch["id"])
    primary = default_look(looks)
    st.markdown(f"**{t('👤 المظهر الرئيسي')}:** {look_label(primary) if primary else '—'}")
    others = [lk for lk in looks if primary is None or lk["id"] != primary["id"]]
    if others:
        st.markdown(f"**{t('مظاهر تانية')}:**")
        for lk in others:
            with st.container(key=f"cf_look_row_{lk['id']}"):
                name_col, act_col = st.columns([3, 2], vertical_alignment="center")
                name_col.markdown(f"• {look_label(lk)}")
                if act_col.button(t("⭐ خليه الأساسي"), key=f"make_default_look_{lk['id']}",
                                  disabled=not can_edit(), use_container_width=True):
                    repo.set_default_look(project_id, lk["id"])
                    st.rerun()
    else:
        st.caption(t("لسه مفيش مظاهر تانية. ضيف مظهر لما الشخصية يتغير شكلها في القصة."))
    st.caption(t("المظهر الرئيسي هو اللي بيتحط أوتوماتيك في أي مشهد أو لقطة، لحد ما تختار غيره هناك."))
    if st.toggle(t("➕ إضافة مظهر جديد للشخصية دي"), key=f"add_look_toggle_{ch['id']}", disabled=not can_edit()):
        if add_look_form(f"add_look_{ch['id']}", ch["id"]):
            st.success(t("تم إضافة المظهر"))
            st.rerun()
    st.markdown('<hr class="cf-soft-sep">', unsafe_allow_html=True)
