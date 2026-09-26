"""لوحة تقرير البناء الدرامي (هرم فرايتاج) — مشتركة بين تبويب الإضافة ومكتبة التحليلات.

التقرير بيتحفظ على التحليل في المكتبة (‎payload["reports"]["dramatic_structure"]‎)،
فاللوحة دي بتاخد رقم التحليل في المكتبة بس، وكل حاجة تانية بتتقري منه:
المشاهد، التقرير لو موجود، والـ job لو لسه شغال. كده الشاشتين بيعرضوا نفس
الحاجة بالظبط، واللي يقفل الصفحة وسط التقرير يرجع يلاقيه.

التقرير بيتطلب بدوسة بس، والتكلفة التقديرية مكتوبة على الزرار نفسه — عمره ما
بيشتغل لوحده بعد التحليل (كل تحليل حتى اللي بيترمي كان هيدفع تمنه). الطلب
بيروح لطابور /v1 لوحده (dramaturgy_jobs.py → dramaturgy_worker.py).
"""

import html
import logging
import uuid

import streamlit as st

import analysis_library as lib
import dramaturgy
import dramaturgy_jobs as jobs
import permissions
from export import build_dramatic_structure_pdf, build_dramatic_structure_word
from i18n import t, tr
from ui import FREE_NOTE, free_cost, ltr

_log = logging.getLogger("cimafast.dramaturgy")

_FALLBACK = "مقدرناش نطلّع تقرير البناء الدرامي. جرّب تاني."

_CSS = """
<style>
.cf-drama { line-height: 1.75; overflow-wrap: anywhere; }
.cf-drama h4 { margin: 0.9rem 0 0.3rem 0; font-size: 1.02rem; }
.cf-drama ul { margin: 0; padding-inline-start: 1.2rem; }
.cf-drama li { margin-bottom: 0.45rem; }
.cf-drama .cf-drama-sub { display: block; opacity: 0.85; font-size: 0.92rem; }
.cf-drama-curve { margin: 0.4rem 0 0.2rem 0; }
.cf-drama-curve svg { display: block; width: 100%; height: auto; }
</style>
"""


def _lang():
    return "en" if st.session_state.get("ui_lang", "ar") == "en" else "ar"


def _flash_key(key):
    return f"_drama_flash_{key}"


def _progress(jid, key):
    """بيتابع الـ job لوحده كل 3 ثواني من غير rerun للصفحة كلها."""

    @st.fragment(run_every=3)
    def _poll():
        info = jobs.status(jid)
        state = info.get("state")
        if state in jobs.TERMINAL:
            st.rerun(scope="app")            # الحفظ برّه الفراجمنت، في التشغيل الكامل
        elif state == "running":
            detail = str(info.get("detail") or "")
            elapsed = detail.split("·", 1)[1].strip() if "·" in detail else ""
            st.info(f"[ ⚙️ ] {t('بيحلل البناء الدرامي...')}"
                    + (f" {ltr(elapsed)}" if elapsed else ""))
        else:
            st.info(f"[ ⏳ ] {t('في الطابور')}")

    _poll()


def _report_html(report, lang):
    parts = [f'<div class="cf-drama" dir="{"rtl" if lang == "ar" else "ltr"}">']
    for sec in dramaturgy.to_sections(report, lang=lang):
        parts.append(f"<h4>{html.escape(sec['heading'])}</h4><ul>")
        for para in sec["paragraphs"]:
            head, *rest = para.split(" | ")
            parts.append("<li>" + html.escape(head)
                         + "".join(f'<span class="cf-drama-sub">{html.escape(r)}</span>' for r in rest)
                         + "</li>")
        parts.append("</ul>")
    parts.append("</div>")
    return "".join(parts)


def show_report(report, script_name, key):
    """المنحنى + الأقسام + التصدير. التقرير نفسه مترجم جاهز من to_sections."""
    lang = _lang()
    st.markdown(f'<div class="cf-drama-curve">{dramaturgy.render_svg(report, lang=lang)}</div>',
                unsafe_allow_html=True)
    st.markdown(_report_html(report, lang), unsafe_allow_html=True)
    meta = report.get("meta") or {}
    bits = [b for b in (meta.get("model"),
                        free_cost(f"${meta['cost_usd']}") if meta.get("cost_usd") is not None else None,
                        (meta.get("generated_at") or "")[:16].replace("T", " ") or None) if b]
    if bits:
        st.caption(ltr(" · ".join(bits)))

    st.markdown(f"**{t('⬇️ تصدير تقرير البناء الدرامي')}**")
    base = (script_name or "script").rsplit(".", 1)[0]
    suffix = "البناء_الدرامي" if lang == "ar" else "dramatic_structure"
    c_pdf, c_word = st.columns(2)
    with c_pdf:
        st.download_button(
            tr("btn_export_pdf"), data=lambda: build_dramatic_structure_pdf(report, script_name, lang),
            file_name=f"{base}_{suffix}.pdf", mime="application/pdf",
            key=f"drama_pdf_{key}", use_container_width=True, on_click="ignore")
    with c_word:
        st.download_button(
            tr("btn_export_word"), data=lambda: build_dramatic_structure_word(report, script_name, lang),
            file_name=f"{base}_{suffix}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key=f"drama_word_{key}", use_container_width=True, on_click="ignore")


def _start(current_user, entry, key):
    try:
        jobs.start(current_user, entry, company_id=st.session_state.get("_cf_company"))
    except permissions.Denied as exc:
        st.error(t(str(exc)))
        return
    except dramaturgy.DramaturgyError as exc:
        st.error(t(str(exc)))
        return
    except Exception as exc:  # noqa: BLE001
        ref = uuid.uuid4().hex[:8]
        _log.exception("[%s] dramaturgy start failed: %s", ref, exc)
        st.error(f"{t(_FALLBACK)} `{ref}`")
        return
    st.rerun()


def render(current_user, library_id, key):
    """اللوحة كاملة لتحليل واحد في المكتبة. ‏key بيفرّق الويدجتس لو اتعرضت أكتر من مرة."""
    if not jobs.available():
        return                               # النسخة دي مالهاش worker للتقرير (البرودكشن لحد دلوقتي)
    st.markdown(_CSS, unsafe_allow_html=True)
    try:
        entry = lib.get(current_user, library_id)
        scenes = jobs.scenes_of(entry)
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, lib.LibraryError):
            st.error(t(str(exc)))
        else:
            _log.exception("dramaturgy panel %s: %s", library_id, exc)
            st.error(t(_FALLBACK))
        return
    st.markdown(f"#### {t('🎭 تقرير البناء الدرامي')}")
    if not scenes:
        st.info(t("مفيش مشاهد في التحليل ده، فمش هيتعمل تقرير بناء درامي."))
        return

    # تقرير خلص ولسه ماتحفظش (حتى لو اللي طلبه قفل الصفحة) بيتحفظ هنا
    if jobs.collect(current_user, entry):
        st.session_state[_flash_key(key)] = ("success", "تقرير البناء الدرامي جاهز")
    running = jobs.active_job(entry["id"])
    last = jobs.latest_job(entry["id"])
    if not running and last:
        info = jobs.status(last)
        # فشل أحدث من آخر تقرير محفوظ: نقول لليوزر مرة واحدة
        seen = st.session_state.setdefault("_drama_failed_seen", set())
        if info.get("state") == "failed" and last not in seen:
            seen.add(last)
            # الرسالة جاية من الـ worker بالعربي وجاهزة للعرض (DramaturgyError أو جملة ثابتة)
            msg = info.get("detail") if info.get("user_message") else _FALLBACK
            st.session_state[_flash_key(key)] = ("error", msg or _FALLBACK)

    flash = st.session_state.pop(_flash_key(key), None)
    if flash:
        (st.success if flash[0] == "success" else st.error)(t(flash[1]))

    report = jobs.report_of(entry)
    if running:
        _progress(running, key)
    else:
        if not report:
            st.caption(t("لسه مفيش تقرير بناء درامي لهذا التحليل") + " — "
                       + t("تحليل تاني فوق نتيجة السيناريو: نقط القوة والضعف في البناء الدرامي حسب هرم فرايتاج، وكل حكم فيه بيترجع لأرقام مشاهد حقيقية."))
        n, cost, ceiling = dramaturgy.estimate(scenes)
        allowed = jobs.can_run(current_user, entry)
        label = t("🎭 عمل تقرير تاني") if report else t("🎭 اعمل تقرير البناء الدرامي")
        # التكلفة على الزرار نفسه — قرار المالك: التقرير بدوسة، والتمن قدامك قبلها
        # الرقم تقديري والخدمة مجانية دلوقتي - مكتوبة على الزرار عشان محدش يخاف يدوس
        if st.button(f"{label} · ~{ltr(f'${cost:.2f}')} · {t('مجاني دلوقتي')}", key=f"drama_go_{key}",
                     use_container_width=True, type="secondary" if report else "primary",
                     disabled=not allowed,
                     help=(f"{ltr(n)} {t('مشهد')} · {t('بحد أقصى')} {ltr(f'${ceiling:.2f}')} · {t(FREE_NOTE)}"
                           if allowed else t(permissions.MESSAGES["run_ai"]))):
            _start(current_user, entry, key)

    if report:
        show_report(report, entry["script_name"], key)
