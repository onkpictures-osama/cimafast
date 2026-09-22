"""F1 — الشركات والمستخدمين ومين يشوف إيه. قاعدة بيانات مؤقتة، عمرها ما بتلمس الإنتاج.

    venv/bin/python tests/test_accounts.py

The plan's definition of done for F1: two companies can use CimaFast side by
side and never see each other's projects. Most tests below pin a piece of that.
"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_TMP = tempfile.mkdtemp(prefix="cimafast-accounts-")
os.environ["STUDIO_DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ.pop("DATABASE_URL", None)

import accounts  # noqa: E402
import auth  # noqa: E402
import database  # noqa: E402

database.init_db()
_results = []

# Two legacy accounts exactly as secrets.toml stores them (fast hashes for tests)
LEGACY = {"melzayat": auth.hash_password("owner-pass-123", iterations=1000),
          "producer": auth.hash_password("producer-pass-1", iterations=1000),
          "costume_designer": auth.hash_password("costume-pass-1", iterations=1000)}


def test(fn):
    _results.append(fn)
    return fn


def _project(name, company_id=None):
    database.run_query("INSERT INTO projects (name, project_type, company_id) VALUES (?, 'فيلم', ?)",
                       (name, company_id))
    return database.fetch_all("SELECT MAX(id) AS id FROM projects")[0]["id"]


def _login(username, password):
    return auth.authenticate(username, password, accounts.auth_users())


def _raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    raise AssertionError(f"{fn.__name__} did not raise {exc.__name__}")


# --- the migration --------------------------------------------------------------------

@test
def test_migration_keeps_every_password_and_links_every_project():
    old = _project("مشروع قديم")                      # created before companies existed
    done = accounts.migrate_accounts(LEGACY)
    assert done["users_added"] == 3 and done["company_created"], done
    assert _login("melzayat", "owner-pass-123") == "melzayat"      # nobody's password changed
    assert _login("producer", "producer-pass-1") == "producer"
    company = database.fetch_all("SELECT id, name FROM companies")[0]
    assert company["name"] == accounts.DEFAULT_COMPANY
    assert database.fetch_all("SELECT company_id FROM projects WHERE id=?", (old,))[0]["company_id"] == company["id"]
    assert accounts.user("melzayat")["is_operator"] == 1
    assert accounts.role_in("producer", company["id"]) == "producer"
    assert accounts.role_in("costume_designer", company["id"]) == "department"
    assert accounts.user("costume_designer")["job_title"] == "مصمم أزياء"


@test
def test_migration_is_safe_to_run_every_start():
    before = database.fetch_all("SELECT COUNT(*) AS n FROM users")[0]["n"]
    done = accounts.migrate_accounts(LEGACY)
    assert done["users_added"] == 0 and not done["company_created"], done
    assert database.fetch_all("SELECT COUNT(*) AS n FROM users")[0]["n"] == before
    assert database.fetch_all("SELECT COUNT(*) AS n FROM companies")[0]["n"] == 1


@test
def test_projects_created_later_without_a_company_get_linked_on_the_next_start():
    pid = _project("مشروع من الكود القديم")
    accounts.migrate_accounts(LEGACY)
    assert database.fetch_all("SELECT company_id FROM projects WHERE id=?", (pid,))[0]["company_id"] is not None


# --- F1's definition of done: two companies, never seeing each other ------------------

def _two_companies():
    a_id, a_pass = accounts.create_company("melzayat", "شركة أ", "admin_a")
    b_id, b_pass = accounts.create_company("melzayat", "شركة ب", "admin_b")
    pa, pb = _project("فيلم أ", a_id), _project("مسلسل ب", b_id)
    return a_id, b_id, pa, pb


@test
def test_two_companies_never_see_each_others_projects():
    a_id, b_id, pa, pb = _two_companies()
    seen_a = {p["id"] for p in accounts.projects_for("admin_a")}
    seen_b = {p["id"] for p in accounts.projects_for("admin_b")}
    assert pa in seen_a and pb not in seen_a
    assert pb in seen_b and pa not in seen_b
    assert accounts.can_access_project("admin_a", pa) and not accounts.can_access_project("admin_a", pb)
    assert accounts.can_access_project("admin_b", pb) and not accounts.can_access_project("admin_b", pa)
    _raises(accounts.AccessDenied, accounts.members, "admin_a", b_id)
    _raises(accounts.AccessDenied, accounts.add_member, "admin_a", b_id, "spy")


@test
def test_the_operator_sees_every_company():
    ids = {c["id"] for c in accounts.companies_for("melzayat")}
    assert len(ids) == database.fetch_all("SELECT COUNT(*) AS n FROM companies")[0]["n"]
    assert all(c["role"] == "operator" for c in accounts.companies_for("melzayat"))


@test
def test_only_the_operator_creates_companies():
    _raises(accounts.AccessDenied, accounts.create_company, "producer", "شركة س", "x_admin")


# --- managing a team --------------------------------------------------------------------

@test
def test_a_new_member_gets_a_one_time_password_and_must_change_it():
    a_id = accounts.companies_for("admin_a")[0]["id"]
    pw = accounts.add_member("admin_a", a_id, "dop_a", "مدير تصوير أ", "department", "مدير تصوير")
    assert pw and len(pw) >= 12
    assert _login("dop_a", pw) == "dop_a"
    assert accounts.user("dop_a")["must_change_password"] == 1
    accounts.change_own_password("dop_a", pw, "a-real-password-9")
    assert _login("dop_a", "a-real-password-9") == "dop_a" and not _login("dop_a", pw)
    assert accounts.user("dop_a")["must_change_password"] == 0


@test
def test_only_admins_manage_the_team():
    a_id = accounts.companies_for("admin_a")[0]["id"]
    _raises(accounts.AccessDenied, accounts.add_member, "dop_a", a_id, "someone")
    _raises(accounts.AccessDenied, accounts.reset_password, "dop_a", a_id, "admin_a")
    _raises(accounts.AccessDenied, accounts.deactivate_member, "dop_a", a_id, "admin_a")


@test
def test_deactivated_member_loses_access_and_cannot_log_in():
    a_id = accounts.companies_for("admin_a")[0]["id"]
    pw = accounts.add_member("admin_a", a_id, "temp_a", role="viewer")
    assert _login("temp_a", pw)
    accounts.deactivate_member("admin_a", a_id, "temp_a")
    assert accounts.projects_for("temp_a") == []
    assert not _login("temp_a", pw), "an account with no company left must not log in"


@test
def test_a_person_in_two_companies_keeps_the_other_after_leaving_one():
    a_id, b_id = (accounts.companies_for("admin_a")[0]["id"], accounts.companies_for("admin_b")[0]["id"])
    pw = accounts.add_member("admin_a", a_id, "freelancer", role="department")
    accounts.add_member("admin_b", b_id, "freelancer", role="department")     # existing user: no new password
    accounts.deactivate_member("admin_a", a_id, "freelancer")
    assert _login("freelancer", pw) == "freelancer"
    assert {c["id"] for c in accounts.companies_for("freelancer")} == {b_id}


@test
def test_password_reset_replaces_the_old_password():
    a_id = accounts.companies_for("admin_a")[0]["id"]
    new = accounts.reset_password("admin_a", a_id, "dop_a")
    assert _login("dop_a", new) and not _login("dop_a", "a-real-password-9")


@test
def test_admins_cannot_lock_themselves_out():
    a_id = accounts.companies_for("admin_a")[0]["id"]
    _raises(accounts.AccessDenied, accounts.deactivate_member, "admin_a", a_id, "admin_a")
    _raises(accounts.AccessDenied, accounts.set_role, "admin_a", a_id, "admin_a", "viewer")


@test
def test_usernames_and_passwords_are_validated():
    a_id = accounts.companies_for("admin_a")[0]["id"]
    _raises(ValueError, accounts.add_member, "admin_a", a_id, "مستخدم عربي")
    _raises(ValueError, accounts.add_member, "admin_a", a_id, "ok_name", role="king")
    _raises(ValueError, accounts.change_own_password, "admin_a", "whatever", "short")


@test
def test_a_company_admin_can_never_touch_the_platform_operator():
    default = [c for c in accounts.companies_for("melzayat") if c["name"] == accounts.DEFAULT_COMPANY][0]["id"]
    accounts.set_role("melzayat", default, "producer", "admin")        # producer now admins the default company
    _raises(accounts.AccessDenied, accounts.reset_password, "producer", default, "melzayat")
    _raises(accounts.AccessDenied, accounts.deactivate_member, "producer", default, "melzayat")
    _raises(accounts.AccessDenied, accounts.set_role, "producer", default, "melzayat", "viewer")
    assert _login("melzayat", "owner-pass-123") == "melzayat"


@test
def test_admins_only_manage_their_own_members():
    a_id = accounts.companies_for("admin_a")[0]["id"]
    _raises(accounts.AccessDenied, accounts.reset_password, "admin_a", a_id, "admin_b")
    _raises(accounts.AccessDenied, accounts.deactivate_member, "admin_a", a_id, "admin_b")
    _raises(accounts.AccessDenied, accounts.deactivate_member, "admin_a", a_id, "nobody_at_all")


@test
def test_a_removed_person_added_back_can_log_in_again():
    a_id = accounts.companies_for("admin_a")[0]["id"]
    pw = accounts.add_member("admin_a", a_id, "returning", role="department")
    accounts.deactivate_member("admin_a", a_id, "returning")
    assert not _login("returning", pw)
    assert accounts.add_member("admin_a", a_id, "returning") is None      # existing account, old password
    assert _login("returning", pw) == "returning"


@test
def test_admin_renames_the_company():
    a_id = accounts.companies_for("admin_a")[0]["id"]
    accounts.rename_company("admin_a", a_id, "استوديو أ")
    assert accounts.companies_for("admin_a")[0]["name"] == "استوديو أ"
    _raises(accounts.AccessDenied, accounts.rename_company, "dop_a", a_id, "x")


# --- B5: نوع الاشتراك (creator / studio / enterprise) --------------------------------

@test
def test_new_companies_default_to_creator_tier():
    a_id = accounts.companies_for("admin_a")[0]["id"]
    row = [c for c in accounts.companies_for("admin_a") if c["id"] == a_id][0]
    assert row["subscription_tier"] == "creator"


@test
def test_only_the_operator_changes_the_subscription_tier():
    a_id = accounts.companies_for("admin_a")[0]["id"]
    _raises(accounts.AccessDenied, accounts.set_subscription_tier, "admin_a", a_id, "enterprise")
    accounts.set_subscription_tier("melzayat", a_id, "enterprise")
    row = [c for c in accounts.companies_for("admin_a") if c["id"] == a_id][0]
    assert row["subscription_tier"] == "enterprise"


@test
def test_an_unknown_tier_is_rejected():
    a_id = accounts.companies_for("admin_a")[0]["id"]
    _raises(ValueError, accounts.set_subscription_tier, "melzayat", a_id, "gold")


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
