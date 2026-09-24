"""تبويب dashboard."""

import streamlit as st
from database import fetch_all, scene_label
from export import build_characters_sheet_excel, build_wardrobe_sheet_excel, build_general_breakdown_excel, build_locations_sheet_excel, build_props_sheet_excel, build_shot_list_excel, build_shot_list_pdf, build_shot_list_word
from i18n import t, tr
from ui import ltr
import audit
import repo


def render(project, project_id, _char_count, _loc_count, _scene_count, _shot_count):
    st.subheader(tr("sub_dashboard"))

    # «إيه اللي ناقص» قبل أزرار التصدير. العنوان بيوعد بنظرة عامة، والتبويب
    # كان أزرار تحميل بس — فمدير الإنتاج مكانش عنده مكان يشوف فيه إيه اللي
    # لسه مش جاهز قبل ما يطبع الكشوفات.
    if _scene_count > 0:
        _gaps = [
            (t("مشاهد من غير لقطات"), repo.scenes_without_shots(project_id),
             lambda r: f"{t('مشهد')} {ltr(scene_label(r))}"),
            (t("مشاهد من غير شخصيات"), repo.scenes_without_characters(project_id),
             lambda r: f"{t('مشهد')} {ltr(scene_label(r))}"),
            (t("أماكن من غير صورة مرجعية"), repo.locations_without_image(project_id),
             lambda r: r["name"]),
            (t("شخصيات من غير صورة مرجعية"), repo.characters_without_image(project_id),
             lambda r: r["name"]),
            (t("لقطات لسه متراجعتش"), repo.unreviewed_shots(project_id),
             lambda r: f"{t('مشهد')} {ltr(scene_label(r))} / {t('لقطة')} {ltr(r['shot_number'])}"),
        ]
        st.markdown(f"#### {t('إيه اللي لسه ناقص')}")
        _open = [(label, rows, fmt) for label, rows, fmt in _gaps if rows]
        if not _open:
            st.success(t("مفيش حاجة ناقصة — كل المشاهد ليها لقطات وشخصيات، وكل حاجة ليها صورة ومتراجعة."))
        for label, rows, fmt in _open:
            with st.expander(f"{label} — {ltr(len(rows))}"):
                _shown = rows[:60]
                st.markdown(" · ".join(fmt(r) for r in _shown)
                            + (f" … (+{ltr(len(rows) - len(_shown))})" if len(rows) > len(_shown) else ""))
        st.divider()

    if _scene_count > 0:
        st.markdown(f"#### {t('📄 تصدير تفريغ اللقطات')}")
        st.caption(t("ملف تفريغ كامل قابل للطباعة، بفورمات سينمائي احترافي."))

        # الملفات بتتبني لما حد يدوس تحميل، من آخر بيانات، في thread منفصل
        # (download_button بياخد دالة). قبل كده كانت بتتبني مسبقًا وتتخزن بمفتاح
        # من *أعداد* الصفوف بس — فتعديل محتوى (اسم شخصية، مكان مشهد، حوار) من
        # غير ما العدد يتغير كان بيطلّع ملف قديم، وكان فيه زرار «تحديث الملفات»
        # بيطلب من المستخدم يفتكر يدوس عليه. وكمان السبعة كانوا بيتبنوا مع أول
        # rerun بعد أي تغيير عدد، حتى لو محدش فاتح التقارير.
        # F3: حدث التصدير بيتسجّل جوه الدالة دي — يعني لما المستخدم يدوس تحميل
        # فعلًا، مش لما الشاشة تترسم. ده الفرق بين "صدّر" و"شاف زرار التصدير".
        # بنقرا المستخدم والشركة هنا (في thread الـ script) لأن بناء الملف بيحصل
        # في thread تاني مالوش جلسة Streamlit.
        _who = st.session_state.get("_auth_user")
        _co = st.session_state.get("_cf_company")

        def _lazy(build):
            def _download():
                audit.event("export", target=build.__name__.replace("build_", ""),
                            username=_who, company_id=_co, project_id=project_id)
                return build(project, project_id, fetch_all)
            return _download


        exp_col1, exp_col2, exp_col3, exp_col4 = st.columns(4)
        with exp_col1:
            st.download_button(
                tr("btn_export_excel"),
                data=_lazy(build_shot_list_excel),
                file_name=f"{project['name']}_تفريغ_اللقطات.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_excel_{project_id}",
            )
        with exp_col2:
            st.download_button(
                tr("btn_export_word"),
                data=_lazy(build_shot_list_word),
                file_name=f"{project['name']}_تفريغ_اللقطات.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"dl_word_{project_id}",
            )
        with exp_col3:
            st.download_button(
                tr("btn_export_pdf"),
                data=_lazy(build_shot_list_pdf),
                file_name=f"{project['name']}_تفريغ_اللقطات.pdf",
                mime="application/pdf",
                key=f"dl_pdf_{project_id}",
            )

        st.markdown(f"#### {t('📋 تقارير الإنتاج القياسية')}")
        st.caption(t(
            "نفس الأوراق القياسية اللي بيستخدمها مديرو الإنتاج (كشف الشخصيات، التفريغ العام، كشف أماكن "
            "التصوير)، متملية أوتوماتيك من بيانات مشروعك. الخانات اللي محتاجة قرار بشري (زي الترشيح، عدد "
            "أيام التصوير، عدد الصفحات) سايبينها فاضية عشان تملاها إنت وقت التحضير الفعلي للتصوير."
        ))
        rep_col1, rep_col2, rep_col3, rep_col4 = st.columns(4)
        with rep_col1:
            st.download_button(
                t("⬇️ كشف الشخصيات"),
                data=_lazy(build_characters_sheet_excel),
                file_name=f"{project['name']}_كشف_الشخصيات.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_characters_sheet_{project_id}",
            )
        with rep_col2:
            st.download_button(
                t("⬇️ التفريغ العام"),
                data=_lazy(build_general_breakdown_excel),
                file_name=f"{project['name']}_التفريغ_العام.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_general_breakdown_{project_id}",
            )
        with rep_col3:
            st.download_button(
                t("⬇️ كشف أماكن التصوير"),
                data=_lazy(build_locations_sheet_excel),
                file_name=f"{project['name']}_كشف_اماكن_التصوير.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_locations_sheet_{project_id}",
            )
        with rep_col4:
            st.download_button(
                t("⬇️ كشف الإكسسوار"),
                data=_lazy(build_props_sheet_excel),
                file_name=f"{project['name']}_كشف_الإكسسوار.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_props_sheet_{project_id}",
            )
        st.download_button(
            t("⬇️ كشف الملابس"),
            data=_lazy(build_wardrobe_sheet_excel),
            file_name=f"{project['name']}_كشف_الملابس.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"dl_wardrobe_sheet_{project_id}",
        )
        st.divider()

    if _loc_count == 0 or _char_count == 0:
        st.info(t("👉 الخطوة الجاية: روح تبويب **الأماكن** و**الشخصيات** وضيف الأماكن والشخصيات الأساسية في مشروعك."))
    elif _scene_count == 0:
        st.info(t("👉 الخطوة الجاية: روح تبويب **السكريبت (المشاهد)** وضيف مشاهد مشروعك (أو استوردها من ملف في تبويب استيراد السكريبت)."))
    elif _shot_count == 0:
        st.info(t("👉 الخطوة الجاية: روح تبويب **التفريغ (اللقطات)** وابدأ تفرّغ كل مشهد للقطات كاميرا تفصيلية."))

    all_shots = repo.shot_summaries_of_project(project_id)
    if not all_shots:
        st.caption(t("لسه مفيش لقطات مضافة"))
    else:
        total = len(all_shots)
        confirmed = sum(1 for s in all_shots if s["confirmed"])
        st.metric(t("نسبة اللقطات الجاهزة للتوليد"), f"{confirmed} / {total}")
        st.progress(confirmed / total if total else 0)

        if total and confirmed == total:
            st.success(t(
                "🎉 كل اللقطات اتراجعت وأتأكد منها. بيانات مشروعك دلوقتي متكاملة وجاهزة كمرجع كامل للإنتاج. "
                "البرنامج الحالي بيوقف هنا — التوليد الفعلي بالذكاء الاصطناعي مش متاح جوه البرنامج ده لسه، "
                "ومحتاج تطوير إضافي يربطه بأدوات التوليد."
            ))
        else:
            st.caption(t("👉 راجع اللقطات اللي لسه مش متأكد منها (🟡) من تبويب التفريغ، وعلّم 'تمت المراجعة' لما تخلص كل واحدة."))

        for s in all_shots:
            icon = "🔵" if s["confirmed"] else f"🟡 {t('محتاجة مراجعة')}"
            st.write(f"{t('مشهد')} {ltr(scene_label(s))} / {t('لقطة')} {s['shot_number']} — {ltr(t(s['shot_size']))} — {icon}")
