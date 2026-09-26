"""👤 حسابي — المشغّل بيعمل حساب، والشخص الجديد بيدخل ويغيّر كلمة السر. في متصفحين.

    venv/bin/python tests/visual/account_ui.py --port 8970 [--out /tmp/shots/acc]
"""

from __future__ import annotations

import argparse
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


def run(port, shot_dir):
    from playwright.sync_api import sync_playwright
    if shot_dir:
        os.makedirs(shot_dir, exist_ok=True)
    with AppUnderTest(REPO, port) as app, sync_playwright() as pw:
        db = os.path.join(app.tmp, "studio.db")
        b = pw.chromium.launch()
        boss = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()
        boss.goto(app.url, wait_until="networkidle"); _settle(boss, 1200); _login(boss, app)
        # حساب التجربة بيتعمل مع أول دخول - بعدها بس نخليه مشغّل
        con = sqlite3.connect(db)
        con.execute("UPDATE users SET is_operator=1 WHERE username=?", (app.username,))
        con.commit(); con.close()
        boss.reload(wait_until="networkidle"); _settle(boss, 1500)
        if boss.get_by_label("اسم المستخدم / Username").count():
            _login(boss, app); _settle(boss, 1500)
        if not _sidebar_open(boss):
            boss.locator('[data-testid="stExpandSidebarButton"]').first.click(); _settle(boss, 600)
        boss.locator(".st-key-sb_open_account button:visible").first.click(); _settle(boss, 3500)
        _no_exception(boss, "account page")
        body = boss.locator("section[data-testid=stMain]").inner_text()
        check("account page opens", "حسابي" in body and "اعمل حساب لحد" in body, body[:300])
        check("…and the sidebar closes", not _sidebar_open(boss))

        form = boss.locator('[data-testid="stForm"]').filter(has_text="اعمل الحساب").first
        form.locator("input").nth(0).fill("كريم محمود")
        form.locator("input").nth(1).fill("Karim.M")
        form.get_by_role("button").filter(has_text="اعمل الحساب").first.click(); _settle(boss, 2500)
        _no_exception(boss, "create account")
        codes = boss.locator('[data-testid="stCode"]').all_inner_texts()
        check("username and password shown", len(codes) >= 3 and codes[0].strip() == "karim.m", str(codes)[:200])
        password = codes[1].strip() if len(codes) > 1 else ""
        check("ready message has link, username and password",
              len(codes) >= 3 and "karim.m" in codes[2] and password in codes[2] and "http" in codes[2])
        form = boss.locator('[data-testid="stForm"]').filter(has_text="اعمل الحساب").first
        check("the form is empty again after creating", form.locator("input").nth(1).input_value() == "")
        check("WhatsApp button", boss.get_by_role("link").filter(has_text="واتساب").count() == 1)
        check("listed under accounts I created",
              "لسه بكلمة السر المؤقتة" in boss.locator("section[data-testid=stMain]").inner_text())
        if shot_dir:
            boss.screenshot(path=os.path.join(shot_dir, "created.png"), full_page=True)

        # الشخص الجديد
        guest = b.new_context(viewport={"width": 1280, "height": 900}).new_page()
        guest.goto(app.url, wait_until="networkidle"); _settle(guest, 1200)
        guest.get_by_label("اسم المستخدم / Username").fill("karim.m")
        guest.get_by_label("كلمة السر / Password").fill(password)
        guest.get_by_role("button", name="دخول / Log in").click(); _settle(guest, 2000)
        check("new person is asked to change the password", "غيّر كلمة السر" in guest.locator("body").inner_text())
        guest.get_by_label("كلمة السر المؤقتة / Temporary password").fill(password)
        guest.get_by_label("كلمة السر الجديدة / New password").fill("karim-secret-2026")
        guest.get_by_label("أعد كتابتها / Repeat it").fill("karim-secret-2026")
        guest.get_by_role("button", name="حفظ / Save").click(); _settle(guest, 2500)
        _no_exception(guest, "after first change")
        check("…then gets into the app", "غيّر كلمة السر / Change your password" not in guest.locator("body").inner_text())

        # يقدر يغيّرها تاني بعدين من «حسابي»
        if not _sidebar_open(guest):
            guest.locator('[data-testid="stExpandSidebarButton"]').first.click(); _settle(guest, 600)
        guest.locator(".st-key-sb_open_account button:visible").first.click(); _settle(guest, 2000)
        g = guest.locator("section[data-testid=stMain]")
        check("a normal account sees no create-account form", "اعمل حساب لحد" not in g.inner_text())
        guest.get_by_label("كلمة السر الحالية").fill("karim-secret-2026")
        guest.get_by_label("كلمة السر الجديدة (١٠ حروف على الأقل)").fill("karim-secret-2027")
        guest.get_by_label("أعد كتابتها").fill("karim-secret-2027")
        guest.get_by_role("button").filter(has_text="حفظ كلمة السر").first.click(); _settle(guest, 2000)
        check("password changed later from «حسابي»", "اتغيّرت كلمة السر" in g.inner_text())

        boss.reload(wait_until="networkidle"); _settle(boss, 1500)
        if boss.get_by_label("اسم المستخدم / Username").count():
            _login(boss, app); _settle(boss, 1500)
            boss.locator(".st-key-sb_open_account button:visible").first.click(); _settle(boss, 2000)
        check("operator sees the person switched to their own password",
              "✅ غيّر كلمة السر" in boss.locator("section[data-testid=stMain]").inner_text())
        b.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8970)
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    run(a.port, a.out)
    print("=" * 60)
    print(f"📊 {sum(results)}/{len(results)} checks passed")
    print("=" * 60)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
