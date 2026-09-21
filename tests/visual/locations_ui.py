"""بيتأكد من شكل تبويب الأماكن في متصفح حقيقي.

اللي بيتختبر هنا طلبات المالك بالظبط (2026-09-21):
- كل مكان ليه صورة: رفع، كاميرا، أو توليد بالذكاء الاصطناعي.
- زرار «➕ إضافة حالة» تحت كل مكان، والفورم مقفول لحد ما يتداس عليه.
- الحالة مفيهاش داخلي/خارجي ولا نهار/ليل — دي بتاعة المشهد.

التوليد نفسه مش بيتنادى هنا (بيكلف فلوس) — بنتأكد إن الزرار موجود بس.

    venv/bin/python tests/visual/locations_ui.py --port 8605
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from shots import REPO, AppUnderTest, _login, _settle  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"{'✅' if cond else '❌'} {name}" + (f" → {detail}" if detail else ""))


def _tiny_png(path):
    raw = b"\x00\xff\x00\x00" * 1
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    open(path, "wb").write(png)


def run(port, shot_dir):
    from playwright.sync_api import sync_playwright

    with AppUnderTest(REPO, port) as app, sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_context(viewport={"width": 1440, "height": 1000}).new_page()
        page.goto(app.url, wait_until="networkidle")
        _settle(page, 1200)
        _login(page, app)
        page.get_by_role("tab").filter(has_text="الأماكن").first.click()
        _settle(page, 900)

        body = page.locator("body").inner_text()
        check("no always-open add-variant panel at the top",
              "اختر مكان لإضافة حالة" not in body)
        check("add-variant form hidden before expanding", "حالة جديدة لـ" not in body)

        page.get_by_text("شقة نادية - الدقي").first.click()
        _settle(page, 900)
        body = page.locator("body").inner_text()
        check("location image section shown", "صورة المكان" in body)
        for src in ("رفع من الجهاز", "الكاميرا", "توليد بالذكاء الاصطناعي"):
            check(f"image source offered: {src}", src in body)
        check("add-variant button visible", page.get_by_role("button", name="➕ إضافة حالة").count() == 1)
        check("add-variant form still closed", "حالة جديدة لـ" not in body)

        expander = page.locator('[data-testid="stExpander"]').filter(has_text="شقة نادية - الدقي").first
        # بندوّر على لابلات الخانات بس: الشرح نفسه بيذكر داخلي/خارجي عشان يقول إنها مش هنا
        labels = expander.locator('[data-testid="stWidgetLabel"]').all_inner_texts()
        check("no INT/EXT field inside the location", not any("داخلي" in x for x in labels), str(labels))
        check("no Day/Night field inside the location", not any("نهار" in x or "ليل" in x for x in labels))

        # upload a location image
        png = os.path.join(tempfile.mkdtemp(), "loc.png")
        _tiny_png(png)
        expander.locator('input[type="file"]').first.set_input_files(png)
        _settle(page, 1200)
        page.get_by_role("button", name="💾 حفظ الصورة").first.click()
        _settle(page, 1500)
        expander = page.locator('[data-testid="stExpander"]').filter(has_text="شقة نادية - الدقي").first
        check("uploaded image is displayed",
              expander.locator('[data-testid="stImage"] img, [data-testid="stImageContainer"] img').count() >= 1)
        check("remove-image button appears", expander.get_by_role("button", name="🗑️ شيل الصورة").count() >= 1)

        # the generate path shows its button without calling the API
        expander.get_by_text("توليد بالذكاء الاصطناعي").first.click()
        _settle(page, 800)
        check("generate button appears when AI is chosen",
              page.get_by_role("button", name="✨ ولّد صورة").count() >= 1)

        # open the add-variant form
        page.get_by_role("button", name="➕ إضافة حالة").first.click()
        _settle(page, 900)
        expander = page.locator('[data-testid="stExpander"]').filter(has_text="شقة نادية - الدقي").first
        form = expander.locator('[data-testid="stForm"]').filter(has_text="حالة جديدة لـ").first
        check("form opens after clicking", form.count() == 1)
        ftxt = form.inner_text()
        check("new-variant form has no INT/EXT", "داخلي" not in ftxt and "خارجي" not in ftxt)
        check("new-variant form has no Day/Night", "نهار" not in ftxt.replace("مثال", "") or "ليل" not in ftxt)
        form.get_by_label("حالة المكان").fill("بعد الحريق")
        form.get_by_label("وصف التغييرات الخاصة بهذه الحالة").fill("الجدران سودا")
        form.get_by_role("button", name="إضافة الحالة").click()
        _settle(page, 1500)
        body = page.locator("body").inner_text()
        check("form closes after adding", "حالة جديدة لـ" not in body)
        expander = page.locator('[data-testid="stExpander"]').filter(has_text="شقة نادية - الدقي").first
        vals = expander.locator('input[type="text"]').evaluate_all("els => els.map(e => e.value)")
        check("new variant saved and listed", "بعد الحريق" in vals, str(vals[:6]))

        # cancel path
        page.get_by_role("button", name="➕ إضافة حالة").first.click()
        _settle(page, 800)
        page.get_by_role("button", name="إلغاء").first.click()
        _settle(page, 800)
        check("cancel closes the form", "حالة جديدة لـ" not in page.locator("body").inner_text())

        if shot_dir:
            os.makedirs(shot_dir, exist_ok=True)
            page.screenshot(path=os.path.join(shot_dir, "locations.png"), full_page=True)
            print("📸", os.path.join(shot_dir, "locations.png"))
        browser.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8605)
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    run(a.port, a.out)
    print("=" * 60)
    print(f"📊 {sum(results)}/{len(results)} checks passed")
    print("=" * 60)
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
