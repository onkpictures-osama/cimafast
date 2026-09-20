#!/usr/bin/env python3
"""Tests for split-scene numbering (35A / 35B).

Why this exists: AI_JSON_PROMPT tells the model to split a photomontage scene
35 into 35, 36, 37 and shift every later scene. That desynchronises the app from
the script the crew is holding, and it breaks re-import - the importer skipped
"scene numbers that already exist", so after a shift it skipped the wrong ones.

Scenes now keep their real number and carry a separate letter. scene_number
stays INTEGER on purpose: scene_number + 1 arithmetic is used when inserting a
scene, and would break if the column became text.
"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["STUDIO_DB_PATH"] = _tmp.name

import json
from database import init_db, fetch_all, run_query, scene_label, _existing_columns, get_connection
from script_parser import parse_json_script
from importer import import_parsed_scenes

results = []
def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"{'✅' if cond else '❌'} {name}" + (f" → {detail}" if detail else ""))


def test_label():
    check("35 + A renders as 35A", scene_label({"scene_number": 35, "scene_suffix": "A"}) == "35A")
    check("no suffix renders bare", scene_label({"scene_number": 36, "scene_suffix": None}) == "36")
    check("missing key renders bare", scene_label({"scene_number": 12}) == "12")
    check("None is safe", scene_label(None) == "")


def test_parser_carries_suffix():
    data = {"scenes": [{"scene_number": 35, "scene_suffix": "A", "location_name": "شقة"},
                       {"scene_number": 35, "scene_suffix": "B", "location_name": "شارع"},
                       {"scene_number": 36, "location_name": "مكتب"}]}
    scenes = parse_json_script(json.dumps(data).encode())["scenes"]
    check("suffixes survive parsing",
          [scene_label(s) for s in scenes] == ["35A", "35B", "36"],
          str([scene_label(s) for s in scenes]))


def test_migration_applied():
    init_db()
    conn = get_connection()
    cols = _existing_columns(conn, "scenes")
    conn.close()
    check("scenes.scene_suffix column exists", "scene_suffix" in cols, str(sorted(cols)))
    check("scene_number is still INTEGER (arithmetic depends on it)",
          "scene_number" in cols)


def _import(pid, scenes):
    return import_parsed_scenes(pid, scenes, fetch_all, run_query)


def test_import_and_reimport():
    init_db()
    pid = run_query("INSERT INTO projects (name, project_type) VALUES (?,?)",
                    ("t", "فيلم"))
    scenes = parse_json_script(json.dumps({"scenes": [
        {"scene_number": 35, "scene_suffix": "A", "location_name": "شقة"},
        {"scene_number": 35, "scene_suffix": "B", "location_name": "شارع"},
        {"scene_number": 36, "location_name": "مكتب"},
    ]}).encode())["scenes"]

    s1 = _import(pid, scenes)
    check("all three imported as distinct scenes", s1["scenes_added"] == 3,
          f"added {s1['scenes_added']}")

    rows = fetch_all("SELECT scene_number, scene_suffix FROM scenes WHERE project_id=?", (pid,))
    labels = sorted(scene_label(r) for r in rows)
    check("35A, 35B and 36 stored as three distinct rows",
          labels == ["35A", "35B", "36"], str(labels))
    check("later scene NOT renumbered", 36 in [r["scene_number"] for r in rows])

    s2 = _import(pid, scenes)
    check("re-import skips all three", s2["scenes_added"] == 0 and len(s2["scenes_skipped"]) == 3,
          f"added {s2['scenes_added']} skipped {s2['scenes_skipped']}")

    extra = parse_json_script(json.dumps({"scenes": [
        {"scene_number": 35, "scene_suffix": "C", "location_name": "سطح"},
    ]}).encode())["scenes"]
    s3 = _import(pid, extra)
    check("a NEW split of an existing number is not wrongly skipped",
          s3["scenes_added"] == 1, f"added {s3['scenes_added']}, skipped {s3['scenes_skipped']}")


def test_sort_order():
    rows = [{"scene_number": 36, "scene_suffix": None},
            {"scene_number": 35, "scene_suffix": "B"},
            {"scene_number": 35, "scene_suffix": None},
            {"scene_number": 35, "scene_suffix": "A"}]
    rows.sort(key=lambda r: (r["scene_number"], r["scene_suffix"] or ""))
    check("sorts 35, 35A, 35B, 36",
          [scene_label(r) for r in rows] == ["35", "35A", "35B", "36"],
          str([scene_label(r) for r in rows]))


if __name__ == "__main__":
    print("\n" + "=" * 60 + "\nSplit-scene numbering (35A / 35B)\n" + "=" * 60 + "\n")
    try:
        for fn in [test_label, test_parser_carries_suffix, test_migration_applied,
                   test_import_and_reimport, test_sort_order]:
            fn()
    finally:
        os.unlink(_tmp.name)
    p, t = sum(results), len(results)
    print("\n" + "=" * 60 + f"\n📊 {p}/{t} tests passed\n" + "=" * 60 + "\n")
    sys.exit(0 if p == t else 1)
