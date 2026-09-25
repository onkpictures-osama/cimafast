"""طاولة التقطيع في تبويب اللقطات — في متصفح حقيقي.

    venv/bin/python tests/visual/decoupage_ui.py --port 8960 [--out /tmp/shots/dec]
"""

from __future__ import annotations

import argparse
import json
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


def _no_exception(page, where):
    errs = page.locator('[data-testid="stException"]')
    check(f"no exception on {where}", errs.count() == 0,
          errs.first.inner_text()[:400] if errs.count() else "")


def _q(db, sql, params=()):
    con = sqlite3.connect(db)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def run(port, shot_dir):
    from playwright.sync_api import sync_playwright
    if shot_dir:
        os.makedirs(shot_dir, exist_ok=True)
    with AppUnderTest(REPO, port) as app, sync_playwright() as pw:
        db = os.path.join(app.tmp, "studio.db")
        b = pw.chromium.launch()
        page = b.new_context(viewport={"width": 1500, "height": 1100}).new_page()
        page.goto(app.url, wait_until="networkidle"); _settle(page, 1200); _login(page, app)
        page.get_by_role("tab").filter(has_text="اللقطات").first.click(); _settle(page, 2500)
        _no_exception(page, "shots tab")

        rows = page.locator(".cf-sc-row")
        check("script shows the scene in blocks", rows.count() == 3, str(rows.count()))
        check("dialogue shows the speaker", page.locator(".cf-sc-who").filter(has_text="نادية").count() == 1)
        rows.nth(0).click(); rows.nth(1).click(); _settle(page, 300)
        page.locator(".cf-sc-bar button.go").first.click(); _settle(page, 2200)
        _no_exception(page, "pick blocks")
        form = page.locator('[data-testid="stForm"]').first
        action = form.locator("textarea").first.input_value()
        check("new-shot form is filled with the picked description", "البلكونة" in action, action)
        check("…and the picked dialogue line", "نادية: مفيش حد جه." in form.inner_text(), "")
        if shot_dir:
            page.screenshot(path=os.path.join(shot_dir, "script.png"), full_page=False)

        # الديكور: كنبة + كروكي، واحفظ كرسمة افتراضية
        page.locator(".cf-pl-bar button").filter(has_text="الديكور").first.click(); _settle(page, 300)
        page.locator(".cf-pl-bar button").filter(has_text="كنبة").first.click(); _settle(page, 300)
        svg = page.locator(".cf-pl svg").first
        box = svg.bounding_box()
        page.locator(".cf-pl-bar button").filter(has_text="كروكي").first.click(); _settle(page, 200)
        page.mouse.move(box["x"] + box["width"] * 0.3, box["y"] + box["height"] * 0.3)
        page.mouse.down()
        for k in range(1, 8):
            page.mouse.move(box["x"] + box["width"] * (0.3 + k * 0.03), box["y"] + box["height"] * 0.35, steps=2)
        page.mouse.up(); _settle(page, 300)
        check("unsaved marker shows", page.locator(".cf-pl-dirty").count() == 1)
        page.locator(".cf-pl-bar button.go").first.click(); _settle(page, 2500)
        _no_exception(page, "save decor")
        rows_db = _q(db, "SELECT variant_id, plan FROM location_plans")
        plan = json.loads(rows_db[0][1]) if rows_db else {}
        check("decor saved as the location's default plan", len(rows_db) == 1 and rows_db[0][0] == 0, str(rows_db)[:200])
        check("…with the sofa and the sketch", any(i["k"] == "sofa" for i in plan.get("items", []))
              and len(plan.get("strokes", [])) == 1, str(plan)[:200])
        check("header says it's the default plan", "الرسمة الافتراضية للمكان" in page.locator("body").inner_text())

        # الشخصيات والكاميرات: حط نادية وكاميرا لقطة 1، واسحب نادية
        page.locator(".cf-pl-bar button").filter(has_text="الشخصيات والكاميرات").first.click(); _settle(page, 300)
        page.locator(".cf-pl-bar button").filter(has_text="● نادية").first.click(); _settle(page, 300)
        page.locator(".cf-pl-bar button").filter(has_text="🎥 1").first.click(); _settle(page, 300)
        svg = page.locator(".cf-pl svg").first
        box = svg.bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        page.mouse.move(cx, cy); page.mouse.down()
        page.mouse.move(cx + 80, cy + 40, steps=8); page.mouse.up(); _settle(page, 300)
        page.locator(".cf-pl-bar button.go").first.click(); _settle(page, 2500)
        _no_exception(page, "save blocking")
        bl = _q(db, "SELECT data FROM scene_blocking")
        data = json.loads(bl[0][0]) if bl else {}
        chars, cams = data.get("chars", []), data.get("cams", [])
        check("character placed and moved from the centre",
              len(chars) == 1 and (chars[0]["x"] != 300 or chars[0]["y"] != 200), str(data)[:200])
        check("camera for shot 1 placed", len(cams) == 1, str(data)[:200])
        if shot_dir:
            page.screenshot(path=os.path.join(shot_dir, "plan.png"), full_page=False)
            page.locator(".cf-pl").first.screenshot(path=os.path.join(shot_dir, "plan-only.png"))

        # الموبايل: الطاولة تحت بعض ومفيش زحلقة أفقية
        page.set_viewport_size({"width": 390, "height": 844}); _settle(page, 1500)
        over = page.evaluate("() => { const m = document.querySelector('section[data-testid=stMain]');"
                             " return m.scrollWidth - m.clientWidth; }")
        check("mobile: no sideways scroll with the cutting table", over <= 2, f"{over}px")
        check("mobile: plan still visible", page.locator(".cf-pl svg").first.bounding_box()["width"] > 250)
        if shot_dir:
            page.locator(".cf-pl").first.screenshot(path=os.path.join(shot_dir, "plan-mobile.png"))
        page.set_viewport_size({"width": 1500, "height": 1100}); _settle(page, 800)

        # حالة تانية لنفس المكان بتشوف الرسمة الافتراضية
        loc = _q(db, "SELECT location_id FROM location_variants v JOIN scenes s ON s.location_variant_id=v.id "
                     "WHERE s.scene_number=1")[0][0]
        n_variants = _q(db, "SELECT COUNT(*) FROM location_variants WHERE location_id=?", (loc,))[0][0]
        check("seed location has its variants", n_variants >= 1, str(n_variants))
        b.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8960)
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    run(a.port, a.out)
    print("=" * 60)
    print(f"📊 {sum(results)}/{len(results)} checks passed")
    print("=" * 60)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
