"""ما بعد الإنتاج + شريط التقدّم حسب المرحلة — في متصفح حقيقي.

    venv/bin/python tests/visual/post_ui.py --port 8775 [--out /tmp/shots/post]
"""

from __future__ import annotations

import argparse
import os
import re
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
          errs.first.inner_text()[:300] if errs.count() else "")


def _bar(page):
    loc = page.locator(".cf-progress-text")
    text = loc.first.inner_text() if loc.count() else ""
    return text.replace("\u2066", "").replace("\u2069", "")


def _phase(page, label):
    page.locator("button").filter(has_text=label).first.click(); _settle(page, 1800)


def run(port, shot_dir):
    from playwright.sync_api import sync_playwright
    if shot_dir:
        os.makedirs(shot_dir, exist_ok=True)
    with AppUnderTest(REPO, port) as app, sync_playwright() as pw:
        db = os.path.join(app.tmp, "studio.db")
        b = pw.chromium.launch()
        page = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()
        page.goto(app.url, wait_until="networkidle"); _settle(page, 1200); _login(page, app)
        _no_exception(page, "login")
        check("pre-production bar shows the steps", "الخطوة" in _bar(page), _bar(page))

        _phase(page, "ما بعد الإنتاج")
        _no_exception(page, "post phase")
        tabs = [x.strip() for x in page.get_by_role("tab").all_inner_texts()]
        check("post phase shows post + crew + settings",
              len(tabs) == 3 and "ما بعد الإنتاج" in tabs[0] and "فريق العمل" in tabs[1], str(tabs))
        check("post bar starts at 0%", "ما بعد الإنتاج 0%" in _bar(page), _bar(page))
        check("bar has one segment per department",
              page.locator(".cf-progress-seg").count() == 7, str(page.locator(".cf-progress-seg").count()))
        exps = page.locator('[data-testid="stExpander"]')
        check("seven department cards", exps.count() == 7, str(exps.count()))

        edit = exps.filter(has_text="المونتاج").first
        edit.locator("summary").first.click(); _settle(page, 1800)
        _no_exception(page, "open editing card")
        edit = page.locator('[data-testid="stExpander"]').filter(has_text="المونتاج").first
        edit.locator('[data-testid="stSelectbox"]').first.click(); _settle(page, 500)
        page.get_by_role("option").filter(has_text="معتمد").first.click(); _settle(page, 500)
        edit.get_by_label("الاستوديو / المسؤول").fill("استوديو التجربة")
        edit.get_by_role("button").filter(has_text="حفظ").first.click(); _settle(page, 2200)
        _no_exception(page, "save editing")
        check("approving one of seven lifts the bar to 14%", "ما بعد الإنتاج 14%" in _bar(page), _bar(page))
        check("one department approved", "1 من 7" in _bar(page), _bar(page))
        check("a partially filled segment renders",
              page.locator(".cf-progress-seg--done").count() == 1)
        if shot_dir:
            page.screenshot(path=os.path.join(shot_dir, "post-saved.png"), full_page=True)
        edit = page.locator('[data-testid="stExpander"]').filter(has_text="المونتاج").first
        if not edit.get_by_placeholder("اكتب تعليق…").is_visible():
            edit.locator("summary").first.click(); _settle(page, 1800)
            edit = page.locator('[data-testid="stExpander"]').filter(has_text="المونتاج").first
        check("saved vendor is kept", edit.get_by_label("الاستوديو / المسؤول").input_value() == "استوديو التجربة")
        edit.get_by_placeholder("اكتب تعليق…").fill("النسخة الأولى وصلت")
        edit.get_by_role("button").filter(has_text="إضافة تعليق").first.click(); _settle(page, 2000)
        check("comment shows under the card", "النسخة الأولى وصلت" in page.locator("body").inner_text())
        if shot_dir:
            page.screenshot(path=os.path.join(shot_dir, "post.png"), full_page=True)

        # الإنتاج: 4 أيام تصوير، ونعلّم يوم منهم «اتصور»
        con = sqlite3.connect(db)
        pid = con.execute("SELECT id FROM projects WHERE name=?", ("عروسة البحر",)).fetchone()[0]
        for n in (1, 2, 3, 4):
            con.execute("INSERT INTO shooting_days (project_id, day_number) VALUES (?, ?)", (pid, n))
        con.commit(); con.close()
        _phase(page, re.compile(r"(?<!بعد )(?<!قبل )الإنتاج\s*$"))
        _no_exception(page, "production phase")
        check("production bar counts shooting days", "0 من 4" in _bar(page), _bar(page))
        page.locator('[data-testid="stCheckbox"]').filter(has_text=re.compile(r"يوم\W*1\W*$")).first.click(); _settle(page, 2200)
        _no_exception(page, "tick day 1")
        check("ticking a day moves the bar to 25%", "التصوير 25%" in _bar(page) and "1 من 4" in _bar(page),
              _bar(page))
        if shot_dir:
            page.screenshot(path=os.path.join(shot_dir, "prod.png"), full_page=True)

        _phase(page, "ما قبل الإنتاج")
        check("back in pre-production the bar shows steps again", "الخطوة" in _bar(page), _bar(page))
        b.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8775)
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    run(a.port, a.out)
    print("=" * 60)
    print(f"📊 {sum(results)}/{len(results)} checks passed")
    print("=" * 60)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
