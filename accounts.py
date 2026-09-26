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
    # الحساب الموقوف أو اللي مدته خلصت (🛡️ إدارة الحسابات) مايدخلش، وجلسته المفتوحة بتقفل
    today = dt.date.today().isoformat()
    return {r["username"]: r["password_hash"]
            for r in fetch_all("SELECT username, password_hash FROM users WHERE active=1 "
                               "AND (expires_at IS NULL OR expires_at='' OR expires_at >= ?)", (today,))}


def user(username):
    return _one("SELECT id, username, display_name, email, job_title, is_operator, active, "
                "must_change_password, last_login_at, created_by FROM users WHERE username=?",
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


# (أ) أعضاء لكل مشروع: الأدوار دي بتشوف كل مشاريع مساحة العمل. الباقي بيشوف
# المشاريع اللي هو عضو فيها (project_members)، أو المشاريع القديمة اللي لسه
# ماتحددلهاش أعضاء (members_scoped = 0) - زي ما كانوا بيشوفوها قبل الميزة.
SEES_ALL_PROJECTS = ("operator", "admin")

_VISIBLE_TO_MEMBER = ("(COALESCE(p.members_scoped, 0) = 0 OR EXISTS "
                      "(SELECT 1 FROM project_members pm WHERE pm.project_id = p.id AND pm.user_id = ?))")


def projects_for(username, company_id=None):
    """المشاريع اللي المستخدم يقدر يشوفها — كلها، أو مساحة عمل واحدة منهم."""
    companies = companies_for(username)
    if company_id is not None:
        companies = [c for c in companies if c["id"] == company_id]
    if not companies:
        return []
    everything = [c["id"] for c in companies if c["role"] in SEES_ALL_PROJECTS]
    limited = [c["id"] for c in companies if c["role"] not in SEES_ALL_PROJECTS]
    parts, params = [], []
    if everything:
        parts.append(f"p.company_id IN ({','.join('?' * len(everything))})")
        params += everything
    if limited:
        parts.append(f"(p.company_id IN ({','.join('?' * len(limited))}) AND {_VISIBLE_TO_MEMBER})")
        params += limited + [user(username)["id"]]
    return fetch_all(f"SELECT p.* FROM projects p WHERE {' OR '.join(parts)} ORDER BY p.id DESC", tuple(params))


def project_role(username, project_id):
    """دور المستخدم في مساحة العمل اللي المشروع تبعها — بس لو يقدر يدخل
    المشروع ده نفسه؛ وإلا None."""
    if not can_access_project(username, project_id):
        return None
    p = _one("SELECT company_id FROM projects WHERE id=?", (project_id,))
    return role_in(username, p["company_id"])


def can_access_project(username, project_id):
    p = _one("SELECT company_id, members_scoped FROM projects WHERE id=?", (project_id,))
    if not p:
        return False
    role = role_in(username, p["company_id"])
    if role is None:
        return False
    if role in SEES_ALL_PROJECTS or not p["members_scoped"]:
        return True
    return _one("SELECT 1 AS ok FROM project_members WHERE project_id=? AND user_id=?",
                (project_id, user(username)["id"])) is not None


def create_project(actor, company_id, name, project_type, resolution, orientation, aspect_ratio,
                   episode_count=None, type_details=None, add_all_members=False):
    """مشروع جديد في شركة معيّنة. قبل F1 المشروع كان بيتعمل من غير شركة وكل الناس
    تشوفه؛ دلوقتي بيتسجّل تبع الشركة اللي المستخدم شغال فيها.

    المسلسل لازم يجي بعدد حلقاته (≥1)، والحلقات من 1 لـ N بتتعمل معاه على
    طول عشان رفع السكريبت يبقى "لأنهي حلقة" من أول يوم. type_details: dict
    بالتفاصيل الخاصة بالنوع، بيتخزن JSON."""
    import admin_users
    admin_users.require_feature(actor, "new_projects")
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
        raise AccessDenied("مش عضو في مساحة العمل دي")
    if not permissions.can(role, "create_project"):
        raise permissions.Denied("create_project")
    from database import run_query
    with audit.action("project_create", "projects", summary=f"إنشاء مشروع «{name}»",
                      username=actor, company_id=company_id) as act:
        act.extra = {"نوع": project_type}
        with permissions.system():
            project_id = run_query(
                "INSERT INTO projects (name, project_type, default_resolution, default_orientation, "
                "default_aspect_ratio, company_id, type_details, members_scoped, created_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)",
                (name, project_type, resolution, orientation, aspect_ratio, company_id,
                 json.dumps(type_details, ensure_ascii=False) if type_details else None,
                 auth.normalize_username(actor)))
            # (أ) المشروع الجديد: منشئه عضو فيه على طول (والمديرين بيشوفوا
            # الكل أصلًا)، و"كل الفريق" لو اتطلب في الفورم
            uids = {user(actor)["id"]}
            if add_all_members:
                uids |= {r["user_id"] for r in fetch_all(
                    "SELECT user_id FROM memberships WHERE company_id=? AND active=1", (company_id,))}
            for uid in uids:
                run_query("INSERT OR IGNORE INTO project_members (project_id, user_id, added_by, added_at) "
                          "VALUES (?, ?, ?, ?)", (project_id, uid, actor, _now()))
            act.extra["كل الفريق"] = bool(add_all_members)
            if project_type == "مسلسل":
                import repo
                repo.ensure_episodes(project_id, episode_count)
                act.extra["حلقات"] = episode_count
        act.entity_id = act.project_id = project_id
    return project_id


def project_team(actor, project_id):
    """أعضاء مساحة العمل بالنسبة للمشروع ده: كل عضو نشط، ودوره، وهل بيشوف
    المشروع (مدير = بيشوف الكل دايمًا). للمدير أو المشغّل بس."""
    p = _one("SELECT company_id, members_scoped FROM projects WHERE id=?", (project_id,))
    if not p:
        raise AccessDenied("المشروع ده مش موجود")
    role = role_in(actor, p["company_id"])
    if role is None or not permissions.can(role, "manage_team"):
        raise AccessDenied("تحديد أعضاء المشروع لمدير المشروع بس")
    rows = fetch_all("""
        SELECT u.id AS user_id, u.username, u.display_name, u.job_title, m.role,
               EXISTS (SELECT 1 FROM project_members pm WHERE pm.project_id=? AND pm.user_id=u.id) AS listed
        FROM memberships m JOIN users u ON u.id = m.user_id
        WHERE m.company_id=? AND m.active=1 AND u.active=1
        ORDER BY u.display_name, u.username""", (project_id, p["company_id"]))
    scoped = bool(p["members_scoped"])
    return {"scoped": scoped, "members": [dict(
        r, sees_all=r["role"] in SEES_ALL_PROJECTS,
        in_project=r["role"] in SEES_ALL_PROJECTS or not scoped or bool(r["listed"])) for r in rows]}


def set_project_team(actor, project_id, usernames):
    """أعضاء المشروع = usernames دول (من أعضاء مساحة العمل النشطين). أول مرة
    بتتعمل لمشروع قديم بتقفله على اللي اتختاروا (members_scoped=1). المديرين
    بيفضلوا شايفين كل حاجة مهما كانت القايمة. بيرجّع (اتضافوا، اتشالوا)."""
    team = project_team(actor, project_id)          # فحص الصلاحية جوه
    wanted = {auth.normalize_username(u) for u in usernames}
    by_name = {m["username"]: m for m in team["members"] if not m["sees_all"]}
    current = {n for n, m in by_name.items() if m["in_project"]}
    target = {n for n in wanted if n in by_name}
    added, removed = sorted(target - current), sorted(current - target)
    if not team["scoped"]:
        # المشروع كان مفتوح للكل: القايمة المحفوظة بتبدأ من اللي اتختاروا بالظبط
        added = sorted(target)
    with audit.action("project_members", "project_members", project_id=project_id, username=actor,
                      summary=f"تحديد أعضاء المشروع ({len(target)} عضو)") as act:
        act.extra = {"اتضافوا": added, "اتشالوا": removed}
        with _tx() as ex:
            ex("UPDATE projects SET members_scoped=1 WHERE id=?", (project_id,))
            for n in removed:
                ex("DELETE FROM project_members WHERE project_id=? AND user_id=?",
                   (project_id, by_name[n]["user_id"]))
            for n in added:
                ex("INSERT OR IGNORE INTO project_members (project_id, user_id, added_by, added_at) "
                   "VALUES (?, ?, ?, ?)", (project_id, by_name[n]["user_id"], actor, _now()))
    return added, removed


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
        raise AccessDenied("المستخدم ده مش عضو في مساحة العمل دي")
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
        raise AccessDenied("مش عضو في مساحة العمل دي")
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


# --- 👤 حسابي: حسابات جديدة من المشغّل (المالك 2026-09-26) ---------------------------
# "وسيلة سلسة جوه اليوزر بتاعي أطلّع بيها يوزر نيم وباسوورد أديه لشخص، والشخص ده
# بعد كده يقدر يغيّر الباسوورد." الحساب الجديد بياخد مساحة عمل شخصية (زي كل
# الحسابات) وكلمة سر مؤقتة بتتعرض مرة واحدة، ولازم يغيّرها أول ما يدخل.

def _require_operator(actor):
    u = user(actor)
    if not u or not u["is_operator"]:
        raise AccessDenied("المشغّل بس يقدر يعمل حسابات جديدة")
    return u


def create_account(actor, display_name, username, tier="studio"):
    """بيرجّع (company_id، كلمة السر المؤقتة). اسم دخول مستخدم قبل كده = خطأ،
    عشان مانضيفش حد موجود لمساحة عمل جديدة من غير ما نقصد."""
    _require_operator(actor)
    name = auth.normalize_username(username)
    if not name or not all(ch.isalnum() and ch.isascii() or ch in "._-" for ch in name):
        raise ValueError("اسم الدخول لازم يكون حروف إنجليزي وأرقام و . _ - بس")
    if user(name):
        raise ValueError("اسم الدخول ده مستخدم قبل كده — اختار اسم تاني")
    if tier not in TIERS:
        raise ValueError(f"نوع اشتراك غير معروف: {tier}")
    shown = (display_name or "").strip() or name
    company_id, password = create_company(actor, shown, name, shown)
    set_subscription_tier(actor, company_id, tier)
    with _tx() as ex:
        ex("UPDATE users SET created_by=? WHERE username=?", (auth.normalize_username(actor), name))
    return company_id, password


def accounts_created_by(actor):
    _require_operator(actor)
    return fetch_all("""SELECT username, display_name, created_at, last_login_at, must_change_password, active
                        FROM users WHERE created_by=? ORDER BY created_at DESC, id DESC""",
                     (auth.normalize_username(actor),))


def operator_reset_password(actor, username):
    """كلمة سر مؤقتة جديدة لحساب عمله المشغّل ده (نسيها، أو الرسالة ضاعت)."""
    _require_operator(actor)
    target = user(username)
    if not target or target["created_by"] != auth.normalize_username(actor):
        raise AccessDenied("تقدر تطلّع كلمة سر جديدة للحسابات اللي إنت عملتها بس")
    company = next((c["id"] for c in companies_for(target["username"]) if c["role"] == "admin"), None)
    if company is None:
        raise AccessDenied("الحساب ده مالوش مساحة عمل")
    return reset_password(actor, company, target["username"])


# --- فريق المشروع (المالك 2026-09-24) ---------------------------------------------
# "مساحة العمل" مابقتش تظهر لليوزر خالص: الفريق بيتضاف على المشروع نفسه (مباشرة
# لو عنده حساب، أو بلينك دعوة). اللي أنشأ المشروع هو مدير المشروع، وكل واحد
# ليه شغلانة في المشروع (مدير تصوير، مونتير...) وصلاحية (يعدّل / يتفرج).
# جوه قاعدة البيانات مساحة العمل (companies) لسه هي حدود العزل: العضو
# المدعو بيتسجل عضو في مساحة عمل صاحب المشروع، بس بيشوف مشروعه بس.

import hashlib as _hashlib

# رؤساء الأقسام في الإنتاج السينمائي - شغلانة كل واحد في فريق المشروع
PROJECT_JOBS = [
    "المنتج", "مدير الإنتاج", "المخرج", "مساعد المخرج الأول", "كاتب السيناريو",
    "مدير التصوير", "مهندس الديكور", "مصمم الملابس", "الماكيير", "مهندس الصوت",
    "المونتير", "مسؤول الكاستينج", "مشرف الراكور", "مشرف المؤثرات البصرية",
    "مدير المواقع", "الإكسسواريست", "أخرى",
]
PROJECT_MANAGER_LABEL = "مدير المشروع"
PERMISSIONS = {"edit": "يعدّل", "view": "مشاهدة بس"}
INVITE_DAYS = 7


def home_company(username):
    """مساحة العمل الشخصية (اللي المستخدم مديرها) - المشاريع الجديدة بتتعمل فيها."""
    u = user(username)
    if not u:
        return None
    row = _one("""SELECT c.id, c.name, c.active, c.subscription_tier, m.role FROM memberships m
                  JOIN companies c ON c.id = m.company_id
                  WHERE m.user_id=? AND m.active=1 AND m.role='admin' AND c.active=1
                  ORDER BY c.id LIMIT 1""", (u["id"],))
    if row:
        return dict(row, role="operator" if u["is_operator"] else row["role"])
    companies = companies_for(username)
    return companies[0] if companies else None


def _project_row(project_id):
    return _one("SELECT id, name, company_id, created_by FROM projects WHERE id=?", (project_id,))


def is_project_manager(username, project_id):
    """مدير المشروع = اللي أنشأه. المشاريع القديمة (من غير منشئ) مديرها
    أدمن مساحة العمل. والمشغّل بيقدر يدير أي مشروع."""
    p = _project_row(project_id)
    if not p or not can_access_project(username, project_id):
        return False
    name = auth.normalize_username(username)
    u = user(name)
    if u and u["is_operator"]:
        return True
    if p["created_by"]:
        return p["created_by"] == name
    return role_in(name, p["company_id"]) == "admin"


def project_context(username, project_id):
    """كل اللي الشاشة محتاجاه عن المستخدم في المشروع ده: مساحة العمل (للعزل
    والسجل)، الدور (للصلاحيات)، الباقة، وشغلانته في المشروع."""
    p = _project_row(project_id)
    if not p or not can_access_project(username, project_id):
        return None
    role = role_in(username, p["company_id"])
    company = _one("SELECT subscription_tier FROM companies WHERE id=?", (p["company_id"],)) or {}
    manager = is_project_manager(username, project_id)
    member = _one("SELECT pm.job_title, pm.permission FROM project_members pm JOIN users u ON u.id = pm.user_id "
                  "WHERE pm.project_id=? AND u.username=?", (project_id, auth.normalize_username(username)))
    if not manager and role not in SEES_ALL_PROJECTS and member and member["permission"] == "view":
        role = "viewer"
    # المشغّل بيقدر يدير أي مشروع، بس مش "مدير المشروع" في مشاريع غيره
    creator = (p["created_by"] == auth.normalize_username(username)) or (
        not p["created_by"] and role_in(username, p["company_id"]) == "admin")
    if manager and not creator and role == "operator":
        job = ROLE_LABELS["operator"]
    elif manager:
        job = PROJECT_MANAGER_LABEL
    else:
        job = (member or {}).get("job_title") or ROLE_LABELS.get(role, role)
    return {"company_id": p["company_id"], "role": role, "tier": company.get("subscription_tier") or "creator",
            "is_manager": manager, "job": job}


def _require_project_manager(actor, project_id):
    if not is_project_manager(actor, project_id):
        raise AccessDenied("إدارة فريق المشروع لمدير المشروع بس")
    p = _project_row(project_id)
    tier = (_one("SELECT subscription_tier FROM companies WHERE id=?", (p["company_id"],)) or {}).get(
        "subscription_tier") or "creator"
    if not TIER_ALLOWS_TEAM.get(tier, True):
        raise AccessDenied("فريق العمل متاح في باقة Studio أو Enterprise")
    return p


def project_team_view(actor, project_id):
    """فريق المشروع لأي حد في المشروع: مدير المشروع الأول، وبعده الأعضاء
    بشغلاناتهم وصلاحياتهم، والدعوات اللي لسه ماتقبلتش (للمدير بس)."""
    p = _project_row(project_id)
    if not p or not can_access_project(actor, project_id):
        raise AccessDenied("المشروع ده مش متاح لحسابك")
    manager_name = p["created_by"]
    if not manager_name:
        row = _one("SELECT u.username FROM memberships m JOIN users u ON u.id = m.user_id "
                   "WHERE m.company_id=? AND m.role='admin' AND m.active=1 ORDER BY m.id LIMIT 1", (p["company_id"],))
        manager_name = row["username"] if row else None
    people = []
    if manager_name:
        mu = user(manager_name)
        people.append({"username": manager_name, "display_name": (mu or {}).get("display_name") or manager_name,
                       "job": PROJECT_MANAGER_LABEL, "permission": "edit", "is_manager": True})
    for r in fetch_all("""
        SELECT u.username, u.display_name, pm.job_title, COALESCE(pm.permission, 'edit') AS permission
        FROM project_members pm JOIN users u ON u.id = pm.user_id
        JOIN memberships m ON m.user_id = u.id AND m.company_id = ? AND m.active = 1
        WHERE pm.project_id = ? AND u.active = 1 ORDER BY pm.id""", (p["company_id"], project_id)):
        if r["username"] == manager_name:
            continue
        people.append({"username": r["username"], "display_name": r["display_name"] or r["username"],
                       "job": r["job_title"] or "—", "permission": r["permission"], "is_manager": False})
    manager = is_project_manager(actor, project_id)
    invites = []
    if manager:
        invites = [dict(r) for r in fetch_all("""
            SELECT id, invitee_name, contact, job_title, permission, created_at, expires_at FROM project_invites
            WHERE project_id=? AND accepted_by IS NULL AND COALESCE(revoked, 0)=0 AND expires_at > ?
            ORDER BY id DESC""", (project_id, _now()))]
    return {"project": dict(p), "people": people, "invites": invites, "can_manage": manager}


def _join_project(ex, project_id, company_id, uid, job, permission, actor):
    """العضوية: عضو في مساحة عمل المشروع (بصلاحية تناسبه) + في فريق المشروع."""
    role = "viewer" if permission == "view" else "department"
    ex("INSERT OR IGNORE INTO memberships (company_id, user_id, role, active, created_at) VALUES (?, ?, ?, 1, ?)",
       (company_id, uid, role, _now()))
    # مايتنزلش دور حد أعلى (منتج/أدمن) ولا يتقفل حد "يعدّل" لمشاهدة في مشروع تاني
    ex("UPDATE memberships SET active=1, role=CASE WHEN role IN ('admin', 'producer', 'manager') THEN role "
       "WHEN ? = 'department' THEN 'department' ELSE role END WHERE company_id=? AND user_id=?",
       (role, company_id, uid))
    ex("INSERT OR IGNORE INTO project_members (project_id, user_id, added_by, added_at, job_title, permission) "
       "VALUES (?, ?, ?, ?, ?, ?)", (project_id, uid, actor, _now(), job, permission))
    ex("UPDATE project_members SET job_title=?, permission=? WHERE project_id=? AND user_id=?",
       (job, permission, project_id, uid))
    ex("UPDATE projects SET members_scoped=1 WHERE id=?", (project_id,))


def _check_job_permission(job, permission):
    if job not in PROJECT_JOBS:
        raise ValueError("اختار الشغلانة من القايمة")
    if permission not in PERMISSIONS:
        raise ValueError("صلاحية غير معروفة")


def add_to_project(actor, project_id, username, job, permission="edit"):
    """بيضيف مستخدم عنده حساب لفريق المشروع على طول."""
    import admin_users
    admin_users.require_feature(actor, "invite_team")
    p = _require_project_manager(actor, project_id)
    _check_job_permission(job, permission)
    name = auth.normalize_username(username)
    u = user(name)
    if not u or not u["active"]:
        raise ValueError("مفيش حساب بالاسم ده — ابعتله لينك دعوة بدل كده")
    with audit.action("project_team_add", "project_members", project_id=project_id, username=actor,
                      summary=f"إضافة «{name}» لفريق المشروع ({job})") as act:
        act.extra = {"المستخدم": name, "الشغلانة": job, "الصلاحية": permission}
        with _tx() as ex:
            _join_project(ex, project_id, p["company_id"], u["id"], job, permission, actor)
    return name


def update_project_member(actor, project_id, username, job, permission):
    p = _require_project_manager(actor, project_id)
    _check_job_permission(job, permission)
    name = auth.normalize_username(username)
    u = user(name)
    if not u:
        raise ValueError("مفيش حساب بالاسم ده")
    with audit.action("project_team_update", "project_members", project_id=project_id, username=actor,
                      summary=f"«{name}» في المشروع: {job} · {PERMISSIONS[permission]}"):
        with _tx() as ex:
            _join_project(ex, project_id, p["company_id"], u["id"], job, permission, actor)


def remove_from_project(actor, project_id, username):
    p = _require_project_manager(actor, project_id)
    name = auth.normalize_username(username)
    if p["created_by"] == name:
        raise AccessDenied("مدير المشروع مايتشالش من مشروعه")
    u = user(name)
    if not u:
        return
    with audit.action("project_team_remove", "project_members", project_id=project_id, username=actor,
                      summary=f"شيل «{name}» من فريق المشروع"):
        with _tx() as ex:
            ex("DELETE FROM project_members WHERE project_id=? AND user_id=?", (project_id, u["id"]))


def _hash_token(token):
    return _hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def create_invite(actor, project_id, invitee_name, contact, job, permission="edit"):
    """لينك دعوة للمشروع - بيرجّع التوكن (بيتعرض مرة واحدة للمدير يبعته)."""
    import admin_users
    admin_users.require_feature(actor, "invite_team")
    _require_project_manager(actor, project_id)
    _check_job_permission(job, permission)
    token = _secrets.token_urlsafe(24)
    expires = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=INVITE_DAYS)).isoformat(timespec="seconds")
    with audit.action("project_invite", "project_invites", project_id=project_id, username=actor,
                      summary=f"دعوة «{(invitee_name or '').strip() or contact or '?'}» للمشروع ({job})"):
        with _tx() as ex:
            ex("INSERT INTO project_invites (project_id, token_hash, invitee_name, contact, job_title, permission, "
               "created_by, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
               (project_id, _hash_token(token), (invitee_name or "").strip() or None, (contact or "").strip() or None,
                job, permission, actor, _now(), expires))
    return token


def invite_info(token):
    """الدعوة لو صالحة (مش مستخدمة، مش ملغية، مش منتهية)، وإلا None."""
    if not token or len(token) > 100:
        return None
    r = _one("""SELECT i.*, p.name AS project_name, p.company_id FROM project_invites i
                JOIN projects p ON p.id = i.project_id
                WHERE i.token_hash=? AND i.accepted_by IS NULL AND COALESCE(i.revoked, 0)=0 AND i.expires_at > ?""",
             (_hash_token(token), _now()))
    if not r:
        return None
    inviter = user(r["created_by"]) or {}
    return dict(r, inviter=inviter.get("display_name") or r["created_by"])


def accept_invite(token, username):
    """المستخدم (بعد ما دخل) بيقبل الدعوة: بيدخل فريق المشروع. بيرجّع project_id."""
    inv = invite_info(token)
    u = user(username)
    if not inv or not u or not u["active"]:
        return None
    with audit.action("project_invite_accept", "project_invites", project_id=inv["project_id"],
                      username=u["username"], summary=f"«{u['username']}» قبل دعوة المشروع «{inv['project_name']}»"):
        with _tx() as ex:
            # قبول مرة واحدة: الجملة بتشترط إن الدعوة لسه متاحة
            ex("UPDATE project_invites SET accepted_by=?, accepted_at=? WHERE id=? AND accepted_by IS NULL",
               (u["username"], _now(), inv["id"]))
            _join_project(ex, inv["project_id"], inv["company_id"], u["id"], inv["job_title"], inv["permission"],
                          inv["created_by"])
    return inv["project_id"]


def register_from_invite(token, username, display_name, password):
    """حساب جديد من لينك دعوة: المستخدم بيختار اسم دخوله وكلمة سره، وبيتعمله
    مساحة عمل شخصية (عشان يقدر يعمل مشاريعه)، وبيدخل فريق المشروع على طول."""
    inv = invite_info(token)
    if not inv:
        raise ValueError("اللينك ده مابقاش صالح — اطلب لينك جديد من مدير المشروع")
    name = auth.normalize_username(username)
    if not name or not all(ch.isalnum() or ch in "._-" for ch in name) or not name.isascii():
        raise ValueError("اسم المستخدم لازم يكون حروف إنجليزي وأرقام و . _ - بس")
    if user(name):
        raise ValueError("الاسم ده متاخد — اختار اسم تاني، أو ادخل بحسابك لو ده انت")
    if len(password or "") < 10:
        raise ValueError("كلمة السر لازم تبقى 10 حروف على الأقل")
    display = (display_name or "").strip() or name
    with audit.action("user_register_invite", "users", username=name, summary=f"حساب جديد من دعوة: «{name}»"):
        with _tx() as ex:
            ex("INSERT INTO users (username, password_hash, display_name, is_operator, active, must_change_password, "
               "created_at) VALUES (?, ?, ?, 0, 1, 0, ?)", (name, auth.hash_password(password), display, _now()))
            ex("INSERT INTO companies (name, active, created_at) VALUES (?, 1, ?)", (display, _now()))
        uid = user(name)["id"]
        cid = _one("SELECT MAX(id) AS id FROM companies")["id"]
        with _tx() as ex:
            ex("INSERT INTO memberships (company_id, user_id, role, active, created_at) VALUES (?, ?, 'admin', 1, ?)",
               (cid, uid, _now()))
    accept_invite(token, name)
    return name


def revoke_invite(actor, project_id, invite_id):
    _require_project_manager(actor, project_id)
    with _tx() as ex:
        ex("UPDATE project_invites SET revoked=1 WHERE id=? AND project_id=?", (invite_id, project_id))
