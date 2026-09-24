"""الصفحة الرئيسية (H1) — قاعدة بيانات مؤقتة، عمرها ما بتلمس الإنتاج.

    venv/bin/python tests/test_home.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_TMP = tempfile.mkdtemp(prefix="cimafast-home-")
os.environ["STUDIO_DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ.pop("DATABASE_URL", None)

import accounts  # noqa: E402
import auth  # noqa: E402
import database  # noqa: E402
import home  # noqa: E402
import repo  # noqa: E402
from permissions import acting_as  # noqa: E402

database.init_db()
accounts.migrate_accounts({"melzayat": auth.hash_password("owner-pass-123", iterations=1000)})
A, _ = accounts.create_company("melzayat", "شركة أ", "boss_a")
B, _ = accounts.create_company("melzayat", "شركة ب", "boss_b")
accounts.add_member("boss_a", A, "costume", role="department", job_title="مصممة أزياء")
accounts.add_member("boss_a", A, "ad", role="department", job_title="مساعد مخرج أول")
accounts.add_member("boss_a", A, "watcher", role="viewer")
EMPTY = accounts.create_project("boss_a", A, "مشروع فاضي", "فيلم", "1080p", "أفقي", "16:9", add_all_members=True)  # (أ): السيناريو هنا = كل الفريق في المشروع
FULL = accounts.create_project("boss_a", A, "عروسة البحر", "مسلسل", "1080p", "أفقي", "16:9",
                              episode_count=10, add_all_members=True)  # (أ): السيناريو هنا = كل الفريق في المشروع
OTHER = accounts.create_project("boss_b", B, "سر الشركة ب", "فيلم", "1080p", "أفقي", "16:9", add_all_members=True)  # (أ): السيناريو هنا = كل الفريق في المشروع

loc = repo.add_location(FULL, "شقة حسام", "", None, None)
database.run_query("INSERT INTO characters (project_id, name) VALUES (?, ?)", (FULL, "إسراء"))
for n in (1, 2, 3):
    database.run_query("INSERT INTO scenes (project_id, scene_number, look_change_notes) VALUES (?, ?, ?)",
                       (FULL, n, "تغيير الفستان" if n == 2 else None))
repo.add_day(FULL)
database.run_query("INSERT INTO props (project_id, name) VALUES (?, ?)", (OTHER, "حسام السري"))

_results = []


def test(fn):
    _results.append(fn)
    return fn


def _cards(user):
    return {c["id"]: c for c in home.cards(user, "/v1/", "/v1/board/")}


@test
def test_an_empty_project_points_at_the_script():
    c = _cards("boss_a")[EMPTY]
    assert c["progress"]["step"] == 2 and not c["progress"]["complete"]
    assert "السيناريو" in c["next_text"] and c["next_href"] == "/v1/?project=%d&tab=import" % EMPTY
    assert c["open_href"].endswith("tab=import")


@test
def test_a_project_with_scenes_points_at_shots_and_opens_on_scenes():
    c = _cards("boss_a")[FULL]
    assert c["overview"]["scenes"] == 3 and c["progress"]["label"] == "تفريغ اللقطات"
    assert c["next_text"] == "3 مشهد لسه من غير لقطات" and c["next_href"].endswith("tab=shots")
    assert c["open_href"].endswith("tab=scenes")
    assert c["board_href"] == f"/v1/board/?project={FULL}"


@test
def test_home_never_shows_another_companys_project():
    assert OTHER not in _cards("boss_a") and set(_cards("boss_b")) == {OTHER}
    assert all(h["project"] != "سر الشركة ب" for h in home.search("boss_a", "حسام", "/v1/"))


@test
def test_needs_you_follows_the_job():
    cards = list(_cards("costume").values())
    costume = {n["id"] for n in home.needs_you("department", "مصممة أزياء", cards)}
    assert {"no_look", "look_changes"} <= costume and "undated_days" not in costume
    ad = {n["id"]: n for n in home.needs_you("department", "مساعد مخرج أول", cards)}
    assert "undated_days" in ad and "unscheduled" in ad and "no_look" not in ad
    assert ad["unscheduled"]["count"] == 3 and ad["unscheduled"]["href"] == f"/v1/board/?project={FULL}"
    assert home.needs_you("viewer", "مصممة أزياء", cards) == []


@test
def test_needs_you_is_sorted_and_links_to_the_exact_screen():
    items = home.needs_you("admin", None, list(_cards("boss_a").values()))
    assert [i["count"] for i in items] == sorted((i["count"] for i in items), reverse=True)
    script = next(i for i in items if i["id"] == "no_script")
    assert script["project_id"] == EMPTY and script["href"].endswith(f"project={EMPTY}&tab=import")


@test
def test_search_is_arabic_aware_and_lists_where_it_found_things():
    hits = home.search("boss_a", "اسراء", "/v1/")                # إسراء without the hamza
    assert hits and hits[0]["kind"] == "شخصية" and hits[0]["href"].endswith("tab=characters")
    assert home.search("boss_a", "الفستان", "/v1/")[0]["kind"] == "مشهد"
    assert home.search("boss_a", "ح", "/v1/") == []                  # one letter is not a search


@test
def test_continue_where_you_left_off_even_for_a_viewer():
    with acting_as("viewer"):
        repo.remember_screen("watcher", FULL, "scenes", "2026-09-21T19:00:00+00:00")
    c = home.continue_link("watcher", "/v1/")
    assert c["project"] == "عروسة البحر" and c["href"] == f"/v1/?project={FULL}&tab=scenes"


@test
def test_continue_is_dropped_when_access_is_lost():
    repo.remember_screen("boss_a", OTHER, "scenes", "2026-09-21T19:00:00+00:00")
    assert home.continue_link("boss_a", "/v1/") is None


def _call(handler, user, method, path, body=None):
    import board.app as board_app
    from starlette.requests import Request
    raw = json.dumps(body or {}).encode()
    scope = {"type": "http", "method": method, "path": path, "query_string": b"",
             "headers": [(b"content-type", b"application/json")]}

    async def receive():
        return {"type": "http.request", "body": raw, "more_body": False}

    real = board_app.current_user
    board_app.current_user = lambda request: user
    try:
        async def run():
            return await handler(Request(scope, receive))
        return asyncio.run(run())
    finally:
        board_app.current_user = real


@test
def test_only_roles_that_may_create_projects_can_from_home():
    import board.app as board_app
    r = _call(board_app.api_create_project, "costume", "POST", "/api/projects",
              {"company_id": A, "name": "من الأزياء"})
    assert r.status_code == 403
    r = _call(board_app.api_create_project, "boss_a", "POST", "/api/projects",
              {"company_id": B, "name": "في شركة غيري"})
    assert r.status_code == 403
    r = _call(board_app.api_create_project, "boss_a", "POST", "/api/projects",
              {"company_id": A, "name": "جديد", "project_type": "إعلان"})
    body = json.loads(r.body)
    assert r.status_code == 200 and body["href"] == f"../?project={body['project_id']}&tab=import"


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
