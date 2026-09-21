#!/usr/bin/env python3
"""نقل الإنتاج لعزل الشركات — شركة لكل حساب (F1، تصميم المالك 2026-09-21).

المالك بلّغ إن بيانات المستخدمين بتتلخبط. السبب: قاعدة الإنتاج مافيهاش أي عزل
— مفيش جداول companies/users/memberships، ومفيش projects.company_id، وقايمة
المشاريع كانت ``SELECT * FROM projects`` من غير أي فلتر. يعني أي حساب بيشوف كل
مشاريع كل الناس.

التصميم اللي المالك أقرّه:

- كل حساب من الـ ١٣ ليه شركته لوحده (١ لـ ١)، وهو أدمن فيها.
- مفيش حاجة مشتركة بين الحسابات افتراضيًا.
- المشروع الموجود («القاهرة -سيدى جابر»، id=7) بيروح لشركة حساب ``producer``.
- الباقي بيبدأوا فاضيين.

الجداول نفسها بتفضل عامة (شركة تقدر يبقى فيها كذا عضو) عشان ده اتجاه المنتج في
PRODUCT-PLAN.md — التصميم ده بيوصّف البيانات الحالية بس، مش بيقيّد السكيما.

الاستعمال — نفس الكود بالظبط على النسخة وعلى الحي، الفرق في المسار بس:

    # بروفة على نسخة
    python3 scripts/migrate_tenancy.py --db /tmp/copy.db --apply
    python3 scripts/migrate_tenancy.py --db /tmp/copy.db --check

    # الحي (بعد موافقة المالك صراحةً، وبعد snapshot)
    python3 scripts/migrate_tenancy.py --db /var/lib/cimafast/studio.db --apply

من غير ``--apply`` بيطبع الخطة ومابيكتبش أي حاجة.

النقل ده **بيزوّد بس**: جداول جديدة وعمود جديد. الكود القديم بيفضل شغال على
السكيما الجديدة (``SELECT *`` بيرجّع عمود زيادة وبس)، وده اللي بيخلّي الرجوع
للكود القديم ممكن من غير ما نرجّع قاعدة البيانات.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sqlite3
import sys
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import auth  # noqa: E402

DEFAULT_SECRETS = "/etc/cimafast/secrets.toml"

# حسابات صاحب المنصة: بيشوفوا كل الشركات (accounts.companies_for). ده الاستثناء
# الوحيد المقصود من "كل حساب يشوف بتاعه بس" — صاحب المنصة لازم يقدر يدير.
OPERATORS = {"melzayat", "osama"}

# المسمى الوظيفي لكل حساب — بيتعرض للمستخدم، ومابيأثرش على الصلاحيات.
JOB_TITLES = {
    "melzayat": "صاحب المنصة", "osama": "صاحب المنصة",
    "producer": "منتج", "filmmaker": "صانع أفلام", "director": "مخرج",
    "assistant_director": "مساعد مخرج أول", "dop": "مدير تصوير",
    "art_director": "مدير فني", "costume_designer": "مصمم أزياء",
    "casting_director": "مدير كاستينج", "editor": "مونتير",
    "screenwriter": "سيناريست", "vfx_supervisor": "مشرف مؤثرات بصرية",
}

# مين بياخد المشاريع الموجودة. {رقم المشروع: اسم المستخدم}
PROJECT_OWNERS = {7: "producer"}


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def company_name(username):
    """اسم الشركة على اسم صاحبها. المالك أو أي أدمن يقدر يغيّره بضغطة من صفحة
    الفريق (accounts.rename_company)، فده اسم مبدئي مش قرار نهائي."""
    return f"شركة {username}"


def load_hashes(path):
    with open(path, "rb") as fh:
        cfg = tomllib.load(fh)
    out = {}
    for raw, pw_hash in (cfg.get("users") or {}).items():
        name = auth.normalize_username(raw)
        if name and pw_hash:
            out[name] = pw_hash
    return out


# --- السكيما ----------------------------------------------------------------------
# مابنكتبش السكيما تاني هنا. database.init_db() هي نفسها اللي التطبيق بيشغّلها،
# وكل جملها CREATE TABLE IF NOT EXISTS / ALTER TABLE ADD COLUMN — يعني بتزوّد بس
# ومابتلمسش صف موجود. نسخة تانية من السكيما هنا كانت هتفرق عن الأصل مع أول تعديل،
# وكانت فعلًا هتسيب القاعدة ناقصة جداول (shooting_days، audit_log) التطبيق
# محتاجها. الحتة دي بتخلّي النقل يسيب القاعدة على السكيما الجديدة بالكامل، قبل
# ما أي كود جديد ينزل.


def build_schema(db_path):
    """بيشغّل init_db بتاعة التطبيق على الملف ده بالظبط."""
    os.environ["STUDIO_DB_PATH"] = db_path
    os.environ.pop("DATABASE_URL", None)
    import database
    if database.DB_PATH != db_path:                 # اتستورد قبل ما نظبط المتغير
        database.DB_PATH = db_path
    database.init_db()
    return database


def add_company_id_column(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(projects)")}
    if "company_id" not in cols:
        conn.execute("ALTER TABLE projects ADD COLUMN company_id INTEGER")
        return True
    return False


# --- النقل -------------------------------------------------------------------------

def plan(conn, hashes):
    """بيرجّع الخطة من غير ما يكتب حاجة."""
    projects = conn.execute("SELECT id, name FROM projects ORDER BY id").fetchall()
    known = set(hashes)
    assigned = {pid: who for pid, who in PROJECT_OWNERS.items() if who in known}
    unassigned = [p for p in projects if p[0] not in assigned]
    return {"accounts": sorted(hashes), "projects": projects,
            "assigned": assigned, "unassigned": unassigned}


def migrate(conn, hashes):
    existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing:
        raise SystemExit(f"!! users table already has {existing} rows — refusing to migrate twice.\n"
                         "   This migration is a one-shot. Inspect the DB before re-running.")

    created = add_company_id_column(conn)
    stamp = now()
    ids = {}
    for name in sorted(hashes):
        cur = conn.execute("INSERT INTO companies (name, active, created_at) VALUES (?, 1, ?)",
                           (company_name(name), stamp))
        cid = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, display_name, job_title, is_operator, "
            "active, must_change_password, created_at) VALUES (?, ?, ?, ?, ?, 1, 0, ?)",
            (name, hashes[name], name, JOB_TITLES.get(name), 1 if name in OPERATORS else 0, stamp))
        uid = cur.lastrowid
        # أدمن في شركته: يقدر ينشئ مشاريع ويضيف ناس لفريقه بعدين.
        conn.execute("INSERT INTO memberships (company_id, user_id, role, active, created_at) "
                     "VALUES (?, ?, 'admin', 1, ?)", (cid, uid, stamp))
        ids[name] = (cid, uid)

    linked = {}
    for pid, who in PROJECT_OWNERS.items():
        if who not in ids:
            continue
        row = conn.execute("SELECT id FROM projects WHERE id=?", (pid,)).fetchone()
        if not row:
            continue
        conn.execute("UPDATE projects SET company_id=? WHERE id=?", (ids[who][0], pid))
        linked[pid] = who

    # أي مشروع مالوش صاحب بيتساب من غير شركة عن قصد: مشروع من غير شركة مش بيبان
    # لحد (projects_for بتفلتر بـ company_id IN (...))، وده أأمن من إننا نخمّن
    # ونديه لحد غلط. المالك بيوزّعه بعدين.
    orphans = [r[0] for r in conn.execute("SELECT id FROM projects WHERE company_id IS NULL")]
    conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_company ON projects (company_id)")
    conn.commit()
    return {"companies": len(ids), "users": len(ids), "memberships": len(ids),
            "column_added": created, "linked": linked, "orphans": orphans}


# --- التحقق ------------------------------------------------------------------------

def check(conn, hashes):
    """بيتأكد إن النتيجة مطابقة للتصميم. بيرجّع قايمة مشاكل (فاضية = تمام)."""
    bad = []
    q = lambda s, p=(): conn.execute(s, p).fetchall()  # noqa: E731

    n_companies = q("SELECT COUNT(*) FROM companies")[0][0]
    n_users = q("SELECT COUNT(*) FROM users")[0][0]
    n_members = q("SELECT COUNT(*) FROM memberships")[0][0]
    if n_users != len(hashes):
        bad.append(f"users = {n_users}, expected {len(hashes)}")
    if n_companies != len(hashes):
        bad.append(f"companies = {n_companies}, expected {len(hashes)} (one per account)")
    if n_members != len(hashes):
        bad.append(f"memberships = {n_members}, expected {len(hashes)}")

    # ١ لـ ١: كل شركة فيها عضو واحد، وكل مستخدم في شركة واحدة
    for cid, n in q("SELECT company_id, COUNT(*) FROM memberships GROUP BY company_id"):
        if n != 1:
            bad.append(f"company {cid} has {n} members, expected exactly 1")
    for uid, n in q("SELECT user_id, COUNT(*) FROM memberships GROUP BY user_id"):
        if n != 1:
            bad.append(f"user {uid} is in {n} companies, expected exactly 1")

    # كل حساب: نفس الـ hash (يعني نفس كلمة السر) ودوره أدمن في شركته
    for name, pw_hash in hashes.items():
        row = q("SELECT id, password_hash, active, must_change_password, is_operator "
                "FROM users WHERE username=?", (name,))
        if not row:
            bad.append(f"account '{name}' is missing from users")
            continue
        uid, stored, active, mustchg, is_op = row[0]
        if stored != pw_hash:
            bad.append(f"'{name}' password hash changed — they can no longer log in")
        if not active:
            bad.append(f"'{name}' is inactive")
        if mustchg:
            bad.append(f"'{name}' is forced to change password (migration should not do that)")
        if bool(is_op) != (name in OPERATORS):
            bad.append(f"'{name}' operator flag is {is_op}, expected {name in OPERATORS}")
        role = q("SELECT role FROM memberships WHERE user_id=?", (uid,))
        if not role or role[0][0] != "admin":
            bad.append(f"'{name}' is not admin of their own company")

    # المشاريع
    for pid, who in PROJECT_OWNERS.items():
        row = q("SELECT company_id FROM projects WHERE id=?", (pid,))
        if not row:
            continue
        want = q("SELECT m.company_id FROM memberships m JOIN users u ON u.id=m.user_id "
                 "WHERE u.username=?", (who,))
        if not want or row[0][0] != want[0][0]:
            bad.append(f"project {pid} is in company {row[0][0]}, expected {who}'s company")

    # كل شركة تانية فاضية
    owners = set(PROJECT_OWNERS.values())
    for name in hashes:
        if name in owners:
            continue
        n = q("SELECT COUNT(*) FROM projects p JOIN memberships m ON m.company_id=p.company_id "
              "JOIN users u ON u.id=m.user_id WHERE u.username=?", (name,))[0][0]
        if n:
            bad.append(f"'{name}' company should be empty but has {n} project(s)")

    # البيانات نفسها لسه كاملة ومربوطة بمشروعها
    for table in ("scenes", "characters", "locations", "props"):
        n = q(f"SELECT COUNT(*) FROM {table} WHERE project_id NOT IN (SELECT id FROM projects)")[0][0]
        if n:
            bad.append(f"{n} row(s) in {table} point at a project that does not exist")

    # السكيما كاملة: الكود الجديد بيقرا من الجداول والأعمدة دي، ولو ناقصة
    # التطبيق بيقع وقت التشغيل مش وقت النقل.
    have = {r[0] for r in q("SELECT name FROM sqlite_master WHERE type='table'")}
    for t in ("companies", "users", "memberships", "user_profile",
              "shooting_days", "shooting_day_scenes", "audit_log", "usage_events"):
        if t not in have:
            bad.append(f"table '{t}' is missing — the new code needs it")
    for table, col in (("projects", "company_id"), ("scenes", "scene_suffix"),
                       ("scenes", "episode_number"), ("scenes", "look_change_notes"),
                       ("scenes", "suggested_shot_size"), ("locations", "maps_url"),
                       ("locations", "reference_image_path")):
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if col not in cols:
            bad.append(f"column {table}.{col} is missing — the new code needs it")
    if not q("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_projects_company'"):
        bad.append("index idx_projects_company is missing")
    return bad


def counts(conn):
    out = {}
    for t in ("projects", "scenes", "characters", "locations", "props", "shots",
              "scene_characters", "scene_props", "character_looks", "location_variants",
              "episodes", "companies", "users", "memberships", "shooting_days", "audit_log"):
        try:
            out[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except sqlite3.OperationalError:
            out[t] = None
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="path to the SQLite database")
    ap.add_argument("--secrets", default=DEFAULT_SECRETS, help="secrets.toml with the [users] hashes")
    ap.add_argument("--apply", action="store_true", help="write (default: print the plan only)")
    ap.add_argument("--check", action="store_true", help="verify an already-migrated database")
    args = ap.parse_args()

    hashes = load_hashes(args.secrets)
    if not hashes:
        raise SystemExit(f"!! no [users] found in {args.secrets}")
    args.db = os.path.abspath(args.db)
    if not os.path.exists(args.db):
        raise SystemExit(f"!! no such database: {args.db}")

    # السكيما الجديدة كاملة (جداول + أعمدة) قبل أي حاجة — بس مش في الجفاف.
    if args.apply:
        build_schema(args.db)

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA foreign_keys=ON")

    if args.check:
        problems = check(conn, hashes)
        print(f"== check {args.db}")
        for t, n in counts(conn).items():
            print(f"   {t:20s} {n}")
        if problems:
            print("\n!! FAILED")
            for p in problems:
                print(f"   - {p}")
            return 1
        print("\n== OK: every account is isolated in its own company, data intact")
        return 0

    p = plan(conn, hashes)
    print(f"== plan for {args.db}")
    print(f"   {len(p['accounts'])} accounts -> {len(p['accounts'])} companies (1:1, each user admin)")
    for pid, who in p["assigned"].items():
        name = next((n for i, n in p["projects"] if i == pid), "?")
        print(f"   project {pid} «{name}» -> شركة {who}")
    for pid, name in p["unassigned"]:
        print(f"   project {pid} «{name}» -> LEFT UNASSIGNED (invisible until assigned)")
    if not args.apply:
        print("\n   dry run — nothing written. Re-run with --apply.")
        return 0

    before = counts(conn)
    done = migrate(conn, hashes)
    after = counts(conn)
    print(f"\n== applied: {done['companies']} companies, {done['users']} users, "
          f"{done['memberships']} memberships; company_id column added: {done['column_added']}")
    for pid, who in done["linked"].items():
        print(f"   project {pid} -> شركة {who}")
    if done["orphans"]:
        print(f"   still unassigned: {done['orphans']}")
    print("\n== row counts (before -> after)")
    for t in before:
        mark = "" if before[t] in (after[t], None) else "   <-- CHANGED"
        print(f"   {t:20s} {before[t]} -> {after[t]}{mark}")
    problems = check(conn, hashes)
    if problems:
        print("\n!! post-migration check FAILED")
        for pr in problems:
            print(f"   - {pr}")
        return 1
    print("\n== post-migration check OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
