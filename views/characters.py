"""تبويب characters."""

import streamlit as st
from database import FIELD_HELP, GENDER_OPTIONS, SPECIES_OPTIONS, fetch_all, run_delete, run_query
from i18n import t, tr
from search import matches
from ui import IMAGE_TYPES, delete_image_file, image_abs_path, library_result_count, library_search, mark_saved, safe_index, save_uploaded_image, show_saved_badge


def render(project_id):
    st.subheader(tr("sub_characters"))
    _chars_before = fetch_all("SELECT id FROM characters WHERE project_id=?", (project_id,))
    _char_q = (library_search(f"char_search_{project_id}", len(_chars_before), "شخصية")
               if _chars_before else "")
    with st.expander(f"➕ {t('إضافة شخصية جديدة')}", expanded=not _chars_before):
        with st.form(f"add_character_{project_id}"):
            ch_name = st.text_input(t("اسم الشخصية"), placeholder=t("مثال: أحمد"))
            ch_role = st.selectbox(t("نوع الدور"), ["بطل", "شرير", "مساعد", "كومبارس"], format_func=t)
            ch_species = st.selectbox(t("نوع الكائن"), SPECIES_OPTIONS, format_func=t, help=FIELD_HELP["species"])
            ch_gender = st.selectbox(t("الجنس"), GENDER_OPTIONS, format_func=t, help=FIELD_HELP["gender"])
            ch_notes = st.text_area(
                t("ملاحظات عامة عن الشخصية"),
                placeholder=t("زي الوزن والبنية الجسمانية (نحيف/تخين/رياضي...) وأي تفاصيل تانية"),
            )
            ch_image = st.file_uploader(t("صورة الشخصية المرجعية (اختياري)"), type=IMAGE_TYPES, key="new_character_image")
            if st.form_submit_button(t("إضافة شخصية")):
                if ch_name.strip():
                    new_char_id = run_query(
                        """INSERT INTO characters
                        (project_id, name, role_type, species, gender, personality_notes)
                        VALUES (?,?,?,?,?,?)""",
                        (project_id, ch_name, ch_role, ch_species, ch_gender, ch_notes),
                    )
                    if ch_image is not None:
                        image_path = save_uploaded_image(ch_image, f"characters/{new_char_id}")
                        run_query("UPDATE characters SET reference_image_path=? WHERE id=?", (image_path, new_char_id))
                    st.rerun()

    characters = fetch_all("SELECT * FROM characters WHERE project_id=?", (project_id,))
    with st.expander(f"➕ {t('إضافة مظهر إضافي لشخصية')}", expanded=False):
        if characters:
            char_map = {c["name"]: c["id"] for c in characters}
            sel_char = st.selectbox(t("اختر شخصية لإضافة مظهر إضافي لها"), list(char_map.keys()))
            char_id = char_map[sel_char]
            with st.form(f"add_look_{char_id}"):
                st.caption(t("المظهر الإضافي بيمثل شكل تاني للشخصية في لحظة مختلفة من القصة (مثال: حلق دقنه، لابس نضارة، اتصاب وبقى في جبس)."))
                look_name = st.text_input(t("اسم المظهر الإضافي"), placeholder=t("مثال: المظهر الرئيسي - حلق دقنه ولابس نضارة"))
                look_age = st.text_input(t("السن الظاهر"), placeholder=t("مثال: 30 سنة"), help=FIELD_HELP["apparent_age"])
                look_makeup = st.selectbox(t("حالة المكياج"), ["طبيعي", "كامل", "بدون", "آثار إصابة", "مكياج شيخوخة"], format_func=t, help=FIELD_HELP["makeup_state"])
                look_hair = st.text_input(t("حالة الشعر"), placeholder=t("مثال: شعر قصير أسود"))
                look_wardrobe = st.text_area(t("وصف الملابس والإكسسوارات"), placeholder=t("مثال: قميص أبيض وبنطلون جينز وساعة يد"))
                look_desc = st.text_area(
                    t("وصف تفصيلي كامل للمظهر (يُستخدم كمرجع للتوليد)"),
                    placeholder=t("مثال: راجل في الثلاثينات، نحيف، شعره قصير أسود، لابس نضارة طبية..."),
                )
                look_image = st.file_uploader(t("صورة مرجعية (اختياري)"), type=IMAGE_TYPES, key="new_look_image")
                if st.form_submit_button(t("➕ إضافة مظهر إضافي")):
                    image_path = save_uploaded_image(look_image, f"characters/{char_id}")
                    run_query(
                        """INSERT INTO character_looks
                        (character_id, look_name, apparent_age, makeup_state, hair_state, wardrobe_description, description, reference_image_path)
                        VALUES (?,?,?,?,?,?,?,?)""",
                        (char_id, look_name, look_age, look_makeup, look_hair, look_wardrobe, look_desc, image_path),
                    )
                    st.rerun()
        else:
            st.caption(t("مفيش شخصيات مضافة لسه"))

    st.divider()
    role_options = ["بطل", "شرير", "مساعد", "كومبارس", "غير محدد"]
    makeup_options = ["طبيعي", "كامل", "بدون", "آثار إصابة", "مكياج شيخوخة"]
    _chars_shown = [c for c in characters
                    if matches(_char_q, c["name"], c["role_type"], c["personality_notes"])]
    if _char_q:
        library_result_count(len(_chars_shown), len(characters))
    for ch in _chars_shown:
        # كسول: محتوى الـ expander بيتنفذ بس وهو مفتوح. من غير كده كل فورم تعديل
        # لكل عنصر مقفول كان بيتبني مع كل ضغطة في أي مكان في البرنامج (556 فورم،
        # 16 ثانية لكل rerun على الإنتاج).
        _lazy_exp = st.expander(f"🎭 {ch['name']} ({t(ch['role_type'])})", key=f"exp_char_{ch['id']}", on_change="rerun")
        with _lazy_exp:
            if _lazy_exp.open:
                with st.form(f"edit_character_{ch['id']}"):
                    ech_name = st.text_input(t("اسم الشخصية"), value=ch["name"])
                    ech_role = st.selectbox(t("نوع الدور"), role_options,
                                             index=safe_index(role_options, ch["role_type"]), format_func=t)
                    ech_species = st.selectbox(t("نوع الكائن"), SPECIES_OPTIONS,
                                                index=safe_index(SPECIES_OPTIONS, ch["species"]), format_func=t, help=FIELD_HELP["species"])
                    ech_gender = st.selectbox(t("الجنس"), GENDER_OPTIONS,
                                               index=safe_index(GENDER_OPTIONS, ch["gender"]), format_func=t, help=FIELD_HELP["gender"])
                    ech_notes = st.text_area(
                        t("ملاحظات عامة عن الشخصية"), value=ch["personality_notes"] or "",
                        placeholder=t("زي الوزن والبنية الجسمانية (نحيف/تخين/رياضي...) وأي تفاصيل تانية"),
                    )
                    if ch["reference_image_path"]:
                        existing_ch_img = image_abs_path(ch["reference_image_path"])
                        if existing_ch_img:
                            st.image(existing_ch_img, width=220)
                
                    # Generate or Upload menu
                    char_image_action = st.radio(
                        t("طريقة إضافة صورة الشخصية"),
                        [t("رفع من الجهاز"), t("توليد (قريباً)")],
                        index=0,
                        key=f"character_image_action_{ch['id']}"
                    )
                
                    ech_image = None
                    if char_image_action == t("رفع من الجهاز"):
                        ech_image = st.file_uploader(
                            t("اختر صورة مرجعية للشخصية"), type=IMAGE_TYPES, key=f"character_image_{ch['id']}"
                        )
                    else:
                        st.info("🔒 ميزة توليد صور الشخصيات الذكية قيد التطوير — ستتمكن قريباً من توليد صور بناءً على الوصف والملابس والمكياج")
                    csave_col, cdel_col = st.columns(2)
                    with csave_col:
                        save_ch = st.form_submit_button(t("💾 حفظ التعديل"))
                    with cdel_col:
                        del_ch = st.form_submit_button(t("🗑️ حذف الشخصية (وكل مظاهرها)"))
                if save_ch:
                    if ech_name.strip():
                        new_ch_image_path = ch["reference_image_path"]
                        if ech_image is not None:
                            new_ch_image_path = save_uploaded_image(ech_image, f"characters/{ch['id']}")
                        run_query(
                            """UPDATE characters SET name=?, role_type=?, species=?, gender=?,
                            personality_notes=?, reference_image_path=? WHERE id=?""",
                            (ech_name, ech_role, ech_species, ech_gender, ech_notes, new_ch_image_path, ch["id"]),
                        )
                        mark_saved(f"char_{ch['id']}")
                        st.rerun()
                    else:
                        st.warning(t("اسم الشخصية مينفعش يبقى فاضي"))
                if del_ch:
                    ok = run_delete(
                        "DELETE FROM characters WHERE id=?", (ch["id"],),
                        t("معرفش أمسح الشخصية دي لأن مظهر بتاعها مستخدم في لقطة أو أكتر. شيلها من اللقطات دي الأول من تبويب التفريغ."),
                    )
                    if ok:
                        delete_image_file(ch["reference_image_path"])
                        st.success(t("تم حذف الشخصية"))
                        st.rerun()
                show_saved_badge(f"char_{ch['id']}")

                st.markdown(f"**{t('المظاهر الإضافية:')}**")
                looks = fetch_all("SELECT * FROM character_looks WHERE character_id=?", (ch["id"],))
                if not looks:
                    st.caption(t("مفيش مظاهر إضافية متضافة لسه"))
                for lk in looks:
                    with st.form(f"edit_look_{lk['id']}"):
                        elk_name = st.text_input(t("اسم المظهر الإضافي"), value=lk["look_name"])
                        elk_age = st.text_input(t("السن الظاهر"), value=lk["apparent_age"] or "", placeholder=t("مثال: 30 سنة"))
                        elk_makeup = st.selectbox(t("حالة المكياج"), makeup_options,
                                                   index=safe_index(makeup_options, lk["makeup_state"]), format_func=t)
                        elk_hair = st.text_input(t("حالة الشعر"), value=lk["hair_state"] or "", placeholder=t("مثال: شعر قصير أسود"))
                        elk_wardrobe = st.text_area(
                            t("وصف الملابس والإكسسوارات"), value=lk["wardrobe_description"] or "",
                            placeholder=t("مثال: قميص أبيض وبنطلون جينز وساعة يد"),
                        )
                        elk_desc = st.text_area(
                            t("وصف تفصيلي كامل للمظهر"), value=lk["description"] or "",
                            placeholder=t("مثال: راجل في الثلاثينات، نحيف، شعره قصير أسود، لابس نضارة طبية..."),
                        )
                        if lk["reference_image_path"]:
                            existing_look_img = image_abs_path(lk["reference_image_path"])
                            if existing_look_img:
                                st.image(existing_look_img, width=220)
                        elk_image = st.file_uploader(t("تغيير الصورة المرجعية"), type=IMAGE_TYPES, key=f"look_image_{lk['id']}")
                        lsave_col, ldel_col = st.columns(2)
                        with lsave_col:
                            save_lk = st.form_submit_button(t("💾 حفظ"))
                        with ldel_col:
                            del_lk = st.form_submit_button(t("🗑️ حذف المظهر الإضافي"))
                    if save_lk:
                        new_look_image_path = lk["reference_image_path"]
                        if elk_image is not None:
                            new_look_image_path = save_uploaded_image(elk_image, f"characters/{ch['id']}")
                        run_query(
                            """UPDATE character_looks SET look_name=?, apparent_age=?, makeup_state=?,
                            hair_state=?, wardrobe_description=?, description=?, reference_image_path=? WHERE id=?""",
                            (elk_name, elk_age, elk_makeup, elk_hair, elk_wardrobe, elk_desc, new_look_image_path, lk["id"]),
                        )
                        mark_saved(f"look_{lk['id']}")
                        st.rerun()
                    if del_lk:
                        ok = run_delete(
                            "DELETE FROM character_looks WHERE id=?", (lk["id"],),
                            t("معرفش أمسح المظهر ده لأنه مستخدم في لقطة أو أكتر. شيله من اللقطات دي الأول من تبويب التفريغ."),
                        )
                        if ok:
                            delete_image_file(lk["reference_image_path"])
                            st.success(t("تم حذف المظهر الإضافي"))
                            st.rerun()
                    show_saved_badge(f"look_{lk['id']}")
