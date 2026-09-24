"""هارنس الصور البصرية — بيشغّل نسخة من البرنامج على بورت منفصل وياخد صور.

ليه موجود: التصميم بيتغير على برنامج على الهوا وعليه 12 مستخدم. الطريقة
الوحيدة إننا نتأكد إن تغيير ما غيّرش حاجة مقصود إنها تفضل زي ما هي، إننا
نصوّر قبل وبعد ونقارن بالبكسل. الكلام مش دليل.

مبيلمسش الإنتاج خالص:
  - بورت منفصل (‎--port‎)، الافتراضي 8599 مش 8501
  - قاعدة بيانات مؤقتة مزروعة (‎seed.py‎) عن طريق ‎STUDIO_DB_PATH‎
  - حساب دخول مؤقت في ‎CIMAFAST_USERS‎ بيتولّد في اللحظة، مش متخزن في الريبو
  - يقدر يشغّل من شجرة تانية (‎--tree‎) عشان نصوّر كوميت قديم للمقارنة

مثال:
    venv/bin/python tests/visual/shots.py --out /tmp/shots/before \\
        --tree /tmp/cf-baseline --port 8591
    venv/bin/python tests/visual/shots.py --out /tmp/shots/after --port 8592
    venv/bin/python tests/visual/shots.py --out /tmp/shots/glass --theme glass --port 8593
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

# الشاشات اللي بنصوّرها — بنمشي عليها بالترتيب في نفس الجلسة
VIEWPORTS = {
    "phone": (390, 844),
    "tablet": (834, 1112),
    "desktop": (1440, 900),
}

TAB_LABELS = {
    "locations": {"ar": "الأماكن", "en": "Locations"},
    "characters": {"ar": "الشخصيات", "en": "Characters"},
    "props": {"ar": "الإكسسوارات", "en": "Props"},
    "scenes": {"ar": "المشاهد", "en": "Scenes"},
    "shots": {"ar": "اللقطات", "en": "Shots"},
    "reports": {"ar": "التقارير النهائية", "en": "Final Reports"},
    "import": {"ar": "إضافة سيناريو", "en": "Add Screenplay"},
}

ANALYZE_LABEL = {"ar": "تحليل الملف", "en": "Analyze File"}

# سكريبت صغير بصيغة البرنامج بيتوقعها — بيتحلل فعليًا وبيطلع لوحة التحليل
SAMPLE_SCRIPT = """مشهد 1 - داخلي - نهار - شقة نادية
نادية بتفتح البلكونة وبتبص على الشارع.
نادية: مفيش حد جه.
حسن: استني شوية.

مشهد 2 - داخلي - ليل - كافيه البورصة
حسن قاعد لوحده بيدوّر في الفنجان.
حسن: أنا مش هرجع تاني.

مشهد 3 - خارجي - غروب - كورنيش الإسكندرية
نادية ماشية والكمنجة في إيدها.
نادية: البحر بيعمل كده كل سنة.
"""


def _free(port):
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _wait_http(url, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.6)
    return False


class AppUnderTest:
    """بيشغّل Streamlit من شجرة معينة على بورت معين بقاعدة بيانات مؤقتة."""

    def __init__(self, tree, port):
        self.tree = os.path.abspath(tree)
        self.port = port
        self.tmp = tempfile.mkdtemp(prefix="cf-shots-")
        self.password = secrets.token_urlsafe(18)
        self.username = "shotbot"
        self.proc = None
        self.log = open(os.path.join(self.tmp, "streamlit.log"), "w")

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def start(self):
        if not _free(self.port):
            raise SystemExit(f"البورت {self.port} مشغول — اختار واحد تاني بـ --port")

        db = os.path.join(self.tmp, "studio.db")
        # الزرع بيستخدم database.py بتاع الشجرة اللي هنصوّرها، عشان السكيما
        # تطابق الكود اللي شغال
        seed = subprocess.run(
            [os.path.join(REPO, "venv/bin/python"), os.path.join(HERE, "seed.py"), db],
            cwd=self.tree, capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": self.tree},
        )
        if seed.returncode != 0:
            raise SystemExit("فشل زرع قاعدة البيانات:\n" + seed.stderr[-3000:])

        # الهاش بيتولّد في اللحظة — مفيش أي كلمة سر أو هاش بيتحفظ في الريبو
        hasher = subprocess.run(
            [os.path.join(REPO, "venv/bin/python"), "-c",
             "import sys, auth; print(auth.hash_password(sys.argv[1]))", self.password],
            cwd=REPO, capture_output=True, text=True,
        )
        if hasher.returncode != 0:
            raise SystemExit("فشل توليد الهاش:\n" + hasher.stderr[-2000:])
        users = json.dumps({self.username: hasher.stdout.strip()})

        env = {
            **os.environ,
            "STUDIO_DB_PATH": db,
            "CIMAFAST_USERS": users,
            "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
        }
        env.pop("CIMAFAST_THEME", None)
        self.proc = subprocess.Popen(
            [os.path.join(REPO, "venv/bin/streamlit"), "run", "app.py",
             "--server.port", str(self.port),
             "--server.address", "127.0.0.1",
             "--server.headless", "true",
             # مراقب الملفات لازم يتقفل: لو أي ملف اتغير وإحنا بنصوّر،
             # Streamlit بيحط شريط "File change / Rerun" فوق الصفحة وبيفسد
             # المقارنة بالبكسل
             "--server.fileWatcherType", "none",
             "--browser.gatherUsageStats", "false"],
            cwd=self.tree, env=env, stdout=self.log, stderr=subprocess.STDOUT,
        )
        if not _wait_http(self.url + "/_stcore/health"):
            self.stop()
            raise SystemExit("الخدمة مقامتش — شوف " + self.log.name)
        return self

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.log.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()


# --------------------------------------------------------------------------
# التنقل في الصفحة
# --------------------------------------------------------------------------

def _settle(page, ms=900):
    """Streamlit بيرسم على مراحل — بننتظر لحد ما الـ spinner يختفي
    وبعدين شوية كمان عشان الخطوط والـ transitions يخلصوا."""
    # ‎networkidle‎ ساعات مبيوصلش على الشاشات اللي فيها صور/خرايط — ده انتظار
    # تحسيني مش شرط، فبناخد اللي نقدر عليه في 8 ثواني وبنكمّل بدل ما الجولة
    # كلها تقع
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    try:
        page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached", timeout=4000)
    except Exception:
        pass
    try:
        page.evaluate("document.fonts && document.fonts.ready")
    except Exception:
        pass
    page.wait_for_timeout(ms)


def _shot(page, out_dir, name):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name + ".png")
    _settle(page)
    page.screenshot(path=path, full_page=True, animations="disabled")
    return path


def _login(page, app):
    page.get_by_label("اسم المستخدم / Username").fill(app.username)
    page.get_by_label("كلمة السر / Password").fill(app.password)
    page.get_by_role("button", name="دخول / Log in").click()
    _settle(page, 1400)


def _click_tab(page, key, lang):
    label = TAB_LABELS[key][lang]
    tab = page.get_by_role("tab").filter(has_text=label).first
    tab.scroll_into_view_if_needed()
    tab.click()
    _settle(page, 700)


def capture(app, out_dir, lang, viewport, theme_flag, browser, shots):
    w, h = VIEWPORTS[viewport]
    ctx = browser.new_context(viewport={"width": w, "height": h},
                              device_scale_factor=1, locale="ar-EG")
    page = ctx.new_page()
    url = app.url + ("/?theme=glass" if theme_flag == "glass" else "/")
    page.goto(url, wait_until="domcontentloaded")

    prefix = f"{lang}-{viewport}"
    shots.append(_shot(page, out_dir, f"{prefix}-01-login"))

    # الدخول وتبديل اللغة بيتعملوا على مقاس سطح المكتب وبعدين بنرجّع المقاس
    # المطلوب. السبب: على الموبايل الشريط الجانبي بيبقى طبقة فوق المحتوى،
    # وزرار اللغة جواه بيتلقّط منها فالكليك مبيوصلش. الشاشات اللي بنصوّرها
    # بتترسم بعد الرجوع للمقاس، فالنتيجة هي نفسها.
    desktop = VIEWPORTS["desktop"]
    if (w, h) != desktop:
        page.set_viewport_size({"width": desktop[0], "height": desktop[1]})
        page.wait_for_timeout(400)

    _login(page, app)

    if lang == "en":
        # segmented_control بيطلع كـ radio مش button
        page.get_by_role("radio", name="EN", exact=True).first.click()
        _settle(page, 1200)

    if (w, h) != desktop:
        page.set_viewport_size({"width": w, "height": h})
        _settle(page, 800)

    shots.append(_shot(page, out_dir, f"{prefix}-02-projects"))

    # كل تبويب بيتصوّر — مش المشاهد والتقارير بس. خطة الموبايل بتطلب تأكيد
    # إن كل شاشة بتتراص في عمود واحد على التليفون، فالشاشات كلها لازم تبقى
    # في المجموعة اللي بنقارنها.
    for idx, key in enumerate(("locations", "characters", "props", "scenes", "shots"), start=3):
        _click_tab(page, key, lang)
        name = "scene-editor" if key == "scenes" else key
        shots.append(_shot(page, out_dir, f"{prefix}-{idx:02d}-{name}"))

    _click_tab(page, "reports", lang)
    shots.append(_shot(page, out_dir, f"{prefix}-08-reports"))

    # لوحة تحليل السيناريو: بترفع ملف وبتدوس تحليل
    _click_tab(page, "import", lang)
    try:
        script_path = os.path.join(app.tmp, "sample-script.txt")
        with open(script_path, "w", encoding="utf-8") as fh:
            fh.write(SAMPLE_SCRIPT)
        page.locator('input[type="file"]').first.set_input_files(script_path)
        _settle(page, 1200)
        page.get_by_role("button").filter(has_text=ANALYZE_LABEL[lang]).first.click()
        _settle(page, 2000)
        shots.append(_shot(page, out_dir, f"{prefix}-09-analysis"))
    except Exception as exc:  # pragma: no cover - بيتسجل بس
        print(f"  ! لوحة التحليل اتخطت في {prefix}: {type(exc).__name__}: {exc}", flush=True)

    ctx.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description="صور بصرية لـ CimaFast Studio")
    ap.add_argument("--out", required=True, help="مجلد الصور")
    ap.add_argument("--tree", default=REPO, help="شجرة الكود اللي هتتشغل (افتراضي: الريبو)")
    ap.add_argument("--port", type=int, default=8599)
    ap.add_argument("--theme", default="classic", choices=["classic", "glass"])
    ap.add_argument("--langs", default="ar,en")
    ap.add_argument("--viewports", default="phone,tablet,desktop")
    args = ap.parse_args(argv)

    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    if os.path.isdir(args.out):
        shutil.rmtree(args.out)
    os.makedirs(args.out, exist_ok=True)

    shots = []
    with AppUnderTest(args.tree, args.port) as app:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--force-color-profile=srgb",
                                               "--disable-lcd-text"])
            for lang in args.langs.split(","):
                for vp in args.viewports.split(","):
                    print(f"  … {lang}/{vp}", flush=True)
                    capture(app, args.out, lang, vp, args.theme, browser, shots)
            browser.close()

    print(f"{len(shots)} صورة في {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
