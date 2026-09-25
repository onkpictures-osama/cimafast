#!/usr/bin/env python3
"""Worker «ارسمها لي» (رسمة المكان من فوق) — لـ /v1 بس (خدمة cimafast-plan-v1).

نفس نظام dramaturgy_worker.py: plan_jobs.py (التطبيق، مستخدم cimafast) بيكتب
الطلب في inbox، والـ worker (root، عشان بيانات دخول claude) بيكتب في status
وoutbox بس، ومابيلمسش قاعدة البيانات — التطبيق بيحفظ الرسمة لما يلاقيها.

نفس قيود الأمان (النص جاي من سيناريو اليوزر): --tools "" و--setting-sources ""
ومفيش MCP، والـ cwd فولدر مؤقت فاضي.
"""
import fcntl
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import traceback

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)
import plan_ai  # noqa: E402  — موديول نقي

ROOT = os.environ.get("CIMAFAST_PLAN_SPOOL", "/var/lib/cimafast-v1/plan-jobs")
INBOX, STATUS, OUTBOX = (os.path.join(ROOT, d) for d in ("inbox", "status", "outbox"))
LOCKFILE = os.environ.get("CIMAFAST_PLAN_LOCKFILE", "/run/cimafast-plan-v1.lock")
MODEL = os.environ.get("CIMAFAST_PLAN_MODEL", "sonnet")
BUDGET_USD = float(os.environ.get("CIMAFAST_PLAN_BUDGET_USD", "0.30"))
POLL_SECONDS = 2
CALL_TIMEOUT = 240
FAILED = "مقدرناش نرسم المكان المرة دي. جرّب تاني بعد شوية، أو ارسمه بإيدك."


def log(msg):
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} plan-worker: {msg}", flush=True)


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
        if not name.endswith(".json") or ".tmp." in name:
            continue
        jid = name[:-5]
        if os.path.exists(os.path.join(STATUS, f"{jid}.json")):
            continue
        m = read_json(os.path.join(INBOX, name))
        if isinstance(m, dict) and m.get("job_id") == jid:
            out.append(m)
    return sorted(out, key=lambda m: m.get("created_at", 0))


def call_claude(prompt, cwd):
    cmd = ["claude", "-p", "--model", MODEL,
           "--tools", "", "--setting-sources", "", "--no-session-persistence",
           "--mcp-config", '{"mcpServers":{}}', "--strict-mcp-config",
           "--output-format", "json", "--max-budget-usd", str(BUDGET_USD),
           "--json-schema", json.dumps(plan_ai.RESPONSE_JSON_SCHEMA)]
    proc = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = proc.communicate(input=prompt, timeout=CALL_TIMEOUT)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        proc.communicate()
        raise RuntimeError(f"claude call exceeded {CALL_TIMEOUT}s")
    try:
        env = json.loads(out)
    except ValueError:
        env = None
    if proc.returncode != 0 or not isinstance(env, dict) or env.get("is_error"):
        raise RuntimeError(f"claude rc={proc.returncode}: {(err or '').strip()[:300] or (out or '')[:300]}")
    body = env.get("structured_output") or env.get("result") or ""
    return body, float(env.get("total_cost_usd") or 0)


def process(job, cwd_root):
    jid = job["job_id"]
    started = time.time()
    with tempfile.TemporaryDirectory(dir=cwd_root, prefix=f"{jid}-") as cwd:
        try:
            body, spent = call_claude(plan_ai.build_prompt(job.get("context") or {}), cwd)
            plan = plan_ai.parse_response(body)
            write_atomic(os.path.join(OUTBOX, f"{jid}.result.json"), {"plan": plan, "cost_usd": round(spent, 4)})
            set_status(jid, "done", f"{len(plan['items'])} item(s)", cost_usd=round(spent, 4))
            log(f"{jid}: done, {len(plan['items'])} items, ${spent:.4f}, {time.time() - started:.0f}s")
        except Exception as exc:  # noqa: BLE001
            log(f"{jid}: FAILED {type(exc).__name__}: {exc}\n{traceback.format_exc(limit=3)}")
            set_status(jid, "failed", FAILED)


def main():
    fh = open(LOCKFILE, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("another plan worker is already running; refusing to start")
    for d in (INBOX, STATUS, OUTBOX):
        os.makedirs(d, exist_ok=True)
    for name in os.listdir(STATUS):           # شغل مات مع العملية اللي قبلنا
        info = read_json(os.path.join(STATUS, name)) or {}
        if name.endswith(".json") and info.get("state") == "running":
            set_status(name[:-5], "failed", FAILED)
    cwd_root = tempfile.mkdtemp(prefix="cimafast-plan-")
    stopping = {"now": False}

    def stop(*_):
        stopping["now"] = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log(f"started (spool {ROOT}, model {MODEL})")
    while not stopping["now"]:
        jobs = claimable()
        if not jobs:
            time.sleep(POLL_SECONDS)
            continue
        set_status(jobs[0]["job_id"], "running", "drawing")
        process(jobs[0], cwd_root)
    log("stopped")


if __name__ == "__main__":
    main()
