"""H4 — تنبيهات التغيير للقسم اللي يهمّه. قاعدة بيانات مؤقتة، عمرها ما بتلمس الإنتاج.

    venv/bin/python tests/test_notify.py

The plan's definition of done for H4: a change to a scene's location or a shoot
day's schedule is visible, same session, to the department it concerns. The tests
pin that, plus what would make notifications a liability: one company seeing
another's changes, and noise (your own edits, departments it does not concern).
"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_TMP = tempfile.mkdtemp(prefix="cimafast-notify-")
os.environ["STUDIO_DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ.pop("DATABASE_URL", None)

import accounts  # noqa: E402
import audit  # noqa: E402
import auth  # noqa: E402
import database  # noqa: E402
import links  # noqa: E402
import notify  # noqa: E402
import permissions  # noqa: E402
import repo  # noqa: E402
from database import fetch_all, run_query  # noqa: E402

database.init_db()
_results = []

# كلمات سر مؤقتة للاختبار بس — مش حسابات حقيقية
accounts.migrate_accounts({"melzayat": auth.hash_password("owner-pass-123", iterations=1000)})
CO_A, _ = accounts.create_company("melzayat", "شركة أ", "boss_a")
CO_B, _ = accounts.create_company("melzayat", "شركة ب", "boss_b")
accounts.add_member("boss_a", CO_A, "dop_a", role="department", job_title="مدير تصوير")
accounts.add_member("boss_a", CO_A, "costume_a", role="department", job_title="مصممة أزياء")
accounts.add_member("boss_a", CO_A, "vague_a", role="department", job_title="مساعد")
accounts.add_member("boss_b", CO_B, "dop_b", role="department", job_title="مدير تصوير")


def test(fn):
    _results.append(fn)
    return fn


def _as(username, company_id, project_id=None):
    audit.set_context(username=username, company_id=company_id, project_id=project_id, source="app")
    permissions.act_as(accounts.role_in(username, company_id))


def _texts(username):
    return [i["text"] for i in notify.feed(username, "/v1/", "/v1/board/")["items"]]


_as("boss_a", CO_A)
P_A = accounts.create_project("boss_a", CO_A, "مشروع أ", "فيلم", "1080p", "أفقي", "16:9")
_as("boss_b", CO_B)
P_B = accounts.create_project("boss_b", CO_B, "مشروع ب", "فيلم", "1080p", "أفقي", "16:9")

_as("boss_a", CO_A, P_A)
run_query("INSERT INTO locations (project_id, name, base_description) VALUES (?, ?, ?)", (P_A, "شقة حسين", ""))
LOC = fetch_all("SELECT MAX(id) AS id FROM locations")[0]["id"]
run_query("INSERT INTO location_variants (location_id, variant_name, description) VALUES (?, ?, ?)",
          (LOC, "الصالة", ""))
V1 = fetch_all("SELECT MAX(id) AS id FROM location_variants")[0]["id"]
run_query("INSERT INTO location_variants (location_id, variant_name, description) VALUES (?, ?, ?)",
          (LOC, "المطبخ", ""))
V2 = fetch_all("SELECT MAX(id) AS id FROM location_variants")[0]["id"]
run_query("INSERT INTO scenes (project_id, scene_number, location_variant_id) VALUES (?, ?, ?)", (P_A, 12, V1))
SCENE = fetch_all("SELECT MAX(id) AS id FROM scenes")[0]["id"]
# كل اللي فات إعداد — "شافوه" الكل، عشان كل اختبار يبدأ من صفر
for _u in ("boss_a", "dop_a", "costume_a", "vague_a", "dop_b"):
    notify.mark_seen(_u, fetch_all("SELECT MAX(id) AS id FROM audit_log")[0]["id"])


# --- الوسم وقت الكتابة ---------------------------------------------------------------

@test
def test_scene_location_change_is_tagged_for_camera_and_art():
    tagged = notify.tag("scenes", "update", '{"changed": {"location_variant_id": {"from": 1, "to": 2}}}')
    for dept in ("camera", "art", "production", "directing"):
        assert f",{dept}," in tagged, tagged
    notes_only = notify.tag("scenes", "update", '{"changed": {"notes": {"from": "", "to": "x"}}}')
    assert ",camera," not in notes_only, "a note edit does not move the camera department"


@test
def test_schedule_concerns_everyone_and_accounts_concern_no_one():
    assert notify.tag("shooting_days", "schedule_save") == ",*,"
    assert notify.tag("shooting_days", "update") == ",*,"
    assert notify.tag("users", "update") is None
    assert notify.tag("auth", "login") is None


@test
def test_departments_come_from_the_job_title():
    assert notify.departments_of("department", "مدير تصوير") == {"camera"}
    assert notify.departments_of("department", "مساعد مخرج أول") >= {"directing", "production"}
    assert "production" in notify.departments_of("admin", None)
    assert notify.departments_of("department", "مساعد") is None, "unknown title sees everything"


# --- مين بيشوف إيه ---------------------------------------------------------------------

@test
def test_location_change_reaches_camera_not_costume_nor_the_editor_himself():
    """معيار الانتهاء: تغيير مكان مشهد بيوصل للقسم اللي يهمّه."""
    _as("boss_a", CO_A, P_A)
    run_query("UPDATE scenes SET location_variant_id=? WHERE id=?", (V2, SCENE))
    assert "مشهد 12: اتغيّر المكان" in _texts("dop_a"), _texts("dop_a")
    assert notify.unread_count("dop_a") == 1
    assert "مشهد 12: اتغيّر المكان" not in _texts("costume_a"), "costume is not concerned"
    assert "مشهد 12: اتغيّر المكان" in _texts("vague_a"), "an unclear title errs on seeing it"
    assert "مشهد 12: اتغيّر المكان" not in _texts("boss_a"), "your own change is not news to you"


@test
def test_a_scene_notification_opens_that_exact_scene():
    item = next(i for i in notify.feed("dop_a", "/v1/", "/v1/board/")["items"] if "مشهد 12" in i["text"])
    assert item["href"] == f"/v1/?project={P_A}&tab=scenes&item={SCENE}", item["href"]
    assert links.item({"item": str(SCENE)}) == SCENE
    assert links.item({"item": "abc"}) is None and links.item({"item": "-4"}) is None


@test
def test_schedule_save_reaches_every_department():
    _as("boss_a", CO_A, P_A)
    repo.add_day(P_A)                                  # بيرجّع رقم اليوم مش الـ id
    day_id = fetch_all("SELECT MAX(id) AS id FROM shooting_days")[0]["id"]
    with audit.action("schedule_save", "shooting_days", project_id=P_A, summary="حفظ جدول التصوير"):
        repo.save_layout(P_A, [{"day_id": day_id, "scene_ids": [SCENE]}])
    for user in ("dop_a", "costume_a", "vague_a"):
        assert "حفظ جدول التصوير" in _texts(user), (user, _texts(user))
    item = next(i for i in notify.feed("costume_a", "/v1/", "/v1/board/")["items"]
                if i["text"] == "حفظ جدول التصوير")
    assert item["href"] == f"/v1/board/?project={P_A}", item["href"]


@test
def test_other_companies_never_see_it():
    assert _texts("dop_b") == [], _texts("dop_b")
    assert notify.unread_count("dop_b") == 0


@test
def test_opening_the_bell_marks_seen_and_never_goes_backwards():
    feed = notify.feed("dop_a", "/v1/", "/v1/board/")
    assert feed["unread"] > 0
    notify.mark_seen("dop_a", feed["latest_id"])
    assert notify.unread_count("dop_a") == 0
    notify.mark_seen("dop_a", 1)                       # تاب قديم مفتوح
    assert notify.last_seen("dop_a") == feed["latest_id"]
    assert _texts("dop_a"), "seen items stay listed, just not counted"


@test
def test_old_untagged_rows_are_history_not_notifications():
    """صفوف السجل من قبل H4 (departments = NULL) مابتطلعش كتنبيهات مرة واحدة."""
    with audit.disabled():
        conn = database.get_connection()
        conn.execute("INSERT INTO audit_log (at, username, company_id, project_id, entity, entity_id, action, "
                     "summary) VALUES (?, 'boss_a', ?, ?, 'scenes', ?, 'update', 'قديم')",
                     (notify._since(), CO_A, P_A, SCENE))
        conn.commit()
        conn.close()
    assert "قديم" not in _texts("vague_a")


@test
def test_seen_marker_is_not_itself_a_notification():
    before = fetch_all("SELECT COUNT(*) AS n FROM audit_log")[0]["n"]
    notify.mark_seen("costume_a", 10 ** 6)
    assert fetch_all("SELECT COUNT(*) AS n FROM audit_log")[0]["n"] == before


@test
def test_feed_never_raises_for_unknown_users():
    assert notify.feed("nobody", "/v1/") == {"unread": 0, "items": [], "latest_id": 0}
    assert notify.unread_count(None) == 0


@test
def test_english_text():
    _as("boss_a", CO_A, P_A)
    run_query("UPDATE scenes SET day_night=? WHERE id=?", ("ليل", SCENE))
    texts = [i["text"] for i in notify.feed("dop_a", "/v1/", lang="en")["items"]]
    assert "Scene 12: time of day changed" in texts, texts
    assert notify.ago("2026-01-01T00:00:00+00:00", lang="en").endswith("ago")



@test
def test_home_bell_api():
    """الجرس في الرئيسية (Starlette): القايمة، والعلامة "شفتهم"، ومن غير دخول = 401."""
    import asyncio
    import json
    sys.path.insert(0, os.path.join(ROOT, "board"))
    import importlib
    board_app = importlib.import_module("app")

    class _Req:
        def __init__(self, body=None):
            self.query_params, self.method, self._body = {}, "POST" if body else "GET", body
            self.headers, self.cookies = {}, {}

        async def json(self):
            return self._body

    def _call(user, handler, body=None):
        board_app.current_user = lambda request: user            # جلسة مزيّفة
        return asyncio.run(handler(_Req(body)))

    _as("boss_a", CO_A, P_A)
    run_query("UPDATE scenes SET weather=? WHERE id=?", ("مطر", SCENE))
    got = _call("vague_a", board_app.api_notifications)
    payload = json.loads(got.body)
    assert got.status_code == 200 and payload["unread"] >= 1, payload
    first = payload["items"][0]
    assert first["href"].startswith(f"../?project={P_A}&tab=scenes"), first["href"]
    assert first["ago"], first
    seen = _call("vague_a", board_app.api_notifications_seen, {"up_to": payload["latest_id"]})
    assert json.loads(seen.body)["unread"] == 0, seen.body
    assert _call("vague_a", board_app.api_notifications_seen, {"up_to": "x"}).status_code == 400
    assert _call(None, board_app.api_notifications).status_code == 401

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
