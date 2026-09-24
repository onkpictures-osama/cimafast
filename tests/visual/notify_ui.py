"""H4 جرس التنبيهات — في متصفح حقيقي، على قاعدة بيانات مزروعة مؤقتة.

معيار الانتهاء في PRODUCT-PLAN: تغيير في مكان مشهد بيبان **في نفس الجلسة**
للقسم اللي يهمّه، من غير refresh. فالاختبار:
1. بيدخل، وبعدين مستخدم تاني بيغيّر مكان مشهد في القاعدة والصفحة مفتوحة.
2. بيستنى الجرس في الشريط الجانبي يعدّ ١ لوحده (من غير reload).
3. بيفتح الجرس، بيلاقي "مشهد N: اتغيّر المكان"، وبيدوس عليه.
4. تبويب المشاهد بيفتح على المشهد ده بس، وفورمته مفتوحة.
وبعدين نفس الجرس على التليفون (390px): زرار ≥44px ومفيش زحلقة أفقية.

    venv/bin/python tests/visual/notify_ui.py --port 8612 [--out /tmp/shots/notify]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from shots import REPO, AppUnderTest, _login, _settle  # noqa: E402

results = []

# تغيير من مستخدم تاني، في process لوحده زي أي جلسة تانية على نفس القاعدة
_CHANGE = r"""
import sys, audit, permissions
from database import fetch_all, run_query
pid = fetch_all("SELECT id FROM projects ORDER BY id DESC LIMIT 1")[0]["id"]
sc = fetch_all("SELECT id, scene_number, location_variant_id FROM scenes WHERE project_id=? "
               "ORDER BY scene_number LIMIT 1", (pid,))[0]
other = fetch_all("SELECT v.id FROM location_variants v JOIN locations l ON l.id=v.location_id "
                  "WHERE l.project_id=? AND v.id<>? LIMIT 1", (pid, sc["location_variant_id"] or 0))[0]["id"]
audit.set_context(username="ad_bot", project_id=pid, source="app")
permissions.act_as("admin")
run_query("UPDATE scenes SET location_variant_id=? WHERE id=?", (other, sc["id"]))
print(sc["id"], sc["scene_number"])
"""


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"{'✅' if cond else '❌'} {name}" + (f" → {detail}" if detail else ""))


def _no_exception(page, where):
    errs = page.locator('[data-testid="stException"]')
    check(f"no exception on {where}", errs.count() == 0,
          errs.first.inner_text()[:300] if errs.count() else "")


def _bell(page):
    # Streamlit بيرسم نسختين من أي popover ليه help (ديسكتوب بتلميح وموبايل من
    # غيره) وبيخبّي واحدة — فبناخد الظاهرة بس.
    return page.locator('[data-testid="stSidebar"] .st-key-cf_notif_pop '
                        '[data-testid="stPopoverButton"] >> visible=true').first


def _count(page):
    """الرقم في شارة الجرس (0 لو مفيش شارة). النص فيه علامات اتجاه."""
    badge = page.locator('[data-testid="stSidebar"] .cf-notif-badge')
    if not badge.count():
        return 0
    digits = "".join(ch for ch in badge.first.inner_text() if ch.isdigit())
    return int(digits) if digits else 0


def run(port, shot_dir):
    from playwright.sync_api import sync_playwright

    if shot_dir:
        os.makedirs(shot_dir, exist_ok=True)
    with AppUnderTest(REPO, port) as app, sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = ctx.new_page()
        page.goto(app.url, wait_until="networkidle")
        _settle(page, 1200)
        _login(page, app)
        _no_exception(page, "login")
        bell = _bell(page)
        check("bell is in the sidebar", bell.count() == 1)
        base = _count(page)          # الزرع نفسه بيتسجّل كتغييرات "من النظام"

        out = subprocess.run([os.path.join(REPO, "venv/bin/python"), "-c", _CHANGE], cwd=REPO,
                             capture_output=True, text=True,
                             env={**os.environ, "STUDIO_DB_PATH": os.path.join(app.tmp, "studio.db")})
        check("another user changed a scene's location", out.returncode == 0, out.stderr[-400:])
        scene_id, scene_no = out.stdout.split()

        t0, count = time.time(), base
        while time.time() - t0 < 45:
            count = _count(page)
            if count == base + 1:
                break
            page.wait_for_timeout(1000)
        check("bell counts it within 45s, no reload", count == base + 1,
              f"{base} → {count} after {time.time() - t0:.0f}s")

        _bell(page).click()
        _settle(page, 1200)
        if shot_dir:
            page.screenshot(path=os.path.join(shot_dir, "desktop-bell-click.png"))
        item = page.locator("a.cf-notif").filter(has_text=f"مشهد {scene_no}: اتغيّر المكان").first
        check("the change is listed in Arabic", item.count() == 1,
              page.locator(".cf-notif-list").first.inner_text()[:200] if page.locator(".cf-notif-list").count() else "no list")
        check("it is marked new", "cf-notif--new" in (item.get_attribute("class") or ""))
        href = item.get_attribute("href") or ""
        check("link points at that scene", f"tab=scenes&item={scene_id}" in href, href)
        if shot_dir:
            page.screenshot(path=os.path.join(shot_dir, "desktop-bell-open.png"))

        item.click()
        _settle(page, 2500)
        _no_exception(page, "following the notification")
        body = page.locator("body").inner_text()
        check("scenes tab shows only the changed scene", "بتعرض المشهد اللي اتغيّر بس" in body)
        opened = page.locator('[data-testid="stExpander"] details[open]').filter(has_text=f"مشهد {scene_no}")
        check("its edit form is open", opened.count() >= 1 or page.get_by_label("رقم المشهد").count() >= 1)
        check("item= is dropped from the address after use", "item=" not in page.url, page.url)
        page.keyboard.press("Escape")
        check("count cleared after opening the bell", _count(page) == 0, _count(page))
        page.get_by_role("button", name="اعرض كل المشاهد").click()
        _settle(page, 1500)
        check("'show all scenes' clears the focus",
              "بتعرض المشهد اللي اتغيّر بس" not in page.locator("body").inner_text())
        if shot_dir:
            page.screenshot(path=os.path.join(shot_dir, "desktop-after.png"))
        ctx.close()

        # التليفون
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        page = ctx.new_page()
        page.goto(app.url, wait_until="networkidle")
        _settle(page, 1200)
        _login(page, app)
        page.locator('[data-testid="stExpandSidebarButton"]').first.click()
        _settle(page, 1200)
        _bell(page).scroll_into_view_if_needed()
        if shot_dir:
            page.screenshot(path=os.path.join(shot_dir, "phone-sidebar.png"))
        box = _bell(page).bounding_box()
        check("phone: bell ≥44px", box and box["width"] >= 44 and box["height"] >= 44, box)
        _bell(page).click()
        _settle(page, 900)
        rows = page.locator("a.cf-notif")
        heights = [rows.nth(i).bounding_box()["height"] for i in range(min(rows.count(), 5))]
        check("phone: every row ≥44px", heights and min(heights) >= 44, heights)
        overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check("phone: no sideways scroll", overflow <= 0, f"{overflow}px")
        if shot_dir:
            page.screenshot(path=os.path.join(shot_dir, "phone-bell-open.png"))
        browser.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8612)
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    run(a.port, a.out)
    print("=" * 60)
    print(f"📊 {sum(results)}/{len(results)} checks passed")
    print("=" * 60)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
