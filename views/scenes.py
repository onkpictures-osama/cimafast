"""تبويب scenes."""

import pandas as pd
import streamlit as st
from database import DAY_NIGHT_OPTIONS, INT_EXT_OPTIONS, next_free_number, scene_label
from i18n import t, tr
from search import matches
from ui import _loc_display, bump_version, fmt_day_night, fmt_int_ext, library_result_count, library_search, ltr, mark_saved, multiselect, safe_index, shift_scene_numbers, show_saved_badge
import repo


def render(project, project_id, _is_ar):
    st.subheader(tr("sub_scenes"))

    locations_all = repo.location_state_labels(project_id)
    loc_variant_map = {r["label"]: r["id"] for r in locations_all}

    _scenes_before = repo.scene_ids_of_project(project_id)
    _scene_q = (library_search(f"scene_search_{project_id}", len(_scenes_before), "مشاهد")
                if _scenes_before else "")
    with st.expander(f"➕ {t('إضافة مشهد جديد')}", expanded=not _scenes_before):
        with st.form(f"add_scene_{project_id}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                sc_number = st.number_input(
                    t("رقم المشهد"), min_value=1, step=1,
                    value=next_free_number(r["scene_number"] for r in repo.scene_numbers_of_project(project_id)))
                sc_int_ext = st.selectbox(t("داخلي/خارجي"), INT_EXT_OPTIONS, format_func=fmt_int_ext, key="scene_int_ext")
            with col2:
                sc_day_night = st.selectbox(t("التوقيت"), DAY_NIGHT_OPTIONS, format_func=fmt_day_night, key="scene_day_night")
                sc_location = st.selectbox(t("المكان"), ["بدون تحديد"] + list(loc_variant_map.keys()), format_func=t)
            with col3:
                sc_weather = st.text_input(t("الطقس"), placeholder=t("مثال: شتاء مشمس، أو صيف حار وضبابي"))
        
            # Episode selection for series
            sc_episode_id = None
            if project["project_type"] == "مسلسل":
                episodes = repo.episode_labels(project_id)
                if episodes:
                    ep_options = ["بدون حلقة"] + [f"الحلقة {ep['episode_number']}: {ep['title']}" for ep in episodes]
                    sc_episode_choice = st.selectbox(t("اختر الحلقة"), ep_options, key=f"scene_episode_{project_id}")
                    if sc_episode_choice != "بدون حلقة":
                        ep_idx = ep_options.index(sc_episode_choice) - 1
                        sc_episode_id = episodes[ep_idx]['id']
            sc_notes = st.text_area(t("ملاحظات المشهد العامة"), height=150)
            all_chars_for_scene = repo.character_names_by_id(project_id)
            char_map_for_scene = {c["name"]: c["id"] for c in all_chars_for_scene}
            sc_characters = multiselect(t("الشخصيات الموجودة في المشهد"), list(char_map_for_scene.keys()))
            all_props_for_scene = repo.prop_names_by_id(project_id)
            prop_map_for_scene = {p["name"]: p["id"] for p in all_props_for_scene}
            sc_props = multiselect(t("الإكسسوارات الموجودة في المشهد"), list(prop_map_for_scene.keys()))
            if st.form_submit_button(t("إضافة مشهد")):
                loc_id = loc_variant_map.get(sc_location)
                existing_scene_numbers_now = {
                    s["scene_number"] for s in repo.scene_numbers_of_project(project_id)
                }
                if sc_number in existing_scene_numbers_now:
                    # الرقم ده مستخدم قبل كده - بندفع كل المشاهد اللي رقمها أكبر
                    # أو يساويه رقم واحد لقدام، عشان المشهد الجديد يحتل الرقم ده
                    # بالظبط من غير ما يبوّظ ترتيب المشاهد التانية
                    shift_scene_numbers(project_id, sc_number)
                    st.info(t("الرقم ده كان مستخدم - تم نقل باقي المشاهد رقم واحد لقدام عشان تتزبط."))
                new_scene_id = repo.add_scene(project_id, sc_episode_id, sc_number, sc_int_ext, sc_day_night, sc_weather, loc_id, sc_notes)
                for _cname in sc_characters:
                    repo.link_character_to_scene(project_id, new_scene_id, char_map_for_scene[_cname])
                for _pname in sc_props:
                    repo.link_prop_to_scene(project_id, new_scene_id, prop_map_for_scene[_pname])
                bump_version(project_id)
                st.rerun()

    st.divider()
    scenes = repo.scenes_of_project(project_id)
    id_to_loc_label = {v: k for k, v in loc_variant_map.items()}

    # جدول المشاهد: نظرة واحدة على كل المشاهد بدل 143 سطر مقفول شبه بعض.
    # البحث والاختيار من الجدول بيصفّوا القايمة اللي تحت (اللي فيها التعديل).
    _chars_by_scene = {}
    for r in repo.scene_character_names(project_id):
        _chars_by_scene.setdefault(r["scene_id"], []).append(r["name"])
    _shots_by_scene = {r["scene_id"]: r["n"] for r in repo.shot_counts_per_scene(project_id)}

    _scenes_shown = scenes
    if scenes:
        _scenes_shown = [
            sc for sc in scenes
            if matches(_scene_q, scene_label(sc), sc["int_ext"], sc["day_night"],
                       id_to_loc_label.get(sc["location_variant_id"]), sc["notes"],
                       " ".join(_chars_by_scene.get(sc["id"], [])))
        ]
        _table = pd.DataFrame([{
            t("رقم"): scene_label(sc),
            t("داخلي/خارجي"): fmt_int_ext(sc["int_ext"] or "غير محدد"),
            t("التوقيت"): fmt_day_night(sc["day_night"] or "غير محدد"),
            t("المكان"): _loc_display(id_to_loc_label.get(sc["location_variant_id"])) or "—",
            t("الشخصيات"): len(_chars_by_scene.get(sc["id"], [])),
            t("اللقطات"): _shots_by_scene.get(sc["id"], 0),
        } for sc in _scenes_shown])
        if _is_ar and not _table.empty:
            _table = _table[_table.columns[::-1]]       # الرقم يبقى في أول العين: يمين
        with st.container(key="cf_scene_table"):
            _pick = st.dataframe(
                _table, hide_index=True, use_container_width=True,
                height=min(38 + 35 * max(len(_table), 1), 420),
                on_select="rerun", selection_mode="multi-row",
                key=f"scene_table_{project_id}",
            )
        _rows = [r for r in (_pick.selection.rows if _pick is not None else []) if r < len(_scenes_shown)]
        if _scene_q:
            library_result_count(len(_scenes_shown), len(scenes))
        if _rows:
            _scenes_shown = [_scenes_shown[r] for r in _rows]
        elif not _scene_q:
            # من غير اختيار ولا بحث مفيش فورمات تعديل خالص. قبل كده كان فيه 143
            # فورم كامل بيتبنوا تحت الجدول — وتبويبات Streamlit كلها بتتنفذ مع أي
            # ضغطة في أي مكان، فكانوا بيتبنوا مع كل حركة في البرنامج.
            _scenes_shown = []
            st.caption(t("اختار مشهد أو أكتر من الجدول (المربع جنب الصف) عشان تعدّلهم أو تمسحهم."))
    # H4: جاي من تنبيه (‎&item=‎) — المشهد اللي اتغيّر بس، وفورمته مفتوحة.
    # لو المشهد مش في المشروع ده (اتمسح، أو رابط مشروع تاني) بنتجاهل الرابط.
    _focus_id = st.session_state.get("_focus_scene")
    _focused = [sc for sc in scenes if sc["id"] == _focus_id] if (_focus_id and scenes) else []
    if _focus_id and not _focused:
        st.session_state.pop("_focus_scene", None)
    if _focused:
        _scenes_shown = _focused
        _fc1, _fc2 = st.columns([0.7, 0.3], vertical_alignment="center")
        _fc1.info(f"🔔 {t('بتعرض المشهد اللي اتغيّر بس.')}")
        if _fc2.button(t("اعرض كل المشاهد"), key="clear_scene_focus", use_container_width=True):
            st.session_state.pop("_focus_scene", None)
            st.rerun()
    int_ext_edit_options = ["غير محدد"] + INT_EXT_OPTIONS
    day_night_edit_options = ["غير محدد"] + DAY_NIGHT_OPTIONS
    loc_edit_options = ["بدون تحديد"] + list(loc_variant_map.keys())

    selected_scene_ids_for_bulk_delete = []
    for sc in _scenes_shown:
        _loc_label = _loc_display(id_to_loc_label.get(sc["location_variant_id"]))
        title = (
            f"{t('مشهد')} {ltr(scene_label(sc))} — {ltr(fmt_int_ext(sc['int_ext'] or 'غير محدد'))} / "
            f"{fmt_day_night(sc['day_night'] or 'غير محدد')}"
            + (f" — 📍 {_loc_label}" if _loc_label else "")
        )
        cb_col, exp_col = st.columns([0.05, 0.95])
        with cb_col:
            st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)
            if st.checkbox("", key=f"bulk_sel_scene_{sc['id']}", label_visibility="collapsed"):
                selected_scene_ids_for_bulk_delete.append(sc["id"])
        # كسول: محتوى الـ expander بيتنفذ بس وهو مفتوح. من غير كده كل فورم تعديل
        # لكل عنصر مقفول كان بيتبني مع كل ضغطة في أي مكان في البرنامج (556 فورم،
        # 16 ثانية لكل rerun على الإنتاج).
        _lazy_exp = exp_col.expander(title, key=f"exp_scene_{sc['id']}", on_change="rerun",
                                     expanded=bool(_focused))
        with _lazy_exp:
            if _lazy_exp.open:
                with st.form(f"edit_scene_{sc['id']}"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        esc_number = st.number_input(t("رقم المشهد"), min_value=1, step=1, value=sc["scene_number"])
                        esc_int_ext = st.selectbox(
                            t("داخلي/خارجي"), int_ext_edit_options,
                            index=safe_index(int_ext_edit_options, sc["int_ext"] or "غير محدد"),
                            format_func=fmt_int_ext,
                        )
                    with col2:
                        esc_day_night = st.selectbox(
                            t("التوقيت"), day_night_edit_options,
                            index=safe_index(day_night_edit_options, sc["day_night"] or "غير محدد"),
                            format_func=fmt_day_night,
                        )
                        esc_location = st.selectbox(
                            t("المكان"), loc_edit_options,
                            index=safe_index(loc_edit_options, id_to_loc_label.get(sc["location_variant_id"], "بدون تحديد")),
                            format_func=t,
                        )
                    with col3:
                        esc_weather = st.text_input(
                            t("الطقس"), value=sc["weather"] or "",
                            placeholder=t("مثال: شتاء مشمس، أو صيف حار وضبابي"),
                        )
                    esc_notes = st.text_area(t("ملاحظات المشهد العامة"), value=sc["notes"] or "", height=180)

                    esc_current_char_ids = {
                        r["character_id"] for r in repo.character_ids_in_scene(sc["id"])
                    }
                    esc_current_char_names = [n for n, cid in char_map_for_scene.items() if cid in esc_current_char_ids]
                    esc_characters = multiselect(
                        t("الشخصيات الموجودة في المشهد"), list(char_map_for_scene.keys()),
                        default=esc_current_char_names,
                    )
                    esc_current_prop_ids = {
                        r["prop_id"] for r in repo.prop_ids_in_scene(sc["id"])
                    }
                    esc_current_prop_names = [n for n, pid in prop_map_for_scene.items() if pid in esc_current_prop_ids]
                    esc_props = multiselect(
                        t("الإكسسوارات الموجودة في المشهد"), list(prop_map_for_scene.keys()),
                        default=esc_current_prop_names,
                    )

                    ssave_col, sdel_col = st.columns(2)
                    with ssave_col:
                        save_sc = st.form_submit_button(t("💾 حفظ التعديل"))
                    with sdel_col:
                        del_sc = st.form_submit_button(t("🗑️ حذف المشهد (وكل لقطاته)"))
                if save_sc:
                    new_int_ext = None if esc_int_ext == "غير محدد" else esc_int_ext
                    new_day_night = None if esc_day_night == "غير محدد" else esc_day_night
                    new_loc_id = loc_variant_map.get(esc_location)
                    if esc_number != sc["scene_number"]:
                        colliding = repo.other_scene_with_number(project_id, esc_number, sc["id"])
                        if colliding:
                            shift_scene_numbers(project_id, esc_number, exclude_scene_id=sc["id"])
                            st.info(t("الرقم ده كان مستخدم - تم نقل باقي المشاهد رقم واحد لقدام عشان تتزبط."))
                    repo.update_scene(project_id, esc_number, new_int_ext, new_day_night, esc_weather, new_loc_id, esc_notes, sc["id"])
                    repo.unlink_scene_characters(project_id, sc["id"])
                    for _cname in esc_characters:
                        repo.link_character_to_scene(project_id, sc["id"], char_map_for_scene[_cname])
                    repo.unlink_scene_props(project_id, sc["id"])
                    for _pname in esc_props:
                        repo.link_prop_to_scene(project_id, sc["id"], prop_map_for_scene[_pname])
                    bump_version(project_id)
                    mark_saved(f"scene_{sc['id']}")
                    st.rerun()
                if del_sc:
                    repo.delete_scene(project_id, sc["id"])
                    bump_version(project_id)
                    st.success(t("تم حذف المشهد"))
                    st.rerun()
                show_saved_badge(f"scene_{sc['id']}")

    if selected_scene_ids_for_bulk_delete:
        with st.container(key=f"bulk_delete_scenes_{project_id}"):
            if st.button(
                f"🗑️ {t('حذف')} {len(selected_scene_ids_for_bulk_delete)} {t('مشهد مختار (وكل لقطاتهم)')}",
            ):
                for _sid in selected_scene_ids_for_bulk_delete:
                    repo.delete_scene(project_id, _sid)
                bump_version(project_id)
                st.success(t("تم حذف المشاهد المختارة"))
                st.rerun()
