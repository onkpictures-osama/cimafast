"""مقارنة مجموعتين صور بالبكسل.

بتستخدم في المرحلة 0 عشان نثبت إن التجميع مغيّرش أي حاجة بصريًا: قبل وبعد
لازم يطابقوا. وبتستخدم بعد كده عشان نشوف بالظبط أي شاشات اتغيرت.

    venv/bin/python tests/visual/compare.py /tmp/shots/before /tmp/shots/after
    venv/bin/python tests/visual/compare.py before after --diff-dir /tmp/shots/diff

بترجّع 0 لو كل حاجة مطابقة، و1 لو فيه أي فرق أو ملف ناقص.
"""

from __future__ import annotations

import argparse
import os
import sys

from PIL import Image, ImageChops

# فرق أقل من كده في القناة بيتجاهل: ترميز PNG وrasterization الخطوط
# بيعملوا فرق بكسل أو اتنين مش مرئي خالص
CHANNEL_TOLERANCE = 2
# نسبة البكسلات المختلفة اللي بعدها نقول "الصورة اتغيرت"
PIXEL_BUDGET = 0.0005  # 0.05%


def compare_pair(a_path, b_path, diff_dir=None):
    a = Image.open(a_path).convert("RGB")
    b = Image.open(b_path).convert("RGB")
    if a.size != b.size:
        return {"name": os.path.basename(a_path), "status": "SIZE",
                "detail": f"{a.size} != {b.size}", "pct": 100.0}

    diff = ImageChops.difference(a, b)
    # نحوّل لقناة واحدة بأقصى فرق، وبعدين نعدّ البكسلات اللي فوق السماحية
    mono = diff.convert("L")
    hist = mono.histogram()
    total = a.size[0] * a.size[1]
    changed = sum(hist[CHANNEL_TOLERANCE + 1:])
    pct = 100.0 * changed / total
    status = "SAME" if pct <= PIXEL_BUDGET * 100 else "DIFF"
    if status == "DIFF" and diff_dir:
        os.makedirs(diff_dir, exist_ok=True)
        ImageChops.invert(mono).save(os.path.join(diff_dir, os.path.basename(a_path)))
    return {"name": os.path.basename(a_path), "status": status,
            "detail": f"{changed}/{total} px", "pct": pct}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--diff-dir", default=None)
    args = ap.parse_args(argv)

    a_files = {f for f in os.listdir(args.before) if f.endswith(".png")}
    b_files = {f for f in os.listdir(args.after) if f.endswith(".png")}

    rows = []
    for name in sorted(a_files | b_files):
        if name not in a_files:
            rows.append({"name": name, "status": "ONLY-AFTER", "detail": "", "pct": 100.0})
            continue
        if name not in b_files:
            rows.append({"name": name, "status": "ONLY-BEFORE", "detail": "", "pct": 100.0})
            continue
        rows.append(compare_pair(os.path.join(args.before, name),
                                 os.path.join(args.after, name), args.diff_dir))

    width = max(len(r["name"]) for r in rows) if rows else 10
    bad = 0
    for r in rows:
        if r["status"] != "SAME":
            bad += 1
        print(f"{r['name'].ljust(width)}  {r['status']:<11} {r['pct']:>7.3f}%  {r['detail']}")
    print(f"\n{len(rows) - bad}/{len(rows)} مطابقة")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
