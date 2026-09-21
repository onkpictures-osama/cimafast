"""طبقة بيانات جدول التصوير — على قاعدة بيانات مؤقتة، عمرها ما بتلمس الإنتاج.

    venv/bin/python tests/test_repo_board.py
"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_TMP = tempfile.mkdtemp(prefix="cimafast-repo-")
os.environ["STUDIO_DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ.pop("DATABASE_URL", None)

import database  # noqa: E402
import repo  # noqa: E402

database.init_db()
_results = []


def test(fn):
    _results.append(fn)
    return fn


def _q(sql, params=()):
    return database.fetch_all(sql, params)


def _project(name="P"):
    database.run_query("INSERT INTO projects (name, project_type) VALUES (?, 'فيلم')", (name,))
    return _q("SELECT MAX(id) AS id FROM projects")[0]["id"]


def _location(pid, name, parent=None):
    database.run_query("INSERT INTO locations (project_id, name, parent_location_id) VALUES (?, ?, ?)",
                       (pid, name, parent))
    lid = _q("SELECT MAX(id) AS id FROM locations")[0]["id"]
    database.run_query("INSERT INTO location_variants (location_id, variant_name) VALUES (?, 'الشكل الأساسي')",
                       (lid,))
    return lid, _q("SELECT MAX(id) AS id FROM location_variants")[0]["id"]


def _scene(pid, number, variant, day_night="نهار", int_ext="INT", cast=()):
    database.run_query(
        "INSERT INTO scenes (project_id, scene_number, int_ext, day_night, location_variant_id) "
        "VALUES (?, ?, ?, ?, ?)", (pid, number, int_ext, day_night, variant))
    sid = _q("SELECT MAX(id) AS id FROM scenes")[0]["id"]
    for cid in cast:
        database.run_query("INSERT INTO scene_characters (scene_id, character_id) VALUES (?, ?)", (sid, cid))
    return sid


def _character(pid, name):
    database.run_query("INSERT INTO characters (project_id, name) VALUES (?, ?)", (pid, name))
    return _q("SELECT MAX(id) AS id FROM characters")[0]["id"]


def _fixture():
    """موقعين: شقة حسين (أوضتين) وكورنيش، نهار وليل، وممثلين."""
    pid = _project()
    _, bedroom = _location(pid, "شقة حسين - غرفة النوم")
    _, kitchen = _location(pid, "شقة حسين - المطبخ")
    _, corniche = _location(pid, "كورنيش الإسكندرية")
    hussein, nadine = _character(pid, "حسين"), _character(pid, "نادين")
    s = {
        1: _scene(pid, 1, bedroom, "نهار", cast=[hussein]),
        2: _scene(pid, 2, corniche, "نهار", "EXT", cast=[hussein, nadine]),
        3: _scene(pid, 3, kitchen, "ليل", cast=[nadine]),
        4: _scene(pid, 4, kitchen, "نهار", cast=[hussein]),
        5: _scene(pid, 5, corniche, "ليل", "EXT", cast=[nadine]),
    }
    return pid, s, hussein, nadine


@test
def test_rooms_of_one_flat_are_one_site():
    assert repo.site_of("شقة حسين - غرفة النوم") == "شقة حسين"
    assert repo.site_of("شقة حسين - المطبخ") == "شقة حسين"
    assert repo.site_of("كورنيش الإسكندرية") == "كورنيش الإسكندرية"
    assert repo.site_of("غرفة النوم", parent_name="شقة حسين") == "شقة حسين"


@test
def test_new_project_board_has_everything_unscheduled():
    pid, s, *_ = _fixture()
    b = repo.board(pid)
    assert b["days"] == []
    assert sorted(b["unscheduled"]) == sorted(s.values())
    strip = b["scenes"][s[2]]
    assert strip["site"] == "كورنيش الإسكندرية" and strip["int_ext"] == "EXT"
    assert {c["name"] for c in strip["cast"]} == {"حسين", "نادين"}


@test
def test_one_site_per_day_never_mixes_sites_or_day_and_night():
    pid, s, *_ = _fixture()
    n = repo.apply_suggestion(pid, per_day=8, sites_per_day=1)
    b = repo.board(pid)
    assert n == len(b["days"]) == 4, n          # شقة نهار، شقة ليل، كورنيش نهار، كورنيش ليل
    for d in b["days"]:
        strips = [b["scenes"][sid] for sid in d["scene_ids"]]
        assert len({x["site"] for x in strips}) == 1
        assert len({x["night"] for x in strips}) == 1
    assert b["unscheduled"] == []
    first = [b["scenes"][sid] for sid in b["days"][0]["scene_ids"]]
    assert not first[0]["night"], "day before night"


@test
def test_company_moves_combine_small_sites_but_never_day_with_night():
    pid, s, *_ = _fixture()
    n = repo.apply_suggestion(pid, per_day=8, sites_per_day=2)
    b = repo.board(pid)
    assert n == 2, n                            # يوم نهار (موقعين) ويوم ليل (موقعين)
    for d in b["days"]:
        strips = [b["scenes"][sid] for sid in d["scene_ids"]]
        assert len({x["night"] for x in strips}) == 1
        assert len({x["site"] for x in strips}) <= 2


@test
def test_company_moves_stay_inside_one_city():
    pid = _project()
    _, cairo = _location(pid, "شقة حسين - القاهرة - المدخل")
    _, alex = _location(pid, "شقة حسين - الإسكندرية")
    _, corniche = _location(pid, "كورنيش الإسكندرية")
    _scene(pid, 1, cairo)
    _scene(pid, 2, alex)
    _scene(pid, 3, corniche)
    days = repo.suggest_layout(pid, per_day=8, sites_per_day=3)
    assert len(days) == 2, days      # القاهرة لوحدها، وإسكندرية (موقعين) مع بعض
    cities = [{repo.city_of(n) for n in names} for names in (
        [r["location"] for r in repo.board_scenes(pid) if r["id"] in d] for d in days)]
    assert all(len(c) == 1 for c in cities), cities


@test
def test_city_is_part_of_the_site():
    assert repo.site_of("شقة حسين - القاهرة - المدخل") == "شقة حسين - القاهرة"
    assert repo.site_of("شقة حسين - الإسكندرية") == "شقة حسين - الإسكندرية"
    assert repo.site_of("المستشفى - غرفة الولادة - الإسكندرية") == "المستشفى - الإسكندرية"
    assert repo.city_of("سيارة - طريق اسكندرية") is None     # «طريق اسكندرية» مش مدينة
    assert repo.city_of("شقة - اسكندرية") == "الإسكندرية"
    # المدينة جوه الاسم نفسه، مش بعد « - » — ده اللي كان فايت
    assert repo.city_of("كورنيش الإسكندرية") == "الإسكندرية"
    assert repo.site_of("كورنيش الإسكندرية") == "كورنيش الإسكندرية"
    assert repo.city_of("محطة مصر - القاهرة") == "القاهرة"
    assert repo.city_of("سيارة حسين - بوابات اسكندرية") == "الإسكندرية"
    assert repo.city_of("شقة حسين") is None


@test
def test_suggestion_respects_the_per_day_cap():
    pid, s, *_ = _fixture()
    repo.apply_suggestion(pid, per_day=1, sites_per_day=1)
    b = repo.board(pid)
    assert len(b["days"]) == 5 and all(len(d["scene_ids"]) == 1 for d in b["days"])


@test
def test_save_layout_round_trips_order_and_renumbers_days():
    pid, s, *_ = _fixture()
    repo.add_day(pid)
    repo.add_day(pid)
    d1, d2 = [d["id"] for d in repo.shooting_days(pid)]
    repo.save_layout(pid, [{"day_id": d2, "scene_ids": [s[3], s[1]]}, {"day_id": d1, "scene_ids": [s[5]]}])
    b = repo.board(pid)
    assert [d["id"] for d in b["days"]] == [d2, d1], "days take the order they were saved in"
    assert [d["day_number"] for d in b["days"]] == [1, 2]
    assert b["days"][0]["scene_ids"] == [s[3], s[1]]
    assert sorted(b["unscheduled"]) == sorted([s[2], s[4]])


@test
def test_save_layout_rejects_foreign_or_duplicate_scenes_and_changes_nothing():
    pid, s, *_ = _fixture()
    other, s_other, *_ = _fixture()
    repo.add_day(pid)
    day = repo.shooting_days(pid)[0]["id"]
    repo.save_layout(pid, [{"day_id": day, "scene_ids": [s[1]]}])
    for bad in ([{"day_id": day, "scene_ids": [s_other[1]]}],
                [{"day_id": day, "scene_ids": [s[1], s[1]]}],
                [{"day_id": repo.add_day(other) and repo.shooting_days(other)[0]["id"], "scene_ids": []}]):
        try:
            repo.save_layout(pid, bad)
        except repo.LayoutError:
            pass
        else:
            raise AssertionError(f"accepted {bad}")
    assert repo.board(pid)["days"][0]["scene_ids"] == [s[1]], "a rejected save must not change anything"


@test
def test_deleting_a_day_returns_its_scenes_to_the_pool():
    pid, s, *_ = _fixture()
    repo.apply_suggestion(pid)
    b = repo.board(pid)
    victim = b["days"][0]
    repo.delete_day(pid, victim["id"])
    after = repo.board(pid)
    assert len(after["days"]) == len(b["days"]) - 1
    assert set(victim["scene_ids"]) <= set(after["unscheduled"])
    assert [d["day_number"] for d in after["days"]] == list(range(1, len(after["days"]) + 1))


@test
def test_day_out_of_days_codes():
    pid, s, hussein, nadine = _fixture()
    for _ in range(3):
        repo.add_day(pid)
    d = [x["id"] for x in repo.shooting_days(pid)]
    # حسين: يوم 1 و3 (يوم 2 انتظار). نادين: يوم 2 بس.
    repo.save_layout(pid, [{"day_id": d[0], "scene_ids": [s[1]]},
                           {"day_id": d[1], "scene_ids": [s[3]]},
                           {"day_id": d[2], "scene_ids": [s[4]]}])
    rows = {r["name"]: r for r in repo.day_out_of_days(pid)["rows"]}
    assert rows["حسين"]["codes"] == ["SW", "H", "WF"], rows["حسين"]["codes"]
    assert rows["حسين"]["work_days"] == 2 and rows["حسين"]["hold_days"] == 1
    assert rows["نادين"]["codes"] == ["", "SWF", ""]


@test
def test_deleting_a_scene_removes_it_from_the_board():
    pid, s, *_ = _fixture()
    repo.apply_suggestion(pid)
    database.run_query("DELETE FROM scenes WHERE id=?", (s[1],))
    b = repo.board(pid)
    assert all(s[1] not in d["scene_ids"] for d in b["days"])


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
