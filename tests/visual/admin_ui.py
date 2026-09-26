"""🛡️ إدارة الحسابات — في متصفح حقيقي: قفل ميزة، إيقاف (والشخص بيشوف السبب)، تشغيل، نقل، حذف.

    venv/bin/python tests/visual/admin_ui.py --port 8995 [--out /tmp/shots/adm]
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


def _sidebar_open(page):
    return page.evaluate("() => { const s = document.querySelector('[data-testid=stSidebar]');"
                         " return !!s && s.getAttribute('aria-expanded') === 'true'; }")


def _q(db, sql, params=()):
    con = sqlite3.connect(db)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def _main(page):
    return page.locator("section[data-testid=stMain]")


def _pick(page, username):
    sel = _main(page).locator('[data-testid="stSelectbox"]').filter(has_text="أو اختار الحساب").first
    sel.locator('button[aria-label="Open"], input').first.click(); _settle(page, 500)
    page.get_by_role("option").filter(has_text=username).first.click(); _settle(page, 1800)


def _tab(page, label):
    page.get_by_role("tab").filter(has_text=label).first.click(); _settle(page, 800)


def _guest_login(b, app, username, password):
    g = b.new_context(viewport={"width": 1200, "height": 900}).new_page()
    g.goto(app.url, wait_until="networkidle"); _settle(g, 1200)
    g.get_by_label("اسم المستخدم / Username").fill(username)
    g.get_by_label("كلمة السر / Password").fill(password)
    g.get_by_role("button", name="دخول / Log in").click(); _settle(g, 2000)
    text = g.locator("body").inner_text()
    g.context.close()
    return text


def run(port, shot_dir):
    from playwright.sync_api import sync_playwright
    if shot_dir:
        os.makedirs(shot_dir, exist_ok=True)
    with AppUnderTest(REPO, port) as app, sync_playwright() as pw:
        db = os.path.join(app.tmp, "studio.db")
        b = pw.chromium.launch()
        page = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()
        page.goto(app.url, wait_until="networkidle"); _settle(page, 1200); _login(page, app)
        con = sqlite3.connect(db); con.execute("UPDATE users SET is_operator=1 WHERE username=?", (app.username,))
        con.commit(); con.close()
        page.reload(wait_until="networkidle"); _settle(page, 1500)
        if page.get_by_label("اسم المستخدم / Username").count():
            _login(page, app); _settle(page, 1500)
        if not _sidebar_open(page):
            page.locator('[data-testid="stExpandSidebarButton"]').first.click(); _settle(page, 600)
        page.locator(".st-key-sb_open_account button:visible").first.click(); _settle(page, 3000)

        # حساب للتجربة من «حسابي»
        form = page.locator('[data-testid="stForm"]').filter(has_text="اعمل الحساب").first
        form.locator("input").nth(0).fill("شخص تجربة")
        form.locator("input").nth(1).fill("test.person")
        form.get_by_role("button").filter(has_text="اعمل الحساب").first.click(); _settle(page, 2500)
        password = page.locator('[data-testid="stCode"]').all_inner_texts()[1].strip()

        page.get_by_role("button").filter(has_text="إدارة كل الحسابات").first.click(); _settle(page, 3000)
        _no_exception(page, "admin page")
        body = _main(page).inner_text()
        check("admin page shows the accounts overview", "إدارة الحسابات" in body and "ماداخلوش ولا مرة" in body
              and _main(page).locator('[data-testid="stDataFrame"]').count() == 1)
        _pick(page, "test.person")
        _no_exception(page, "pick account")
        check("account detail with tabs", page.get_by_role("tab").filter(has_text="نقل ودمج").count() == 1)
        if shot_dir:
            page.screenshot(path=os.path.join(shot_dir, "admin.png"), full_page=True)

        _tab(page, "الوصول والمزايا")
        page.locator('[data-testid="stCheckbox"]').filter(has_text="تصدير التقارير").first.click()
        page.get_by_role("button").filter(has_text="حفظ المزايا").first.click(); _settle(page, 2200)
        feats = _q(db, "SELECT disabled_features FROM users WHERE username='test.person'")[0][0]
        check("exports locked for that account", json.loads(feats or "[]") == ["exports"], feats)

        _pick(page, "test.person"); _tab(page, "الوصول والمزايا")
        page.get_by_role("button").filter(has_text="أوقف الحساب").first.click(); _settle(page, 2200)
        check("suspended in the database", _q(db, "SELECT active FROM users WHERE username='test.person'")[0][0] == 0)
        text = _guest_login(b, app, "test.person", password)
        check("suspended person is told why at login", "موقوف" in text, text[-200:])

        _pick(page, "test.person"); _tab(page, "الوصول والمزايا")
        page.get_by_role("button").filter(has_text="شغّل الحساب تاني").first.click(); _settle(page, 2200)
        text = _guest_login(b, app, "test.person", password)
        check("after reactivation the person gets in (password change screen)", "غيّر كلمة السر" in text, text[-200:])

        _pick(page, "test.person"); _tab(page, "نقل ودمج")
        tf = page.locator('[data-testid="stForm"]').filter(has_text="لمين؟").first
        tf.locator('[data-testid="stRadio"] label').filter(has_text="حساب جديد").first.click()
        tf.locator("input[type=text]").nth(0).fill("شخص جديد")
        tf.locator("input[type=text]").nth(1).fill("new.person")
        tf.get_by_role("button").filter(has_text="انقل").first.click(); _settle(page, 3000)
        _no_exception(page, "transfer")
        check("transfer to a brand-new account creates it", _q(db, "SELECT COUNT(*) FROM users WHERE username='new.person'")[0][0] == 1)
        check("new account's password shown", "كلمة سر الحساب الجديد" in _main(page).inner_text())
        backups = os.listdir(os.path.join(app.tmp, "admin-backups")) if os.path.isdir(os.path.join(app.tmp, "admin-backups")) else []
        check("a database backup was taken before the transfer", any("transfer-test.person" in f for f in backups), str(backups))

        _pick(page, "test.person"); _tab(page, "حذف")
        dform = page.locator('[data-testid="stForm"]').filter(has_text="للتأكيد").first
        dform.locator("input").first.fill("test.person")
        dform.get_by_role("button").filter(has_text="احذف الحساب").first.click(); _settle(page, 2500)
        _no_exception(page, "delete")
        check("account deleted", _q(db, "SELECT COUNT(*) FROM users WHERE username='test.person'")[0][0] == 0)
        b.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8995)
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    run(a.port, a.out)
    print("=" * 60)
    print(f"📊 {sum(results)}/{len(results)} checks passed")
    print("=" * 60)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
