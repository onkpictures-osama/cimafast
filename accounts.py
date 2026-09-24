"""الشركات والمستخدمين ومين يشوف إيه — PRODUCT-PLAN بند F1.

CimaFast نظام ERP بتستخدمه شركات إنتاج كتير. قبل الموديول ده الحسابات كانت
١٣ اسم في secrets.toml، ومفيش شركات، وكل مستخدم بيشوف كل مشروع. هنا:

- كل مستخدم صف في جدول users (نفس hash كلمة السر اللي كان في secrets.toml —
  محدش كلمة سره بتتغير في النقل).
- كل مشروع تبع شركة (projects.company_id).
- العضوية (memberships) بتقول المستخدم في أنهي شركة وبأي دور.
- المستخدم بيشوف مشاريع الشركات اللي هو عضو فيها وبس. المشغّل (operator —
  صاحب المنصة) بيشوف كل الشركات.

الموديول ده مابيستوردش Streamlit: التطبيقين (Streamlit والـ board) والاختبارات
بيستعملوه هو نفسه.
"""

from __future__ import annotations

import datetime as dt
import secrets as _secrets
import string
import sys as _sys

import contextlib

import audit
import auth
import permissions
from database import fetch_all
from repo import _tx as _repo_tx


@contextlib.contextmanager
def _tx():
    """كل دالة هنا بتفحص صلاحياتها بنفسها (أدمن، المستخدم نفسه، المشغّل)، فكتاباتها
    ماتتقفلش بقاعدة "المشاهد مايكتبش" — المشاهد لازم يقدر يغيّر كلمة سره."""
    with permissions.system(), _repo_tx() as ex:
        yield ex

# الأدوار، من الأوسع للأضيق. الفرض (مين يقدر يمسح إيه) بند F2؛ هنا بنسجلها بس.
ROLES = ("admin", "producer", "manager", "department", "viewer")
ROLE_LABELS = {
    "admin": "مدير المشروع", "producer": "منتج", "manager": "مدير إنتاج / مساعد مخرج أول",
    "department": "رئيس قسم", "viewer": "مشاهدة فقط", "operator": "مشغّل المنصة",
}
DEFAULT_COMPANY = "مساحة العمل الافتراضية"

# B5 ("بوابات الاشتراك"): نوع الاشتراك بيحدد قدرة الحساب على ضم فريق —
# creator شغال لوحده دايمًا، studio بيضيف فريق صغير، enterprise بيضيف عدد
# كبير. الأسماء والأرقام دي لسه مقترحة (SUBSCRIPTIONS-PLAN.md) مش مقفولة
# نهائيًا، فده تمثيل مبدئي مش نظام فوترة حقيقي.
TIERS = ("creator", "studio", "enterprise")
TIER_LABELS = {"creator": "Creator", "studio": "Studio", "enterprise": "Enterprise"}
TIER_ALLOWS_TEAM = {"creator": False, "studio": True, "enterprise": True}

# الحسابات القديمة أغلبها أسماء وظايف؛ ده أول تخمين للدور والمسمى، والأدمن
# يقدر يغيّره من صفحة الفريق.
_LEGACY_ROLES = {
    "producer": ("producer", "منتج"), "filmmaker": ("producer", "صانع أفلام"),
    "assistant_director": ("manager", "مساعد مخرج أول"),
    "director": ("department", "مخرج"), "dop": ("department", "مدير تصوير"),
    "art_director": ("department", "مدير فني"), "costume_designer": ("department", "مصمم أزياء"),
    "casting_director": ("department", "مدير كاستينج"), "editor": ("department", "مونتير"),
    "screenwriter": ("department", "سيناريست"), "vfx_supervisor": ("department", "مشرف مؤثرات بصرية"),
}
# حسابات صاحب المنصة: melzayat حسابه الشخصي، وosama اسم حساب GitHub بتاعه.
_LEGACY_OPERATORS = {"melzayat", "osama"}


class AccessDenied(PermissionError):
    pass


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _one(sql, params=()):
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def temp_password(length=12):
    """كلمة سر مؤقتة سهلة تتقري وتتكتب: من غير حروف بتتلخبط (0/O، 1/l/I)."""
    alphabet = "".join(c for c in string.ascii_letters + string.digits if c not in "0O1lI")
    return "".join(_secrets.choice(alphabet) for _ in range(length))


# --- النقل من secrets.toml (مرة واحدة، وبيتعاد من غير ضرر) -----------------------------

def migrate_accounts(legacy_users: dict, company_name: str = DEFAULT_COMPANY):
    """بينقل حسابات secrets.toml للقاعدة، ويربط كل مشروع مالوش شركة بالشركة الافتراضية.

    آمن إنه يتنده في كل تشغيل: مابيضيفش مستخدم موجود، ومابيعملش شركة تانية لو
    فيه واحدة. بيرجّع ملخص باللي اتعمل.

    F3: النقل ده شغل نظام مش شغل مستخدم — بيتسجّل صف واحد بالملخص لو حصل فيه
    حاجة، مش صف لكل حساب. وبيتنده في كل تشغيل، فلو سجّلنا العدم هيتكتب صف فاضي
    كل مرة الخدمة بتقوم.
    """
    with audit.disabled():
        done = _migrate_accounts(legacy_users, company_name)
    if done["users_added"] or done["company_created"] or done["projects_linked"]:
        audit.log("migrate_accounts", "users", summary="نقل الحسابات من ملف الأسرار للقاعدة",
                  changes=done, source="system")
    return done


def _migrate_accounts(legacy_users: dict, company_name: str):
    done = {"users_added": 0, "company_created": False, "projects_linked": 0, "memberships_added": 0}
    have_users = _one("SELECT COUNT(*) AS n FROM users")["n"]
    company = _one("SELECT id FROM companies ORDER BY id LIMIT 1")
    with _tx() as ex:
        if not company:
            ex("INSERT INTO companies (name, active, created_at) VALUES (?, 1, ?)", (company_name, _now()))
            done["company_created"] = True
    company_id = _one("SELECT id FROM companies ORDER BY id LIMIT 1")["id"]
    if not have_users and legacy_users:
        with _tx() as ex:
            for raw_name, pw_hash in legacy_users.items():
                name = auth.normalize_username(raw_name)
                if not name or not pw_hash:
                    continue
                role, title = _LEGACY_ROLES.get(name, ("admin" if name in _LEGACY_OPERATORS else "department",
                                                       None))
                ex("INSERT INTO users (username, password_hash, display_name, job_title, is_operator, "
                   "active, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
                   (name, pw_hash, name, title, 1 if name in _LEGACY_OPERATORS else 0, _now()))
                done["users_added"] += 1
        for u in fetch_all("SELECT id, username FROM users"):
            role = _LEGACY_ROLES.get(u["username"], ("admin" if u["username"] in _LEGACY_OPERATORS
                                                     else "department", None))[0]
            with _tx() as ex:
                ex("INSERT OR IGNORE INTO memberships (company_id, user_id, role, active, created_at) "
                   "VALUES (?, ?, ?, 1, ?)", (company_id, u["id"], role, _now()))
            done["memberships_added"] += 1
    # ربط المشاريع اليتيمة (من غير شركة) بالشركة الافتراضية — ده نقل مرة واحدة
    # للمشاريع اللي اتعملت قبل F1، مش قاعدة دايمة.
    #
    # الدالة دي بتتنده في كل تشغيل للخدمة. لو سِبناها تتبنى أي مشروع يتيم على
    # طول، تبقى وظيفة شغالة للأبد بتدّي أقدم شركة على المنصة أي مشروع
    # company_id بتاعه NULL لأي سبب (باج، صف راجع من باك أب، استيراد غلط).
    # مع شركتين أو أكتر ده بالظبط "بيانات شركة بتظهر عند شركة تانية".
    # فبناخد اليتامى بس وإحنا لسه شركة واحدة — يعني ده فعلًا النقل القديم.
    # غير كده بنسيبهم: مشروع من غير شركة مش بيبان لحد (projects_for بتفلتر
    # بـ company_id IN (...) وNULL عمرها ما بتطابق)، وده الفشل الآمن.
    orphans = _one("SELECT COUNT(*) AS n FROM projects WHERE company_id IS NULL")["n"]
    companies = _one("SELECT COUNT(*) AS n FROM companies")["n"]
    if orphans and companies == 1:
        with _tx() as ex:
            ex("UPDATE projects SET company_id=? WHERE company_id IS NULL", (company_id,))
        done["projects_linked"] = orphans
    elif orphans:
        done["orphans_left"] = orphans
        print(f"[accounts] {orphans} project(s) have no company and {companies} companies exist — "
              "leaving them unassigned (they stay invisible). Assign them deliberately.",
              file=_sys.stderr, flush=True)
    return done


# --- الدخول -------------------------------------------------------------------------

def auth_users():
    """{username: password_hash} للمستخدمين الفعّالين — نفس الشكل اللي auth متعوّد عليه،
    فتسجيل الدخول وكوكي الجلسة شغالين من غير أي تغيير."""
    return {r["username"]: r["password_hash"]
            for r in fetch_all("SELECT username, password_hash FROM users WHERE active=1")}


def user(username):
    return _one("SELECT id, username, display_name, email, job_title, is_operator, active, "
                "must_change_password, last_login_at FROM users WHERE username=?",
                (auth.normalize_username(username),))


def touch_login(username):
    """آخر دخول + سجل الدخول (F3).

    الدخول بيتسجّل في الجدولين عن قصد: في audit_log عشان سؤال الأمن ("مين دخل
    الحساب ده وإمتى")، وفي usage_events عشان سؤال المنتج ("كام واحد بيستخدم
    البرنامج الأسبوع ده"). الاتنين مختلفين في القراءة وفي مدة الحفظ.
    """
    name = auth.normalize_username(username)
    company = next((c["id"] for c in companies_for(name)), None)
    with audit.action("login", "auth", summary=f"دخول {name}",
                      username=name, company_id=company):
        with _tx() as ex:
            ex("UPDATE users SET last_login_at=? WHERE username=?", (_now(), name))
    audit.event("login", target="streamlit", username=name, company_id=company)


def log_logout(username):
    name = auth.normalize_username(username)
    company = next((c["id"] for c in companies_for(name)), None)
    audit.log("logout", "auth", summary=f"خروج {name}", username=name, company_id=company)


def log_failed_login(username):
    """محاولة دخول فاشلة — أهم صف في السجل لما حد يحاول يدخل حساب مش بتاعه.

    الاسم بيتسجّل زي ما اتكتب (بعد التوحيد) من غير كلمة السر أبدًا.
    """
    name = auth.normalize_username(username or "")[:64]
    company = next((c["id"] for c in companies_for(name)), None) if name else None
    audit.log("login_failed", "auth", summary=f"محاولة دخول فاشلة باسم {name or '—'}",
              username=name or None, company_id=company)


# --- مين يشوف إيه ---------------------------------------------------------------------

def companies_for(username):
    """الشركات اللي المستخدم يقدر يدخلها، ودوره في كل واحدة."""
    u = user(username)
    if not u or not u["active"]:
        return []
    if u["is_operator"]:
        return [dict(r, role="operator") for r in
                fetch_all("SELECT id, name, active, subscription_tier FROM companies ORDER BY name")]
    return fetch_all("""
        SELECT c.id, c.name, c.active, c.subscription_tier, m.role
        FROM memberships m JOIN companies c ON c.id = m.company_id
        WHERE m.user_id = ? AND m.active = 1 AND c.active = 1 ORDER BY c.name""", (u["id"],))


def role_in(username, company_id):
    for c in companies_for(username):
        if c["id"] == company_id:
            return c["role"]
    return None


def projects_for(username, company_id=None):
    """المشاريع اللي المستخدم يقدر يشوفها — كلها، أو شركة واحدة منهم."""
    allowed = [c["id"] for c in companies_for(username)]
    if company_id is not None:
        allowed = [c for c in allowed if c == company_id]
    if not allowed:
        return []
    marks = ",".join("?" * len(allowed))
    return fetch_all(f"SELECT * FROM projects WHERE company_id IN ({marks}) ORDER BY id DESC", tuple(allowed))


def project_role(username, project_id):
    """دور المستخدم في الشركة اللي المشروع تبعها، أو None لو مالوش دخل بيه."""
    p = _one("SELECT company_id FROM projects WHERE id=?", (project_id,))
    return role_in(username, p["company_id"]) if p else None


def can_access_project(username, project_id):
    p = _one("SELECT company_id FROM projects WHERE id=?", (project_id,))
    return bool(p) and role_in(username, p["company_id"]) is not None


def create_project(actor, company_id, name, project_type, resolution, orientation, aspect_ratio,
                   episode_count=None, type_details=None):
    """مشروع جديد في شركة معيّنة. قبل F1 المشروع كان بيتعمل من غير شركة وكل الناس
    تشوفه؛ دلوقتي بيتسجّل تبع الشركة اللي المستخدم شغال فيها.

    المسلسل لازم يجي بعدد حلقاته (≥1)، والحلقات من 1 لـ N بتتعمل معاه على
    طول عشان رفع السكريبت يبقى "لأنهي حلقة" من أول يوم. type_details: dict
    بالتفاصيل الخاصة بالنوع، بيتخزن JSON."""
    if project_type == "مسلسل":
        try:
            episode_count = int(episode_count)
        except (TypeError, ValueError):
            episode_count = 0
        if episode_count < 1:
            raise ValueError("المسلسل لازم يبقى له عدد حلقات (1 أو أكتر)")
    import json
    role = role_in(actor, company_id)
    if role is None:
        raise AccessDenied("مش عضو في المشروع ده")
    if not permissions.can(role, "create_project"):
        raise permissions.Denied("create_project")
    from database import run_query
    with audit.action("project_create", "projects", summary=f"إنشاء مشروع «{name}»",
                      username=actor, company_id=company_id) as act:
        act.extra = {"نوع": project_type}
        with permissions.system():
            project_id = run_query(
                "INSERT INTO projects (name, project_type, default_resolution, default_orientation, "
                "default_aspect_ratio, company_id, type_details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, project_type, resolution, orientation, aspect_ratio, company_id,
                 json.dumps(type_details, ensure_ascii=False) if type_details else None))
            if project_type == "مسلسل":
                import repo
                repo.ensure_episodes(project_id, episode_count)
                act.extra["حلقات"] = episode_count
        act.entity_id = act.project_id = project_id
    return project_id


def delete_project(actor, project_id):
    """مسح مشروع — بعد التأكد إنه تبع شركة المستخدم فعلًا.

    repo.delete_project بيفحص الصلاحية (مدير الشركة) بس مش بيفحص المشروع تبع
    مين، فـ id من شركة تانية كان هيتمسح بصلاحية أدمن شركتك انت. أخطر عملية في
    البرنامج، فالفحص هنا قبل أي مسح.
    """
    role = project_role(actor, project_id)
    if role is None:
        raise AccessDenied("المشروع ده مش من مشاريع مساحة عملك")
    if not permissions.can(role, "delete_project"):
        raise permissions.Denied("delete_project")
    import repo
    with permissions.system():
        repo.delete_project(project_id)


# --- إدارة الفريق (مدير الشركة أو المشغّل) -------------------------------------------------

def _require_admin(actor, company_id):
    if role_in(actor, company_id) not in ("admin", "operator"):
        raise AccessDenied("مدير المشروع بس يقدر يعمل ده")


def _require_manageable(actor, company_id, username):
    """الأدمن يدير أعضاء شركته بس — وعمره ما يلمس حساب مشغّل المنصة.

    المشغّل عضو في شركة (الافتراضية مثلًا)؛ لو أدمن الشركة دي قدر يغيّر كلمة سره
    يبقى خد المنصة كلها. عشان كده حساب المشغّل مايديروش غير مشغّل.
    """
    _require_admin(actor, company_id)
    target = user(username)
    if not target or not _one("SELECT 1 AS ok FROM memberships WHERE company_id=? AND user_id=?",
                              (company_id, target["id"])):
        raise AccessDenied("المستخدم ده مش عضو في المشروع ده")
    if target["is_operator"] and not user(actor)["is_operator"]:
        raise AccessDenied("حساب مشغّل المنصة مايتعدّلش من هنا")
    return target


def rename_company(actor, company_id, name):
    _require_admin(actor, company_id)
    if not (name or "").strip():
        raise ValueError("اسم مساحة العمل مطلوب")
    old = _one("SELECT name FROM companies WHERE id=?", (company_id,))
    with audit.action("company_rename", "companies", entity_id=company_id,
                      summary=f"تغيير اسم مساحة العمل لـ «{name.strip()}»",
                      username=actor, company_id=company_id) as act:
        act.extra = {"من": (old or {}).get("name"), "لـ": name.strip()}
        with _tx() as ex:
            ex("UPDATE companies SET name=? WHERE id=?", (name.strip(), company_id))


def set_subscription_tier(actor, company_id, tier):
    """بتغيّر نوع الاشتراك — المشغّل بس، زي إنشاء مساحة العمل، لحد ما يبقى فيه
    نظام فوترة حقيقي بيحصّل الترقية فعليًا بدل ما تتحط يدوي."""
    u = user(actor)
    if not u or not u["is_operator"]:
        raise AccessDenied("المشغّل بس يقدر يغيّر نوع الاشتراك")
    if tier not in TIERS:
        raise ValueError(f"نوع اشتراك غير معروف: {tier}")
    old = _one("SELECT subscription_tier FROM companies WHERE id=?", (company_id,))
    with audit.action("subscription_tier_change", "companies", entity_id=company_id,
                      summary=f"نوع الاشتراك بقى {TIER_LABELS.get(tier, tier)}",
                      username=actor, company_id=company_id) as act:
        act.extra = {"من": (old or {}).get("subscription_tier"), "لـ": tier}
        with _tx() as ex:
            ex("UPDATE companies SET subscription_tier=? WHERE id=?", (tier, company_id))


def members(actor, company_id):
    if role_in(actor, company_id) is None:
        raise AccessDenied("مش عضو في المشروع ده")
    return fetch_all("""
        SELECT u.username, u.display_name, u.email, u.job_title, u.active AS user_active,
               u.last_login_at, m.role, m.active FROM memberships m JOIN users u ON u.id = m.user_id
        WHERE m.company_id = ? ORDER BY m.active DESC, u.display_name""", (company_id,))


def add_member(actor, company_id, username, display_name=None, role="department",
               job_title=None, email=None):
    """بيضيف مستخدم جديد للشركة (أو مستخدم موجود من شركة تانية). بيرجّع كلمة سر
    مؤقتة لو المستخدم جديد — بتتعرض مرة واحدة للأدمن عشان يبعتها، والمستخدم لازم
    يغيّرها أول ما يدخل."""
    _require_admin(actor, company_id)
    if role not in ROLES:
        raise ValueError(f"دور غير معروف: {role}")
    name = auth.normalize_username(username)
    if not name or not all(ch.isalnum() or ch in "._-" for ch in name):
        raise ValueError("اسم المستخدم لازم يكون حروف إنجليزي وأرقام و . _ - بس")
    existing = user(name)
    password = None
    # F3: صف سجل واحد بمعنى واضح ("ضاف فلان بدور كذا") بدل تلات صفوف جداول.
    with audit.action("member_add", "users", summary=f"إضافة «{name}» للفريق بدور {ROLE_LABELS.get(role, role)}",
                      username=actor, company_id=company_id) as act:
        act.extra = {"المستخدم": name, "الدور": role, "حساب جديد": not existing}
        with _tx() as ex:
            if not existing:
                password = temp_password()
                ex("INSERT INTO users (username, password_hash, display_name, email, job_title, "
                   "is_operator, active, must_change_password, created_at) VALUES (?, ?, ?, ?, ?, 0, 1, 1, ?)",
                   (name, auth.hash_password(password), display_name or name, email, job_title, _now()))
        uid = user(name)["id"]
        act.entity_id = uid
        with _tx() as ex:
            # حساب اتقفل لما اتشال من آخر شركة ليه بيتفتح تاني لما يرجع
            ex("UPDATE users SET active=1 WHERE id=?", (uid,))
            ex("INSERT OR IGNORE INTO memberships (company_id, user_id, role, active, created_at) "
               "VALUES (?, ?, ?, 1, ?)", (company_id, uid, role, _now()))
            ex("UPDATE memberships SET role=?, active=1 WHERE company_id=? AND user_id=?",
               (role, company_id, uid))
    return password


def set_role(actor, company_id, username, role):
    _require_manageable(actor, company_id, username)
    if role not in ROLES:
        raise ValueError(f"دور غير معروف: {role}")
    if auth.normalize_username(username) == auth.normalize_username(actor) and role != "admin":
        raise AccessDenied("مينفعش تشيل صلاحية الأدمن من نفسك — خلّي أدمن تاني يعملها")
    name = auth.normalize_username(username)
    before = role_in(name, company_id)
    with audit.action("role_change", "memberships",
                      summary=f"دور «{name}» بقى {ROLE_LABELS.get(role, role)}",
                      username=actor, company_id=company_id) as act:
        act.extra = {"المستخدم": name, "من": before, "لـ": role}
        with _tx() as ex:
            ex("UPDATE memberships SET role=? WHERE company_id=? AND "
               "user_id=(SELECT id FROM users WHERE username=?)", (role, company_id, name))


def deactivate_member(actor, company_id, username):
    """بيشيل المستخدم من الشركة. لو ملوش شركة تانية، حسابه كله بيتقفل ومايقدرش يدخل."""
    name = auth.normalize_username(username)
    if name == auth.normalize_username(actor):
        raise AccessDenied("مينفعش تقفل حسابك انت")
    uid = _require_manageable(actor, company_id, name)["id"]
    with audit.action("member_remove", "users", entity_id=uid, summary=f"شيل «{name}» من الفريق",
                      username=actor, company_id=company_id) as act:
        with _tx() as ex:
            ex("UPDATE memberships SET active=0 WHERE company_id=? AND user_id=?", (company_id, uid))
        left = _one("SELECT COUNT(*) AS n FROM memberships WHERE user_id=? AND active=1", (uid,))["n"]
        if not left and not user(name)["is_operator"]:
            with _tx() as ex:
                ex("UPDATE users SET active=0 WHERE id=?", (uid,))
        act.extra = {"المستخدم": name, "الحساب اتقفل": not left}


def reset_password(actor, company_id, username):
    """كلمة سر مؤقتة جديدة لعضو في الشركة؛ لازم يغيّرها أول ما يدخل."""
    target = _require_manageable(actor, company_id, username)
    password = temp_password()
    # كلمة السر نفسها عمرها ما بتوصل للسجل — الصف بيقول إن التصفير حصل وبس.
    with audit.action("password_reset", "users", entity_id=target["id"],
                      summary=f"تصفير كلمة سر «{target['username']}»",
                      username=actor, company_id=company_id):
        with _tx() as ex:
            ex("UPDATE users SET password_hash=?, must_change_password=1 WHERE username=?",
               (auth.hash_password(password), auth.normalize_username(username)))
    return password


def change_own_password(username, old_password, new_password):
    if len(new_password or "") < 10:
        raise ValueError("كلمة السر لازم تكون ١٠ حروف على الأقل")
    name = auth.authenticate(username, old_password, auth_users())
    if not name:
        raise AccessDenied("كلمة السر الحالية غلط")
    company = next((c["id"] for c in companies_for(name)), None)
    with audit.action("password_change", "users", summary=f"«{name}» غيّر كلمة سره",
                      username=name, company_id=company):
        with _tx() as ex:
            ex("UPDATE users SET password_hash=?, must_change_password=0 WHERE username=?",
               (auth.hash_password(new_password), name))


def create_company(actor, name, admin_username, admin_display_name=None, admin_email=None):
    """مساحة عمل جديدة على المنصة وأول أدمن ليها — للمشغّل بس. بيرجّع كلمة سر الأدمن المؤقتة."""
    u = user(actor)
    if not u or not u["is_operator"]:
        raise AccessDenied("المشغّل بس يقدر يضيف مساحة عمل")
    if not (name or "").strip():
        raise ValueError("اسم مساحة العمل مطلوب")
    # صف سجل واحد للشركة الجديدة (مش صف عام + صف بمعنى).
    with audit.action("company_create", "companies", username=actor,
                      summary=f"مساحة عمل جديدة على المنصة: «{name.strip()}»") as act:
        with _tx() as ex:
            ex("INSERT INTO companies (name, active, created_at) VALUES (?, 1, ?)",
               (name.strip(), _now()))
        company_id = _one("SELECT MAX(id) AS id FROM companies")["id"]
        act.entity_id = act.company_id = company_id
    return company_id, add_member(actor, company_id, admin_username, admin_display_name, "admin",
                                  "مدير المشروع", admin_email)
