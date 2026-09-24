"""H4 — تنبيهات التغيير للقسم اللي يهمّه.

سجل F3 (``audit_log``) بيعرف مين غيّر إيه، بس مابيقولش لحد. مدير التصوير
مابيعرفش إن مكان مشهد اتغيّر غير لو فتح البرنامج ودوّر بنفسه. هنا حاجتين:

1. **وقت الكتابة:** كل صف في السجل بياخد عمود ``departments`` — الأقسام اللي
   التغيير ده يخصّها (``tag()``). التغيير في مكان المشهد يخص الفني والتصوير
   والإنتاج؛ حفظ جدول التصوير يخص الكل. الوسم بيتكتب مع الصف، في نفس
   الـ transaction، فمفيش تغيير بيتسجّل من غير ما يتوسم.
2. **وقت القراءة:** كل مستخدم بيشوف التغييرات اللي تخص قسمه في مشاريع شركاته،
   من غير اللي هو عملها بنفسه (``feed()``). "اتشاف لحد فين" متخزن في جدول
   ``notification_seen`` لوحده — مش في ``user_profile``، لأن ده بيتمسح ويتكتب
   تاني مع كل تبويب بيتفتح.

القسم بيتعرف من المسمى الوظيفي (``users.job_title``) بنفس أسلوب «محتاجك» في
home.py — كلمات في المسمى، مش قايمة مقفولة. مدير الشركة والمنتج ومدير الإنتاج
قسمهم «الإنتاج» بالدور نفسه. رئيس قسم مسماه مش مفهوم **بيشوف الكل**: تنبيه
زيادة أرخص بكتير من قسم يفوته تغيير.

الملف ده مفيهوش Streamlit ولا Starlette عشان يتختبر لوحده.
"""
from __future__ import annotations

import datetime as dt
import json
import sys

from search import normalize

ALL = "*"

# (المفتاح، الاسم، كلمات في المسمى الوظيفي)
DEPARTMENTS = (
    ("directing", "الإخراج", ("مخرج",)),               # "مساعد مخرج" برضه — بيهمّه
    ("production", "الإنتاج", ("منتج", "إنتاج", "مساعد مخرج", "لوكيشن")),
    ("camera", "التصوير", ("تصوير", "كاميرا", "إضاءة")),
    ("art", "الفني والديكور", ("فني", "ديكور", "مواقع", "أماكن", "إكسسوار", "اكسسوار")),
    ("costume", "الأزياء والماكياج", ("أزياء", "ازياء", "ماكياج", "مكياج", "شعر", "ملابس")),
    ("casting", "الكاستينج", ("كاستينج", "اختيار الممثلين")),
    ("script", "السيناريو", ("سيناريست", "كاتب", "سيناريو")),
    ("editing", "المونتاج", ("مونتير", "مونتاج")),
    ("vfx", "المؤثرات", ("مؤثرات", "vfx")),
)
DEPARTMENT_LABELS = {key: label for key, label, _ in DEPARTMENTS}
_PRODUCTION_ROLES = {"operator", "admin", "producer", "manager"}

# أعمدة المشهد اللي تغييرها بيحرّك التصوير نفسه (مكان، داخلي/خارجي، توقيت)،
# مش ملاحظة أو طقس بس.
_SCENE_SHOOT_COLS = {"location_variant_id", "int_ext", "day_night", "scene_number", "scene_suffix"}

_ENTITY_DEPTS = {
    "scenes": {"directing", "production"},
    "shooting_days": {ALL},
    "shooting_day_scenes": {ALL},
    "locations": {"art", "camera", "production", "directing"},
    "location_variants": {"art", "camera", "production", "directing"},
    "characters": {"costume", "casting", "directing"},
    "character_looks": {"costume", "directing"},
    "scene_characters": {"costume", "casting", "directing", "production"},
    "character_actor_casting": {"casting", "production", "directing"},
    "props": {"art", "production"},
    "scene_props": {"art", "production"},
    "shot_props": {"art"},
    "shots": {"directing", "camera", "editing"},
    "shot_characters": {"directing", "camera"},
    "camera_setups": {"camera", "directing"},
    "reference_images": {"art", "costume", "directing"},
    "episodes": {"production", "script"},
}

# عمليات ليها اسم (audit.action) — بتسبق الجدول
_ACTION_DEPTS = {
    "schedule_save": {ALL},
    "schedule_suggest": {ALL},
    "import_script": {ALL},
}

# أسماء الأعمدة اللي بتظهر في سطر التنبيه ("اتغيّر: المكان، التوقيت")
FIELD_LABELS = {
    "location_variant_id": "المكان", "int_ext": "داخلي/خارجي", "day_night": "التوقيت",
    "scene_number": "رقم المشهد", "scene_suffix": "رقم المشهد", "weather": "الطقس",
    "notes": "الملاحظات", "shoot_date": "تاريخ التصوير", "day_number": "ترتيب الأيام",
    "name": "الاسم", "description": "الوصف", "reference_image_path": "الصورة المرجعية",
}

FIELD_LABELS_EN = {
    "location_variant_id": "location", "int_ext": "INT/EXT", "day_night": "time of day",
    "scene_number": "scene number", "scene_suffix": "scene number", "weather": "weather",
    "notes": "notes", "shoot_date": "shoot date", "day_number": "day order",
    "name": "name", "description": "description", "reference_image_path": "reference image",
}
DEPARTMENT_LABELS_EN = {
    "directing": "Directing", "production": "Production", "camera": "Camera", "art": "Art",
    "costume": "Costume & make-up", "casting": "Casting", "script": "Script",
    "editing": "Editing", "vfx": "VFX",
}
_ACTION_TEXT_EN = {"schedule_save": "Shooting schedule saved",
                   "schedule_suggest": "Shooting schedule suggested",
                   "import_script": "Script imported"}

# التبويب اللي التنبيه بيفتحه (H2)؛ "board" يعني جدول التصوير
_ENTITY_TAB = {
    "scenes": "scenes", "scene_characters": "scenes", "scene_props": "scenes",
    "locations": "locations", "location_variants": "locations",
    "characters": "characters", "character_looks": "characters",
    "character_actor_casting": "characters",
    "props": "props", "shots": "shots", "shot_characters": "shots", "shot_props": "shots",
    "camera_setups": "shots", "episodes": "settings",
    "shooting_days": "board", "shooting_day_scenes": "board",
}
_ACTION_TAB = {"schedule_save": "board", "schedule_suggest": "board", "import_script": "scenes"}

WINDOW_DAYS = 14          # التنبيه الأقدم من كده مش "تغيير جديد" — ده تاريخ، مكانه سجل النشاط
MAX_ITEMS = 30


# --- وقت الكتابة ------------------------------------------------------------------

def _changed_columns(changes):
    if isinstance(changes, str):
        try:
            changes = json.loads(changes)
        except ValueError:
            return set()
    if isinstance(changes, dict) and isinstance(changes.get("changed"), dict):
        return set(changes["changed"])
    return set()


def tag(entity, action, changes=None):
    """الأقسام اللي التغيير ده يخصّها، بالشكل اللي بيتخزن: ",art,camera," أو None.

    الفواصل في الأول والآخر عشان ``LIKE '%,art,%'`` مايلقطش قسم اسمه جزء من
    اسم قسم تاني، ونفس الاستعلام يشتغل على SQLite وPostgres.
    """
    depts = set(_ACTION_DEPTS.get(action) or _ENTITY_DEPTS.get(entity) or ())
    if not depts:
        return None
    if entity == "scenes":
        if action in ("create", "delete"):
            depts = {ALL}                          # مشهد اتضاف أو اتشال: الجدول كله بيتأثر
        elif _changed_columns(changes) & _SCENE_SHOOT_COLS:
            depts |= {"camera", "art"}
    if ALL in depts:
        return f",{ALL},"
    return "," + ",".join(sorted(depts)) + ","


# --- مين يهمّه إيه ---------------------------------------------------------------

def departments_of(role, job_title):
    """أقسام المستخدم، أو None يعني "كل حاجة" (مسمى مش مفهوم)."""
    job = normalize(job_title or "")
    mine = {key for key, _, words in DEPARTMENTS if job and any(normalize(w) in job for w in words)}
    if role in _PRODUCTION_ROLES:
        mine.add("production")
    return mine or None


def _dept_clause(depts):
    """شرط SQL: الصفوف الموسومة للكل أو لقسم من أقسام المستخدم."""
    if depts is None:
        return "departments IS NOT NULL AND departments <> ''", []
    parts = ["departments LIKE ?"]
    params = [f"%,{ALL},%"]
    for d in sorted(depts):
        parts.append("departments LIKE ?")
        params.append(f"%,{d},%")
    return "(" + " OR ".join(parts) + ")", params


def _since():
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=WINDOW_DAYS)).isoformat(timespec="seconds")


def _scope(username):
    """(شرط SQL، باراميترز) لتنبيهات المستخدم ده، أو None لو مالوش حاجة يشوفها."""
    import accounts
    me = accounts.user(username) if username else None
    if not me or not me["active"]:
        return None
    projects = [p["id"] for p in accounts.projects_for(username)]
    if not projects:
        return None
    companies = accounts.companies_for(username)
    rank = {r: i for i, r in enumerate(("operator", "admin", "producer", "manager", "department", "viewer"))}
    role = min((c["role"] for c in companies), key=lambda r: rank.get(r, 99), default="viewer")
    where, params = _dept_clause(departments_of(role, me["job_title"]))
    marks = ",".join("?" * len(projects))
    clauses = [f"project_id IN ({marks})", "(username IS NULL OR username <> ?)", "at >= ?", where]
    return " AND ".join(clauses), [*projects, username, _since(), *params]


def last_seen(username):
    from database import fetch_all
    rows = fetch_all("SELECT last_seen_id FROM notification_seen WHERE username=?", (username,))
    return (rows[0]["last_seen_id"] or 0) if rows else 0


def mark_seen(username, up_to_id):
    """التنبيهات لحد الرقم ده اتشافت. مابيرجعش لورا أبدًا (تابين مفتوحين)."""
    if not username or not up_to_id:
        return
    try:
        import permissions
        import repo
        current = last_seen(username)
        if int(up_to_id) <= current:
            return
        with permissions.system(), repo._tx() as ex:
            ex("DELETE FROM notification_seen WHERE username=?", (username,))
            ex("INSERT INTO notification_seen (username, last_seen_id, updated_at) VALUES (?, ?, ?)",
               (username, int(up_to_id), dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")))
    except Exception as exc:  # noqa: BLE001 — التنبيه عمره ما يوقّع الشاشة
        print(f"[notify] mark_seen: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)


def unread_count(username):
    try:
        scope = _scope(username)
        if scope is None:
            return 0
        where, params = scope
        from database import fetch_all
        rows = fetch_all(f"SELECT COUNT(*) AS n FROM audit_log WHERE {where} AND id > ?",
                         tuple(params + [last_seen(username)]))
        return int(rows[0]["n"]) if rows else 0
    except Exception as exc:  # noqa: BLE001
        print(f"[notify] unread_count: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 0


# --- العرض --------------------------------------------------------------------------

def _scene_labels(ids):
    if not ids:
        return {}
    from database import fetch_all, scene_label
    marks = ",".join("?" * len(ids))
    rows = fetch_all(f"SELECT id, scene_number, scene_suffix FROM scenes WHERE id IN ({marks})", tuple(ids))
    return {r["id"]: scene_label(r) for r in rows}


def _names(usernames):
    if not usernames:
        return {}
    from database import fetch_all
    marks = ",".join("?" * len(usernames))
    rows = fetch_all(f"SELECT username, display_name FROM users WHERE username IN ({marks})", tuple(usernames))
    return {r["username"]: (r["display_name"] or r["username"]) for r in rows}


def _text(row, scene_labels, lang="ar"):
    """سطر التنبيه بلغة الفريق: "مشهد 12: اتغيّر المكان" بدل "تعديل في المشاهد #88".

    الإنجليزي للحالات المفهومة بس؛ الباقي بيرجع لملخّص السجل العربي زي ما هو
    (سجل النشاط نفسه عربي بس لحد دلوقتي)."""
    en = lang == "en"
    labels = FIELD_LABELS_EN if en else FIELD_LABELS
    fields = []
    for col in _changed_columns(row["changes"]):
        label = labels.get(col)
        if label and label not in fields:
            fields.append(label)
    joined = (", " if en else "، ").join(fields)
    if row["entity"] == "scenes" and row["entity_id"] in scene_labels:
        head = f"{'Scene' if en else 'مشهد'} {scene_labels[row['entity_id']]}"
        if row["action"] == "update":
            if fields:
                return f"{head}: {joined} changed" if en else f"{head}: اتغيّر {joined}"
            return f"{head}: edited" if en else f"{head}: اتعدّل"
        if row["action"] == "create":
            return f"{head}: added" if en else f"{head}: اتضاف"
    if row["entity"] == "shooting_days" and row["action"] == "update" and fields:
        return f"Shoot day: {joined} changed" if en else f"يوم تصوير: اتغيّر {joined}"
    if en and row["action"] in _ACTION_TEXT_EN:
        return _ACTION_TEXT_EN[row["action"]]
    return row["summary"] or row["action"]


def _href(row, app_base, board_base):
    import links
    tab = _ACTION_TAB.get(row["action"]) or _ENTITY_TAB.get(row["entity"])
    pid = row["project_id"]
    if tab == "board":
        return f"{board_base}?project={int(pid)}" if board_base else links.screen(app_base, pid, "settings")
    if tab is None:
        return links.screen(app_base, pid)
    item = row["entity_id"] if (row["entity"] == "scenes" and row["action"] != "delete") else None
    return links.screen(app_base, pid, tab, item=item)


def feed(username, app_base, board_base=None, limit=MAX_ITEMS, lang="ar"):
    """{"unread": عدد، "items": [...]} — الأحدث الأول. عمره ما بيرمي استثناء."""
    try:
        scope = _scope(username)
        if scope is None:
            return {"unread": 0, "items": [], "latest_id": 0}
        where, params = scope
        from database import fetch_all
        rows = fetch_all(
            f"SELECT id, at, username, project_id, entity, entity_id, action, summary, changes, departments "
            f"FROM audit_log WHERE {where} ORDER BY id DESC LIMIT ?",
            tuple(params + [max(1, min(int(limit), 100))]))
        seen = last_seen(username)
        scene_labels = _scene_labels(sorted({r["entity_id"] for r in rows
                                             if r["entity"] == "scenes" and r["entity_id"]}))
        names = _names(sorted({r["username"] for r in rows if r["username"]}))
        import accounts
        projects = {p["id"]: p["name"] for p in accounts.projects_for(username)}
        items = []
        for r in rows:
            depts = [d for d in (r["departments"] or "").strip(",").split(",") if d and d != ALL]
            items.append({
                "id": r["id"], "at": r["at"], "unread": r["id"] > seen,
                "who": names.get(r["username"], r["username"] or "—"),
                "project": projects.get(r["project_id"], ""),
                "text": _text(r, scene_labels, lang),
                "departments": [(DEPARTMENT_LABELS_EN if lang == "en" else DEPARTMENT_LABELS)[d]
                                for d in depts if d in DEPARTMENT_LABELS]
                               or (["Everyone"] if lang == "en" else ["الكل"]),
                "href": _href(r, app_base, board_base),
            })
        return {"unread": unread_count(username), "items": items,
                "latest_id": rows[0]["id"] if rows else 0}
    except Exception as exc:  # noqa: BLE001
        print(f"[notify] feed: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return {"unread": 0, "items": [], "latest_id": 0}


def ago(at, now=None, lang="ar"):
    """"من ٥ دقايق" — نص قصير للموبايل."""
    try:
        when = dt.datetime.fromisoformat(at)
        if when.tzinfo is None:
            when = when.replace(tzinfo=dt.timezone.utc)
    except (TypeError, ValueError):
        return ""
    secs = max(0, int(((now or dt.datetime.now(dt.timezone.utc)) - when).total_seconds()))
    en = lang == "en"
    if secs < 60:
        return "just now" if en else "دلوقتي"
    for size, en_unit, ar_unit in ((86400, "d", "يوم"), (3600, "h", "ساعة"), (60, "min", "دقيقة")):
        if secs >= size:
            n = secs // size
            return f"{n} {en_unit} ago" if en else f"من {n} {ar_unit}"
    return ""
