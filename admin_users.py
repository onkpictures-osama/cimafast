"""🛡️ إدارة الحسابات — للمشغّل بس (المالك 2026-09-26).

"تحكم في اليوزرز: حذف، تعديل، دمج، ونقل ملفاته ليوزر جديد… أوقف نشاطه، اقفله
فيتشرز، افتحله حاجات." كل عملية هنا:
- للمشغّل بس، وعمرها ما بتلمس حساب مشغّل تاني ولا حسابك انت.
- بتتسجل في سجل النشاط (audit) بلغة واضحة.
- النقل والدمج والحذف بياخدوا نسخة احتياطية من قاعدة البيانات الأول (snapshot).

«ملفات» اليوزر = المشاريع اللي هو عاملها (created_by)، وتحليلاته في مكتبة
التحليلات، والممثلين والأماكن اللي ضافهم في مساحة عمله.
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import sqlite3

import accounts
import audit
import auth
from accounts import AccessDenied, _now, _one, _tx, user
from database import DB_PATH, USE_POSTGRES, fetch_all

# المزايا اللي تتقفل أو تتفتح لكل حساب (المفتاح ← الاسم في الشاشة)
FEATURES = {
    "new_projects": "إنشاء مشاريع جديدة",
    "ai_analysis": "تحليل السيناريو بالذكاء الاصطناعي",
    "dramaturgy": "تقرير البناء الدرامي",
    "ai_plan": "🤖 ارسمها لي (رسمة المكان)",
    "assistant": "🤖 المساعد",
    "invite_team": "إضافة ناس لفريق المشروع",
    "exports": "تصدير التقارير (Excel / Word / PDF)",
}
FEATURE_DENIED = "الميزة دي مقفولة على حسابك — كلّم إدارة البرنامج لو محتاجها."
BACKUP_DIR = os.environ.get("CIMAFAST_ADMIN_BACKUPS") or os.path.join(os.path.dirname(DB_PATH), "admin-backups")
KEEP_BACKUPS = 30


# --- قراءة -----------------------------------------------------------------------------

def disabled_features(username):
    row = _one("SELECT disabled_features FROM users WHERE username=?", (auth.normalize_username(username or ""),))
    try:
        return set(json.loads((row or {}).get("disabled_features") or "[]")) & set(FEATURES)
    except ValueError:
        return set()


def feature_on(username, key):
    """المشغّل كل حاجة مفتوحة له. أي حد تاني: مفتوحة إلا لو اتقفلت على حسابه.
    (اسم مالوش حساب مابيدخلش البرنامج أصلًا - القفل بيبقى على حساب موجود.)"""
    u = user(username or "")
    if not u or u["is_operator"]:
        return True
    return key not in disabled_features(username)


def require_feature(username, key):
    if username and not feature_on(username, key):
        raise AccessDenied(FEATURE_DENIED)


def assistant_limit(username, default):
    row = _one("SELECT assistant_daily_limit FROM users WHERE username=?", (auth.normalize_username(username or ""),))
    v = (row or {}).get("assistant_daily_limit")
    return default if v is None else int(v)


def home_company_id(username):
    """مساحة العمل الشخصية: اللي هو أدمن فيها (أول واحدة)."""
    u = user(username)
    if not u:
        return None
    row = _one("SELECT m.company_id AS id FROM memberships m WHERE m.user_id=? AND m.role='admin' "
               "ORDER BY m.company_id LIMIT 1", (u["id"],))
    return row["id"] if row else None


def overview(actor):
    """كل الحسابات بأرقامها — للجدول."""
    _require_operator(actor)
    rows = fetch_all("""
        SELECT u.id, u.username, u.display_name, u.email, u.job_title, u.is_operator, u.active,
               u.must_change_password, u.created_at, u.last_login_at, u.created_by, u.expires_at,
               u.disabled_features, u.admin_note, u.merged_into,
               (SELECT c.subscription_tier FROM memberships m JOIN companies c ON c.id=m.company_id
                 WHERE m.user_id=u.id AND m.role='admin' ORDER BY c.id LIMIT 1) AS tier,
               (SELECT COUNT(*) FROM projects p WHERE p.created_by=u.username) AS projects,
               (SELECT COUNT(*) FROM scenes s JOIN projects p ON p.id=s.project_id
                 WHERE p.created_by=u.username) AS scenes,
               (SELECT COUNT(*) FROM usage_events e WHERE e.username=u.username) AS events,
               (SELECT COUNT(*) FROM assistant_messages a WHERE a.username=u.username) AS questions
        FROM users u ORDER BY u.created_at DESC, u.id DESC""")
    today = dt.date.today().isoformat()
    for r in rows:
        r["expired"] = bool(r["expires_at"]) and r["expires_at"][:10] < today
        r["status"] = ("merged" if r["merged_into"] else "suspended" if not r["active"]
                       else "expired" if r["expired"] else "active")
    return rows


def activity(actor, username, limit=40):
    _require_operator(actor)
    name = auth.normalize_username(username)
    events = fetch_all("SELECT at, event, target, project_id FROM usage_events WHERE username=? "
                       "ORDER BY id DESC LIMIT ?", (name, limit))
    changes = fetch_all("SELECT at, action, summary, project_id FROM audit_log WHERE username=? "
                        "ORDER BY id DESC LIMIT ?", (name, limit))
    questions = fetch_all("SELECT at, screen, question, state FROM assistant_messages WHERE username=? "
                          "ORDER BY id DESC LIMIT 20", (name,))
    projects = fetch_all("""SELECT p.id, p.name, p.project_type,
                              (SELECT COUNT(*) FROM scenes s WHERE s.project_id=p.id) AS scenes,
                              (SELECT COUNT(*) FROM characters c WHERE c.project_id=p.id) AS characters
                            FROM projects p WHERE p.created_by=? ORDER BY p.id""", (name,))
    return {"events": events, "changes": changes, "questions": questions, "projects": projects}


def owned(username):
    """اللي هيتنقل: مشاريعه، تحليلاته، ممثلينه وأماكنه (في مساحة عمله)."""
    name = auth.normalize_username(username)
    home = home_company_id(name)
    return {
        "projects": fetch_all("SELECT id, name, company_id FROM projects WHERE created_by=?", (name,)),
        "library": fetch_all("SELECT id FROM analysis_library WHERE owner_username=? OR company_id=?", (name, home)),
        "actors": fetch_all("SELECT id FROM actors WHERE owner_company_id=?", (home,)) if home else [],
        "venues": fetch_all("SELECT id FROM venues WHERE owner_company_id=?", (home,)) if home else [],
        "home": home,
    }


# --- حماية ---------------------------------------------------------------------------

def _require_operator(actor):
    u = user(actor or "")
    if not u or not u["is_operator"]:
        raise AccessDenied("المشغّل بس يقدر يدير الحسابات")
    return u


def _target(actor, username):
    """الحساب اللي هيتعدّل: موجود، مش انت، ومش مشغّل."""
    _require_operator(actor)
    t = user(username or "")
    if not t:
        raise ValueError("الحساب ده مش موجود")
    if t["username"] == auth.normalize_username(actor):
        raise AccessDenied("مينفعش تعمل ده على حسابك انت")
    if t["is_operator"]:
        raise AccessDenied("حساب مشغّل المنصة مايتعدّلش من هنا")
    return t


def snapshot(label):
    """نسخة من قاعدة البيانات قبل أي نقل/دمج/حذف (SQLite بس). بيرجّع المسار أو None."""
    if USE_POSTGRES or not os.path.exists(DB_PATH):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    path = os.path.join(BACKUP_DIR, f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{label}.db")
    src = sqlite3.connect(DB_PATH)
    try:
        dst = sqlite3.connect(path)
        with dst:
            src.backup(dst)
        dst.close()
    finally:
        src.close()
    for old in sorted(glob.glob(os.path.join(BACKUP_DIR, "*.db")))[:-KEEP_BACKUPS]:
        os.unlink(old)
    return path


# --- تعديل البيانات والوصول -----------------------------------------------------------

def update_profile(actor, username, display_name=None, email=None, job_title=None, admin_note=None,
                   tier=None, expires_at=None, assistant_daily_limit=None):
    t = _target(actor, username)
    if tier is not None and tier not in accounts.TIERS:
        raise ValueError(f"نوع اشتراك غير معروف: {tier}")
    if expires_at:
        dt.date.fromisoformat(str(expires_at)[:10])
    with audit.action("admin_user_update", "users", entity_id=t["id"], username=actor,
                      summary=f"تعديل بيانات «{t['username']}»") as act:
        act.extra = {k: v for k, v in {"الاسم": display_name, "الباقة": tier, "ينتهي": expires_at,
                                        "حد المساعد": assistant_daily_limit}.items() if v not in (None, "")}
        with _tx() as ex:
            ex("UPDATE users SET display_name=?, email=?, job_title=?, admin_note=?, expires_at=?, "
               "assistant_daily_limit=? WHERE id=?",
               ((display_name or "").strip() or t["username"], (email or "").strip() or None,
                (job_title or "").strip() or None, (admin_note or "").strip() or None,
                str(expires_at)[:10] if expires_at else None,
                None if assistant_daily_limit in (None, "") else max(0, int(assistant_daily_limit)), t["id"]))
    home = home_company_id(t["username"])
    if tier and home:
        accounts.set_subscription_tier(actor, home, tier)


def set_active(actor, username, active):
    """إيقاف الحساب: مايقدرش يدخل، والجلسة المفتوحة بتقفل مع أول ضغطة."""
    t = _target(actor, username)
    with audit.action("admin_user_suspend" if not active else "admin_user_reactivate", "users",
                      entity_id=t["id"], username=actor,
                      summary=f"{'إيقاف' if not active else 'تشغيل'} حساب «{t['username']}»"):
        with _tx() as ex:
            ex("UPDATE users SET active=? WHERE id=?", (1 if active else 0, t["id"]))


def set_features(actor, username, disabled):
    t = _target(actor, username)
    disabled = sorted(set(disabled) & set(FEATURES))
    with audit.action("admin_user_features", "users", entity_id=t["id"], username=actor,
                      summary=f"مزايا «{t['username']}»") as act:
        act.extra = {"مقفول": [FEATURES[k] for k in disabled] or "ولا حاجة"}
        with _tx() as ex:
            ex("UPDATE users SET disabled_features=? WHERE id=?", (json.dumps(disabled) if disabled else None, t["id"]))


def reset_password(actor, username):
    t = _target(actor, username)
    home = home_company_id(t["username"])
    if home is None:
        password = accounts.temp_password()
        with _tx() as ex:
            ex("UPDATE users SET password_hash=?, must_change_password=1 WHERE id=?",
               (auth.hash_password(password), t["id"]))
        return password
    return accounts.reset_password(actor, home, t["username"])


# --- النقل والدمج والحذف ---------------------------------------------------------------

def _ensure_target_user(actor, target_username, new_display_name=None):
    """الحساب اللي هياخد الملفات: موجود، أو جديد يتعمل دلوقتي. بيرجّع (user، كلمة سر لو جديد)."""
    name = auth.normalize_username(target_username)
    existing = user(name)
    if existing:
        if not existing["active"]:
            raise ValueError("الحساب اللي هتنقل له موقوف — شغّله الأول")
        return existing, None
    _cid, password = accounts.create_account(actor, new_display_name or name, name)
    return user(name), password


def _move_files(ex, src, dst, keep_src_access):
    """src ← dst: المشاريع ومكتبة التحليلات والممثلين والأماكن. بيرجّع عدّاد."""
    src_home = home_company_id(src["username"])
    dst_home = home_company_id(dst["username"])
    if dst_home is None:
        raise ValueError("الحساب اللي هتنقل له مالوش مساحة عمل")
    counts = {"مشاريع": 0, "تحليلات": 0, "ممثلين": 0, "أماكن حقيقية": 0}
    for p in fetch_all("SELECT id, company_id FROM projects WHERE created_by=?", (src["username"],)):
        # فريق المشروع لازم يفضل شايفه في مساحة العمل الجديدة
        for m in fetch_all("""SELECT pm.user_id, COALESCE(ms.role, 'department') AS role FROM project_members pm
                              LEFT JOIN memberships ms ON ms.user_id=pm.user_id AND ms.company_id=?
                              WHERE pm.project_id=?""", (p["company_id"], p["id"])):
            if m["user_id"] == dst["id"]:
                continue
            role = m["role"] if m["role"] in ("viewer", "department", "manager", "producer") else "department"
            ex("INSERT OR IGNORE INTO memberships (company_id, user_id, role, active, created_at) VALUES (?, ?, ?, 1, ?)",
               (dst_home, m["user_id"], role, _now()))
        ex("UPDATE projects SET company_id=?, created_by=? WHERE id=?", (dst_home, dst["username"], p["id"]))
        ex("DELETE FROM project_members WHERE project_id=? AND user_id=?", (p["id"], dst["id"]))
        if keep_src_access:
            ex("INSERT OR IGNORE INTO memberships (company_id, user_id, role, active, created_at) "
               "VALUES (?, ?, 'department', 1, ?)", (dst_home, src["id"], _now()))
            ex("INSERT OR IGNORE INTO project_members (project_id, user_id, added_by, added_at, job_title, permission) "
               "VALUES (?, ?, ?, ?, ?, 'edit')", (p["id"], src["id"], "admin", _now(), None))
            ex("UPDATE projects SET members_scoped=1 WHERE id=?", (p["id"],))
        else:
            ex("DELETE FROM project_members WHERE project_id=? AND user_id=?", (p["id"], src["id"]))
        ex("UPDATE project_invites SET created_by=? WHERE project_id=? AND created_by=?",
           (dst["username"], p["id"], src["username"]))
        counts["مشاريع"] += 1
    counts["تحليلات"] = len(fetch_all("SELECT id FROM analysis_library WHERE owner_username=? OR company_id=?",
                                      (src["username"], src_home)))
    ex("UPDATE analysis_library SET owner_username=?, company_id=? WHERE owner_username=? OR company_id=?",
       (dst["username"], dst_home, src["username"], src_home))
    if src_home:
        counts["ممثلين"] = len(fetch_all("SELECT id FROM actors WHERE owner_company_id=?", (src_home,)))
        counts["أماكن حقيقية"] = len(fetch_all("SELECT id FROM venues WHERE owner_company_id=?", (src_home,)))
        ex("UPDATE actors SET owner_company_id=? WHERE owner_company_id=?", (dst_home, src_home))
        ex("UPDATE venues SET owner_company_id=? WHERE owner_company_id=?", (dst_home, src_home))
    return counts


def transfer(actor, username, target_username, new_display_name=None, keep_access=True):
    """ينقل ملفات حساب لحساب تاني (موجود أو جديد). بيرجّع (العدّاد، كلمة سر الحساب الجديد أو None، النسخة)."""
    src = _target(actor, username)
    if auth.normalize_username(target_username) == src["username"]:
        raise ValueError("اختار حساب تاني تنقل له")
    backup = snapshot(f"transfer-{src['username']}")
    dst, password = _ensure_target_user(actor, target_username, new_display_name)
    if dst["is_operator"]:
        raise AccessDenied("انقل لحساب عادي، مش لمشغّل المنصة")
    with audit.action("admin_user_transfer", "users", entity_id=src["id"], username=actor,
                      summary=f"نقل ملفات «{src['username']}» لـ «{dst['username']}»") as act:
        with _tx() as ex:
            counts = _move_files(ex, src, dst, keep_access)
        act.extra = dict(counts, **{"نسخة احتياطية": os.path.basename(backup) if backup else "—"})
    return counts, password, backup


def merge(actor, username, into_username):
    """يدمج حساب في حساب تاني: كل ملفاته وعضوياته بتروح للتاني، والقديم بيتقفل
    (بيفضل موجود عشان سجل النشاط يفضل مفهوم)."""
    src = _target(actor, username)
    dst = _target(actor, into_username)
    if src["id"] == dst["id"]:
        raise ValueError("اختار حساب تاني")
    if not dst["active"]:
        raise ValueError("الحساب اللي هتدمج فيه موقوف — شغّله الأول")
    backup = snapshot(f"merge-{src['username']}")
    with audit.action("admin_user_merge", "users", entity_id=src["id"], username=actor,
                      summary=f"دمج «{src['username']}» في «{dst['username']}»") as act:
        with _tx() as ex:
            counts = _move_files(ex, src, dst, keep_src_access=False)
            src_home = home_company_id(src["username"])
            # مشاريع ناس تانية كان عضو فيها
            n = 0
            for pm in fetch_all("SELECT project_id, job_title, permission FROM project_members WHERE user_id=?", (src["id"],)):
                ex("INSERT OR IGNORE INTO project_members (project_id, user_id, added_by, added_at, job_title, permission) "
                   "VALUES (?, ?, ?, ?, ?, ?)", (pm["project_id"], dst["id"], "admin", _now(), pm["job_title"], pm["permission"]))
                n += 1
            ex("DELETE FROM project_members WHERE user_id=?", (src["id"],))
            for m in fetch_all("SELECT company_id, role FROM memberships WHERE user_id=? AND active=1", (src["id"],)):
                if m["company_id"] == src_home:
                    continue
                ex("INSERT OR IGNORE INTO memberships (company_id, user_id, role, active, created_at) VALUES (?, ?, ?, 1, ?)",
                   (m["company_id"], dst["id"], m["role"], _now()))
            ex("UPDATE memberships SET active=0 WHERE user_id=?", (src["id"],))
            if src_home:
                ex("UPDATE companies SET active=0 WHERE id=? AND NOT EXISTS (SELECT 1 FROM projects WHERE company_id=?)",
                   (src_home, src_home))
            ex("UPDATE users SET active=0, merged_into=? WHERE id=?", (dst["username"], src["id"]))
            counts["مشاريع ناس تانية كان فيها"] = n
        act.extra = dict(counts, **{"نسخة احتياطية": os.path.basename(backup) if backup else "—"})
    return counts, backup


def delete(actor, username, confirm, delete_projects=False):
    """حذف نهائي. لازم تكتب اسم الدخول بالظبط للتأكيد. لو عنده مشاريع: يا تنقلها
    الأول، يا تختار تمسحها معاه. الممثلين والأماكن الحقيقية اللي في مساحة عمله
    بيفضلوا (ممكن يكونوا متعاقدين في مشاريع تانية)، ومساحة عمله بتتقفل."""
    t = _target(actor, username)
    if auth.normalize_username(confirm or "") != t["username"]:
        raise ValueError("اكتب اسم الدخول بالظبط عشان تأكد الحذف")
    projects = fetch_all("SELECT id FROM projects WHERE created_by=?", (t["username"],))
    if projects and not delete_projects:
        raise ValueError(f"الحساب ده عنده {len(projects)} مشروع — انقلهم لحد تاني الأول، أو اختار تمسحهم معاه")
    backup = snapshot(f"delete-{t['username']}")
    home = home_company_id(t["username"])
    import repo
    with audit.action("admin_user_delete", "users", entity_id=t["id"], username=actor,
                      summary=f"حذف حساب «{t['username']}»") as act:
        act.extra = {"مشاريع اتمسحت": len(projects) if delete_projects else 0,
                     "نسخة احتياطية": os.path.basename(backup) if backup else "—"}
        from permissions import system
        with system():
            for p in projects:
                repo.delete_project(p["id"])
        with _tx() as ex:
            ex("DELETE FROM project_members WHERE user_id=?", (t["id"],))
            ex("DELETE FROM memberships WHERE user_id=?", (t["id"],))
            ex("UPDATE project_invites SET revoked=1 WHERE created_by=? AND accepted_at IS NULL", (t["username"],))
            if home:
                ex("DELETE FROM analysis_library WHERE company_id=? OR owner_username=?", (home, t["username"]))
                ex("UPDATE companies SET active=0 WHERE id=? AND NOT EXISTS (SELECT 1 FROM memberships WHERE company_id=?)",
                   (home, home))
            ex("DELETE FROM users WHERE id=?", (t["id"],))
    return backup


def blocked_reason(username, password):
    """بعد دخول فاشل: لو كلمة السر صح بس الحساب موقوف/منتهي — عشان نقوله السبب
    (من غير ما نكشف إن الاسم موجود لحد مايعرفش كلمة السر)."""
    row = _one("SELECT password_hash, active, expires_at, merged_into FROM users WHERE username=?",
               (auth.normalize_username(username or ""),))
    if not row or not auth.verify_password((password or "").strip(), row["password_hash"]):
        return None
    if row["merged_into"]:
        return f"الحساب ده اتدمج في «{row['merged_into']}» — ادخل بالحساب ده."
    if not row["active"]:
        return "الحساب ده موقوف — كلّم إدارة البرنامج."
    if row["expires_at"] and row["expires_at"][:10] < dt.date.today().isoformat():
        return "مدة الحساب ده خلصت — كلّم إدارة البرنامج عشان تتجدد."
    return None
