"""فحص شاشة الموبايل في متصفح حقيقي (390×844) — بالقياس مش بالنظر.

الخطة في ‎MOBILE-REDESIGN-PLAN.md‎. الملف ده هو الدليل على المراحل 1 و2 و3:

  1. **التنقل**: مفيش تبويب واقع بره الشاشة، والخط اللي تحت التبويب المفتوح
     (‎.react-aria-SelectionIndicator‎) لسه مظبوط بعد ما خلّينا الشريط يلفّ.
     دي بالظبط المخاطرة اللي الخطة حذّرت منها، فبتتقاس هنا تبويب تبويب.
  2. **الشريط الجانبي**: على عرض التليفون Streamlit بيقفله ويحوّله طبقة فوق
     المحتوى. بنتأكد إنه فعلاً كده، وإن زرار فتحه مساحته ≥44px، وإنه لما
     يتفتح بيغطي المحتوى مش بيزقّه.
  3. **الرصّ في عمود واحد**: أي عمودين في نفس الصف = التخطيط لسه مش مرصوص.
  4. **مساحات اللمس**: كل زرار/حقل ≥44px.
  5. **مفيش زحلقة أفقية** في الصفحة نفسها، وبنسجّل الحاجات اللي CSS الصفحة
     مش بيوصلها أصلاً (‎stDataFrame‎ و‎iframe‎) عشان القرار يبقى مبني على
     قياس مش على تخمين.

    venv/bin/python tests/visual/mobile_ui.py --port 8607
    venv/bin/python tests/visual/mobile_ui.py --port 8607 --theme glass
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from shots import REPO, VIEWPORTS, AppUnderTest, _click_tab, _login, _settle  # noqa: E402

PHONE = VIEWPORTS["phone"]
TOUCH = 44
# سماحية بكسل واحد: قياسات المتصفح كسور عشرية
EPS = 1.0

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  →  {detail}" if detail else ""),
          flush=True)


# --------------------------------------------------------------------------
# قياسات بتتعمل جوه المتصفح
# --------------------------------------------------------------------------

JS_TABS = r"""() => {
    const vw = window.innerWidth;
    const list = document.querySelector('.stTabs [role="tablist"]');
    if (!list) return {none: true};
    const tabs = [...list.querySelectorAll('[role="tab"]')];
    return {
        count: tabs.length,
        listHeight: Math.round(list.getBoundingClientRect().height),
        scrollOverflow: Math.round(list.scrollWidth - list.clientWidth),
        offscreen: tabs.filter(t => {
            const r = t.getBoundingClientRect();
            return r.left < -1 || r.right > vw + 1;
        }).map(t => t.innerText.trim()),
        short: tabs.filter(t => t.getBoundingClientRect().height < 44 - 0.5)
                   .map(t => t.innerText.trim()),
    };
}"""

JS_INDICATOR = r"""() => {
    const sel = document.querySelector('.stTabs [role="tab"][aria-selected="true"]');
    if (!sel) return {err: 'no selected tab'};
    const ind = sel.querySelector('.react-aria-SelectionIndicator')
             || document.querySelector('.stTabs .react-aria-SelectionIndicator');
    if (!ind) return {err: 'no indicator'};
    const a = ind.getBoundingClientRect(), b = sel.getBoundingClientRect();
    return {tab: sel.innerText.trim(),
            dx: +(a.left - b.left).toFixed(1),
            dw: +(a.width - b.width).toFixed(1),
            dy: +(a.bottom - b.bottom).toFixed(1),
            inside: sel.contains(ind)};
}"""

JS_SCREEN = r"""() => {
    const vw = window.innerWidth;
    const main = document.querySelector('[data-testid="stMain"]') || document.body;
    const cols = [...main.querySelectorAll('[data-testid="stColumn"]')]
        .filter(c => c.getBoundingClientRect().width > 0 && c.getBoundingClientRect().height > 0);
    // عمودين في نفس الصف = مش مرصوص. بنقارن مواضع الـ top.
    const rows = {};
    for (const c of cols) {
        const r = c.getBoundingClientRect();
        const k = Math.round(r.top);
        (rows[k] = rows[k] || []).push(Math.round(r.width));
    }
    const shared = Object.entries(rows).filter(([, w]) => w.length > 1);
    const touch = [...main.querySelectorAll(
        '.stButton button, .stDownloadButton button, .stFormSubmitButton button,' +
        ' [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,' +
        ' [data-testid="stRadio"] [role="radiogroup"] label')]
        .filter(e => {const r = e.getBoundingClientRect(); return r.height > 0 && r.height < 43.5;})
        .map(e => (e.innerText || e.placeholder || e.type) + ':' + Math.round(e.getBoundingClientRect().height));
    const wide = [...main.querySelectorAll('*')].filter(e => {
        const r = e.getBoundingClientRect();
        return r.width > vw + 1 && r.height > 0;
    });
    return {
        pageOverflow: Math.round(document.documentElement.scrollWidth - vw),
        sharedRows: shared.map(([t, w]) => ({top: +t, widths: w})),
        smallTouch: touch,
        wideCount: wide.length,
        wideKinds: [...new Set(wide.map(e => e.getAttribute('data-testid') || e.tagName.toLowerCase()))],
        frames: [...main.querySelectorAll('iframe')].map(f => ({
            w: Math.round(f.getBoundingClientRect().width),
            title: f.title || '',
        })),
        // الصور بمقاس ثابت بالبكسل متعدّيش عرض العمود
        wideImages: [...main.querySelectorAll('[data-testid="stImage"] img')]
            .filter(i => {
                const p = i.closest('[data-testid="stVerticalBlock"]') || main;
                return i.getBoundingClientRect().width > p.getBoundingClientRect().width + 1;
            }).length,
        dataframes: [...main.querySelectorAll('[data-testid="stDataFrame"]')].map(d => ({
            w: Math.round(d.getBoundingClientRect().width),
            sw: Math.round((d.querySelector('[class*="dvn-scroller"]') || d).scrollWidth),
            // علامة إن فيه أعمدة مخبّية: التدرّج على حرف الجدول
            fade: getComputedStyle(d, '::after').backgroundImage !== 'none',
        })),
    };
}"""

JS_SIDEBAR = r"""() => {
    const sb = document.querySelector('[data-testid="stSidebar"]');
    // في Streamlit 1.64 زرار فتح الشريط اسمه stExpandSidebarButton
    const ctrl = document.querySelector('[data-testid="stExpandSidebarButton"]');
    const main = document.querySelector('[data-testid="stMain"]');
    const r = sb ? sb.getBoundingClientRect() : null;
    const cr = ctrl ? ctrl.getBoundingClientRect() : null;
    return {
        present: !!sb,
        visible: !!(r && r.width > 0 && r.height > 0),
        ariaExpanded: sb ? sb.getAttribute('aria-expanded') : null,
        width: r ? Math.round(r.width) : 0,
        ctrl: cr ? {w: Math.round(cr.width), h: Math.round(cr.height)} : null,
        mainLeft: main ? Math.round(main.getBoundingClientRect().left) : null,
        mainWidth: main ? Math.round(main.getBoundingClientRect().width) : null,
    };
}"""


def _run_lang(page, app, lang, out_dir, shots_on):
    print(f"\n=== {lang} @ {PHONE[0]}x{PHONE[1]} ===", flush=True)

    # التنقل بين التبويبات
    tabs = page.evaluate(JS_TABS)
    check(f"[{lang}] شريط التبويبات موجود", not tabs.get("none"), json.dumps(tabs, ensure_ascii=False))
    if tabs.get("none"):
        return
    check(f"[{lang}] مفيش تبويب بره الشاشة", not tabs["offscreen"],
          f"{tabs['count']} تبويب · ارتفاع الشريط {tabs['listHeight']}px · "
          f"بره: {tabs['offscreen'] or 'ولا واحد'}")
    check(f"[{lang}] الشريط مش بيزحلق أفقي", tabs["scrollOverflow"] <= 0,
          f"scrollWidth-clientWidth = {tabs['scrollOverflow']}px")
    check(f"[{lang}] كل تبويب ≥{TOUCH}px", not tabs["short"], str(tabs["short"]))

    # الخط تحت التبويب المفتوح — تبويب تبويب
    keys = ["locations", "characters", "props", "scenes", "shots", "reports", "import"]
    worst = 0.0
    misses = []
    for key in keys:
        _click_tab(page, key, lang)
        m = page.evaluate(JS_INDICATOR)
        if m.get("err"):
            misses.append(f"{key}: {m['err']}")
            continue
        worst = max(worst, abs(m["dx"]), abs(m["dw"]), abs(m["dy"]))
        if max(abs(m["dx"]), abs(m["dw"]), abs(m["dy"])) > EPS or not m["inside"]:
            misses.append(f"{key}: dx={m['dx']} dw={m['dw']} dy={m['dy']} inside={m['inside']}")
        # كل شاشة بتتقاس وهي مفتوحة
        s = page.evaluate(JS_SCREEN)
        check(f"[{lang}] {key}: عمود واحد", not s["sharedRows"],
              f"{len(s['sharedRows'])} صف فيه أكتر من عمود"
              + (f" {s['sharedRows'][:2]}" if s["sharedRows"] else ""))
        check(f"[{lang}] {key}: مفيش زحلقة أفقية للصفحة", s["pageOverflow"] <= 1,
              f"{s['pageOverflow']}px · عناصر أعرض من الشاشة: "
              f"{s['wideCount']} {s['wideKinds'][:5]}")
        check(f"[{lang}] {key}: مساحات اللمس ≥{TOUCH}px", not s["smallTouch"],
              str(s["smallTouch"][:4]))
        check(f"[{lang}] {key}: مفيش صورة أوسع من عمودها", s["wideImages"] == 0,
              f"{s['wideImages']} صورة")
        # أي جدول بيزحلق لازم يبان عليه إنه بيكمل
        hidden = [d for d in s["dataframes"] if d["sw"] > d["w"] + 1]
        if hidden:
            check(f"[{lang}] {key}: الجدول اللي بيزحلق عليه علامة",
                  all(d["fade"] for d in hidden), str(hidden))
        if s["dataframes"] or s["frames"]:
            print(f"      … {key}: dataframes={s['dataframes']} iframes={s['frames']}",
                  flush=True)
        if shots_on:
            page.screenshot(path=os.path.join(out_dir, f"mobile-{lang}-{key}.png"),
                            full_page=True)

    check(f"[{lang}] الخط تحت التبويب المفتوح مظبوط في كل التبويبات", not misses,
          f"أكبر فرق {worst}px" if not misses else "; ".join(misses))

    # الشريط الجانبي: مقفول وبيتحوّل طبقة
    sb = page.evaluate(JS_SIDEBAR)
    check(f"[{lang}] الشريط الجانبي مقفول على التليفون",
          sb["present"] and not sb["visible"], json.dumps(sb, ensure_ascii=False))
    check(f"[{lang}] زرار فتح الشريط ≥{TOUCH}px",
          bool(sb["ctrl"]) and sb["ctrl"]["w"] >= TOUCH - 0.5 and sb["ctrl"]["h"] >= TOUCH - 0.5,
          json.dumps(sb["ctrl"], ensure_ascii=False))
    before_main = sb["mainWidth"]
    page.locator('[data-testid="stExpandSidebarButton"]').first.click()
    _settle(page, 800)
    op = page.evaluate(JS_SIDEBAR)
    check(f"[{lang}] الشريط بيفتح فوق المحتوى مش بيزقّه",
          op["visible"] and op["mainWidth"] == before_main,
          f"عرض الشريط {op['width']}px · عرض المحتوى {before_main}→{op['mainWidth']}")
    if shots_on:
        page.screenshot(path=os.path.join(out_dir, f"mobile-{lang}-sidebar.png"), full_page=False)
    page.keyboard.press("Escape")
    _settle(page, 600)
    still = page.evaluate(JS_SIDEBAR)
    if still["visible"]:
        page.locator('[data-testid="stSidebarCollapseButton"]').first.click()
        _settle(page, 600)


def main(argv=None):
    ap = argparse.ArgumentParser(description="فحص شاشة الموبايل")
    ap.add_argument("--port", type=int, default=8607)
    ap.add_argument("--tree", default=REPO)
    ap.add_argument("--theme", default="classic", choices=["classic", "glass"])
    ap.add_argument("--langs", default="ar,en")
    ap.add_argument("--out", default=None, help="لو اتحدد، بيتصوّر كل شاشة هناك")
    args = ap.parse_args(argv)

    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    if args.out:
        os.makedirs(args.out, exist_ok=True)

    with AppUnderTest(args.tree, args.port) as app:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--force-color-profile=srgb",
                                               "--disable-lcd-text"])
            for lang in args.langs.split(","):
                ctx = browser.new_context(viewport={"width": PHONE[0], "height": PHONE[1]},
                                          device_scale_factor=1, locale="ar-EG")
                page = ctx.new_page()
                page.goto(app.url + ("/?theme=glass" if args.theme == "glass" else "/"),
                          wait_until="domcontentloaded")
                _settle(page)
                # الدخول وتبديل اللغة على مقاس سطح المكتب (نفس سبب shots.py:
                # زرار اللغة جوه الشريط الجانبي اللي بيبقى طبقة على التليفون)
                desktop = VIEWPORTS["desktop"]
                page.set_viewport_size({"width": desktop[0], "height": desktop[1]})
                page.wait_for_timeout(400)
                _login(page, app)
                if lang == "en":
                    page.get_by_role("button", name="EN", exact=True).first.click()
                    _settle(page, 1200)
                page.set_viewport_size({"width": PHONE[0], "height": PHONE[1]})
                _settle(page, 900)
                _run_lang(page, app, lang, args.out or "", bool(args.out))
                ctx.close()
            browser.close()

    ok = sum(1 for r in results if r)
    print(f"\n{ok}/{len(results)} فحص عدّى")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
