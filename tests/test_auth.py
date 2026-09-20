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
    stored = auth.hash_password("correct-horse-battery")
    assert auth.verify_password("correct-horse-battery", stored)
    assert not auth.verify_password("correct-horse-batteru", stored)
    assert not auth.verify_password("", stored)
    assert not auth.verify_password("CORRECT-HORSE-BATTERY", stored)


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
    users = {"testuser": auth.hash_password("correct-horse-battery")}
    assert auth.authenticate("testuser", "correct-horse-battery", users) == "testuser"
    # الاسم مش حساس لحالة الحروف ولا للمسافات
    assert auth.authenticate("  TESTUSER ", "correct-horse-battery", users) == "testuser"
    assert auth.authenticate("testuser", "wrong", users) is None
    assert auth.authenticate("nobody", "correct-horse-battery", users) is None
    assert auth.authenticate("", "", users) is None
    assert auth.authenticate("testuser", "correct-horse-battery", {}) is None
    assert auth.authenticate(None, None, users) is None


@check
def test_users_from_env():
    stored = auth.hash_password("correct-horse-battery")
    os.environ[auth.USERS_ENV] = json.dumps({"Testuser": stored})
    try:
        users = auth.resolve_users()
        assert users == {"testuser": stored}, users
        assert auth.authenticate("testuser", "correct-horse-battery", users) == "testuser"
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


@check
def test_session_token_roundtrip():
    users = {"testuser": auth.hash_password("x")}
    token = auth.make_session_token("TestUser", secret="s3cret")
    assert token is not None
    assert auth.verify_session_token(token, users, secret="s3cret") == "testuser"


@check
def test_session_token_without_secret_is_none():
    assert auth.make_session_token("testuser", secret=None) is None
    assert auth.verify_session_token("anything.123.abc", {"testuser": "h"}, secret=None) is None


@check
def test_session_token_wrong_secret_rejected():
    token = auth.make_session_token("testuser", secret="s3cret")
    users = {"testuser": auth.hash_password("x")}
    assert auth.verify_session_token(token, users, secret="wrong") is None


@check
def test_session_token_tampering_rejected():
    token = auth.make_session_token("testuser", secret="s3cret")
    users = {"testuser": auth.hash_password("x")}
    name, expiry, sig = token.split(".")
    tampered = f"someoneelse.{expiry}.{sig}"
    assert auth.verify_session_token(tampered, users, secret="s3cret") is None


@check
def test_session_token_expired_rejected():
    import time
    users = {"testuser": auth.hash_password("x")}
    payload = f"testuser.{int(time.time()) - 10}"
    sig = auth.hmac.new(b"s3cret", payload.encode("utf-8"), auth.hashlib.sha256).hexdigest()
    expired_token = f"{payload}.{sig}"
    assert auth.verify_session_token(expired_token, users, secret="s3cret") is None


@check
def test_session_token_deleted_user_rejected():
    token = auth.make_session_token("testuser", secret="s3cret")
    assert auth.verify_session_token(token, {}, secret="s3cret") is None


@check
def test_session_token_malformed_rejected():
    users = {"testuser": auth.hash_password("x")}
    for bad in ("", "a.b", "a.b.c.d", None, 123):
        assert auth.verify_session_token(bad, users, secret="s3cret") is None, bad


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
