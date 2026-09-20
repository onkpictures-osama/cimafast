"""اختبارات منطق الدخول (auth.py) — بتشتغل لوحدها من غير pytest:

    venv/bin/python tests/test_auth.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auth  # noqa: E402

CHECKS = []


def check(fn):
    CHECKS.append(fn)
    return fn


@check
def test_hash_roundtrip():
    stored = auth.hash_password("selim2015")
    assert auth.verify_password("selim2015", stored)
    assert not auth.verify_password("selim2014", stored)
    assert not auth.verify_password("", stored)
    assert not auth.verify_password("SELIM2015", stored)


@check
def test_hash_is_salted():
    # نفس كلمة السر لازم تدي hash مختلف كل مرة (salt عشوائي)
    assert auth.hash_password("x") != auth.hash_password("x")


@check
def test_hash_format():
    stored = auth.hash_password("x", iterations=1000)
    parts = stored.split("$")
    assert len(parts) == 4, stored
    assert parts[0] == "pbkdf2_sha256"
    assert parts[1] == "1000"


@check
def test_broken_hashes_never_pass():
    for bad in ("", "x", "$$$", "pbkdf2_sha256$abc$aa$bb", "md5$1$aa$bb",
                "pbkdf2_sha256$600000$!!!$bb", "pbkdf2_sha256$0$YWE=$YmI=",
                "pbkdf2_sha256$600000$$", None, 123):
        assert not auth.verify_password("anything", bad), bad
        assert not auth.verify_password("", bad), bad


@check
def test_unicode_password():
    # كلمة سر بالعربي لازم تشتغل (الكود القديم كان بيقع معاها في hmac)
    stored = auth.hash_password("سر-قوي-٢٠٢٦")
    assert auth.verify_password("سر-قوي-٢٠٢٦", stored)
    assert not auth.verify_password("سر-قوي-٢٠٢٥", stored)


@check
def test_authenticate():
    users = {"osama": auth.hash_password("selim2015")}
    assert auth.authenticate("osama", "selim2015", users) == "osama"
    # الاسم مش حساس لحالة الحروف ولا للمسافات
    assert auth.authenticate("  OSAMA ", "selim2015", users) == "osama"
    assert auth.authenticate("osama", "wrong", users) is None
    assert auth.authenticate("nobody", "selim2015", users) is None
    assert auth.authenticate("", "", users) is None
    assert auth.authenticate("osama", "selim2015", {}) is None
    assert auth.authenticate(None, None, users) is None


@check
def test_users_from_env():
    stored = auth.hash_password("selim2015")
    os.environ[auth.USERS_ENV] = json.dumps({"Osama": stored})
    try:
        users = auth.resolve_users()
        assert users == {"osama": stored}, users
        assert auth.authenticate("osama", "selim2015", users) == "osama"
    finally:
        os.environ.pop(auth.USERS_ENV, None)


@check
def test_bad_env_is_empty_not_crash():
    for bad in ("not json", "[1,2]", '"text"', "", "   "):
        os.environ[auth.USERS_ENV] = bad
        try:
            assert auth._users_from_env() == {}, bad
        finally:
            os.environ.pop(auth.USERS_ENV, None)


@check
def test_entries_without_a_hash_are_dropped():
    assert auth._clean_users({"a": "", "b": None, "c": 5, "": "h", "d": " h "}) == {"d": "h"}


@check
def test_no_login_flag():
    os.environ.pop(auth.ALLOW_NO_LOGIN_ENV, None)
    assert not auth.no_login_allowed()
    for on in ("1", "true", "YES", "on"):
        os.environ[auth.ALLOW_NO_LOGIN_ENV] = on
        assert auth.no_login_allowed(), on
    for off in ("0", "false", "", "maybe"):
        os.environ[auth.ALLOW_NO_LOGIN_ENV] = off
        assert not auth.no_login_allowed(), off
    os.environ.pop(auth.ALLOW_NO_LOGIN_ENV, None)


def main():
    failures = 0
    for fn in CHECKS:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL {fn.__name__}: {exc}")
    print(f"\n{len(CHECKS) - failures}/{len(CHECKS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
