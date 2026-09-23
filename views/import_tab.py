"""تبويب import."""

import ai_jobs
import analysis_library
import json
import logging
import uuid
import streamlit as st
import streamlit.components.v1 as st_components
from ai_prompt import AI_JSON_PROMPT
from database import fetch_all, run_query, scene_label
from i18n import t, tr
from importer import import_parsed_scenes
from script_md import to_markdown
from script_parser import apply_character_merges, apply_location_merges, extract_lines, find_location_matches_with_states, find_similar_location_groups, find_similar_name_groups, looks_like_screenplay, parse_json_script, parse_script
from ui import fmt_day_night, fmt_int_ext, ltr, multiselect
import audit
import repo
from views import dramaturgy_panel


_log = logging.getLogger("cimafast.import")

# الأخطاء اللي بنرمي لها رسالة بالعربي احنا بنفسنا (زي "فيه تحليل شغال
# بالفعل") تعدّي للمستخدم زي ما هي. أي حاجة تانية — خصوصًا أخطاء نظام
# التشغيل — لأ.
_SAFE_TO_SHOW = (RuntimeError, ValueError, KeyError, TypeError)

_ERR_TITLE = "مشكلة في السيرفر مش في ملفك"
_ERR_BODY = "الملف وصل تمام بس مقدرناش نكمّل. جرّب تاني بعد شوية، ولو المشكلة فضلت ابعت الكود ده للدعم"


def _user_error(exc, where):
    """رسالة يفهمها مخرج بيرفع سيناريو، والخطأ الحقيقي يروح للوج.

    كان `st.error(str(e))` بيطلّع نص نظام التشغيل الخام على الشاشة، مثلًا
    "Read-only file system: '/var/lib/cimafast/ai-jobs/inbox/…tmp' [Errno 30]".
    ده مبيقولش للمستخدم أي حاجة يعملها، وكمان بيكشف مسارات السيرفر.
    بنسجّل التفاصيل كاملة في لوج الخدمة (journalctl) ونرجّع للمستخدم
    رسالة واضحة + كود مرجعي يقوله للدعم.
    """
    ref = uuid.uuid4().hex[:8]
    _log.exception("[%s] %s failed: %s: %s", ref, where, type(exc).__name__, exc)
    if isinstance(exc, _SAFE_TO_SHOW) and str(exc).strip():
        return str(exc)
    return f"⚠️ {t(_ERR_TITLE)}\n\n{t(_ERR_BODY)}: `{ref}`"


_ANALYSIS_RTL_CSS = """
<style>
/* نتائج التحليل كلها عربي: أسماء شخصيات وأماكن وإكسسوارات وملاحظات.
   Streamlit بيرندر الجداول والمقاييس والـ expander من الشمال لليمين
   افتراضيًا، فالأسماء العربية كانت بتتعرض بمحاذاة غلط وعلامات الترقيم
   بتقع في الناحية الغلط. الستايل ده متربط بمفتاح الكونتينر عشان يأثر
   على منطقة التحليل بس ومايلخبطش باقي الصفحة. */
.st-key-cf_analysis, .st-key-cf_compare { direction: rtl; text-align: right; }
.st-key-cf_analysis p, .st-key-cf_compare p,
.st-key-cf_analysis li, .st-key-cf_compare li,
.st-key-cf_analysis h2, .st-key-cf_analysis h3,
.st-key-cf_compare h2, .st-key-cf_compare h3 { direction: rtl; text-align: right; }
.st-key-cf_analysis [data-testid="stCaptionContainer"],
.st-key-cf_compare [data-testid="stCaptionContainer"] { direction: rtl; text-align: right; }
.st-key-cf_analysis [data-testid="stMetric"],
.st-key-cf_compare [data-testid="stMetric"] { direction: rtl; text-align: right; }
.st-key-cf_analysis [data-testid="stExpander"] summary,
.st-key-cf_compare [data-testid="stExpander"] summary { direction: rtl; text-align: right; }
/* الجدول: الهيدر والخلايا لازم يتقلبوا مع بعض */
.st-key-cf_compare [data-testid="stDataFrame"] { direction: rtl; }
.st-key-cf_compare [data-testid="stDataFrame"] [role="columnheader"],
.st-key-cf_compare [data-testid="stDataFrame"] [role="gridcell"] {
    direction: rtl; text-align: right;
}
/* الأرقام والكود يفضلوا LTR جوه نص عربي */
.st-key-cf_analysis code, .st-key-cf_compare code { direction: ltr; unicode-bidi: embed; }
</style>
"""


def _analysis_rtl_css():
    """بيحقن الستايل مرة واحدة في كل تشغيل للصفحة."""
    st.markdown(_ANALYSIS_RTL_CSS, unsafe_allow_html=True)


def _clear_analysis_state():
    """بيمسح أي نتيجة تحليل من الجلسة — السريعة واللي من الذكاء الاصطناعي —
    من غير ما يفترض إن مفتاح معيّن موجود."""
    for key in ("parsed_script", "ai_parsed_script", "ai_job_id",
                "_ai_pending", "_which_analysis", "_ai_last_seen_state",
                "_ai_load_attempted"):
        st.session_state.pop(key, None)


def _render_copy_button(text, label, done_label):
    """زرار نسخ حقيقي للبرومبت.

    Streamlit مفيهاش API للكليبورد، وكمان الكومبوننت بيتحط في iframe من غير
    صلاحية clipboard-write، فـ navigator.clipboard بيترفض هناك. فبنجرب الـ API
    الحديثة الأول، ولو رفضت بنقع على execCommand بـ textarea مخفي — ده لسه
    شغال جوه الـ iframe. زرار التنزيل و st.code تحته هما خط الرجعة الأخير لو
    المتصفح رفض الاتنين.
    """
    payload = json.dumps(text)
    st_components.html(
        f"""
        <button id="cf-copy" style="width:100%;padding:0.55rem 1rem;cursor:pointer;
            border-radius:12px;border:1.5px solid #FECA05;
            background:rgba(254,202,5,0.12);color:#FECA05;font-weight:600;
            font-family:Inter,Cairo,system-ui,sans-serif;font-size:0.95rem;">
          {label}
        </button>
        <script>
        const txt = {payload};
        const btn = document.getElementById("cf-copy");
        function ok() {{ btn.textContent = {json.dumps(done_label)}; }}
        btn.addEventListener("click", async () => {{
          try {{
            await navigator.clipboard.writeText(txt);
            ok();
          }} catch (e) {{
            const ta = document.createElement("textarea");
            ta.value = txt;
            ta.style.position = "fixed";
            ta.style.opacity = "0";
            document.body.appendChild(ta);
            ta.select();
            try {{ document.execCommand("copy"); ok(); }}
            catch (e2) {{ btn.textContent = "⚠️"; }}
            document.body.removeChild(ta);
          }}
        }});
        </script>
        """,
        height=56,
    )


def _render_source_picker(fast, ai):
    """المقارنة بين التحليلين + اختيار اللي هيتستورد.

    التحليل السريع بيشتغل بقواعد ثابتة والذكاء الاصطناعي بيفهم السياق، فبيختلفوا.
    بنوري الفرق بدل ما نختار لليوزر، وبعدين اللي يختاره هو اللي بيكمل في نفس
    خطوات المراجعة والاستيراد الموجودة تحت."""
    fs = {s["scene_number"]: s for s in fast["scenes"]}
    as_ = {s["scene_number"]: s for s in ai["scenes"]}
    meta = ai.get("meta") or {}

    st.markdown("---")
    st.markdown(f"### ⚖️ {t('مقارنة التحليلين')}")
    c1, c2, c3 = st.columns(3)
    c1.metric(t("مشاهد — تحليل سريع"), len(fs))
    c2.metric(t("مشاهد — ذكاء اصطناعي"), len(as_),
              delta=len(as_) - len(fs) if len(as_) != len(fs) else None)
    if meta.get("cost_usd") is not None:
        c3.metric(t("تكلفة التحليل"), f"${meta['cost_usd']}")

    only_ai = sorted(set(as_) - set(fs))
    only_fast = sorted(set(fs) - set(as_))
    if only_ai:
        st.caption(f"🤖 {t('مشاهد لقاها الذكاء الاصطناعي بس')}: "
                   + "، ".join(str(n) for n in only_ai[:25]))
    if only_fast:
        st.caption(f"🔍 {t('مشاهد لقاها التحليل السريع بس')}: "
                   + "، ".join(str(n) for n in only_fast[:25]))

    rows = []
    for n in sorted(set(fs) & set(as_)):
        a, b = fs[n], as_[n]
        for field, label in (("characters", t("الشخصيات")), ("props", t("الإكسسوارات"))):
            extra = [x for x in b.get(field) or [] if x not in (a.get(field) or [])]
            missing = [x for x in a.get(field) or [] if x not in (b.get(field) or [])]
            if extra or missing:
                rows.append({
                    t("مشهد"): n, t("الحقل"): label,
                    t("زوّده الذكاء الاصطناعي"): "، ".join(extra) or "—",
                    t("موجود في السريع بس"): "، ".join(missing) or "—",
                })
    if rows:
        with st.expander(f"{t('تفاصيل الفروق')} ({len(rows)})"):
            st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption(t("مفيش فروق في الشخصيات أو الإكسسوارات بين التحليلين."))


def _render_analysis_dashboard(scenes):
    """لوحة تحليل السيناريو.

    كانت متكتوبة جوه زرار "تأكيد وإضافة المشاهد"، وبعد ما بترسم على طول
    بيتمسح parsed_script ويتعمل rerun — يعني كانت بتترسم في إطار بيتلغي
    قبل ما المستخدم يشوفه أصلًا. دلوقتي بتتعرض عادي وبتفضل ظاهرة."""
    st.markdown("---")
    st.markdown(f"## 📊 {t('تحليل السيناريو')}")
    tabs = st.tabs([t("📝 المشاهد"), t("👥 الشخصيات"), t("🏠 الأماكن"), t("🎬 الإكسسوارات"), t("📑 JSON")])

    with tabs[0]:
        for sc in scenes:
            st.subheader(f"{t('مشهد')} {ltr(scene_label(sc))}")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.caption(f"**{t('النوع')}**: {fmt_int_ext(sc.get('int_ext', 'غير محدد'))}")
            with col2:
                st.caption(f"**{t('الوقت')}**: {fmt_day_night(sc.get('day_night', 'غير محدد'))}")
            with col3:
                st.caption(f"**{t('المكان')}**: {sc.get('location_name', t('مكان غير محدد'))}")
            if sc.get('characters'):
                st.caption(f"**{t('الشخصيات')}**: {', '.join(sc['characters'])}")
            if sc.get('props'):
                st.caption(f"**🎬 {t('الإكسسوارات')}**: {', '.join(sc['props'])}")

    with tabs[1]:
        all_chars = set()
        for sc in scenes:
            all_chars.update(sc.get('characters', []))
        st.write(f"**{t('إجمالي الشخصيات')}**: {len(all_chars)}")
        for char in sorted(all_chars):
            appearances = sum(1 for sc in scenes if char in sc.get('characters', []))
            st.caption(f"{char} ({appearances} {t('مشاهد')})")

    with tabs[2]:
        all_locs = set()
        for sc in scenes:
            if sc.get('location_name'):
                all_locs.add(sc['location_name'])
        st.write(f"**{t('إجمالي الأماكن')}**: {len(all_locs)}")
        for loc in sorted(all_locs):
            st.caption(loc)

    with tabs[3]:
        all_props = set()
        for sc in scenes:
            all_props.update(sc.get('props', []))
        st.write(f"**{t('إجمالي الإكسسوارات')}**: {len(all_props)}")
        for prop in sorted(all_props):
            st.caption(prop)

    with tabs[4]:
        import json
        json_output = json.dumps({'scenes': scenes}, ensure_ascii=False, indent=2)
        st.code(json_output, language="json")
        st.download_button(
            label=t("📥 تحميل JSON"),
            data=json_output,
            file_name="analysis.json",
            mime="application/json"
        )


def render(project_id):
    st.subheader(tr("sub_import"))
    st.caption(t(
        "ارفع ملف السيناريو (.docx أو .txt)، والنظام هيحاول يتعرف على رقم كل مشهد، "
        "داخلي/خارجي، النهار/الليل، المكان، والحوار، ويملى تبويب (السكريبت) تلقائيًا. "
        "تقدر تراجع النتيجة وتعدل أو تضيف أي حاجة بعد كده. وفي حالة السكريبتات "
        "الصعبة، تقدر ترفع ملف JSON جاهز من أي AI (شوف التفاصيل تحت)."
    ))
    st.caption(t(
        "لأفضل نتيجة، اكتب كل مشهد في سطر بصيغة زي: "
        "\"مشهد 1 - داخلي - نهار - غرفة المعيشة\"، والحوار في سطر منفصل بصيغة "
        "\"اسم الشخصية: الكلام\"."
    ))

    with st.expander(t("🤖 التحليل خارج البرنامج — حلّل السكريبت على أي AI وارجع بالنتيجة")):
        st.markdown(t(
            "لو السكريبت شكله معقد والتحليل اللي جوه البرنامج مش طالع كويس، حلّله بره "
            "على أي AI في أربع خطوات:"
        ))
        st.markdown(t(
            "**1.** دوس «📋 نسخ البرومبت» تحت.\n\n"
            "**2.** افتح Claude أو ChatGPT أو Gemini، الصق البرومبت، وارفق معاه ملف "
            "السكريبت (أو الصق نصه كامل بعد البرومبت).\n\n"
            "**3.** احفظ الـ JSON اللي هيرجعلك في ملف اسمه `script.json`.\n\n"
            "**4.** ارفع `script.json` من زرار رفع الملف تحت — هيتقري ويتستورد زي أي سكريبت."
        ))

        _render_copy_button(AI_JSON_PROMPT, t("📋 نسخ البرومبت"), t("✅ اتنسخ"))
        st.download_button(
            t("⬇️ أو نزّل البرومبت كملف"), AI_JSON_PROMPT,
            file_name="cimafast_prompt.txt", mime="text/plain",
            key="dl_prompt", use_container_width=True)

        st.markdown(
            f'<div class="cf-copy-hint">👇 {t("ده نص البرومبت كامل، لو حبيت تراجعه أو تنسخه يدويًا")}</div>',
            unsafe_allow_html=True,
        )
        st.code(AI_JSON_PROMPT, language="text")

    uploaded_file = st.file_uploader(t("اختر ملف السكريبت"), type=["docx", "txt", "pdf", "json"], key="script_upload")

    _known = [r["name"] for r in repo.character_names_of_project(project_id)]
    _ai_active = ai_jobs.active_job(project_id)

    _c_fast, _c_ai = st.columns(2)
    with _c_fast:
        _run_fast = uploaded_file is not None and st.button(
            t("🔍 تحليل الملف"), use_container_width=True,
            help=t("تحليل سريع ومجاني على الجهاز، من غير ذكاء اصطناعي."))
    with _c_ai:
        _run_ai = uploaded_file is not None and st.button(
            t("🤖 تحليل بالذكاء الاصطناعي"), use_container_width=True,
            disabled=bool(_ai_active),
            help=t("تحليل أعمق بـ Opus. بيستغرق دقايق وبيكلف فلوس."))

    if _run_fast:
        try:
            st.session_state["parsed_script"] = parse_script(
                uploaded_file.name, uploaded_file.getvalue(), known_characters=_known)
        except Exception as e:
            st.error(f"{t('حصل خطأ أثناء تحليل الملف:')} {_user_error(e, 'fast parse')}")

    # --- تحليل الذكاء الاصطناعي: تقدير -> تأكيد -> طابور ------------------
    if _run_ai:
        try:
            _lines = extract_lines(uploaded_file.name, uploaded_file.getvalue())
            _md, _stats = to_markdown(_lines)
            _conf, _ev = looks_like_screenplay(_lines)
            st.session_state["_ai_pending"] = {
                "md": _md, "stats": _stats, "filename": uploaded_file.name,
                "confidence": _conf, "evidence": _ev}
        except Exception as e:
            st.error(f"{t('حصل خطأ أثناء قراءة الملف:')} {_user_error(e, 'ai read')}")

    _pending = st.session_state.get("_ai_pending")
    if _pending and not _ai_active:
        _n, _cost, _ceiling = ai_jobs.estimate(_pending["md"])
        _st = _pending["stats"]
        st.info(
            f"{t('عدد المشاهد المكتشفة')}: **{_n}** · "
            f"{t('تكلفة تقديرية')}: **${_cost}** ({t('بحد أقصى')} ${_ceiling})\n\n"
            f"{t('تم تنضيف الملف قبل الإرسال')}: {_st['raw_chars']:,} → "
            f"{_st['md_chars']:,} {t('حرف')}"
            + (f" ({_st['saved_pct']}% {t('أقل')})" if _st['saved_pct'] > 0 else ""))
        # لو المستند مش شكله سيناريو، الـ AI مش هيقدر يقول "مش عارف" — الـ
        # schema بتفرض عليه يرجّع مشاهد، فهيخترعها. بنحذّر قبل الصرف.
        _conf = _pending.get("confidence", 1.0)
        _ev = _pending.get("evidence", {})
        if _conf < 0.3:
            st.error(
                f"⚠️ {t('الملف ده مش شكله سيناريو.')}\n\n"
                f"{t('مفيش فيه عناوين مشاهد')} ({_ev.get('scene_headers', 0)}) "
                f"{t('ولا داخلي/خارجي')} ({_ev.get('int_ext', 0)}) "
                f"{t('ولا سطور حوار')} ({_ev.get('dialogue_lines', 0)}).\n\n"
                f"{t('لو كملت، الذكاء الاصطناعي هيضطر يخترع مشاهد وأرقام مش موجودة في الملف.')}")
        elif _conf < 0.6:
            st.warning(
                f"⚠️ {t('أدلة قليلة إن ده سيناريو')} "
                f"({t('عناوين مشاهد')}: {_ev.get('scene_headers', 0)}, "
                f"{t('حوار')}: {_ev.get('dialogue_lines', 0)}). "
                f"{t('راجع النتيجة كويس قبل الاستيراد.')}")
        _ok, _no = st.columns(2)
        with _ok:
            _go_label = t("✅ ابدأ التحليل") if _conf >= 0.3 else t("⚠️ كمّل بالرغم من كده")
            if st.button(_go_label, use_container_width=True, key="_ai_go"):
                try:
                    st.session_state.pop("_ai_load_attempted", None)
                    st.session_state["ai_job_id"] = ai_jobs.start(
                        _pending["md"], project_id, _pending["filename"],
                        known_characters=_known, max_cost_usd=_ceiling)
                    # F3: تشغيل التحليل بيكلّف فلوس — بيتسجّل كحدث استخدام بسقفه
                    # job_id: مكتبة التحليلات بتعرف منه مين اللي شغّل التحليل
                    audit.event("ai", target="script_analysis", project_id=project_id,
                                detail={"file": _pending["filename"], "ceiling_usd": _ceiling,
                                        "job_id": st.session_state["ai_job_id"]})
                    st.session_state.pop("_ai_pending", None)
                    st.rerun()
                except Exception as e:
                    st.error(_user_error(e, "ai start"))
        with _no:
            if st.button(t("إلغاء"), use_container_width=True, key="_ai_no"):
                st.session_state.pop("_ai_pending", None)
                st.rerun()

    # لو التاب اتقفل والتحليل لسه شغال، نرجّع نتابعه بدل ما يضيع
    if _ai_active and not st.session_state.get("ai_job_id"):
        st.session_state["ai_job_id"] = _ai_active
    # ولو كان خلص خلاص، نرجّع آخر نتيجة بدل ما تحليل اتدفع فيه فلوس يضيع
    # بمجرد ريفريش أو إعادة تشغيل للبرنامج
    if not st.session_state.get("ai_job_id"):
        _recent = ai_jobs.latest_completed(project_id)
        if _recent:
            st.session_state["ai_job_id"] = _recent

    _job = st.session_state.get("ai_job_id")
    if _job:
        _state = ai_jobs.status(_job).get("state")

        @st.fragment(run_every=(3 if _state not in ai_jobs.TERMINAL else None))
        def _ai_progress():
            """بيحدّث حالة التحليل لوحده من غير ما يعمل rerun للصفحة كلها،
            عشان اللي اليوزر ملاه فوق ما يضيعش منه."""
            info = ai_jobs.status(_job)
            state, detail = info.get("state"), info.get("detail", "")
            spent = info.get("cost_usd")
            extra = f" · ${spent}" if spent else ""
            if state == "done":
                st.success(f"[ ✅ ] {t('التحليل خلص')} — {detail}{extra}")
                # الفراجمنت بيعيد تشغيل نفسه بس. الكود اللي بيحمّل النتيجة
                # برّه، وبيقرا الحالة مرة واحدة كل تشغيل كامل للصفحة — فكان
                # بيفضل شايف "شغال" للأبد، والمستخدم لازم يعمل ريفريش بإيده.
                # rerun على مستوى التطبيق بيشغّل التحميل فورًا.
                # مرة واحدة بس. لو ملف النتيجة مش مقروء، ai_parsed_script
                # عمره ما هيتظبط، والـ rerun هيفضل يلف للأبد.
                if (not st.session_state.get("ai_parsed_script")
                        and not st.session_state.get("_ai_load_attempted")):
                    st.session_state["_ai_load_attempted"] = True
                    st.rerun(scope="app")
            elif state == "failed":
                # detail جاي من الـ worker وممكن يكون نص استثناء بايثون خام.
                # بنعرض سطر مفهوم، والتفاصيل التقنية تحت في expander لمين
                # يحتاجها، مش كعنوان الرسالة.
                st.error(f"[ ❌ ] {t('التحليل فشل')}{extra} — "
                         f"{t('مقدرناش نكمّل التحليل. ملفك زي ما هو، تقدر تجرّب تاني.')}")
                if detail:
                    with st.expander(t("تفاصيل تقنية")):
                        st.code(detail, language="text")
                if st.session_state.get("_ai_last_seen_state") != "failed":
                    st.session_state["_ai_last_seen_state"] = "failed"
                    st.rerun(scope="app")
            elif state == "running":
                st.info(f"[ ⚙️ ] {t('بيحلل')} — {detail}{extra}")
            else:
                st.info(f"[ ⏳ ] {t('في الطابور')} — {detail}")

        _ai_progress()

        if _state == "done" and not st.session_state.get("ai_parsed_script"):
            _res = ai_jobs.result(_job)
            if _res:
                try:
                    _payload = json.dumps({"scenes": _res["scenes"]}, ensure_ascii=False)
                    _parsed_ai = parse_json_script(_payload.encode("utf-8"),
                                                   known_characters=_known)
                    _parsed_ai["warnings"] = list(_res.get("warnings", [])) + \
                        list(_parsed_ai.get("warnings", []))
                    _parsed_ai["meta"] = _res.get("meta", {})
                    # مكتبة التحليلات: التحليل بيتحفظ على الحساب لوحده، بره المشروع،
                    # عشان لو ده المشروع الغلط يتستورد بعدين في الصح. عمره ما بيوقّع الشاشة.
                    _saved = analysis_library.save_job(
                        _job, fallback_owner=st.session_state.get("_auth_user"),
                        fallback_company=st.session_state.get("_cf_company"))
                    _parsed_ai["library_id"] = _saved
                    st.session_state["ai_parsed_script"] = _parsed_ai
                    st.rerun()
                except Exception as e:
                    st.error(f"{t('نتيجة الذكاء الاصطناعي مش مقروءة:')} "
                             f"{_user_error(e, 'ai result parse')}")
            else:
                st.error(t("التحليل خلص بس ملف النتيجة مش موجود. جرّب تاني."))
        if _state in ai_jobs.TERMINAL:
            if st.button(t("🧹 إخفاء نتيجة التحليل"), key="_ai_clear"):
                for _k in ("ai_job_id", "ai_parsed_script"):
                    st.session_state.pop(_k, None)
                st.rerun()

    _fast_parsed = st.session_state.get("parsed_script")
    _ai_parsed = st.session_state.get("ai_parsed_script")
    if _fast_parsed and _ai_parsed:
        _analysis_rtl_css()
        with st.container(key="cf_compare"):
            _render_source_picker(_fast_parsed, _ai_parsed)
        _choice = st.radio(
            t("اختار التحليل اللي هيتستورد:"),
            [t("🤖 الذكاء الاصطناعي"), t("🔍 التحليل السريع")],
            horizontal=True, key="_which_analysis")
        parsed = _ai_parsed if _choice == t("🤖 الذكاء الاصطناعي") else _fast_parsed
    else:
        parsed = _ai_parsed or _fast_parsed
    if not parsed and st.session_state.get("last_analysis"):
        # بعد ما المشاهد تتضاف، التحليل يفضل متاح بدل ما يختفي
        _analysis_rtl_css()
        with st.container(key="cf_analysis"):
            _render_analysis_dashboard(st.session_state["last_analysis"])
    if not parsed:
        # بعد الاستيراد (أو في زيارة تانية) التقرير يفضل متاح على آخر تحليل
        # اتعمل من المشروع ده في المكتبة، مش بس وقت ما النتيجة على الشاشة
        _drama_entry = (dramaturgy_panel.jobs.entry_for_project(st.session_state.get("_auth_user"), project_id)
                        if dramaturgy_panel.jobs.available() else None)
        if _drama_entry:
            with st.container(border=True, key="cf_drama_import"):
                dramaturgy_panel.render(st.session_state.get("_auth_user"), _drama_entry, key="import")
    if parsed:
        scenes = parsed["scenes"]
        for w in parsed["warnings"]:
            st.warning(w)
        if parsed.get("library_id"):
            # التحليل بقى محفوظ على الحساب — لو ده المشروع الغلط، مفيش حاجة ضاعت
            st.markdown(
                f'<div class="cf-lib-saved">📚 {t("التحليل ده اتحفظ في مكتبة التحليلات بتاعتك — لو ده مش المشروع الصح، استورده من هناك في أي مشروع تاني.")} '
                f'<a href="?page=library" target="_self">{t("افتح المكتبة")}</a></div>',
                unsafe_allow_html=True)
            # تقرير البناء الدرامي: بدوسة بس (بيكلّف)، وبيتحفظ على نفس التحليل في المكتبة
            with st.container(border=True, key="cf_drama_import"):
                dramaturgy_panel.render(st.session_state.get("_auth_user"),
                                        parsed["library_id"], key="import")

        st.success(f"{t('تم التعرف على')} {len(scenes)} {t('مشهد في الملف. راجعهم وعدّل أي حاجة غلط قبل التأكيد:')}")
        excluded_scene_indices = set()
        kept_characters_by_scene = {}
        for idx, sc in enumerate(scenes):
            title = (
                f"{t('مشهد')} {ltr(scene_label(sc))} — {ltr(fmt_int_ext(sc['int_ext'] or 'غير محدد'))} / "
                f"{fmt_day_night(sc['day_night'] or 'غير محدد')} — {sc['location_name'] or t('مكان غير محدد')}"
            )
            with st.expander(title):
                exclude = st.checkbox(
                    t("🚫 استبعد المشهد ده من الاستيراد (مثلاً لو ده صفحة عنوان مش مشهد حقيقي)"),
                    key=f"exclude_scene_{idx}",
                )
                if exclude:
                    excluded_scene_indices.add(idx)
                if sc["characters"]:
                    kept_characters_by_scene[idx] = multiselect(
                        t("الشخصيات المكتشفة — شيل أي حاجة مش اسم شخصية فعلي (زي نوع الفيلم أو التاريخ أو المكان)"),
                        options=sc["characters"], default=sc["characters"], key=f"chars_{idx}",
                    )
                else:
                    kept_characters_by_scene[idx] = []
                    st.caption(t("مفيش شخصيات اتكشفت في المشهد ده"))
                if sc.get("props"):
                    st.caption(f"🎬 {t('الإكسسوارات')}: {', '.join(sc['props'])}")
                else:
                    st.caption(t("🎬 مفيش إكسسوارات نشطة"))
                st.text(sc["notes"] if sc["notes"] else "—")

        # نسخة معاينة من غير ما نلمس بيانات الجلسة الأصلية، عشان لو المستخدم شال
        # شخصية بالغلط يقدر يرجعها من غير ما يعيد رفع الملف
        preview_scenes = []
        for idx, sc in enumerate(scenes):
            if idx in excluded_scene_indices:
                continue
            sc_view = dict(sc)
            sc_view["characters"] = kept_characters_by_scene.get(idx, sc["characters"])
            preview_scenes.append(sc_view)

        merge_map = {}
        _analysis_rtl_css()
        with st.container(key="cf_analysis"):
            _render_analysis_dashboard(preview_scenes)

        similar_groups = find_similar_name_groups(preview_scenes)
        if similar_groups:
            st.markdown("---")
            st.markdown(f"**{t('🧑‍🤝‍🧑 لقينا أسماء شخصيات متشابهة — هي نفس الشخصية؟')}**")
            for gi, group in enumerate(similar_groups):
                if gi > 0:
                    st.markdown('<hr class="cf-soft-sep">', unsafe_allow_html=True)
                choice = st.radio(
                    f"{t('الأسماء:')} {'، '.join(group)}",
                    options=["دمجهم في شخصية واحدة", "لأ، شخصيات مختلفة"],
                    format_func=t,
                    key=f"merge_choice_{gi}",
                    horizontal=True,
                )
                if choice == "دمجهم في شخصية واحدة":
                    default_canonical = max(group, key=len)
                    canonical = st.selectbox(
                        t("اختار الاسم اللي هيتسجل بيه في المشروع"),
                        options=group,
                        index=group.index(default_canonical),
                        key=f"merge_canonical_{gi}",
                    )
                    for name in group:
                        if name != canonical:
                            merge_map[name] = canonical

        location_merge_map = {}

        # كشف ذكي للأماكن مع الحالات الدرامية
        smart_location_matches = find_location_matches_with_states(preview_scenes)
        if smart_location_matches:
            st.markdown("---")
            st.markdown(f"**🎭 {t('كشف ذكي للحالات الدرامية')}**")
            st.caption(t(
                "البرنامج كشف أماكن تغيّرت بسبب الزمن أو أحداث درامية (حريق، تدمير، إلخ). "
                "يمكن ربطها تلقائياً كحالات لنفس المكان."
            ))
            for match in smart_location_matches:
                if match['state_changes']:
                    with st.expander(f"📍 {match['location']} - {', '.join(match['state_changes'])}"):
                        st.write(f"**الحالات المكتشفة:** {', '.join(match['state_changes'])}")
                        if match['suggested_variant']:
                            st.write(f"**الاسم المقترح للحالة:** {match['suggested_variant']}")
                        if match['matching_locations']:
                            st.write(f"**ربط مقترح:** {match['matching_locations'][0]['existing_location']['name']}")

        similar_location_groups = find_similar_location_groups(preview_scenes)
        if similar_location_groups:
            st.markdown("---")
            st.markdown(f"**{t('🏠 لقينا أماكن متشابهة — هي حالات مختلفة لنفس المكان؟')}**")
            st.caption(t(
                "مثال: \"سطح اليخت\" و\"سطح اليخت بعد لحظات\" غالبًا نفس المكان في وقتين مختلفين، "
                "مش مكانين منفصلين. لو دمجتهم، الاسم الأصلي هيتسجل كحالة (Variant) تحت المكان الرئيسي."
            ))
            for li, group in enumerate(similar_location_groups):
                if li > 0:
                    st.markdown('<hr class="cf-soft-sep">', unsafe_allow_html=True)
                loc_choice = st.radio(
                    f"{t('الأماكن:')} {'، '.join(group)}",
                    options=["دمجهم كحالات لنفس المكان الرئيسي", "لأ، أماكن مختلفة فعلاً"],
                    format_func=t,
                    key=f"loc_merge_choice_{li}",
                    horizontal=True,
                )
                if loc_choice == "دمجهم كحالات لنفس المكان الرئيسي":
                    default_loc_canonical = min(group, key=len)
                    loc_canonical = st.selectbox(
                        t("اختار اسم المكان الرئيسي اللي هيتسجل بيه"),
                        options=group,
                        index=group.index(default_loc_canonical),
                        key=f"loc_merge_canonical_{li}",
                    )
                    for name in group:
                        if name != loc_canonical:
                            location_merge_map[name] = loc_canonical

        if excluded_scene_indices:
            st.caption(f"{t('هيتستبعد')} {len(excluded_scene_indices)} {t('مشهد من الاستيراد حسب اختيارك فوق.')}")

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button(t("🔵 تأكيد وإضافة كل المشاهد للمشروع")):
                scenes_to_import = apply_character_merges(preview_scenes, merge_map)
                scenes_to_import = apply_location_merges(scenes_to_import, location_merge_map)
                # F3: استيراد فيه ١٤٣ مشهد بيكتب آلاف الصفوف. الصف الواحد ده
                # بيقول مين استورد وإمتى وكام مشهد — والتفاصيل في البيانات نفسها.
                with audit.action("import_script", "scenes", project_id=project_id) as _act:
                    summary = import_parsed_scenes(project_id, scenes_to_import, fetch_all, run_query)
                    _act.summary = f"استيراد سيناريو: {summary['scenes_added']} مشهد جديد"
                    _act.extra = {"مشاهد": summary["scenes_added"],
                                  "شخصيات جديدة": len(summary["characters_added"]),
                                  "أماكن جديدة": len(summary["locations_added"]),
                                  "إكسسوارات جديدة": len(summary["props_added"]),
                                  "مشاهد متخطاة": len(summary["scenes_skipped"])}
                msg = f"{t('تم إضافة')} {summary['scenes_added']} {t('مشهد جديد.')}"
                if summary["characters_added"]:
                    msg += f" {t('شخصيات جديدة:')} {'، '.join(summary['characters_added'])}."
                if summary["locations_added"]:
                    msg += f" {t('أماكن جديدة:')} {'، '.join(summary['locations_added'])}."
                if summary["props_added"]:
                    msg += f" {t('إكسسوارات جديدة:')} {'، '.join(summary['props_added'])}."
                if summary["scenes_skipped"]:
                    skipped = "، ".join(str(n) for n in summary["scenes_skipped"])
                    msg += f" {t('تم تخطي مشاهد أرقام')} ({skipped}) {t('لأنها موجودة بالفعل.')}"
                st.success(msg)

                st.session_state["last_analysis"] = list(scenes_to_import)

                # لازم نمسح النتيجتين. الاستيراد كان بيمسح parsed_script بس
                # بـ del، ولو التحليل جاي من الذكاء الاصطناعي المفتاح ده مش
                # موجود أصلًا — فكان بيرمي KeyError **بعد** ما البيانات
                # تتسجل فعلًا، فالمستخدم يشوف خطأ والنتيجة لسه على الشاشة
                # ويفتكر إن مفيش حاجة اتضافت.
                # لازم نعلّم التحليل إنه اتستورد، وإلا الاسترجاع بيرجّعه
                # على الشاشة في نفس اللحظة وكأن مفيش حاجة حصلت
                _done_job = st.session_state.get("ai_job_id")
                _clear_analysis_state()
                if _done_job:
                    ai_jobs.mark_imported(_done_job)
                st.rerun()
        with col_b:
            if st.button(t("🗑️ إلغاء ومسح النتائج")):
                # لازم نأرشف الجوب هنا كمان. مسح الحالة لوحده مش كفاية: أول
                # ما الصفحة تعيد التشغيل، الاسترجاع بيلاقي نفس التحليل المكتمل
                # ويرجّعه على الشاشة — فالزرار يبان كأنه مش شغال.
                _dismissed = st.session_state.get("ai_job_id")
                _clear_analysis_state()
                if _dismissed:
                    ai_jobs.mark_imported(_dismissed)
                st.rerun()
