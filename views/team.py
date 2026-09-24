"""👥 فريق العمل — فريق المشروع (المالك 2026-09-24).

"لما أكون واقف على المشروع يبقى فيه زرار اسمه فريق العمل، لما أخش عليه أشوف
مين فريق العمل وأدوارهم وبيشتغلوا إيه من شغلانات رؤساء الأقسام." اللي أنشأ
المشروع هو مدير المشروع، وهو بس اللي بيضيف ويشيل. الإضافة: حد عنده حساب
(باسم دخوله) بيتضاف على طول، وحد جديد بياخد لينك دعوة (نسخ أو واتساب) -
بيفتحه، يعمل حساب أو يدخل، ويلاقي المشروع قدامه. "مساحة العمل" مابتظهرش.
"""

import os
from urllib.parse import quote

import pandas as pd
import streamlit as st

import accounts
from i18n import t
from ui import ltr


def _app_url():
    """عنوان البرنامج اللي هيتحط في لينك الدعوة (نفس اللي اليوزر فاتحه)."""
    explicit = os.environ.get("CIMAFAST_APP_URL")
    if explicit:
        return explicit.rstrip("/") + "/"
    headers = getattr(st.context, "headers", {}) or {}
    host = headers.get("X-Forwarded-Host") or headers.get("Host") or "cimafast.io"
    scheme = headers.get("X-Forwarded-Proto") or ("http" if host.startswith(("127.", "localhost")) else "https")
    base = (os.environ.get("STREAMLIT_SERVER_BASE_URL_PATH") or "").strip("/")
    return f"{scheme}://{host}/" + (f"{base}/" if base else "")


def render(project, project_id, current_user):
    st.subheader(f"👥 {t('فريق العمل')} — {project['name']}")
    team = accounts.project_team_view(current_user, project_id)
    people = team["people"]
    st.caption(f"{ltr(len(people))} {t('في الفريق')} · {t('اللي أنشأ المشروع هو مدير المشروع.')}")

    for p in people:
        _person(project_id, current_user, p, team["can_manage"])

    if not team["can_manage"]:
        st.caption(t("إضافة حد للفريق أو تغيير الأدوار من مدير المشروع."))
        return
    ctx = accounts.project_context(current_user, project_id)
    if not accounts.TIER_ALLOWS_TEAM.get(ctx["tier"], True):
        st.info(t("فريق العمل متاح في باقة Studio أو Enterprise — رقّي الاشتراك عشان تضيف فريق للمشروع."))
        return
    st.divider()
    _add_form(project, project_id, current_user)
    if team["invites"]:
        st.divider()
        st.markdown(f"**✉️ {t('دعوات لسه ماتقبلتش')}**")
        for inv in team["invites"]:
            c1, c2 = st.columns([5, 1], vertical_alignment="center")
            who = inv["invitee_name"] or inv["contact"] or "—"
            c1.markdown(f"{who} · {t(inv['job_title'])} · {t(accounts.PERMISSIONS[inv['permission']])}"
                        f" <span style='opacity:.6'>({t('لحد')} {inv['expires_at'][:10]})</span>",
                        unsafe_allow_html=True)
            if c2.button(t("إلغاء"), key=f"inv_revoke_{inv['id']}", use_container_width=True):
                accounts.revoke_invite(current_user, project_id, inv["id"])
                st.rerun()
    link = st.session_state.get(f"_invite_link_{project_id}")
    if link:
        _show_link(project, link)


def _person(project_id, current_user, p, can_manage):
    initials = "".join(w[0] for w in (p["display_name"] or "?").split()[:2]).upper() or "?"
    with st.container(border=True, key=f"team_{project_id}_{p['username']}"):
        c1, c2 = st.columns([1, 6], vertical_alignment="center")
        # نفس دايرة الأحرف الأولى بتاعة الشريط الجانبي (ستايلها هناك مقصور عليه)
        c1.markdown(f'<div style="width:40px;height:40px;border-radius:50%;background:var(--cf-yellow);'
                    f'color:var(--cf-ink);display:flex;align-items:center;justify-content:center;'
                    f'font-weight:800;margin:auto">{initials}</div>', unsafe_allow_html=True)
        badge = "⭐ " if p["is_manager"] else ""
        perm = "" if p["is_manager"] else f" · {t(accounts.PERMISSIONS.get(p['permission'], p['permission']))}"
        c2.markdown(f"**{badge}{p['display_name']}** <span style='opacity:.6'>@{p['username']}</span>  \n"
                    f"{t(p['job'])}{perm}", unsafe_allow_html=True)
        if can_manage and not p["is_manager"]:
            with st.popover(f"✏️ {t('تعديل')}"):
                job = st.selectbox(t("الشغلانة في المشروع"), accounts.PROJECT_JOBS, format_func=t,
                                   index=accounts.PROJECT_JOBS.index(p["job"]) if p["job"] in accounts.PROJECT_JOBS
                                   else len(accounts.PROJECT_JOBS) - 1, key=f"tj_{project_id}_{p['username']}")
                perm_key = st.radio(t("الصلاحية"), list(accounts.PERMISSIONS), horizontal=True,
                                    format_func=lambda k: t(accounts.PERMISSIONS[k]),
                                    index=list(accounts.PERMISSIONS).index(p["permission"])
                                    if p["permission"] in accounts.PERMISSIONS else 0,
                                    key=f"tp_{project_id}_{p['username']}")
                b1, b2 = st.columns(2)
                if b1.button(f"💾 {t('حفظ')}", key=f"ts_{project_id}_{p['username']}", use_container_width=True):
                    accounts.update_project_member(current_user, project_id, p["username"], job, perm_key)
                    st.rerun()
                if b2.button(f"🗑️ {t('شيل من الفريق')}", key=f"tr_{project_id}_{p['username']}",
                             use_container_width=True):
                    accounts.remove_from_project(current_user, project_id, p["username"])
                    st.rerun()


def _add_form(project, project_id, current_user):
    st.markdown(f"**➕ {t('أضف حد لفريق العمل')}**")
    with st.form(f"team_add_{project_id}", clear_on_submit=True):
        c1, c2 = st.columns(2)
        name = c1.text_input(t("الاسم"), placeholder=t("مثال: أحمد سمير"))
        who = c2.text_input(t("اسم الدخول لو عنده حساب — أو موبايله/إيميله"),
                            placeholder="ahmed.dop / 01xxxxxxxxx")
        c3, c4 = st.columns(2)
        job = c3.selectbox(t("الشغلانة في المشروع"), accounts.PROJECT_JOBS, format_func=t, index=None,
                           placeholder=t("اختار الشغلانة"))
        perm = c4.radio(t("الصلاحية"), list(accounts.PERMISSIONS), horizontal=True,
                        format_func=lambda k: t(accounts.PERMISSIONS[k]))
        st.caption(t("لو كتبت اسم دخول حد عنده حساب بيتضاف على طول. غير كده بيتعمل لينك دعوة تبعته له "
                     "(واتساب أو نسخ) — بيفتحه ويعمل حسابه ويلاقي المشروع."))
        submitted = st.form_submit_button(f"➕ {t('أضف')}", type="primary")
    if not submitted:
        return
    if not job:
        st.warning(t("اختار الشغلانة في المشروع"))
        return
    who = (who or "").strip()
    if who and accounts.user(who):
        try:
            accounts.add_to_project(current_user, project_id, who, job, perm)
            st.toast(f"{t('اتضاف للفريق')}: {who}", icon="👥")
            st.rerun()
        except (ValueError, accounts.AccessDenied) as exc:
            st.error(t(str(exc)))
        return
    if not (name or "").strip() and not who:
        st.warning(t("اكتب اسمه أو رقمه عشان تعرف الدعوة دي لمين"))
        return
    token = accounts.create_invite(current_user, project_id, name, who, job, perm)
    st.session_state[f"_invite_link_{project_id}"] = f"{_app_url()}?invite={token}"
    st.rerun()


def _show_link(project, link):
    st.success(t("لينك الدعوة جاهز — ابعته للشخص ده. بيشتغل مرة واحدة ولمدة 7 أيام."))
    st.code(link, language=None)
    msg = f"{t('انت مدعو لفريق عمل مشروع')} «{project['name']}» {t('على CimaFast Studio')}: {link}"
    st.markdown(f'<a class="cf-navlink" href="https://wa.me/?text={quote(msg)}" target="_blank" '
                f'rel="noopener">🟢 {t("ابعته واتساب")}</a>', unsafe_allow_html=True)
