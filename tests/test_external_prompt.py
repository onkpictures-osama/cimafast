#!/usr/bin/env python3
"""Tests for the developed external-analysis prompt (uploaded 2026-09-21).

Why this exists: the prompt asks the model for five fields the app had never
seen — episode_number, characters_speaking, look_change_notes,
suggested_shot_size and suggested_camera_movement. parse_json_script used to
drop every unknown key without a word, so a user following the instructions in
"التحليل خارج البرنامج" would have paid an AI for data the import silently threw
away. Two of the five now have a real home, and the other three raise a warning
instead of vanishing.

The prompt is a single source shared by the copy box in app.py and the Opus
worker in /opt/cimafast-ai/worker.py, so the worker's tool schema has to declare
the same fields — a field the schema does not mention is a field the model will
not emit, however clearly the prompt asks for it.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_prompt import AI_JSON_PROMPT
from script_parser import parse_json_script

results = []
def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"{'✅' if cond else '❌'} {name}" + (f" → {detail}" if detail else ""))


def parse(doc):
    return parse_json_script(json.dumps(doc, ensure_ascii=False).encode("utf-8"))


FULL = {"scenes": [{
    "episode_number": 2, "scene_number": 1, "int_ext": "INT", "day_night": "ليل",
    "location_name": "شقة حسين - غرفة نوم حسين",
    "characters": ["حسين", "سها", "البواب"],
    "characters_speaking": ["حسين", "سها"],
    "props": ["تليفون"],
    "look_change_notes": "حسين ظهر بنظارة لأول مرة",
    "suggested_shot_size": "متوسطة", "suggested_camera_movement": "ثابتة",
    "notes": "حسين: إزيك\nسها: كويسة",
}]}

# --- the prompt itself -------------------------------------------------------
check("prompt is the two-phase version",
      "المرحلة 1" in AI_JSON_PROMPT and "المرحلة 2" in AI_JSON_PROMPT)
for field in ("episode_number", "characters_speaking", "look_change_notes",
              "suggested_shot_size", "suggested_camera_movement"):
    check(f"prompt asks for {field}", field in AI_JSON_PROMPT)
check("prompt still forbids markdown fences around the JSON",
      "من غير ```json" in AI_JSON_PROMPT)

# --- characters_speaking drives silent detection -----------------------------
sc = parse(FULL)["scenes"][0]
check("present-but-silent character detected from the explicit list",
      sc["silent_characters"] == ["البواب"], str(sc["silent_characters"]))
check("speakers are not marked silent",
      "حسين" not in sc["silent_characters"] and "سها" not in sc["silent_characters"])
check("every character is still present", set(sc["characters"]) ==
      {"حسين", "سها", "البواب"})
check("the internal _speaking key does not leak downstream", "_speaking" not in sc)

# An empty speaking list means nobody talks - not "fall back to guessing".
quiet = parse({"scenes": [{"scene_number": 1, "characters": ["أ", "ب"],
                           "characters_speaking": [], "notes": "مشهد صامت"}]})["scenes"][0]
check("an empty speaking list makes everyone silent",
      set(quiet["silent_characters"]) == {"أ", "ب"}, str(quiet["silent_characters"]))

# Without the field at all, the old text heuristic must still run.
legacy = parse({"scenes": [{"scene_number": 1, "characters": ["أ"],
                            "notes": "أ: أهلا"}]})["scenes"][0]
check("a file without characters_speaking still parses",
      legacy["silent_characters"] == [], str(legacy["silent_characters"]))

# --- look_change_notes has to survive ---------------------------------------
check("look change is kept in the notes under a clear label",
      "[تغيير في الشكل]" in sc["notes"] and "نظارة" in sc["notes"])
check("the original notes are not lost", "حسين: إزيك" in sc["notes"])
check("no empty label when there is no look change",
      "[تغيير في الشكل]" not in legacy["notes"])

# --- the three fields with no import path must warn, not vanish --------------
warns = " ".join(parse(FULL)["warnings"])
check("episode numbers raise a warning", "الحلقات" in warns)
check("shot suggestions raise a warning", "حركة الكاميرا" in warns)
check("the values are still carried on the scene",
      sc["episode_number"] == 2 and sc["suggested_shot_size"] == "متوسطة"
      and sc["suggested_camera_movement"] == "ثابتة")
quiet_warns = " ".join(parse({"scenes": [{"scene_number": 1}]})["warnings"])
check("no spurious warning when the fields are absent",
      "الحلقات" not in quiet_warns and "حركة الكاميرا" not in quiet_warns)

# --- the worker must be allowed to emit what the prompt asks for -------------
worker = "/opt/cimafast-ai/worker.py"
if os.path.exists(worker):
    src = open(worker, encoding="utf-8").read()
    schema = src.split("SCENE_SCHEMA", 1)[1].split("GLOSSARY_SCHEMA", 1)[0]
    for field in ("episode_number", "characters_speaking", "look_change_notes",
                  "suggested_shot_size", "suggested_camera_movement"):
        check(f"worker schema declares {field}", f'"{field}"' in schema)
else:
    print("⚠️  worker not installed on this host; schema checks skipped")

print("=" * 60)
print(f"📊 {sum(results)}/{len(results)} tests passed")
print("=" * 60)
sys.exit(0 if all(results) else 1)
