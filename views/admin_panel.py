"""🛡️ إدارة الحسابات — صفحة المشغّل (المالك 2026-09-26). بتتفتح من «👤 حسابي».

جدول بكل الحسابات وأرقامها، وتختار حساب فتشوف وتعمل: تعديل بياناته وباقته
ومدته، إيقافه، كلمة سر مؤقتة، قفل/فتح مزايا، نقل ملفاته لحساب تاني (أو جديد)،
دمجه في حساب تاني، نشاطه، وحذفه. المنطق كله في admin_users.py.
"""

import datetime as dt

import pandas as pd
import streamlit as st

import accounts
import admin_users as au
from i18n import t
from ui import close_page, ltr

_STATUS = {"active": "🟢 شغال", "suspended": "⏸️ موقوف", "expired": "⌛ مدته خلصت", "merged": "🔗 اتدمج"}
_MSG = "_adm_msg"


def _flash(kind, text, extra=None):
    st.session_state[_MSG] = (kind, text, extra)


def _show_flash():
    msg = st.session_state.pop(_MSG, None)
    if not msg:
        return
    kind, text, extra = msg
    getattr(st, kind)(text)
    if extra:
        st.code(extra, language=None)


def _date(s):
    return (s or "")[:16].replace("T", " ") or "—"


def _table(rows):
    c1, c2, c3 = st.columns([3, 2, 2])
    q = c1.text_input(t("دوّر"), placeholder=t("اسم أو اسم دخول…"), key="adm_q").strip().lower()
    status = c2.selectbox(t("الحالة"), ["all", "active", "never", "temp", "suspended", "expired", "merged"],
                          key="adm_status",
                          format_func=lambda k: {"all": t("الكل"), "never": t("ماداخلش ولا مرة"),
                                                 "temp": t("لسه بكلمة السر المؤقتة")}.get(k) or t(_STATUS[k]))
    makers = sorted({r["created_by"] for r in rows if r["created_by"]})
    maker = c3.selectbox(t("عمله"), ["all"] + makers, key="adm_maker",
                         format_func=lambda k: t("الكل") if k == "all" else k)
    out = []
    for r in rows:
        if q and q not in (r["username"] or "").lower() and q not in (r["display_name"] or "").lower():
            continue
        if status == "never" and r["last_login_at"]:
            continue
        if status == "temp" and not r["must_change_password"]:
            continue
        if status not in ("all", "never", "temp") and r["status"] != status:
            continue
        if maker != "all" and r["created_by"] != maker:
            continue
        out.append(r)
    df = pd.DataFrame([{
        t("الاسم"): r["display_name"] or r["username"], t("اسم الدخول"): r["username"],
        t("الحالة"): ("🛡️ " + t("مشغّل")) if r["is_operator"] else t(_STATUS[r["status"]]),
        t("الباقة"): accounts.TIER_LABELS.get(r["tier"], "—"), t("مشاريع"): r["projects"], t("مشاهد"): r["scenes"],
        t("أسئلة للمساعد"): r["questions"], t("آخر دخول"): _date(r["last_login_at"]),
        t("اتعمل"): _date(r["created_at"])[:10], t("عمله"): r["created_by"] or "—",
    } for r in out])
    st.caption(f"{ltr(len(out))} {t('حساب')}")
    if df.empty:
        return None
    if st.session_state.get("ui_lang", "ar") == "ar":
        df = df[df.columns[::-1]]
    ev = st.dataframe(df, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
                      height=min(40 + 35 * len(df), 460), key="adm_table")
    picked = ev.selection.rows if ev and ev.selection else []
    if picked:
        return out[picked[0]]["username"]
    names = {r["username"]: f"{r['display_name'] or r['username']} ({r['username']})" for r in out}
    return st.selectbox(t("أو اختار الحساب"), list(names), index=None, format_func=names.get,
                        placeholder=t("اكتب أو اختار…"), key="adm_pick")


def _profile_tab(actor, r):
    with st.form(f"adm_profile_{r['username']}"):
        c1, c2 = st.columns(2)
        name = c1.text_input(t("الاسم"), r["display_name"] or "")
        email = c2.text_input(t("الإيميل"), r["email"] or "")
        c1, c2 = st.columns(2)
        job = c1.text_input(t("الوظيفة"), r["job_title"] or "")
        tier = c2.radio(t("الباقة"), accounts.TIERS, horizontal=True,
                        index=accounts.TIERS.index(r["tier"]) if r["tier"] in accounts.TIERS else 0,
                        format_func=lambda k: accounts.TIER_LABELS[k])
        c1, c2 = st.columns(2)
        try:
            exp = dt.date.fromisoformat((r["expires_at"] or "")[:10])
        except ValueError:
            exp = None
        expires = c1.date_input(t("الحساب شغال لحد (فاضي = على طول)"), value=exp)
        limit = c2.number_input(t("حد أسئلة المساعد في اليوم (فاضي = 40)"), min_value=0, max_value=1000, step=10,
                                value=au.assistant_limit(r["username"], None))
        note = st.text_area(t("ملاحظة داخلية (مابتظهرش له)"), r["admin_note"] or "", height=70)
        if st.form_submit_button(f"💾 {t('حفظ')}", type="primary"):
            au.update_profile(actor, r["username"], name, email, job, note, tier,
                              expires.isoformat() if expires else None, limit)
            _flash("success", f"✅ {t('اتحفظت بيانات')} {r['username']}")
            st.rerun()


def _access_tab(actor, r):
    c1, c2 = st.columns(2)
    if r["active"]:
        if c1.button(f"⏸️ {t('أوقف الحساب')}", key="adm_suspend", use_container_width=True,
                     help=t("مش هيقدر يدخل، ولو فاتح البرنامج هيطلع مع أول ضغطة. ملفاته زي ما هي.")):
            au.set_active(actor, r["username"], False)
            _flash("warning", f"⏸️ {t('الحساب اتوقف')}: {r['username']}")
            st.rerun()
    elif not r["merged_into"]:
        if c1.button(f"▶️ {t('شغّل الحساب تاني')}", key="adm_resume", use_container_width=True, type="primary"):
            au.set_active(actor, r["username"], True)
            _flash("success", f"▶️ {t('الحساب اشتغل تاني')}: {r['username']}")
            st.rerun()
    if c2.button(f"🔄 {t('كلمة سر مؤقتة جديدة')}", key="adm_reset", use_container_width=True):
        pw = au.reset_password(actor, r["username"])
        _flash("info", f"🔑 {t('كلمة السر المؤقتة لـ')} {r['username']} — {t('بتظهر مرة واحدة، وهيطلب منه يغيّرها أول ما يدخل:')}", pw)
        st.rerun()
    st.markdown(f"**{t('المزايا')}** — {t('شيل العلامة عشان تقفل الميزة على الحساب ده:')}")
    off = au.disabled_features(r["username"])
    with st.form(f"adm_features_{r['username']}"):
        chosen = {k: st.checkbox(t(label), value=k not in off, key=f"adm_f_{r['username']}_{k}")
                  for k, label in au.FEATURES.items()}
        if st.form_submit_button(f"💾 {t('حفظ المزايا')}", type="primary"):
            au.set_features(actor, r["username"], [k for k, on in chosen.items() if not on])
            _flash("success", f"✅ {t('اتحفظت مزايا')} {r['username']}")
            st.rerun()


def _move_tab(actor, r, all_rows):
    own = au.owned(r["username"])
    st.caption(f"{t('ملفاته')}: {ltr(len(own['projects']))} {t('مشروع')} · {ltr(len(own['library']))} {t('تحليل')} · "
               f"{ltr(len(own['actors']))} {t('ممثل')} · {ltr(len(own['venues']))} {t('مكان حقيقي')}")
    others = [x for x in all_rows if x["username"] != r["username"] and not x["is_operator"] and x["status"] == "active"]
    label = {x["username"]: f"{x['display_name'] or x['username']} ({x['username']})" for x in others}

    st.markdown(f"##### 📦 {t('انقل ملفاته لحساب تاني')}")
    with st.form(f"adm_transfer_{r['username']}"):
        mode = st.radio(t("لمين؟"), ["existing", "new"], horizontal=True,
                        format_func=lambda m: t("حساب موجود") if m == "existing" else t("حساب جديد"))
        target = st.selectbox(t("الحساب الموجود"), list(label), format_func=label.get) if label else None
        c1, c2 = st.columns(2)
        new_name = c1.text_input(t("اسم الحساب الجديد"))
        new_user = c2.text_input(t("اسم الدخول الجديد (إنجليزي)"))
        keep = st.checkbox(t("يفضل عضو في مشاريعه بعد النقل (يعدّل)"), value=True)
        if st.form_submit_button(f"📦 {t('انقل')}", type="primary"):
            dest = new_user if mode == "new" else target
            try:
                counts, pw, backup = au.transfer(actor, r["username"], dest, new_name, keep)
            except (ValueError, accounts.AccessDenied) as exc:
                st.error(t(str(exc)))
            else:
                text = " · ".join(f"{t(k)}: {v}" for k, v in counts.items())
                _flash("success", f"📦 {t('اتنقل')} → {dest}: {text}",
                       f"{t('كلمة سر الحساب الجديد')}: {pw}" if pw else None)
                st.rerun()

    st.markdown(f"##### 🔗 {t('ادمجه في حساب تاني')}")
    st.caption(t("كل ملفاته وعضوياته في مشاريع الناس بتروح للحساب التاني، والحساب ده بيتقفل (بيفضل في السجل)."))
    with st.form(f"adm_merge_{r['username']}"):
        into = st.selectbox(t("يدمج في"), list(label), format_func=label.get) if label else None
        sure = st.checkbox(t("متأكد — الحساب ده هيتقفل بعد الدمج"))
        if st.form_submit_button(f"🔗 {t('ادمج')}"):
            if not sure or not into:
                st.error(t("علّم «متأكد» واختار الحساب الأول"))
            else:
                try:
                    counts, _backup = au.merge(actor, r["username"], into)
                except (ValueError, accounts.AccessDenied) as exc:
                    st.error(t(str(exc)))
                else:
                    text = " · ".join(f"{t(k)}: {v}" for k, v in counts.items())
                    _flash("success", f"🔗 {r['username']} → {into}: {text}")
                    st.rerun()


def _activity_tab(actor, r):
    a = au.activity(actor, r["username"])
    if a["projects"]:
        st.markdown(f"**{t('مشاريعه')}**")
        st.dataframe(pd.DataFrame([{t("المشروع"): p["name"], t("النوع"): t(p["project_type"] or ""),
                                    t("مشاهد"): p["scenes"], t("شخصيات"): p["characters"]} for p in a["projects"]]),
                     hide_index=True, use_container_width=True)
    if a["questions"]:
        st.markdown(f"**🤖 {t('سأل المساعد')}**")
        for q in a["questions"]:
            st.markdown(f"- {_date(q['at'])} · {q['screen'] or '—'} · {q['question']}")
    rows = [{"at": e["at"], "what": f"{e['event']} · {e['target'] or ''}"} for e in a["events"]] + \
           [{"at": c["at"], "what": c["summary"] or c["action"]} for c in a["changes"]]
    rows.sort(key=lambda x: x["at"], reverse=True)
    if rows:
        st.markdown(f"**{t('آخر نشاط')}**")
        st.dataframe(pd.DataFrame([{t("الوقت"): _date(x["at"]), t("عمل إيه"): x["what"]} for x in rows[:50]]),
                     hide_index=True, use_container_width=True, height=320)
    if not (a["projects"] or a["questions"] or rows):
        st.caption(t("لسه مفيش نشاط."))


def _delete_tab(actor, r):
    n = len(au.owned(r["username"])["projects"])
    st.warning(t("الحذف نهائي: الحساب بيتمسح وعضوياته، ومساحة عمله بتتقفل. بتتاخد نسخة احتياطية من قاعدة البيانات قبلها."))
    with st.form(f"adm_delete_{r['username']}"):
        with_projects = False
        if n:
            st.caption(f"{t('عنده')} {ltr(n)} {t('مشروع — انقلهم من «نقل ودمج» الأول، أو امسحهم معاه:')}")
            with_projects = st.checkbox(t("امسح مشاريعه كمان"))
        confirm = st.text_input(f"{t('اكتب اسم الدخول للتأكيد')}: {r['username']}")
        if st.form_submit_button(f"🗑️ {t('احذف الحساب نهائيًا')}"):
            try:
                au.delete(actor, r["username"], confirm, with_projects)
            except (ValueError, accounts.AccessDenied) as exc:
                st.error(t(str(exc)))
            else:
                _flash("success", f"🗑️ {t('اتحذف')}: {r['username']}")
                st.session_state.pop("adm_table", None)
                st.rerun()


def render(actor):
    st.button(f"↩ {t('رجوع')}", key="adm_back", on_click=close_page)
    if not (accounts.user(actor or "") or {}).get("is_operator"):
        st.error(t("الصفحة دي لمشغّل المنصة بس."))
        return
    st.subheader(f"🛡️ {t('إدارة الحسابات')}")
    _show_flash()
    rows = au.overview(actor)
    week = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)).isoformat()
    m = st.columns(5)
    m[0].metric(t("الحسابات"), ltr(len(rows)))
    m[1].metric(t("شغالة"), ltr(sum(1 for r in rows if r["status"] == "active")))
    m[2].metric(t("موقوفة / خلصت"), ltr(sum(1 for r in rows if r["status"] in ("suspended", "expired"))))
    m[3].metric(t("دخلوا آخر ٧ أيام"), ltr(sum(1 for r in rows if (r["last_login_at"] or "") >= week)))
    m[4].metric(t("ماداخلوش ولا مرة"), ltr(sum(1 for r in rows if not r["last_login_at"])))

    picked = _table(rows)
    if not picked:
        st.caption(f"👆 {t('اختار حساب من الجدول (المربع جنب الصف) أو من القايمة عشان تديره.')}")
        return
    r = next(x for x in rows if x["username"] == picked)
    st.divider()
    st.markdown(f"### {r['display_name'] or r['username']} · `{r['username']}` · "
                f"{t(_STATUS[r['status']]) if not r['is_operator'] else '🛡️ ' + t('مشغّل')}")
    if r["merged_into"]:
        st.caption(f"🔗 {t('اتدمج في')} {r['merged_into']}")
    if r["is_operator"] or r["username"] == actor:
        st.info(t("ده حساب مشغّل — مايتعدّلش من هنا."))
        _activity_tab(actor, r)
        return
    tabs = st.tabs([f"📋 {t('البيانات')}", f"🔒 {t('الوصول والمزايا')}", f"📦 {t('نقل ودمج')}",
                    f"📈 {t('النشاط')}", f"🗑️ {t('حذف')}"])
    with tabs[0]:
        _profile_tab(actor, r)
    with tabs[1]:
        _access_tab(actor, r)
    with tabs[2]:
        _move_tab(actor, r, rows)
    with tabs[3]:
        _activity_tab(actor, r)
    with tabs[4]:
        _delete_tab(actor, r)
