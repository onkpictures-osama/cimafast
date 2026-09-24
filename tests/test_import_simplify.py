"""شاشة الاستيراد المبسطة (المالك 2026-09-24).

    venv/bin/python tests/test_import_simplify.py

بيقفل: CimaFast AI Inspector بيبدأ من دوسة واحدة (من غير شاشة تقدير و"ابدأ
التحليل")، بالسقف المحسوب؛ والعداد بيعد بالثانية على جهاز اليوزر وسكريبته
مفيهوش حرف يخلّي st.html يمسحه. الـ AI الحقيقي مابيتنادهش (بيكلّف فلوس).
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_results = []


def test(fn):
    _results.append(fn)
    return fn


def _app_start():
    import os
    import sys
    sys.path.insert(0, os.environ["_IS_ROOT"])
    import streamlit as st
    import views.import_tab as it
    calls = st.session_state.setdefault("_calls", [])
    it.ai_jobs.estimate = lambda md: (3, 0.4, 1.5)
    it.ai_jobs.start = lambda md, pid, fn, known_characters=None, max_cost_usd=None: (
        calls.append((pid, fn, max_cost_usd)) or "job-1")
    it.audit.event = lambda *a, **k: None
    if not calls:
        it._start_ai("مشهد 1 - داخلي - نهار - شقة", 7, "script.txt", [])
    st.write("started", st.session_state.get("ai_job_id"), len(calls))


@test
def test_ai_starts_in_one_click_with_the_ceiling():
    from streamlit.testing.v1 import AppTest
    os.environ["_IS_ROOT"] = ROOT
    at = AppTest.from_function(_app_start, default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    assert at.session_state["_calls"] == [(7, "script.txt", 1.5)], at.session_state["_calls"]
    assert at.session_state["ai_job_id"] == "job-1"


@test
def test_no_estimate_confirm_step_left_in_the_screen():
    src = open(os.path.join(ROOT, "views", "import_tab.py"), encoding="utf-8").read()
    assert "✅ ابدأ التحليل" not in src and "تكلفة تقديرية" not in src
    # الحاجة الوحيدة اللي بتوقف: ملف مش شكله سيناريو (الـ AI هيخترع مشاهد)
    assert "كمّل بالرغم من كده" in src and "_conf < 0.3" in src


@test
def test_timer_script_survives_st_html():
    import views.import_tab as it
    sent = []
    real = it.st.html
    it.st.html = lambda body, **kw: sent.append(body)
    try:
        it._live_timer(1_700_000_000.0)
    finally:
        it.st.html = real
    html = sent[0]
    inner = html.split("<script>", 1)[1].rsplit("</script>", 1)[0]
    assert "<" not in inner, "st.html بيمسح السكريبت لو فيه حرف أصغر من"
    assert "setInterval(tick,1000)" in inner and "1700000000000" in inner


def main():
    failed = 0
    for fn in _results:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except Exception as exc:
            failed += 1
            print(f"  FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(_results) - failed}/{len(_results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
