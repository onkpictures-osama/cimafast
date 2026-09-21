"""F2 — الأدوار والصلاحيات. قاعدة بيانات مؤقتة، عمرها ما بتلمس الإنتاج.

    venv/bin/python tests/test_permissions.py

The plan's definition of done for F2: a viewer cannot change data and only an
admin can delete a project. The checks live in the data layer, so these tests go
through repo / database directly — the same path every screen uses.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_TMP = tempfile.mkdtemp(prefix="cimafast-perms-")
os.environ["STUDIO_DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ.pop("DATABASE_URL", None)

import accounts  # noqa: E402
import ai_jobs  # noqa: E402
import auth  # noqa: E402
import database  # noqa: E402
import image_gen  # noqa: E402
import permissions  # noqa: E402
import repo  # noqa: E402
from permissions import Denied, acting_as  # noqa: E402

database.init_db()
_results = []

LEGACY = {"melzayat": auth.hash_password("owner-pass-123", iterations=1000)}
accounts.migrate_accounts(LEGACY)
CO, _ = accounts.create_company("melzayat", "شركة الاختبار", "boss")
_PASSWORDS = {r: accounts.add_member("boss", CO, f"{r}_user", role=r)
              for r in ("producer", "manager", "department", "viewer")}


def test(fn):
    _results.append(fn)
    return fn


def _project(name="P"):
    return accounts.create_project("boss", CO, name, "فيلم", "1080p", "أفقي", "16:9")


def _raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    raise AssertionError(f"{getattr(fn, '__name__', fn)} did not raise {exc.__name__}")


# --- the rule table ------------------------------------------------------------------

@test
def test_the_rule_table():
    for role in ("operator", "admin", "producer", "manager", "department"):
        assert permissions.can(role, "edit"), role
    assert not permissions.can("viewer", "edit") and not permissions.can("viewer", "run_ai")
    assert {r for r in permissions.CAPABILITIES["delete_project"]} == {"operator", "admin"}
    assert not permissions.can(None, "edit") and not permissions.can("king", "edit")


# --- F2's definition of done ------------------------------------------------------------

@test
def test_a_viewer_cannot_change_any_data():
    pid = _project("مشروع للمشاهدة")
    with acting_as("viewer"):
        assert repo.project(pid)                                       # reading is fine
        _raises(Denied, repo.add_location, pid, "شقة", "", None)       # single write
        _raises(Denied, repo.add_day, pid)                             # board write
        _raises(Denied, repo.save_layout, pid, [])                     # transaction write
        _raises(Denied, database.run_query, "UPDATE projects SET name='x' WHERE id=?", (pid,))
    assert repo.project(pid)["name"] == "مشروع للمشاهدة"


@test
def test_only_an_admin_deletes_a_project():
    pid = _project("مشروع للحذف")
    for role in ("producer", "manager", "department", "viewer"):
        with acting_as(role):
            _raises(Denied, repo.delete_project, pid)
    assert repo.project(pid)
    with acting_as("admin"):
        repo.delete_project(pid)
    assert not repo.project(pid)


@test
def test_department_heads_edit_project_data():
    pid = _project("مشروع للأقسام")
    with acting_as("department"):
        repo.add_location(pid, "شقة البطل", "", None)
        repo.add_day(pid)
    assert database.fetch_all("SELECT COUNT(*) AS n FROM locations WHERE project_id=?", (pid,))[0]["n"] == 1


@test
def test_who_creates_projects():
    for role in ("department", "viewer"):
        _raises(Denied, accounts.create_project, f"{role}_user", CO, "x", "فيلم", "1080p", "أفقي", "16:9")
    for role in ("producer", "manager"):
        assert accounts.create_project(f"{role}_user", CO, f"من {role}", "فيلم", "1080p", "أفقي", "16:9")


# --- things a viewer must still be able to do ----------------------------------------------

@test
def test_a_viewer_still_changes_their_own_password_and_logs_in():
    with acting_as("viewer"):
        accounts.touch_login("viewer_user")
        accounts.change_own_password("viewer_user", _PASSWORDS["viewer"], "viewer-new-pass-1")
    assert auth.authenticate("viewer_user", "viewer-new-pass-1", accounts.auth_users()) == "viewer_user"


@test
def test_no_role_means_the_server_itself_and_is_not_restricted():
    # workers, migrations and scripts run with no user attached
    assert permissions.current_role() is None
    database.run_query("UPDATE companies SET active=1 WHERE id=?", (CO,))


# --- things that cost money are refused before the money is spent ---------------------------

@test
def test_a_viewer_cannot_start_an_ai_analysis():
    submitted = []
    real = ai_jobs.spool.submit
    ai_jobs.spool.submit = lambda *a, **k: submitted.append(a) or "job"
    try:
        with acting_as("viewer"):
            _raises(Denied, ai_jobs.start, "مشهد ١", 1, "x.md")
    finally:
        ai_jobs.spool.submit = real
    assert not submitted, "the job reached the queue"


@test
def test_a_viewer_cannot_generate_images():
    with acting_as("viewer"):
        _raises(Denied, image_gen.generate_image, "a room", "fake-key")


# --- the schedule board API ---------------------------------------------------------------

def _call(handler, user, method, path, body=None, query=b""):
    import board.app as board_app
    from starlette.requests import Request
    raw = json.dumps(body or {}).encode()
    scope = {"type": "http", "method": method, "path": path, "query_string": query,
             "headers": [(b"content-type", b"application/json")]}

    async def receive():
        return {"type": "http.request", "body": raw, "more_body": False}

    real = board_app.current_user
    board_app.current_user = lambda request: user
    try:
        async def run():           # own task → own context, like a real request
            return await handler(Request(scope, receive))
        return asyncio.run(run())
    finally:
        board_app.current_user = real


@test
def test_the_board_is_read_only_for_viewers():
    import board.app as board_app
    pid = _project("مشروع الجدول")
    r = _call(board_app.api_board, "viewer_user", "GET", "/api/board", query=f"project_id={pid}".encode())
    assert r.status_code == 200 and json.loads(r.body)["can_edit"] is False
    r = _call(board_app.api_add_day, "viewer_user", "POST", "/api/days", {"project_id": pid})
    assert r.status_code == 403, r.status_code
    assert not repo.shooting_days(pid)
    r = _call(board_app.api_add_day, "department_user", "POST", "/api/days", {"project_id": pid})
    assert r.status_code == 200, r.body
    r = _call(board_app.api_board, "department_user", "GET", "/api/board", query=f"project_id={pid}".encode())
    assert json.loads(r.body)["can_edit"] is True


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
