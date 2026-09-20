#!/usr/bin/env python3
"""Regression tests for the drama script analyzer.

Each case here corresponds to a defect that shipped and was reported as working:

  1. Props extraction used a bare substring search. The commit that claimed to
     "handle Arabic articles" added an OPTIONAL prefix with no word boundary,
     which matches identically with or without the alternation - a no-op. It
     read 'الدرجة' (step) as 'درج' (drawer) and 'الكوبري' (bridge) as 'كوب' (cup).
  2. Silent-character detection was handed the list of characters who HAVE
     dialogue, so it could only ever return speakers - the exact opposite - and
     its result was appended to a list those names were already in, making the
     whole block dead code. The 'silent_characters' key never existed.
  3. The analysis dashboard was rendered inside the confirm-import button, which
     then deleted parsed_script and called st.rerun(), discarding the frame it
     had just drawn. It was unreachable in the browser.

Run:  venv/bin/python test_script_parser.py
"""
import sys

from script_parser import (
    _extract_props_from_text,
    _detect_silent_characters,
    parse_script,
)

results = []


def check(name, condition, detail=""):
    results.append(bool(condition))
    print(f"{'✅' if condition else '❌'} {name}" + (f" → {detail}" if detail else ""))


def scene_from(script, **kw):
    out = parse_script("t.txt", script.encode("utf-8"), **kw)
    return out["scenes"][0] if out["scenes"] else {}


# ---------------------------------------------------------------- props
def test_props_word_boundaries():
    for text, forbidden, why in [
        ("وصل إلى الدرجة الأولى", "درج", "'الدرجة' (step) is not a drawer"),
        ("عبروا الكوبري بسرعة", "كوب", "'الكوبري' (bridge) is not a cup"),
        ("ركب المدرج", "درج", "'المدرج' (runway) is not a drawer"),
        ("سيفون الحمام", "سيف", "'سيفون' (cistern) is not a sword"),
    ]:
        got = _extract_props_from_text(text, [])
        check(f"no false positive: {why}", forbidden not in got, f"got {got}")


def test_props_still_found():
    for text, expected, why in [
        ("أحمد يمسك الكتاب", "كتاب", "ال prefix"),
        ("أخرج المسدس والمفتاح", "مفتاح", "وال prefix"),
        ("وضع الفنجان على الطاولة", "فنجان", "plain noun"),
        ("فتح الدرج", "درج", "genuine drawer still detected"),
    ]:
        got = _extract_props_from_text(text, [])
        check(f"still detects {expected} ({why})", expected in got, f"got {got}")


# ------------------------------------------------------- silent characters
def test_silent_excludes_speakers():
    # the original bug: a character WITH dialogue came back as "silent"
    silent = _detect_silent_characters("أحمد يدخل الغرفة", ["أحمد"], ["أحمد"])
    check("a speaking character is never silent", silent == [], f"got {silent}")


def test_silent_finds_non_speaker():
    silent = _detect_silent_characters("سعاد تقف في الركن", ["أحمد"], ["أحمد", "سعاد"])
    check("a non-speaking character in the action is silent", silent == ["سعاد"], f"got {silent}")


def test_silent_ignores_absent():
    silent = _detect_silent_characters("سعاد تقف في الركن", ["أحمد"], ["أحمد", "خالد"])
    check("a character absent from the scene is not silent", silent == [], f"got {silent}")


def test_silent_name_boundaries():
    # 'علي' must not match inside 'عليها'
    silent = _detect_silent_characters("وضع يده عليها", [], ["علي"])
    check("name not matched inside a longer word", silent == [], f"got {silent}")


# ----------------------------------------------------------- end to end
SCRIPT = """مشهد 1 - داخلي - نهار - شقة

أحمد يمسك الهاتف. سعاد تقف في الركن بلا كلام. وصل إلى الدرجة الأولى.

أحمد: أين المفتاح يا فاطمة؟

فاطمة: لا أعرف.
"""


def test_end_to_end():
    sc = scene_from(SCRIPT, known_characters=["سعاد", "خالد"])
    check("key 'silent_characters' exists (was never created before)",
          "silent_characters" in sc, f"keys={sorted(sc)[:6]}")
    check("سعاد detected as silent", sc.get("silent_characters") == ["سعاد"],
          f"got {sc.get('silent_characters')}")
    check("silent character added to the scene cast",
          "سعاد" in sc.get("characters", []), f"got {sc.get('characters')}")
    check("خالد (not in scene) excluded", "خالد" not in sc.get("characters", []))
    check("props clean end to end", sorted(sc.get("props", [])) == sorted(["هاتف", "مفتاح"]),
          f"got {sc.get('props')}")


def test_cross_scene_roster():
    """A character who speaks in one scene and is silent in another."""
    script = """مشهد 1 - داخلي - نهار - شقة

فاطمة تقف بجوار النافذة.

أحمد: أين أنت؟

مشهد 2 - داخلي - ليل - شقة

فاطمة: أنا هنا.
"""
    scenes = parse_script("t.txt", script.encode("utf-8"))["scenes"]
    check("two scenes parsed", len(scenes) == 2, f"got {len(scenes)}")
    if len(scenes) == 2:
        check("فاطمة silent in scene 1, speaking in scene 2",
              scenes[0].get("silent_characters") == ["فاطمة"]
              and "فاطمة" in scenes[1].get("characters", []),
              f"s1 silent={scenes[0].get('silent_characters')} s2 cast={scenes[1].get('characters')}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Drama analyzer regression suite")
    print("=" * 60 + "\n")
    for fn in [test_props_word_boundaries, test_props_still_found,
               test_silent_excludes_speakers, test_silent_finds_non_speaker,
               test_silent_ignores_absent, test_silent_name_boundaries,
               test_end_to_end, test_cross_scene_roster]:
        fn()
    passed, total = sum(results), len(results)
    print("\n" + "=" * 60)
    print(f"📊 {passed}/{total} tests passed")
    print("=" * 60 + "\n")
    sys.exit(0 if passed == total else 1)
