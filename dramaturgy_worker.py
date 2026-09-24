#!/usr/bin/env python3
"""Worker تقرير البناء الدرامي — لـ /v1 بس (خدمة cimafast-dramaturgy-v1).

بيقرا الطلبات اللي dramaturgy_jobs.py كتبها في CIMAFAST_DRAMA_SPOOL، يبني
البرومبت من dramaturgy.py، يكلّم claude مرة واحدة، يتحقق من الرد
(dramaturgy.parse_response)، ويكتب التقرير في outbox. مابيلمسش قاعدة
البيانات خالص: التطبيق (مستخدم cimafast) هو اللي بيحفظ التقرير في مكتبة
التحليلات لما يلاقيه — نفس السبب اللي في spool.py: root بيكتب في SQLite
ممكن يسيب journal ملكه والتطبيق مايقدرش يفتحه.

ليه ملف لوحده ومش جوه /opt/cimafast-ai/worker.py: الملف ده مشترك مع worker
البرودكشن، وأي تعديل فيه بيوصل البرودكشن أول ما الخدمة بتاعته تعيد التشغيل.

الأمان — نفس قواعد worker.py بالظبط، لأن ملخص المشاهد نص جاي من سيناريو
اليوزر وبيتحول لبرومبت:
  --tools ""                 مفيش أي أداة تتنفذ
  --setting-sources ""       مايقراش أي settings (ولا بتاعة المشروع ولا /root)
  --mcp-config {} --strict-mcp-config   مفيش MCP
  cwd = فولدر مؤقت فاضي، عمره ما بيبقى جوه الريبو
وممنوع --bare (بيكسر تسجيل الدخول).
"""
import datetime as dt
import fcntl
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import traceback

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)
import dramaturgy  # noqa: E402  — موديول نقي: json وre بس، مفيش venv

ROOT = os.environ.get("CIMAFAST_DRAMA_SPOOL", "/var/lib/cimafast-v1/drama-jobs")
INBOX, STATUS, OUTBOX = (os.path.join(ROOT, d) for d in ("inbox", "status", "outbox"))
LOCKFILE = os.environ.get("CIMAFAST_DRAMA_LOCKFILE", "/run/cimafast-dramaturgy-v1.lock")
MODEL = os.environ.get("CIMAFAST_DRAMA_MODEL", "sonnet")
POLL_SECONDS = 3
CALL_TIMEOUT = 600
MIN_BUDGET_USD = 0.10          # السقف أقل من كده بيقطع المكالمة قبل ما ترد أصلًا
DEFAULT_BUDGET_USD = 1.00

FAILED_GENERIC = "مقدرناش نعمل التقرير المرة دي. التحليل نفسه زي ما هو، جرّب تاني بعد شوية."
FAILED_BUDGET = ("التقرير وقف قبل ما يخلص لأنه وصل سقف المصروف (اتصرف ${spent:.2f}). "
                 "التحليل نفسه زي ما هو.")


def log(msg):
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} dramaturgy-worker: {msg}", flush=True)


def write_atomic(path, payload):
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def set_status(jid, state, detail="", **extra):
    payload = {"state": state, "detail": detail, "heartbeat": time.time()}
    payload.update(extra)
    write_atomic(os.path.join(STATUS, f"{jid}.json"), payload)


def claimable():
    out = []
    for name in os.listdir(INBOX):
        if not name.endswith(".json") or name.endswith(".scenes.json") or ".tmp." in name:
            continue
        jid = name[:-5]
        if os.path.exists(os.path.join(STATUS, f"{jid}.json")):
            continue
        m = read_json(os.path.join(INBOX, name))
        if m:
            out.append(m)
    return sorted(out, key=lambda m: m.get("created_at", 0))


def call_claude(prompt, schema, budget, cwd):
    cmd = ["claude", "-p", "--model", MODEL,
           "--tools", "", "--setting-sources", "", "--no-session-persistence",
           "--mcp-config", '{"mcpServers":{}}', "--strict-mcp-config",
           "--output-format", "json", "--max-budget-usd", str(budget),
           "--json-schema", json.dumps(schema)]
    # البرومبت على stdin مش argument: سيناريو 140 مشهد ممكن يعدّي حد الـ argv
    proc = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = proc.communicate(input=prompt, timeout=CALL_TIMEOUT)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        proc.communicate()
        raise RuntimeError(f"claude call exceeded {CALL_TIMEOUT}s")
    spent = 0.0
    envelope = None
    if out:
        try:
            envelope = json.loads(out)
            spent = float(envelope.get("total_cost_usd") or 0)
        except (ValueError, AttributeError):
            envelope = None
    if proc.returncode != 0 or envelope is None or envelope.get("is_error"):
        # الـ envelope فيه usage طويل؛ أول 300 حرف منه مابيقولوش حاجة (ده اللي
        # حصل في أول تشغيلة حقيقية). بنسجّل الحقول اللي بتشرح السبب بس.
        env = envelope or {}
        summary = {k: env.get(k) for k in ("subtype", "stop_reason", "num_turns", "duration_ms",
                                           "total_cost_usd", "result") if env.get(k) is not None}
        reason = (err or "").strip() or json.dumps(summary, ensure_ascii=False)[:600] or out[:300]
        exc = RuntimeError(f"claude rc={proc.returncode}: {reason or '(no output)'}")
        exc.spent = spent
        # وصلنا سقف المصروف: ده قرار سقف مش عطل في الموديل، واليوزر لازم يعرف إن فيه فلوس اتصرفت
        exc.budget_hit = spent >= budget * 0.95
        raise exc
    body = envelope.get("structured_output") or envelope.get("result") or ""
    if not isinstance(body, str):
        body = json.dumps(body, ensure_ascii=False)
    return body, spent


class Heartbeat:
    """الشاشة بتسأل كل 3 ثواني — من غير نبض الحالة تبان واقفة."""

    def __init__(self, jid, detail, every=10):
        self.jid, self.detail, self.every = jid, detail, every
        self.started = time.time()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self._stop.wait(self.every):
            el = int(time.time() - self.started)
            set_status(self.jid, "running", f"{self.detail} · {el // 60}:{el % 60:02d}")

    def __enter__(self):
        set_status(self.jid, "running", self.detail)
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._thread.join(timeout=2)
        return False


def process(job, cwd_root):
    jid = job["job_id"]
    started = time.time()
    scenes = read_json(os.path.join(INBOX, f"{jid}.scenes.json"))
    if not isinstance(scenes, list) or not scenes:
        set_status(jid, "failed", "مفيش مشاهد في الطلب ده، فمش هيتعمل تقرير.")
        return
    budget = job.get("max_cost_usd") or DEFAULT_BUDGET_USD
    budget = max(MIN_BUDGET_USD, float(budget))
    spent = 0.0
    with tempfile.TemporaryDirectory(dir=cwd_root, prefix=f"{jid}-") as cwd:
        try:
            prompt = dramaturgy.build_prompt(scenes)
            with Heartbeat(jid, "بيقرا المشاهد ويبني هرم فرايتاج"):
                body, spent = call_claude(prompt, dramaturgy.RESPONSE_JSON_SCHEMA, budget, cwd)
            report = dramaturgy.parse_response(body, scenes)
            report = dramaturgy.with_meta(
                report, model=MODEL, cost_usd=round(spent, 4),
                generated_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
            report["meta"]["job_id"] = jid
            report["meta"]["estimate_usd"] = job.get("estimate_usd")
            report["meta"]["duration_s"] = round(time.time() - started, 1)
            # النتيجة الأول وبعدين الحالة: الشاشة عمرها ما تشوف done قبل الملف
            write_atomic(os.path.join(OUTBOX, f"{jid}.result.json"), {"report": report})
            set_status(jid, "done", f"{len(report['weaknesses'])} weak zone(s)", cost_usd=round(spent, 4))
            log(f"{jid}: done, {len(scenes)} scene(s), ${spent:.4f}, {time.time() - started:.0f}s")
        except dramaturgy.DramaturgyError as exc:
            # رسالة عربي جاهزة من dramaturgy.py — تتعرض لليوزر زي ما هي
            log(f"{jid}: rejected: {exc}")
            set_status(jid, "failed", str(exc), cost_usd=round(spent, 4), user_message=True)
        except Exception as exc:  # noqa: BLE001
            spent = getattr(exc, "spent", spent) or spent
            log(f"{jid}: FAILED {type(exc).__name__}: {exc}\n{traceback.format_exc(limit=3)}")
            # التفاصيل التقنية في اللوج بس؛ اليوزر ياخد جملة مفهومة
            msg = (FAILED_BUDGET.format(spent=spent) if getattr(exc, "budget_hit", False)
                   else FAILED_GENERIC)
            set_status(jid, "failed", msg, cost_usd=round(spent, 4), user_message=True)


def recover_orphans():
    """أي job حالته running وقت ما الـ worker بيبدأ مات مع العملية اللي قبلنا
    (الـ lock بيضمن إن مفيش نسخة تانية شغالة) — نقفله بدل ما يفضل معلّق."""
    for name in os.listdir(STATUS):
        if not name.endswith(".json") or ".tmp." in name:
            continue
        info = read_json(os.path.join(STATUS, name)) or {}
        if info.get("state") == "running":
            set_status(name[:-5], "failed", FAILED_GENERIC, user_message=True)
            log(f"{name[:-5]}: marked failed (worker restarted mid-run)")


def main():
    fh = open(LOCKFILE, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("another dramaturgy worker is already running; refusing to start")
    for d in (INBOX, STATUS, OUTBOX):
        os.makedirs(d, exist_ok=True)
    recover_orphans()
    cwd_root = tempfile.mkdtemp(prefix="cimafast-drama-")
    stopping = {"now": False}

    def stop(*_):
        log("shutdown requested; finishing the current job")
        stopping["now"] = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    log(f"started (spool {ROOT}, model {MODEL})")
    while not stopping["now"]:
        jobs = claimable()
        if not jobs:
            time.sleep(POLL_SECONDS)
            continue
        job = jobs[0]
        set_status(job["job_id"], "running", "starting")
        log(f"claimed {job['job_id']} (library entry {job.get('entry_id')})")
        process(job, cwd_root)
    log("stopped")


if __name__ == "__main__":
    main()
