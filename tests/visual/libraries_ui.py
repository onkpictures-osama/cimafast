"""المكتبات في الشريط الجانبي + اختيار ممثل لشخصية من المكتبة — في متصفح حقيقي.

ترتيب الشريط (المالك 2026-09-24): اللوجو ← المكتبات ← المشروع (إنشاء،
الحالي، الدور، الفريق) ← المستخدم. ومن كارت الشخصية «اختار من مكتبة
الممثلين» بيفتح المكتبة في وضع "بتختار لدور X" وبعد التعاقد بيرجع للشخصية.

    venv/bin/python tests/visual/libraries_ui.py --port 8901 [--out /tmp/shots/libs]
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


def _open_sidebar(page):
    if page.evaluate("() => document.querySelector('section[data-testid=stSidebar]')"
                     "?.getAttribute('aria-expanded')") != "true":
        page.locator('[data-testid="stExpandSidebarButton"]').first.click(); _settle(page, 900)


def run(port, shot_dir):
    from playwright.sync_api import sync_playwright
    if shot_dir:
        os.makedirs(shot_dir, exist_ok=True)
    with AppUnderTest(REPO, port) as app, sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()
        page.goto(app.url, wait_until="networkidle"); _settle(page, 1200); _login(page, app)
        _no_exception(page, "login")
        order = page.evaluate("""() => ['cf_sb_brand','cf_sb_libs','cf_sb_projects','cf_sb_account']
            .map(k => { const e = document.querySelector('.st-key-' + k); return e ? Math.round(e.getBoundingClientRect().top) : -1; })""")
        check("sidebar order: logo → libraries → project → user", -1 not in order and order == sorted(order), str(order))
        libs = page.locator(".st-key-cf_sb_libs").inner_text()
        check("libraries section has actors + locations + analyses",
              all(x in libs for x in ("مكتبة الممثلين", "مكتبة مواقع التصوير", "مكتبة التحليلات")))
        if shot_dir:
            page.locator('[data-testid="stSidebar"]').screenshot(path=os.path.join(shot_dir, "sidebar.png"))

        page.locator(".st-key-sb_lib_actors button:visible").first.click(); _settle(page, 2000)
        _no_exception(page, "actors library")
        main = page.locator("section[data-testid=stMain]").inner_text()
        check("actors library opens as its own page", "مكتبة الممثلين" in main and "رجوع للمشروع" in main)
        page.get_by_role("button").filter(has_text="رجوع للمشروع").first.click(); _settle(page, 1800)
        check("back returns to the project tabs", page.get_by_role("tab").count() > 0)

        _open_sidebar(page)
        page.locator(".st-key-sb_lib_locations_lib button:visible").first.click(); _settle(page, 1800)
        _no_exception(page, "locations library")
        check("locations library page opens", "مكتبة مواقع التصوير" in page.locator("section[data-testid=stMain]").inner_text())
        page.get_by_role("button").filter(has_text="رجوع للمشروع").first.click(); _settle(page, 1500)

        # اختيار ممثل لشخصية من المكتبة
        page.get_by_role("tab").filter(has_text="الشخصيات").first.click(); _settle(page, 1500)
        card = page.locator('[data-testid="stExpander"]').filter(has_text="نادية").filter(has_text="🎭").first
        card.locator("summary").first.click(); _settle(page, 1800)
        page.get_by_role("button").filter(has_text="اختار من مكتبة الممثلين").first.click(); _settle(page, 2200)
        _no_exception(page, "pick mode")
        main = page.locator("section[data-testid=stMain]").inner_text()
        check("library opens in 'choosing for نادية' mode", "بتختار ممثل/ة لدور" in main and "نادية" in main)
        page.get_by_text("إضافة ممثل/ة جديد/ة").first.click(); _settle(page, 800)
        form = page.locator('[data-testid="stForm"]').filter(has_text="إضافة الممثل/ة").first
        form.locator("input").first.fill("ممثلة المكتبة")
        form.get_by_role("button").filter(has_text="إضافة الممثل/ة").first.click(); _settle(page, 2200)
        _no_exception(page, "add actor in pick mode")
        if shot_dir:
            page.screenshot(path=os.path.join(shot_dir, "pick-profile.png"), full_page=True)
        page.get_by_role("button").filter(has_text="تعاقد للدور ده").first.click(); _settle(page, 2500)
        _no_exception(page, "cast from library")
        sel = page.locator('[role="tab"][aria-selected="true"]').first.inner_text() if page.get_by_role("tab").count() else ""
        check("after casting you're back on the characters tab", "الشخصيات" in sel, sel)
        head = page.locator('[data-testid="stExpander"]').filter(has_text="نادية").filter(has_text="🎭").first.locator("summary").inner_text()
        check("character card shows the cast actor", "ممثلة المكتبة" in head, head)
        b.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8901)
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    run(a.port, a.out)
    print("=" * 60)
    print(f"📊 {sum(results)}/{len(results)} checks passed")
    print("=" * 60)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
