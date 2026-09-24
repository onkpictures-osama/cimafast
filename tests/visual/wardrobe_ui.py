"""P10 الملابس — في متصفح حقيقي، على قاعدة بيانات مزروعة مؤقتة.

اللي بيتختبر:
- تبويب «الممثلين» بيفتح على ممثلين المشروع، و«الملابس» بعده على طول.
- لوحة الغيارات: ⚠️ للشخصية اللي في مشهد من غير غيار، وزرار "حط غيار 1 في
  المشاهد اللي من غير غيار" بيملاها.
- الغيارات والقطع: إضافة غيار جديد باسمه، وكارته بيفتح بجدول القطع.
- قايمة القطع: الرسالة الفاضية وزرار كشف الملابس.

    venv/bin/python tests/visual/wardrobe_ui.py --port 8731 [--out /tmp/shots/wardrobe]
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from shots import REPO, AppUnderTest, _login, _settle  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"{'✅' if cond else '❌'} {name}" + (f" → {detail}" if detail else ""))


def _no_exception(page, where):
    errs = page.locator('[data-testid="stException"]')
    check(f"no exception on {where}", errs.count() == 0,
          errs.first.inner_text()[:300] if errs.count() else "")


def _tab(page, label):
    tab = page.get_by_role("tab").filter(has_text=label).first
    tab.scroll_into_view_if_needed()
    tab.click()
    _settle(page, 1400)


def stage(page, shot_dir):
    tabs = [x.strip() for x in page.get_by_role("tab").all_inner_texts()]
    i_c = next(i for i, x in enumerate(tabs) if "الممثلين" in x)
    check("tab order: الشخصيات ← الممثلين ← الملابس",
          "الشخصيات" in tabs[i_c - 1] and "الملابس" in tabs[i_c + 1], str(tabs))

    _tab(page, "الممثلين")
    _no_exception(page, "cast tab")
    body = page.locator("body").inner_text()
    check("cast tab opens on the project's cast", "ممثلين المشروع" in body and "خزانة المواهب" in body)

    _tab(page, "الملابس")
    _no_exception(page, "wardrobe tab")
    body = page.locator("body").inner_text()
    check("wardrobe metrics shown", "الغيارات" in body and "مشهد من غير غيار" in body)
    grid = page.locator('[data-testid="stDataFrame"]').first
    cells = grid.locator('[role="gridcell"]').all_inner_texts()
    check("board flags scenes with no change", "⚠️" in cells, str(cells[:12]))
    if shot_dir:
        page.screenshot(path=os.path.join(shot_dir, "board-before.png"), full_page=True)

    fill = page.get_by_role("button").filter(has_text="في المشاهد اللي من غير غيار").first
    check("fill-missing button offered", fill.count() > 0)
    fill.click()
    _settle(page, 2000)
    _no_exception(page, "fill missing")
    cells = page.locator('[data-testid="stDataFrame"]').first.locator('[role="gridcell"]').all_inner_texts()
    check("board now shows change 1", "1" in cells, str(cells[:12]))

    page.locator("button").filter(has_text="الغيارات والقطع").first.click()
    _settle(page, 1500)
    _no_exception(page, "changes section")
    form = page.locator('[data-testid="stForm"]').filter(has_text="اسم الغيار الجديد").first
    form.locator("input").first.fill("بدلة الفرح")
    form.get_by_role("button").filter(has_text="غيار جديد").first.click()
    _settle(page, 2000)
    _no_exception(page, "add change")
    card = page.locator('[data-testid="stExpander"]').filter(has_text="غيار 2 · بدلة الفرح").first
    check("new change listed as غيار 2", card.count() > 0)
    card.locator("summary").first.click()
    _settle(page, 1800)
    _no_exception(page, "open change card")
    card = page.locator('[data-testid="stExpander"]').filter(has_text="غيار 2 · بدلة الفرح").first
    check("change card has an items table", card.locator('[data-testid="stDataFrame"]').count() > 0
          and "حفظ القطع" in card.inner_text())
    if shot_dir:
        page.screenshot(path=os.path.join(shot_dir, "changes.png"), full_page=True)

    page.locator("button").filter(has_text="قايمة القطع").first.click()
    _settle(page, 1500)
    _no_exception(page, "items section")
    body = page.locator("body").inner_text()
    check("empty items message + wardrobe sheet button",
          "لسه مفيش قطع ملابس" in body and "كشف الملابس" in body)


def run(port, shot_dir, width=1440, height=1000):
    from playwright.sync_api import sync_playwright

    if shot_dir:
        os.makedirs(shot_dir, exist_ok=True)
    with AppUnderTest(REPO, port) as app, sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_context(viewport={"width": width, "height": height}).new_page()
        page.goto(app.url, wait_until="networkidle")
        _settle(page, 1200)
        _login(page, app)
        _no_exception(page, "login")
        try:
            stage(page, shot_dir)
        except Exception:
            page.screenshot(path="/tmp/wardrobe-fail.png", full_page=True)
            raise
        browser.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8731)
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    run(a.port, a.out)
    print("=" * 60)
    print(f"📊 {sum(results)}/{len(results)} checks passed")
    print("=" * 60)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
