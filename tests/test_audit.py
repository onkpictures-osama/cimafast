"""F3 — سجل التدقيق وأحداث الاستخدام. قاعدة بيانات مؤقتة، عمرها ما بتلمس الإنتاج.

    venv/bin/python tests/test_audit.py

The plan's definition of done for F3: any change can be traced, and adoption is
reported from events rather than guessed. The tests below pin that, plus the two
things that would make the log itself a liability — leaking a password hash, and
leaking one company's activity to another.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_TMP = tempfile.mkdtemp(prefix="cimafast-audit-")
os.environ["STUDIO_DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ.pop("DATABASE_URL", None)

import accounts  # noqa: E402
import audit  # noqa: E402
import auth  # noqa: E402
import database  # noqa: E402
import permissions  # noqa: E402
import repo  # noqa: E402
from database import fetch_all, run_query  # noqa: E402

database.init_db()
_results = []

LEGACY = {"melzayat": auth.hash_password("owner-pass-123", iterations=1000)}
accounts.migrate_accounts(LEGACY)
CO_A, _ = accounts.create_company("melzayat", "شركة أ", "boss_a")
CO_B, _ = accounts.create_company("melzayat", "شركة ب", "boss_b")
accounts.add_member("boss_a", CO_A, "dept_a", role="department")
accounts.add_member("boss_a", CO_A, "viewer_a", role="viewer")


def test(fn):
    _results.append(fn)
    return fn


def _raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    raise AssertionError(f"{getattr(fn, '__name__', fn)} did not raise {exc.__name__}")


def _rows(**kw):
    return audit.entries("melzayat", limit=1000, **kw)


def _last(entity=None, action=None):
    rows = audit.entries("melzayat", entity=entity, action_name=action, limit=1)
    return rows[0] if rows else None


def _as(username, company_id, project_id=None, role=None):
    """سياق مستخدم واحد: الدور للصلاحيات (F2) والسياق للسجل (F3)."""
    audit.set_context(username=username, company_id=company_id, project_id=project_id,
                      source="app")
    permissions.act_as(role or accounts.role_in(username, company_id))


def _project(owner, company_id, name):
    _as(owner, company_id)
    return accounts.create_project(owner, company_id, name, "فيلم", "1080p", "أفقي", "16:9")


P_A = _project("boss_a", CO_A, "مشروع شركة أ")
P_B = _project("boss_b", CO_B, "مشروع شركة ب")


# --- التسجيل التلقائي من طبقة البيانات ------------------------------------------------

@test
def test_every_write_is_logged_with_who_what_when():
    """أي INSERT/UPDATE/DELETE بيتسجّل من غير ما الشاشة تعمل أي حاجة."""
    _as("dept_a", CO_A, P_A)
    run_query("INSERT INTO characters (project_id, name) VALUES (?, ?)", (P_A, "حسين"))
    cid = fetch_all("SELECT MAX(id) AS id FROM characters")[0]["id"]
    row = _last(entity="characters")
    assert row["action"] == "create", row
    assert row["username"] == "dept_a", row
    assert row["entity_id"] == cid, row
    assert row["company_id"] == CO_A and row["project_id"] == P_A, row
    assert row["at"], "every row is timestamped"
    assert json.loads(row["changes"])["new"]["name"] == "حسين", row


@test
def test_update_keeps_the_old_value_and_the_new_one():
    _as("dept_a", CO_A, P_A)
    run_query("INSERT INTO locations (project_id, name, base_description) VALUES (?, ?, ?)",
              (P_A, "شقة حسين", "وصف"))
    lid = fetch_all("SELECT MAX(id) AS id FROM locations")[0]["id"]
    run_query("UPDATE locations SET name=? WHERE id=?", ("شقة حسين - الصالة", lid))
    row = _last(entity="locations", action="update")
    changed = json.loads(row["changes"])["changed"]
    assert changed["name"] == {"from": "شقة حسين", "to": "شقة حسين - الصالة"}, changed


@test
def test_delete_keeps_the_row_that_is_gone():
    """أهم صف في السجل: اللي بيقول إيه اللي اتمسح، لأن البيانات نفسها مبقتش موجودة."""
    _as("boss_a", CO_A, P_A)
    run_query("INSERT INTO props (project_id, name) VALUES (?, ?)", (P_A, "مفتاح"))
    pid = fetch_all("SELECT MAX(id) AS id FROM props")[0]["id"]
    run_query("DELETE FROM props WHERE id=?", (pid,))
    row = _last(entity="props", action="delete")
    assert json.loads(row["changes"])["old"]["name"] == "مفتاح", row
    assert row["entity_id"] == pid, row


@test
def test_a_save_that_changes_nothing_is_not_an_event():
    _as("dept_a", CO_A, P_A)
    run_query("INSERT INTO characters (project_id, name) VALUES (?, ?)", (P_A, "سميحة"))
    cid = fetch_all("SELECT MAX(id) AS id FROM characters")[0]["id"]
    before = len(_rows(entity="characters", action_name="update"))
    run_query("UPDATE characters SET name=? WHERE id=?", ("سميحة", cid))
    assert len(_rows(entity="characters", action_name="update")) == before


@test
def test_the_data_layer_transaction_is_logged_too():
    """repo._tx هو الطريق التاني للكتابة — لازم يتسجّل زي run_query بالظبط."""
    _as("boss_a", CO_A, P_A)
    repo.add_day(P_A)
    row = _last(entity="shooting_days")
    assert row["action"] == "create" and row["username"] == "boss_a", row


@test
def test_the_log_never_logs_itself():
    _as("boss_a", CO_A, P_A)
    audit.log("test_marker", "projects", entity_id=P_A, summary="علامة")
    assert not _rows(entity="audit_log"), "audit rows must not audit themselves"
    assert not _rows(entity="usage_events")


# --- اللي مايتسجلش أبدًا -----------------------------------------------------------

@test
def test_a_password_hash_never_reaches_the_log():
    """لو الـ hash اتخزن في السجل يبقى السجل بقى نسخة تانية من ملف كلمات السر."""
    accounts.reset_password("boss_a", CO_A, "dept_a")
    new_hash = fetch_all("SELECT password_hash FROM users WHERE username='dept_a'")[0]["password_hash"]
    for row in _rows():
        blob = f"{row['summary']} {row['changes']}"
        assert new_hash not in blob, row
        assert "pbkdf2" not in blob.lower(), row
    # والكتابة المباشرة (من غير الغلاف بتاع accounts) برضه بتتعتّم
    _as("boss_a", CO_A)
    with permissions.system():
        run_query("UPDATE users SET password_hash=? WHERE username=?", ("SECRET-HASH", "viewer_a"))
    row = _last(entity="users", action="update")
    assert "SECRET-HASH" not in (row["changes"] or ""), row
    # الصف بيقول إن كلمة السر اتغيّرت — من غير القيمة القديمة ولا الجديدة
    assert json.loads(row["changes"])["changed"]["password_hash"] == audit.SECRET_CHANGED, row


@test
def test_a_failed_login_is_logged_without_the_password():
    accounts.log_failed_login("boss_a")
    row = _last(entity="auth", action="login_failed")
    assert row["username"] == "boss_a", row
    assert "boss_a" in row["summary"], row


@test
def test_login_and_logout_are_logged_and_counted():
    accounts.touch_login("boss_a")
    accounts.log_logout("boss_a")
    assert _last(entity="auth", action="login"), "login is an audit event"
    assert _last(entity="auth", action="logout"), "logout is an audit event"
    # والدخول كمان حدث استخدام — سؤال التبنّي بيتقري من الجدول التاني
    events = audit.usage_events("boss_a", CO_A, event_name="login")
    assert any(e["username"] == "boss_a" for e in events), events


# --- العزل بين الشركات (F1) ----------------------------------------------------------

@test
def test_a_company_admin_sees_only_their_own_company():
    rows = audit.entries("boss_a", limit=1000)
    assert rows, "the admin of company A sees company A's activity"
    assert {r["company_id"] for r in rows} == {CO_A}, "no row from another company"
    assert not any(r["project_id"] == P_B for r in rows)


@test
def test_asking_for_another_companys_log_is_refused():
    _raises(accounts.AccessDenied, audit.entries, "boss_a", company_id=CO_B)
    _raises(accounts.AccessDenied, audit.usage_summary, "boss_a", CO_B)


@test
def test_a_viewer_and_a_department_head_cannot_read_the_log_at_all():
    for who in ("viewer_a", "dept_a"):
        _raises(accounts.AccessDenied, audit.entries, who)
    assert not permissions.can("viewer", "view_audit")
    assert not permissions.can("department", "view_audit")
    assert permissions.can("admin", "view_audit")


@test
def test_the_operator_sees_every_company():
    companies = {r["company_id"] for r in audit.entries("melzayat", limit=1000)}
    assert {CO_A, CO_B} <= companies, companies


@test
def test_filtering_by_user_and_entity_and_text():
    assert all(r["username"] == "dept_a" for r in audit.entries("boss_a", username="dept_a"))
    assert all(r["entity"] == "locations" for r in audit.entries("boss_a", entity="locations"))
    hits = audit.entries("boss_a", text="شقة حسين")
    assert hits and all("شقة" in (h["summary"] or "") + (h["changes"] or "") for h in hits)


# --- الضجيج: عملية واحدة = صف واحد -------------------------------------------------

@test
def test_a_bulk_import_is_one_row_not_thousands():
    """استيراد ١٤٣ مشهد لازم يبقى سطر واحد، وإلا السجل بيبقى مالوش لازمة."""
    _as("boss_a", CO_A, P_A)
    before = len(_rows())
    with audit.action("import_script", "scenes", project_id=P_A) as act:
        for n in range(1, 21):
            run_query("INSERT INTO scenes (project_id, scene_number) VALUES (?, ?)", (P_A, n))
        act.summary = "استيراد سيناريو: 20 مشهد جديد"
        act.extra = {"مشاهد": 20}
    after = _rows()
    assert len(after) == before + 1, f"{len(after) - before} rows for one import"
    row = after[0]
    assert row["action"] == "import_script" and row["project_id"] == P_A, row
    assert json.loads(row["changes"])["مشاهد"] == 20, row
    assert fetch_all("SELECT COUNT(*) AS n FROM scenes WHERE project_id=?", (P_A,))[0]["n"] == 20


@test
def test_an_action_that_failed_is_not_logged_as_done():
    _as("boss_a", CO_A, P_A)
    before = len(_rows())
    try:
        with audit.action("import_script", "scenes", project_id=P_A):
            run_query("INSERT INTO scenes (project_id, scene_number) VALUES (?, ?)", (P_A, 99))
            raise RuntimeError("الاستيراد وقع في نصه")
    except RuntimeError:
        pass
    assert len(_rows()) == before, "a failed operation must not claim it happened"


@test
def test_team_changes_read_like_sentences_not_tables():
    accounts.set_role("boss_a", CO_A, "dept_a", "manager")
    row = _last(action="role_change")
    assert "dept_a" in row["summary"], row
    changes = json.loads(row["changes"])
    assert changes["من"] == "department" and changes["لـ"] == "manager", changes
    assert row["company_id"] == CO_A


@test
def test_changing_the_screen_memory_is_not_a_data_change():
    """user_profile بتتكتب مع كل ضغطة تبويب — دي استخدام مش تعديل بيانات."""
    _as("boss_a", CO_A, P_A)
    before = len(_rows())
    repo.remember_screen("boss_a", P_A, "scenes", "2026-09-21T00:00:00+00:00")
    assert len(_rows()) == before


# --- أحداث الاستخدام ---------------------------------------------------------------

@test
def test_usage_summary_counts_features_and_people():
    audit.event("export", target="shot_list_excel", username="boss_a",
                company_id=CO_A, project_id=P_A)
    audit.event("export", target="shot_list_excel", username="dept_a",
                company_id=CO_A, project_id=P_A)
    audit.event("screen", target="scenes", username="dept_a", company_id=CO_A, project_id=P_A)
    summary = audit.usage_summary("boss_a", CO_A, days=30)
    exports = next(r for r in summary["rows"] if r["event"] == "export")
    assert exports["times"] == 2 and exports["people"] == 2, exports
    assert summary["active_users"] >= 2, summary


@test
def test_usage_events_are_scoped_per_company_too():
    audit.event("export", target="secret_report", username="boss_b",
                company_id=CO_B, project_id=P_B)
    rows = audit.usage_events("boss_a", CO_A, days=30, limit=1000)
    assert rows, "company A has usage of its own"
    assert all(r["company_id"] == CO_A for r in rows)
    assert not any(r["target"] == "secret_report" for r in rows)


@test
def test_a_broken_log_never_breaks_a_users_save():
    """السجل مش أهم من شغل المستخدم: لو التسجيل وقع، الحفظ بيكمّل عادي."""
    _as("boss_a", CO_A, P_A)
    original = audit._insert_audit
    audit._insert_audit = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("audit is down"))
    try:
        run_query("INSERT INTO props (project_id, name) VALUES (?, ?)", (P_A, "شنطة"))
    finally:
        audit._insert_audit = original
    assert fetch_all("SELECT name FROM props WHERE project_id=? AND name='شنطة'", (P_A,)), \
        "the prop must be saved even when the audit write fails"


# --- الشاشة (board) ------------------------------------------------------------------

@test
def test_the_activity_api_refuses_a_non_admin_and_serves_an_admin():
    sys.path.insert(0, os.path.join(ROOT, "board"))
    import board.app as board_app

    class _Req:
        def __init__(self, params):
            self.query_params = params
            self.method = "GET"

    async def _call(user, params):
        board_app.current_user = lambda request: user      # جلسة مزيّفة
        return await board_app.api_activity(_Req(params))

    ok = asyncio.run(_call("boss_a", {"company_id": str(CO_A)}))
    assert ok.status_code == 200
    payload = json.loads(ok.body)
    assert payload["rows"] and all(r["company_id"] == CO_A for r in payload["rows"])
    assert payload["filters"]["users"], "the filter lists come from the company's own rows"

    denied = asyncio.run(_call("boss_a", {"company_id": str(CO_B)}))
    assert denied.status_code == 403, denied.body

    nobody = asyncio.run(_call("viewer_a", {}))
    assert nobody.status_code == 403, nobody.body


if __name__ == "__main__":
    failures = 0
    for fn in _results:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(_results) - failures}/{len(_results)} passed")
    sys.exit(1 if failures else 0)
