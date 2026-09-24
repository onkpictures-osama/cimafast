"""التنقّل بيقفل الشريط الجانبي وبيودّي للصفحة الصح — في متصفح حقيقي.

طلب المالك (2026-09-24): ترس الإعدادات، إنشاء مشروع، وتغيير المشروع لازم
يقفلوا الشريط الجانبي ويودّوا للصفحة على طول؛ وجدول التصوير مش في الإعدادات.

    venv/bin/python tests/visual/navigation_ui.py --port 8791
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from shots import REPO, AppUnderTest, _login, _settle  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"{'✅' if cond else '❌'} {name}" + (f" → {detail}" if detail else ""))


def _sidebar_open(page):
    return page.evaluate("() => document.querySelector('section[data-testid=stSidebar]')"
                         "?.getAttribute('aria-expanded')") == "true"


def _open_sidebar(page):
    if not _sidebar_open(page):
        page.locator('[data-testid="stExpandSidebarButton"]').first.click()
        _settle(page, 900)


def _selected_tab(page):
    return page.locator('[role="tab"][aria-selected="true"]').first.inner_text().strip()


def run(port, width):
    from playwright.sync_api import sync_playwright
    with AppUnderTest(REPO, port) as app, sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_context(viewport={"width": width, "height": 900}).new_page()
        page.goto(app.url, wait_until="networkidle"); _settle(page, 1200); _login(page, app)
        con = sqlite3.connect(os.path.join(app.tmp, "studio.db"))
        con.execute("UPDATE memberships SET role='admin' WHERE user_id=(SELECT id FROM users WHERE username=?)",
                    (app.username,))
        con.commit(); con.close()
        page.reload(wait_until="networkidle"); _settle(page, 1500)
        if page.get_by_label("اسم المستخدم / Username").count():
            _login(page, app); _settle(page, 1500)
        tag = f"[{width}px]"

        # 1) ترس الإعدادات
        _open_sidebar(page)
        page.locator('.st-key-sb_open_settings button:visible').first.click(); _settle(page, 2200)
        check(f"{tag} ⚙️ opens Project Settings", "إعدادات المشروع" in _selected_tab(page), _selected_tab(page))
        check(f"{tag} ⚙️ closes the sidebar", not _sidebar_open(page))
        body = page.locator("section[data-testid=stMain]").inner_text()
        check(f"{tag} no shooting-schedule link inside settings", "جدول التصوير" not in body)

        # 2) إنشاء مشروع
        _open_sidebar(page)
        sb = page.locator('[data-testid="stSidebar"]')
        sb.get_by_text("إنشاء مشروع جديد").first.click(); _settle(page, 800)
        sb.locator("[class*=st-key-new_proj_name] input").fill("مشروع التنقل")
        sb.get_by_role("button", name="إنشاء المشروع").click(); _settle(page, 2600)
        title = page.locator("h2").filter(has_text="مشروع التنقل").count()
        check(f"{tag} new project opens right away", title > 0)
        check(f"{tag} …on «إضافة سيناريو»", "إضافة سيناريو" in _selected_tab(page), _selected_tab(page))
        check(f"{tag} …and the sidebar closes", not _sidebar_open(page))
        _open_sidebar(page)
        form_open = page.evaluate("""() => [...document.querySelectorAll('[data-testid=stSidebar] details')]
            .some(d => d.open && d.querySelector('summary').innerText.includes('إنشاء مشروع'))""")
        check(f"{tag} the create form comes back closed", not form_open)

        # 3) تغيير المشروع
        _open_sidebar(page)
        sel = page.locator('[data-testid="stSidebar"] [data-testid="stSelectbox"]').filter(has_text="المشروع الحالي").first
        sel.locator('button[aria-label="Open"]').first.click(); _settle(page, 600)
        page.get_by_role("option").filter(has_text="عروسة البحر").first.click(); _settle(page, 2400)
        check(f"{tag} switching project shows it", page.locator("h2").filter(has_text="عروسة البحر").count() > 0)
        check(f"{tag} switching project closes the sidebar", not _sidebar_open(page))
        errs = page.locator('[data-testid="stException"]').count()
        check(f"{tag} no exceptions", errs == 0)
        b.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8791)
    a = ap.parse_args(argv)
    run(a.port, 1440)
    run(a.port + 1, 390)
    print("=" * 60)
    print(f"📊 {sum(results)}/{len(results)} checks passed")
    print("=" * 60)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
