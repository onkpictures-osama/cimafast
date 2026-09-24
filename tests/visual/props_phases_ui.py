"""الإكسسوار تابع للأماكن + مفتاح المراحل — في متصفح حقيقي.

    venv/bin/python tests/visual/props_phases_ui.py --port 8771 [--out /tmp/shots/props]
"""

from __future__ import annotations

import argparse
import os
import re
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


def _tabs(page):
    return [x.strip() for x in page.get_by_role("tab").all_inner_texts()]


def run(port, shot_dir):
    from playwright.sync_api import sync_playwright
    if shot_dir:
        os.makedirs(shot_dir, exist_ok=True)
    with AppUnderTest(REPO, port) as app, sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()
        page.goto(app.url, wait_until="networkidle"); _settle(page, 1200); _login(page, app)
        _no_exception(page, "login")
        tabs = _tabs(page)
        want = ["سيناريو", "الأماكن", "الإكسسوار", "الشخصيات", "الممثلين", "الملابس", "المشاهد", "اللقطات",
                "التقارير", "فريق العمل", "إعدادات"]
        check("pre-production tabs in the agreed order",
              len(tabs) == len(want) and all(w in x for w, x in zip(want, tabs)), str(tabs))

        page.get_by_role("tab").filter(has_text="الإكسسوار").first.click(); _settle(page, 1800)
        _no_exception(page, "props tab")
        body = page.locator("body").inner_text()
        check("props explained (set vs hand vs worn)", "الإكسسواريست" in body and "الملابس" in body)
        if shot_dir:
            page.screenshot(path=os.path.join(shot_dir, "props-unplaced.png"), full_page=True)
        apply_btn = page.get_by_role("button").filter(has_text="تطبيق")
        if apply_btn.count():
            apply_btn.first.click(); _settle(page, 2200)
            _no_exception(page, "apply suggestions")
        page.locator("button").filter(has_text="إكسسوار الأماكن").first.click(); _settle(page, 1500)
        _no_exception(page, "set props section")
        exp = page.locator('[data-testid="stExpander"]').filter(has_text="🏠").first
        check("locations listed with their props", exp.count() > 0)
        exp.locator("summary").first.click(); _settle(page, 1800)
        _no_exception(page, "open a location")
        check("location shows a props table",
              page.locator('[data-testid="stExpander"]').filter(has_text="🏠").first
              .locator('[data-testid="stDataFrame"]').count() > 0)
        if shot_dir:
            page.screenshot(path=os.path.join(shot_dir, "props-places.png"), full_page=True)

        page.locator("button").filter(has_text=re.compile(r"(?<!بعد )(?<!قبل )الإنتاج\s*$")).first.click(); _settle(page, 1800)
        _no_exception(page, "production phase")
        tabs = _tabs(page)
        check("production phase shows schedule + crew + settings",
              len(tabs) == 3 and "جدول التصوير" in tabs[0] and "فريق العمل" in tabs[1], str(tabs))
        check("schedule tab shows its summary", "مشاهد متجدولة" in page.locator("body").inner_text())

        # الرابط المباشر (زي اللي في التنبيهات والرئيسية): بيفتح مرحلته لوحده.
        # جلسة التجربة مابتفضلش بعد goto، فبندخل تاني والرابط بيتطبق بعد الدخول.
        page.goto(app.url + "/?tab=schedule", wait_until="networkidle"); _settle(page, 2000)
        if page.get_by_label("اسم المستخدم / Username").count():
            _login(page, app)
            _settle(page, 2000)
        tabs = _tabs(page)
        check("a link to the schedule opens the production phase", tabs and "جدول التصوير" in tabs[0], str(tabs))
        b.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8771)
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    run(a.port, a.out)
    print("=" * 60)
    print(f"📊 {sum(results)}/{len(results)} checks passed")
    print("=" * 60)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
