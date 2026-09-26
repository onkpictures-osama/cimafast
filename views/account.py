"""👤 حسابي — صفحة من الشريط الجانبي (المالك 2026-09-26).

- أي حد: يغيّر كلمة السر بتاعته.
- المشغّل (osama، melzayat): "وسيلة سلسة أطلّع بيها يوزر نيم وباسوورد أديه
  لشخص، والشخص ده بعد كده يقدر يغيّر الباسوورد". الحساب الجديد بكلمة سر مؤقتة
  بتظهر مرة واحدة، ومعاها رسالة جاهزة للنسخ أو واتساب؛ وأول ما يدخل البرنامج
  بيطلب منه يغيّرها. وقايمة بالحسابات اللي عملها وحالة كل واحد، مع كلمة سر
  مؤقتة جديدة لو حد نسي.
"""

from urllib.parse import quote

import streamlit as st

import accounts
from auth import normalize_username
from i18n import t
from ui import close_page, ltr
from views.team import _app_url

_SHOWN = "_acc_credentials"          # آخر كلمة سر اتطلعت — بتتمسح لما يدوس «تمام»


def _password_form(username):
    st.markdown(f"#### 🔑 {t('غيّر كلمة السر')}")
    with st.form("acc_change_pw", clear_on_submit=True):
        old = st.text_input(t("كلمة السر الحالية"), type="password")
        new = st.text_input(t("كلمة السر الجديدة (١٠ حروف على الأقل)"), type="password")
        again = st.text_input(t("أعد كتابتها"), type="password")
        if st.form_submit_button(t("حفظ كلمة السر"), type="primary"):
            if new != again:
                st.error(t("الكلمتين مش زي بعض"))
            else:
                try:
                    accounts.change_own_password(username, old, new)
                    st.success(f"✅ {t('اتغيّرت كلمة السر')}")
                except (ValueError, accounts.AccessDenied) as exc:
                    st.error(t(str(exc)))


def _message(name, username, password, url):
    return (f"{t('أهلًا')} {name}،\n"
            f"{t('ده حسابك على سيما فاست ستوديو:')}\n"
            f"{t('الرابط')}: {url.rstrip('/')}\n"
            f"{t('اسم الدخول')}: {username}\n"
            f"{t('كلمة السر المؤقتة')}: {password}\n"
            f"{t('أول ما تدخل البرنامج هيطلب منك تختار كلمة سر جديدة.')}")


def _credentials_card():
    shown = st.session_state.get(_SHOWN)
    if not shown:
        return
    with st.container(border=True):
        st.markdown(f"#### ✅ {t('الحساب جاهز')} — {shown['name']}" if shown["new"]
                    else f"#### 🔄 {t('كلمة سر مؤقتة جديدة')} — {shown['name']}")
        c1, c2 = st.columns(2)
        c1.caption(t("اسم الدخول"))
        c1.code(shown["username"], language=None)
        c2.caption(t("كلمة السر المؤقتة"))
        c2.code(shown["password"], language=None)
        st.caption(f"⚠️ {t('كلمة السر دي بتظهر هنا مرة واحدة بس. أول ما يدخل هيطلب منه يغيّرها بكلمة سر من اختياره.')}")
        text = _message(shown["name"], shown["username"], shown["password"], shown["url"])
        st.caption(t("رسالة جاهزة — انسخها (زرار النسخ فوق الرسالة على الشمال) أو ابعتها واتساب:"))
        # st.code بيكتب من الشمال لليمين؛ كل سطر ياخد اتجاه أول حرف فيه عشان العربي يتقري صح
        st.markdown("<style>.st-key-acc_msg pre, .st-key-acc_msg code { direction: rtl; unicode-bidi: plaintext;"
                    " text-align: start; white-space: pre-wrap; font-family: inherit; }</style>",
                    unsafe_allow_html=True)
        with st.container(key="acc_msg"):
            st.code(text, language=None)
        b1, b2 = st.columns(2)
        # واتساب برّه البرنامج - تاب جديد مقبول هنا
        b1.link_button(f"🟢 {t('ابعت على واتساب')}", f"https://wa.me/?text={quote(text)}", use_container_width=True)
        if b2.button(f"👌 {t('تمام، خلّصت')}", key="acc_done", use_container_width=True):
            st.session_state.pop(_SHOWN, None)
            st.rerun()


def _create_form(actor):
    st.markdown(f"#### 👤 {t('اعمل حساب لحد')}")
    # بعد ما الحساب يتعمل الفورم بياخد اسم جديد فيرجع فاضي؛ لو فيه خطأ بيفضل
    # زي ما هو عشان مايكتبش تاني
    n = st.session_state.get("_acc_form_n", 0)
    with st.form(f"acc_create_{n}", clear_on_submit=False):
        c1, c2 = st.columns(2)
        name = c1.text_input(t("اسمه"), placeholder=t("مثال: كريم محمود"))
        username = c2.text_input(t("اسم الدخول (إنجليزي)"), placeholder="karim.m",
                                 help=t("حروف إنجليزي صغيرة وأرقام و . _ - بس. هو اللي هيكتبه وهو بيدخل."))
        tier = st.radio(t("الباقة"), accounts.TIERS, index=accounts.TIERS.index("studio"), horizontal=True,
                        format_func=lambda k: accounts.TIER_LABELS[k])
        if st.form_submit_button(f"➕ {t('اعمل الحساب وطلّع كلمة السر')}", type="primary"):
            try:
                _cid, password = accounts.create_account(actor, name, username, tier)
            except (ValueError, accounts.AccessDenied) as exc:
                st.error(t(str(exc)))
            else:
                login = normalize_username(username)
                st.session_state[_SHOWN] = {"name": (name or "").strip() or login, "username": login,
                                            "password": password, "url": _app_url(), "new": True}
                st.session_state["_acc_form_n"] = n + 1
                st.rerun()


def _created_list(actor):
    rows = accounts.accounts_created_by(actor)
    if not rows:
        return
    st.markdown(f"#### 📋 {t('الحسابات اللي عملتها')}")
    for r in rows:
        with st.container(border=True, horizontal=True, vertical_alignment="center",
                          horizontal_alignment="distribute", key=f"acc_row_{r['username']}"):
            status = (f"⏳ {t('لسه بكلمة السر المؤقتة')}" if r["must_change_password"]
                      else f"✅ {t('غيّر كلمة السر')}")
            last = (r["last_login_at"] or "")[:16].replace("T", " ")
            st.markdown(f"**{r['display_name'] or r['username']}** · `{r['username']}`  \n{status}"
                        + (f" · {t('آخر دخول')} {ltr(last)}" if last else f" · {t('لسه مادخلش')}"))
            if st.button(f"🔄 {t('كلمة سر مؤقتة جديدة')}", key=f"acc_reset_{r['username']}"):
                try:
                    password = accounts.operator_reset_password(actor, r["username"])
                except accounts.AccessDenied as exc:
                    st.error(t(str(exc)))
                else:
                    st.session_state[_SHOWN] = {"name": r["display_name"] or r["username"], "username": r["username"],
                                                "password": password, "url": _app_url(), "new": False}
                    st.rerun()


def render(current_user):
    st.button(f"↩ {t('رجوع')}", key="acc_back", on_click=close_page)
    me = accounts.user(current_user or "")
    st.subheader(f"👤 {t('حسابي')} — {(me or {}).get('display_name') or current_user}")
    st.caption(f"{t('اسم الدخول')}: {current_user}")
    if me and me["is_operator"]:
        _credentials_card()
        _create_form(current_user)
        _created_list(current_user)
        st.divider()
    _password_form(current_user)
