"""🤖 زرار «اسأل المساعد» — ظاهر طول الوقت في ركن الشاشة (المالك 2026-09-26).

"زرار AI assistant يساعدهم يسألوه في أي حاجة عن البرنامج، ويكون طول الوقت
ظاهر معاهم عشان يساعدهم يتحركوا جوه البرنامج." الرد بيجي من دليل البرنامج
(assistant_guide.md) ومعاه زراير تودّي للشاشة المناسبة على طول.
"""

import time

import streamlit as st

import assistant
import assistant_jobs
import repo
from i18n import t
from ui import go_to, open_page

_HIST = "_asst_hist"
_GO = "_asst_go"

_CSS = """<style>
.st-key-cf_assistant { position: fixed; bottom: 18px; left: 18px; z-index: 999990; width: auto !important; }
.st-key-cf_assistant > div > div > button, .st-key-cf_assistant [data-testid="stPopoverButton"] {
  border-radius: 999px !important; padding: 8px 18px !important; font-weight: 700 !important;
  background: #ffc828 !important; color: #111 !important; border: none !important;
  box-shadow: 0 6px 18px rgba(0,0,0,.45) !important; }
.st-key-cf_assistant [data-testid="stPopoverButton"] * { color: #111 !important; }
.st-key-cf_asst_body { width: min(420px, 88vw); direction: %s; text-align: start; }
</style>"""

# أسئلة جاهزة حسب مكان اليوزر — أول ما يفتح المساعد من غير ما يعرف يسأل إيه
_STARTERS = {
    None: ["أبدأ منين؟", "إزاي أعمل مشروع جديد؟", "إزاي أضيف حد للفريق؟"],
    "import": ["معنديش سيناريو، أبدأ إزاي؟", "الفرق بين التحليل السريع والعميق إيه؟", "الشخصيات ماظهرتش بعد التحليل"],
    "shots": ["إزاي أعمل لقطة من النص؟", "إزاي أحط الكاميرا في الرسمة؟", "إزاي أرسم المكان من فوق؟"],
    "schedule": ["إزاي أعمل أيام التصوير؟", "إزاي أعلّم إن يوم اتصور؟"],
    "post": ["إزاي أتابع المونتاج والتلوين؟"],
}


def consume_navigation():
    """بتتنده بدري في app.py (قبل التبويبات): زرار «افتح» في رد المساعد."""
    slug = st.session_state.pop(_GO, None)
    if not slug or slug not in assistant.DESTINATIONS:
        return
    if assistant.DESTINATIONS[slug][0] == "page":
        open_page(assistant.PAGE_SLUGS[slug])
    else:
        go_to(slug)


def _context():
    ss = st.session_state
    page = st.query_params.get("page")
    tab = st.query_params.get("tab")
    screen_key = {"actors": "actors_library", "locations_lib": "locations_library", "library": "analysis_library",
                  "account": "account", "team": "team", "settings": "settings"}.get(page) if page else tab
    screen = assistant.DESTINATIONS.get(screen_key, (None, None))[1] if screen_key else None
    ctx = {"الاسم": ss.get("_auth_user"), "اللغة": ss.get("ui_lang", "ar"),
           "الشاشة": screen or ("الرئيسية / بداية البرنامج" if not ss.get("_cf_project") else None),
           "المرحلة": {"pre": "ما قبل الإنتاج", "prod": "الإنتاج", "post": "ما بعد الإنتاج"}.get(ss.get("_cf_phase")),
           "صلاحيته": ss.get("_cf_role")}
    pid = ss.get("_cf_project")
    if pid:
        try:
            p = repo.project_by_id(pid)[0]
            ov = repo.project_overview(pid)
            ctx["المشروع"] = f"{p['name']} ({p['project_type']})"
            ctx["في المشروع"] = (f"{ov['scenes']} مشهد، {ov['characters']} شخصية، {ov['locations']} مكان، "
                                 f"{ov['shots']} لقطة، {ov['days']} يوم تصوير")
        except Exception:  # noqa: BLE001 — المساعد مايوقعش الصفحة أبدًا
            pass
    return ctx, screen_key


def _send(question, ctx):
    hist = st.session_state.setdefault(_HIST, [])
    try:
        jid = assistant_jobs.ask(st.session_state.get("_auth_user") or "?", question, ctx,
                                 [h for h in hist if h.get("a")], company_id=st.session_state.get("_cf_company"),
                                 project_id=st.session_state.get("_cf_project"))
    except (ValueError, assistant_jobs.LimitReached, RuntimeError) as exc:
        hist.append({"q": question, "a": t(str(exc)), "goes": [], "state": "failed"})
        return
    hist.append({"q": question, "a": "", "goes": [], "state": "waiting", "jid": jid})


@st.fragment
def _chat():
    ctx, screen_key = _context()
    hist = st.session_state.setdefault(_HIST, [])
    with st.container(height=380, key="cf_asst_log", border=False):
        if not hist:
            st.markdown(f"👋 {t('أنا مساعد سيما فاست. اسألني عن أي حاجة في البرنامج — إزاي تعمل حاجة أو تلاقيها فين.')}")
            for i, q in enumerate(_STARTERS.get(screen_key) or _STARTERS[None]):
                if st.button(t(q), key=f"asst_starter_{i}"):
                    _send(t(q), ctx)
                    st.rerun(scope="fragment")
        for i, h in enumerate(hist):
            with st.chat_message("user"):
                st.markdown(h["q"])
            with st.chat_message("assistant", avatar="🤖"):
                if h["state"] == "waiting":
                    st.caption(f"⏳ {t('بيفكّر…')}")
                else:
                    st.markdown(h["a"])
                    for slug in h.get("goes") or []:
                        if st.button(f"↪ {t('افتح')} {t(assistant.DESTINATIONS[slug][1])}", key=f"asst_go_{i}_{slug}"):
                            st.session_state[_GO] = slug
                            st.rerun(scope="app")
    with st.form("asst_form", clear_on_submit=True, border=False):
        c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
        q = c1.text_input(t("سؤالك"), label_visibility="collapsed", placeholder=t("اسأل عن أي حاجة في البرنامج…"))
        if c2.form_submit_button("➤", use_container_width=True) and q.strip():
            _send(q, ctx)
            st.rerun(scope="fragment")
    pending = next((h for h in hist if h["state"] == "waiting"), None)
    if pending:
        res = assistant_jobs.poll(pending["jid"])
        if res["state"] == "waiting":
            time.sleep(1.2)
        else:
            pending.update(a=res["answer"], goes=res["goes"], state=res["state"])
        st.rerun(scope="fragment")


def render():
    if not assistant_jobs.available() or not st.session_state.get("_auth_user"):
        return
    st.markdown(_CSS % ("rtl" if st.session_state.get("ui_lang", "ar") == "ar" else "ltr"), unsafe_allow_html=True)
    with st.container(key="cf_assistant"):
        with st.popover(f"🤖 {t('اسأل المساعد')}"):
            with st.container(key="cf_asst_body"):
                _chat()
