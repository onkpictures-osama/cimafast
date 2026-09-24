"""F3 — سجل التدقيق وأحداث الاستخدام.

جدولين، كل واحد ليه شغلانة مختلفة عن التاني عن قصد:

- ``audit_log`` — **مين غيّر إيه وإمتى**: سجل مساءلة، بيتكتب مرة واحدة ومبيتعدّلش.
  بيتسجّل أوتوماتيك من طبقة البيانات نفسها: أي INSERT/UPDATE/DELETE بيعدّي على
  ``database.run_query`` أو ``repo._tx`` بيتسجّل بقيمه القديمة والجديدة، فمفيش
  شاشة تقدر تنسى التسجيل — نفس فكرة فحص الصلاحيات في F2.
- ``usage_events`` — **مين استخدم إيه**: دخول، فتح شاشة، تصدير ملف، تشغيل تحليل.
  صفوف كتير ورخيصة ومش حساسة، وبتترد على سؤال "الناس بتستخدم إيه فعلًا".

ليه الاتنين مش واحد؟ السجل الأول بيتقري لما حد يسأل "مين مسح المشهد ده"، والتاني
بيتقري مجمّع ("كام واحد صدّر تقرير الشهر ده"). لو اتحطوا في جدول واحد، الاستعلام
المجمّع هيدوس على سجل المساءلة، وسياسة الحذف بتاعت الاتنين مختلفة.

**العزل بين الشركات:** كل صف تبع شركة (``company_id``)، والعرض بيفلتر بيها زي كل
حاجة في F1 — مدير شركة بيشوف نشاط شركته وبس، ومشغّل المنصة بيشوف الكل.

السياق (مين، أنهي شركة، أنهي مشروع) بيتقري بنفس أسلوب ``permissions``::

    audit.set_resolver(fn)            # Streamlit: الدور والشركة من session_state
    audit.set_context(username=..., company_id=...)   # Starlette: لكل طلب لوحده
    with audit.action("import_script", "scenes", project_id=7, summary="..."):
        ...                            # كل الكتابات جوه بتتلمّ في صف واحد

قاعدة أساسية: **السجل عمره ما يوقّع عملية المستخدم.** أي خطأ هنا بيتبلع
وبيتطبع على stderr — الفيلم أهم من اللوج.
"""
from __future__ import annotations

import contextlib
import contextvars
import datetime as dt
import json
import re
import sys

# جداول مش بتتسجّل: السجل نفسه (عشان مايسجّلش نفسه للأبد)، وذاكرة "آخر شاشة"
# بتاعت الصفحة الرئيسية (بتتكتب مع كل ضغطة تبويب — دي حدث استخدام مش تغيير بيانات).
# notification_seen (H4) نفس فكرة user_profile: "اتشاف لحد فين" حالة شاشة، مش تغيير بيانات.
SKIP_TABLES = {"audit_log", "usage_events", "user_profile", "notification_seen"}

# أعمدة قيمتها ماتتكتبش في السجل أبدًا. hash كلمة السر لو اتخزن في اللوج يبقى
# اللوج بقى نسخة تانية من ملف كلمات السر.
_SECRET_HINTS = ("password", "secret", "token", "hash")
SECRET_CHANGED = "اتغيّرت (القيمة نفسها مابتتسجّلش)"

MAX_VALUE_CHARS = 200          # قيمة واحدة
MAX_CHANGES_CHARS = 2000       # الـ JSON كله

# أفعال بأسماء عربية للعرض. اللي مش هنا بيتعرض زي ما هو.
ACTION_LABELS = {
    "create": "إضافة", "update": "تعديل", "delete": "حذف",
    "login": "دخول", "logout": "خروج", "login_failed": "محاولة دخول فاشلة",
    "password_change": "تغيير كلمة السر", "password_reset": "تصفير كلمة السر",
    "member_add": "إضافة عضو", "member_remove": "شيل عضو", "role_change": "تغيير دور",
    "company_create": "إنشاء مساحة عمل", "company_rename": "تغيير اسم مساحة العمل",
    "project_create": "إنشاء مشروع", "import_script": "استيراد سيناريو",
    "schedule_save": "حفظ جدول التصوير", "schedule_suggest": "اقتراح جدول تصوير",
}

ENTITY_LABELS = {
    "auth": "الدخول", "users": "الحسابات", "memberships": "العضوية", "companies": "مساحات العمل",
    "projects": "المشاريع", "scenes": "المشاهد", "locations": "الأماكن",
    "location_variants": "حالات الأماكن", "characters": "الشخصيات",
    "character_looks": "لوكات الشخصيات", "props": "الإكسسوارات", "shots": "اللقطات",
    "episodes": "الحلقات", "shooting_days": "أيام التصوير",
    "shooting_day_scenes": "جدول التصوير", "scene_characters": "شخصيات المشاهد",
    "scene_props": "إكسسوارات المشاهد", "shot_characters": "شخصيات اللقطات",
    "shot_props": "إكسسوارات اللقطات", "reference_images": "الصور المرجعية",
    "camera_setups": "إعدادات الكاميرا",
    "post_departments": "أقسام ما بعد الإنتاج", "post_comments": "تعليقات ما بعد الإنتاج",
}

EVENT_LABELS = {
    "login": "تسجيل دخول", "screen": "فتح شاشة", "export": "تصدير ملف",
    "ai": "تشغيل ذكاء اصطناعي", "search": "بحث", "page": "فتح صفحة",
}

# الـ target بيتخزن بالإنجليزي (اسم التبويب أو الملف في الكود) عشان يفضل ثابت لو
# النص في الواجهة اتغيّر؛ العرض بيترجمه هنا — المستخدم بيقرا عربي.
TARGET_LABELS = {
    # تبويبات التطبيق
    "import": "إضافة سيناريو", "locations": "الأماكن", "characters": "الشخصيات",
    "props": "الإكسسوارات", "scenes": "المشاهد", "shots": "اللقطات",
    "reports": "التقارير النهائية", "schedule": "جدول التصوير", "post": "ما بعد الإنتاج",
    # شاشات الواجهة الجديدة
    "board": "جدول التصوير", "home": "الرئيسية", "team": "الفريق", "activity": "سجل النشاط",
    # ملفات التصدير
    "shot_list_excel": "تفريغ اللقطات (Excel)", "shot_list_word": "تفريغ اللقطات (Word)",
    "shot_list_pdf": "تفريغ اللقطات (PDF)", "characters_sheet_excel": "كشف الشخصيات",
    "general_breakdown_excel": "التفريغ العام", "locations_sheet_excel": "كشف أماكن التصوير",
    "props_sheet_excel": "كشف الإكسسوار", "post_report_excel": "تقرير ما بعد الإنتاج",
    # غير كده
    "script_analysis": "تحليل سيناريو", "streamlit": "التطبيق",
}


class AuditError(RuntimeError):
    pass


# --- السياق -------------------------------------------------------------------------

_CONTEXT = contextvars.ContextVar("cimafast_audit_ctx", default=None)
_COLLECTOR = contextvars.ContextVar("cimafast_audit_collector", default=None)
_DISABLED = contextvars.ContextVar("cimafast_audit_off", default=False)
_resolver = None


def _enabled():
    return not _DISABLED.get()


def set_resolver(fn):
    """Streamlit بيشغّل كل rerun في thread جديد، فالـ contextvar مابيعيشش بينهم —
    الدالة دي بتقرا السياق من session_state وقت الكتابة (زي permissions.set_resolver)."""
    global _resolver
    _resolver = fn


def set_context(**fields):
    """سياق الطلب الحالي (Starlette: كل طلب ليه context لوحده)."""
    _CONTEXT.set({k: v for k, v in fields.items() if v is not None})


@contextlib.contextmanager
def context(**fields):
    base = dict(_CONTEXT.get() or {})
    base.update({k: v for k, v in fields.items() if v is not None})
    token = _CONTEXT.set(base)
    try:
        yield
    finally:
        _CONTEXT.reset(token)


@contextlib.contextmanager
def disabled():
    """كتابة من غير تسجيل: النقل الأول من secrets.toml، والسكريبتات، والاختبارات.

    contextvar مش متغيّر عام: تشغيلة واحدة بتوقف السجل عن نفسها بس، مش عن
    باقي المستخدمين اللي شغالين في نفس اللحظة في threads تانية.
    """
    token = _DISABLED.set(True)
    try:
        yield
    finally:
        _DISABLED.reset(token)


def current_context():
    ctx = dict(_CONTEXT.get() or {})
    if _resolver is not None and not ctx.get("username"):
        try:
            resolved = _resolver() or {}
        except Exception:  # noqa: BLE001 — مفيش جلسة Streamlit في الـ thread ده
            resolved = {}
        for key, value in (resolved or {}).items():
            if value is not None:
                ctx.setdefault(key, value)
    return ctx


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


_company_cache = {}


def _company_of_project(project_id):
    """شركة المشروع — المشروع مابينتقلش من شركة لشركة، فالنتيجة بتتخزّن."""
    if project_id in _company_cache:
        return _company_cache[project_id]
    try:
        from database import fetch_all
        rows = fetch_all("SELECT company_id FROM projects WHERE id=?", (project_id,))
    except Exception:  # noqa: BLE001
        return None
    cid = rows[0]["company_id"] if rows else None
    if cid is not None:
        _company_cache[project_id] = cid
    return cid


def _resolved(ctx, project_id=None, company_id=None):
    """(اسم المستخدم، الشركة، المشروع، المصدر) بعد ما ناخد الناقص من السياق."""
    project = project_id if project_id is not None else ctx.get("project_id")
    company = company_id if company_id is not None else ctx.get("company_id")
    if company is None and project is not None:
        company = _company_of_project(project)
    return ctx.get("username"), company, project, ctx.get("source") or "app"


# --- قراءة الاستعلام (مين اتغيّر وإيه اللي اتغيّر) ---------------------------------------

_WRITE_RE = re.compile(
    r"^\s*(?:INSERT\s+(?:OR\s+IGNORE\s+)?INTO|UPDATE|DELETE\s+FROM)\s+([A-Za-z_][\w]*)", re.IGNORECASE)
_INSERT_COLS_RE = re.compile(r"^\s*INSERT\s+(?:OR\s+IGNORE\s+)?INTO\s+\w+\s*\(([^)]*)\)", re.IGNORECASE)
_SET_RE = re.compile(r"\bSET\b(.*?)(?:\bWHERE\b|$)", re.IGNORECASE | re.DOTALL)
_WHERE_RE = re.compile(r"\bWHERE\b(.*)$", re.IGNORECASE | re.DOTALL)


def _verb(sql):
    head = sql.lstrip()[:6].upper()
    if head.startswith("INSERT"):
        return "create"
    if head.startswith("UPDATE"):
        return "update"
    if head.startswith("DELETE"):
        return "delete"
    return None


_INSERT_VALUES_RE = re.compile(r"\bVALUES\s*\((.*)\)", re.IGNORECASE | re.DOTALL)


def _insert_exprs(sql):
    """التعبيرات اللي جوه VALUES(...) — «?, 1, ?» → ['?', '1', '?']."""
    m = _INSERT_VALUES_RE.search(sql)
    if not m:
        return []
    out, depth, buf = [], 0, ""
    for ch in m.group(1):
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                break
            depth -= 1
        if ch == "," and depth == 0:
            out.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        out.append(buf.strip())
    return out


def _split_assignments(set_part):
    """«a=?, b=COALESCE(b,?), c=?» → [(العمود، النص بتاع القيمة)] من غير ما الفاصلة
    اللي جوه دالة تقسم غلط."""
    out, depth, buf = [], 0, ""
    for ch in set_part:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        out.append(buf)
    pairs = []
    for chunk in out:
        if "=" not in chunk:
            continue
        col, _, expr = chunk.partition("=")
        pairs.append((col.strip().strip('"'), expr.strip()))
    return pairs


def _clean(value):
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return value
    text = str(value)
    return text[:MAX_VALUE_CHARS] + "…" if len(text) > MAX_VALUE_CHARS else text


def _is_secret(column):
    low = (column or "").lower()
    return any(h in low for h in _SECRET_HINTS)


def _redact(column, value):
    return "***" if _is_secret(column) else _clean(value)


def _new_values(sql, params, verb):
    """القيم الجديدة اللي الاستعلام بيكتبها، والـ params اللي تخص شرط WHERE."""
    params = list(params or [])
    if verb == "create":
        m = _INSERT_COLS_RE.match(sql)
        if not m:
            return {}, []
        cols = [c.strip().strip('"') for c in m.group(1).split(",")]
        values = {}
        exprs = _insert_exprs(sql)
        if exprs and len(exprs) == len(cols):
            # VALUES فيها قيم ثابتة مخلوطة بعلامات استفهام
            # («… (name, active, created_at) VALUES (?, 1, ?)»)، فالترتيب لوحده
            # بيزحلق القيم عمود. بنمشي على التعبيرات ونعدّ العلامات.
            used = 0
            for col, expr in zip(cols, exprs):
                if expr == "?":
                    if used < len(params):
                        values[col] = _redact(col, params[used])
                    used += 1
                elif "?" in expr:
                    values[col] = "?"
                    used += expr.count("?")
                else:
                    values[col] = _redact(col, expr.strip("'\""))
        else:
            for i, col in enumerate(cols):
                if i < len(params):
                    values[col] = _redact(col, params[i])
        return values, []
    if verb == "update":
        m = _SET_RE.search(sql)
        if not m:
            return {}, params
        set_part = m.group(1)
        used, values = 0, {}
        for col, expr in _split_assignments(set_part):
            marks = expr.count("?")
            if expr == "?" and used < len(params):
                values[col] = _redact(col, params[used])
            elif marks:
                values[col] = "?"          # تعبير مش قيمة مباشرة
            used += marks
        return values, params[used:]
    return {}, params                       # delete: كل الـ params في WHERE


def _before_row(cur, table, sql, where_params):
    """الصف زي ما كان قبل التعديل/الحذف — بنقراه بنفس شرط WHERE قبل التنفيذ.

    بيرجّع (الصف، عدد الصفوف اللي هتتأثر تقريبًا). لو الشرط معقّد أو الاستعلام
    من غير WHERE بنرجّع (None, None) وخلاص: السجل يفضل ناقص شوية أحسن ما العملية
    نفسها تقع.
    """
    m = _WHERE_RE.search(sql)
    if not m:
        return None, None
    where = m.group(1).strip().rstrip(";")
    from database import _adapt_query
    cur.execute(_adapt_query(f"SELECT * FROM {table} WHERE {where}"), tuple(where_params))
    rows = cur.fetchall()
    if not rows:
        return None, 0
    first = rows[0]
    return (dict(first) if hasattr(first, "keys") else first), len(rows)


class _Write:
    """اللي اتجمّع عن كتابة واحدة بين ما بنبص عليها وبين ما بنسجّلها."""

    __slots__ = ("table", "verb", "new", "before", "rows", "entity_id")

    def __init__(self, table, verb, new, before, rows, entity_id):
        self.table, self.verb, self.new = table, verb, new
        self.before, self.rows, self.entity_id = before, rows, entity_id


def watch(cur, sql, params=()):
    """قبل التنفيذ: بيقرا الحالة القديمة ويرجّع توكن يتبعت لـ record().

    بيرجّع None لما مفيش حاجة تتسجّل (قراءة، جدول مستثنى، أو إحنا جوه
    ``action()`` اللي بتلمّ كل حاجة في صف واحد).
    """
    if not _enabled():
        return None
    try:
        verb = _verb(sql)
        if not verb:
            return None
        m = _WRITE_RE.match(sql)
        if not m:
            return None
        table = m.group(1)
        if table in SKIP_TABLES:
            return None
        collector = _COLLECTOR.get()
        if collector is not None:
            collector.count(table, verb)
            return None
        new, where_params = _new_values(sql, params, verb)
        before, rows = (None, None)
        if verb in ("update", "delete"):
            try:
                before, rows = _before_row(cur, table, sql, where_params)
            except Exception:  # noqa: BLE001 — شرط مش متوقّع؛ نكمل من غير قيم قديمة
                before, rows = None, None
        entity_id = None
        if before and isinstance(before, dict):
            entity_id = before.get("id")
        return _Write(table, verb, new, before, rows, entity_id)
    except Exception as exc:  # noqa: BLE001
        _warn("watch", exc)
        return None


def record(cur, token, last_id=None):
    """بعد التنفيذ: بيكتب صف السجل على **نفس** الـ cursor، يعني جوه نفس الـ
    transaction بتاعت التغيير — يا الاتنين يتحفظوا يا ولا واحد فيهم."""
    if token is None or not _enabled():
        return
    try:
        entity_id = token.entity_id
        if entity_id is None:
            entity_id = last_id if last_id is not None else getattr(cur, "lastrowid", None)
        changes = _changes(token)
        if token.verb == "update" and changes is None:
            # حفظ من غير تغيير حقيقي (اليوزر داس حفظ من غير ما يعدّل حاجة).
            # لو سجّلناه، السجل هيبقى مليان صفوف "تعديل" مالهاش تعديل.
            return
        ctx = current_context()
        username, company, project, source = _resolved(ctx, project_id=_project_hint(token, ctx))
        _insert_audit(cur, {
            "at": _now(), "username": username, "company_id": company, "project_id": project,
            "entity": token.table, "entity_id": entity_id, "action": token.verb,
            "summary": _summary(token, entity_id), "changes": changes, "source": source,
        })
    except Exception as exc:  # noqa: BLE001
        _warn("record", exc)


def _project_hint(token, ctx):
    """المشروع من الصف نفسه لو السياق مش عارفه (سكريبت، worker)."""
    if ctx.get("project_id") is not None:
        return ctx["project_id"]
    for source in (token.new, token.before):
        if isinstance(source, dict) and source.get("project_id"):
            return source["project_id"]
    if token.table == "projects" and token.entity_id:
        return token.entity_id
    return None


def _changes(token):
    """JSON بالقيم القديمة والجديدة للأعمدة اللي اتغيّرت فعلًا."""
    out = {}
    if token.verb == "create":
        out = {"new": {k: v for k, v in token.new.items() if v is not None}}
    elif token.verb == "update":
        diff = {}
        for col, value in token.new.items():
            if _is_secret(col):
                # القيمة القديمة والجديدة الاتنين «***»، فالمقارنة هتقول "مفيش
                # تغيير" وهي فيه. بنسجّل إن العمود ده اتغيّر من غير أي قيمة.
                diff[col] = SECRET_CHANGED
                continue
            old = _redact(col, token.before.get(col)) if isinstance(token.before, dict) else None
            if old != value:
                diff[col] = {"from": old, "to": value}
        if not diff:
            return None                      # حفظ من غير تغيير حقيقي: مش حدث
        out = {"changed": diff}
    elif token.verb == "delete" and isinstance(token.before, dict):
        out = {"old": {k: _redact(k, v) for k, v in token.before.items() if v is not None}}
    if token.rows and token.rows > 1:
        out["rows"] = token.rows
    if not out:
        return None
    text = json.dumps(out, ensure_ascii=False)
    return text if len(text) <= MAX_CHANGES_CHARS else text[:MAX_CHANGES_CHARS] + "…"


def _summary(token, entity_id):
    label = ENTITY_LABELS.get(token.table, token.table)
    name = None
    for source in (token.new, token.before):
        if isinstance(source, dict):
            name = source.get("name") or source.get("username") or name
    where = f"«{name}»" if name else (f"#{entity_id}" if entity_id else "")
    return f"{ACTION_LABELS.get(token.verb, token.verb)} في {label} {where}".strip()


# --- الكتابة في الجدولين ----------------------------------------------------------------

_AUDIT_SQL = ("INSERT INTO audit_log (at, username, company_id, project_id, entity, entity_id, "
              "action, summary, changes, source, departments) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")


def _departments(entity, action, changes):
    """H4: الأقسام اللي الصف ده يخصّها. غلطة هنا بتسيب الصف من غير وسم، مش بتوقّعه."""
    try:
        import notify
        return notify.tag(entity, action, changes)
    except Exception as exc:  # noqa: BLE001
        _warn("departments", exc)
        return None
_USAGE_SQL = ("INSERT INTO usage_events (at, username, company_id, project_id, event, target, "
              "detail, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?)")


def _insert_audit(cur, row):
    from database import _adapt_query
    cur.execute(_adapt_query(_AUDIT_SQL), (
        row["at"], row["username"], row["company_id"], row["project_id"], row["entity"],
        row["entity_id"], row["action"], row["summary"], row["changes"], row["source"],
        _departments(row["entity"], row["action"], row["changes"])))


def _own_write(sql, values):
    """كتابة لوحدها (دخول، حدث استخدام) — اتصال خاص بيها، ومش بتعدّي على
    ``run_query`` عشان الصلاحيات ماتمنعهاش: دخول المشاهد لازم يتسجّل برضه."""
    from database import _adapt_query, get_connection
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(_adapt_query(sql), values)
        conn.commit()
    finally:
        conn.close()


def log(action, entity, entity_id=None, summary=None, changes=None,
        username=None, company_id=None, project_id=None, source=None, cur=None):
    """صف سجل بمعنى واضح (دخول، تغيير دور، استيراد سيناريو…)."""
    if not _enabled():
        return
    try:
        ctx = current_context()
        if username:
            ctx = dict(ctx, username=username)
        user, company, project, src = _resolved(ctx, project_id, company_id)
        changes_text = json.dumps(changes, ensure_ascii=False) if isinstance(changes, dict) else changes
        row = (_now(), user, company, project, entity, entity_id, action, summary,
               changes_text, source or src, _departments(entity, action, changes_text))
        if cur is not None:
            from database import _adapt_query
            cur.execute(_adapt_query(_AUDIT_SQL), row)
        else:
            _own_write(_AUDIT_SQL, row)
    except Exception as exc:  # noqa: BLE001
        _warn("log", exc)


def event(name, target=None, detail=None, username=None, company_id=None,
          project_id=None, source=None):
    """حدث استخدام: دخول، فتح شاشة، تصدير، تشغيل تحليل."""
    if not _enabled():
        return
    try:
        ctx = current_context()
        if username:
            ctx = dict(ctx, username=username)
        user, company, project, src = _resolved(ctx, project_id, company_id)
        _own_write(_USAGE_SQL, (
            _now(), user, company, project, name, target,
            json.dumps(detail, ensure_ascii=False) if isinstance(detail, dict) else detail,
            source or src))
    except Exception as exc:  # noqa: BLE001
        _warn("event", exc)


class _Collector:
    """بيعد الكتابات اللي جوه ``action()`` بدل ما يسجّل كل واحدة لوحدها.

    اللي جوه الـ with يقدر يكمّل الصف بحاجات مابتتعرفش غير بعد التنفيذ::

        with audit.action("project_create", "projects", ...) as act:
            act.entity_id = run_query(...)
    """

    def __init__(self, entity_id=None, summary=None, project_id=None, company_id=None):
        self.counts = {}
        self.entity_id, self.summary = entity_id, summary
        self.project_id, self.company_id = project_id, company_id
        self.extra = {}

    def count(self, table, verb):
        key = f"{ACTION_LABELS.get(verb, verb)} {ENTITY_LABELS.get(table, table)}"
        self.counts[key] = self.counts.get(key, 0) + 1


@contextlib.contextmanager
def action(name, entity, entity_id=None, summary=None, project_id=None,
           company_id=None, username=None, source=None):
    """بتلمّ كل الكتابات اللي جواها في صف سجل واحد.

    استيراد سيناريو فيه ١٤٣ مشهد بيكتب آلاف الصفوف؛ من غير ده السجل بيبقى
    مليان ضوضاء واللي بيدوّر على "مين مسح المشهد ده" مش هيلاقيه. بيتستعمل
    كمان في عمليات ليها معنى واضح (تغيير دور، حفظ جدول التصوير) عشان الصف
    يبقى مكتوب بلغة المستخدم مش بلغة الجداول.

    اللي بيتكتب في تفاصيل الصف هو ``act.extra`` بس — اللي الكود كتبه بلغة
    المستخدم. عدّاد الكتابات (``act.counts``) متاح للي عايزه (``act.extra =
    act.counts``)، بس مش بيتسجّل لوحده: في عملية زي الدخول، "تعديل الحسابات: ١"
    مش معلومة، دي طريقة الجداول مش لغة الناس.
    """
    if not _enabled():
        yield _Collector(entity_id, summary, project_id, company_id)
        return
    collector = _Collector(entity_id, summary, project_id, company_id)
    token = _COLLECTOR.set(collector)
    failed = False
    try:
        yield collector
    except Exception:
        failed = True                      # العملية وقعت: مفيش صف سجل لحاجة ماحصلتش
        raise
    finally:
        _COLLECTOR.reset(token)
        if not failed:
            changes = dict(collector.extra) if collector.extra else None
            log(name, entity, entity_id=collector.entity_id, summary=collector.summary,
                changes=changes, username=username, company_id=collector.company_id,
                project_id=collector.project_id, source=source)


def _warn(where, exc):
    print(f"[audit] {where}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)


# --- القراءة (شاشة سجل النشاط) ------------------------------------------------------

def _allowed_companies(actor):
    """الشركات اللي المستخدم ده يقدر يشوف سجلها — مدير الشركة لشركته، والمشغّل للكل.

    بيرجّع None يعني "كل الشركات" (المشغّل). لستة فاضية يعني مايشوفش حاجة.
    """
    import accounts
    import permissions
    me = accounts.user(actor) if actor else None
    if me and me["is_operator"]:
        return None
    return [c["id"] for c in accounts.companies_for(actor or "")
            if permissions.can(c["role"], "view_audit")]


def _scope(actor, company_id):
    """شرط SQL بيقفل النتيجة على شركات المستخدم — مفيش سجل بيعدّي الحدود دي."""
    import accounts
    allowed = _allowed_companies(actor)
    if allowed is None:                                   # المشغّل
        if company_id is None:
            return "1=1", []
        return "company_id = ?", [company_id]
    if not allowed:
        raise accounts.AccessDenied("سجل النشاط لمدير المشروع بس")
    if company_id is not None:
        if company_id not in allowed:
            raise accounts.AccessDenied("مش مدير مشروع في الحساب ده")
        return "company_id = ?", [company_id]
    marks = ",".join("?" * len(allowed))
    return f"company_id IN ({marks})", list(allowed)


def entries(actor, company_id=None, username=None, entity=None, action_name=None,
            project_id=None, since=None, text=None, limit=200):
    """صفوف سجل التدقيق اللي المستخدم ده مسموح له يشوفها، الأحدث الأول."""
    where, params = _scope(actor, company_id)
    clauses = [where]
    if username:
        clauses.append("username = ?")
        params.append(username)
    if entity:
        clauses.append("entity = ?")
        params.append(entity)
    if action_name:
        clauses.append("action = ?")
        params.append(action_name)
    if project_id is not None:
        clauses.append("project_id = ?")
        params.append(project_id)
    if since:
        clauses.append("at >= ?")
        params.append(since)
    if text:
        clauses.append("(summary LIKE ? OR changes LIKE ?)")
        params += [f"%{text}%", f"%{text}%"]
    from database import fetch_all
    params.append(max(1, min(int(limit), 1000)))
    return fetch_all(f"SELECT * FROM audit_log WHERE {' AND '.join(clauses)} "
                     f"ORDER BY at DESC, id DESC LIMIT ?", tuple(params))


def filters_for(actor, company_id=None):
    """القيم اللي فعلًا موجودة في سجل الشركة دي — عشان القوايم تبقى مفيدة."""
    where, params = _scope(actor, company_id)
    from database import fetch_all
    def _col(name):
        rows = fetch_all(f"SELECT DISTINCT {name} AS v FROM audit_log WHERE {where} AND {name} IS NOT NULL "
                         f"ORDER BY {name}", tuple(params))
        return [r["v"] for r in rows]
    return {"users": _col("username"), "entities": _col("entity"), "actions": _col("action")}


def usage_summary(actor, company_id=None, days=30):
    """تبنّي المنتج: كل حدث بيحصل كام مرة، وكام مستخدم عمله، في آخر كام يوم."""
    where, params = _scope(actor, company_id)
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=int(days))).isoformat(timespec="seconds")
    from database import fetch_all
    rows = fetch_all(
        f"SELECT event, target, COUNT(*) AS times, COUNT(DISTINCT username) AS people "
        f"FROM usage_events WHERE {where} AND at >= ? GROUP BY event, target "
        f"ORDER BY times DESC", tuple(params + [since]))
    people = fetch_all(
        f"SELECT COUNT(DISTINCT username) AS n FROM usage_events WHERE {where} AND at >= ?",
        tuple(params + [since]))
    return {"days": int(days), "since": since, "rows": rows,
            "active_users": (people[0]["n"] if people else 0)}


def usage_events(actor, company_id=None, event_name=None, days=30, limit=200):
    where, params = _scope(actor, company_id)
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=int(days))).isoformat(timespec="seconds")
    clauses = [where, "at >= ?"]
    params = params + [since]
    if event_name:
        clauses.append("event = ?")
        params.append(event_name)
    from database import fetch_all
    params.append(max(1, min(int(limit), 1000)))
    return fetch_all(f"SELECT * FROM usage_events WHERE {' AND '.join(clauses)} "
                     f"ORDER BY at DESC, id DESC LIMIT ?", tuple(params))
