import os
import re
import sys
import time
import uuid
import json
import datetime
import streamlit as st
import pandas as pd
import streamlit.components.v1 as st_components
from auth import (
    authenticate, no_login_allowed, resolve_users,
    make_session_token, verify_session_token, SESSION_COOKIE_NAME,
)
from search import matches
from importer import DEFAULT_VARIANT
from database import (
    scene_label,
    next_free_number,
    init_db, FIELD_HELP,
    fetch_all, run_query, run_delete,
    CAMERA_MOVEMENT_OPTIONS, SHOT_SIZE_OPTIONS, CAMERA_ANGLE_OPTIONS,
    SPECIES_OPTIONS, GENDER_OPTIONS, PROJECT_ROLE_OPTIONS, INT_EXT_OPTIONS,
    INT_EXT_LABELS, DAY_NIGHT_OPTIONS, DAY_NIGHT_LABELS, bilingual_label,
)
from ai_prompt import AI_JSON_PROMPT
import ai_jobs
import image_gen
from script_md import to_markdown
from script_parser import (
    extract_lines, parse_json_script, looks_like_screenplay,
    parse_script, find_similar_name_groups, apply_character_merges,
    find_similar_location_groups, apply_location_merges,
    find_location_matches_with_states,
)
from importer import import_parsed_scenes
import theme
from export import (
    build_shot_list_excel, build_shot_list_word, build_shot_list_pdf,
    build_characters_sheet_excel, build_general_breakdown_excel, build_locations_sheet_excel,
    build_props_sheet_excel,
)

from i18n import t, tr
from ui import ltr, mark_saved, safe_index, show_saved_badge
import views.import_tab, views.locations, views.characters, views.props, views.scenes, views.shots, views.reports

st.set_page_config(page_title="CimaFast Studio", page_icon="🎬", layout="wide")

# الشكل: النسخة الافتراضية classic، و‎?theme=glass‎ بيشغّل التصميم الجديد.
# كل الـ CSS بقى في حزمة theme/ — مكان واحد بدل تلاتة.
_theme_variant = theme.resolve_variant(st)
theme.inject_base(st, _theme_variant, lang=st.session_state.get("ui_lang", "ar"))


def _render_locked_screen():
    """شاشة القفل لما مفيش حسابات متظبطة — بنقفل الباب ونقول للمسؤول السبب."""
    st.markdown(
        "<h2 style='text-align:center; margin-top:15vh;'>🎬 CimaFast Studio</h2>"
        "<p dir='auto' style='text-align:center; font-size:1.1rem;'>"
        "🔒 الدخول مقفول: مفيش حسابات متظبطة على السيرفر."
        "<br>Access locked: no user accounts are configured.</p>"
        "<p dir='auto' style='text-align:center; opacity:0.7;'>"
        "المسؤول لازم يظبط قسم [users] في ملف الأسرار وبعدين يعيد تشغيل الخدمة."
        "<br>An administrator must set the [users] section in secrets.toml "
        "and restart the service.</p>",
        unsafe_allow_html=True,
    )


def _set_session_cookie(token):
    """بيحط توكن الجلسة في كوكي بالمتصفح (30 يوم) عشان المستخدم يفضل داخل
    حتى بعد ريفريش أو نشر تحديث جديد للبرنامج. مفيش API جاهزة في Streamlit
    لكتابة كوكي، فبنعملها بسطر JS صغير."""
    st.html(
        f"<script>document.cookie="
        f"'{SESSION_COOKIE_NAME}={token}; Max-Age={30*24*60*60}; Path=/; SameSite=Lax; Secure';"
        f"</script>",
        unsafe_allow_javascript=True,
    )


def _clear_session_cookie():
    st.html(
        f"<script>document.cookie="
        f"'{SESSION_COOKIE_NAME}=; Max-Age=0; Path=/; SameSite=Lax; Secure';"
        f"</script>",
        unsafe_allow_javascript=True,
    )


def _render_login_screen():
    """شاشة تسجيل الدخول: اسم مستخدم + كلمة سر.

    بتظهر قبل ما نعرف لغة الواجهة، فالتسميات مكتوبة بالعربي والإنجليزي مع
    بعض. الاتجاه RTL عشان العربي هو الأساس، بس خانات الإدخال نفسها LTR لأن
    اسم المستخدم وكلمة السر بالإنجليزي."""
    theme.inject_login(st, _theme_variant)
    st.markdown(
        """
        <div class="cf-login" dir="rtl">
            <h2>🎬 CimaFast Studio</h2>
            <p>تسجيل الدخول / Sign in</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        st.session_state["_signup_mode"] = False
        
        # فورم عشان زرار Enter في الموبايل يبعت من غير ما المستخدم يدوّر على الزرار
        with st.form("_login_form", clear_on_submit=False):
            username = st.text_input("اسم المستخدم / Username", key="_login_username")
            password = st.text_input(
                "كلمة السر / Password", type="password", key="_login_password"
            )
            submitted = st.form_submit_button("دخول / Log in", use_container_width=True)
        if submitted:
            user = authenticate(username, password, resolve_users())
            if user:
                st.session_state["_authenticated"] = True
                st.session_state["_auth_user"] = user
                st.session_state.pop("_login_attempts", None)
                # الكوكي بيتحط في الـ run الجاي (مش هنا) عشان لو حطيناها قبل
                # st.rerun() مباشرة، الصفحة بتتغير قبل ما المتصفح ياخد فرصة
                # ينفّذ السكريبت اللي بيحط الكوكي فعليًا
                st.session_state["_pending_session_cookie"] = make_session_token(user)
                st.rerun()
            # تأخير بسيط ومتزايد بعد كل محاولة فاشلة عشان نصعّب التخمين الآلي
            attempts = st.session_state.get("_login_attempts", 0) + 1
            st.session_state["_login_attempts"] = attempts
            if attempts > 2:
                time.sleep(min(attempts - 2, 4) * 0.5)
            st.error("اسم المستخدم أو كلمة السر غلط / Wrong username or password")


def _check_login():
    """بوابة الدخول. بترجّع True بس لما يكون فيه مستخدم داخل فعلًا."""
    # لو المستخدم لسه خارج (Log out) دلوقتي، لازم نمسح كوكي الجلسة فعليًا
    # في المتصفح، ونتجاهل قيمتها القديمة في الـ run ده بالذات (لسه وصلت
    # مع نفس الطلب اللي جبنا بيه الصفحة، قبل ما سكريبت المسح يتنفذ فعلًا)
    just_logged_out = st.session_state.pop("_just_logged_out", False)
    if just_logged_out:
        _clear_session_cookie()
    if st.session_state.get("_authenticated") and st.session_state.get("_auth_user"):
        return True
    users = resolve_users()
    # جلسة جديدة (ريفريش أو بعد نشر تحديث) - نشوف لو فيه كوكي دخول ساري
    # قبل ما نعرض شاشة تسجيل الدخول من الأول
    if users and not just_logged_out:
        cookie_token = st.context.cookies.get(SESSION_COOKIE_NAME)
        remembered_user = verify_session_token(cookie_token, users)
        if remembered_user:
            st.session_state["_authenticated"] = True
            st.session_state["_auth_user"] = remembered_user
            return True
    if not users:
        # مفيش حسابات: بنقفل افتراضيًا (fail closed). الاستثناء الوحيد هو
        # التطوير المحلي لما المطور يطلب كده صراحةً بالمتغير ده.
        if no_login_allowed():
            st.warning(
                "⚠️ البرنامج شغال من غير تسجيل دخول (وضع التطوير المحلي) — "
                "متستخدمش الإعداد ده على سيرفر منشور.\n\n"
                "Running without login (local development mode) — "
                "do not use this on a deployed server."
            )
            return True
        print(
            "[auth] no user accounts configured — locking the app. "
            "Set a [users] section in secrets.toml, "
            "or CIMAFAST_ALLOW_NO_PASSWORD=1 for local dev.",
            file=sys.stderr,
            flush=True,
        )
        _render_locked_screen()
        return False
    _render_login_screen()
    return False


def _logout():
    """خروج: بنمسح مفاتيح الدخول بس وسايبين باقي حالة الجلسة زي ما هي عشان
    المستخدم ميخسرش اختياراته لو رجع دخل تاني."""
    for key in ("_authenticated", "_auth_user", "_login_attempts"):
        st.session_state.pop(key, None)
    st.session_state["_just_logged_out"] = True


if not _check_login():
    st.stop()

_pending_cookie_token = st.session_state.pop("_pending_session_cookie", None)
if _pending_cookie_token:
    _set_session_cookie(_pending_cookie_token)

init_db()

if "ui_lang" not in st.session_state:
    st.session_state["ui_lang"] = "ar"
_is_ar = st.session_state["ui_lang"] == "ar"
_dir = "rtl" if _is_ar else "ltr"
_text_align = "right" if _is_ar else "left"
# شريط أدوات Streamlit نفسه (Deploy + قائمة الثلاث نقط) بيتلف عاديًا من
# غير ما يتبع اتجاه اللغة، فبنعكس ترتيبه بس وقت العربي عشان يطلع في الناحية
# المقابلة (شمال) بدل ما يتلخبط مع الشريط الجانبي اللي بيبقى يمين
_toolbar_row_dir = "row-reverse" if _is_ar else "row"





















_APP_DESCRIPTION = (
    "البرنامج ده بيساعدك تجهز وتنظم بيانات الإنتاج كلها (الأماكن، الشخصيات، المشاهد، تفريغ اللقطات) "
    "وتتأكد إنها متكاملة وجاهزة. مفيش مرحلة توليد فيديو فعلي بالذكاء الاصطناعي جوه البرنامج ده لسه — "
    "دي خطوة مستقبلية محتاجة تطوير إضافي لربطها بأدوات التوليد."
)

theme.inject_main(
    st,
    _theme_variant,
    dir_=_dir,
    align=_text_align,
    rowdir=_toolbar_row_dir,
)

# ---------------- دوال مساعدة للتعامل مع قاعدة البيانات ----------------
# ملحوظة: fetch_all / run_query / run_delete بقوا متعرّفين مركزيًا في
# database.py (مستوردين فوق) عشان يقدروا يشتغلوا مع SQLite محليًا أو
# Postgres/Supabase وقت النشر أونلاين من غير ما app.py يهتم بالاختلاف.





















# ---------------- تخزين الصور المرجعية (لوكاشنز، لوكات الشخصيات، ستوري بورد اللقطات) ----------------




















# ---------------- الشريط الجانبي: اختيار / إنشاء مشروع ----------------

_lang_col1, _lang_col2 = st.sidebar.columns(2)
with _lang_col1:
    if st.button("EN", use_container_width=True, disabled=st.session_state["ui_lang"] == "en", key="lang_btn_en"):
        st.session_state["ui_lang"] = "en"
        st.rerun()
with _lang_col2:
    if st.button("AR", use_container_width=True, disabled=st.session_state["ui_lang"] == "ar", key="lang_btn_ar"):
        st.session_state["ui_lang"] = "ar"
        st.rerun()

# المستخدم الحالي وزرار الخروج (بيظهر بس لما يكون فيه تسجيل دخول فعلي)
_current_user = st.session_state.get("_auth_user")
if _current_user:
    st.sidebar.caption(f"{tr('logged_in_as')}: {_current_user}")
    if st.sidebar.button(tr("logout"), use_container_width=True, key="logout_btn"):
        _logout()
        st.rerun()

st.sidebar.markdown(
    f"""
    <div class="cf-sidebar-header">
        <div class="cf-title">🎬 CimaFast Studio</div>
        <div class="cf-subtitle">{tr('studio_tagline')}</div>
        <div class="cf-desc-box">{t(_APP_DESCRIPTION)}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.caption(tr("sidebar_projects"))

projects = fetch_all("SELECT * FROM projects ORDER BY id DESC")
project_names = {p["name"]: p["id"] for p in projects}

with st.sidebar.expander(tr("new_project")):
    new_name = st.text_input(t("اسم المشروع"), placeholder=t("مثال: عروسة البحر"))
    new_type = st.selectbox(t("نوع المشروع"), ["فيلم", "مسلسل", "إعلان", "فيديو قصير"], format_func=t, help=FIELD_HELP["project_type"])
    new_res = st.selectbox(t("الدقة الافتراضية"), ["720p", "1080p", "2K", "4K"], help=FIELD_HELP["default_resolution"])
    new_orient = st.selectbox(t("الاتجاه الافتراضي"), ["أفقي", "رأسي", "مربع"], format_func=t, help=FIELD_HELP["default_orientation"])
    new_ratio = st.selectbox(t("نسبة الأبعاد الافتراضية"), ["4:5", "16:9", "9:16", "1:1", "4:3", "21:9"], index=0)
    if st.button(t("إنشاء المشروع")):
        if new_name.strip():
            run_query(
                "INSERT INTO projects (name, project_type, default_resolution, default_orientation, default_aspect_ratio) VALUES (?,?,?,?,?)",
                (new_name, new_type, new_res, new_orient, new_ratio),
            )
            st.success(t("تم إنشاء المشروع"))
            st.rerun()
        else:
            st.warning(t("اكتب اسم المشروع أولًا"))

if not projects:
    st.info(t("ابدأ بإنشاء مشروع جديد من القائمة الجانبية"))
    st.stop()

selected_project_name = st.sidebar.selectbox(tr("select_project"), list(project_names.keys()), key="project_selector")
project_id = project_names[selected_project_name]
project = fetch_all("SELECT * FROM projects WHERE id=?", (project_id,))[0]

# لو المستخدم بدّل المشروع، لازم نمسح أي معاينة سكريبت لسه واقفة من غير
# تأكيد، عشان ميحصلش استيراد مشاهد بالغلط لمشروع تاني
if st.session_state.get("parsed_script_project_id") != project_id:
    # كل نتيجة تحليل مربوطة بمشروع واحد. لو اليوزر بدّل المشروع لازم نمسحها
    # كلها — النتيجة السريعة ونتيجة الذكاء الاصطناعي ومتابعة الشغل الجاري —
    # وإلا تحليل مشروع بيظهر في مشروع تاني ويتستورد فيه بالغلط.
    for _k in ("parsed_script", "ai_parsed_script", "ai_job_id",
               "last_analysis", "_ai_pending", "_which_analysis"):
        st.session_state.pop(_k, None)
    st.session_state["parsed_script_project_id"] = project_id

# Episodes section (للمسلسلات)
if project["project_type"] == "مسلسل":
    # العنوان كان نص ثنائي ثابت (عربي + إنجليزي) مبيعديش على t() — وفي الواجهة
    # الإنجليزي الكلمة العربية كانت بتترسم مكسّرة جوه سطر LTR.
    with st.sidebar.expander(f"🎬 {t('الحلقات')}"):
        episodes = fetch_all("SELECT * FROM episodes WHERE project_id=? ORDER BY episode_number", (project_id,))
        
        st.subheader(t("إنشاء حلقة جديدة"))
        new_ep_num = st.number_input(t("رقم الحلقة"), min_value=1, value=len(episodes)+1, key=f"new_ep_num_{project_id}")
        new_ep_title = st.text_input(t("عنوان الحلقة"), key=f"new_ep_title_{project_id}")
        new_ep_desc = st.text_area(t("وصف الحلقة"), key=f"new_ep_desc_{project_id}")
        
        if st.button(t("إضافة حلقة"), key=f"add_ep_btn_{project_id}"):
            if new_ep_title.strip():
                run_query(
                    "INSERT INTO episodes (project_id, episode_number, title, description) VALUES (?,?,?,?)",
                    (project_id, int(new_ep_num), new_ep_title, new_ep_desc)
                )
                st.success(t("تم إضافة الحلقة"))
                st.rerun()
            else:
                st.warning(t("أدخل عنوان الحلقة"))
        
        # List episodes
        if episodes:
            st.subheader(f"{t('الحلقات')} ({len(episodes)})")
            for ep in episodes:
                with st.expander(f"الحلقة {ep['episode_number']}: {ep['title'] or '(بدون عنوان)'}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**رقم:** {ep['episode_number']}")
                    with col2:
                        st.write(f"**الحالة:** {ep.get('status', 'planning')}")
                    
                    if ep['description']:
                        st.write(f"**الوصف:** {ep['description']}")
                    
                    # Delete button
                    if st.button(t("حذف الحلقة"), key=f"del_ep_{ep['id']}"):
                        run_query("DELETE FROM episodes WHERE id=?", (ep['id'],))
                        st.success(t("تم حذف الحلقة"))
                        st.rerun()

with st.sidebar.expander(tr("edit_delete_project")):
    # ملحوظة مهمة: كل الـ keys هنا لازم تتربط برقم المشروع (project_id) —
    # لو الـ key ثابت، Streamlit بيفتكر قيمة قديمة من مشروع تاني كان متفتح
    # قبل كده، وده ممكن يأدي لحفظ أو حتى مسح المشروع الغلط بالغلط.
    e_proj_name = st.text_input(t("اسم المشروع"), value=project["name"], key=f"edit_proj_name_{project_id}")
    e_proj_type = st.selectbox(
        t("نوع المشروع"), ["فيلم", "مسلسل", "إعلان", "فيديو قصير"],
        index=safe_index(["فيلم", "مسلسل", "إعلان", "فيديو قصير"], project["project_type"]),
        format_func=t,
        key=f"edit_proj_type_{project_id}",
    )
    e_proj_res = st.selectbox(
        t("الدقة الافتراضية"), ["720p", "1080p", "2K", "4K"],
        index=safe_index(["720p", "1080p", "2K", "4K"], project["default_resolution"]),
        key=f"edit_proj_res_{project_id}",
    )
    e_proj_orient = st.selectbox(
        t("الاتجاه الافتراضي"), ["أفقي", "رأسي", "مربع"],
        index=safe_index(["أفقي", "رأسي", "مربع"], project["default_orientation"]),
        format_func=t,
        key=f"edit_proj_orient_{project_id}",
    )
    e_proj_ratio = st.selectbox(
        t("نسبة الأبعاد الافتراضية"), ["4:5", "16:9", "9:16", "1:1", "4:3", "21:9"],
        index=safe_index(["4:5", "16:9", "9:16", "1:1", "4:3", "21:9"], project["default_aspect_ratio"]),
        key=f"edit_proj_ratio_{project_id}",
    )
    if st.button(t("💾 حفظ تعديل المشروع"), key=f"save_proj_btn_{project_id}"):
        if e_proj_name.strip():
            run_query(
                "UPDATE projects SET name=?, project_type=?, default_resolution=?, default_orientation=?, default_aspect_ratio=? WHERE id=?",
                (e_proj_name, e_proj_type, e_proj_res, e_proj_orient, e_proj_ratio, project_id),
            )
            st.success(t("تم تعديل بيانات المشروع"))
            st.rerun()
        else:
            st.warning(t("اسم المشروع مينفعش يبقى فاضي"))

    st.markdown("---")
    st.caption(t("⚠️ حذف المشروع بيمسح كل الأماكن والشخصيات والمشاهد واللقطات بتاعته نهائيًا."))
    confirm_delete_project = st.checkbox(
        f"{t('متأكد إني عايز أمسح مشروع')} \"{project['name']}\" {t('وكل بياناته')}",
        key=f"confirm_delete_project_{project_id}",
    )
    if st.button(t("🗑️ حذف المشروع نهائيًا"), disabled=not confirm_delete_project, key=f"delete_proj_btn_{project_id}"):
        run_query("DELETE FROM projects WHERE id=?", (project_id,))
        st.success(t("تم حذف المشروع"))
        st.rerun()

if project["owner_name"]:
    _owner_line = f"👤 {project['owner_name']}"
    if project["owner_role"]:
        _owner_line += f" · {t(project['owner_role'])}"
    st.sidebar.markdown(f'<div class="cf-owner-box">{_owner_line}</div>', unsafe_allow_html=True)

with st.sidebar:
    _settings_key = f"show_settings_{project_id}"
    if _settings_key not in st.session_state:
        st.session_state[_settings_key] = False
    _set_col1, _set_col2 = st.columns([1, 5])
    with _set_col1:
        if st.button("⚙", key=f"toggle_settings_{project_id}", type="primary", help=t("الإعدادات")):
            st.session_state[_settings_key] = not st.session_state[_settings_key]
    with _set_col2:
        st.markdown(f'<div class="cf-settings-label">{t("⚙️ الإعدادات")}</div>', unsafe_allow_html=True)

    if st.session_state[_settings_key]:
        st.caption(t("اسمك ووظيفتك في المشروع ده (بتتحفظ مع المشروع نفسه)."))
        role_options_with_blank = ["—"] + PROJECT_ROLE_OPTIONS
        e_owner_name = st.text_input(
            t("اسم المستخدم"), value=project["owner_name"] or "", placeholder=t("مثال: أحمد محمد"),
            key=f"edit_owner_name_{project_id}",
        )
        e_owner_role = st.selectbox(
            t("الوظيفة في المشروع"), role_options_with_blank,
            index=safe_index(role_options_with_blank, project["owner_role"] or "—"),
            format_func=t,
            key=f"edit_owner_role_{project_id}",
        )
        if st.button(t("💾 حفظ الإعدادات"), key=f"save_settings_btn_{project_id}"):
            run_query(
                "UPDATE projects SET owner_name=?, owner_role=? WHERE id=?",
                (e_owner_name, None if e_owner_role == "—" else e_owner_role, project_id),
            )
            mark_saved(f"settings_{project_id}")
            st.rerun()
        show_saved_badge(f"settings_{project_id}")

_caption_line = (
    f"{t(project['project_type'])} · {ltr(project['default_resolution'])} · "
    f"{t(project['default_orientation'])} · {ltr(project['default_aspect_ratio'])}"
)
st.markdown(
    f"""
    <div style="text-align:center;">
        <h2 style="margin-bottom:2px;">🎬 {project['name']}</h2>
        <div style="opacity:0.75; font-size:0.9rem;">{_caption_line}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------- شريط مراحل العمل ----------------
_loc_count = fetch_all("SELECT COUNT(*) c FROM locations WHERE project_id=?", (project_id,))[0]["c"]
_char_count = fetch_all("SELECT COUNT(*) c FROM characters WHERE project_id=?", (project_id,))[0]["c"]
_scene_count = fetch_all("SELECT COUNT(*) c FROM scenes WHERE project_id=?", (project_id,))[0]["c"]
_shot_count = fetch_all(
    "SELECT COUNT(*) c FROM shots sh JOIN scenes s ON sh.scene_id=s.id WHERE s.project_id=?", (project_id,)
)[0]["c"]
_confirmed_count = fetch_all(
    "SELECT COUNT(*) c FROM shots sh JOIN scenes s ON sh.scene_id=s.id WHERE s.project_id=? AND sh.confirmed=1",
    (project_id,),
)[0]["c"]

_stage_defs = [
    ("🎬", tr("stage_project")),
    ("📍", tr("stage_locations_chars")),
    ("📝", tr("stage_scenes")),
    ("🎥", tr("stage_shots")),
    ("🔍", tr("stage_review")),
]
_done_flags = [
    True,
    _loc_count > 0 and _char_count > 0,
    _scene_count > 0,
    _shot_count > 0,
    _shot_count > 0 and _confirmed_count == _shot_count,
]
_current_idx = next((i for i, d in enumerate(_done_flags) if not d), len(_done_flags) - 1)

_scenes_with_shots = fetch_all(
    "SELECT COUNT(DISTINCT s.id) c FROM scenes s JOIN shots sh ON sh.scene_id=s.id WHERE s.project_id=?",
    (project_id,),
)[0]["c"]
_all_done = all(_done_flags)

# سطر تقدّم واحد بدل خمس كروت. الكروت كانت بتاخد ~90px فوق كل تبويب وبتكرر
# نفس التقسيمة اللي التبويبات تحتها عاملاها بأسامي تانية — تنقل مزدوج.
# السطر بيقول المرحلة الحالية وإيه اللي فاضل فيها بالأرقام.
if _all_done:
    _progress_detail = t("كل اللقطات اتراجعت واتأكدت")
elif _current_idx == 1:
    _progress_detail = f"{ltr(_loc_count)} {t('مكان')} · {ltr(_char_count)} {t('شخصية')}"
elif _current_idx == 2:
    _progress_detail = t("لسه مفيش مشاهد — ابدأ من «إضافة سيناريو»")
elif _current_idx == 3:
    _progress_detail = (f"{ltr(_scenes_with_shots)} {t('من')} {ltr(_scene_count)} "
                        f"{t('مشهد ليهم لقطات')}")
else:
    _progress_detail = (f"{ltr(_confirmed_count)} {t('من')} {ltr(_shot_count)} "
                        f"{t('لقطة اتراجعت')}")

_segments = "".join(
    f'<span class="cf-progress-seg cf-progress-seg--'
    f'{"done" if _d else ("current" if _i == _current_idx else "pending")}" '
    f'title="{_lbl}"></span>'
    for _i, ((_icon, _lbl), _d) in enumerate(zip(_stage_defs, _done_flags))
)
_step_no = len(_stage_defs) if _all_done else _current_idx + 1
st.markdown(
    f'<div class="cf-progress" dir="{_dir}">'
    f'<div class="cf-progress-bar" aria-hidden="true">{_segments}</div>'
    f'<div class="cf-progress-text"><strong>{t("الخطوة")} {ltr(_step_no)} {t("من")} '
    f'{ltr(len(_stage_defs))} · {_stage_defs[min(_step_no, len(_stage_defs)) - 1][1]}</strong>'
    f' — {_progress_detail}</div>'
    f'</div>',
    unsafe_allow_html=True,
)

tab_import, tab_locations, tab_characters, tab_props, tab_scenes, tab_breakdown, tab_dashboard = st.tabs(
    [tr("tab_import"), tr("tab_locations"), tr("tab_characters"), tr("tab_props"),
     tr("tab_scenes"), tr("tab_breakdown"), tr("tab_dashboard")],
    key="main_tabs",
)

# ---------------- تبويب استيراد السكريبت ----------------


# ---------------- التبويبات ----------------
# كل تبويب في views/<اسم>.py. الترتيب هنا هو ترتيب st.tabs فوق.
with tab_import:
    views.import_tab.render(project_id=project_id)
with tab_locations:
    views.locations.render(project_id=project_id)
with tab_characters:
    views.characters.render(project_id=project_id)
with tab_props:
    views.props.render(project_id=project_id)
with tab_scenes:
    views.scenes.render(project=project, project_id=project_id, _is_ar=_is_ar)
with tab_breakdown:
    views.shots.render(project_id=project_id)
with tab_dashboard:
    views.reports.render(project=project, project_id=project_id, _char_count=_char_count, _loc_count=_loc_count, _scene_count=_scene_count, _shot_count=_shot_count)
