"""فريق العمل والدعوة — في متصفح حقيقي، بمتصفحين (مدير المشروع والمدعو).

    venv/bin/python tests/visual/team_ui.py --port 8831 [--out /tmp/shots/team]
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


def _sidebar_open(page):
    return page.evaluate("() => document.querySelector('section[data-testid=stSidebar]')"
                         "?.getAttribute('aria-expanded')") == "true"


def run(port, shot_dir):
    from playwright.sync_api import sync_playwright
    if shot_dir:
        os.makedirs(shot_dir, exist_ok=True)
    with AppUnderTest(REPO, port) as app, sync_playwright() as pw:
        b = pw.chromium.launch()
        boss = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()
        boss.goto(app.url, wait_until="networkidle"); _settle(boss, 1200); _login(boss, app)
        # زي سكريبت الترقية: صاحب المساحة مديرها، والباقة Studio
        con = sqlite3.connect(os.path.join(app.tmp, "studio.db"))
        con.execute("UPDATE memberships SET role='admin' WHERE user_id=(SELECT id FROM users WHERE username=?)",
                    (app.username,))
        con.execute("UPDATE companies SET subscription_tier='studio'")
        con.commit(); con.close()
        boss.reload(wait_until="networkidle"); _settle(boss, 1500)
        if boss.get_by_label("اسم المستخدم / Username").count():
            _login(boss, app); _settle(boss, 1500)
        _no_exception(boss, "manager login")

        sb = boss.locator('[data-testid="stSidebar"]').inner_text()
        check("no 'مساحة العمل' in the sidebar", "مساحة العمل" not in sb)
        check("sidebar shows the manager's role", "مدير المشروع" in sb)
        check("sidebar has the crew button", "فريق العمل" in sb)
        boss.locator(".st-key-sb_open_team button:visible").first.click(); _settle(boss, 2200)
        sel = boss.locator("section[data-testid=stMain] h3").first.inner_text()
        check("crew button opens the crew page", "فريق العمل" in sel and boss.get_by_role("tab").count() == 0, sel)
        check("…and closes the sidebar", not _sidebar_open(boss))
        _no_exception(boss, "crew page")

        form = boss.locator('[data-testid="stForm"]').filter(has_text="الشغلانة في المشروع").first
        form.locator("input").nth(0).fill("هبة")
        form.locator("input").nth(1).fill("01000000000")
        form.locator('[data-testid="stSelectbox"] button[aria-label="Open"]').first.click(); _settle(boss, 500)
        boss.get_by_role("option").filter(has_text="مصمم الملابس").first.click(); _settle(boss, 400)
        form.get_by_role("button").filter(has_text="أضف").first.click(); _settle(boss, 2200)
        _no_exception(boss, "create invite")
        code = boss.locator('[data-testid="stCode"]').first.inner_text() if boss.locator('[data-testid="stCode"]').count() else ""
        m = re.search(r"https?://\S+\?invite=\S+", code)
        check("invite link shown", bool(m), code[:120])
        check("WhatsApp share offered", boss.get_by_text("ابعته واتساب").count() > 0)
        if shot_dir:
            boss.screenshot(path=os.path.join(shot_dir, "crew-invite.png"), full_page=True)

        guest = b.new_context(viewport={"width": 390, "height": 844}).new_page()
        guest.goto(m.group(0), wait_until="networkidle"); _settle(guest, 1800)
        body = guest.locator("body").inner_text()
        check("invite link explains who invites to which project", "بيدعوك لفريق عمل مشروع" in body
              and "عروسة البحر" in body and "مصمم الملابس" in body)
        if shot_dir:
            guest.screenshot(path=os.path.join(shot_dir, "invite-landing.png"), full_page=True)
        f = guest.locator('[data-testid="stForm"]').first
        inputs = f.locator("input")
        inputs.nth(1).fill("heba")
        inputs.nth(2).fill("a-long-password")
        inputs.nth(3).fill("a-long-password")
        f.get_by_role("button").filter(has_text="إنشاء الحساب").first.click(); _settle(guest, 3000)
        _no_exception(guest, "register from invite")
        title = guest.locator("h2").filter(has_text="عروسة البحر").count()
        check("new member lands on the project", title > 0)
        guest.locator('[data-testid="stExpandSidebarButton"]').first.click(); _settle(guest, 900)
        gsb = guest.locator('[data-testid="stSidebar"]').inner_text()
        check("new member's role shows their job", "مصمم الملابس" in gsb, gsb[:200])

        boss.reload(wait_until="networkidle"); _settle(boss, 2000)
        if boss.get_by_label("اسم المستخدم / Username").count():
            _login(boss, app); _settle(boss, 1500)
        boss.locator('[data-testid="stExpandSidebarButton"]').first.click() if not _sidebar_open(boss) else None
        _settle(boss, 800)
        boss.locator(".st-key-sb_open_team button:visible").first.click(); _settle(boss, 2200)
        crew = boss.locator("section[data-testid=stMain]").inner_text()
        check("manager sees the new member on the crew", "@heba" in crew and "مصمم الملابس" in crew)
        b.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8831)
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    run(a.port, a.out)
    print("=" * 60)
    print(f"📊 {sum(results)}/{len(results)} checks passed")
    print("=" * 60)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
