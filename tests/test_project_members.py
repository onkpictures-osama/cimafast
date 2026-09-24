"""(أ) أعضاء لكل مشروع — مين يشوف أنهي مشروع جوه مساحة العمل.

    venv/bin/python tests/test_project_members.py

بيقفل (موافقة المالك 2026-09-24):
- مدير المشروع (admin) والمشغّل بيشوفوا كل مشاريع مساحة العمل.
- المشروع القديم (قبل الميزة) مفتوح لكل الأعضاء - محدش خسر دخول.
- المشروع الجديد بيبدأ بمنشئه بس، أو بكل الفريق لو اتطلب.
- المدير بس يحدد الأعضاء؛ أول تحديد لمشروع قديم بيقفله على اللي اتختاروا.
- projects_for وcan_access_project وproject_role متفقين دايمًا.
- عضو مساحة عمل تانية أو عضو اتشال عمره ما بيشوف المشروع.

قاعدة بيانات مؤقتة — عمرها ما بتلمس الإنتاج.
"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_TMP = tempfile.mkdtemp(prefix="cimafast-pm-")
os.environ["STUDIO_DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ.pop("DATABASE_URL", None)

import database  # noqa: E402

database.init_db()

import accounts  # noqa: E402
import auth  # noqa: E402
from database import fetch_all, run_query  # noqa: E402

accounts.migrate_accounts({"melzayat": auth.hash_password("pw-123456", iterations=1000)})
A, _ = accounts.create_company("melzayat", "مساحة أ", "boss_a")
B, _ = accounts.create_company("melzayat", "مساحة ب", "boss_b")
accounts.add_member("boss_a", A, "prod_a", role="producer")
accounts.add_member("boss_a", A, "dep_a", role="department")
accounts.add_member("boss_a", A, "view_a", role="viewer")
accounts.add_member("boss_b", B, "dep_b", role="department")

# مشروع قديم: اتعمل قبل الميزة (من غير members_scoped ومن غير أعضاء)
run_query("INSERT INTO projects (name, project_type, company_id) VALUES ('قديم', 'فيلم', ?)", (A,))
OLD = fetch_all("SELECT MAX(id) AS id FROM projects")[0]["id"]
NEW = accounts.create_project("prod_a", A, "جديد", "فيلم", "4K", "أفقي", "16:9")
ALL = accounts.create_project("prod_a", A, "للكل", "فيلم", "4K", "أفقي", "16:9", add_all_members=True)

_results = []


def test(fn):
    _results.append(fn)
    return fn


def _raises(exc, fn, *a):
    try:
        fn(*a)
    except exc:
        return
    raise AssertionError(f"{fn.__name__} ماطلعش {exc.__name__}")


def _sees(username, pid):
    listed = pid in {p["id"] for p in accounts.projects_for(username)}
    access = accounts.can_access_project(username, pid)
    role = accounts.project_role(username, pid)
    assert listed == access == (role is not None), (username, pid, listed, access, role)
    return access


@test
def test_old_project_stays_open_to_every_member():
    for u in ("boss_a", "prod_a", "dep_a", "view_a", "melzayat"):
        assert _sees(u, OLD), u
    assert not _sees("dep_b", OLD) and not _sees("boss_b", OLD)


@test
def test_new_project_starts_with_its_creator_and_the_managers():
    assert _sees("prod_a", NEW) and _sees("boss_a", NEW) and _sees("melzayat", NEW)
    assert not _sees("dep_a", NEW) and not _sees("view_a", NEW)
    assert not _sees("boss_b", NEW)


@test
def test_add_all_members_option():
    for u in ("prod_a", "dep_a", "view_a", "boss_a"):
        assert _sees(u, ALL), u
    assert not _sees("dep_b", ALL)


@test
def test_only_the_manager_sets_the_team():
    _raises(accounts.AccessDenied, accounts.project_team, "dep_a", NEW)
    _raises(accounts.AccessDenied, accounts.project_team, "prod_a", NEW)
    _raises(accounts.AccessDenied, accounts.project_team, "boss_b", NEW)
    team = accounts.project_team("boss_a", NEW)
    names = {m["username"]: m for m in team["members"]}
    assert team["scoped"] and names["boss_a"]["sees_all"] and names["prod_a"]["in_project"]
    assert not names["dep_a"]["in_project"] and "dep_b" not in names


@test
def test_adding_and_removing_a_member():
    added, removed = accounts.set_project_team("boss_a", NEW, ["prod_a", "dep_a", "dep_b"])
    assert added == ["dep_a"] and removed == [], (added, removed)       # dep_b من مساحة تانية: اتجاهل
    assert _sees("dep_a", NEW) and not _sees("dep_b", NEW)
    added, removed = accounts.set_project_team("boss_a", NEW, ["prod_a"])
    assert removed == ["dep_a"] and not _sees("dep_a", NEW)
    # المدير عمره ما بيتشال
    accounts.set_project_team("boss_a", NEW, [])
    assert _sees("boss_a", NEW) and not _sees("prod_a", NEW)
    accounts.set_project_team("boss_a", NEW, ["prod_a"])


@test
def test_first_edit_of_an_old_project_scopes_it():
    team = accounts.project_team("boss_a", OLD)
    assert not team["scoped"] and all(m["in_project"] for m in team["members"])
    accounts.set_project_team("boss_a", OLD, ["dep_a"])
    assert accounts.project_team("boss_a", OLD)["scoped"]
    assert _sees("dep_a", OLD) and not _sees("prod_a", OLD) and not _sees("view_a", OLD)
    assert _sees("boss_a", OLD)


@test
def test_removed_member_loses_every_project():
    accounts.set_project_team("boss_a", ALL, ["dep_a", "prod_a", "view_a"])
    assert _sees("view_a", ALL)
    accounts.deactivate_member("boss_a", A, "view_a")
    assert not _sees("view_a", ALL) and accounts.projects_for("view_a") == []


@test
def test_home_and_notifications_follow_the_same_rule():
    import home
    ids = {c["id"] for c in home.cards("dep_a", "/app/", "/board/")}
    assert NEW not in ids and OLD in ids, ids
    found = {r.get("project_id") for r in home.search("dep_a", "جديد", "/app/")}
    assert NEW not in found, found


def main():
    failed = 0
    for fn in _results:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except Exception as exc:
            failed += 1
            print(f"  FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(_results) - failed}/{len(_results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
