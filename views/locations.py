"""تبويب locations."""

import image_gen
import streamlit as st
from i18n import t, tr
from search import matches
from ui import delete_image_file, library_result_count, library_search, mark_saved, render_image_picker, safe_index, show_saved_badge
from ui import guarded_delete
import repo


def render(project_id):
    st.subheader(tr("sub_locations"))

    locations = repo.locations_of_project(project_id)
    location_name_by_id = {l["id"]: l["name"] for l in locations}

    # المكتبة الأول، والإضافة سطر واحد مقفول. قبل كده فورم الإضافة الفاضي كان
    # أول حاجة في التبويب والـ 99 مكان تحت منه. لما المكتبة فاضية الفورم بيبقى
    # مفتوح — الشاشة الفاضية دعوة إنك تضيف.
    _loc_q = library_search(f"loc_search_{project_id}", len(locations), "مكان") if locations else ""
    with st.expander(f"➕ {t('إضافة مكان جديد')}", expanded=not locations):
        st.caption(t(
            "لو عندك مكان رئيسي وجواه أماكن فرعية (زي شقة حسام وجواها غرفة نوم)، "
            "أضف المكان الرئيسي الأول، وبعدين أضف المكان الفرعي واختار له 'تابع لمكان رئيسي'."
        ))
        with st.form(f"add_location_{project_id}"):
            loc_name = st.text_input(t("اسم المكان"), placeholder=t("مثال: شقة حسام"))
            parent_add_options = ["بدون - مكان رئيسي"] + [l["name"] for l in locations]
            loc_parent = st.selectbox(t("تابع لمكان رئيسي؟"), parent_add_options, format_func=t)
            loc_desc = st.text_area(
                t("وصف عام ثابت للمكان"),
                placeholder=t("مثال: شقة قديمة في حي شعبي، جدرانها بيج فاتح، فيها أثاث خشبي تقيل"),
            )
            if st.form_submit_button(t("إضافة مكان")):
                if loc_name.strip():
                    parent_id = None
                    if loc_parent != "بدون - مكان رئيسي":
                        parent_id = {l["name"]: l["id"] for l in locations}.get(loc_parent)
                    repo.add_location(project_id, loc_name, loc_desc, parent_id)
                    st.rerun()
    if not locations:
        st.caption(t("مفيش أماكن مضافة لسه"))

    st.divider()

    children_by_parent = {}
    for l in locations:
        if l["parent_location_id"]:
            children_by_parent.setdefault(l["parent_location_id"], []).append(l)

    def render_location(l, indent=""):
        # كسول: محتوى الـ expander بيتنفذ بس وهو مفتوح. من غير كده كل فورم تعديل
        # لكل عنصر مقفول كان بيتبني مع كل ضغطة في أي مكان في البرنامج (556 فورم،
        # 16 ثانية لكل rerun على الإنتاج).
        _lazy_exp = st.expander(f"{indent}📍 {l['name']}", key=f"exp_loc_{l['id']}", on_change="rerun")
        with _lazy_exp:
            if _lazy_exp.open:
                st.markdown(f"**{t('🖼️ صورة المكان')}**")

                def _save_loc_image(rel, _id=l["id"]):
                    repo.set_location_image(rel, _id)

                render_image_picker(
                    f"locimg_{l['id']}", l["reference_image_path"], f"locations/{l['id']}",
                    lambda extra, _l=l: image_gen.build_prompt(
                        _l["name"], _l["base_description"] or "", extra=extra),
                    _save_loc_image,
                )
                st.markdown('<hr class="cf-soft-sep">', unsafe_allow_html=True)

                with st.form(f"edit_location_{l['id']}"):
                    e_loc_name = st.text_input(t("اسم المكان"), value=l["name"])
                    edit_parent_options = ["بدون - مكان رئيسي"] + [
                        other["name"] for other in locations if other["id"] != l["id"]
                    ]
                    current_parent_name = location_name_by_id.get(l["parent_location_id"], "بدون - مكان رئيسي")
                    e_loc_parent = st.selectbox(
                        t("تابع لمكان رئيسي؟"), edit_parent_options,
                        index=safe_index(edit_parent_options, current_parent_name),
                        format_func=t,
                    )
                    e_loc_desc = st.text_area(
                        t("وصف عام ثابت للمكان"), value=l["base_description"] or "",
                        placeholder=t("مثال: شقة قديمة في حي شعبي، جدرانها بيج فاتح، فيها أثاث خشبي تقيل"),
                    )
                    save_col, del_col = st.columns(2)
                    with save_col:
                        save_loc = st.form_submit_button(t("💾 حفظ التعديل"))
                    with del_col:
                        del_loc = st.form_submit_button(t("🗑️ حذف المكان (وكل حالاته)"))
                if save_loc:
                    if e_loc_name.strip():
                        new_parent_id = None
                        if e_loc_parent != "بدون - مكان رئيسي":
                            new_parent_id = {o["name"]: o["id"] for o in locations if o["id"] != l["id"]}.get(e_loc_parent)
                        repo.update_location(e_loc_name, e_loc_desc, new_parent_id, l["id"])
                        mark_saved(f"loc_{l['id']}")
                        st.rerun()
                    else:
                        st.warning(t("اسم المكان مينفعش يبقى فاضي"))
                show_saved_badge(f"loc_{l['id']}")
                if del_loc:
                    ok = guarded_delete(repo.delete_location, (l["id"],), t("معرفش أمسح المكان ده لأنه مستخدم في مشهد، أو ليه أماكن فرعية تابعة له. شيل الارتباطات دي الأول."))
                    if ok:
                        delete_image_file(l["reference_image_path"])
                        st.success(t("تم حذف المكان"))
                        st.rerun()

                st.markdown(f"**{t('الحالات (Variants):')}**")
                st.caption(t(
                    "الحالة هي شكل المكان نفسه في وقت معيّن من الأحداث (محروق، بعد التجديد، بعد سنين). "
                    "داخلي/خارجي ونهار/ليل بيتحددوا في المشهد، مش هنا."
                ))
                variants = repo.states_of_location(l["id"])
                if not variants:
                    st.caption(t("مفيش حالات مضافة لسه"))
                move_options = {other["name"]: other["id"] for other in locations}
                for v in variants:
                    with st.container(border=True):
                        with st.form(f"edit_variant_{v['id']}"):
                            ev_name = st.text_input(t("حالة المكان"), value=v["variant_name"])
                            ev_desc = st.text_area(t("وصف التغييرات الخاصة بهذه الحالة"), value=v["description"] or "")
                            ev_move_to = st.selectbox(
                                t("المكان (غيّره لو عايز تنقل الحالة دي لمكان تاني — مفيد لدمج أماكن مكررة)"),
                                list(move_options.keys()), index=safe_index(list(move_options.keys()), l["name"]),
                            )
                            vsave_col, vdel_col = st.columns(2)
                            with vsave_col:
                                save_var = st.form_submit_button(t("💾 حفظ"))
                            with vdel_col:
                                del_var = st.form_submit_button(t("🗑️ حذف الحالة"))
                        if save_var:
                            repo.update_location_state(ev_name, ev_desc, move_options[ev_move_to], v["id"])
                            mark_saved(f"variant_{v['id']}")
                            st.rerun()
                        if del_var:
                            ok = guarded_delete(repo.delete_location_state, (v["id"],), t("معرفش أمسح الحالة دي لأنها مستخدمة في مشهد أو أكتر. شيلها من المشاهد دي الأول من تبويب السكريبت."))
                            if ok:
                                delete_image_file(v["reference_image_path"])
                                st.success(t("تم حذف الحالة"))
                                st.rerun()
                        show_saved_badge(f"variant_{v['id']}")

                        st.caption(t("صورة مرجعية للحالة"))

                        def _save_var_image(rel, _id=v["id"]):
                            repo.set_location_state_image(rel, _id)

                        render_image_picker(
                            f"varimg_{v['id']}", v["reference_image_path"], f"locations/{l['id']}",
                            lambda extra, _l=l, _v=v: image_gen.build_prompt(
                                _l["name"], _l["base_description"] or "",
                                _v["variant_name"], _v["description"] or "", extra=extra),
                            _save_var_image,
                        )

                # فورم إضافة الحالة مقفول لحد ما اليوزر يطلبه — لو مفتوح تحت كل
                # مكان من الأول الصفحة بتبقى زحمة ومشتتة.
                open_key = f"add_var_open_{l['id']}"
                if not st.session_state.get(open_key):
                    if st.button(t("➕ إضافة حالة"), key=f"add_var_btn_{l['id']}"):
                        st.session_state[open_key] = True
                        st.rerun()
                else:
                    with st.form(f"add_variant_{l['id']}", clear_on_submit=True):
                        st.markdown(f"**{t('➕ حالة جديدة لـ')} {l['name']}**")
                        v_name = st.text_input(
                            t("حالة المكان"),
                            placeholder=t("مثال: الشكل الرئيسي للمكان، أو: المكان محروق، أو: المكان بعد التجديد"))
                        v_desc = st.text_area(
                            t("وصف التغييرات الخاصة بهذه الحالة"),
                            placeholder=t("مثال: المكان اتحرق واتهد بعد حريق في نص الأحداث"))
                        st.caption(t("تقدر تضيف صورة للحالة بعد ما تتحفظ — رفع أو كاميرا أو توليد."))
                        add_col, cancel_col = st.columns(2)
                        with add_col:
                            add_var = st.form_submit_button(t("إضافة الحالة"))
                        with cancel_col:
                            cancel_var = st.form_submit_button(t("إلغاء"))
                    if add_var:
                        if v_name.strip():
                            repo.add_location_state(l["id"], v_name.strip(), v_desc)
                            st.session_state[open_key] = False
                            st.rerun()
                        else:
                            st.warning(t("اكتب اسم الحالة الأول"))
                    if cancel_var:
                        st.session_state[open_key] = False
                        st.rerun()

        for child in children_by_parent.get(l["id"], []):
            render_location(child, indent="↳ ")

    def _loc_hit(l):
        return matches(_loc_q, l["name"], l["base_description"])

    top_level_locations = [l for l in locations if not l["parent_location_id"]]
    _loc_shown = 0
    for l in top_level_locations:
        if _loc_hit(l) or any(_loc_hit(k) for k in children_by_parent.get(l["id"], [])):
            render_location(l)
            _loc_shown += 1
    if _loc_q:
        library_result_count(_loc_shown, len(top_level_locations))
