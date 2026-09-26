"""مكتبة مواقع التصوير — في متصفح حقيقي: سكاوتنج موقع جديد، البحث بالمعنى،
واختيار موقع لمكان من كارته (مترتب بالأنسب) والرجوع للأماكن بالحجز.

    venv/bin/python tests/visual/venues_ui.py --port 8941 [--out /tmp/shots/venues]
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


def _main(page):
    return page.locator("section[data-testid=stMain]").inner_text()


def run(port, shot_dir):
    from playwright.sync_api import sync_playwright
    if shot_dir:
        os.makedirs(shot_dir, exist_ok=True)
    with AppUnderTest(REPO, port) as app, sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()
        page.goto(app.url, wait_until="networkidle"); _settle(page, 1200); _login(page, app)
        page.locator(".st-key-sb_lib_locations_lib button:visible").first.click(); _settle(page, 2000)
        _no_exception(page, "locations library")
        check("empty library explains how to start", "لسه مفيش مواقع" in _main(page))

        page.get_by_text("موقع جديد (سكاوتنج)").first.click(); _settle(page, 800)
        form = page.locator('[data-testid="stForm"]').filter(has_text="إضافة الموقع").first
        form.locator("input").nth(0).fill("فيلا الاختبار")
        form.locator('[class*="st-key-vnew_city"] input').fill("القاهرة")
        ms = form.locator('[class*="st-key-vnew_spaces"]')
        for space in ("أوضة نوم", "مطبخ"):
            inp = ms.locator('input[role="combobox"]').first
            inp.click(); inp.fill(space); _settle(page, 500)
            opts = page.get_by_role("option").filter(has_text=space)
            if opts.count():
                opts.first.click()
            else:
                inp.press("Enter")
            _settle(page, 500)
        page.keyboard.press("Escape")
        form.get_by_role("button").filter(has_text="إضافة الموقع").first.click(); _settle(page, 2200)
        _no_exception(page, "add venue")
        main = _main(page)
        check("new venue profile with its spaces", "فيلا الاختبار" in main and "المساحات اللي جواه" in main)

        # 📷 صور كتير: كل صورة = مساحة بمعاينتها في الجدول
        import sqlite3
        import tempfile
        from PIL import Image
        tmpd = tempfile.mkdtemp()
        paths = []
        for name, color in (("مطبخ.png", "orange"), ("IMG_2031.jpg", "teal"), ("living_room.jpg", "purple")):
            pth = os.path.join(tmpd, name)
            Image.new("RGB", (640, 420), color).save(pth)
            paths.append(pth)
        page.locator('[data-testid="stExpander"]').filter(has_text="تعديل الموقع ومساحاته").first.locator("summary").first.click()
        _settle(page, 1500)
        up = page.locator('[data-testid="stFileUploader"]').filter(has_text="صور المساحات").last
        up.locator('input[type="file"]').set_input_files(paths); _settle(page, 2500)
        page.get_by_role("button").filter(has_text="مساحة من الصور").first.click(); _settle(page, 3000)
        _no_exception(page, "add spaces from photos")
        db = os.path.join(app.tmp, "studio.db")
        con = sqlite3.connect(db)
        got = con.execute("SELECT s.name, s.photo_path FROM venue_spaces s JOIN venues v ON v.id=s.venue_id "
                          "WHERE v.name='فيلا الاختبار' AND s.photo_path IS NOT NULL ORDER BY s.id").fetchall()
        con.close()
        names = [g[0] for g in got]
        check("three photos → three spaces with photos", len(got) == 3, str(got))
        check("names come from meaningful file names, camera names become «مساحة N»",
              names[:1] == ["مطبخ"] and names[1].startswith("مساحة") and names[2] == "living room", str(names))
        check("photo files saved", all(os.path.exists(os.path.join(app.tree, g[1])) for g in got))
        if shot_dir:
            page.screenshot(path=os.path.join(shot_dir, "space-photos.png"), full_page=True)
        page.get_by_role("button").filter(has_text="رجوع لقايمة المواقع").first.click(); _settle(page, 1500)

        page.locator('[class*="st-key-venue_q"] input').fill("غرفة نوم")
        page.keyboard.press("Enter"); _settle(page, 1500)
        check("search by meaning: 'غرفة نوم' finds the villa's bedroom", "فيلا الاختبار" in _main(page))
        if shot_dir:
            page.screenshot(path=os.path.join(shot_dir, "library.png"), full_page=True)

        page.get_by_role("button").filter(has_text="رجوع للمشروع").first.click(); _settle(page, 1500)
        page.get_by_role("tab").filter(has_text="الأماكن").first.click(); _settle(page, 1500)
        card = page.locator('[data-testid="stExpander"]').filter(has_text="شقة نادية").first
        card.locator("summary").first.click(); _settle(page, 1800)
        page.get_by_role("button").filter(has_text="اختار من مكتبة المواقع").first.click(); _settle(page, 2200)
        _no_exception(page, "pick mode")
        main = _main(page)
        check("library opens in 'finding a location for' mode", "بتدوّر على موقع لـ" in main and "شقة نادية" in main)
        check("rows show how much of the place they cover", "بيغطي" in main)
        if shot_dir:
            page.screenshot(path=os.path.join(shot_dir, "pick.png"), full_page=True)
        page.locator('[class*="st-key-venue_row_"]').filter(has_text="فيلا الاختبار").get_by_role("button").first.click()
        _settle(page, 1800)
        page.get_by_role("button").filter(has_text="احجزه للمكان ده").first.click(); _settle(page, 2500)
        _no_exception(page, "book venue")
        sel = page.locator('[role="tab"][aria-selected="true"]').first.inner_text() if page.get_by_role("tab").count() else ""
        check("back on the locations tab after booking", "الأماكن" in sel, sel)
        head = page.locator('[data-testid="stExpander"]').filter(has_text="شقة نادية").first.locator("summary").inner_text()
        check("location card shows the booked venue", "فيلا الاختبار" in head, head)
        b.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8941)
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    run(a.port, a.out)
    print("=" * 60)
    print(f"📊 {sum(results)}/{len(results)} checks passed")
    print("=" * 60)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
