"""جدول التصوير (stripboard) — أول شاشة في الواجهة الجديدة.

Starlette مباشرةً (هي الأساس اللي FastAPI مبني عليه). متركّبة في نفس بيئة
Streamlit، فمفيش أي مكتبة جديدة: تثبيت FastAPI كان ممكن يرقّي Starlette من
تحت Streamlit ويكسر الإنتاج.

بتشتغل جنب تطبيق Streamlit مش مكانه: Caddy بيوجّه /v1/board/ هنا وباقي /v1/
لـ Streamlit، والاتنين على نفس قاعدة البيانات عن طريق repo.py.

الدخول مشترك: Streamlit بيحط كوكي cf_session موقّع على Path=/، والتطبيق ده
بيتحقق منه بنفس verify_session_token. اللي داخل هناك داخل هنا.

    uvicorn board.app:app --port 8503
"""

from __future__ import annotations

import contextlib
import os
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlparse

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import accounts  # noqa: E402
import analysis_library  # noqa: E402
import audit  # noqa: E402
import auth  # noqa: E402
import database  # noqa: E402
import home  # noqa: E402
import project_types  # noqa: E402
import links  # noqa: E402
import notify  # noqa: E402
import permissions  # noqa: E402
import repo  # noqa: E402
import videos  # noqa: E402

SECRETS_PATH = Path(os.environ.get("CIMAFAST_SECRETS", "/etc/cimafast/secrets.toml"))
HERE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(HERE / "templates"))


def _asset_version() -> str:
    """نسخة ثابتة وقت الإقلاع بس — بتتغيّر مع كل ديبلوي (commit جديد أو
    إعادة تشغيل) عشان أي كاش (متصفح أو بروكسي) يضطر ياخد نسخة جديدة من
    static/board.css وأخواتها بدل ما يفضل شايل نسخة قديمة بعد التحديث."""
    try:
        import subprocess

        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return str(int(Path(__file__).stat().st_mtime))


templates.env.globals["asset_version"] = _asset_version()


# --- الدخول -------------------------------------------------------------------

def _secrets():
    try:
        with open(SECRETS_PATH, "rb") as fh:
            return tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def current_user(request: Request):
    """اسم المستخدم من كوكي Streamlit، أو None.

    بيقرا secrets.toml في كل طلب عن قصد: لو حساب اتمسح أو السر اتغيّر، الجلسة
    بتقع فورًا من غير ما حد يعيد تشغيل الخدمة.
    """
    cfg = _secrets()
    secret = (os.environ.get("CIMAFAST_SESSION_SECRET")
              or (cfg.get("auth") or {}).get("cookie_secret") or cfg.get("SESSION_SECRET"))
    # F1: الحسابات من جدول users (نفس اللي Streamlit بيستخدمه)؛ secrets.toml
    # احتياطي بس قبل أول نقل.
    users = accounts.auth_users() or {auth.normalize_username(k): v
                                      for k, v in (cfg.get("users") or {}).items()}
    user = auth.verify_session_token(request.cookies.get(auth.SESSION_COOKIE_NAME), users,
                                     secret=str(secret) if secret else None)
    # F3: سياق السجل للطلب ده. كل طلب في Starlette ليه context لوحده، فمفيش
    # طلب بيشوف سياق طلب تاني حتى لو الاتنين شغالين في نفس اللحظة.
    audit.set_context(username=user, source="board")
    return user


class SameOriginWrites(BaseHTTPMiddleware):
    """أي طلب بيغيّر بيانات لازم يكون JSON وجاي من نفس الموقع.

    الكوكي SameSite=Lax بيمنع أغلب الـ CSRF، والشرطين دول بيقفلوا الباقي:
    فورم HTML من موقع تاني مبيقدرش يبعت application/json، والـ Origin بيتقارن
    بالـ Host.
    """

    async def dispatch(self, request, call_next):
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            origin = request.headers.get("origin")
            host = request.headers.get("x-forwarded-host") or request.headers.get("host")
            if origin and urlparse(origin).netloc != host:
                return JSONResponse({"error": "cross-origin write refused"}, status_code=403)
            if not request.headers.get("content-type", "").startswith("application/json"):
                return JSONResponse({"error": "JSON only"}, status_code=415)
        return await call_next(request)


def _need_user(request):
    user = current_user(request)
    if not user:
        return None, JSONResponse({"error": "not signed in"}, status_code=401)
    return user, None


def _project_id(request, body=None, user=None):
    """رقم المشروع من الطلب — وبس لو المستخدم عضو في الشركة اللي المشروع تبعها.

    مشروع شركة تانية بيرجّع 404 زي المشروع اللي مش موجود، عشان رقم مشروع مايكشفش
    إن فيه مشروع بالرقم ده عند شركة تانية.
    """
    raw = (body or {}).get("project_id") if body else request.query_params.get("project_id")
    try:
        pid = int(raw)
    except (TypeError, ValueError):
        return None, JSONResponse({"error": "project_id required"}, status_code=400)
    user = user or current_user(request)
    if not repo.project(pid) or not user or not accounts.can_access_project(user, pid):
        return None, JSONResponse({"error": "no such project"}, status_code=404)
    # F2: الدور في شركة المشروع بيحكم الطلب ده كله (repo بيرفض الكتابة لو مش مسموح)،
    # وأي طلب مش GET لازم يكون من حد يقدر يعدّل.
    role = accounts.project_role(user, pid)
    permissions.act_as(role)
    audit.set_context(username=user, project_id=pid, source="board")   # F3
    if request.method != "GET" and not permissions.can(role, "edit"):
        return None, JSONResponse({"error": permissions.MESSAGES["edit"]}, status_code=403)
    return pid, None


# --- الصفحة --------------------------------------------------------------------

async def page(request: Request):
    user = current_user(request)
    if not user:
        return templates.TemplateResponse(request, "signin.html", {"app_url": "../"}, status_code=401)
    projects = accounts.projects_for(user)          # only the user's companies
    audit.event("screen", target="board")           # F3: تبنّي الشاشات الجديدة
    return templates.TemplateResponse(request, "board.html", {"user": user, "projects": projects})


# --- الـ API -------------------------------------------------------------------

async def api_board(request: Request):
    _, err = _need_user(request)
    if err:
        return err
    pid, err = _project_id(request)
    if err:
        return err
    b = repo.board(pid)
    return JSONResponse({"project": repo.project(pid)["name"], "scenes": b["scenes"],
                         "days": b["days"], "unscheduled": b["unscheduled"],
                         "can_edit": permissions.can(permissions.current_role(), "edit")})


async def api_save(request: Request):
    _, err = _need_user(request)
    if err:
        return err
    body = await request.json()
    pid, err = _project_id(request, body)
    if err:
        return err
    try:
        # F3: حفظ الجدول بيمسح ويعيد كتابة كل المشاهد على الأيام. الصف المفيد هو
        # "فلان حفظ جدول التصوير" مش ٣٠٠ صف نقل مشهد.
        days = [{"day_id": int(d["day_id"]), "scene_ids": [int(s) for s in d["scene_ids"]]}
                for d in body.get("days", [])]
        with audit.action("schedule_save", "shooting_days", project_id=pid,
                          summary="حفظ جدول التصوير") as act:
            act.extra = {"أيام": len(days), "مشاهد متجدولة": sum(len(d["scene_ids"]) for d in days)}
            repo.save_layout(pid, days)
    except (repo.LayoutError, KeyError, TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)
    return JSONResponse({"ok": True})


async def api_add_day(request: Request):
    _, err = _need_user(request)
    if err:
        return err
    pid, err = _project_id(request, await request.json())
    if err:
        return err
    return JSONResponse({"day_number": repo.add_day(pid)})


async def api_update_day(request: Request):
    _, err = _need_user(request)
    if err:
        return err
    body = await request.json()
    pid, err = _project_id(request, body)
    if err:
        return err
    repo.update_day(pid, int(request.path_params["day_id"]), body.get("shoot_date"), body.get("notes"))
    return JSONResponse({"ok": True})


async def api_delete_day(request: Request):
    _, err = _need_user(request)
    if err:
        return err
    pid, err = _project_id(request, await request.json())
    if err:
        return err
    repo.delete_day(pid, int(request.path_params["day_id"]))
    return JSONResponse({"ok": True})


async def api_suggest(request: Request):
    _, err = _need_user(request)
    if err:
        return err
    body = await request.json()
    pid, err = _project_id(request, body)
    if err:
        return err
    with audit.action("schedule_suggest", "shooting_days", project_id=pid,
                      summary="اقتراح جدول تصوير") as act:
        days = repo.apply_suggestion(pid, body.get("per_day", 8), body.get("sites_per_day", 2))
        act.extra = {"أيام": len(days) if isinstance(days, list) else None}
    return JSONResponse({"days": days})


async def api_dood(request: Request):
    _, err = _need_user(request)
    if err:
        return err
    pid, err = _project_id(request)
    if err:
        return err
    return JSONResponse(repo.day_out_of_days(pid))


# --- الفريق (F1) -----------------------------------------------------------------
# مدير الشركة يضيف ناس ويغيّر أدوارهم ويصفّر كلمات السر ويشيل حد؛ أي حد يغيّر
# كلمة سره؛ مشغّل المنصة يضيف شركة. الصلاحيات كلها جوه accounts.py — هنا بس
# بنترجم AccessDenied لـ 403 وValueError لـ 400.

def _team_call(fn, *args):
    try:
        return fn(*args), None
    except accounts.AccessDenied as exc:
        return None, JSONResponse({"error": str(exc)}, status_code=403)
    except ValueError as exc:
        return None, JSONResponse({"error": str(exc)}, status_code=400)


def _company_id(request, body=None):
    raw = (body or {}).get("company_id") if body is not None else request.query_params.get("company_id")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


async def team_page(request: Request):
    user = current_user(request)
    if not user:
        return templates.TemplateResponse(request, "signin.html", {"app_url": "../../"}, status_code=401)
    me = accounts.user(user)
    companies = accounts.companies_for(user)
    audit.event("screen", target="team",
                company_id=next((c["id"] for c in companies), None))
    return templates.TemplateResponse(request, "team.html", {
        "user": user, "companies": companies, "is_operator": bool(me and me["is_operator"]),
        "roles": [(r, accounts.ROLE_LABELS[r]) for r in accounts.ROLES],
        "can_view_audit": any(permissions.can(c["role"], "view_audit") for c in companies)})


async def api_team(request: Request):
    user, err = _need_user(request)
    if err:
        return err
    cid = _company_id(request)
    rows, err = _team_call(accounts.members, user, cid)
    if err:
        return err
    return JSONResponse({"role": accounts.role_in(user, cid), "me": user,
                         "members": [dict(r) for r in rows]})


async def api_team_add(request: Request):
    user, err = _need_user(request)
    if err:
        return err
    b = await request.json()
    pw, err = _team_call(accounts.add_member, user, _company_id(request, b), b.get("username", ""),
                         b.get("display_name") or None, b.get("role", "department"),
                         b.get("job_title") or None, b.get("email") or None)
    return err or JSONResponse({"temp_password": pw})


async def api_team_update(request: Request):
    user, err = _need_user(request)
    if err:
        return err
    b = await request.json()
    _, err = _team_call(accounts.set_role, user, _company_id(request, b), request.path_params["username"],
                        b.get("role", ""))
    return err or JSONResponse({"ok": True})


async def api_team_reset(request: Request):
    user, err = _need_user(request)
    if err:
        return err
    b = await request.json()
    pw, err = _team_call(accounts.reset_password, user, _company_id(request, b),
                         request.path_params["username"])
    return err or JSONResponse({"temp_password": pw})


async def api_team_remove(request: Request):
    user, err = _need_user(request)
    if err:
        return err
    b = await request.json()
    _, err = _team_call(accounts.deactivate_member, user, _company_id(request, b),
                        request.path_params["username"])
    return err or JSONResponse({"ok": True})


async def api_company_rename(request: Request):
    user, err = _need_user(request)
    if err:
        return err
    b = await request.json()
    _, err = _team_call(accounts.rename_company, user, _company_id(request, b), b.get("name", ""))
    return err or JSONResponse({"ok": True})


async def api_company_create(request: Request):
    user, err = _need_user(request)
    if err:
        return err
    b = await request.json()
    out, err = _team_call(accounts.create_company, user, b.get("name", ""), b.get("admin_username", ""),
                          b.get("admin_display_name") or None, b.get("admin_email") or None)
    if err:
        return err
    return JSONResponse({"company_id": out[0], "temp_password": out[1]})


async def api_my_password(request: Request):
    user, err = _need_user(request)
    if err:
        return err
    b = await request.json()
    _, err = _team_call(accounts.change_own_password, user, b.get("old", ""), b.get("new", ""))
    return err or JSONResponse({"ok": True})


# --- الصفحة الرئيسية (H1) ----------------------------------------------------------
# Caddy بيوصّل /v1/home/ هنا كـ /home/ (uri strip_prefix /v1). الروابط كلها نسبية
# لـ /v1/home/: التطبيق "../"، جدول التصوير "../board/"، الفريق "../board/team/".
HOME_APP, HOME_BOARD, HOME_STATIC = "../", "../board/", "../board/static/"
# أصول البراند متركّبة على /board/brand (نفس مجلد تطبيق ستريمليت)
HOME_BRAND = "../board/brand/"

TOOL_GROUPS = [
    ("السيناريو", [("import", "📤", "إضافة سيناريو وتحليله", "ارفع الملف والذكاء الاصطناعي يطلّع المشاهد والأماكن والشخصيات")]),
    ("التفريغ", [("locations", "📍", "الأماكن", "كل مكان وحالاته وصوره ولينك الخريطة"),
                 ("characters", "🎭", "الشخصيات واللوكات", "الشخصيات وصورها وتغييرات اللوك"),
                 ("props", "🎒", "الإكسسوارات", "الإكسسوار: الكمية والمصدر والحالة"),
                 ("scenes", "📝", "المشاهد", "جدول المشاهد: داخلي/خارجي، ليل/نهار، المكان والشخصيات")]),
    ("اللقطات", [("shots", "🎥", "تفريغ اللقطات", "اللقطات لكل مشهد ومراجعتها")]),
    ("الجدولة", [("board", "🗓️", "جدول التصوير", "سحب وإفلات المشاهد على أيام التصوير، واقتراح جدول"),
                 ("dood", "👥", "أيام الممثلين (DOOD)", "كل ممثل بيشتغل أنهي أيام")]),
    ("التقارير", [("reports", "📊", "التقارير والتصدير", "Excel وWord وPDF، واللي لسه ناقص")]),
]


async def home_page(request: Request):
    user = current_user(request)
    if not user:
        return templates.TemplateResponse(request, "signin.html", {"app_url": HOME_APP}, status_code=401)
    me = accounts.user(user) or {}
    companies = accounts.companies_for(user)
    cards = home.cards(user, HOME_APP, HOME_BOARD)
    cont = home.continue_link(user, HOME_APP)
    # الدور اللي بيحكم "محتاجك": الأعلى بين شركات المستخدم (الأغلب شركة واحدة)
    rank = {r: i for i, r in enumerate(("operator", "admin", "producer", "manager", "department", "viewer"))}
    role = min((c["role"] for c in companies), key=lambda r: rank.get(r, 99), default="viewer")
    focus = next((c for c in cards if cont and c["name"] == cont["project"]), cards[0] if cards else None)
    tools = []
    for group, items in TOOL_GROUPS:
        row = []
        for key, icon, title, desc in items:
            if not focus:
                href = None
            elif key == "board":
                href = focus["board_href"]
            elif key == "dood":
                href = focus["board_href"] + "#dood"
            else:
                href = links.screen(HOME_APP, focus["id"], key)
            row.append({"icon": icon, "title": title, "desc": desc, "href": href})
        tools.append((group, row))
    audit.event("screen", target="home", company_id=next((c["id"] for c in companies), None))
    creatable = [c for c in companies if permissions.can(c["role"], "create_project")]
    # مكتبة التحليلات: عدد التحليلات المحفوظة على الحساب. غلطة هنا ماتوقّعش الرئيسية.
    try:
        library_count = analysis_library.count_for(user)
    except Exception as exc:  # noqa: BLE001
        print(f"[home] library count: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        library_count = 0
    # دايرة الأفتار: مفيش صور حسابات في البرنامج لسه (زي قرار الشريط
    # الجانبي بالظبط) — أحرف أولى من الاسم بدل صورة، مش هاش عشوائي.
    _display_name = (me.get("display_name") or user or "?").strip()
    initials = "".join(w[0] for w in _display_name.split()[:2]).upper() or "?"
    return templates.TemplateResponse(request, "home.html", {
        "user": user, "me": me, "initials": initials, "role_label": accounts.ROLE_LABELS.get(role, role),
        "companies": companies, "creatable": creatable, "cards": cards, "continue": cont,
        "needs": home.needs_you(role, me.get("job_title"), cards)[:12], "tools": tools,
        "focus": focus, "library_count": library_count, "can_manage_team": any(permissions.can(c["role"], "manage_team") for c in companies),
        "static": HOME_STATIC, "app": HOME_APP, "board": HOME_BOARD,
        "brand": HOME_BRAND})


# --- التنبيهات (H4) -----------------------------------------------------------------
# الروابط جوه كل تنبيه محسوبة من مكان الصفحة الرئيسية (‎/v1/home/‎)، زي كروت
# المشاريع بالظبط — الجرس في الرئيسية بس.

async def api_notifications(request: Request):
    user, err = _need_user(request)
    if err:
        return err
    feed = notify.feed(user, HOME_APP, HOME_BOARD)
    for item in feed["items"]:
        item["ago"] = notify.ago(item["at"])
    return JSONResponse(feed)


async def api_notifications_seen(request: Request):
    user, err = _need_user(request)
    if err:
        return err
    body = await request.json()
    try:
        up_to = int(body.get("up_to"))
    except (TypeError, ValueError, AttributeError):
        return JSONResponse({"error": "up_to required"}, status_code=400)
    notify.mark_seen(user, up_to)
    return JSONResponse({"ok": True, "unread": notify.unread_count(user)})


async def api_search(request: Request):
    user, err = _need_user(request)
    if err:
        return err
    return JSONResponse({"results": home.search(user, request.query_params.get("q", ""), HOME_APP)})


async def api_create_project(request: Request):
    user, err = _need_user(request)
    if err:
        return err
    b = await request.json()
    try:
        cid = int(b.get("company_id"))
    except (TypeError, ValueError):
        return JSONResponse({"error": "company_id required"}, status_code=400)
    name = (b.get("name") or "").strip()
    kind = project_types.normalize_type(b.get("project_type") or "فيلم")
    if not name:
        return JSONResponse({"error": "اسم المشروع مطلوب"}, status_code=400)
    if kind not in project_types.TYPES:
        return JSONResponse({"error": "نوع مش معروف"}, status_code=400)
    episodes = None
    if kind == project_types.SERIES:
        # المسلسل مايتعملش من غير عدد حلقاته (طلب المالك 2026-09-24)
        try:
            episodes = int(b.get("episode_count"))
        except (TypeError, ValueError):
            episodes = 0
        if not 1 <= episodes <= 500:
            return JSONResponse({"error": "اكتب عدد حلقات المسلسل"}, status_code=400)
    res, orient, ratio = project_types.technical_defaults(kind)
    try:
        pid = accounts.create_project(user, cid, name, kind, res, orient, ratio, episode_count=episodes,
                                      add_all_members=bool(b.get("add_all_members")))
    except (accounts.AccessDenied, permissions.Denied) as exc:
        return JSONResponse({"error": str(exc)}, status_code=403)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse({"project_id": pid, "href": links.screen(HOME_APP, pid, "import")})


# --- سجل النشاط (F3) --------------------------------------------------------------
# مدير الشركة بيشوف نشاط شركته بس، والمشغّل بيشوف الكل — الفلترة نفسها جوه
# audit.py (دالة _scope)، فمفيش استعلام هنا بيقدر يتخطّاها.

def _audit_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs), None
    except accounts.AccessDenied as exc:
        return None, JSONResponse({"error": str(exc)}, status_code=403)
    except (TypeError, ValueError) as exc:
        return None, JSONResponse({"error": str(exc)}, status_code=400)


async def activity_page(request: Request):
    user = current_user(request)
    if not user:
        return templates.TemplateResponse(request, "signin.html", {"app_url": "../../"}, status_code=401)
    companies = [c for c in accounts.companies_for(user) if permissions.can(c["role"], "view_audit")]
    me = accounts.user(user) or {}
    if me.get("is_operator"):
        companies = accounts.companies_for(user)
    if not companies:
        return templates.TemplateResponse(request, "activity.html", {
            "user": user, "companies": [], "denied": True, "actions": [], "entities": []},
            status_code=403)
    audit.event("screen", target="activity", company_id=companies[0]["id"])
    return templates.TemplateResponse(request, "activity.html", {
        "user": user, "companies": companies, "denied": False,
        "action_labels": audit.ACTION_LABELS, "entity_labels": audit.ENTITY_LABELS,
        "event_labels": audit.EVENT_LABELS})


def _int_or_none(raw):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


async def api_activity(request: Request):
    user, err = _need_user(request)
    if err:
        return err
    q = request.query_params
    out, err = _audit_call(
        audit.entries, user, company_id=_int_or_none(q.get("company_id")),
        username=q.get("user") or None, entity=q.get("entity") or None,
        action_name=q.get("action") or None, project_id=_int_or_none(q.get("project_id")),
        since=q.get("since") or None, text=q.get("q") or None,
        limit=_int_or_none(q.get("limit")) or 200)
    if err:
        return err
    filters, err = _audit_call(audit.filters_for, user, _int_or_none(q.get("company_id")))
    if err:
        return err
    names = {p["id"]: p["name"] for p in accounts.projects_for(user)}
    rows = [dict(r, project_name=names.get(r["project_id"])) for r in out]
    return JSONResponse({"rows": rows, "filters": filters,
                         "action_labels": audit.ACTION_LABELS,
                         "entity_labels": audit.ENTITY_LABELS})


async def api_usage(request: Request):
    user, err = _need_user(request)
    if err:
        return err
    q = request.query_params
    out, err = _audit_call(audit.usage_summary, user, _int_or_none(q.get("company_id")),
                           _int_or_none(q.get("days")) or 30)
    if err:
        return err
    return JSONResponse(dict(out, event_labels=audit.EVENT_LABELS,
                             target_labels=audit.TARGET_LABELS))


# --- البروفايل العام للممثل (P9، من غير دخول) ----------------------------------
# هنا مش في Streamlit عشان صفحة HTML حقيقية بتقدر تحط Open Graph: واتساب وفيسبوك
# بيعرضوا الاسم والصورة في معاينة اللينك. الحقول المسموحة كلها في public_profile.py.
# PUBLIC_BOARD_URL: المسار اللي Caddy بيوصّل بيه للتطبيق ده من برّه (بيشيله قبل
# ما الطلب يوصل)، محتاجينه عشان og:image لازم يبقى رابط مطلق.
PUBLIC_BOARD_URL = os.environ.get("CIMAFAST_BOARD_URL", "/v1/board/")
# CSP: مفيش سكريبت من برّه، والـ iframe بس من خدمات الفيديو المعروفة (videos.EMBED_HOSTS).
# Referrer: الأصل بس (من غير التوكن) — يوتيوب بيرفض التضمين لو مفيش origin خالص.
_PUBLIC_HEADERS = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex",
                   "X-Content-Type-Options": "nosniff",
                   "Referrer-Policy": "strict-origin-when-cross-origin",
                   "Content-Security-Policy": (
                       "default-src 'none'; img-src 'self' data:; font-src 'self'; "
                       "style-src 'unsafe-inline'; script-src 'unsafe-inline'; media-src https:; "
                       "frame-src " + " ".join(videos.EMBED_HOSTS) + "; "
                       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")}


def _public_url(request, token):
    host = request.headers.get("host", "")
    return f"{request.url.scheme}://{host}{PUBLIC_BOARD_URL.rstrip('/')}/p/{token}"


async def public_actor_page(request: Request):
    import public_profile
    token = request.path_params["token"]
    lang = "en" if request.query_params.get("lang") == "en" else "ar"
    actor = repo.actor_by_public_token(token)
    if not actor:
        # نفس الرد لتوكن غلط أو اتلغى أو ممثل اتمسح — مفيش فرق يكشف حاجة
        return HTMLResponse(public_profile.render_not_found(lang, asset_base="../"),
                            status_code=404, headers=_PUBLIC_HEADERS)
    url = _public_url(request, token)
    view = public_profile.public_view(actor)
    page = public_profile.render_page(
        view, lang, photo_url=f"{url}/photo", share_url=url,
        lang_switch_url="?lang=ar" if lang == "en" else "?lang=en", asset_base="../")
    return HTMLResponse(page, headers=_PUBLIC_HEADERS)


async def public_actor_photo(request: Request):
    """صورة الممثل صاحب التوكن ده بس. مفيش أي جزء من المسار جاي من الطلب."""
    import public_profile
    actor = repo.actor_by_public_token(request.path_params["token"])
    path = public_profile.photo_file(actor) if actor else None
    if not path:
        return HTMLResponse("", status_code=404, headers=_PUBLIC_HEADERS)
    return FileResponse(path, media_type=public_profile.photo_media_type(path), headers=_PUBLIC_HEADERS)


async def healthz(request: Request):
    """بيلمس قاعدة البيانات فعلًا — 200 من غير ما يوصل للبيانات مايثبتش حاجة."""
    try:
        database.fetch_all("SELECT 1 AS ok")
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=503)
    return JSONResponse({"ok": True})


@contextlib.asynccontextmanager
async def lifespan(app):
    database.init_db()          # بيضيف جداول الجدول لو مش موجودة، ومش بيلمس غيرها
    yield


app = Starlette(
    routes=[
        Route("/", page),
        Route("/healthz", healthz),
        Route("/p/{token:str}", public_actor_page, methods=["GET"]),
        Route("/p/{token:str}/photo", public_actor_photo, methods=["GET"]),
        Route("/api/board", api_board, methods=["GET"]),
        Route("/api/board", api_save, methods=["PUT"]),
        Route("/api/days", api_add_day, methods=["POST"]),
        Route("/api/days/{day_id:int}", api_update_day, methods=["PATCH"]),
        Route("/api/days/{day_id:int}", api_delete_day, methods=["DELETE"]),
        Route("/api/suggest", api_suggest, methods=["POST"]),
        Route("/api/dood", api_dood, methods=["GET"]),
        Route("/home", lambda request: RedirectResponse("home/", status_code=308)),
        Route("/home/", home_page),
        Route("/api/search", api_search, methods=["GET"]),
        Route("/api/notifications", api_notifications, methods=["GET"]),
        Route("/api/notifications/seen", api_notifications_seen, methods=["POST"]),
        Route("/api/projects", api_create_project, methods=["POST"]),
        # Location نسبي: Caddy شايل /v1/board، فـ "/team/" المطلق كان هيودّي على الإنتاج
        Route("/team", lambda request: RedirectResponse("team/", status_code=308)),
        Route("/team/", team_page),
        Route("/api/team", api_team, methods=["GET"]),
        Route("/api/team/members", api_team_add, methods=["POST"]),
        Route("/api/team/members/{username}", api_team_update, methods=["PATCH"]),
        Route("/api/team/members/{username}", api_team_remove, methods=["DELETE"]),
        Route("/api/team/members/{username}/reset", api_team_reset, methods=["POST"]),
        # F3: سجل النشاط وتحليلات الاستخدام
        Route("/activity", lambda request: RedirectResponse("activity/", status_code=308)),
        Route("/activity/", activity_page),
        Route("/api/activity", api_activity, methods=["GET"]),
        Route("/api/usage", api_usage, methods=["GET"]),
        Route("/api/companies", api_company_create, methods=["POST"]),
        Route("/api/companies/rename", api_company_rename, methods=["POST"]),
        Route("/api/me/password", api_my_password, methods=["POST"]),
        Mount("/static", StaticFiles(directory=str(HERE / "static")), name="static"),
        Mount("/fonts", StaticFiles(directory=str(ROOT / "static" / "fonts")), name="fonts"),
        # أصول البراند (اللوجو والأيقونة) — نفس المجلد اللي تطبيق ستريمليت
        # بيقرا منه، عشان تفضل نسخة واحدة على الديسك مش اتنين يتفرقوا بعدين
        Mount("/brand", StaticFiles(directory=str(ROOT / "static" / "brand")), name="brand"),
    ],
    middleware=[Middleware(SameOriginWrites)],
    lifespan=lifespan,
)
