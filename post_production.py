"""ما بعد الإنتاج (بند PP1 في PRODUCT-PLAN.md، طلب المالك 2026-09-24).

الأقسام والحالات ثابتة هنا (مش في قاعدة البيانات) عشان كل المشاريع تتكلم نفس
اللغة والتقرير يطلع بنفس الترتيب. الحسابات هنا من غير Streamlit عشان تتختبر
لوحدها: نسبة إنجاز كل قسم، والمتوسط اللي شريط التقدّم بيعرضه.
"""
from __future__ import annotations

import datetime as dt

# (المفتاح، الأيقونة، الاسم) بترتيب الشغل الفعلي: المونتاج الأول، والماستر آخر حاجة
DEPARTMENTS = [
    ("edit", "✂️", "المونتاج"),
    ("vfx", "✨", "المؤثرات البصرية (CGI)"),
    ("color", "🎨", "التلوين (Color)"),
    ("music", "🎼", "الموسيقى"),
    ("sound", "🔊", "تصميم الصوت"),
    ("mix", "🎚️", "الدوبلاج والميكساج"),
    ("titles", "🎞️", "التترات والجرافيك والماستر"),
]
DEPT_KEYS = [d[0] for d in DEPARTMENTS]

# (المفتاح، الأيقونة، الاسم)
STATUSES = [
    ("not_started", "⚪", "لم يبدأ"),
    ("in_progress", "🔵", "جاري"),
    ("in_review", "🟡", "في المراجعة"),
    ("changes", "🟠", "محتاج تعديل"),
    ("approved", "🟢", "معتمد"),
]
STATUS_KEYS = [s[0] for s in STATUSES]

STALE_DAYS = 7   # قسم شغّال ومحدش حدّثه أسبوع = بيتعلّم عليه


def dept(key):
    return next((d for d in DEPARTMENTS if d[0] == key), None)


def status(key):
    return next((s for s in STATUSES if s[0] == key), STATUSES[0])


def effective_progress(row):
    """النسبة اللي بتتحسب: المعتمد 100% دايمًا، واللي لم يبدأ 0% دايمًا."""
    if not row:
        return 0
    st = row.get("status") or "not_started"
    if st == "approved":
        return 100
    if st == "not_started":
        return 0
    try:
        return max(0, min(100, int(row.get("progress") or 0)))
    except (TypeError, ValueError):
        return 0


def is_stale(row, today=None):
    """شغّال (مش لم يبدأ ومش معتمد) وآخر تحديث من أكتر من أسبوع."""
    if not row or (row.get("status") or "not_started") in ("not_started", "approved"):
        return False
    raw = (row.get("updated_at") or "")[:10]
    try:
        last = dt.date.fromisoformat(raw)
    except ValueError:
        return False
    return ((today or dt.date.today()) - last).days > STALE_DAYS


def summary(rows):
    """rows = صفوف post_departments (ممكن ناقصة). بيرجّع كل الأقسام بالترتيب
    + متوسط الإنجاز وعدد المعتمد."""
    by_key = {r["dept_key"]: dict(r) for r in rows or []}
    items = []
    for key, icon, name in DEPARTMENTS:
        row = by_key.get(key) or {"dept_key": key, "status": "not_started", "progress": 0}
        items.append({"key": key, "icon": icon, "name": name, "row": row,
                      "progress": effective_progress(row), "stale": is_stale(row)})
    overall = round(sum(i["progress"] for i in items) / len(items)) if items else 0
    approved = sum(1 for i in items if (i["row"].get("status") == "approved"))
    return {"items": items, "overall": overall, "approved": approved, "total": len(items)}
