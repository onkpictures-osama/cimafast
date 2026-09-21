"""تبويب props."""

import streamlit as st
from i18n import t, tr
from search import matches
from ui import library_result_count, library_search, mark_saved, safe_index, show_saved_badge
import repo


def render(project_id):
    st.subheader(tr("sub_props"))

    characters_for_props = repo.characters_of_project_by_id(project_id)
    char_options_for_props = ["بدون - غير مرتبط بشخصية"] + [c["name"] for c in characters_for_props]
    char_id_by_name = {c["name"]: c["id"] for c in characters_for_props}

    _props_before = repo.prop_ids_of_project(project_id)
    _prop_q = (library_search(f"prop_search_{project_id}", len(_props_before), "إكسسوار")
               if _props_before else "")
    with st.expander(f"➕ {t('إضافة إكسسوار جديد')}", expanded=not _props_before):
        st.caption(t(
            "أي حاجة بيمسكها أو بيستخدمها أي شخصية أو ليها دور في حدث المشهد (سكينة، تليفون، شنطة، سلاح...). "
            "تقدر تربط الإكسسوار بشخصية معينة (زي مسدس البطل)، وتعلّم عليه لو حساس للراكورد (يعني لازم يفضل في "
            "نفس الحالة بين اللقطات المتتالية)."
        ))
        with st.form(f"add_prop_{project_id}"):
            prop_name = st.text_input(t("اسم الإكسسوار"), placeholder=t("مثال: سكينة عم جابر"))
            prop_continuity = st.checkbox(t("حساس للراكورد؟ (لازم يفضل في نفس الحالة بين اللقطات)"))
            prop_character = st.selectbox(t("مرتبط بشخصية (اختياري)"), char_options_for_props)
            if st.form_submit_button(t("إضافة إكسسوار")):
                if prop_name.strip():
                    linked_char_id = char_id_by_name.get(prop_character)
                    repo.add_prop(project_id, prop_name, int(prop_continuity), linked_char_id)
                    st.rerun()
                else:
                    st.warning(t("اسم الإكسسوار مينفعش يبقى فاضي"))

    st.divider()
    props_list = repo.props_of_project(project_id)
    if not props_list:
        st.caption(t("مفيش إكسسوارات مضافة لسه"))
    _char_name_by_id = {c["id"]: c["name"] for c in characters_for_props}
    _props_shown = [pr for pr in props_list
                    if matches(_prop_q, pr["name"], _char_name_by_id.get(pr["character_id"]))]
    if _prop_q:
        library_result_count(len(_props_shown), len(props_list))
    for pr in _props_shown:
        char_label = next((c["name"] for c in characters_for_props if c["id"] == pr["character_id"]), None)
        badge = f" — {t('مرتبط بـ')} {char_label}" if char_label else ""
        # كسول: محتوى الـ expander بيتنفذ بس وهو مفتوح. من غير كده كل فورم تعديل
        # لكل عنصر مقفول كان بيتبني مع كل ضغطة في أي مكان في البرنامج (556 فورم،
        # 16 ثانية لكل rerun على الإنتاج).
        _lazy_exp = st.expander(f"🎒 {pr['name']}{badge}", key=f"exp_prop_{pr['id']}", on_change="rerun")
        with _lazy_exp:
            if _lazy_exp.open:
                with st.form(f"edit_prop_{pr['id']}"):
                    ep_name = st.text_input(t("اسم الإكسسوار"), value=pr["name"])
                    ep_continuity = st.checkbox(
                        t("حساس للراكورد؟ (لازم يفضل في نفس الحالة بين اللقطات)"),
                        value=bool(pr["continuity_sensitive"]),
                    )
                    ep_char_options = ["بدون - غير مرتبط بشخصية"] + [c["name"] for c in characters_for_props]
                    current_char_name = char_label or "بدون - غير مرتبط بشخصية"
                    ep_character = st.selectbox(
                        t("مرتبط بشخصية (اختياري)"), ep_char_options,
                        index=safe_index(ep_char_options, current_char_name),
                    )
                    psave_col, pdel_col = st.columns(2)
                    with psave_col:
                        save_pr = st.form_submit_button(t("💾 حفظ التعديل"))
                    with pdel_col:
                        del_pr = st.form_submit_button(t("🗑️ حذف الإكسسوار"))
                if save_pr:
                    if ep_name.strip():
                        new_linked_char_id = char_id_by_name.get(ep_character)
                        repo.update_prop(ep_name, int(ep_continuity), new_linked_char_id, pr["id"])
                        mark_saved(f"prop_{pr['id']}")
                        st.rerun()
                    else:
                        st.warning(t("اسم الإكسسوار مينفعش يبقى فاضي"))
                if del_pr:
                    repo.delete_prop(pr["id"])
                    st.success(t("تم حذف الإكسسوار"))
                    st.rerun()
                show_saved_badge(f"prop_{pr['id']}")
