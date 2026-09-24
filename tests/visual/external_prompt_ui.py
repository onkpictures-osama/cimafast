"""بيتأكد إن قسم «التحليل خارج البرنامج» بيترسم فعلًا في المتصفح.

ليه المتصفح مش اختبار نصي: زرار النسخ مبني على ‎st.components.v1.html‎، يعني
بيتحط جوه iframe. الـ iframe ده ملهوش صلاحية ‎clipboard-write‎، فالـ API
الحديثة بترفض جواه — الحاجة الوحيدة اللي بتثبت إن خط الرجعة
(‎execCommand‎) شغال فعلًا هي إننا نضغط الزرار في متصفح حقيقي ونشوف
اللابل بيتغيّر لـ «اتنسخ» ولا لأ.

    venv/bin/python tests/visual/external_prompt_ui.py --port 8597

بيرجّع 1 لو أي فحص سقط.
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import tempfile  # noqa: E402

from shots import REPO, SAMPLE_SCRIPT, AppUnderTest, _click_tab, _login, _settle  # noqa: E402

EXT_BUTTON = "التحليل خارج CimaFast"
COPY_LABEL = "نسخ البرومبت"
COPIED_LABEL = "اتنسخ"
DOWNLOAD_LABEL = "نزّل البرومبت كملف"

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"{'✅' if cond else '❌'} {name}" + (f" → {detail}" if detail else ""))


def run(port, shot_dir):
    from playwright.sync_api import sync_playwright

    with AppUnderTest(REPO, port) as app, sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.goto(app.url, wait_until="networkidle")
        _settle(page, 1200)
        _login(page, app)
        _click_tab(page, "import", "ar")

        # المالك 2026-09-24: مفيش شرح التحليل الخارجي قبل الرفع - تلات طرق بعد الرفع
        before = page.locator("section[data-testid=stMain]").inner_text()
        check("nothing about external analysis before the upload",
              EXT_BUTTON not in before and "script.json" not in before)
        tmp = tempfile.mkdtemp(prefix="cf-ext-")
        path = os.path.join(tmp, "script.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(SAMPLE_SCRIPT)
        page.locator('input[type="file"]').first.set_input_files(path)
        _settle(page, 1500)
        main = page.locator("section[data-testid=stMain]").inner_text()
        check("three options after the upload",
              all(x in main for x in ("تحليل الملف", "CimaFast AI Inspector", EXT_BUTTON)), main[-300:])
        page.get_by_role("button").filter(has_text=EXT_BUTTON).first.click()
        _settle(page, 1200)

        body = page.locator("body").inner_text()
        check("the old wording is gone", "مبيحللوش كويس" not in body)
        check("the steps are shown", "script.json" in body)
        check("the download fallback is offered", DOWNLOAD_LABEL in body)

        frame = None
        for f in page.frames:
            try:
                if f.locator("#cf-copy").count() > 0:
                    frame = f
                    break
            except Exception:
                continue
        check("the copy button rendered inside its component", frame is not None)

        if frame is not None:
            btn = frame.locator("#cf-copy")
            check("the button carries the copy label", COPY_LABEL in btn.inner_text(),
                  btn.inner_text().strip())
            btn.click()
            page.wait_for_timeout(700)
            after = btn.inner_text().strip()
            check("clicking it actually copies (label flips, no ⚠️)",
                  COPIED_LABEL in after, after)

        if shot_dir:
            os.makedirs(shot_dir, exist_ok=True)
            path = os.path.join(shot_dir, "external_prompt.png")
            page.screenshot(path=path, full_page=True, animations="disabled")
            print(f"📸 {path}")

        ctx.close()
        browser.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description="فحص قسم التحليل خارج البرنامج")
    ap.add_argument("--port", type=int, default=8597)
    ap.add_argument("--out", default="", help="مجلد لحفظ لقطة للشاشة")
    args = ap.parse_args(argv)
    run(args.port, args.out)
    print("=" * 60)
    print(f"📊 {sum(results)}/{len(results)} checks passed")
    print("=" * 60)
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
