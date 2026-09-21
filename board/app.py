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
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import accounts  # noqa: E402
import auth  # noqa: E402
import database  # noqa: E402
import home  # noqa: E402
import links  # noqa: E402
import permissions  # noqa: E402
import repo  # noqa: E402

SECRETS_PATH = Path(os.environ.get("CIMAFAST_SECRETS", "/etc/cimafast/secrets.toml"))
HERE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(HERE / "templates"))


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
    return auth.verify_session_token(request.cookies.get(auth.SESSION_COOKIE_NAME), users,
                                     secret=str(secret) if secret else None)


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
    if request.method != "GET" and not permissions.can(role, "edit"):
        return None, JSONResponse({"error": permissions.MESSAGES["edit"]}, status_code=403)
    return pid, None


# --- الصفحة --------------------------------------------------------------------

async def page(request: Request):
    user = current_user(request)
    if not user:
        return templates.TemplateResponse(request, "signin.html", {"app_url": "../"}, status_code=401)
    projects = accounts.projects_for(user)          # only the user's companies
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
        repo.save_layout(pid, [{"day_id": int(d["day_id"]), "scene_ids": [int(s) for s in d["scene_ids"]]}
                               for d in body.get("days", [])])
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
    return JSONResponse({"days": repo.apply_suggestion(pid, body.get("per_day", 8),
                                                     body.get("sites_per_day", 2))})


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
    return templates.TemplateResponse(request, "team.html", {
        "user": user, "companies": accounts.companies_for(user), "is_operator": bool(me and me["is_operator"]),
        "roles": [(r, accounts.ROLE_LABELS[r]) for r in accounts.ROLES]})


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

TOOL_GROUPS = [
    ("السيناريو", [("import", "📤", "إضافة سيناريو وتحليله", "ارفع الملف والذكاء الاصطناعي يطلّع المشاهد والأماكن والشخصيات")]),
    ("التفريغ", [("locations", "📍", "الأماكن", "كل مكان وحالاته وصوره ولينك الخريطة"),
                 ("characters", "🎭", "الشخصيات واللوكات", "الشخصيات وصورها وتغييرات اللوك"),
                 ("props", "🎒", "الإكسسوارات", "الإكسسوارات والراكور"),
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
    creatable = [c for c in companies if permissions.can(c["role"], "create_project")]
    return templates.TemplateResponse(request, "home.html", {
        "user": user, "me": me, "role_label": accounts.ROLE_LABELS.get(role, role),
        "companies": companies, "creatable": creatable, "cards": cards, "continue": cont,
        "needs": home.needs_you(role, me.get("job_title"), cards)[:12], "tools": tools,
        "focus": focus, "can_manage_team": any(permissions.can(c["role"], "manage_team") for c in companies),
        "static": HOME_STATIC, "app": HOME_APP, "board": HOME_BOARD})


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
    kind = b.get("project_type") or "فيلم"
    if not name:
        return JSONResponse({"error": "اسم المشروع مطلوب"}, status_code=400)
    if kind not in ("فيلم", "مسلسل", "إعلان", "فيديو قصير"):
        return JSONResponse({"error": "نوع مش معروف"}, status_code=400)
    try:
        pid = accounts.create_project(user, cid, name, kind, "1080p", "أفقي", "16:9")
    except (accounts.AccessDenied, permissions.Denied) as exc:
        return JSONResponse({"error": str(exc)}, status_code=403)
    return JSONResponse({"project_id": pid, "href": links.screen(HOME_APP, pid, "import")})


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
        Route("/api/projects", api_create_project, methods=["POST"]),
        # Location نسبي: Caddy شايل /v1/board، فـ "/team/" المطلق كان هيودّي على الإنتاج
        Route("/team", lambda request: RedirectResponse("team/", status_code=308)),
        Route("/team/", team_page),
        Route("/api/team", api_team, methods=["GET"]),
        Route("/api/team/members", api_team_add, methods=["POST"]),
        Route("/api/team/members/{username}", api_team_update, methods=["PATCH"]),
        Route("/api/team/members/{username}", api_team_remove, methods=["DELETE"]),
        Route("/api/team/members/{username}/reset", api_team_reset, methods=["POST"]),
        Route("/api/companies", api_company_create, methods=["POST"]),
        Route("/api/companies/rename", api_company_rename, methods=["POST"]),
        Route("/api/me/password", api_my_password, methods=["POST"]),
        Mount("/static", StaticFiles(directory=str(HERE / "static")), name="static"),
        Mount("/fonts", StaticFiles(directory=str(ROOT / "static" / "fonts")), name="fonts"),
    ],
    middleware=[Middleware(SameOriginWrites)],
    lifespan=lifespan,
)
