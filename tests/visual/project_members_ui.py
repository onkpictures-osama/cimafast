"""(أ) أعضاء لكل مشروع — قسم «أعضاء المشروع» في ⚙️ إعدادات المشروع، في متصفح.

اللي بيتختبر: المدير بيشوف القسم، المشروع القديم بيقول إنه مفتوح للكل، شيل
علامة عضو + حفظ = العضو ده مابقاش يشوف المشروع (متأكد من القاعدة نفسها)،
وفورم المشروع الجديد فيه "ضيف كل فريق مساحة العمل".

    venv/bin/python tests/visual/project_members_ui.py --port 8761
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from shots import REPO, AppUnderTest, _login, _settle  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"{'✅' if cond else '❌'} {name}" + (f" → {detail}" if detail else ""))


def _py(app, code):
    """كود بايثون على قاعدة التجربة نفسها (نفس الشجرة ونفس STUDIO_DB_PATH)."""
    out = subprocess.run([os.path.join(REPO, "venv/bin/python"), "-c", code], cwd=REPO, text=True,
                         capture_output=True, env={**os.environ, "PYTHONPATH": REPO,
                                                   "STUDIO_DB_PATH": os.path.join(app.tmp, "studio.db")})
    if out.returncode:
        raise SystemExit(out.stderr[-1500:])
    return out.stdout.strip()


def run(port):
    from playwright.sync_api import sync_playwright
    with AppUnderTest(REPO, port) as app, sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()
        page.goto(app.url, wait_until="networkidle"); _settle(page, 1200); _login(page, app)
        con = sqlite3.connect(os.path.join(app.tmp, "studio.db"))
        con.execute("UPDATE memberships SET role='admin' WHERE user_id=(SELECT id FROM users WHERE username=?)",
                    (app.username,))
        con.commit(); con.close()
        cid = _py(app, f"import accounts; print(accounts.companies_for('{app.username}')[0]['id'])")
        # باقة Creator = شغال لوحده ومفيش فريق (القسم مستخبي عن قصد) - هنا Studio
        con = sqlite3.connect(os.path.join(app.tmp, "studio.db"))
        con.execute("UPDATE companies SET subscription_tier='studio' WHERE id=?", (int(cid),))
        con.commit(); con.close()
        _py(app, f"import accounts; accounts.add_member('{app.username}', {cid}, 'dep_x', role='department')")
        pid = _py(app, f"import accounts; print(accounts.projects_for('{app.username}')[0]['id'])")
        check("before: dep_x sees the old project",
              _py(app, f"import accounts; print(accounts.can_access_project('dep_x', {pid}))") == "True")

        page.reload(wait_until="networkidle"); _settle(page, 1500)
        if page.get_by_label("اسم المستخدم / Username").count():
            _login(page, app)
        tab = page.get_by_role("tab").filter(has_text="إعدادات المشروع").first
        tab.scroll_into_view_if_needed(); tab.click(); _settle(page, 1800)
        body = page.locator("body").inner_text()
        check("members section shown to the manager", "أعضاء المشروع" in body)
        check("old project explained as open to everyone", "مفتوح لكل أعضاء مساحة العمل" in body)
        box = page.locator('[class*="st-key-pm_"]').filter(has_text="dep_x").first
        check("dep_x listed and ticked", box.count() > 0 and box.locator("input").first.is_checked())
        box.locator("label").first.click(); _settle(page, 800)
        page.get_by_role("button").filter(has_text="حفظ أعضاء المشروع").first.click(); _settle(page, 2000)
        errs = page.locator('[data-testid="stException"]').count()
        check("no exception on save", errs == 0)
        check("after: dep_x no longer sees the project",
              _py(app, f"import accounts; print(accounts.can_access_project('dep_x', {pid}))") == "False")
        check("after: the manager still does",
              _py(app, f"import accounts; print(accounts.can_access_project('{app.username}', {pid}))") == "True")
        page.screenshot(path="/tmp/project-members.png", full_page=False)

        sb = page.locator('[data-testid="stSidebar"]')
        sb.get_by_text("إنشاء مشروع جديد").first.click(); _settle(page, 800)
        check("new-project form offers 'add the whole team'", "ضيف كل فريق مساحة العمل للمشروع" in sb.inner_text())
        b.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8761)
    a = ap.parse_args(argv)
    run(a.port)
    print("=" * 60)
    print(f"📊 {sum(results)}/{len(results)} checks passed")
    print("=" * 60)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
