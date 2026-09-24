"""ما بعد الإنتاج + شريط التقدّم في مرحلة الإنتاج (المالك 2026-09-24)."""
import datetime as dt
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["STUDIO_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

import database  # noqa: E402

database.init_db()

import permissions  # noqa: E402
import post_production as pp  # noqa: E402
import repo  # noqa: E402
from database import fetch_all, run_query  # noqa: E402

TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


def _project(name):
    with permissions.system():
        run_query("INSERT INTO companies (name) VALUES (?)", (name,))
        cid = fetch_all("SELECT id FROM companies WHERE name=?", (name,))[0]["id"]
        run_query("INSERT INTO projects (name, company_id) VALUES (?, ?)", (name, cid))
    return fetch_all("SELECT id FROM projects WHERE name=?", (name,))[0]["id"]


A, B = _project("post-a"), _project("post-b")


@test
def test_empty_project_has_all_departments_not_started():
    s = pp.summary(repo.post_departments(A))
    assert [i["key"] for i in s["items"]] == pp.DEPT_KEYS and len(pp.DEPT_KEYS) == 7
    assert s["overall"] == 0 and s["approved"] == 0


@test
def test_progress_is_averaged_and_status_overrides_it():
    with permissions.system():
        repo.save_post_department(A, "edit", updated_by="u", status="in_progress", progress=70)
        repo.save_post_department(A, "color", status="approved", progress=10)       # معتمد = 100
        repo.save_post_department(A, "music", status="not_started", progress=90)    # لم يبدأ = 0
    s = pp.summary(repo.post_departments(A))
    by = {i["key"]: i["progress"] for i in s["items"]}
    assert by["edit"] == 70 and by["color"] == 100 and by["music"] == 0
    assert s["overall"] == round(170 / 7) and s["approved"] == 1


@test
def test_saving_keeps_fields_not_passed():
    with permissions.system():
        repo.save_post_department(A, "vfx", status="in_progress", progress=20, vendor_name="Studio X",
                                  preview_url="https://vimeo.com/1")
        repo.save_post_department(A, "vfx", progress=40)
    row = next(r for r in repo.post_departments(A) if r["dept_key"] == "vfx")
    assert row["progress"] == 40 and row["vendor_name"] == "Studio X" and row["preview_url"] == "https://vimeo.com/1"


@test
def test_departments_are_per_project():
    assert repo.post_departments(B) == []
    assert all(r["dept_key"] != "edit" or r["progress"] == 70 for r in repo.post_departments(A))


@test
def test_unknown_department_or_status_is_refused():
    for kwargs in ({"dept_key": "catering"}, {"dept_key": "edit", "status": "done"}):
        try:
            with permissions.system():
                repo.save_post_department(A, **kwargs)
        except ValueError:
            continue
        raise AssertionError(f"accepted {kwargs}")


@test
def test_a_viewer_cannot_edit_post():
    try:
        with permissions.acting_as("viewer"):
            repo.save_post_department(A, "edit", progress=5)
    except permissions.Denied:
        return
    raise AssertionError("viewer saved a post department")


@test
def test_stale_flag_after_a_week_only_while_working():
    old = (dt.date.today() - dt.timedelta(days=9)).isoformat()
    assert pp.is_stale({"status": "in_progress", "updated_at": old})
    assert not pp.is_stale({"status": "approved", "updated_at": old})
    assert not pp.is_stale({"status": "in_review", "updated_at": dt.date.today().isoformat()})


@test
def test_comments_are_scoped_and_blank_ones_dropped():
    with permissions.system():
        repo.add_post_comment(A, "edit", "u", "  النسخة التانية جاهزة ")
        repo.add_post_comment(A, "edit", "u", "   ")
    assert [c["body"] for c in repo.post_comments(A, "edit")] == ["النسخة التانية جاهزة"]
    assert repo.post_comments(B, "edit") == []


@test
def test_production_progress_counts_days_shot_and_their_scenes():
    with permissions.system():
        for n in (1, 2, 3):
            run_query("INSERT INTO shooting_days (project_id, day_number) VALUES (?, ?)", (A, n))
        for n in (1, 2, 3):
            run_query("INSERT INTO scenes (project_id, scene_number) VALUES (?, ?)", (A, n))
        days = repo.shooting_days(A)
        scenes = fetch_all("SELECT id FROM scenes WHERE project_id=? ORDER BY id", (A,))
        run_query("INSERT INTO shooting_day_scenes (day_id, scene_id, position) VALUES (?, ?, 0)",
                  (days[0]["id"], scenes[0]["id"]))
        run_query("INSERT INTO shooting_day_scenes (day_id, scene_id, position) VALUES (?, ?, 1)",
                  (days[0]["id"], scenes[1]["id"]))
        repo.set_day_shot(A, days[0]["id"], True)
        repo.set_day_shot(B, days[1]["id"], True)          # مشروع تاني: مايأثرش
    p = repo.production_progress(A)
    assert (p["days"], p["days_shot"], p["scenes"], p["scenes_shot"]) == (3, 1, 3, 2), p
    with permissions.system():
        repo.set_day_shot(A, days[0]["id"], False)
    assert repo.production_progress(A)["days_shot"] == 0


@test
def test_post_report_builds():
    import export
    data = export.build_post_report_excel({"name": "post-a", "project_type": "film"}, A, fetch_all)
    assert data[:2] == b"PK"


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
