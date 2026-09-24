"""لينك الدعوة لفريق مشروع (?invite=) — المالك 2026-09-24.

اللي بيفتح اللينك: لو داخل بالفعل بيدخل فريق المشروع على طول
(accept_from_link). لو لأ، شاشة الدخول بتقوله مين داعيه ولأنهي مشروع،
ويختار: حساب جديد (فورم قصير) أو يدخل بحسابه - وفي الحالتين المشروع
بيتفتحله. التوكن بيتشال من العنوان بعد ما يتستخدم.
"""

import streamlit as st

import accounts
from i18n import t


def login_panel(finish_login):
    """شاشة الدخول للي فاتح لينك دعوة. بترجّع True لو رسمت فورم الحساب الجديد
    (ساعتها فورم الدخول العادي مابيترسمش)."""
    token = st.query_params.get("invite")
    if not token:
        return False
    inv = accounts.invite_info(token)
    if not inv:
        st.warning("لينك الدعوة ده مابقاش صالح (اتستخدم أو انتهى أو اتلغى) — اطلب لينك جديد من مدير المشروع. / "
                   "This invite link is no longer valid — ask the project manager for a new one.")
        return False
    st.info(f"📩 **{inv['inviter']}** بيدعوك لفريق عمل مشروع **«{inv['project_name']}»** — {inv['job_title']}")
    mode = st.segmented_control("", ["new", "login"], default="new", key="_invite_mode", required=True,
                                label_visibility="collapsed",
                                format_func=lambda m: "✨ حساب جديد / New account" if m == "new"
                                else "🔑 عندي حساب / I have an account")
    if mode != "new":
        return False
    with st.form("_invite_register"):
        display = st.text_input("اسمك / Your name", value=inv["invitee_name"] or "")
        uname = st.text_input("اسم الدخول (إنجليزي) / Username", key="_login_username",
                              placeholder="ahmed.samir")
        pw = st.text_input("كلمة السر (10 حروف على الأقل) / Password", type="password", key="_login_password")
        pw2 = st.text_input("أكّد كلمة السر / Repeat password", type="password")
        go = st.form_submit_button("إنشاء الحساب والدخول للمشروع / Create account & join",
                                   use_container_width=True, type="primary")
    if go:
        if pw != pw2:
            st.error("كلمتين السر مش زي بعض / Passwords don't match")
        else:
            try:
                name = accounts.register_from_invite(token, uname, display, pw)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["_link_project_id"] = inv["project_id"]
                del st.query_params["invite"]
                finish_login(name)
    return True




def accept_from_link(current_user):
    token = st.query_params.get("invite")
    if not token or not current_user:
        return
    del st.query_params["invite"]
    joined = accounts.accept_invite(token, current_user)
    if joined:
        st.session_state["_link_project_id"] = joined
        st.toast(t("انضميت لفريق العمل — المشروع اتفتح"), icon="👥")
    else:
        st.toast(t("لينك الدعوة ده مابقاش صالح — اطلب لينك جديد من مدير المشروع."), icon="⚠️")
