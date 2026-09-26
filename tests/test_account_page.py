"""👤 حسابي: المشغّل بيعمل حساب لحد بكلمة سر مؤقتة، والشخص بيغيّرها (المالك 2026-09-26)."""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["STUDIO_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

import database  # noqa: E402

database.init_db()

import accounts  # noqa: E402
import auth  # noqa: E402
from database import fetch_all, run_query  # noqa: E402
import permissions  # noqa: E402

TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


with permissions.system():
    for name, op in (("osama", 1), ("melzayat", 1), ("plain", 0)):
        run_query("INSERT INTO users (username, password_hash, display_name, is_operator, active, "
                  "must_change_password, created_at) VALUES (?, ?, ?, ?, 1, 0, '2026-01-01')",
                  (name, auth.hash_password("x" * 12), name, op))

CREATED = {}


@test
def test_operator_creates_an_account_with_a_temporary_password():
    cid, pw = accounts.create_account("osama", "كريم محمود", "  Karim.M ")
    CREATED["pw"] = pw
    u = accounts.user("karim.m")
    assert u and u["display_name"] == "كريم محمود" and u["must_change_password"] == 1
    assert u["created_by"] == "osama"
    assert auth.authenticate("karim.m", pw, accounts.auth_users()) == "karim.m"
    assert accounts.role_in("karim.m", cid) == "admin"
    tier = fetch_all("SELECT subscription_tier FROM companies WHERE id=?", (cid,))[0]["subscription_tier"]
    assert tier == "studio"


@test
def test_the_person_changes_the_password():
    accounts.change_own_password("karim.m", CREATED["pw"], "new-secret-123")
    assert accounts.user("karim.m")["must_change_password"] == 0
    assert auth.authenticate("karim.m", "new-secret-123", accounts.auth_users()) == "karim.m"
    assert not auth.authenticate("karim.m", CREATED["pw"], accounts.auth_users())


@test
def test_bad_or_taken_usernames_are_refused():
    for uname in ("karim.m", "OSAMA", "كريم", "has space", ""):
        try:
            accounts.create_account("osama", "x", uname)
        except ValueError:
            continue
        raise AssertionError(f"accepted {uname!r}")


@test
def test_only_operators_create_accounts():
    for actor in ("plain", "karim.m", "nobody"):
        try:
            accounts.create_account(actor, "x", f"from.{actor}")
        except accounts.AccessDenied:
            continue
        raise AssertionError(f"{actor} created an account")


@test
def test_each_operator_sees_and_resets_only_their_accounts():
    accounts.create_account("melzayat", "حد تاني", "other.one")
    assert [r["username"] for r in accounts.accounts_created_by("osama")] == ["karim.m"]
    assert [r["username"] for r in accounts.accounts_created_by("melzayat")] == ["other.one"]
    pw = accounts.operator_reset_password("osama", "karim.m")
    assert accounts.user("karim.m")["must_change_password"] == 1
    assert auth.authenticate("karim.m", pw, accounts.auth_users()) == "karim.m"
    for target in ("other.one", "melzayat", "plain"):
        try:
            accounts.operator_reset_password("osama", target)
        except accounts.AccessDenied:
            continue
        raise AssertionError(f"osama reset {target}")


if __name__ == "__main__":
    passed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
            passed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{passed}/{len(TESTS)} passed")
    sys.exit(0 if passed == len(TESTS) else 1)
