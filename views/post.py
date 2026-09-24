"""تبويب «🎞️ ما بعد الإنتاج» (بند PP1، طلب المالك 2026-09-24).

كارت لكل قسم (مونتاج، مؤثرات، تلوين، موسيقى، صوت، ميكساج، تترات وماستر):
الحالة، نسبة الإنجاز، الاستوديو أو الفريلانسر اللي شغّال عليه وإزاي نوصله،
لينكين معاينة (فيميو/درايف... إحنا مابنرفعش ملفات)، ميعاد التسليم،
وتعليقات الفريق. شريط التقدّم فوق بياخد المتوسط من هنا.
"""

import datetime as dt
import html

import streamlit as st

import audit
import post_production as pp
import repo
from database import fetch_all
from export import build_post_report_excel
from i18n import t
from ui import ltr
from views.looks import can_edit


def _title(item):
    row = item["row"]
    _k, icon, label = pp.status(row.get("status"))
    stale = f" · ⚠️ {t('ماتحدّثش من أسبوع')}" if item["stale"] else ""
    return f"{item['icon']} {t(item['name'])} — {icon} {t(label)} · {ltr(item['progress'])}%{stale}"


def _form(project_id, item, current_user, editable):
    row, key = item["row"], item["key"]
    with st.form(f"post_form_{key}", border=False):
        c1, c2 = st.columns(2)
        status = c1.selectbox(t("الحالة"), pp.STATUS_KEYS, index=pp.STATUS_KEYS.index(row.get("status") or "not_started"),
                              format_func=lambda k: f"{pp.status(k)[1]} {t(pp.status(k)[2])}", disabled=not editable)
        progress = c2.slider(t("نسبة الإنجاز"), 0, 100, int(row.get("progress") or 0), step=5, disabled=not editable,
                             help=t("«معتمد» بيتحسب 100% و«لم يبدأ» 0% مهما كانت النسبة هنا."))
        c1, c2, c3 = st.columns(3)
        vendor = c1.text_input(t("الاستوديو / المسؤول"), row.get("vendor_name") or "", disabled=not editable)
        contact = c2.text_input(t("التواصل (تليفون / إيميل)"), row.get("vendor_contact") or "", disabled=not editable)
        location = c3.text_input(t("المكان"), row.get("vendor_location") or "", disabled=not editable)
        c1, c2, c3 = st.columns(3)
        url1 = c1.text_input(t("لينك معاينة"), row.get("preview_url") or "", disabled=not editable,
                             placeholder="https://vimeo.com/…")
        url2 = c2.text_input(t("لينك معاينة تاني"), row.get("preview_url2") or "", disabled=not editable)
        try:
            due_value = dt.date.fromisoformat(row.get("due_date") or "")
        except ValueError:
            due_value = None
        due = c3.date_input(t("ميعاد التسليم"), value=due_value, disabled=not editable)
        notes = st.text_area(t("ملاحظات"), row.get("notes") or "", height=80, disabled=not editable)
        if st.form_submit_button(f"💾 {t('حفظ')}", disabled=not editable, type="primary"):
            repo.save_post_department(
                project_id, key, updated_by=current_user, status=status, progress=progress,
                vendor_name=vendor.strip(), vendor_contact=contact.strip(), vendor_location=location.strip(),
                preview_url=url1.strip(), preview_url2=url2.strip(),
                due_date=due.isoformat() if due else None, notes=notes.strip())
            st.toast(f"✅ {t('اتحفظ')}")
            st.rerun()


def _links(row):
    urls = [u for u in (row.get("preview_url"), row.get("preview_url2")) if u]
    if urls:
        cols = st.columns(len(urls) + 2)
        for col, (n, u) in zip(cols, enumerate(urls, start=1)):
            # برّه البرنامج (فيميو/درايف) - تاب جديد مقبول هنا
            col.link_button(f"▶️ {t('معاينة')} {ltr(n)}", u)


def _comments(project_id, key, current_user, editable):
    st.markdown(f"**💬 {t('تعليقات')}**")
    for c in repo.post_comments(project_id, key):
        st.markdown(f"<div dir='auto' style='text-align:start'><strong>{html.escape(c['author'] or '—')}</strong> · "
                    f"<span style='opacity:.6'>{(c['created_at'] or '')[:16].replace('T', ' ')}</span><br>"
                    f"{html.escape(c['body'])}</div>", unsafe_allow_html=True)
    if editable:
        with st.form(f"post_comment_{key}", clear_on_submit=True, border=False):
            body = st.text_input(t("تعليق جديد"), label_visibility="collapsed", placeholder=t("اكتب تعليق…"))
            if st.form_submit_button(t("إضافة تعليق")) and body.strip():
                repo.add_post_comment(project_id, key, current_user, body)
                st.rerun()


def render(project, project_id, current_user):
    st.subheader(f"🎞️ {t('ما بعد الإنتاج')}")
    s = pp.summary(repo.post_departments(project_id))
    c1, c2, c3 = st.columns(3)
    c1.metric(t("الإنجاز الكلي"), f"{ltr(s['overall'])}%")
    c2.metric(t("أقسام معتمدة"), f"{ltr(s['approved'])} {t('من')} {ltr(s['total'])}")
    c3.metric(t("ماتحدّثتش من أسبوع"), ltr(sum(1 for i in s["items"] if i["stale"])))

    who, co = st.session_state.get("_auth_user"), st.session_state.get("_cf_company")

    def _report():
        audit.event("export", target="post_report_excel", username=who, company_id=co, project_id=project_id)
        return build_post_report_excel(project, project_id, fetch_all)

    st.download_button(f"📊 {t('تقرير ما بعد الإنتاج (Excel)')}", data=_report,
                       file_name=f"{project['name']}_ما_بعد_الإنتاج.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       key=f"dl_post_{project_id}")

    editable = can_edit()
    for item in s["items"]:
        _lazy_exp = st.expander(_title(item), key=f"exp_post_{item['key']}", on_change="rerun")
        if _lazy_exp.open:
            with _lazy_exp:
                st.progress(item["progress"] / 100)
                _links(item["row"])
                _form(project_id, item, current_user, editable)
                _comments(project_id, item["key"], current_user, editable)
