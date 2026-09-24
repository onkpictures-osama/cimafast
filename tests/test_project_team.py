"""فريق المشروع والدعوات (المالك 2026-09-24).

    venv/bin/python tests/test_project_team.py

بيقفل: اللي أنشأ المشروع هو مديره، الفريق بيتضاف على المشروع (بحساب موجود
أو بلينك دعوة)، كل واحد ليه شغلانة وصلاحية في المشروع، المدعو بيشوف مشروعه
بس، اللينك مرة واحدة ولمدة محدودة ويتلغي، المدير بس بيدير (وباقة Creator
مابتضيفش فريق)، والمشاريع القديمة بتتقفل على اللي كانوا شايفينها.

قاعدة بيانات مؤقتة — عمرها ما بتلمس الإنتاج.
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_TMP = tempfile.mkdtemp(prefix="cimafast-team-")
os.environ["STUDIO_DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ.pop("DATABASE_URL", None)

import database  # noqa: E402

database.init_db()

import accounts  # noqa: E402
import auth  # noqa: E402
import permissions  # noqa: E402
from database import fetch_all, run_query  # noqa: E402

accounts.migrate_accounts({"melzayat": auth.hash_password("pw-123456", iterations=1000)})
A, _ = accounts.create_company("melzayat", "مساحة نادية", "nadia")
B, _ = accounts.create_company("melzayat", "مساحة سمير", "samir")
with permissions.system():
    run_query("UPDATE companies SET subscription_tier='studio' WHERE id IN (?, ?)", (A, B))
accounts.add_member("samir", B, "karim", role="admin")            # حساب موجود (مساحته هو)
FILM = accounts.create_project("nadia", A, "فيلم نادية", "فيلم", "4K", "أفقي", "16:9")
SECRET = accounts.create_project("nadia", A, "مشروع تاني لنادية", "فيلم", "4K", "أفقي", "16:9")

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


@test
def test_creator_is_the_project_manager():
    assert fetch_all("SELECT created_by FROM projects WHERE id=?", (FILM,))[0]["created_by"] == "nadia"
    ctx = accounts.project_context("nadia", FILM)
    assert ctx["is_manager"] and ctx["job"] == "مدير المشروع" and ctx["company_id"] == A
    assert accounts.home_company("nadia")["id"] == A
    team = accounts.project_team_view("nadia", FILM)
    assert team["people"][0]["username"] == "nadia" and team["people"][0]["is_manager"]


@test
def test_add_existing_account_with_job_and_permission():
    accounts.add_to_project("nadia", FILM, "karim", "مدير التصوير", "edit")
    ctx = accounts.project_context("karim", FILM)
    assert ctx and ctx["job"] == "مدير التصوير" and not ctx["is_manager"] and permissions.can(ctx["role"], "edit")
    assert not accounts.can_access_project("karim", SECRET)         # بيشوف المشروع اللي اتضاف له بس
    accounts.update_project_member("nadia", FILM, "karim", "مدير التصوير", "view")
    assert accounts.project_context("karim", FILM)["role"] == "viewer"
    accounts.update_project_member("nadia", FILM, "karim", "مدير التصوير", "edit")
    # كريم لسه مدير مساحته هو - الإضافة مانزلتش دوره هناك
    assert accounts.role_in("karim", B) == "admin"


@test
def test_only_the_manager_manages_and_creator_tier_blocks():
    _raises(accounts.AccessDenied, accounts.add_to_project, "karim", FILM, "samir", "المخرج", "edit")
    _raises(accounts.AccessDenied, accounts.create_invite, "karim", FILM, "x", "", "المخرج", "edit")
    _raises(ValueError, accounts.add_to_project, "nadia", FILM, "karim", "رئيس جمهورية", "edit")
    _raises(ValueError, accounts.add_to_project, "nadia", FILM, "no_such_user", "المخرج", "edit")
    with permissions.system():
        run_query("UPDATE companies SET subscription_tier='creator' WHERE id=?", (A,))
    try:
        _raises(accounts.AccessDenied, accounts.add_to_project, "nadia", FILM, "samir", "المخرج", "edit")
    finally:
        with permissions.system():
            run_query("UPDATE companies SET subscription_tier='studio' WHERE id=?", (A,))


@test
def test_invite_new_person_registers_and_sees_only_that_project():
    token = accounts.create_invite("nadia", FILM, "هبة", "0100", "مصمم الملابس", "edit")
    inv = accounts.invite_info(token)
    assert inv["project_name"] == "فيلم نادية" and inv["job_title"] == "مصمم الملابس"
    assert not fetch_all("SELECT 1 FROM project_invites WHERE token_hash=?", (token,)), "التوكن متخزن زي ما هو"
    _raises(ValueError, accounts.register_from_invite, token, "heba", "هبة", "short")
    _raises(ValueError, accounts.register_from_invite, token, "nadia", "هبة", "a-long-password")
    name = accounts.register_from_invite(token, "Heba", "هبة", "a-long-password")
    assert name == "heba"
    assert auth.authenticate("heba", "a-long-password", accounts.auth_users()) == "heba"
    assert [p["id"] for p in accounts.projects_for("heba")] == [FILM]
    assert accounts.project_context("heba", FILM)["job"] == "مصمم الملابس"
    assert accounts.home_company("heba")["role"] == "admin"          # مساحة شخصية لمشاريعها هي
    assert accounts.invite_info(token) is None                        # مرة واحدة بس
    assert accounts.accept_invite(token, "karim") is None


@test
def test_existing_user_accepts_invite():
    token = accounts.create_invite("nadia", SECRET, "سمير", "", "المخرج", "view")
    assert accounts.accept_invite(token, "samir") == SECRET
    assert accounts.project_context("samir", SECRET)["role"] == "viewer"
    assert not accounts.can_access_project("samir", FILM)


@test
def test_revoked_and_expired_invites_are_dead():
    t1 = accounts.create_invite("nadia", FILM, "x", "", "المونتير", "edit")
    inv_id = fetch_all("SELECT MAX(id) AS id FROM project_invites")[0]["id"]
    accounts.revoke_invite("nadia", FILM, inv_id)
    assert accounts.invite_info(t1) is None
    t2 = accounts.create_invite("nadia", FILM, "y", "", "المونتير", "edit")
    past = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).isoformat(timespec="seconds")
    with permissions.system():
        run_query("UPDATE project_invites SET expires_at=? WHERE id=(SELECT MAX(id) FROM project_invites)", (past,))
    assert accounts.invite_info(t2) is None
    assert accounts.invite_info("garbage") is None and accounts.invite_info("") is None


@test
def test_remove_member_and_manager_stays():
    accounts.remove_from_project("nadia", FILM, "karim")
    assert not accounts.can_access_project("karim", FILM)
    _raises(accounts.AccessDenied, accounts.remove_from_project, "nadia", FILM, "nadia")
    names = [p["username"] for p in accounts.project_team_view("nadia", FILM)["people"]]
    assert names[0] == "nadia" and "karim" not in names and "heba" in names


@test
def test_orphan_project_is_not_scoped_to_an_empty_team():
    run_query("INSERT INTO projects (name, project_type) VALUES ('من غير مساحة', 'فيلم')")
    orphan = fetch_all("SELECT MAX(id) AS id FROM projects")[0]["id"]
    database.init_db()
    assert not fetch_all("SELECT members_scoped FROM projects WHERE id=?", (orphan,))[0]["members_scoped"]


@test
def test_legacy_projects_get_scoped_to_who_saw_them():
    accounts.add_member("nadia", A, "old_editor", role="department")
    run_query("INSERT INTO projects (name, project_type, company_id) VALUES ('قديم', 'فيلم', ?)", (A,))
    old = fetch_all("SELECT MAX(id) AS id FROM projects")[0]["id"]
    assert accounts.can_access_project("old_editor", old)
    database.init_db()                                                # بيقفله على اللي كانوا شايفينه
    assert fetch_all("SELECT members_scoped FROM projects WHERE id=?", (old,))[0]["members_scoped"] == 1
    assert accounts.can_access_project("old_editor", old)
    assert not accounts.can_access_project("old_editor", FILM)
    # المشروع القديم مديره أدمن مساحة العمل
    assert accounts.is_project_manager("nadia", old) and not accounts.is_project_manager("old_editor", old)


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
