"""خانات الدخول مايكبّرش فيها الكيبورد أول حرف — في متصفح حقيقي.

البلاغ (2026-09-24): الموبايل بيكبّر أول حرف في اسم المستخدم (وساعات كلمة
السر) لوحده، وكلمة السر حساسة للحروف فالدخول بيفشل. اللي بيتختبر:
- خانة الاسم وكلمة السر عليهم autocapitalize=none وautocorrect=off
  وspellcheck=false، وفاضلين عليهم بعد محاولة فاشلة (Streamlit بيبني الخانات
  من جديد مع كل rerun).
- الرسالة بعد الفشل بتنبّه إن كلمة السر بتفرق بين الكبير والصغير.
- اسم المستخدم بـ Capital أول حرف بيدخل عادي.

    venv/bin/python tests/visual/login_nocaps_ui.py --port 8711
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from shots import REPO, AppUnderTest, _settle  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"{'✅' if cond else '❌'} {name}" + (f" → {detail}" if detail else ""))


ATTRS_JS = """() => ['div[class*=st-key-_login_username] input', 'div[class*=st-key-_login_password] input']
  .map(sel => { const i = document.querySelector(sel); return i && [i.getAttribute('autocapitalize'),
    i.getAttribute('autocorrect'), i.getAttribute('spellcheck'), i.getAttribute('autocomplete')]; })"""


def _attrs_ok(page, where):
    got = page.evaluate(ATTRS_JS)
    ok = (got[0] == ["none", "off", "false", "username"]
          and got[1] == ["none", "off", "false", "current-password"])
    check(f"no auto-caps on login fields ({where})", ok, str(got))


def run(port):
    from playwright.sync_api import sync_playwright
    with AppUnderTest(REPO, port) as app, sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_context(viewport={"width": 390, "height": 844}).new_page()
        page.goto(app.url, wait_until="networkidle")
        _settle(page, 1500)
        _attrs_ok(page, "first load")

        page.get_by_label("اسم المستخدم / Username").fill(app.username)
        page.get_by_label("كلمة السر / Password").fill("Wrong-" + app.password)
        page.get_by_role("button", name="دخول / Log in").click()
        _settle(page, 1800)
        body = page.locator("body").inner_text()
        check("wrong password explains case sensitivity", "بتفرق بين الحروف الكبيرة والصغيرة" in body)
        _attrs_ok(page, "after a failed attempt")

        page.get_by_label("اسم المستخدم / Username").fill(app.username.capitalize())
        page.get_by_label("كلمة السر / Password").fill(app.password)
        page.get_by_role("button", name="دخول / Log in").click()
        _settle(page, 2500)
        check("capitalised username still logs in",
              page.locator('[data-testid="stSidebar"]').count() > 0
              and not page.get_by_label("اسم المستخدم / Username").count())
        browser.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8711)
    a = ap.parse_args(argv)
    run(a.port)
    print("=" * 60)
    print(f"📊 {sum(results)}/{len(results)} checks passed")
    print("=" * 60)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
