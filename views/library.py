"""شاشة مكتبة التحليلات (‎?page=library‎) — على مستوى الحساب، بره أي مشروع.

المنطق كله في analysis_library.py؛ هنا العرض بس: بحث، وكارت لكل تحليل عليه
أربع حاجات — استورد في مشروع، تقرير البناء الدرامي، نزّل الملف، احذف (بتأكيد).
"""

import html
import logging
import uuid

import streamlit as st

import analysis_library as lib
import links
import permissions
from i18n import t
from ui import feature_on, ltr
from views import dramaturgy_panel

_log = logging.getLogger("cimafast.library")

_CSS = """
<style>
/* الشاشة كلها عربي أولًا: الكروت والأسماء والأرقام بتتبع اتجاه اللغة. */
.st-key-cf_library { direction: var(--cf-lib-dir, rtl); }
.cf-lib-title { font-weight: 700; font-size: 1.05rem; margin: 0 0 2px 0;
                overflow-wrap: anywhere; }
.cf-lib-meta { opacity: 0.75; font-size: 0.88rem; line-height: 1.6; overflow-wrap: anywhere; }
.cf-lib-counts { font-size: 0.92rem; margin-top: 2px; }
.cf-lib-badge { display: inline-block; font-size: 0.78rem; padding: 1px 8px; border-radius: 999px;
                border: 1px solid rgba(254, 202, 5, 0.45); margin-inline-start: 6px; }
</style>
"""


def _user_error(exc, where):
    """نفس قاعدة تبويب الإضافة: رسالتنا العربي تعدّي، أي حاجة تانية تروح اللوج بكود."""
    if isinstance(exc, (lib.LibraryError, permissions.Denied)):
        return t(str(exc))
    ref = uuid.uuid4().hex[:8]
    _log.exception("[%s] library %s failed: %s", ref, where, exc)
    return f"⚠️ {t('حصلت مشكلة عندنا مش في ملفك. جرّب تاني، ولو فضلت ابعت الكود ده للدعم')}: `{ref}`"


def _when(value):
    return ltr((value or "")[:16].replace("T", " ")) if value else "—"


def _upload(current_user, company_id, can_edit):
    with st.expander(t("⬆️ ارفع ملف تحليل من CimaFast")):
        if not can_edit:
            st.info(t("حسابك مشاهدة فقط — تقدر تتصفح وتنزّل التحليلات، بس مش تضيف."))
            return
        st.caption(t("ملف اتنزّل من مكتبة CimaFast (من حسابك أو من حساب تاني) — بيتضاف لمكتبتك في مساحة العمل دي.")
                   + " " + ltr(lib.FILE_SUFFIX))
        up = st.file_uploader(t("اختار الملف"), type=["json"], key="lib_upload")
        if up is not None and st.button(t("➕ ضيفه للمكتبة"), key="lib_upload_go", use_container_width=True):
            try:
                _, created = lib.add_upload(current_user, company_id, up.getvalue())
                st.session_state["_lib_flash"] = ("success", t("اتضاف للمكتبة.") if created
                                                  else t("التحليل ده موجود في المكتبة بالفعل."))
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(_user_error(exc, "upload"))


def _import_panel(current_user, row):
    eid = row["id"]
    targets = lib.importable_projects(current_user)
    if not targets:
        st.info(t("مفيش مشروع تقدر تستورد فيه. محتاج دور تعديل في مشروع (مش مشاهدة فقط)."))
        return
    by_id = {p["id"]: p for p in targets}
    many_companies = len({p["company"] for p in targets}) > 1
    pid = st.selectbox(
        t("المشروع اللي هيتستورد فيه"), list(by_id), key=f"lib_target_{eid}",
        format_func=lambda i: by_id[i]["name"] + (f" — {by_id[i]['company']}" if many_companies else ""))
    try:
        probe = lib.plan_import(current_user, eid, pid, lib.MODE_MERGE)
    except Exception as exc:  # noqa: BLE001
        st.error(_user_error(exc, "plan"))
        return
    if probe["project_has_data"]:
        choice = st.radio(
            t("المشروع فيه بيانات بالفعل. تحب:"),
            [lib.MODE_MERGE, lib.MODE_NEW], key=f"lib_mode_{eid}",
            format_func=lambda m: t("🔗 دمج مع الموجود (الشخصيات والأماكن المتشابهة تتربط بالموجود)")
            if m == lib.MODE_MERGE else t("🆕 بيانات جديدة (من غير مطابقة مع الموجود)"))
    else:
        choice = lib.MODE_NEW
        st.caption(t("المشروع فاضي — التحليل هيتضاف زي ما هو."))
    plan = probe if choice == lib.MODE_MERGE else lib.plan_import(current_user, eid, pid, choice)

    lines = [f"- {t('مشاهد جديدة')}: **{ltr(plan['new_scene_count'])}**"]
    if plan["skipped_scenes"]:
        lines.append(f"- {t('مشاهد أرقامها موجودة في المشروع وهتتخطى')}: "
                     f"{ltr('، '.join(plan['skipped_scenes'][:30]))}"
                     + (" …" if len(plan["skipped_scenes"]) > 30 else ""))
    lines.append(f"- {t('شخصيات جديدة')}: **{ltr(len(plan['new_characters']))}** · "
                 f"{t('أماكن جديدة')}: **{ltr(len(plan['new_locations']))}**")
    if plan["existing_characters"] or plan["existing_locations"]:
        lines.append(f"- {t('موجودين بنفس الاسم وهيتربطوا بيهم')}: "
                     f"{ltr(len(plan['existing_characters']))} {t('شخصية')} · "
                     f"{ltr(len(plan['existing_locations']))} {t('مكان')}")
    st.markdown("\n".join(lines))

    accepted_c, accepted_l = [], []
    if choice == lib.MODE_MERGE and (plan["char_matches"] or plan["loc_matches"]):
        st.markdown(f"**{t('هيتدمجوا مع الموجود — شيل علامة أي واحد مش هو هو:')}**")
        for i, (a, b, strong) in enumerate(plan["char_matches"]):
            if st.checkbox(f"🎭 «{a}» {t('هو نفسه')} «{b}»", value=True, key=f"lib_cm_{eid}_{pid}_{i}"):
                accepted_c.append((a, b, strong))
        for i, (a, b, strong) in enumerate(plan["loc_matches"]):
            label = (f"📍 «{a}» {t('هو نفسه')} «{b}»" if strong
                     else f"📍 «{a}» {t('حالة تانية من')} «{b}»")
            if st.checkbox(label, value=True, key=f"lib_lm_{eid}_{pid}_{i}"):
                accepted_l.append((a, b, strong))

    if st.button(t("📥 استورد في المشروع ده"), key=f"lib_go_{eid}", use_container_width=True,
                 type="primary", disabled=plan["new_scene_count"] == 0):
        try:
            summary = lib.import_into_project(current_user, eid, pid, choice, accepted_c, accepted_l)
        except Exception as exc:  # noqa: BLE001
            st.error(_user_error(exc, "import"))
            return
        msg = (f"{t('تم إضافة')} {ltr(summary['scenes_added'])} {t('مشهد جديد.')} "
               f"{t('شخصيات جديدة:')} {ltr(len(summary['characters_added']))} · "
               f"{t('أماكن جديدة:')} {ltr(len(summary['locations_added']))}")
        if summary["characters_merged"] or summary["locations_merged"]:
            msg += (f" · {t('اتدمج مع الموجود')}: {ltr(len(summary['characters_merged']))} "
                    f"{t('شخصية')}، {ltr(len(summary['locations_merged']))} {t('مكان')}")
        st.session_state["_lib_flash"] = ("success", msg)
        st.session_state["_lib_opened_project"] = (pid, by_id[pid]["name"])
        st.session_state.pop("_lib_open", None)
        st.rerun()
    if plan["new_scene_count"] == 0:
        st.caption(t("كل مشاهد التحليل ده موجودة في المشروع بالفعل — مفيش حاجة جديدة تتستورد."))


def _entry_card(current_user, row, can_import):
    eid = row["id"]
    with st.container(border=True, key=f"cf_lib_entry_{eid}"):
        badge = t("ملف مرفوع") if row["origin"] == "upload" else t("ذكاء اصطناعي")
        st.markdown(
            f'<div class="cf-lib-title">📄 <bdi>{html.escape(row["script_name"])}</bdi>'
            f'<span class="cf-lib-badge">{html.escape(badge)}</span></div>'
            f'<div class="cf-lib-meta">{html.escape(t("اتحلل"))} {_when(row["analysed_at"])}'
            f' · {html.escape(t("بواسطة"))} {html.escape(row["owner_username"] or "—")}'
            f' · {html.escape(t("من مشروع"))} «<bdi>{html.escape(row["source_project_name"] or "—")}</bdi>»</div>'
            f'<div class="cf-lib-counts">{ltr(row["scene_count"])} {html.escape(t("مشهد"))} · '
            f'{ltr(row["character_count"])} {html.escape(t("شخصية"))} · '
            f'{ltr(row["location_count"])} {html.escape(t("مكان"))}</div>',
            unsafe_allow_html=True)

        # زرار التقرير بس على النسخة اللي ليها worker للتقرير (/v1 دلوقتي)
        if dramaturgy_panel.jobs.available():
            c_imp, c_drama, c_dl, c_del = st.columns(4)
        else:
            (c_imp, c_dl, c_del), c_drama = st.columns(3), None
        with c_imp:
            if st.button(t("📥 استورد في مشروع"), key=f"lib_imp_{eid}", use_container_width=True,
                         disabled=not can_import,
                         help=None if can_import else t("حسابك مشاهدة فقط — مينفعش تستورد في مشروع.")):
                st.session_state["_lib_open"] = None if st.session_state.get("_lib_open") == eid else eid
                st.session_state.pop("_lib_confirm_delete", None)
                st.session_state.pop("_lib_drama", None)
        if c_drama is not None:
            with c_drama:
                # مفيش علامة "فيه تقرير" في الكارت نفسه: ده محتاج نفك JSON كل صف في
                # اللستة، واللستة معمولة من الأعمدة الخفيفة بس (_LIST_COLS). التقرير
                # بيتقري لما اللوحة تتفتح.
                if st.button(t("🎭 البناء الدرامي"), key=f"lib_drama_{eid}", use_container_width=True):
                    st.session_state["_lib_drama"] = None if st.session_state.get("_lib_drama") == eid else eid
                    st.session_state.pop("_lib_open", None)
                    st.session_state.pop("_lib_confirm_delete", None)
        with c_dl:
            st.download_button(
                t("⬇️ نزّل ملف"), data=lambda: lib.to_file(lib.get(current_user, eid),
                                                         exported_by=current_user)[1],
                file_name=lib.file_name(row), mime="application/json", key=f"lib_dl_{eid}",
                disabled=not feature_on("exports"),
                use_container_width=True, on_click="ignore")
        with c_del:
            if st.button(t("🗑️ احذف"), key=f"lib_del_{eid}", use_container_width=True,
                         disabled=not lib.can_delete(current_user, row)):
                st.session_state["_lib_confirm_delete"] = eid
                st.session_state.pop("_lib_open", None)
                st.session_state.pop("_lib_drama", None)

        if st.session_state.get("_lib_confirm_delete") == eid:
            st.warning(t("متأكد إنك عايز تحذف التحليل ده من المكتبة؟ المشاريع اللي اتستورد فيها "
                         "مش هتتأثر، بس الملف نفسه هيروح. نزّله الأول لو ممكن تحتاجه."))
            c_yes, c_no = st.columns(2)
            with c_yes:
                if st.button(t("أيوه، احذفه"), key=f"lib_del_yes_{eid}", use_container_width=True,
                             type="primary"):
                    try:
                        lib.delete(current_user, eid)
                        st.session_state["_lib_flash"] = ("success", t("اتحذف من المكتبة."))
                    except Exception as exc:  # noqa: BLE001
                        st.session_state["_lib_flash"] = ("error", _user_error(exc, "delete"))
                    st.session_state.pop("_lib_confirm_delete", None)
                    st.rerun()
            with c_no:
                if st.button(t("لأ، سيبه"), key=f"lib_del_no_{eid}", use_container_width=True):
                    st.session_state.pop("_lib_confirm_delete", None)
                    st.rerun()

        if st.session_state.get("_lib_open") == eid:
            _import_panel(current_user, row)
        if c_drama is not None and st.session_state.get("_lib_drama") == eid:
            dramaturgy_panel.render(current_user, eid, key=f"lib_{eid}")


def render(current_user, company_id, role, is_ar=True):
    st.markdown(_CSS.replace("var(--cf-lib-dir, rtl)", "rtl" if is_ar else "ltr"),
                unsafe_allow_html=True)
    can_edit = permissions.can(role, "edit")
    # الحفظ التلقائي: أي تحليل خلص ومش في المكتبة لسه (حتى لو اللي شغّله قفل الصفحة)
    lib.sync_from_spool()

    with st.container(key="cf_library"):
        st.subheader(t("📚 مكتبة التحليلات"))
        st.caption(t("كل سيناريو بيتحلل بالذكاء الاصطناعي بيتحفظ هنا لوحده، على حسابك وبره أي مشروع. "
                     "لو استوردته في المشروع الغلط، استورده من هنا في المشروع الصح — أو ادمجه مع "
                     "مشروع فيه بيانات، والشخصيات والأماكن المتشابهة بتتربط بالموجود بدل ما تتكرر."))

        flash = st.session_state.pop("_lib_flash", None)
        if flash:
            (st.success if flash[0] == "success" else st.error)(flash[1])
        opened = st.session_state.pop("_lib_opened_project", None)
        if opened:
            st.markdown(
                f'<a class="cf-navlink" href="{html.escape(links.screen("./", opened[0], "scenes"), quote=True)}"'
                f' target="_self">🎬 {html.escape(t("افتح المشروع"))} «{html.escape(opened[1])}»</a>',
                unsafe_allow_html=True)

        _upload(current_user, company_id, can_edit)

        query = st.text_input(t("🔍 دوّر باسم السيناريو أو المشروع أو اللي حلّله"),
                              key="lib_search", placeholder=t("مثال: الحلقة الاولى"))
        rows = lib.list_for(current_user, query)
        total = lib.count_for(current_user)
        if not total:
            st.info(t("المكتبة فاضية لسه. أول ما تحلل سيناريو بالذكاء الاصطناعي في أي مشروع، "
                      "التحليل هيتحفظ هنا لوحده."))
            return
        st.caption(f"{ltr(len(rows))} {t('من')} {ltr(total)} {t('تحليل')}")
        if not rows:
            st.info(t("مفيش تحليل بالاسم ده."))
        # الاستيراد بدور المستخدم في شركة المشروع نفسه، مش الشركة المفتوحة دلوقتي
        can_import = bool(lib.importable_projects(current_user))
        for row in rows:
            _entry_card(current_user, row, can_import)
