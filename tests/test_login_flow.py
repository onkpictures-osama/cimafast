"""اختبار شاشة الدخول جوه البرنامج نفسه عن طريق Streamlit AppTest.

بيشتغل على قاعدة بيانات مؤقتة (STUDIO_DB_PATH) — عمره ما بيلمس قاعدة الإنتاج:

    venv/bin/python tests/test_login_flow.py
"""

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_TMPDIR = tempfile.mkdtemp(prefix="cimafast-test-")
os.environ["STUDIO_DB_PATH"] = os.path.join(_TMPDIR, "test.db")
os.environ.pop("DATABASE_URL", None)
os.environ.pop("CIMAFAST_ALLOW_NO_PASSWORD", None)

import auth  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = os.path.join(ROOT, "app.py")
PASSWORD = "selim2015"
CHECKS = []


def check(fn):
    CHECKS.append(fn)
    return fn


def _with_users():
    os.environ[auth.USERS_ENV] = json.dumps(
        {"osama": auth.hash_password(PASSWORD, iterations=1000)}
    )


def _fresh_app():
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    return at


def _login(at, username, password):
    _widget(at, "text_input", "_login_username").set_value(username)
    _widget(at, "text_input", "_login_password").set_value(password)
    at.button[0].click().run()
    return at


def _widget(at, kind, key, in_sidebar=False):
    """بيرجّع الودجت لو موجود وإلا None — AppTest بيرمي KeyError لما ميلاقيش."""
    target = at.sidebar if in_sidebar else at
    try:
        return getattr(target, kind)(key=key)
    except KeyError:
        return None


def _body_text(at):
    return " ".join(m.value for m in at.markdown) + " ".join(
        getattr(e, "value", "") for e in at.error
    )


@check
def test_login_screen_blocks_the_app():
    _with_users()
    at = _fresh_app()
    assert _widget(at, "text_input", "_login_username") is not None
    assert _widget(at, "text_input", "_login_password") is not None
    # مفيش أي حاجة من البرنامج نفسه ظاهرة قبل الدخول
    assert not at.sidebar.selectbox, "app content leaked before login"
    assert "CimaFast Studio" in _body_text(at)


@check
def test_wrong_password_is_rejected():
    _with_users()
    at = _login(_fresh_app(), "osama", "wrong")
    assert at.error, "no error shown for a wrong password"
    assert _widget(at, "text_input", "_login_username") is not None, "still on login screen"


@check
def test_wrong_username_is_rejected():
    _with_users()
    at = _login(_fresh_app(), "ahmed", PASSWORD)
    assert at.error
    assert _widget(at, "text_input", "_login_username") is not None


@check
def test_correct_credentials_open_the_app():
    _with_users()
    at = _login(_fresh_app(), "osama", PASSWORD)
    assert not at.exception, at.exception
    assert at.session_state["_authenticated"] is True
    assert at.session_state["_auth_user"] == "osama"
    # شاشة الدخول اختفت والشريط الجانبي بتاع البرنامج ظهر
    assert _widget(at, "text_input", "_login_username") is None
    assert _widget(at, "button", "logout_btn", in_sidebar=True) is not None


@check
def test_username_is_case_insensitive():
    _with_users()
    at = _login(_fresh_app(), " Osama ", PASSWORD)
    assert at.session_state.get("_auth_user") == "osama"


@check
def test_logout_returns_to_login():
    _with_users()
    at = _login(_fresh_app(), "osama", PASSWORD)
    _widget(at, "button", "logout_btn", in_sidebar=True).click().run()
    assert not at.exception, at.exception
    assert not at.session_state.get("_authenticated")
    assert _widget(at, "text_input", "_login_username") is not None, "logout did not re-lock"


@check
def test_no_accounts_locks_the_app():
    os.environ.pop(auth.USERS_ENV, None)
    at = _fresh_app()
    assert not at.text_input, "login form shown although no accounts exist"
    assert "الدخول مقفول" in _body_text(at)


def main():
    failures = 0
    for fn in CHECKS:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except (AssertionError, KeyError, AttributeError) as exc:
            failures += 1
            print(f"  FAIL {fn.__name__}: {exc}")
        finally:
            os.environ.pop(auth.USERS_ENV, None)
    print(f"\n{len(CHECKS) - failures}/{len(CHECKS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
