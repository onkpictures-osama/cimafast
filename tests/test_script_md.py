#!/usr/bin/env python3
"""Tests for the markdown normalisation layer.

The safety property under test: it removes page furniture and NEVER removes
screenplay content. A normaliser that silently eats a line of dialogue would
corrupt every downstream breakdown, so content preservation is asserted
explicitly, including for content that looks like furniture.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from script_md import to_markdown

results = []
def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"{'✅' if cond else '❌'} {name}" + (f" → {detail}" if detail else ""))


RAW = """سيناريو: الرحلة الأخيرة

- 1 -

مشهد 1 - داخلي - نهار - شقة أحمد

أحمد يجلس ممسكًا الهاتف.


أحمد: أين المفتاح؟

فاطمة: لا أعرف.

________________________

سيناريو: الرحلة الأخيرة
- 2 -

مشهد 2 : خارجي - ليل - الشارع

سعاد تقف صامتة.

سيناريو: الرحلة الأخيرة
- 3 -
سيناريو: الرحلة الأخيرة
- 4 -
سيناريو: الرحلة الأخيرة
"""


def test_furniture_removed():
    md, st = to_markdown(RAW.splitlines())
    check("page numbers removed", "- 1 -" not in md and "- 2 -" not in md)
    check("decorative rule removed", "______" not in md)
    check("repeated running header removed", md.count("سيناريو: الرحلة الأخيرة") == 0,
          f"count={md.count('سيناريو: الرحلة الأخيرة')}")
    check("stats report what was removed", st["removed"].get("page furniture", 0) > 0, str(st["removed"]))
    check("stats name the removed header",
          any("الرحلة" in h for h in st["removed_header_samples"]), str(st["removed_header_samples"]))


def test_content_preserved():
    md, _ = to_markdown(RAW.splitlines())
    for must in ["أين المفتاح؟", "لا أعرف", "أحمد يجلس ممسكًا الهاتف", "سعاد تقف صامتة"]:
        check(f"keeps content: {must[:22]}", must in md)


def test_repeated_dialogue_is_never_removed():
    """A short line repeated many times is furniture-shaped - but if it is
    dialogue it must survive regardless of how often it repeats."""
    lines = []
    for i in range(1, 9):
        lines += [f"مشهد {i} - داخلي - نهار - غرفة", "أحمد: نعم.", ""]
    md, _ = to_markdown(lines)
    check("dialogue repeated 8 times is fully kept", md.count("نعم.") == 8,
          f"kept {md.count('نعم.')}/8")


def test_headings_and_dialogue_formatting():
    md, _ = to_markdown(RAW.splitlines())
    check("scene heading becomes an h2", "## مشهد 1" in md, md.splitlines()[0] if md else "")
    check("heading keeps its detail", "داخلي - نهار - شقة أحمد" in md)
    check("colon-form heading normalised too", "## مشهد 2" in md)
    check("dialogue marked up", "**أحمد:** أين المفتاح؟" in md)


def test_whitespace_collapsed():
    md, st = to_markdown(["مشهد 1", "", "", "", "أحمد    يدخل\tالغرفة", "", ""])
    check("no triple blank lines", "\n\n\n" not in md, repr(md))
    check("internal runs of spaces collapsed", "أحمد يدخل الغرفة" in md, repr(md))
    check("reports a saving", st["saved_chars"] >= 0 and 0 <= st["saved_pct"] <= 100)


def test_empty_and_odd_input():
    md, st = to_markdown([])
    check("empty input does not crash", md.strip() == "" and st["raw_chars"] == 0)
    md2, _ = to_markdown(["مشهد 1 - داخلي - نهار - مكان"])
    check("single heading works", "## مشهد 1" in md2)


def test_real_saving():
    md, st = to_markdown(RAW.splitlines())
    check("normalisation actually shrinks the input", st["saved_pct"] > 10,
          f"saved {st['saved_pct']}% ({st['raw_chars']}→{st['md_chars']} chars)")


if __name__ == "__main__":
    print("\n" + "=" * 60 + "\nScript markdown normalisation\n" + "=" * 60 + "\n")
    for fn in [test_furniture_removed, test_content_preserved,
               test_repeated_dialogue_is_never_removed,
               test_headings_and_dialogue_formatting, test_whitespace_collapsed,
               test_empty_and_odd_input, test_real_saving]:
        fn()
    p, t = sum(results), len(results)
    print("\n" + "=" * 60 + f"\n📊 {p}/{t} tests passed\n" + "=" * 60 + "\n")
    sys.exit(0 if p == t else 1)
