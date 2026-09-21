"""الصفحة الرئيسية (H1) — المنطق من غير واجهة: تقدّم كل مشروع، الخطوة الجاية،
"محتاجك" حسب دور المستخدم ووظيفته، والبحث في كل مشاريعه.

الواجهة (board/app.py + templates/home.html) بتعرض اللي هنا بس. الأرقام كلها من
repo.project_overview، فمفيش SQL هنا (tests/test_data_layer.py).

كل عنصر فيه `href` — رابط للشاشة المظبوطة: Streamlit بـ links.screen، أو جدول
التصوير. الـ base بيتبعت من الواجهة عشان نفس المنطق يشتغل في أي مسار.
"""
from __future__ import annotations

import accounts
import links
import repo
from search import normalize

STAGES = ("المشروع", "الأماكن والشخصيات", "المشاهد", "تفريغ اللقطات", "المراجعة")


def progress(ov):
    """نفس المراحل الخمسة بتاعة سطر التقدّم جوه المشروع (app.py)."""
    done = [
        True,
        ov["locations"] > 0 and ov["characters"] > 0,
        ov["scenes"] > 0,
        ov["shots"] > 0,
        ov["shots"] > 0 and ov["confirmed_shots"] == ov["shots"],
    ]
    current = next((i for i, d in enumerate(done) if not d), len(done) - 1)
    return {"done": done, "current": current, "step": current + 1, "of": len(done),
            "label": STAGES[current], "complete": all(done)}


def next_step(ov, app, board):
    """الخطوة الجاية للمشروع: جملة واحدة + رابط. app/board: دوال بتبني الروابط."""
    if ov["scenes"] == 0:
        return "ارفع السيناريو وحلّله عشان المشاهد والأماكن والشخصيات تتعمل لوحدها", app("import")
    if ov["locations"] == 0 or ov["characters"] == 0:
        return "كمّل الأماكن والشخصيات", app("locations" if ov["locations"] == 0 else "characters")
    missing = ov["scenes"] - ov["scenes_with_shots"]
    if missing:
        return f"{missing} مشهد لسه من غير لقطات", app("shots")
    unreviewed = ov["shots"] - ov["confirmed_shots"]
    if unreviewed:
        return f"{unreviewed} لقطة مستنية مراجعة", app("shots")
    if ov["days"] == 0:
        return "اعمل جدول التصوير", board
    unscheduled = ov["scenes"] - ov["scheduled_scenes"]
    if unscheduled:
        return f"{unscheduled} مشهد لسه مش في جدول التصوير", board
    return "كل مراحل المشروع مكتملة — التقارير جاهزة للتصدير", app("reports")


# --- "محتاجك" ----------------------------------------------------------------------------
# الدور في الشركة بيقول المستخدم يقدر يعمل إيه (F2)؛ المسمى الوظيفي بيقول إيه يهمّه.
# القاعدة بتتطابق لو الدور في roles أو أي كلمة من words في المسمى الوظيفي.

_PLANNERS = ("admin", "producer", "manager", "operator")
RULES = [
    # (id, roles, words في المسمى, شرط/عدد من الأرقام, الجملة, التبويب أو "board")
    ("unscheduled", _PLANNERS, ("مساعد مخرج", "منتج", "مدير إنتاج"),
     lambda o: (o["scenes"] - o["scheduled_scenes"]) if o["scenes"] and o["days"] else 0,
     "مشهد لسه مش في جدول التصوير", "board"),
    ("no_schedule", _PLANNERS, ("مساعد مخرج", "منتج", "مدير إنتاج"),
     lambda o: o["scenes"] if o["scenes"] and not o["days"] else 0,
     "مشهد ومفيش جدول تصوير لسه", "board"),
    ("undated_days", _PLANNERS, ("مساعد مخرج", "منتج", "مدير إنتاج"),
     lambda o: o["days_without_date"], "يوم تصوير من غير تاريخ", "board"),
    ("no_shots", ("manager",), ("مخرج", "تصوير"),
     lambda o: o["scenes"] - o["scenes_with_shots"], "مشهد من غير لقطات", "shots"),
    ("unreviewed", ("manager",), ("مخرج", "تصوير"),
     lambda o: o["shots"] - o["confirmed_shots"], "لقطة مستنية مراجعة", "shots"),
    ("no_look", (), ("أزياء", "ماكياج", "مكياج", "شعر"),
     lambda o: o["characters_without_look"], "شخصية ملهاش لوك متسجّل", "characters"),
    ("look_changes", (), ("أزياء", "ماكياج", "مكياج", "شعر"),
     lambda o: o["scenes_with_look_change"], "مشهد فيه تغيير لوك", "scenes"),
    ("location_images", (), ("فني", "ديكور", "مواقع", "أماكن"),
     lambda o: o["locations_without_image"], "مكان من غير صورة مرجعية", "locations"),
    ("character_images", (), ("كاستينج", "اختيار الممثلين"),
     lambda o: o["characters_without_image"], "شخصية من غير صورة مرجعية", "characters"),
    ("no_script", ("admin", "producer", "operator"), ("سيناريست", "كاتب"),
     lambda o: 1 if not o["scenes"] else 0, "المشروع لسه من غير سيناريو", "import"),
]


def _applies(rule, role, job_title):
    _, roles, words, *_ = rule
    job = normalize(job_title or "")
    return role in roles or any(normalize(w) in job for w in words)


def needs_you(role, job_title, cards):
    """العناصر اللي محتاجة المستخدم ده، من كل مشاريعه. المشاهد مالوش مهام."""
    if role == "viewer":
        return []
    items = []
    for card in cards:
        ov = card["overview"]
        for rule in RULES:
            if not _applies(rule, role, job_title):
                continue
            rid, _, _, count_of, text, target = rule
            n = count_of(ov)
            if n > 0:
                items.append({"id": rid, "count": n, "text": text, "project": card["name"],
                              "project_id": card["id"],
                              "href": card["board_href"] if target == "board" else card["tab_href"](target)})
    items.sort(key=lambda i: -i["count"])
    return items


# --- المشاريع ---------------------------------------------------------------------------

def cards(username, app_base, board_base):
    """كارت لكل مشروع المستخدم يقدر يشوفه، في كل شركاته."""
    out = []
    companies = {c["id"]: c for c in accounts.companies_for(username)}
    for p in accounts.projects_for(username):
        ov = repo.project_overview(p["id"])

        def tab_href(tab, _pid=p["id"]):
            return links.screen(app_base, _pid, tab)

        board = f"{board_base}?project={p['id']}"
        step_text, step_href = next_step(ov, tab_href, board)
        company = companies.get(p["company_id"]) or {}
        out.append({"id": p["id"], "name": p["name"], "type": p["project_type"],
                    "company": company.get("name"), "role": company.get("role"),
                    "overview": ov, "progress": progress(ov),
                    "next_text": step_text, "next_href": step_href,
                    # "افتح": مشروع لسه من غير سيناريو يبدأ من الإضافة، غير كده من المشاهد
                    "open_href": tab_href("scenes" if ov["scenes"] else "import"), "board_href": board,
                    "reports_href": tab_href("reports"), "tab_href": tab_href})
    return out


# --- البحث -------------------------------------------------------------------------------

def search(username, query, app_base, limit=30):
    """بحث عربي ذكي في مشاريع المستخدم: شخصيات، أماكن، إكسسوارات، مشاهد."""
    q = normalize(query or "")
    if len(q) < 2:
        return []
    hits = []
    for p in accounts.projects_for(username):
        pid, pname = p["id"], p["name"]
        for kind, tab, rows, text_of in (
            ("شخصية", "characters", repo.characters_of_project(pid), lambda r: r["name"]),
            ("مكان", "locations", repo.locations_of_project(pid), lambda r: r["name"]),
            ("إكسسوار", "props", repo.props_of_project(pid), lambda r: r["name"]),
            ("مشهد", "scenes", repo.scenes_of_project(pid),
             # تغيير اللوك جزء من البحث: قسم الأزياء بيدوّر بـ "الفستان" مش برقم المشهد
             lambda r: f"{r['scene_number']}{r.get('scene_suffix') or ''} — "
                       + " · ".join(x for x in (r.get("notes"), r.get("look_change_notes")) if x)),
        ):
            for r in rows:
                label = text_of(dict(r))
                if q in normalize(label):
                    hits.append({"kind": kind, "label": label.strip()[:90], "project": pname,
                                 "href": links.screen(app_base, pid, tab)})
                    if len(hits) >= limit:
                        return hits
    return hits


def continue_link(username, app_base):
    """"كمّل من مكان ما وقفت": آخر مشروع وتبويب، لو لسه مسموح له يفتحه."""
    last = repo.last_screen(username)
    if not last or not last["last_project_id"]:
        return None
    pid = last["last_project_id"]
    if not accounts.can_access_project(username, pid):
        return None
    tab = last["last_tab"] if last["last_tab"] in links.TABS else None
    return {"project": repo.project(pid)["name"], "tab": tab,
            "href": links.screen(app_base, pid, tab), "when": last["updated_at"]}
