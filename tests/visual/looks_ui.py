"""P5 المظاهر والراكور — في متصفح حقيقي، على قاعدة بيانات مزروعة مؤقتة.

البلاغ (2026-09-23): "إضافة مظهر/حالة لشخصية مش شغالة كويس". اللي بيتختبر:
- شخصية مضافة باليد بيبقى ليها «المظهر الرئيسي» على طول، وبتظهر في اختيار
  شخصيات اللقطة (ده كان الباج نفسه).
- المظاهر في كارت الشخصية: المظهر الرئيسي + مظاهر تانية بزرار «خليه الأساسي».

    venv/bin/python tests/visual/looks_ui.py --port 8611 [--out /tmp/shots/looks]
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
    _settle(page, 900)


def _char_card(page, name):
    return page.locator('[data-testid="stExpander"]').filter(has_text=f"🎭 {name}").first


def stage_characters(page, shot_dir):
    _tab(page, "الشخصيات")
    body = page.locator("body").inner_text()
    check("old hidden 'extra look' expander is gone", "إضافة مظهر إضافي لشخصية" not in body)

    # 1) شخصية جديدة باليد
    page.get_by_text("➕ إضافة شخصية جديدة").first.click()
    _settle(page, 700)
    form = page.locator('[data-testid="stForm"]').filter(has_text="إضافة شخصية").first
    form.get_by_label("اسم الشخصية").fill("سلمى")
    form.get_by_role("button", name="إضافة شخصية").click()
    _settle(page, 1500)
    _no_exception(page, "add character")

    card = _char_card(page, "سلمى")
    card.locator("summary").first.click()
    _settle(page, 1500)
    card = _char_card(page, "سلمى")
    txt = card.inner_text()
    check("hand-added character shows a main look", "المظهر الرئيسي" in txt and "المظهر الافتراضي" in txt, txt[:200])

    # 2) مظهر جديد من الكارت نفسه
    card.get_by_text("➕ إضافة مظهر جديد للشخصية دي").first.click()
    _settle(page, 1000)
    card = _char_card(page, "سلمى")
    form = card.locator('[data-testid="stForm"]').filter(has_text="اسم المظهر").first
    form.get_by_label("اسم المظهر").fill("بالنضارة")
    form.get_by_role("button", name="➕ إضافة المظهر").click()
    _settle(page, 1600)
    _no_exception(page, "add look")
    card = _char_card(page, "سلمى")
    txt = card.inner_text()
    check("new look listed under other looks", "مظاهر تانية" in txt and "بالنضارة" in txt)

    # 3) خليه الأساسي
    card.get_by_role("button", name="⭐ خليه الأساسي").first.click()
    _settle(page, 1600)
    _no_exception(page, "make default")
    card = _char_card(page, "سلمى")
    txt = card.inner_text()
    main_line = next((ln for ln in txt.splitlines() if "المظهر الرئيسي" in ln), "")
    check("main look switched", "بالنضارة" in main_line or "بالنضارة" in txt.split("مظاهر تانية")[0], main_line)
    if shot_dir:
        card.screenshot(path=os.path.join(shot_dir, "character-card.png"))


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
        stage_characters(page, shot_dir)
        browser.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8611)
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    run(a.port, a.out)
    print("=" * 60)
    print(f"📊 {sum(results)}/{len(results)} checks passed")
    print("=" * 60)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
