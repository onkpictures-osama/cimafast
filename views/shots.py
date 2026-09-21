"""تبويب breakdown."""

import streamlit as st
from database import (
    CAMERA_ANGLE_OPTIONS,
    CAMERA_MOVEMENT_OPTIONS,
    DAY_NIGHT_OPTIONS,
    FIELD_HELP,
    SHOT_SIZE_OPTIONS,
    fetch_all,
    next_free_number,
    scene_label,
)
from i18n import t, tr
from ui import IMAGE_TYPES, bump_version, delete_image_file, fmt_day_night, image_abs_path, ltr, mark_saved, multiselect, safe_index, save_uploaded_image, shift_shot_numbers, show_saved_badge, unused_dialogue_lines
import repo


def render(project_id):
    st.subheader(tr("sub_breakdown"))
    scenes = repo.scenes_of_project(project_id)
    if not scenes:
        st.info(t("لازم تضيف مشهد واحد على الأقل من تبويب السكريبت أولًا"))
    else:
        scene_map = {f"{t('مشهد')} {ltr(scene_label(s))}": s["id"] for s in scenes}
        sel_scene = st.selectbox(t("اختر المشهد"), list(scene_map.keys()))
        scene_id = scene_map[sel_scene]
        current_scene_row = repo.scene_notes_and_time(scene_id)[0]
        available_dialogue_lines = unused_dialogue_lines(current_scene_row["notes"], scene_id, fetch_all)

        with st.form(f"add_shot_{scene_id}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                sh_number = st.number_input(
                    t("رقم اللقطة"), min_value=1, step=1,
                    value=next_free_number(r["shot_number"] for r in repo.shot_numbers_of_scene(scene_id)))
                sh_size = st.selectbox(t("حجم الكادر"), SHOT_SIZE_OPTIONS, format_func=t, help=FIELD_HELP["shot_size"])
            with col2:
                sh_movement = st.selectbox(t("حركة الكاميرا"), CAMERA_MOVEMENT_OPTIONS, format_func=t, help=FIELD_HELP["camera_movement"])
                sh_angle = st.selectbox(t("زاوية الكاميرا"), CAMERA_ANGLE_OPTIONS, format_func=t, help=FIELD_HELP["camera_angle"])
            with col3:
                sh_duration = st.number_input(t("المدة (ثانية)"), min_value=1.0, max_value=30.0, value=5.0, step=0.5)
                sh_emotion = st.slider(t("قوة المشاعر"), 1, 5, 3, help=FIELD_HELP["emotion_intensity"])

            col4, col5 = st.columns(2)
            with col4:
                # اللقطة الجديدة بتاخد نهار/ليل المشهد بتاعها كقيمة افتراضية، والمستخدم
                # يقدر يغيّرها لو اللقطة دي بالذات اتصورت في وقت مختلف عن باقي المشهد
                sh_day_night = st.selectbox(t("النهار/الليل"), DAY_NIGHT_OPTIONS,
                                             index=safe_index(DAY_NIGHT_OPTIONS, current_scene_row["day_night"]),
                                             format_func=fmt_day_night,
                                             help=FIELD_HELP["day_night"])
            with col5:
                sh_weather = st.text_input(t("حالة الطقس"), placeholder=t("مثال: شتاء مشمس، أو صيف حار وضبابي"))

            sh_action = st.text_area(
                t("وصف الحركة داخل اللقطة"), height=100,
                placeholder=t("مثال: أحمد بيدخل الأوضة وبيقفل الباب وراه، سارة واقفة جنب الشباك بتبص برة"),
            )
            sh_emotion_label = st.text_input(t("وصف المشاعر"), placeholder=t("مثال: أحمد حزين، سارة غير مهتمة"))
            if available_dialogue_lines:
                st.caption(t(
                    "دول سطور الحوار اللي لسه في حوار المشهد ومتحطوش في لقطة تانية - اختار بس اللي موجود في "
                    "اللقطة دي (سيبها من غير اختيار لو اللقطة من غير حوار)."
                ))
                sh_selected_dialogue = multiselect(t("سطور الحوار المتاحة من حوار المشهد"), available_dialogue_lines)
                sh_dialogue = "\n".join(sh_selected_dialogue)
                with st.expander(t("أو اكتب/عدّل الحوار يدويًا بدل الاختيار")):
                    sh_dialogue_manual = st.text_area(
                        t("الحوار (لو موجود)"), height=100,
                        placeholder=t("مثال: أحمد (حزين): إزيك يا سارة؟\nسارة (غير مبالية): تمام والحمد لله."),
                    )
                    if sh_dialogue_manual.strip():
                        sh_dialogue = sh_dialogue_manual
            else:
                sh_dialogue = st.text_area(
                    t("الحوار (لو موجود)"), height=150,
                    placeholder=t("مثال: أحمد (حزين): إزيك يا سارة؟\nسارة (غير مبالية): تمام والحمد لله."),
                )
            sh_style = st.text_area(
                t("ملاحظات النمط البصري / المرجع"), height=120,
                placeholder=t("مثال: إضاءة دافية، ألوان بيج وبني، حركة كاميرا هادئة"),
            )
            sh_music = st.checkbox(t("تضمين موسيقى في التوليد نفسه؟ (غير مستحسن)"), value=False, help=FIELD_HELP["include_music"])

            st.markdown(f"**{t('الشخصيات الموجودة في اللقطة')}**")
            all_looks = repo.look_labels_of_project(project_id)
            look_map = {r["label"]: r["id"] for r in all_looks}
            selected_looks = multiselect(t("اختر مظهر كل شخصية ظاهرة"), list(look_map.keys()))
            dialogue_flags = {}
            if selected_looks:
                st.caption(t("لكل شخصية، حدد لو ليها حوار في اللقطة دي (سيبها فاضية لو الشخصية موجودة بس ساكتة)"))
                for _label in selected_looks:
                    dialogue_flags[_label] = st.checkbox(
                        f"{_label} — {t('لها حوار في اللقطة دي؟')}", value=True, key=f"new_shot_dialogue_{_label}",
                    )

            st.markdown(f"**{t('الإكسسوارات الموجودة في اللقطة')}**")
            all_props = repo.prop_names_by_id(project_id)
            prop_map = {r["name"]: r["id"] for r in all_props}
            selected_props = multiselect(t("اختر الإكسسوارات الظاهرة في اللقطة"), list(prop_map.keys()))

            sh_confirmed = st.checkbox(t("🔵 تمت المراجعة والموافقة على كل بيانات اللقطة"), help=FIELD_HELP["confirmed"])
            sh_storyboard = st.file_uploader(t("صورة ستوري بورد مرجعية (اختياري)"), type=IMAGE_TYPES, key="new_shot_storyboard")

            if st.form_submit_button(t("حفظ اللقطة")):
                existing_shot_numbers_now = {
                    s["shot_number"] for s in repo.shot_numbers_of_scene(scene_id)
                }
                if sh_number in existing_shot_numbers_now:
                    shift_shot_numbers(scene_id, sh_number)
                    st.info(t("الرقم ده كان مستخدم - تم نقل باقي اللقطات رقم واحد لقدام عشان تتزبط."))
                shot_id = repo.add_shot(scene_id, sh_number, sh_size, sh_movement, sh_angle, sh_duration, sh_day_night, sh_weather, sh_action, sh_emotion, sh_emotion_label, sh_dialogue, sh_style, int(sh_music), int(sh_confirmed))
                bump_version(project_id)
                if sh_storyboard is not None:
                    storyboard_path = save_uploaded_image(sh_storyboard, f"shots/{shot_id}")
                    repo.set_shot_storyboard(storyboard_path, shot_id)
                for label in selected_looks:
                    repo.add_shot_character(shot_id, look_map[label], int(dialogue_flags.get(label, True)))
                for prop_label in selected_props:
                    repo.add_shot_prop(shot_id, prop_map[prop_label])
                st.success(t("تم حفظ اللقطة"))
                st.rerun()

        st.divider()
        shots = repo.shots_of_scene(scene_id)
        for sh in shots:
            status_icon = "🔵" if sh["confirmed"] else "🟡"
            # كسول: محتوى الـ expander بيتنفذ بس وهو مفتوح. من غير كده كل فورم تعديل
            # لكل عنصر مقفول كان بيتبني مع كل ضغطة في أي مكان في البرنامج (556 فورم،
            # 16 ثانية لكل rerun على الإنتاج).
            _lazy_exp = st.expander(f"{status_icon} {t('لقطة')} {sh['shot_number']} — {ltr(t(sh['shot_size']))} / {ltr(t(sh['camera_movement']))}", key=f"exp_shot_{sh['id']}", on_change="rerun")
            with _lazy_exp:
                if _lazy_exp.open:
                    current_looks = repo.characters_in_shot(sh["id"])
                    current_dialogue_by_look_id = {r["look_id"]: bool(r["has_dialogue"]) for r in current_looks}
                    current_look_ids = set(current_dialogue_by_look_id.keys())
                    current_labels = [label for label, lid in look_map.items() if lid in current_look_ids]
                    current_prop_ids = {
                        r["prop_id"] for r in repo.prop_ids_in_shot(sh["id"])
                    }
                    current_prop_labels = [name for name, pid in prop_map.items() if pid in current_prop_ids]

                    with st.form(f"edit_shot_{sh['id']}"):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            esh_number = st.number_input(t("رقم اللقطة"), min_value=1, step=1, value=sh["shot_number"])
                            esh_size = st.selectbox(t("حجم الكادر"), SHOT_SIZE_OPTIONS,
                                                     index=safe_index(SHOT_SIZE_OPTIONS, sh["shot_size"]), format_func=t)
                        with col2:
                            esh_movement = st.selectbox(t("حركة الكاميرا"), CAMERA_MOVEMENT_OPTIONS,
                                                         index=safe_index(CAMERA_MOVEMENT_OPTIONS, sh["camera_movement"]), format_func=t)
                            esh_angle = st.selectbox(t("زاوية الكاميرا"), CAMERA_ANGLE_OPTIONS,
                                                      index=safe_index(CAMERA_ANGLE_OPTIONS, sh["camera_angle"]), format_func=t)
                        with col3:
                            esh_duration = st.number_input(
                                t("المدة (ثانية)"), min_value=1.0, max_value=30.0,
                                value=float(sh["duration_seconds"] or 5.0), step=0.5,
                            )
                            esh_emotion = st.slider(t("قوة المشاعر"), 1, 5, value=sh["emotion_intensity"] or 3)

                        ecol4, ecol5 = st.columns(2)
                        with ecol4:
                            esh_day_night = st.selectbox(
                                t("النهار/الليل"), DAY_NIGHT_OPTIONS,
                                index=safe_index(DAY_NIGHT_OPTIONS, sh["day_night"]),
                                format_func=fmt_day_night,
                            )
                        with ecol5:
                            esh_weather = st.text_input(
                                t("حالة الطقس"), value=sh["weather"] or "",
                                placeholder=t("مثال: شتاء مشمس، أو صيف حار وضبابي"),
                            )

                        esh_action = st.text_area(
                            t("وصف الحركة داخل اللقطة"), value=sh["action_description"] or "", height=100,
                            placeholder=t("مثال: أحمد بيدخل الأوضة وبيقفل الباب وراه، سارة واقفة جنب الشباك بتبص برة"),
                        )
                        esh_emotion_label = st.text_input(
                            t("وصف المشاعر"), value=sh["emotion_label"] or "", placeholder=t("مثال: أحمد حزين، سارة غير مهتمة"),
                        )
                        esh_edit_available_lines = unused_dialogue_lines(
                            current_scene_row["notes"], scene_id, fetch_all, exclude_shot_id=sh["id"]
                        )
                        if esh_edit_available_lines:
                            esh_current_dialogue_lines = [
                                l.strip() for l in (sh["dialogue_text"] or "").split("\n") if l.strip()
                            ]
                            st.caption(t(
                                "دول سطور الحوار اللي لسه في حوار المشهد ومتحطوش في لقطة تانية - اختار بس اللي موجود في "
                                "اللقطة دي (سيبها من غير اختيار لو اللقطة من غير حوار)."
                            ))
                            esh_selected_dialogue = multiselect(
                                t("سطور الحوار المتاحة من حوار المشهد"), esh_edit_available_lines,
                                default=[l for l in esh_current_dialogue_lines if l in esh_edit_available_lines],
                            )
                            esh_dialogue = "\n".join(esh_selected_dialogue)
                            with st.expander(t("أو اكتب/عدّل الحوار يدويًا بدل الاختيار")):
                                esh_dialogue_manual = st.text_area(
                                    t("الحوار (لو موجود)"), value="", height=100,
                                    placeholder=t("مثال: أحمد (حزين): إزيك يا سارة؟\nسارة (غير مبالية): تمام والحمد لله."),
                                )
                                if esh_dialogue_manual.strip():
                                    esh_dialogue = esh_dialogue_manual
                        else:
                            esh_dialogue = st.text_area(
                                t("الحوار (لو موجود)"), value=sh["dialogue_text"] or "", height=150,
                                placeholder=t("مثال: أحمد (حزين): إزيك يا سارة؟\nسارة (غير مبالية): تمام والحمد لله."),
                            )
                        esh_style = st.text_area(
                            t("ملاحظات النمط البصري / المرجع"), value=sh["visual_style_notes"] or "", height=120,
                            placeholder=t("مثال: إضاءة دافية، ألوان بيج وبني، حركة كاميرا هادئة"),
                        )
                        esh_music = st.checkbox(t("تضمين موسيقى في التوليد نفسه؟ (غير مستحسن)"), value=bool(sh["include_music"]))

                        st.markdown(f"**{t('الشخصيات الموجودة في اللقطة')}**")
                        esh_selected_looks = multiselect(
                            t("اختر مظهر كل شخصية ظاهرة"), list(look_map.keys()), default=current_labels
                        )
                        esh_dialogue_flags = {}
                        if esh_selected_looks:
                            st.caption(t("لكل شخصية، حدد لو ليها حوار في اللقطة دي (سيبها فاضية لو الشخصية موجودة بس ساكتة)"))
                            for _label in esh_selected_looks:
                                _default = current_dialogue_by_look_id.get(look_map[_label], True)
                                esh_dialogue_flags[_label] = st.checkbox(
                                    f"{_label} — {t('لها حوار في اللقطة دي؟')}", value=_default,
                                    key=f"edit_shot_dialogue_{sh['id']}_{_label}",
                                )

                        st.markdown(f"**{t('الإكسسوارات الموجودة في اللقطة')}**")
                        esh_selected_props = multiselect(
                            t("اختر الإكسسوارات الظاهرة في اللقطة"), list(prop_map.keys()), default=current_prop_labels
                        )

                        esh_confirmed = st.checkbox(t("🔵 تمت المراجعة والموافقة على كل بيانات اللقطة"), value=bool(sh["confirmed"]))

                        if sh["storyboard_image_path"]:
                            existing_storyboard = image_abs_path(sh["storyboard_image_path"])
                            if existing_storyboard:
                                st.image(existing_storyboard, width=260)
                        esh_storyboard = st.file_uploader(
                            t("تغيير صورة الستوري بورد المرجعية"), type=IMAGE_TYPES, key=f"shot_storyboard_{sh['id']}"
                        )

                        hsave_col, hdel_col = st.columns(2)
                        with hsave_col:
                            save_sh = st.form_submit_button(t("💾 حفظ التعديل"))
                        with hdel_col:
                            del_sh = st.form_submit_button(t("🗑️ حذف اللقطة"))

                    if save_sh:
                        if esh_number != sh["shot_number"]:
                            colliding_shot = repo.other_shot_with_number(sh["scene_id"], esh_number, sh["id"])
                            if colliding_shot:
                                shift_shot_numbers(sh["scene_id"], esh_number, exclude_shot_id=sh["id"])
                                st.info(t("الرقم ده كان مستخدم - تم نقل باقي اللقطات رقم واحد لقدام عشان تتزبط."))
                        new_storyboard_path = sh["storyboard_image_path"]
                        if esh_storyboard is not None:
                            new_storyboard_path = save_uploaded_image(esh_storyboard, f"shots/{sh['id']}")
                        repo.update_shot(esh_number, esh_size, esh_movement, esh_angle, esh_duration, esh_day_night, esh_weather, esh_action, esh_emotion, esh_emotion_label, esh_dialogue, esh_style, int(esh_music), int(esh_confirmed), new_storyboard_path, sh["id"])
                        repo.unlink_shot_characters(sh["id"])
                        for label in esh_selected_looks:
                            repo.add_shot_character(sh["id"], look_map[label], int(esh_dialogue_flags.get(label, True)))
                        repo.unlink_shot_props(sh["id"])
                        for prop_label in esh_selected_props:
                            repo.add_shot_prop(sh["id"], prop_map[prop_label])
                        bump_version(project_id)
                        mark_saved(f"shot_{sh['id']}")
                        st.rerun()
                    if del_sh:
                        repo.delete_shot(sh["id"])
                        bump_version(project_id)
                        delete_image_file(sh["storyboard_image_path"])
                        st.success(t("تم حذف اللقطة"))
                        st.rerun()
                    show_saved_badge(f"shot_{sh['id']}")
