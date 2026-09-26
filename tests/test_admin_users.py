"""🛡️ إدارة الحسابات: مزايا، إيقاف، مدة، نقل، دمج، حذف (المالك 2026-09-26)."""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_TMP = tempfile.mkdtemp()
os.environ["STUDIO_DB_PATH"] = os.path.join(_TMP, "t.db")
os.environ["CIMAFAST_ADMIN_BACKUPS"] = os.path.join(_TMP, "backups")

import database  # noqa: E402

database.init_db()

import accounts  # noqa: E402
import admin_users as au  # noqa: E402
import auth  # noqa: E402
import permissions  # noqa: E402
from database import fetch_all, run_query  # noqa: E402

TESTS = []
PW = "secret-pass-123"


def test(fn):
    TESTS.append(fn)
    return fn


with permissions.system():
    run_query("INSERT INTO users (username, password_hash, display_name, is_operator, active, must_change_password, "
              "created_at) VALUES ('osama', ?, 'osama', 1, 1, 0, '2026-01-01')", (auth.hash_password(PW),))
H = {}
for name in ("aly", "bob", "cara", "dina", "team.mate"):
    H[name], pw = accounts.create_account("osama", name, name)
    accounts.change_own_password(name, pw, PW)


def _project(owner, pname):
    pid = accounts.create_project(owner, H[owner], pname, "فيلم", "4K", "أفقي", "16:9")
    return pid if isinstance(pid, int) else fetch_all("SELECT id FROM projects WHERE name=?", (pname,))[0]["id"]


P_ALY = _project("aly", "فيلم علي")
accounts.add_to_project("aly", P_ALY, "team.mate", "المونتير")
P_DINA = _project("dina", "فيلم دينا")
accounts.add_to_project("dina", P_DINA, "cara", "مدير التصوير")
with permissions.system():
    run_query("INSERT INTO analysis_library (company_id, owner_username, script_name, payload, saved_at, analysed_at, origin, content_hash) VALUES (?, 'aly', 's', '{}', '2026-01-01', '2026-01-01', 'fast', 'h1')",
              (H["aly"],))
    run_query("INSERT INTO actors (full_name, owner_company_id, created_by) VALUES ('ممثل علي', ?, 'aly')", (H["aly"],))


@test
def test_features_lock_and_unlock():
    assert au.feature_on("aly", "exports")
    au.set_features("osama", "aly", ["exports", "new_projects", "bogus"])
    assert au.disabled_features("aly") == {"exports", "new_projects"}
    assert not au.feature_on("aly", "exports") and au.feature_on("osama", "exports")
    try:
        _project("aly", "ممنوع")
    except accounts.AccessDenied:
        pass
    else:
        raise AssertionError("created a project with new_projects locked")
    au.set_features("osama", "aly", [])
    assert au.feature_on("aly", "new_projects")


@test
def test_suspend_blocks_login_with_a_reason():
    au.set_active("osama", "bob", False)
    assert "bob" not in accounts.auth_users()
    assert "موقوف" in au.blocked_reason("bob", PW)
    assert au.blocked_reason("bob", "wrong") is None
    au.set_active("osama", "bob", True)
    assert "bob" in accounts.auth_users()


@test
def test_expired_account_cannot_log_in():
    au.update_profile("osama", "bob", "بوب", None, None, "تجربة", "creator", "2020-01-01", 5)
    assert "bob" not in accounts.auth_users() and "خلصت" in au.blocked_reason("bob", PW)
    assert au.assistant_limit("bob", 40) == 5
    au.update_profile("osama", "bob", "بوب", None, None, None, "studio", None, None)
    assert "bob" in accounts.auth_users() and au.assistant_limit("bob", 40) == 40


@test
def test_transfer_moves_projects_library_actors_and_keeps_the_team():
    counts, pw, backup = au.transfer("osama", "aly", "bob", keep_access=True)
    assert pw is None and backup and os.path.exists(backup)
    assert counts["مشاريع"] == 1 and counts["تحليلات"] == 1 and counts["ممثلين"] == 1
    p = fetch_all("SELECT company_id, created_by FROM projects WHERE id=?", (P_ALY,))[0]
    assert (p["company_id"], p["created_by"]) == (H["bob"], "bob")
    assert accounts.is_project_manager("bob", P_ALY)
    assert accounts.can_access_project("team.mate", P_ALY), "the crew lost the project"
    assert accounts.can_access_project("aly", P_ALY) and not accounts.is_project_manager("aly", P_ALY)
    assert fetch_all("SELECT owner_username FROM analysis_library")[0]["owner_username"] == "bob"
    assert fetch_all("SELECT owner_company_id FROM actors")[0]["owner_company_id"] == H["bob"]


@test
def test_transfer_to_a_new_account():
    pid = _project("cara", "فيلم كارا")
    counts, pw, _ = au.transfer("osama", "cara", "cara.new", "كارا الجديدة", keep_access=False)
    assert pw and accounts.user("cara.new")["must_change_password"] == 1
    assert fetch_all("SELECT created_by FROM projects WHERE id=?", (pid,))[0]["created_by"] == "cara.new"
    assert not accounts.can_access_project("cara", pid)


@test
def test_merge_moves_memberships_and_closes_the_old_account():
    assert accounts.can_access_project("cara", P_DINA)
    counts, _ = au.merge("osama", "cara", "bob")
    assert counts["مشاريع ناس تانية كان فيها"] == 1
    u = accounts.user("cara")
    assert not u["active"] and fetch_all("SELECT merged_into FROM users WHERE username='cara'")[0]["merged_into"] == "bob"
    assert accounts.can_access_project("bob", P_DINA) and not accounts.can_access_project("cara", P_DINA)
    assert "اتدمج" in au.blocked_reason("cara", PW)


@test
def test_delete_needs_confirmation_and_a_decision_about_projects():
    for confirm, with_p in (("wrong", True), ("dina", False)):
        try:
            au.delete("osama", "dina", confirm, with_p)
        except ValueError:
            continue
        raise AssertionError(f"deleted with {confirm!r}, {with_p}")
    au.delete("osama", "dina", " Dina ", delete_projects=True)
    assert accounts.user("dina") is None
    assert not fetch_all("SELECT id FROM projects WHERE id=?", (P_DINA,))


@test
def test_operators_and_self_are_protected_and_only_operators_act():
    for actor, target in (("osama", "osama"), ("bob", "aly"), ("aly", "bob")):
        try:
            au.set_active(actor, target, False)
        except accounts.AccessDenied:
            continue
        raise AssertionError(f"{actor} suspended {target}")


@test
def test_overview_counts():
    rows = {r["username"]: r for r in au.overview("osama")}
    assert rows["bob"]["projects"] == 1 and rows["cara"]["status"] == "merged"
    assert rows["bob"]["tier"] == "studio"


if __name__ == "__main__":
    passed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
            passed += 1
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            print(f"  FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{passed}/{len(TESTS)} passed")
    sys.exit(0 if passed == len(TESTS) else 1)
