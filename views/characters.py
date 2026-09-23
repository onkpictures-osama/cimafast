"""تبويب characters."""

import image_gen
import streamlit as st
from database import FIELD_HELP, GENDER_OPTIONS, SPECIES_OPTIONS
from i18n import t, tr
from search import matches
from ui import IMAGE_TYPES, delete_image_file, image_abs_path, library_result_count, library_search, mark_saved, render_image_picker, safe_index, save_uploaded_image, show_saved_badge
from ui import guarded_delete
import repo
from views.looks import render_looks_summary as _render_looks_summary

# صورة الممثل/ة الحقيقي المتعاقد معاه/ا + صورة خلفية/مكان - نفس الفكرة
# للشخصية وللمظهر الإضافي، عشان التوليد يتقيّد بيهم لو موجودين (P2 - مرجع
# 2026-09-23: "خزانة المواهب" فيها صورة الممثل أصلًا لو اتعيّن، لكن هنا
# بنسيب رفع يدوي بسيط بدل ما نربط التبويبين - أبسط وميحتاجش الممثل يبقى
# متعيّن الأول عشان تولّد صورة للشخصية).
_CHAR_REFERENCE_SLOTS = [
    ("actor", "صورة الممثل/ة الحقيقي (اختياري)"),
    ("bg", "صورة خلفية/مكان (اختياري)"),
]


def render(project_id):
    st.subheader(tr("sub_characters"))
    _chars_before = repo.character_ids_of_project(project_id)
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
                    new_char_id = repo.add_character(project_id, ch_name, ch_role, ch_species, ch_gender, ch_notes)
                    if ch_image is not None:
                        image_path = save_uploaded_image(ch_image, f"characters/{new_char_id}")
                        repo.set_character_image(project_id, image_path, new_char_id)
                    st.rerun()

    characters = repo.characters_of_project(project_id)
    # P5: إضافة المظهر بقت جوه كارت الشخصية نفسها (_render_looks_summary) بدل
    # expander منفصل مستخبي اسمه "إضافي" - اللي كان سبب إن محدش لاقيه.

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
                # P9 خزانة المواهب: مين الممثل/ة المتعاقد معاه/ا لهذا الدور -
                # لو لسه مفيش حد، بروفايل الممثل/ة نفسه (تبويب خزانة المواهب)
                # هو اللي بيعمل التعيين (مش من هنا)، عشان نفس المنطق يفضل
                # مكانه واحد بدل ما يتكرر جوه كل شاشة.
                _casting = repo.casting_for_character(ch["id"])
                if _casting:
                    _cast_label = _casting.get("stage_name") or _casting["full_name"]
                    _cast_title = ("الممثل/ة المتعاقد معاه/ا" if _casting["status"] == "cast"
                                   else "الممثل/ة المرشّح/ة")
                    _cast_img = image_abs_path(_casting["photo_path"]) if _casting.get("photo_path") else None
                    if _cast_img:
                        st.image(_cast_img, width=64)
                    st.caption(f"🎬 {t(_cast_title)}: {_cast_label}")
                else:
                    st.caption(t("لسه مفيش ممثل/ة متعيّن لهذا الدور. عيّنه من بروفايله في تبويب «خزانة المواهب»."))

                st.markdown(f"**{t('🖼️ صورة الشخصية المرجعية')}**")

                def _save_char_image(rel, _id=ch["id"]):
                    repo.set_character_image(project_id, rel, _id)

                render_image_picker(
                    f"charimg_{ch['id']}", ch["reference_image_path"], f"characters/{ch['id']}",
                    lambda shot_size, light, _c=ch: image_gen.build_character_prompt(
                        _c["name"], _c["role_type"] or "", _c["species"] or "", _c["gender"] or "",
                        _c["personality_notes"] or "", shot_size=shot_size, light=light),
                    _save_char_image,
                    reference_slots=_CHAR_REFERENCE_SLOTS,
                )
                st.markdown('<hr class="cf-soft-sep">', unsafe_allow_html=True)

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
                    csave_col, cdel_col = st.columns(2)
                    with csave_col:
                        save_ch = st.form_submit_button(t("💾 حفظ التعديل"))
                    with cdel_col:
                        del_ch = st.form_submit_button(t("🗑️ حذف الشخصية (وكل مظاهرها)"))
                if save_ch:
                    if ech_name.strip():
                        repo.update_character(project_id, ech_name, ech_role, ech_species, ech_gender, ech_notes, ch["reference_image_path"], ch["id"])
                        mark_saved(f"char_{ch['id']}")
                        st.rerun()
                    else:
                        st.warning(t("اسم الشخصية مينفعش يبقى فاضي"))
                if del_ch:
                    ok = guarded_delete(repo.delete_character, (project_id, ch["id"]), t("معرفش أمسح الشخصية دي لأن مظهر بتاعها مستخدم في لقطة أو أكتر. شيلها من اللقطات دي الأول من تبويب التفريغ."))
                    if ok:
                        delete_image_file(ch["reference_image_path"])
                        st.success(t("تم حذف الشخصية"))
                        st.rerun()
                show_saved_badge(f"char_{ch['id']}")

                _render_looks_summary(project_id, ch)

                st.markdown(f"**{t('تفاصيل كل مظهر (تعديل وصورة):')}**")
                looks = repo.looks_of_character(ch["id"])
                if not looks:
                    st.caption(t("مفيش مظاهر إضافية متضافة لسه"))
                for lk in looks:
                    with st.container(border=True):
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
                            lsave_col, ldel_col = st.columns(2)
                            with lsave_col:
                                save_lk = st.form_submit_button(t("💾 حفظ"))
                            with ldel_col:
                                del_lk = st.form_submit_button(t("🗑️ حذف المظهر الإضافي"))
                        if save_lk:
                            repo.update_character_look(project_id, elk_name, elk_age, elk_makeup, elk_hair, elk_wardrobe, elk_desc, lk["reference_image_path"], lk["id"])
                            mark_saved(f"look_{lk['id']}")
                            st.rerun()
                        if del_lk:
                            ok = guarded_delete(repo.delete_character_look, (project_id, lk["id"]), t("معرفش أمسح المظهر ده لأنه مستخدم في لقطة أو أكتر. شيله من اللقطات دي الأول من تبويب التفريغ."))
                            if ok:
                                delete_image_file(lk["reference_image_path"])
                                st.success(t("تم حذف المظهر الإضافي"))
                                st.rerun()
                        show_saved_badge(f"look_{lk['id']}")

                        st.caption(t("🖼️ صورة مرجعية للمظهر"))

                        def _save_look_image(rel, _id=lk["id"]):
                            repo.set_character_look_image(project_id, rel, _id)

                        render_image_picker(
                            f"lookimg_{lk['id']}", lk["reference_image_path"], f"characters/{ch['id']}",
                            lambda shot_size, light, _c=ch, _lk=lk: image_gen.build_character_prompt(
                                _c["name"], _c["role_type"] or "", _c["species"] or "", _c["gender"] or "",
                                _c["personality_notes"] or "", _lk["look_name"] or "", _lk["apparent_age"] or "",
                                _lk["makeup_state"] or "", _lk["hair_state"] or "", _lk["wardrobe_description"] or "",
                                _lk["description"] or "", shot_size=shot_size, light=light),
                            _save_look_image,
                            reference_slots=_CHAR_REFERENCE_SLOTS,
                        )
