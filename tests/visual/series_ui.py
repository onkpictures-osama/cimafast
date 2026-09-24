"""المسلسل والحلقات — في متصفح حقيقي، على قاعدة بيانات مزروعة مؤقتة.

طلب المالك (2026-09-24): النوع أول اختيار، المسلسل بعدد حلقات إجباري،
والرفع بيبقى "لأنهي حلقة". اللي بيتختبر:
- فورم المشروع الجديد: المسلسل من غير عدد حلقات مايتعملش، وبعدد بيتعمل
  وحلقاته معاه.
- تبويب الإضافة: شبكة الحلقات، ولو اسم الملف بيقول حلقة غير اللي اخترتها
  البرنامج بيسأل (مابيخمّنش) والزرار مقفول لحد ما تختار.
- المشاهد بتتسجل "2/1"، وفلتر الحلقات في تبويب المشاهد.

    venv/bin/python tests/visual/series_ui.py --port 8691 [--out /tmp/shots/series]
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from shots import REPO, SAMPLE_SCRIPT, AppUnderTest, _login, _settle  # noqa: E402

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
    _settle(page, 1200)


def stage(page, shot_dir):
    sb = page.locator('[data-testid="stSidebar"]')
    sb.get_by_text("إنشاء مشروع جديد").first.click()
    _settle(page, 800)
    sb.locator("[class*=st-key-new_proj_type] button").filter(has_text="مسلسل").first.click()
    _settle(page, 1000)
    body = sb.inner_text()
    check("series asks for episode count", "عدد الحلقات" in body)
    sb.get_by_label("اسم المشروع").fill("مسلسل الاختبار")
    sb.get_by_role("button", name="إنشاء المشروع").click()
    _settle(page, 1200)
    check("no series without episode count", "اكتب عدد حلقات المسلسل" in sb.inner_text())
    sb.locator("[class*=st-key-new_proj_episodes] input").fill("8")
    sb.locator("[class*=st-key-new_proj_episodes] input").press("Tab")
    _settle(page, 600)
    if shot_dir:
        sb.screenshot(path=os.path.join(shot_dir, "new-series-form.png"))
    sb.get_by_role("button", name="إنشاء المشروع").click()
    _settle(page, 2000)
    _no_exception(page, "create series")

    # المشروع الجديد: اختاره من القايمة
    sel = sb.locator('[data-testid="stSelectbox"]').filter(has_text="المشروع الحالي").first
    sel.locator("input").click()
    _settle(page, 400)
    page.get_by_role("option").filter(has_text="مسلسل الاختبار").first.click()
    _settle(page, 2000)

    _tab(page, "إضافة سيناريو")
    _no_exception(page, "import tab")
    grid = page.locator(".st-key-cf_import_episodes")
    check("episode grid shows 8 episodes", grid.count() and "0 من 8" in grid.inner_text().replace("⁦", "").replace("⁩", ""),
          grid.inner_text()[:200] if grid.count() else "no grid")
    if shot_dir and grid.count():
        grid.screenshot(path=os.path.join(shot_dir, "episode-grid.png"))

    tmp = tempfile.mkdtemp(prefix="cf-series-ui-")
    path = os.path.join(tmp, "الحلقة 2.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(SAMPLE_SCRIPT)
    page.locator('input[type="file"]').first.set_input_files(path)
    _settle(page, 1200)
    page.get_by_role("button").filter(has_text="تحليل الملف").first.click()
    _settle(page, 3000)
    _no_exception(page, "fast analysis")
    assign = page.locator(".st-key-cf_import_ep_assign")
    txt = assign.inner_text() if assign.count() else ""
    check("filename episode mismatch is asked, not guessed", "اسم الملف" in txt and "الحلقة 2" in txt, txt[:200])
    confirm = page.get_by_role("button").filter(has_text="تأكيد وإضافة كل المشاهد").first
    check("confirm disabled until the episode is chosen", confirm.is_disabled())
    if shot_dir and assign.count():
        assign.screenshot(path=os.path.join(shot_dir, "episode-conflict.png"))
    assign.get_by_text("الحلقة 2 (اللي في الملف)").first.click()
    _settle(page, 1200)
    confirm = page.get_by_role("button").filter(has_text="تأكيد وإضافة كل المشاهد").first
    check("confirm enabled after choosing", not confirm.is_disabled())
    confirm.click()
    _settle(page, 2500)
    _no_exception(page, "import into episode 2")

    _tab(page, "المشاهد")
    _no_exception(page, "scenes tab")
    heads = page.locator('[data-testid="stDataFrame"] [role="gridcell"]').all_inner_texts()
    check("scenes labelled 2/1, 2/2, 2/3", all(x in heads for x in ("2/1", "2/2", "2/3")), str(heads[:12]))
    filt = page.locator('[class*="st-key-scene_ep_filter_"]')
    check("episode filter shown", filt.count() and "كل الحلقات" in filt.inner_text())
    if shot_dir:
        page.screenshot(path=os.path.join(shot_dir, "scenes-tab.png"))


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
        # حساب التجربة بيتعمل بدور قسم (مابيعملش مشاريع) - هنا بس بنرقّيه
        # مدير شركة عشان نختبر فورم الإنشاء، في قاعدة التجربة المؤقتة.
        import sqlite3
        con = sqlite3.connect(os.path.join(app.tmp, "studio.db"))
        con.execute("UPDATE memberships SET role='admin' WHERE user_id="
                    "(SELECT id FROM users WHERE username=?)", (app.username,))
        con.commit()
        con.close()
        page.reload(wait_until="networkidle")
        _settle(page, 1500)
        if page.get_by_label("اسم المستخدم / Username").count():
            _login(page, app)
        _settle(page, 1500)
        try:
            stage(page, shot_dir)
        except Exception:
            page.screenshot(path="/tmp/series-fail.png")
            raise
        browser.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8691)
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    run(a.port, a.out)
    print("=" * 60)
    print(f"📊 {sum(results)}/{len(results)} checks passed")
    print("=" * 60)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
