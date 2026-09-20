"""بيقيس أقصى تداخل لطبقات ‎backdrop-filter‎ في الصفحة الحقيقية.

ليه: البلور شغل GPU على جهاز المستخدم، والتداخل بيضاعف التكلفة. المالك
بيفتح البرنامج من الموبايل، فالحد الأقصى المسموح **طبقتين متداخلتين**.
اختبار الـ CSS البنيوي في ‎tests/test_theme.py‎ بيمنع الدرجة المعتمة من إنها
تعلن بلور، بس الحاجة الوحيدة اللي بتقيس التداخل الفعلي هي المتصفح.

    venv/bin/python tests/visual/blur_depth.py --port 8596

بيرجّع 1 لو أي شاشة عدّت طبقتين.
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from shots import (  # noqa: E402
    ANALYZE_LABEL, SAMPLE_SCRIPT, TAB_LABELS, VIEWPORTS, AppUnderTest,
    REPO, _click_tab, _login, _settle,
)

MAX_NESTED_BLUR = 2

# بنمشي على كل عنصر ونعدّ كام أب ليه (هو نفسه ضمنهم) عليه backdrop-filter
JS_MAX_DEPTH = """
() => {
  const blurred = el => {
    const s = getComputedStyle(el);
    const v = s.backdropFilter || s.webkitBackdropFilter || 'none';
    return v && v !== 'none' && !/^blur\\(0px\\)$/.test(v.trim());
  };
  let worst = 0, worstPath = '';
  const walk = (el, depth, path) => {
    const d = blurred(el) ? depth + 1 : depth;
    const p = blurred(el)
      ? path + ' > ' + el.tagName.toLowerCase() +
        (el.className && typeof el.className === 'string'
          ? '.' + el.className.trim().split(/\\s+/).slice(0, 2).join('.')
          : '')
      : path;
    if (d > worst) { worst = d; worstPath = p; }
    for (const c of el.children) walk(c, d, p);
  };
  walk(document.body, 0, 'body');
  return { depth: worst, path: worstPath };
}
"""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8596)
    ap.add_argument("--tree", default=REPO)
    ap.add_argument("--theme", default="glass", choices=["classic", "glass"])
    args = ap.parse_args(argv)

    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    worst = []
    with AppUnderTest(args.tree, args.port) as app:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            w, h = VIEWPORTS["desktop"]
            ctx = browser.new_context(viewport={"width": w, "height": h})
            page = ctx.new_page()
            page.goto(app.url + ("/?theme=glass" if args.theme == "glass" else "/"),
                      wait_until="domcontentloaded")
            _settle(page)
            worst.append(("login", page.evaluate(JS_MAX_DEPTH)))
            _login(page, app)
            worst.append(("projects", page.evaluate(JS_MAX_DEPTH)))
            for key in ("scenes", "reports"):
                _click_tab(page, key, "ar")
                worst.append((key, page.evaluate(JS_MAX_DEPTH)))
            _click_tab(page, "import", "ar")
            script_path = os.path.join(app.tmp, "s.txt")
            with open(script_path, "w", encoding="utf-8") as fh:
                fh.write(SAMPLE_SCRIPT)
            page.locator('input[type="file"]').first.set_input_files(script_path)
            _settle(page, 1200)
            page.get_by_role("button").filter(has_text=ANALYZE_LABEL["ar"]).first.click()
            _settle(page, 2000)
            worst.append(("analysis", page.evaluate(JS_MAX_DEPTH)))
            browser.close()

    bad = 0
    for name, res in worst:
        ok = res["depth"] <= MAX_NESTED_BLUR
        bad += 0 if ok else 1
        print(f"{name:<10} depth={res['depth']}  {'ok' if ok else 'OVER LIMIT'}")
        if not ok:
            print("   " + res["path"])
    print(f"\nالحد الأقصى {MAX_NESTED_BLUR} — {len(worst) - bad}/{len(worst)} شاشة داخل الحد")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
