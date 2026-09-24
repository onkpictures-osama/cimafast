"""الممثل جوه السيستم — في متصفح حقيقي، على قاعدة بيانات مزروعة مؤقتة.

البلاغ (2026-09-23): "فين إضافة الممثل للمشروع وربطه بشخصية". اللي بيتختبر:
- كارت الشخصية فيه قسم الكاستينج: ممثل/ة جديد/ة من الكارت نفسه → تعاقد.
- الكارت بعدها بيبان فيه رقم الكاست واسم الممثل/ة، والملخص فوق بيتحدّث.
- «رقّم الباقيين» بيرقّم كل الشخصيات، وجدول المشاهد فيه عمود أرقام الكاست.

    venv/bin/python tests/visual/casting_ui.py --port 8613 [--out /tmp/shots/casting]
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


def _tab(page, label):
    tab = page.get_by_role("tab").filter(has_text=label).first
    tab.scroll_into_view_if_needed()
    tab.click()
    _settle(page, 900)


def _char_card(page, name):
    return page.locator('[data-testid="stExpander"]').filter(has_text=name).filter(has_text="🎭").first


def stage(page, shot_dir):
    _tab(page, "الشخصيات")
    _no_exception(page, "characters tab")
    body = page.locator("body").inner_text()
    check("cast summary line shows", "دور اتعاقد له ممثل/ة" in body, body[:200])

    card = _char_card(page, "نادية")
    card.locator("summary").first.click()
    _settle(page, 1500)
    card = _char_card(page, "نادية")
    check("casting section inside the card", "الممثل/ة والكاستينج" in card.inner_text())

    form = card.locator('[data-testid="stForm"]').filter(has_text="اختار ممثل/ة").first
    form.locator('[data-testid="stSelectbox"]').first.click()
    _settle(page, 500)
    page.get_by_role("option").filter(has_text="ممثل/ة جديد/ة مش في الخزانة").first.click()
    _settle(page, 400)
    form.get_by_label("الاسم (لو جديد/ة)").fill("ممثلة اختبار")
    form.get_by_role("button", name="✅ تعاقد").click()
    _settle(page, 2000)
    _no_exception(page, "cast new actor from card")

    card = _char_card(page, "نادية")
    head = card.locator("summary").first.inner_text()
    check("card title shows cast number and actor", "#1" in head and "ممثلة اختبار" in head, head)
    if not card.locator("details").first.get_attribute("open") is not None:
        card.locator("summary").first.click()
        _settle(page, 1500)
        card = _char_card(page, "نادية")
    if shot_dir:
        card.screenshot(path=os.path.join(shot_dir, "character-casting.png"))

    page.get_by_role("button", name="#️⃣ رقّم الباقيين").first.click()
    _settle(page, 1800)
    _no_exception(page, "auto number")
    body = page.locator("body").inner_text()
    plain = re.sub("[\u200e\u200f\u2066-\u2069]", "", body)
    check("everyone numbered", "3/3 ليهم رقم في التفريغ" in plain,
          next((ln for ln in body.splitlines() if "ليهم رقم" in ln), ""))

    _tab(page, "المشاهد")
    _no_exception(page, "scenes tab")
    grid = page.locator('[data-testid="stDataFrame"]').first
    # الجدول بيترسم على canvas - العناوين في الجدول المخفي بتاع الـ accessibility
    # الجدول بيترسم متأخر شوية - من غير الانتظار ده الفحص كان بيقرا [] ساعات
    try:
        grid.locator('[role="columnheader"]').first.wait_for(timeout=8000)
    except Exception:
        pass
    heads = grid.locator('[role="columnheader"]').all_inner_texts() if grid.count() else []
    check("scene table has cast-number column", any("أرقام الكاست" in h for h in heads), str(heads))
    if shot_dir:
        grid.screenshot(path=os.path.join(shot_dir, "scene-table.png"))


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
        stage(page, shot_dir)
        browser.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8613)
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    run(a.port, a.out)
    print("=" * 60)
    print(f"📊 {sum(results)}/{len(results)} checks passed")
    print("=" * 60)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
