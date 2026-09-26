"""🤖 زرار المساعد العائم — في متصفح حقيقي، بـ worker وهمي بيرد من غير claude.

    venv/bin/python tests/visual/assistant_ui.py --port 8990 [--out /tmp/shots/asst]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SPOOL = tempfile.mkdtemp(prefix="cf-asst-")
for _d in ("inbox", "status", "outbox"):
    os.makedirs(os.path.join(SPOOL, _d))
os.environ["CIMAFAST_ASSISTANT_SPOOL"] = SPOOL

from shots import REPO, AppUnderTest, _login, _settle  # noqa: E402

results = []
PROMPTS = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"{'✅' if cond else '❌'} {name}" + (f" → {detail}" if detail else ""))


def _fake_worker(stop):
    seen = set()
    while not stop.is_set():
        for name in os.listdir(os.path.join(SPOOL, "inbox")):
            if not name.endswith(".json") or name in seen:
                continue
            seen.add(name)
            jid = name[:-5]
            m = json.load(open(os.path.join(SPOOL, "inbox", name)))
            PROMPTS.append(m["prompt"])
            time.sleep(1.5)
            json.dump({"answer": "روح لتبويب «📝 المشاهد» ودوس «إضافة مشهد».\nGO: scenes"},
                      open(os.path.join(SPOOL, "outbox", f"{jid}.result.json"), "w"), ensure_ascii=False)
            json.dump({"state": "done"}, open(os.path.join(SPOOL, "status", f"{jid}.json"), "w"))
        time.sleep(0.3)


def run(port, shot_dir):
    from playwright.sync_api import sync_playwright
    if shot_dir:
        os.makedirs(shot_dir, exist_ok=True)
    stop = threading.Event()
    threading.Thread(target=_fake_worker, args=(stop,), daemon=True).start()
    with AppUnderTest(REPO, port) as app, sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()
        page.goto(app.url, wait_until="networkidle"); _settle(page, 1200); _login(page, app)
        btn = page.locator(".st-key-cf_assistant button").first
        check("assistant button is on screen", btn.count() == 1 and btn.is_visible())
        box = btn.bounding_box()
        check("…fixed in the bottom-left corner", box and box["x"] < 200 and box["y"] > 850, str(box))
        btn.click(); _settle(page, 1200)
        body = page.locator(".st-key-cf_asst_body").first
        check("opens with a welcome and ready questions",
              "مساعد سيما فاست" in body.inner_text() and body.get_by_role("button").count() >= 3)
        body.get_by_placeholder("اسأل عن أي حاجة في البرنامج…").fill("إزاي أضيف مشهد؟")
        body.locator("button").filter(has_text="➤").first.click()
        for _ in range(20):
            _settle(page, 700)
            if "إضافة مشهد" in body.inner_text():
                break
        check("answer shows in the chat", "روح لتبويب «📝 المشاهد»" in body.inner_text(), body.inner_text()[-300:])
        check("prompt carried the question and the screen",
              PROMPTS and "إزاي أضيف مشهد؟" in PROMPTS[-1] and "=== الدليل ===" in PROMPTS[-1])
        go = body.get_by_role("button").filter(has_text="افتح")
        check("answer offers an «افتح» button", go.count() == 1, str(go.count()))
        if shot_dir:
            page.screenshot(path=os.path.join(shot_dir, "chat.png"))
        go.first.click(); _settle(page, 2500)
        sel = page.locator('[role="tab"][aria-selected="true"]').first.inner_text()
        check("«افتح» lands on the scenes tab", "المشاهد" in sel, sel)
        check("assistant still on screen after navigating", page.locator(".st-key-cf_assistant button").first.is_visible())
        page.set_viewport_size({"width": 390, "height": 844}); _settle(page, 1200)
        mb = page.locator(".st-key-cf_assistant button").first.bounding_box()
        check("mobile: button visible inside the screen", mb and mb["x"] >= 0 and mb["y"] + mb["height"] <= 844, str(mb))
        b.close()
    stop.set()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8990)
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    run(a.port, a.out)
    print("=" * 60)
    print(f"📊 {sum(results)}/{len(results)} checks passed")
    print("=" * 60)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
