"""طاولة التقطيع: نص المشهد، رسمة المكان (افتراضية/حالة)، أماكن الشخصيات والكاميرات،
وطابور «ارسمها لي» (المالك 2026-09-25)."""
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_TMP = tempfile.mkdtemp()
os.environ["STUDIO_DB_PATH"] = os.path.join(_TMP, "t.db")
os.environ["CIMAFAST_PLAN_SPOOL"] = os.path.join(_TMP, "plan-jobs")

import database  # noqa: E402

database.init_db()

import blocking  # noqa: E402
import permissions  # noqa: E402
import plan_ai  # noqa: E402
import plan_jobs  # noqa: E402
import repo  # noqa: E402
from database import fetch_all, run_query  # noqa: E402

TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


def _one(sql, params):
    return fetch_all(sql, params)[0]["id"]


def _project(name):
    with permissions.system():
        run_query("INSERT INTO companies (name) VALUES (?)", (name,))
        cid = _one("SELECT id FROM companies WHERE name=?", (name,))
        run_query("INSERT INTO projects (name, company_id) VALUES (?, ?)", (name, cid))
        pid = _one("SELECT id FROM projects WHERE name=?", (name,))
        run_query("INSERT INTO locations (project_id, name, base_description) VALUES (?, ?, ?)",
                  (pid, "شقة حسين", "صالة فيها كنبة وترابيزة"))
        lid = _one("SELECT id FROM locations WHERE project_id=?", (pid,))
        run_query("INSERT INTO location_variants (location_id, variant_name) VALUES (?, ?)", (lid, "عادية"))
        run_query("INSERT INTO location_variants (location_id, variant_name) VALUES (?, ?)", (lid, "بعد الخناقة"))
        v1, v2 = [r["id"] for r in fetch_all("SELECT id FROM location_variants WHERE location_id=? ORDER BY id", (lid,))]
        notes = "حسين بيدخل الشقة. بيرمي الشنطة على الكنبة!\nحسين: أنا جيت.\nنادين (من المطبخ): اتأخرت ليه؟"
        run_query("INSERT INTO scenes (project_id, scene_number, location_variant_id, notes) VALUES (?, 1, ?, ?)",
                  (pid, v1, notes))
        run_query("INSERT INTO scenes (project_id, scene_number, location_variant_id, notes) VALUES (?, 2, ?, ?)",
                  (pid, v2, "الشقة متكسرة."))
        s1, s2 = [r["id"] for r in fetch_all("SELECT id FROM scenes WHERE project_id=? ORDER BY scene_number", (pid,))]
        run_query("INSERT INTO characters (project_id, name) VALUES (?, ?)", (pid, "حسين"))
        ch = _one("SELECT id FROM characters WHERE project_id=?", (pid,))
        run_query("INSERT INTO scene_characters (scene_id, character_id) VALUES (?, ?)", (s1, ch))
        run_query("INSERT INTO shots (scene_id, shot_number, shot_size) VALUES (?, 1, ?)", (s1, "عامة (Wide)"))
        shot = _one("SELECT id FROM shots WHERE scene_id=?", (s1,))
    return {"p": pid, "l": lid, "v1": v1, "v2": v2, "s1": s1, "s2": s2, "ch": ch, "shot": shot}


A, B = _project("dec-a"), _project("dec-b")


@test
def test_script_splits_sentences_and_dialogue():
    blocks = blocking.script_blocks("حسين بيدخل الشقة. بيرمي الشنطة!\nحسين: أنا جيت.\n\nنادين (من المطبخ): اتأخرت ليه؟")
    assert [b["kind"] for b in blocks] == ["action", "action", "dialogue", "dialogue"], blocks
    assert blocks[2]["speaker"] == "حسين" and blocks[2]["text"] == "أنا جيت."
    assert blocks[3]["speaker"] == "نادين (من المطبخ)"
    assert [b["i"] for b in blocks] == [0, 1, 2, 3]


@test
def test_selection_fills_shot_texts_and_coverage():
    blocks = blocking.script_blocks("حسين بيدخل الشقة. بيرمي الشنطة!\nحسين: أنا جيت.")
    action, dialogue = blocking.texts_for(blocks, [1, 2])
    assert action == "بيرمي الشنطة!" and dialogue == "حسين: أنا جيت."
    cov = blocking.coverage(blocks, [{"shot_number": 1, "script_blocks": "[0, 1]"},
                                     {"shot_number": 2, "script_blocks": "[1, 2, 99]"}])
    assert cov == {0: [1], 1: [1, 2], 2: [2]}
    assert blocking.parse_block_ids("not json") == set()


@test
def test_plan_is_cleaned():
    p = blocking.clean_plan({"w": 99999, "h": "x", "items": [
        {"k": "sofa", "x": 5000, "y": 10, "w": 200, "h": 80, "r": 0, "label": "كنبة" * 30},
        {"k": "rocket", "x": 1, "y": 1}], "strokes": [{"pts": [[1, 1]]}, {"pts": [[1, 1], [50, 50]]}]})
    assert p["w"] == 2000 and p["h"] == 400
    assert len(p["items"]) == 1 and p["items"][0]["x"] == 2000 and len(p["items"][0]["label"]) == 40
    assert len(p["strokes"]) == 1
    assert blocking.clean_plan("garbage") is None


@test
def test_default_plan_applies_to_every_state_until_a_state_has_its_own():
    assert repo.location_plan(A["p"], A["l"], A["v1"]) is None
    with permissions.system():
        repo.save_location_plan(A["p"], A["l"], 0, {"w": 500, "h": 400, "items": [
            {"k": "sofa", "x": 100, "y": 100, "w": 200, "h": 80, "r": 0, "label": "كنبة"}]})
    for v in (A["v1"], A["v2"]):
        cur = repo.location_plan(A["p"], A["l"], v)
        assert cur["is_default"] and cur["plan"]["items"][0]["label"] == "كنبة"
    with permissions.system():
        repo.save_location_plan(A["p"], A["l"], A["v2"], {"w": 500, "h": 400, "items": []})
    assert not repo.location_plan(A["p"], A["l"], A["v2"])["is_default"]
    assert repo.location_plan(A["p"], A["l"], A["v2"])["plan"]["items"] == []
    assert repo.location_plan(A["p"], A["l"], A["v1"])["is_default"]
    with permissions.system():
        repo.drop_variant_plan(A["p"], A["l"], A["v2"])
    assert repo.location_plan(A["p"], A["l"], A["v2"])["is_default"]


@test
def test_plans_are_per_project():
    assert repo.location_plan(B["p"], B["l"], B["v1"]) is None
    for bad in ((B["p"], A["l"], 0), (A["p"], A["l"], B["v1"])):
        try:
            with permissions.system():
                repo.save_location_plan(*bad, {"w": 300, "h": 300, "items": []})
        except ValueError:
            continue
        raise AssertionError(f"saved a plan across projects: {bad}")


@test
def test_blocking_keeps_only_this_scenes_people_and_shots():
    plan = repo.location_plan(A["p"], A["l"], A["v1"])["plan"]
    with permissions.system():
        repo.save_scene_blocking(A["p"], A["s1"], {
            "chars": [{"id": A["ch"], "x": 50, "y": 60, "f": 90, "tx": 200, "ty": 60}, {"id": B["ch"], "x": 1, "y": 1}],
            "cams": [{"shot_id": A["shot"], "x": 250, "y": 9999, "r": -90}, {"shot_id": B["shot"], "x": 1, "y": 1}]}, plan)
    bl = repo.scene_blocking(A["p"], A["s1"])
    assert [c["id"] for c in bl["chars"]] == [A["ch"]] and bl["chars"][0]["tx"] == 200
    assert [c["shot_id"] for c in bl["cams"]] == [A["shot"]]
    assert bl["cams"][0]["y"] == plan["h"] + blocking.margin(plan["w"], plan["h"])     # برّه الأوضة بحد
    assert repo.scene_blocking(B["p"], A["s1"]) is None
    try:
        with permissions.system():
            repo.save_scene_blocking(B["p"], A["s1"], {"chars": [], "cams": []}, plan)
    except ValueError:
        pass
    else:
        raise AssertionError("saved blocking for another project's scene")


@test
def test_shot_coverage_is_scoped():
    with permissions.system():
        repo.set_shot_blocks(A["p"], A["shot"], [2, 0])
        repo.set_shot_blocks(B["p"], A["shot"], [5])              # مشروع تاني: مايأثرش
    row = fetch_all("SELECT script_blocks FROM shots WHERE id=?", (A["shot"],))[0]
    assert json.loads(row["script_blocks"]) == [0, 2]


@test
def test_a_viewer_cannot_draw():
    try:
        with permissions.acting_as("viewer"):
            repo.save_location_plan(A["p"], A["l"], 0, {"w": 300, "h": 300, "items": []})
    except permissions.Denied:
        return
    raise AssertionError("viewer saved a plan")


@test
def test_scene_place():
    place = repo.scene_place(A["p"], A["s2"])
    assert place["location"] == "شقة حسين" and place["variant"] == "بعد الخناقة"
    assert repo.scene_place(B["p"], A["s2"]) is None


@test
def test_ai_prompt_uses_only_the_projects_texts():
    ctx = plan_jobs.context(A["p"], A["l"])
    assert ctx["location"] == "شقة حسين" and len(ctx["scenes"]) == 2
    prompt = plan_ai.build_prompt(ctx)
    assert "صالة فيها كنبة وترابيزة" in prompt and "Do not invent decor" in prompt
    try:
        plan_jobs.context(B["p"], A["l"])
    except ValueError:
        pass
    else:
        raise AssertionError("read another project's location")


@test
def test_ai_job_round_trip_applies_once_as_default():
    with permissions.system():
        jid = plan_jobs.submit(B["p"], B["l"], "u")
    assert plan_jobs.latest(B["p"], B["l"])["state"] == "queued"
    assert plan_jobs.submit(B["p"], B["l"], "u") == jid                  # مابيبعتش اتنين
    root = os.environ["CIMAFAST_PLAN_SPOOL"]
    for d in ("status", "outbox"):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    body = json.dumps({"w": 600, "h": 450, "items": [{"k": "table", "x": 300, "y": 200, "w": 120, "h": 80,
                                                      "r": 0, "label": "ترابيزة"}]})
    with open(os.path.join(root, "outbox", f"{jid}.result.json"), "w") as fh:
        json.dump({"plan": plan_ai.parse_response(body)}, fh)
    with open(os.path.join(root, "status", f"{jid}.json"), "w") as fh:
        json.dump({"state": "done"}, fh)
    job = plan_jobs.latest(B["p"], B["l"])
    assert job["state"] == "done" and not job["applied"]
    with permissions.system():
        plan_jobs.apply(B["p"], job)
    cur = repo.location_plan(B["p"], B["l"], B["v2"])
    assert cur["is_default"] and cur["source"] == "ai" and cur["plan"]["items"][0]["label"] == "ترابيزة"
    assert plan_jobs.latest(B["p"], B["l"])["applied"]
    try:
        with permissions.system():
            plan_jobs.apply(A["p"], job)
    except ValueError:
        return
    raise AssertionError("applied a job to another project")


@test
def test_shot_list_pdf_gets_a_plans_page():
    import export
    data = export.build_shot_list_pdf({"name": "dec-a", "project_type": "فيلم"}, A["p"], fetch_all)
    assert data[:4] == b"%PDF"
    with open(os.path.join(_TMP, "plans.pdf"), "wb") as fh:
        fh.write(data)
    assert data.count(b"/Type /Page\n") + data.count(b"/Type /Page ") + data.count(b"/Type /Page>") >= 2 \
        or data.count(b"/Page") >= 3


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
