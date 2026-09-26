#!/usr/bin/env python3
"""Worker مساعد البرنامج — لـ /v1 بس (خدمة cimafast-assistant-v1).

نفس نظام plan_worker.py: assistant_jobs.py (التطبيق) بيكتب السؤال والبرومبت
الجاهز في inbox، والـ worker (root، عشان بيانات دخول claude) بيكتب في status
وoutbox بس ومابيلمسش قاعدة البيانات. نفس قيود الأمان: --tools "" و
--setting-sources "" ومفيش MCP وcwd فاضي — السؤال نص جاي من اليوزر.
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
from concurrent.futures import ThreadPoolExecutor

ROOT = os.environ.get("CIMAFAST_ASSISTANT_SPOOL", "/var/lib/cimafast-v1/assistant-jobs")
INBOX, STATUS, OUTBOX = (os.path.join(ROOT, d) for d in ("inbox", "status", "outbox"))
LOCKFILE = os.environ.get("CIMAFAST_ASSISTANT_LOCKFILE", "/run/cimafast-assistant-v1.lock")
MODEL = os.environ.get("CIMAFAST_ASSISTANT_MODEL", "haiku")
BUDGET_USD = float(os.environ.get("CIMAFAST_ASSISTANT_BUDGET_USD", "0.08"))
PARALLEL = int(os.environ.get("CIMAFAST_ASSISTANT_PARALLEL", "3"))   # كذا يوزر بيسألوا في نفس الوقت
POLL_SECONDS = 0.7
CALL_TIMEOUT = 120
FAILED = "المساعد مش قادر يرد دلوقتي. جرّب تاني بعد شوية."


def log(msg):
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} assistant-worker: {msg}", flush=True)


def write_atomic(path, payload):
    tmp = f"{path}.tmp.{os.getpid()}.{time.monotonic_ns()}"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    os.replace(tmp, path)


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def set_status(jid, state, **extra):
    write_atomic(os.path.join(STATUS, f"{jid}.json"), dict(state=state, heartbeat=time.time(), **extra))


def claimable(taken):
    out = []
    for name in os.listdir(INBOX):
        if not name.endswith(".json") or ".tmp." in name:
            continue
        jid = name[:-5]
        if jid in taken or os.path.exists(os.path.join(STATUS, f"{jid}.json")):
            continue
        m = read_json(os.path.join(INBOX, name))
        if isinstance(m, dict) and m.get("job_id") == jid and isinstance(m.get("prompt"), str):
            out.append(m)
    return sorted(out, key=lambda m: m.get("created_at", 0))


def call_claude(prompt, cwd):
    cmd = ["claude", "-p", "--model", MODEL,
           "--tools", "", "--setting-sources", "", "--no-session-persistence",
           "--mcp-config", '{"mcpServers":{}}', "--strict-mcp-config",
           "--output-format", "json", "--max-budget-usd", str(BUDGET_USD)]
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
    return str(env.get("result") or ""), float(env.get("total_cost_usd") or 0)


def process(job, cwd_root):
    jid = job["job_id"]
    started = time.time()
    with tempfile.TemporaryDirectory(dir=cwd_root, prefix=f"{jid}-") as cwd:
        try:
            answer, spent = call_claude(job["prompt"], cwd)
            write_atomic(os.path.join(OUTBOX, f"{jid}.result.json"), {"answer": answer, "cost_usd": round(spent, 5)})
            set_status(jid, "done", cost_usd=round(spent, 5))
            log(f"{jid}: done ${spent:.4f} {time.time() - started:.1f}s")
        except Exception as exc:  # noqa: BLE001
            log(f"{jid}: FAILED {type(exc).__name__}: {exc}\n{traceback.format_exc(limit=2)}")
            set_status(jid, "failed", detail=FAILED)


def main():
    fh = open(LOCKFILE, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("another assistant worker is already running; refusing to start")
    for d in (INBOX, STATUS, OUTBOX):
        os.makedirs(d, exist_ok=True)
    for name in os.listdir(STATUS):
        info = read_json(os.path.join(STATUS, name)) or {}
        if name.endswith(".json") and info.get("state") == "running":
            set_status(name[:-5], "failed", detail=FAILED)
    cwd_root = tempfile.mkdtemp(prefix="cimafast-assistant-")
    stopping = {"now": False}
    signal.signal(signal.SIGTERM, lambda *_: stopping.update(now=True))
    signal.signal(signal.SIGINT, lambda *_: stopping.update(now=True))
    log(f"started (spool {ROOT}, model {MODEL}, parallel {PARALLEL})")
    running = {}
    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        while not stopping["now"]:
            for jid in [j for j, f in running.items() if f.done()]:
                running.pop(jid)
            free = PARALLEL - len(running)
            if free > 0:
                for job in claimable(set(running))[:free]:
                    set_status(job["job_id"], "running")
                    running[job["job_id"]] = pool.submit(process, job, cwd_root)
            time.sleep(POLL_SECONDS)
    log("stopped")


if __name__ == "__main__":
    main()
