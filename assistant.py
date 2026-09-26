"""🤖 مساعد البرنامج — البرومبت وقراءة الرد (موديول نقي، مابيستوردش Streamlit).

المساعد بيرد من assistant_guide.md بس (مرجع مكتوب للبرنامج) + مكان اليوزر
دلوقتي في البرنامج. لو السؤال مش في الدليل بيقول كده بدل ما يخترع ميزة. ممكن
يقترح زراير تنقّل: سطور ‎GO: <مفتاح>‎ في آخر الرد، والشاشة بتحوّلها زراير.
"""
from __future__ import annotations

import os
import re

GUIDE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assistant_guide.md")

# الأماكن اللي المساعد يقدر يودّي لها: (المفتاح، النوع، الاسم اللي على الزرار)
DESTINATIONS = {
    "import": ("tab", "📤 إضافة سيناريو"), "locations": ("tab", "📍 الأماكن"), "props": ("tab", "🎒 الإكسسوارات"),
    "characters": ("tab", "🎭 الشخصيات"), "actors": ("tab", "🎬 الممثلين"), "wardrobe": ("tab", "👗 الملابس"),
    "scenes": ("tab", "📝 المشاهد"), "shots": ("tab", "🎥 اللقطات"), "reports": ("tab", "📊 التقارير النهائية"),
    "schedule": ("tab", "🗓️ جدول التصوير"), "post": ("tab", "🎞️ أقسام ما بعد الإنتاج"),
    "team": ("tab", "👥 فريق العمل"), "settings": ("tab", "⚙️ إعدادات المشروع"),
    "account": ("page", "👤 حسابي"), "actors_library": ("page", "🎭 مكتبة الممثلين"),
    "locations_library": ("page", "📍 مكتبة مواقع التصوير"), "analysis_library": ("page", "📚 مكتبة التحليلات"),
}
PAGE_SLUGS = {"account": "account", "actors_library": "actors", "locations_library": "locations_lib",
              "analysis_library": "library"}

MAX_QUESTION = 800
MAX_HISTORY = 6
_GO_RE = re.compile(r"^\s*GO:\s*([a-z_]+)\s*$", re.MULTILINE)


def guide():
    with open(GUIDE_PATH, encoding="utf-8") as fh:
        return fh.read()


def build_prompt(question, context, history=()):
    """context = {name, lang, screen, project, project_type, role, counts:{...}, operator}."""
    ctx_lines = [f"- {k}: {v}" for k, v in context.items() if v not in (None, "", {}, [])]
    hist = []
    for h in list(history)[-MAX_HISTORY:]:
        hist.append(f"المستخدم: {h.get('q', '')}\nالمساعد: {h.get('a', '')}")
    dests = ", ".join(DESTINATIONS)
    return "\n".join([
        "أنت «مساعد سيما فاست» جوه برنامج سيما فاست ستوديو. شغلتك تساعد المستخدم يلاقي طريقه في البرنامج ويعرف يعمل اللي عايزه.",
        "قواعد:",
        "- رد من الدليل اللي تحت بس. لو الحاجة مش في الدليل قول بوضوح إنك مش متأكد إنها موجودة في البرنامج، واقترح أقرب حاجة موجودة. ماتخترعش زراير ولا شاشات ولا مزايا.",
        "- رد بالعامية المصرية وبإيجاز (خطوات مرقّمة قصيرة لو فيه خطوات)، واكتب أسامي الزراير والتبويبات زي ما هي في الدليل بالظبط. لو المستخدم كتب بالإنجليزي رد بالإنجليزي.",
        "- استخدم مكان المستخدم دلوقتي (تحت) عشان تقوله يروح فين من مكانه.",
        "- المشاريع والمشاهد اللي في حساب المستخدم بياناته هو؛ إنت بتشرح البرنامج، مش بتدير إنتاجه.",
        "- لو فيه شاشة معيّنة هتفيده، اكتب في آخر الرد سطر أو اتنين بالشكل ده بالظبط: GO: <مفتاح> — من المفاتيح دي بس: " + dests,
        "- لو السؤال مالوش علاقة بالبرنامج، رد باختصار إنك مساعد البرنامج بس.",
        "",
        "=== مكان المستخدم دلوقتي ===",
        *ctx_lines,
        "",
        "=== الدليل ===",
        guide(),
        "",
        *(["=== المحادثة لحد دلوقتي ===", *hist, ""] if hist else []),
        "=== سؤال المستخدم ===",
        question[:MAX_QUESTION],
    ])


def parse_answer(text):
    """(نص الرد من غير سطور GO، [مفاتيح التنقل المسموحة بس، من غير تكرار])."""
    text = (text or "").strip()
    goes = []
    for slug in _GO_RE.findall(text):
        if slug in DESTINATIONS and slug not in goes:
            goes.append(slug)
    body = _GO_RE.sub("", text).strip()
    return body, goes[:3]
