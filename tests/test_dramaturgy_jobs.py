"""تقرير البناء الدرامي من أول الدوسة لحد ما يتحفظ على التحليل في المكتبة:
dramaturgy_jobs.py (التطبيق) ← الطابور ← dramaturgy_worker.py (الـ worker).

    venv/bin/python tests/test_dramaturgy_jobs.py

قاعدة بيانات مؤقتة وطابور مؤقت — ومكالمة claude مستبدلة برد ثابت، فمفيش
فلوس بتتصرف ومفيش حاجة بتلمس /v1 أو الإنتاج.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
_TMP = tempfile.mkdtemp(prefix="cimafast-drama-")
os.environ["STUDIO_DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ["CIMAFAST_AI_SPOOL"] = os.path.join(_TMP, "ai-jobs")
os.environ["CIMAFAST_DRAMA_SPOOL"] = os.path.join(_TMP, "drama-jobs")
os.environ["CIMAFAST_DRAMA_LOCKFILE"] = os.path.join(_TMP, "drama.lock")
os.environ.pop("DATABASE_URL", None)

import accounts  # noqa: E402
import analysis_library as lib  # noqa: E402
import auth  # noqa: E402
import database  # noqa: E402
import dramaturgy  # noqa: E402
import dramaturgy_jobs as jobs  # noqa: E402
import dramaturgy_worker as worker  # noqa: E402
import permissions  # noqa: E402
import test_dramaturgy as fixtures  # noqa: E402

database.init_db()
_results = []

accounts.migrate_accounts({"melzayat": auth.hash_password("owner-pass-123", iterations=1000),
                           "producer": auth.hash_password("producer-pass-1", iterations=1000)})
COMPANY = accounts.companies_for("producer")[0]["id"]
accounts.add_member("melzayat", COMPANY, "watcher", role="viewer")
OTHER, _ = accounts.create_company("melzayat", "شركة تانية", "other_admin")

ANALYSIS = {"scenes": [dict(s, notes=f"ملخص مشهد {s['scene_number']}") for s in fixtures.SCENES],
            "warnings": [], "meta": {}}
with permissions.system():
    ENTRY_ID, _ = lib.save(ANALYSIS, script_name="سيناريو تجربة.pdf", owner="producer",
                           company_id=COMPANY)
for d in (worker.INBOX, worker.STATUS, worker.OUTBOX):
    os.makedirs(d, exist_ok=True)


def test(fn):
    _results.append(fn)
    return fn


def _raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc as e:
        return e
    raise AssertionError(f"{getattr(fn, '__name__', fn)} did not raise {exc.__name__}")


def _entry(user="producer"):
    return lib.get(user, ENTRY_ID)


def _run_worker(reply, spent=0.031):
    """دورة واحدة للـ worker، بمكالمة claude مستبدلة."""
    calls = []

    def fake_call(prompt, schema, budget, cwd):
        calls.append({"prompt": prompt, "budget": budget, "cwd": cwd})
        if isinstance(reply, Exception):
            raise reply
        return reply, spent
    real = worker.call_claude
    worker.call_claude = fake_call
    try:
        for job in worker.claimable():
            worker.set_status(job["job_id"], "running", "starting")
            worker.process(job, _TMP)
    finally:
        worker.call_claude = real
    return calls


@test
def test_unavailable_without_spool_env():
    saved = os.environ.pop("CIMAFAST_DRAMA_SPOOL")
    try:
        assert not jobs.available(), "من غير الطابور الزرار لازم يختفي (البرودكشن)"
    finally:
        os.environ["CIMAFAST_DRAMA_SPOOL"] = saved
    assert jobs.available()


@test
def test_viewer_and_other_company_cannot_run():
    assert not jobs.can_run("watcher", _entry("watcher"))
    _raises(permissions.Denied, jobs.start, "watcher", _entry("watcher"))
    entry = _entry()
    assert not jobs.can_run("other_admin", entry), "شركة تانية مايصحش تصرف على تحليل مش بتاعها"
    assert jobs.can_run("producer", entry)
    assert not os.listdir(worker.INBOX), "الرفض مايكتبش أي طلب في الطابور"


@test
def test_full_round_trip_saves_report_on_library_entry():
    entry = _entry()
    jid = jobs.start("producer", entry)
    assert jobs.active_job(ENTRY_ID) == jid
    assert jobs.start("producer", entry) == jid, "دوسة مكررة مابتبعتش طلب تاني"
    manifest = json.load(open(os.path.join(worker.INBOX, f"{jid}.json"), encoding="utf-8"))
    assert manifest["max_cost_usd"] == dramaturgy.estimate(jobs.scenes_of(entry))[2]

    calls = _run_worker(json.dumps(fixtures._valid_payload(), ensure_ascii=False))
    assert len(calls) == 1
    assert "عدد المشاهد (N) = 10" in calls[0]["prompt"]
    assert not calls[0]["cwd"].startswith(ROOT), "المكالمة عمرها ما تتعمل جوه الريبو"
    assert jobs.status(jid)["state"] == "done"
    assert jobs.active_job(ENTRY_ID) is None

    entry = _entry()
    assert jobs.collect("producer", entry) is True
    assert jobs.collect("producer", _entry()) is False, "نفس التقرير مايتحفظش مرتين"
    report = jobs.report_of(_entry())
    assert report and report["scene_count"] == 10
    assert report["meta"]["cost_usd"] == 0.031 and report["meta"]["job_id"] == jid
    # F3: التشغيل اتسجّل حدث استخدام، والحفظ صف في سجل النشاط
    ev = database.fetch_all("SELECT username, detail FROM usage_events WHERE event='ai' "
                            "AND target=?", (dramaturgy.REPORT_KEY,))
    assert ev and ev[-1]["username"] == "producer" and jid in ev[-1]["detail"]
    assert database.fetch_all("SELECT id FROM audit_log WHERE action='library_report'")
    # بيطلع مع ملف المكتبة المصدّر
    _, raw = lib.to_file(_entry(), exported_by="producer")
    assert dramaturgy.REPORT_KEY in json.loads(raw)["analysis"]["reports"]


@test
def test_rerun_same_scenes_replaces_saved_report():
    first = jobs.report_of(_entry())["meta"]["generated_at"]
    jid = jobs.start("producer", _entry())
    assert jobs.status(jid)["state"] == "queued", "الإعادة بتمسح حالة التشغيلة القديمة"
    import time
    time.sleep(1.1)                       # generated_at بالثانية
    _run_worker(json.dumps(fixtures._valid_payload(), ensure_ascii=False), spent=0.02)
    assert jobs.collect("producer", _entry()) is True
    rep = jobs.report_of(_entry())
    assert rep["meta"]["generated_at"] != first and rep["meta"]["cost_usd"] == 0.02


@test
def test_bad_reply_fails_with_arabic_message_and_keeps_old_report():
    before = jobs.report_of(_entry())
    bad = fixtures._valid_payload()
    bad["tension_curve"] = bad["tension_curve"][:3]
    # نفس المحتوى → نفس رقم الـ job؛ start بيمسح حالته القديمة ويعيد الطلب
    jid = jobs.start("producer", _entry())
    _run_worker(json.dumps(bad, ensure_ascii=False))
    info = jobs.status(jid)
    assert info["state"] == "failed" and info.get("user_message")
    assert "منحنى التوتر" in info["detail"], info["detail"]
    assert "Traceback" not in info["detail"]
    assert jobs.collect("producer", _entry()) is False
    assert jobs.report_of(_entry()) == before, "رد بايظ مايمسحش التقرير اللي قبله"


@test
def test_worker_crash_shows_generic_arabic_not_raw_exception():
    jid = jobs.start("producer", _entry())
    _run_worker(RuntimeError("claude rc=1: /root/.claude secret path"))
    info = jobs.status(jid)
    assert info["state"] == "failed" and info["detail"] == worker.FAILED_GENERIC
    assert "/root" not in info["detail"]


@test
def test_budget_hit_tells_user_money_was_spent():
    """أول تشغيلة حقيقية (2026-09-23) وقفت عند السقف — الرسالة لازم تقول كده بدل "جرّب تاني"."""
    jid = jobs.start("producer", _entry())
    exc = RuntimeError("claude rc=1: budget")
    exc.spent, exc.budget_hit = 0.38, True
    _run_worker(exc)
    info = jobs.status(jid)
    assert info["state"] == "failed" and "سقف المصروف" in info["detail"] and "0.38" in info["detail"]
    assert info["cost_usd"] == 0.38


@test
def test_orphaned_running_job_is_released_on_worker_start():
    jid = jobs.start("producer", _entry())
    worker.set_status(jid, "running", "starting")
    worker.recover_orphans()
    assert jobs.status(jid)["state"] == "failed"
    assert jobs.active_job(ENTRY_ID) is None, "الزرار مايفضلش مقفول بعد إعادة تشغيل الـ worker"


@test
def test_script_analysis_spool_is_untouched():
    """التقرير له طابور لوحده: مكتبة التحليلات مابتشوفهوش كتحليل سيناريو."""
    assert not os.path.exists(os.environ["CIMAFAST_AI_SPOOL"]) or \
        not os.listdir(os.path.join(os.environ["CIMAFAST_AI_SPOOL"], "outbox"))
    assert lib.sync_from_spool() == 0


@test
def test_exports_render_with_curve():
    import export
    rep = jobs.report_of(_entry())
    png = export.dramaturgy_curve_png(rep, "ar")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    pdf = export.build_dramatic_structure_pdf(rep, "سيناريو تجربة.pdf", "ar")
    assert pdf[:5] == b"%PDF-" and (b"/Image" in pdf or b"/XObject" in pdf)
    docx_bytes = export.build_dramatic_structure_word(rep, "سيناريو تجربة.pdf", "en")
    assert docx_bytes[:2] == b"PK" and b"word/media/" in docx_bytes


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
