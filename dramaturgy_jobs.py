"""تشغيل تقرير البناء الدرامي من التطبيق — جانب التطبيق من الطابور.

التطبيق بيشتغل بمستخدم cimafast ومايقدرش يكلّم claude (بيانات الدخول في
/root/.claude). فبنكتب الطلب في طابور ملفات، وdramaturgy_worker.py (root،
خدمة cimafast-dramaturgy-v1) بيقراه ويكتب النتيجة. نفس قواعد spool.py في
/opt/cimafast-ai: التطبيق بيكتب في inbox بس، والـ worker في status وoutbox بس،
وكل كتابة tmp + os.replace، فمفيش ملف بيتكتب من الاتنين.

ليه طابور لوحده ومش طابور التحليل (/var/lib/cimafast-v1/ai-jobs):
- worker.py هناك مشترك مع البرودكشن — تعديله تعديل برودكشن محتاج موافقة المالك.
- مكتبة التحليلات (sync_from_spool) بتقرا أي نتيجة في outbox هناك كأنها تحليل.

الميزة شغالة بس لو CIMAFAST_DRAMA_SPOOL متظبط (drop-in على cimafast-v1). من
غيره الزرار مابيظهرش خالص — فالكود ده لو وصل البرودكشن مع أي دفعة مش هيغيّر
حاجة هناك لحد ما حد يعمل للبرودكشن worker وطابور بتوعه بموافقة المالك.

الموديول ده مابيستوردش Streamlit.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

import accounts
import analysis_library as lib
import audit
import dramaturgy
import permissions

TERMINAL = ("done", "failed")
STALE_SECONDS = 20 * 60        # job من غير heartbeat الوقت ده كله يبقى ميت، نسمح بإعادة التشغيل


def spool_root():
    return os.environ.get("CIMAFAST_DRAMA_SPOOL") or None


def available():
    return spool_root() is not None


def _dirs():
    root = spool_root()
    if not root:
        raise RuntimeError("تقرير البناء الدرامي مش متاح على النسخة دي.")
    return tuple(os.path.join(root, d) for d in ("inbox", "status", "outbox"))


def _write_atomic(path, payload):
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


# --- المشاهد والتكلفة ----------------------------------------------------------------

def scenes_of(entry):
    """مشاهد التحليل المحفوظ بنفس الشكل اللي الاستيراد بيقبله (فيه scene_suffix)."""
    return lib.parsed_scenes(entry["payload"])["scenes"]


def estimate(entry):
    """(عدد المشاهد، التكلفة المتوقعة، السقف) من dramaturgy.estimate()."""
    return dramaturgy.estimate(scenes_of(entry))


def report_of(entry):
    rep = ((entry.get("payload") or {}).get("reports") or {}).get(dramaturgy.REPORT_KEY)
    return rep if isinstance(rep, dict) and rep.get("stages") else None


def job_id(entry_id, scenes):
    """بصمة المحتوى: دبل كليك أو rerun مايبعتش نفس الطلب مرتين."""
    digest = hashlib.sha256(json.dumps(scenes, ensure_ascii=False, sort_keys=True,
                                       default=str).encode("utf-8")).hexdigest()[:16]
    return f"lib{int(entry_id)}-{digest}"


# --- الصلاحيات (F2) --------------------------------------------------------------------

def can_run(username, entry):
    """التشغيل بيكلّف فلوس: لازم دور غير "مشاهدة" في شركة التحليل نفسه (مش
    الشركة المفتوحة دلوقتي)، أو صاحب التحليل لو من غير شركة، أو المشغّل."""
    if not username:
        return False
    import admin_users
    if not admin_users.feature_on(username, "dramaturgy"):
        return False
    u = accounts.user(username)
    if u and u["is_operator"]:
        return True
    cid = entry.get("company_id")
    if cid is None:
        return entry.get("owner_username") == username
    role = accounts.role_in(username, cid)
    return bool(role) and permissions.can(role, "run_ai")


# --- الطابور -----------------------------------------------------------------------

def status(jid):
    _, status_dir, _ = _dirs()
    return _read(os.path.join(status_dir, f"{jid}.json")) or {"state": "queued", "detail": ""}


def result(jid):
    _, _, outbox = _dirs()
    return _read(os.path.join(outbox, f"{jid}.result.json"))


def _jobs_for(entry_id):
    """كل الطلبات اللي اتبعتت للتحليل ده، الأحدث الأول: [(jid، manifest)]."""
    inbox, _, _ = _dirs()
    if not os.path.isdir(inbox):
        return []
    out = []
    prefix = f"lib{int(entry_id)}-"
    for name in os.listdir(inbox):
        if (name.startswith(prefix) and name.endswith(".json") and ".tmp." not in name
                and not name.endswith(".scenes.json")):
            m = _read(os.path.join(inbox, name))
            if isinstance(m, dict):
                out.append((name[:-5], m))
    return sorted(out, key=lambda x: x[1].get("created_at", 0), reverse=True)


def _is_stale(info):
    return time.time() - float(info.get("heartbeat") or 0) > STALE_SECONDS


def active_job(entry_id):
    """طلب لسه في الطابور أو شغال للتحليل ده (عشان مانشغّلش اتنين)."""
    for jid, m in _jobs_for(entry_id):
        info = status(jid)
        state = info.get("state")
        if state in TERMINAL:
            continue
        if state == "queued" and time.time() - m.get("created_at", 0) > STALE_SECONDS:
            continue               # الـ worker ماستلموش خالص — منسيبوش يقفل الزرار للأبد
        if state == "running" and _is_stale(info):
            continue
        return jid
    return None


def latest_job(entry_id):
    jobs = _jobs_for(entry_id)
    return jobs[0][0] if jobs else None


def start(username, entry, *, company_id=None):
    """بيبعت طلب التقرير. بيرجّع رقم الـ job.

    F2: المشاهد مايقدرش يشغّل. F3: كل تشغيل بيتسجّل حدث استخدام بالتكلفة
    المتوقعة والسقف."""
    if not can_run(username, entry):
        raise permissions.Denied("run_ai")
    existing = active_job(entry["id"])
    if existing:
        return existing
    scenes = scenes_of(entry)
    if not scenes:
        raise dramaturgy.DramaturgyError("مفيش مشاهد في التحليل ده، فمش هيتعمل تقرير بناء درامي.")
    n, cost, ceiling = dramaturgy.estimate(scenes)
    inbox, status_dir, outbox = _dirs()
    os.makedirs(inbox, exist_ok=True)
    jid = job_id(entry["id"], scenes)
    manifest_path = os.path.join(inbox, f"{jid}.json")
    if os.path.exists(manifest_path):
        # نفس المحتوى اتبعت قبل كده وخلص أو فشل — نمسح حالته عشان يتقبل تاني
        for path in (os.path.join(status_dir, f"{jid}.json"),
                     os.path.join(outbox, f"{jid}.result.json")):
            try:
                os.unlink(path)
            except OSError:
                pass
    _write_atomic(os.path.join(inbox, f"{jid}.scenes.json"), scenes)
    # المانيفست آخر حاجة: وجوده هو اللي بيقول إن الطلب جاهز يتستلم
    _write_atomic(manifest_path, {
        "job_id": jid, "entry_id": entry["id"], "script_name": entry.get("script_name"),
        "requested_by": username, "company_id": entry.get("company_id"),
        "scene_count": n, "estimate_usd": cost, "max_cost_usd": ceiling,
        "created_at": time.time(),
    })
    audit.event("ai", target=dramaturgy.REPORT_KEY, username=username,
                company_id=entry.get("company_id") if entry.get("company_id") is not None else company_id,
                project_id=entry.get("source_project_id"),
                detail={"library_id": entry["id"], "job_id": jid, "scenes": n,
                        "estimate_usd": cost, "ceiling_usd": ceiling})
    return jid


def collect(username, entry):
    """لو فيه تقرير خلص ولسه ماتحفظش على التحليل، بيحفظه (attach_reports).
    بيرجّع True لو حفظ حاجة جديدة. عمره ما بيرمي — اللي بيفشل بيروح اللوج."""
    try:
        jid = latest_job(entry["id"])
        if not jid or status(jid).get("state") != "done":
            return False
        res = result(jid)
        report = (res or {}).get("report")
        if not isinstance(report, dict):
            return False
        current = report_of(entry)
        # نفس التشغيلة اتحفظت قبل كده؟ (إعادة التقرير لنفس المشاهد بتدّي نفس
        # رقم الـ job، فالمقارنة بوقت التوليد كمان)
        mine = report.get("meta") or {}
        theirs = (current or {}).get("meta") or {}
        if current and (theirs.get("job_id"), theirs.get("generated_at")) == \
                (mine.get("job_id"), mine.get("generated_at")):
            return False
        lib.attach_reports(entry["id"], {dramaturgy.REPORT_KEY: report})
        entry.setdefault("payload", {}).setdefault("reports", {})[dramaturgy.REPORT_KEY] = report
        return True
    except Exception as exc:  # noqa: BLE001
        lib._warn(f"dramaturgy collect {entry.get('id')}", exc)
        return False


def entry_for_project(username, project_id):
    """أحدث تحليل في المكتبة اتشغّل من المشروع ده (والمستخدم يقدر يشوفه)."""
    for row in lib.list_for(username):
        if row.get("source_project_id") == project_id:
            return row["id"]
    return None
