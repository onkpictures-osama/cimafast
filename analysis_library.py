"""مكتبة التحليلات (مكتبة التحليلات) — كل تحليل سيناريو بيتحفظ على مستوى الحساب.

المشكلة اللي بتحلها (طلب المالك 2026-09-23): التحليل بالذكاء الاصطناعي كان
متربط بالمشروع اللي اتشغّل منه بس. لو حد رفع السيناريو في المشروع الغلط
واتحلل، التحليل اللي اتدفع فيه فلوس كان يا يتستورد غلط يا يضيع. هنا كل تحليل
خلص بيتحفظ لوحده في جدول ‎analysis_library‎، بره أي مشروع، ويقدر يتستورد
بعدين في أي مشروع (جديد أو فيه بيانات، بدمج الشخصيات والأماكن المتشابهة).

مين يشوف إيه (F1):
- التحليل بيتسجّل باسم اللي شغّله (owner_username) وتبع شركة المشروع اللي
  اتشغّل منه (company_id).
- بيشوفه: صاحبه، وأي عضو في نفس الشركة، والمشغّل. شركة تانية لأ.
- الحذف: صاحبه أو مدير الشركة أو المشغّل.
- الاستيراد في مشروع: لازم يكون ليك دور تعديل في شركة المشروع ده (F2) —
  المشاهد (viewer) بيتصفح وينزّل الملف بس.

صيغة الملف (‎.cimafast-analysis.json‎) — نسخة 1:

    {
      "format": "cimafast-analysis",       # ثابت: ده اللي بيقول الملف ده بتاعنا
      "version": 1,                         # أي نسخة أكبر من VERSION بترفض
      "exported_at": "2026-09-23T16:01:00+00:00",
      "generator": "CimaFast Studio",
      "script": {
        "name": "الحلقة الاولى.pdf",       # إلزامي
        "analysed_at": "...", "analysed_by": "...", "source_project": "...",
        "counts": {"scenes": 15, "characters": 9, "locations": 8}
      },
      "analysis": {                          # نفس شكل نتيجة الـ AI (spool) بالظبط
        "scenes": [ {scene_number, int_ext, day_night, location_name,
                     characters, props, notes, ...}, ... ],
        "warnings": [...], "meta": {...},
        "reports": {                         # اختياري ومفتوح: تقارير بتتولد بعد التحليل
          "<اسم التقرير>": {...}             # (زي تقرير البناء الدرامي) بتتخزن وتتصدّر
        }                                    # معاه. مفتاح مش معروف بيتحفظ زي ما هو.
      }
    }

UTF-8 والعربي زي ما هو (ensure_ascii=False) — الملف يتقري بعين الإنسان.
أي ملف تاني (نسخة مش معروفة، JSON بايظ، من غير مشاهد) بيترفض برسالة عربي
واضحة، ومفيش استثناء خام بيوصل للشاشة.

الموديول ده مابيستوردش Streamlit: التطبيق والـ board والاختبارات بيستعملوه.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import os
import re
import sys

import accounts
import audit
import permissions
from database import fetch_all, run_query
from importer import import_parsed_scenes
from script_parser import apply_character_merges, parse_json_script
from search import matches as _search_matches
from search import normalize

FORMAT = "cimafast-analysis"
VERSION = 1
FILE_SUFFIX = ".cimafast-analysis.json"
MAX_FILE_BYTES = 25 * 1024 * 1024       # سيناريو مسلسل كامل بيطلع أقل من 2 ميجا
MAX_SCENES = 5000
MAX_NAME_CHARS = 200

MODE_NEW = "new"          # بيانات جديدة: من غير مطابقة مع الموجود
MODE_MERGE = "merge"      # دمج: الشخصيات والأماكن المتشابهة بتتربط بالموجود

_LIST_COLS = ("id, company_id, owner_username, script_name, source_project_id, "
              "source_project_name, analysed_at, saved_at, origin, job_id, "
              "scene_count, character_count, location_count")


class LibraryError(ValueError):
    """رسالة عربي جاهزة تتعرض للمستخدم زي ما هي."""


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _warn(where, exc):
    print(f"[library] {where}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)


# --- التحليل نفسه ------------------------------------------------------------------

def clean_payload(payload):
    """الأجزاء اللي بتتخزن بس: المشاهد والتحذيرات والـ meta."""
    scenes = payload.get("scenes") if isinstance(payload, dict) else None
    if not isinstance(scenes, list):
        raise LibraryError("التحليل مفيهوش قايمة مشاهد.")
    warnings = payload.get("warnings") or []
    meta = payload.get("meta") or {}
    out = {"scenes": scenes,
           "warnings": [str(w) for w in warnings] if isinstance(warnings, list) else [],
           "meta": meta if isinstance(meta, dict) else {}}
    # تقارير إضافية بتتولد بعد التحليل (البناء الدرامي وغيره) — كل تقرير
    # object باسمه، والمكتبة بتشيله وتصدّره من غير ما تفهمه. مش جزء من
    # البصمة: نفس المشاهد بتقرير أو من غيره = نفس التحليل.
    reports = payload.get("reports")
    if isinstance(reports, dict) and reports:
        out["reports"] = {str(k): v for k, v in reports.items() if isinstance(v, (dict, list))}
    return out


def content_hash(payload):
    """بصمة المشاهد: نفس التحليل مايتحفظش مرتين في نفس الشركة."""
    text = json.dumps(payload.get("scenes") or [], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parsed_scenes(payload, known_characters=None):
    """المشاهد بنفس الشكل اللي الاستيراد بيقبله (نفس مسار ملف JSON في تبويب الإضافة)."""
    data = json.dumps({"scenes": payload.get("scenes") or []}, ensure_ascii=False).encode("utf-8")
    return parse_json_script(data, known_characters=known_characters)


def summarize(payload):
    scenes = parsed_scenes(payload)["scenes"]
    chars, locs = set(), set()
    for sc in scenes:
        chars.update(sc.get("characters") or [])
        if sc.get("location_name"):
            locs.add(sc["location_name"])
    return {"scenes": len(scenes), "characters": len(chars), "locations": len(locs)}


# --- الحفظ ---------------------------------------------------------------------------

def save(payload, *, script_name, owner, company_id, source_project_id=None,
         source_project_name=None, analysed_at=None, origin="ai", job_id=None):
    """بيحفظ تحليل في المكتبة. بيرجّع (id، اتضاف جديد ولا كان موجود).

    الفحص على البصمة: نفس المشاهد في نفس الشركة (أو لنفس الشخص لو من غير
    شركة) بترجّع الصف الموجود بدل ما تكرره. الصلاحية بيفحصها اللي بينده."""
    payload = clean_payload(payload)
    if not payload["scenes"]:
        raise LibraryError("التحليل مفيهوش مشاهد، فمش هيتحفظ.")
    digest = content_hash(payload)
    if company_id is not None:
        dup = fetch_all("SELECT id FROM analysis_library WHERE content_hash=? AND company_id=?",
                        (digest, company_id))
    else:
        dup = fetch_all("SELECT id FROM analysis_library WHERE content_hash=? AND company_id IS NULL "
                        "AND owner_username=?", (digest, owner))
    if dup:
        if payload.get("reports"):
            attach_reports(dup[0]["id"], payload["reports"])
        return dup[0]["id"], False
    counts = summarize(payload)
    name = (str(script_name or "").strip() or "سيناريو من غير اسم")[:MAX_NAME_CHARS]
    with permissions.system(), audit.action(
            "library_save", "analysis_library", company_id=company_id,
            summary=f"حفظ تحليل «{name}» في مكتبة التحليلات") as act:
        new_id = run_query(
            "INSERT INTO analysis_library (company_id, owner_username, script_name, source_project_id, "
            "source_project_name, analysed_at, saved_at, origin, job_id, content_hash, scene_count, "
            "character_count, location_count, payload) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (company_id, owner, name, source_project_id, source_project_name,
             analysed_at or _now(), _now(), origin, job_id, digest, counts["scenes"],
             counts["characters"], counts["locations"], json.dumps(payload, ensure_ascii=False)))
        act.entity_id = new_id
        act.extra = {"المصدر": {"ai": "تحليل بالذكاء الاصطناعي", "upload": "ملف مرفوع"}.get(origin, origin),
                     "مشاهد": counts["scenes"]}
    return new_id, True


def attach_reports(entry_id, reports):
    """بيضيف/بيحدّث تقارير على تحليل محفوظ (‎payload["reports"][اسم] = بيانات‎).

    للتقارير اللي بتتولد بعد التحليل (زي البناء الدرامي): بتتحفظ مع التحليل
    وبتطلع في الملف المصدّر. الصلاحية بيفحصها اللي بينده، زي save()."""
    reports = {str(k): v for k, v in (reports or {}).items() if isinstance(v, (dict, list))}
    if not reports:
        return
    rows = fetch_all("SELECT payload, company_id, script_name FROM analysis_library WHERE id=?",
                     (entry_id,))
    if not rows:
        raise LibraryError("التحليل ده مش موجود أو مش متاح لحسابك.")
    payload = json.loads(rows[0]["payload"])
    payload.setdefault("reports", {}).update(reports)
    with permissions.system(), audit.action(
            "library_report", "analysis_library", entity_id=entry_id, company_id=rows[0]["company_id"],
            summary=f"تقرير على تحليل «{rows[0]['script_name']}» في مكتبة التحليلات") as act:
        act.extra = {"التقارير": "، ".join(sorted(reports))}
        run_query("UPDATE analysis_library SET payload=? WHERE id=?",
                  (json.dumps(payload, ensure_ascii=False), entry_id))


# --- الحفظ التلقائي من طابور التحليل (ai_jobs / spool) ---------------------------------
# الطابور نفسه مابيتغيّرش خالص: بنقرا ملفاته بس. الشكل (من /opt/cimafast-ai/spool.py):
# inbox/<job>.json المانيفست، status/<job>.json الحالة، outbox/<job>.result.json
# النتيجة، وبعد الاستيراد المانيفست والحالة بيتنقلوا لـ done/inbox-… و done/status-….

def spool_root():
    return os.environ.get("CIMAFAST_AI_SPOOL", "/var/lib/cimafast/ai-jobs")


def _spool_matches_db(root):
    """الطابور تبع قاعدة البيانات اللي جنبه بس: ‎/var/lib/cimafast/{ai-jobs,studio.db}‎
    و‎/var/lib/cimafast-v1/{ai-jobs,studio.db}‎. أرقام المشاريع في النسختين
    متكررة، فقاعدة تانية (اختبار، نسخة) ماتقراش طابور مش بتاعها."""
    import database
    return (os.path.dirname(os.path.abspath(root))
            == os.path.dirname(os.path.abspath(database.DB_PATH)))


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _job_files(root, jid):
    status = (_read(os.path.join(root, "status", f"{jid}.json"))
              or _read(os.path.join(root, "done", f"status-{jid}.json")) or {})
    manifest = (_read(os.path.join(root, "inbox", f"{jid}.json"))
                or _read(os.path.join(root, "done", f"inbox-{jid}.json")) or {})
    result = _read(os.path.join(root, "outbox", f"{jid}.result.json"))
    return status, manifest, result


def _project_of_job(jid, manifest):
    pid = manifest.get("project_id")
    if pid is None:
        try:
            pid = int(str(jid).split("-", 1)[0])
        except ValueError:
            pid = None
    return pid


def _attribution(jid, project_id, filename):
    """مين شغّل التحليل: من حدث الاستخدام "ai" اللي اتسجّل وقت التشغيل (F3).
    الأحدث بيسجّل رقم الـ job نفسه؛ الأقدم بنطابقه باسم الملف."""
    if project_id is None:
        return None, None
    rows = fetch_all("SELECT username, company_id, detail FROM usage_events WHERE event='ai' "
                     "AND target='script_analysis' AND project_id=? ORDER BY id DESC", (project_id,))
    by_file = None
    for r in rows:
        try:
            detail = json.loads(r["detail"] or "{}")
        except ValueError:
            detail = {}
        if not isinstance(detail, dict):
            continue
        if detail.get("job_id") == jid:
            return r["username"], r["company_id"]
        if by_file is None and filename and detail.get("file") == filename:
            by_file = (r["username"], r["company_id"])
    return by_file or (None, None)


def save_job(jid, root=None, fallback_owner=None, fallback_company=None):
    """بيحفظ نتيجة job خلص. بيرجّع id الصف أو None لو مفيش حاجة تتحفظ.

    عمره ما بيرمي: الحفظ التلقائي مايوقّعش شاشة التحليل أبدًا."""
    root = root or spool_root()
    try:
        status, manifest, result = _job_files(root, jid)
        if status.get("state") != "done" or not isinstance(result, dict):
            return None
        if not isinstance(result.get("scenes"), list) or not result["scenes"]:
            return None                      # تحليل رجع صفر مشاهد = فشل، مش تحليل
        pid = _project_of_job(jid, manifest)
        filename = manifest.get("filename")
        owner, company = _attribution(jid, pid, filename)
        project = fetch_all("SELECT name, company_id FROM projects WHERE id=?", (pid,)) if pid else []
        if project and project[0]["company_id"] is not None:
            company = project[0]["company_id"]
        owner = owner or fallback_owner
        company = company if company is not None else fallback_company
        ts = status.get("heartbeat") or manifest.get("created_at")
        analysed_at = (dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat(timespec="seconds")
                       if isinstance(ts, (int, float)) else None)
        entry_id, _ = save(result, script_name=filename or f"تحليل {jid}", owner=owner,
                           company_id=company, source_project_id=pid,
                           source_project_name=project[0]["name"] if project else None,
                           analysed_at=analysed_at, origin="ai", job_id=jid)
        return entry_id
    except Exception as exc:  # noqa: BLE001
        _warn(f"save_job {jid}", exc)
        return None


def sync_from_spool(root=None):
    """الحفظ التلقائي + ملء المكتبة بالتحليلات القديمة: أي نتيجة خلصت في الطابور
    ومش في المكتبة بتتحفظ. بيتنده مع بداية البرنامج وكل ما شاشة المكتبة تتفتح،
    فالتحليل بيتحفظ حتى لو اللي شغّله قفل الصفحة قبل ما يخلص. بيرجّع عدد اللي اتضاف."""
    root = root or spool_root()
    outbox = os.path.join(root, "outbox")
    if not _spool_matches_db(root) or not os.path.isdir(outbox):
        return 0
    try:
        known = {r["job_id"] for r in fetch_all(
            "SELECT job_id FROM analysis_library WHERE job_id IS NOT NULL")}
        names = os.listdir(outbox)
    except Exception as exc:  # noqa: BLE001
        _warn("sync", exc)
        return 0
    added = 0
    for name in sorted(names):
        if not name.endswith(".result.json"):
            continue
        jid = name[: -len(".result.json")]
        if jid in known:
            continue
        if save_job(jid, root) is not None:
            added += 1
    return added


# --- مين يشوف إيه -------------------------------------------------------------------

def _is_operator(username):
    u = accounts.user(username) if username else None
    return bool(u and u["is_operator"])


def _visible_where(username):
    """(شرط SQL، باراميترز) للتحليلات اللي المستخدم يقدر يشوفها."""
    if _is_operator(username):
        return "1=1", ()
    allowed = [c["id"] for c in accounts.companies_for(username or "")]
    if not allowed:
        return "owner_username = ?", (username,)
    marks = ",".join("?" * len(allowed))
    return f"(owner_username = ? OR company_id IN ({marks}))", (username, *allowed)


def list_for(username, query="", limit=500):
    """تحليلات المستخدم وشركاته، الأحدث الأول، ومفلترة بالبحث العربي (أ/ا، ة/ه…)."""
    if not username:
        return []
    where, params = _visible_where(username)
    rows = fetch_all(f"SELECT {_LIST_COLS} FROM analysis_library WHERE {where} "
                     "ORDER BY saved_at DESC, id DESC", params)
    out = []
    for r in rows:
        if _search_matches(query, r["script_name"], r["source_project_name"], r["owner_username"]):
            out.append(r)
            if len(out) >= limit:
                break
    return out


def count_for(username):
    if not username:
        return 0
    where, params = _visible_where(username)
    rows = fetch_all(f"SELECT COUNT(*) AS n FROM analysis_library WHERE {where}", params)
    return int(rows[0]["n"]) if rows else 0


def get(username, entry_id):
    """الصف كامل بالتحليل نفسه — أو LibraryError لو مش موجود أو مش من حقه يشوفه
    (نفس الرسالة في الحالتين عشان مانكشفش وجود تحليل شركة تانية)."""
    where, params = _visible_where(username)
    rows = fetch_all(f"SELECT * FROM analysis_library WHERE id=? AND {where}", (entry_id, *params))
    if not rows:
        raise LibraryError("التحليل ده مش موجود أو مش متاح لحسابك.")
    row = dict(rows[0])
    try:
        row["payload"] = json.loads(row["payload"])
    except ValueError:
        raise LibraryError("بيانات التحليل ده بايظة ومش مقروءة.") from None
    return row


def can_delete(username, entry):
    if not username:
        return False
    if entry.get("owner_username") == username or _is_operator(username):
        return True
    cid = entry.get("company_id")
    return cid is not None and accounts.role_in(username, cid) in ("admin", "operator")


def delete(username, entry_id):
    entry = get(username, entry_id)
    if not can_delete(username, entry):
        raise LibraryError("حذف التحليل لصاحبه أو لمدير المشروع بس.")
    with permissions.system(), audit.action(
            "library_delete", "analysis_library", entity_id=entry_id, company_id=entry["company_id"],
            username=username, summary=f"حذف تحليل «{entry['script_name']}» من مكتبة التحليلات") as act:
        act.extra = {"مشاهد": entry["scene_count"], "المشروع الأصلي": entry["source_project_name"] or "—"}
        run_query("DELETE FROM analysis_library WHERE id=?", (entry_id,))


# --- الملف --------------------------------------------------------------------------

_UNSAFE_FILENAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


def file_name(entry):
    base = re.sub(r"\.(docx?|pdf|txt|json|md)$", "", str(entry.get("script_name") or ""), flags=re.I)
    base = _UNSAFE_FILENAME.sub("_", base).strip(" ._") or "analysis"
    return base[:80] + FILE_SUFFIX


def to_file(entry, exported_by=None):
    """(اسم الملف، البايتات) لتحليل من المكتبة (صف من get())."""
    doc = {
        "format": FORMAT,
        "version": VERSION,
        "exported_at": _now(),
        "generator": "CimaFast Studio",
        "script": {
            "name": entry["script_name"],
            "analysed_at": entry.get("analysed_at"),
            "analysed_by": entry.get("owner_username"),
            "source_project": entry.get("source_project_name"),
            "counts": {"scenes": entry.get("scene_count"), "characters": entry.get("character_count"),
                       "locations": entry.get("location_count")},
        },
        "analysis": clean_payload(entry["payload"]),
    }
    if exported_by:
        doc["exported_by"] = exported_by
    return file_name(entry), json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")


def parse_file(data):
    """بيقرا ملف ‎.cimafast-analysis.json‎ وبيتأكد منه بالتفصيل.

    بيرجّع {"script_name", "analysed_at", "source_project", "payload"} — أو
    LibraryError برسالة عربي تقول للمستخدم إيه المشكلة بالظبط."""
    if not data:
        raise LibraryError("الملف فاضي.")
    if len(data) > MAX_FILE_BYTES:
        raise LibraryError("الملف أكبر من المسموح (25 ميجا) — ده مش شكل ملف تحليل.")
    try:
        text = data.decode("utf-8-sig")
    except (UnicodeDecodeError, AttributeError):
        raise LibraryError("الملف مش بترميز UTF-8 — ده مش ملف تحليل من CimaFast.") from None
    try:
        doc = json.loads(text)
    except ValueError:
        raise LibraryError("الملف مش JSON سليم — ممكن يكون اتقطع أو اتعدّل بإيد.") from None
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise LibraryError("ده مش ملف تحليل من CimaFast (لازم يكون ‎.cimafast-analysis.json‎). "
                           "لو ده JSON من AI تاني، ارفعه من تبويب «إضافة سيناريو» جوه المشروع.")
    version = doc.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise LibraryError("رقم نسخة الملف مش مفهوم — الملف ممكن يكون اتعدّل.")
    if version > VERSION:
        raise LibraryError(f"الملف ده متصدّر من نسخة أحدث من CimaFast (نسخة {version})، "
                           f"والبرنامج هنا بيقرا لحد نسخة {VERSION}.")
    if version < 1:
        raise LibraryError(f"نسخة الملف ({version}) مش مدعومة.")
    script = doc.get("script")
    if not isinstance(script, dict) or not str(script.get("name") or "").strip():
        raise LibraryError("بيانات السيناريو ناقصة في الملف (اسم السيناريو).")
    analysis = doc.get("analysis")
    if not isinstance(analysis, dict) or not isinstance(analysis.get("scenes"), list):
        raise LibraryError("الملف مفيهوش تحليل (قايمة المشاهد ناقصة).")
    scenes = analysis["scenes"]
    if not scenes:
        raise LibraryError("الملف مفيهوش ولا مشهد.")
    if len(scenes) > MAX_SCENES:
        raise LibraryError(f"الملف فيه أكتر من {MAX_SCENES} مشهد — ده مش شكل سيناريو.")
    for i, sc in enumerate(scenes, 1):
        if not isinstance(sc, dict):
            raise LibraryError(f"المشهد رقم {i} في الملف مش مكتوب صح.")
        num = sc.get("scene_number")
        if isinstance(num, bool):
            num = None
        try:
            int(num)
        except (TypeError, ValueError):
            raise LibraryError(f"المشهد رقم {i} في الملف من غير رقم مشهد صحيح.") from None
        for key in ("characters", "props"):
            if sc.get(key) is not None and not isinstance(sc[key], list):
                raise LibraryError(f"المشهد رقم {i}: «{key}» لازم تكون قايمة.")
    if analysis.get("warnings") is not None and not isinstance(analysis["warnings"], list):
        raise LibraryError("التحذيرات في الملف لازم تكون قايمة.")
    if analysis.get("meta") is not None and not isinstance(analysis["meta"], dict):
        raise LibraryError("بيانات التشغيل (meta) في الملف مش مكتوبة صح.")
    reports = analysis.get("reports")
    if reports is not None and (not isinstance(reports, dict)
                                or not all(isinstance(v, (dict, list)) for v in reports.values())):
        raise LibraryError("التقارير في الملف مش مكتوبة صح.")
    payload = clean_payload(analysis)
    try:
        ok = parsed_scenes(payload)["scenes"]
    except Exception:  # noqa: BLE001
        ok = []
    if not ok:
        raise LibraryError("مقدرناش نقرا ولا مشهد من الملف.")
    analysed_at = script.get("analysed_at")
    source = script.get("source_project")
    return {"script_name": str(script["name"]).strip()[:MAX_NAME_CHARS],
            "analysed_at": str(analysed_at)[:40] if analysed_at else None,
            "source_project": str(source)[:MAX_NAME_CHARS] if source else None,
            "payload": payload}


def _require_edit(username, company_id):
    role = accounts.role_in(username, company_id) if company_id is not None else None
    if role is None:
        raise LibraryError("حسابك مش عضو في الشركة دي.")
    if not permissions.can(role, "edit"):
        raise permissions.Denied("edit")
    return role


def add_upload(username, company_id, data):
    """ملف تحليل مرفوع بيدخل مكتبة المستخدم (في شركته الحالية). (id، جديد؟)"""
    _require_edit(username, company_id)
    parsed = parse_file(data)
    return save(parsed["payload"], script_name=parsed["script_name"], owner=username,
                company_id=company_id, source_project_name=parsed["source_project"],
                analysed_at=parsed["analysed_at"], origin="upload")


# --- الاستيراد في مشروع (مع الدمج) ---------------------------------------------------

_PAREN = re.compile(r"[\(\[（][^\)\]）]*[\)\]）]")


def _words(name):
    """كلمات الاسم للمقارنة: من غير اللي بين قوسين، ومن غير «ال» في أول الكلمة
    (سويسي / السويسي)، وبعد توحيد الحروف (أ/ا، ة/ه، ى/ي)."""
    out = []
    for w in normalize(_PAREN.sub(" ", name or "")).split():
        out.append(w[2:] if w.startswith("ال") and len(w) >= 4 else w)
    return out


def _paren(name):
    m = _PAREN.search(name or "")
    return normalize(m.group(0)) if m else ""


def match_name(incoming, existing):
    """الاسم الموجود في المشروع اللي الاسم الجاي غالبًا هو هو: (الاسم، قوي؟) أو None.

    قوي = نفس الاسم بعد التوحيد (أحمد/احمد، الشقة/الشقه، سويسي/السويسي).
    ضعيف = كلمات واحد جوه التاني (سيد السويسي / السويسي) — بيتعرض للمستخدم يأكّده.
    اسمين بقوسين مختلفين (يونس (والد نادين) / يونس (ابن حسين)) عمرهم ما بيتدمجوا:
    دي طريقة السيناريو في التفريق بين شخصيتين بنفس الاسم."""
    n = normalize(incoming)
    for e in existing:
        if normalize(e) == n:
            return e, True
    words = _words(incoming)
    if not words:
        return None

    def _clash(e):
        return bool(_paren(e) and _paren(incoming) and _paren(e) != _paren(incoming))

    same = [e for e in existing if _words(e) == words and not _clash(e)]
    if len(same) == 1:
        return same[0], True
    if same:
        return None                          # أكتر من واحد: مش هنخمّن
    ws = set(words)
    near = []
    for e in existing:
        ew = set(_words(e))
        if not ew or _clash(e):
            continue
        shorter = ws if len(ws) <= len(ew) else ew
        if (ws <= ew or ew <= ws) and len("".join(shorter)) >= 3:
            near.append(e)
    if len(near) == 1:
        return near[0], False
    return None


def _existing_names(project_id):
    chars = [r["name"] for r in fetch_all("SELECT name FROM characters WHERE project_id=?", (project_id,))]
    locs = [r["name"] for r in fetch_all("SELECT name FROM locations WHERE project_id=?", (project_id,))]
    keys = {(r["scene_number"], r.get("scene_suffix") or None) for r in fetch_all(
        "SELECT scene_number, scene_suffix FROM scenes WHERE project_id=?", (project_id,))}
    return chars, locs, keys


def _check_project(username, project_id):
    role = accounts.project_role(username, project_id)
    if role is None:
        raise LibraryError("المشروع ده مش متاح لحسابك.")
    if not permissions.can(role, "edit"):
        raise permissions.Denied("edit")
    return role


def plan_import(username, entry_id, project_id, mode=MODE_MERGE):
    """معاينة قبل الاستيراد: إيه اللي هيتضاف، وإيه اللي هيتدمج مع الموجود.

    char_matches / loc_matches: [(الاسم في التحليل، الاسم في المشروع، قوي؟)]."""
    entry = get(username, entry_id)
    _check_project(username, project_id)
    chars, locs, scene_keys = _existing_names(project_id)
    scenes = parsed_scenes(entry["payload"], known_characters=chars)["scenes"]
    in_chars, in_locs = [], []
    for sc in scenes:
        for c in sc.get("characters") or []:
            if c not in in_chars:
                in_chars.append(c)
        if sc.get("location_name") and sc["location_name"] not in in_locs:
            in_locs.append(sc["location_name"])
    char_matches, loc_matches = [], []
    if mode == MODE_MERGE:
        for c in in_chars:
            if c in chars:
                continue                     # نفس الاسم بالظبط: الاستيراد بيربطه لوحده
            m = match_name(c, chars)
            if m:
                char_matches.append((c, m[0], m[1]))
        for loc in in_locs:
            if loc in locs:
                continue
            m = match_name(loc, locs)
            if m:
                loc_matches.append((loc, m[0], m[1]))
    skipped = [f"{sc['scene_number']}{sc.get('scene_suffix') or ''}" for sc in scenes
               if (sc["scene_number"], sc.get("scene_suffix") or None) in scene_keys]
    matched_c = {a for a, _, _ in char_matches}
    matched_l = {a for a, _, _ in loc_matches}
    return {
        "entry": entry, "scenes": scenes, "mode": mode,
        "char_matches": char_matches, "loc_matches": loc_matches,
        "new_characters": [c for c in in_chars if c not in chars and c not in matched_c],
        "new_locations": [x for x in in_locs if x not in locs and x not in matched_l],
        "existing_characters": [c for c in in_chars if c in chars],
        "existing_locations": [x for x in in_locs if x in locs],
        "skipped_scenes": skipped, "new_scene_count": len(scenes) - len(skipped),
        "project_has_data": bool(chars or locs or scene_keys),
    }


def apply_merges(scenes, char_matches, loc_matches):
    """بيطبّق الدمج المتأكد على نسخة من المشاهد (الأصل مابيتلمسش).

    الشخصيات بتعدّي على apply_character_merges بتاعة script_parser (بتصلّح أسماء
    المتكلمين في الحوار كمان). الأماكن: التطابق القوي مجرد اختلاف في الكتابة
    فبياخد اسم المكان الموجود؛ الضعيف بيتسجّل حالة (Variant) تحت المكان
    الموجود — نفس منطق دمج الأماكن في تبويب الإضافة."""
    out = copy.deepcopy(scenes)
    out = apply_character_merges(out, {a: b for a, b, _ in char_matches})
    locs = {a: (b, strong) for a, b, strong in loc_matches}
    for sc in out:
        original = sc.get("location_name")
        if original in locs:
            target, strong = locs[original]
            sc["location_name"] = target
            if not strong:
                sc["location_variant_hint"] = original
    return out


def import_into_project(username, entry_id, project_id, mode=MODE_MERGE,
                        char_matches=None, loc_matches=None):
    """بيستورد تحليل من المكتبة في مشروع، من نفس مسار الاستيراد (importer.py).

    char_matches / loc_matches: الدمج اللي المستخدم أكّده من المعاينة. لو None
    بيتاخد كل اللي المعاينة اقترحته. الصلاحية (F2) بدور المستخدم في شركة
    المشروع نفسه، مش الشركة المفتوحة في الشريط الجانبي. السجل (F3) صف واحد."""
    role = _check_project(username, project_id)
    plan = plan_import(username, entry_id, project_id, mode)
    if mode != MODE_MERGE:
        char_matches, loc_matches = [], []
    else:
        char_matches = plan["char_matches"] if char_matches is None else char_matches
        loc_matches = plan["loc_matches"] if loc_matches is None else loc_matches
    scenes = apply_merges(plan["scenes"], char_matches, loc_matches)
    entry = plan["entry"]
    company = fetch_all("SELECT company_id FROM projects WHERE id=?", (project_id,))[0]["company_id"]
    with permissions.acting_as(role), audit.action(
            "import_script", "scenes", project_id=project_id, company_id=company,
            username=username) as act:
        summary = import_parsed_scenes(project_id, scenes, fetch_all, run_query)
        act.summary = (f"استيراد من مكتبة التحليلات «{entry['script_name']}»: "
                       f"{summary['scenes_added']} مشهد جديد")
        act.extra = {"من المكتبة": entry["script_name"],
                     "الطريقة": "دمج مع الموجود" if mode == MODE_MERGE else "بيانات جديدة",
                     "مشاهد": summary["scenes_added"],
                     "شخصيات جديدة": len(summary["characters_added"]),
                     "شخصيات اتدمجت": len(char_matches),
                     "أماكن جديدة": len(summary["locations_added"]),
                     "أماكن اتدمجت": len(loc_matches),
                     "مشاهد متخطاة": len(summary["scenes_skipped"])}
    summary["characters_merged"] = [(a, b) for a, b, _ in char_matches]
    summary["locations_merged"] = [(a, b) for a, b, _ in loc_matches]
    return summary


def importable_projects(username):
    """المشاريع اللي المستخدم يقدر يستورد فيها: كل شركاته، بدوره في كل واحدة."""
    out = []
    roles = {c["id"]: (c["role"], c["name"]) for c in accounts.companies_for(username or "")}
    for p in accounts.projects_for(username or ""):
        role, company = roles.get(p["company_id"], (None, None))
        if role and permissions.can(role, "edit"):
            out.append({"id": p["id"], "name": p["name"], "company": company})
    return out
