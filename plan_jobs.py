"""🤖 «ارسمها لي» — جانب التطبيق من طابور الرسمة (plan_worker.py بيرد).

نفس قواعد dramaturgy_jobs.py: التطبيق بيكتب في inbox بس (والعلامات بتاعته
هو: ‎.applied‎ و‎.seen‎)، والـ worker في status وoutbox. الميزة شغالة بس لو
CIMAFAST_PLAN_SPOOL متظبط (على /v1)؛ من غيره الزرار مابيظهرش.
"""
from __future__ import annotations

import json
import os
import time

import audit
import permissions
import repo
from database import fetch_all

STALE_SECONDS = 10 * 60


def spool_root():
    return os.environ.get("CIMAFAST_PLAN_SPOOL") or None


def available():
    return spool_root() is not None


def _dirs():
    root = spool_root()
    if not root:
        raise RuntimeError("رسم المكان بالذكاء الاصطناعي مش متاح على النسخة دي.")
    return tuple(os.path.join(root, d) for d in ("inbox", "status", "outbox"))


def _write_atomic(path, payload):
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    os.replace(tmp, path)


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def context(project_id, location_id):
    """المكان ووصفه وحالاته ونص المشاهد اللي بتحصل فيه — ده كل اللي الـ AI بيشوفه."""
    loc = fetch_all("SELECT name, base_description FROM locations WHERE id=? AND project_id=?",
                    (location_id, project_id))
    if not loc:
        raise ValueError("location is not in this project")
    variants = fetch_all("SELECT variant_name, description FROM location_variants WHERE location_id=? ORDER BY id",
                         (location_id,))
    scenes = fetch_all("""SELECT s.notes FROM scenes s JOIN location_variants v ON v.id=s.location_variant_id
                          WHERE v.location_id=? AND s.project_id=? AND COALESCE(s.notes,'')<>''
                          ORDER BY s.episode_number, s.scene_number LIMIT 8""", (location_id, project_id))
    return {"location": loc[0]["name"], "base_description": loc[0]["base_description"] or "",
            "variants": [{"name": v["variant_name"], "description": v["description"] or ""} for v in variants],
            "scenes": [s["notes"] for s in scenes]}


def _prefix(project_id, location_id):
    return f"p{int(project_id)}-l{int(location_id)}-"


def latest(project_id, location_id):
    """آخر طلب للمكان ده بحالته: {job_id, state, detail, applied, seen, result} أو None."""
    if not (available() and project_id and location_id):
        return None
    inbox, status_dir, outbox = _dirs()
    if not os.path.isdir(inbox):
        return None
    prefix = _prefix(project_id, location_id)
    names = sorted((n for n in os.listdir(inbox) if n.startswith(prefix) and n.endswith(".json") and ".tmp." not in n),
                   reverse=True)
    if not names:
        return None
    jid = names[0][:-5]
    m = _read(os.path.join(inbox, names[0])) or {}
    info = _read(os.path.join(status_dir, f"{jid}.json")) or {"state": "queued", "detail": ""}
    state = info.get("state")
    if state == "queued" and time.time() - float(m.get("created_at") or 0) > STALE_SECONDS:
        state = "failed"
        info["detail"] = "الطلب ماتستلمش — جرّب تاني."
    if state == "running" and time.time() - float(info.get("heartbeat") or 0) > STALE_SECONDS:
        state = "failed"
    return {"job_id": jid, "state": state, "detail": info.get("detail") or "",
            "project_id": m.get("project_id"), "location_id": m.get("location_id"),
            "applied": os.path.exists(os.path.join(inbox, f"{jid}.applied")),
            "seen": os.path.exists(os.path.join(inbox, f"{jid}.seen")),
            "result": _read(os.path.join(outbox, f"{jid}.result.json")) if state == "done" else None}


def submit(project_id, location_id, username):
    permissions.require("run_ai")
    job = latest(project_id, location_id)
    if job and job["state"] in ("queued", "running"):
        return job["job_id"]
    inbox, _, _ = _dirs()
    os.makedirs(inbox, exist_ok=True)
    jid = f"{_prefix(project_id, location_id)}{int(time.time() * 1000)}"
    _write_atomic(os.path.join(inbox, f"{jid}.json"), {
        "job_id": jid, "project_id": int(project_id), "location_id": int(location_id),
        "requested_by": username, "created_at": time.time(), "context": context(project_id, location_id)})
    audit.event("ai", target="location_plan", username=username, project_id=project_id,
                detail={"location_id": int(location_id), "job_id": jid})
    return jid


def _mark(job, suffix):
    inbox, _, _ = _dirs()
    with open(os.path.join(inbox, f"{job['job_id']}.{suffix}"), "w") as fh:
        fh.write(str(time.time()))


def apply(project_id, job):
    """الرسمة اللي رجعت → الرسمة الافتراضية للمكان (source=ai)، مرة واحدة."""
    if int(job.get("project_id") or 0) != int(project_id):
        raise ValueError("job is for another project")
    plan = (job.get("result") or {}).get("plan")
    repo.save_location_plan(project_id, int(job["location_id"]), 0, plan, source="ai",
                            updated_by="🤖 AI")
    _mark(job, "applied")


def mark_seen(job):
    _mark(job, "seen")
