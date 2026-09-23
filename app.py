import datetime
import html
import json
import os
import sys
import time
import streamlit as st
from auth import (
    authenticate, no_login_allowed, resolve_users,
    make_session_token, verify_session_token, SESSION_COOKIE_NAME,
)
from database import init_db, FIELD_HELP
import theme

from i18n import t, tr
from ui import ltr
import views.import_tab, views.locations, views.characters, views.actors, views.props, views.scenes, views.shots, views.reports
import views.project_settings
import repo
import accounts
import audit
import links
import notify
import permissions

# أيقونة البرنامج = العلامة لوحدها على مربع كحلي (الدليل ص 04، lockup رقم 5:
# "Icon only — app icon, favicon, avatar, watermark"). كانت إيموجي 🎬، يعني
# الفافيكون في تاب المتصفح مكانش فيه أي حاجة من البراند.
st.set_page_config(
    page_title="CimaFast Studio",
    page_icon=theme.brand.asset_path(theme.brand.APP_ICON),
    layout="wide",
)

# الشكل: النسخة الافتراضية classic، و‎?theme=glass‎ بيشغّل التصميم الجديد.
# كل الـ CSS بقى في حزمة theme/ — مكان واحد بدل تلاتة.
_theme_variant = theme.resolve_variant(st)
theme.inject_base(st, _theme_variant, lang=st.session_state.get("ui_lang", "ar"))


def _render_locked_screen():
    """شاشة القفل لما مفيش حسابات متظبطة — بنقفل الباب ونقول للمسؤول السبب."""
    st.markdown(
        "<div class='cf-login__logo' style='margin-top:15vh'>%s</div>"
        % theme.brand.lockup("dark", px=64)
        + "<p dir='auto' style='text-align:center; font-size:1.1rem;'>"
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
    # اللوجو الرسمي بدل الإيموجي + النص: الـ lockup الأفقي بنسخة الاستوديو
    # (STUDIO مكان MEDIA، الدليل ص 04) على سطح غامق ⇒ النسخة الصفرا.
    # الاسم العربي جنبه بخط Cairo، زي ما الدليل بيطلب بالظبط — مش جوه
    # الـ lockup ولا ترجمة حرفية جوه الووردمارك.
    st.markdown(
        """
        <div class="cf-login" dir="rtl">
            <div class="cf-login__logo">%s</div>
            <p>تسجيل الدخول / Sign in</p>
        </div>
        """ % theme.brand.lockup_master("dark", height=80, arabic=True),
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
            # زرار الدخول هو الحدث الأساسي في الصفحة ⇒ زرار primary،
            # يعني تعبئة صفرا وحروف Ink زي ما الدليل بيقول (ص 08).
            submitted = st.form_submit_button(
                "دخول / Log in", use_container_width=True, type="primary")
        if submitted:
            user = authenticate(username, password, _auth_users())
            if user:
                accounts.touch_login(user)
                st.session_state["_authenticated"] = True
                st.session_state["_auth_user"] = user
                st.session_state.pop("_login_attempts", None)
                # الكوكي بيتحط في الـ run الجاي (مش هنا) عشان لو حطيناها قبل
                # st.rerun() مباشرة، الصفحة بتتغير قبل ما المتصفح ياخد فرصة
                # ينفّذ السكريبت اللي بيحط الكوكي فعليًا
                st.session_state["_pending_session_cookie"] = make_session_token(user)
                st.rerun()
            # F3: كل محاولة فاشلة بتتسجّل (الاسم بس، من غير كلمة السر أبدًا)
            accounts.log_failed_login(username)
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
    users = _auth_users()
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
    if st.session_state.get("_auth_user"):
        accounts.log_logout(st.session_state["_auth_user"])
    for key in ("_authenticated", "_auth_user", "_login_attempts", "_cf_role"):
        st.session_state.pop(key, None)
    st.session_state["_just_logged_out"] = True


def _nav_link(label, href, title=None, icon_only=False):
    """لينك بشكل زرار، بيفتح في نفس التاب. st.link_button دايمًا بيفتح تاب
    جديد، وده بيبعتر الرئيسية والتطبيق والجدول على كذا تاب.

    ‎st.markdown‎ عادي مش ‎st.sidebar.markdown‎ عمدًا: بيترسم في أي حاوية
    (عمود، شريط جانبي...) اللي بينادي عليها من جواها، مش الشريط الجانبي
    دايمًا.

    ‎title‎: لما اللينك يبقى أيقونة لوحدها من غير كلام (زي 🏠 بعد تعديل
    2026-09-23)، الأيقونة مش اسم يقراه قارئ الشاشة. فبنحط الكلمة في
    ‎aria-label‎ (الاسم المنطوق) و‎title‎ (تلميح الماوس) - الكلمة اتشالت من
    الشاشة بس، مش من الوصول."""
    attrs = ""
    if title:
        esc = html.escape(title, quote=True)
        attrs = f' title="{esc}" aria-label="{esc}"'
    cls = "cf-navlink cf-navlink--icon" if icon_only else "cf-navlink"
    st.markdown(
        f'<a class="{cls}" href="{html.escape(href, quote=True)}" target="_self"{attrs}>{html.escape(label)}</a>',
        unsafe_allow_html=True)


def _session_role():
    """F2: دور المستخدم في الشركة المختارة. Streamlit بيشغّل كل rerun في thread
    جديد، فالدور بيتقري من session_state مش من متغيّر في الـ thread."""
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    if get_script_run_ctx(suppress_warning=True) is None:
        return None
    return st.session_state.get("_cf_role")


def _session_audit_context():
    """F3: مين شغّال وعلى أنهي شركة ومشروع — نفس حكاية الدور: من session_state."""
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    if get_script_run_ctx(suppress_warning=True) is None:
        return {}
    return {"username": st.session_state.get("_auth_user"),
            "company_id": st.session_state.get("_cf_company"),
            "project_id": st.session_state.get("_cf_project"),
            "source": "app"}


permissions.set_resolver(_session_role)
audit.set_resolver(_session_audit_context)


@st.cache_resource
def _bootstrap_accounts():
    """F1: الجداول + نقل حسابات secrets.toml للقاعدة، مرة واحدة لكل process.
    آمن يتعاد: مابيضيفش مستخدم أو شركة موجودين."""
    init_db()
    done = accounts.migrate_accounts(resolve_users())
    print(f"[accounts] migration: {done}", file=sys.stderr, flush=True)
    return done


def _auth_users():
    """الحسابات الفعّالة من جدول users. secrets.toml احتياطي بس قبل أول نقل."""
    return accounts.auth_users() or resolve_users()


_bootstrap_accounts()

# البروفايل العام للممثل/ة (P9): ‎?profile=<token>‎ بيتعرض من غير دخول وبيقف
# هنا — قبل بوابة الدخول، ومن غير ما أي حاجة من البرنامج نفسه تترسم.
if st.query_params.get("profile"):
    views.actors.render_public_profile(st.query_params.get("profile"))
    st.stop()

if not _check_login():
    st.stop()

_pending_cookie_token = st.session_state.pop("_pending_session_cookie", None)
if _pending_cookie_token:
    _set_session_cookie(_pending_cookie_token)

# كلمة سر مؤقتة (حساب جديد أو إعادة تعيين من الأدمن) لازم تتغير قبل أي حاجة تانية.
_me_row = accounts.user(st.session_state.get("_auth_user") or "")
if _me_row and _me_row["must_change_password"]:
    st.markdown('<div class="cf-login" dir="rtl"><h2>🔐 غيّر كلمة السر / Change your password</h2>'
                '<p>دي كلمة سر مؤقتة. اختار كلمة سر جديدة (١٠ حروف على الأقل) عشان تكمّل.</p></div>',
                unsafe_allow_html=True)
    _, _mid, _ = st.columns([1, 1.4, 1])
    with _mid, st.form("_change_pw_form"):
        _old = st.text_input("كلمة السر المؤقتة / Temporary password", type="password")
        _new = st.text_input("كلمة السر الجديدة / New password", type="password")
        _again = st.text_input("أعد كتابتها / Repeat it", type="password")
        if st.form_submit_button("حفظ / Save", use_container_width=True):
            if _new != _again:
                st.error("الكلمتين مش زي بعض / The two passwords differ")
            else:
                try:
                    accounts.change_own_password(_me_row["username"], _old, _new)
                    st.rerun()
                except (ValueError, accounts.AccessDenied) as _e:
                    st.error(str(_e))
    st.stop()

# H1: الدخول بيوصّل على الصفحة الرئيسية (مش جوه آخر مشروع). مرة واحدة في الجلسة،
# وبس لو مفيش رابط لشاشة معيّنة — "افتح" من الرئيسية بيجي بـ ?project= فبيعدّي.
_home_url = os.environ.get("CIMAFAST_HOME_URL")
if _home_url and not st.session_state.get("_landed"):
    st.session_state["_landed"] = True
    if links.parse(st.query_params) == (None, None):
        # setTimeout: كوكي الدخول (st.html فوق) لازم يتكتب قبل ما نسيب الصفحة
        st.html(f"<script>setTimeout(function(){{window.location.replace({json.dumps(_home_url)})}}, 150)</script>",
                unsafe_allow_javascript=True)
        st.stop()

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




















# ---------------- جرس التنبيهات (H4) ----------------
# التغييرات اللي تخص قسم المستخدم (notify.py). ‎run_every=30‎ عشان التغيير
# يوصل في نفس الجلسة من غير ما حد يعمل refresh — الـ fragment بس اللي بيعيد،
# مش الصفحة كلها، فمفيش فورم مفتوحة بتتأثر. فتح الجرس = "شفتهم".

def _mark_notifications_seen():
    # بيتنادي مع الفتح والقفل الاتنين؛ mark_seen مابيرجعش لورا، فالقفل مالوش أثر.
    _latest = st.session_state.get("_notif_latest") or 0
    st.session_state["_notif_seen_before"] = notify.last_seen(_current_user)
    notify.mark_seen(_current_user, _latest)


@st.fragment(run_every=30)
def _notification_bell():
    _lang = st.session_state.get("ui_lang", "ar")
    _feed = notify.feed(_current_user, "", os.environ.get("CIMAFAST_BOARD_URL"), lang=_lang)
    st.session_state["_notif_latest"] = _feed["latest_id"]
    _unread = _feed["unread"]
    # العدد في شارة لوحده جنب الجرس، مش في اسم الزرار: Streamlit بيعتبر
    # الـ popover عنصر جديد لما اسمه يتغيّر، فكان بيقفل نفسه أول ما يتفتح
    # (الفتح بيصفّر العدد ← الاسم بيتغيّر ← يتقفل).
    _bell_row = st.container(horizontal=True, gap=None, vertical_alignment="center", wrap=False)
    if _unread:
        _bell_row.markdown(
            '<span class="cf-notif-badge" role="status" aria-label="%s">%s</span>'
            % (html.escape(f"{_unread} {t('تنبيه جديد')}", quote=True), html.escape(ltr(min(_unread, 99)))),
            unsafe_allow_html=True)
    with _bell_row.popover("", icon=":material/notifications:", key="cf_notif_pop",
                           help=t("التغييرات اللي تخص قسمك"), on_change=_mark_notifications_seen):
        st.markdown(f"**{t('التغييرات اللي تخص قسمك')}**")
        if not _feed["items"]:
            st.caption(t("مفيش تغييرات جديدة في مشاريعك آخر أسبوعين."))
            return
        _before = st.session_state.get("_notif_seen_before")
        _rows = []
        for _it in _feed["items"][:15]:
            _new = _it["unread"] or (_before is not None and _it["id"] > _before)
            _rows.append(
                '<a class="cf-notif%s" href="%s" target="_self">'
                '<span class="cf-notif__text">%s</span>'
                '<span class="cf-notif__meta">%s · %s · %s</span></a>'
                % (" cf-notif--new" if _new else "", html.escape(_it["href"], quote=True),
                   html.escape(_it["text"]), html.escape(_it["who"]), html.escape(_it["project"]),
                   html.escape(notify.ago(_it["at"], lang=_lang))))
        # الـ popover بيترسم بره ‎.stApp‎ فمابيورثش اتجاهها — من غير ‎dir‎ صريح
        # «الأقواس» في الملخصات العربي كانت بتقلب ناحيتها.
        st.markdown('<div class="cf-notif-list" dir="%s">%s</div>'
                    % ("ltr" if _lang == "en" else "rtl", "".join(_rows)), unsafe_allow_html=True)


# ---------------- الشريط الجانبي ----------------
# إعادة تصميم 2026-09-23 (رابعة، سطح غامق): موافقة صاحب المنتج ("Yes") على
# موك أب مرجعي شاركه — خلفية كحلي غامقة بدل الحقل الأصفر، بدل ما تبقى
# تعديل مسافات زي المرة اللي فاتت. الاستثناء موثّق ومؤرّخ في
# theme/brand.py وستايله في theme/sidebar.py — للشريط الجانبي بس، باقي
# البرنامج زي ما هو بالحقل الأصفر حيثما استُخدم.
#
# تفسير بنية الموك أب: "الرئيسية" و"المشاريع" ظاهرين فيه كصفين متوازيين
# بسهم (›) يوحي بصفحات فرعية تتفتح تحتهم. البرنامج ده صفحة Streamlit واحدة
# مش راوتر صفحات متداخلة، و"المشاريع" في الموك أب مالوش أي محتوى غير
# اختيار/إنشاء المشروع اللي أصلًا موجودين تحت - فمفيش داعي لسهم بيوعد
# بحاجة مش موجودة (mystery-meat nav). القرار هنا: "الرئيسية" فضلت رابط
# فعلي (بيودّي فعلاً لصفحة تانية)، و"المشاريع" بقت عنوان قسم غير قابل
# للنقر فوق نفس عناصر اختيار/إنشاء المشروع اللي كانت موجودة أصلًا - نفس
# الوظيفة بالظبط، غلاف بصري بس اتغيّر.
#
# ترتيب رأسي عدّله المالك بعد ما شاف النتيجة على الهوا (2026-09-23): "ارفع
# بلوك اللغه فوق ونزل زرار الرييسية تحت". فبدّلنا الاتنين مكان بعض حرفيًا -
# مفتاح اللغة (segmented_control) طلع تحت التاجلاين مباشرة، ورابط
# "الرئيسية" نزل تحت جوه قسم الحساب.
#
# تعديل تاني من محمد الزيات في نفس اليوم بعد ما شاف النتيجة: "نزّل بلوك
# اللغة تحت جنب الرئيسية، واشيل كلمة (اللغة) وكلمة (الرئيسية) - الأيقونات
# لوحدها واضحة". فالاتنين بقوا **صف واحد** في آخر الشريط جنب الأفتار
# (الكود تحت، قبل زرار الخروج)، وكل واحد فيهم أيقونته بس: 🏠 للرئيسية و🌐
# للغة جنب حبتين AR/EN. الكلام ما اتشالش من الوصول - اتنقل لـ
# ‎aria-label/title‎ (اللينك) و‎label_visibility="collapsed"‎ (المفتاح،
# Streamlit بيفضل يستخدم التسمية كاسم منطوق)، فقارئ الشاشة لسه بيقول
# "الرئيسية" و"اللغة". مفيش مفتاح لغة فوق خالص دلوقتي.
#
# كل التحكمات الشغالة فضلت زي ما هي (نفس المنطق، نفس session_state):
# اختيار الحساب (لو أكتر من واحد)، إنشاء مشروع، اختيار المشروع، اللغة،
# الرئيسية، الخروج. الجديد بس عناصر عرض إضافية: صف أفتار بالحروف الأولى
# (مفيش ميزة صور حسابات لسه - PRODUCT-PLAN)، وحقل "الدور" للقراءة بس
# (الدور نفسه كان معروف من قبل، بس مش ظاهر في الشريط).

with st.sidebar.container(gap=2):
    with st.container(horizontal=True, gap="small",
                       vertical_alignment="center", wrap=False):
        # سطح غامق دلوقتي ⇒ نسخة العلامة الصفرا (mark-dark). و‎lockup()‎
        # المركّبة مش ‎lockup_master()‎ الماستر عشان يطلع "CimaFast STUDIO"
        # زي كل سطح تاني في التطبيق، مش "MEDIA" بتاعة الماستر الجامد.
        st.markdown(
            '<div class="cf-title">%s</div>' % theme.brand.lockup("dark", px=36),
            unsafe_allow_html=True,
        )
        # أيقونة "معلومات" مش "؟" - طلب محمد الزيات (2026-09-23): علامة
        # الاستفهام بتتقري "مساعدة"، والزرار ده بيعرض نبذة عن البرنامج.
        # ‎:material/info:‎ من خط Material Symbols اللي Streamlit شايله جواه،
        # فمش معتمد على خطوط الجهاز (ده اللي خلّى "ⓘ" تفشل قبل كده)، وبياخد
        # لون النص زي باقي الشريط بدل مربع إيموجي أزرق ثابت ("ℹ️").
        with st.popover("", icon=":material/info:"):
            st.markdown(f"**{tr('studio_tagline')}**")
            st.caption(t(_APP_DESCRIPTION))
    # تاجلاين تحت اللوجو - نفس نص "؟" (studio_tagline)، مش ترجمة حرفية
    # لتاجلاين إنجليزي جديد ("IDEAS TO SCREEN") مالوش وجود في نظام الهوية.
    # مفيش تاجلاين تانية في آخر الشريط (كان فيها "GOOD STORIES GO FURTHER"
    # في الموك أب) - نفس الجملة مكررة مرتين في شريط بالطول ده زحمة مش زينة.
    st.markdown(
        '<div class="cf-sb-tagline">%s</div>' % html.escape(tr("studio_tagline")),
        unsafe_allow_html=True,
    )
    # مفيش مفتاح لغة هنا فوق خالص بعد تعديل محمد (2026-09-23) - نزل تحت في
    # صف واحد جنب أيقونة الرئيسية، شوف قسم الحساب في آخر الشريط.

_sb_projects = st.sidebar.container(gap=6)
_sb_projects.markdown(
    '<div class="cf-sb-section-label">📁 %s</div>' % html.escape(tr("sidebar_projects")),
    unsafe_allow_html=True,
)

_current_user = st.session_state.get("_auth_user")

# F1: المستخدم بيشوف مشاريع الحسابات اللي هو عضو فيها بس. لو عضو في أكتر من
# حساب (أو المشغّل)، بيختار واحد.
_my_companies = accounts.companies_for(_current_user or "")
if not _my_companies:
    _sb_projects.error(t("حسابك مش مربوط بأي شركة. كلّم مدير الشركة بتاعتك."))
    st.stop()
# H2: رابط مباشر (?project=&tab=) من الصفحة الرئيسية أو تنبيه أو بوست. بيتطبّق
# مرة واحدة لما يوصل؛ بعد كده اليوزر حر يتنقّل، وشريط العنوان بيتبعه (تحت).
# لازم يتنفّذ قبل ما selectbox الحساب يتبنى تحت، عشان بيحط قيمة الجلسة بتاعته.
_link_project, _link_tab = links.parse(st.query_params)
if (_link_project or _link_tab) and (_link_project, _link_tab) != st.session_state.get("_applied_link"):
    st.session_state["_applied_link"] = (_link_project, _link_tab)
    if _link_project:
        if accounts.can_access_project(_current_user, _link_project):
            _lp = repo.project(_link_project)
            if len(_my_companies) > 1:
                st.session_state["company_selector"] = next(
                    c["name"] for c in _my_companies if c["id"] == _lp["company_id"])
            st.session_state["_link_project_name"] = _lp["name"]
        else:
            st.toast(t("الرابط ده لمشروع مش متاح لحسابك."), icon="🔒")
    if _link_tab:
        st.session_state["main_tabs"] = tr(links.TABS[_link_tab])
# H4: ‎&item=‎ من تنبيه — المشهد اللي اتغيّر بيتفتح لوحده في تبويب المشاهد.
# بيتشال من الرابط بعد ما يتقري، عشان rerun بعد كده مايرجّعش التركيز عليه.
_link_item = links.item(st.query_params)
if _link_item is not None:
    if _link_tab == "scenes":
        st.session_state["_focus_scene"] = _link_item
    del st.query_params["item"]

if len(_my_companies) > 1:
    _company_names = {c["name"]: c for c in _my_companies}
    _company = _company_names[_sb_projects.selectbox(t("الحساب"), list(_company_names), key="company_selector")]
else:
    _company = _my_companies[0]
company_id = _company["id"]
# B5: نوع الاشتراك (Enterprise / Studio / Creator) — كلمة "شركة" ماتظهرش
# هنا خالص، الإطار كله User + نوع اشتراك. العرض الفعلي بقى في الشريط
# السفلي تحت (بعد اختيار المشروع)، مش هنا.
_tier = _company.get("subscription_tier") or "creator"
_tier_label = accounts.TIER_LABELS.get(_tier, _tier)
# F2: من هنا لحد آخر الـ run (والـ callbacks في الـ run الجاي) كل كتابة بتتفحص بالدور ده
_role = _company["role"]
st.session_state["_cf_role"] = _role
# F3: نفس الفكرة للسجل — كل كتابة بتتسجّل باسم المستخدم والشركة دي
st.session_state["_cf_company"] = company_id
_can_edit = permissions.can(_role, "edit")
if not _can_edit:
    _sb_projects.info(f"👁️ {t('مشاهدة فقط — تقدر تتصفح وتصدّر، بس مش تعدّل.')}")

projects = accounts.projects_for(_current_user, company_id)
project_names = {p["name"]: p["id"] for p in projects}

if permissions.can(_role, "create_project"):
    with _sb_projects.expander(tr("new_project")):
        new_name = st.text_input(t("اسم المشروع"), placeholder=t("مثال: عروسة البحر"))
        new_type = st.selectbox(t("نوع المشروع"), ["فيلم", "مسلسل", "إعلان", "فيديو قصير"], format_func=t, help=FIELD_HELP["project_type"])
        new_res = st.selectbox(t("الدقة الافتراضية"), ["720p", "1080p", "2K", "4K"], help=FIELD_HELP["default_resolution"])
        new_orient = st.selectbox(t("الاتجاه الافتراضي"), ["أفقي", "رأسي", "مربع"], format_func=t, help=FIELD_HELP["default_orientation"])
        new_ratio = st.selectbox(t("نسبة الأبعاد الافتراضية"), ["4:5", "16:9", "9:16", "1:1", "4:3", "21:9"], index=0)
        if st.button(t("إنشاء المشروع")):
            if new_name.strip():
                accounts.create_project(_current_user, company_id, new_name, new_type, new_res, new_orient, new_ratio)
                st.success(t("تم إنشاء المشروع"))
                st.rerun()
            else:
                st.warning(t("اكتب اسم المشروع أولًا"))

# الشريط ده بيتبني قبل فحص "مفيش مشاريع" تحت (مش بعد اختيار المشروع):
# يوزر ملوش مشاريع كان بيوقف عند st.stop() من غير زرار خروج ولا مفتاح
# لغة. ترتيب الظهور مابيتغيّرش - الحاوية دي بتتعمل بعد _sb_projects
# فبتفضل تحتها، واختيار المشروع بيتكتب جوه _sb_projects.
# شريط الحساب — رفيع، في الآخر خالص، بعد ما اخترت مشروعك مش قبله. فاصل
# رفيع واحد قبل القسم ده بس - مفيش فاصل بعده، لأنه آخر حاجة في الشريط
# الجانبي أصلًا (اللي بعده محتوى المشروع في المنطقة الرئيسية، مش هنا).
#
# صف الأفتار: مفيش ميزة صور حسابات في البرنامج لسه (مفيش عمود صورة في
# جدول users، ولا مسار رفع) - ده خارج نطاق الشغلانة دي عمدًا (تخزين/
# اعتدال/خصوصية محتاجين قرار لوحدهم). بدالها دايرة بالحروف الأولى من
# display_name (أو اسم الدخول لو مفيش)، بنفس لغة ألوان العلامة
# (تعبئة صفرا + حروف كحلي) بدل ما تخترع بالتة جديدة. الاسم تحته نوع
# الاشتراك (Creator/Studio/Enterprise) - نفس اللي كان في الكابشن القديم،
# مش وظيفة، غلاف بصري بس اتغيّر.
st.sidebar.markdown('<hr class="cf-sb-sep">', unsafe_allow_html=True)
_sb_account = st.sidebar.container(gap=6)
_display_name = ((_me_row["display_name"] if _me_row else None) or _current_user or "?").strip()
_initials = "".join(w[0] for w in _display_name.split()[:2]).upper() or "?"
_sb_account.markdown(
    '<div class="cf-sb-avatar-row">'
    '<div class="cf-sb-avatar">%s</div>'
    '<div><div class="cf-sb-avatar-name">%s</div>'
    '<div class="cf-sb-avatar-role">%s</div></div>'
    "</div>"
    % (html.escape(_initials), html.escape(_display_name), html.escape(_tier_label)),
    unsafe_allow_html=True,
)

# صف الأيقونات: الرئيسية 🏠 + اللغة 🌐 AR/EN جنب بعض - طلب محمد الزيات
# (2026-09-23): "نزّل بلوك اللغة جنب الرئيسية، واشيل كلمة اللغة وكلمة
# الرئيسية، الأيقونات لوحدها واضحة".
#
# ‎horizontal=True‎ (حاوية أفقية، Streamlit 1.64) مش ‎st.columns‎: الأعمدة
# بتقسم العرض بالنسب فبتسيب فراغ ميت جنب أيقونة عرضها 44px، والحاوية
# الأفقية بتحط العناصر جنب بعض بمقاسها الطبيعي. و‎vertical_alignment=
# "center"‎ عشان اللينك (ارتفاع 44) يقع في نص حبتين AR/EN (44 كمان).
# الترتيب بيتبع اتجاه اللغة تلقائيًا (‎direction‎ على الشريط في
# theme/sidebar.py) فالرئيسية بتقع ناحية بداية السطر في اللغتين.
#
# الكلام اتشال من الشاشة بس مش من الوصول: اللينك بياخد ‎aria-label/title‎
# ("الرئيسية")، ومفتاح اللغة تسميته لسه ‎language_label‎ بس
# ‎label_visibility="collapsed"‎ - Streamlit بيفضل يستخدمها كاسم منطوق
# للمجموعة. الجلوب نفسه ‎aria-hidden‎ عشان ميتقريش مرتين.
#
# لو ‎CIMAFAST_HOME_URL‎ مش متظبط (تشغيلة من غير رئيسية) الأيقونة مش
# بتتكوّن خالص ومفتاح اللغة بياخد الصف لوحده - زي ما كان بالظبط.
_sb_nav_row = _sb_account.container(
    horizontal=True, gap="small", vertical_alignment="center", wrap=False)
with _sb_nav_row:
    if os.environ.get("CIMAFAST_HOME_URL"):
        _nav_link("🏠", os.environ["CIMAFAST_HOME_URL"],
                  title=t("الرئيسية"), icon_only=True)
    _notification_bell()
    st.markdown('<div class="cf-sb-globe" aria-hidden="true">🌐</div>',
                unsafe_allow_html=True)
    # الشكل (حبتين مستقلتين مدوّرتين تمامًا، المختارة تعبئة صفرا) متفروض في
    # theme/sidebar.py - شكل segmented_control الافتراضي (زرارين ملزّقين،
    # اختيار بحد بس) بيتغيّر هناك، مش هنا.
    _lang_widget_key = "lang_toggle"
    if _lang_widget_key not in st.session_state:
        st.session_state[_lang_widget_key] = st.session_state["ui_lang"].upper()
    _lang_selected = st.segmented_control(
        tr("language_label"), options=["AR", "EN"], key=_lang_widget_key,
        required=True, label_visibility="collapsed",
    )
if _lang_selected.lower() != st.session_state["ui_lang"]:
    st.session_state["ui_lang"] = _lang_selected.lower()
    st.rerun()

# زرار خروج بعرض الشريط كامل - آخر حاجة في الشريط زي ما كان دايمًا.
if _sb_account.button(tr("logout"), key="logout_btn", use_container_width=True):
    _logout()
    st.rerun()

if not projects:
    if permissions.can(_role, "create_project"):
        _sb_projects.info(t("ابدأ بإنشاء مشروع جديد من القائمة الجانبية"))
    else:
        _sb_projects.info(t("مفيش مشاريع في الشركة دي لسه. مدير الشركة أو المنتج هو اللي بينشئ المشاريع."))
    st.stop()

_wanted = st.session_state.pop("_link_project_name", None)
if _wanted in project_names:
    st.session_state["project_selector"] = _wanted
selected_project_name = _sb_projects.selectbox(tr("current_project_label"), list(project_names.keys()), key="project_selector")
project_id = project_names[selected_project_name]
st.session_state["_cf_project"] = project_id       # F3: كل كتابة بتتسجّل على المشروع ده
project = repo.project_by_id(project_id)[0]

# "الدور" - عرض للقراءة بس، مش اختيار: الدور بيتغيّر من صفحة الفريق
# (ROLE_LABELS نفسها بتتغيّر من هناك)، مش من هنا. من غير شكل سهم/قابلية
# ضغط عمدًا عشان الشكل ميوهمش إنه dropdown شغال.
_sb_projects.markdown(
    '<div class="cf-sb-field"><span class="cf-sb-field__label">%s</span>'
    '<span class="cf-sb-field__value">%s</span></div>'
    % (html.escape(tr("role_label")), html.escape(t(accounts.ROLE_LABELS.get(_role, _role)))),
    unsafe_allow_html=True,
)


# جدول التصوير، إدارة الفريق، تعديل/حذف المشروع، الحلقات — كل التفاصيل
# التنفيذية دي بقت في تبويب "⚙️ إعدادات المشروع" (views/project_settings.py)
# بدل الشريط الجانبي، زي ما طلب المالك.
_board_url = os.environ.get("CIMAFAST_BOARD_URL")

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
_loc_count = repo.count_locations(project_id)[0]["c"]
_char_count = repo.count_characters(project_id)[0]["c"]
_scene_count = repo.count_scenes(project_id)[0]["c"]
_shot_count = repo.count_shots(project_id)[0]["c"]
_confirmed_count = repo.count_confirmed_shots(project_id)[0]["c"]

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

_scenes_with_shots = repo.count_scenes_with_shots(project_id)[0]["c"]
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

# on_change="rerun": التبويب المفتوح بس هو اللي بيتبني (tab.open)، بدل السبعة في
# كل ضغطة — ومعرفة التبويب المفتوح بتخلّي شريط العنوان رابط للشاشة دي بالظبط.
_tabs = st.tabs([tr(k) for k in links.TABS.values()], key="main_tabs", on_change="rerun")
(tab_import, tab_locations, tab_characters, tab_actors, tab_props, tab_scenes, tab_breakdown,
 tab_dashboard, tab_settings) = _tabs
_open_tab = next((slug for slug, tab in zip(links.TABS, _tabs) if tab.open), "import")
# شريط العنوان = الشاشة الحالية: يتحفظ bookmark أو يتبعت لزميل
st.query_params.update(project=str(project_id), tab=_open_tab)
st.session_state["_applied_link"] = (project_id, _open_tab)
# "كمّل من مكان ما وقفت" في الرئيسية: بنكتب بس لما الشاشة تتغيّر، مش كل ضغطة
if st.session_state.get("_remembered") != (project_id, _open_tab):
    repo.remember_screen(_current_user, project_id, _open_tab,
                         datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
    st.session_state["_remembered"] = (project_id, _open_tab)
    # F3: نفس الشرط بيخلّي الحدث ده "فتح شاشة" مرة واحدة، مش مع كل ضغطة جوه الشاشة
    audit.event("screen", target=_open_tab, project_id=project_id, company_id=company_id)

# ---------------- تبويب استيراد السكريبت ----------------


# ---------------- التبويبات ----------------
# كل تبويب في views/<اسم>.py. الترتيب هنا هو ترتيب st.tabs فوق.
# F2: لو مشاهد داس على زرار تعديل، طبقة البيانات بترفض وهنا بنوريله رسالة
# مفهومة بدل traceback. التبويب نفسه بيكمل عادي في الـ rerun الجاي.
def _render(view, **kwargs):
    try:
        view.render(**kwargs)
    except permissions.Denied as exc:
        st.warning(t(str(exc)))


if tab_import.open:
    with tab_import:
        if permissions.can(_role, "run_ai"):
            _render(views.import_tab, project_id=project_id)
        else:
            st.info(t("استيراد السكريبت وتحليله لأعضاء الفريق اللي عندهم صلاحية تعديل. حسابك مشاهدة فقط."))
if tab_locations.open:
    with tab_locations:
        _render(views.locations, project_id=project_id)
if tab_characters.open:
    with tab_characters:
        _render(views.characters, project_id=project_id)
if tab_actors.open:
    with tab_actors:
        _render(views.actors, project_id=project_id, company_id=company_id)
if tab_props.open:
    with tab_props:
        _render(views.props, project_id=project_id)
if tab_scenes.open:
    with tab_scenes:
        _render(views.scenes, project=project, project_id=project_id, _is_ar=_is_ar)
if tab_breakdown.open:
    with tab_breakdown:
        _render(views.shots, project_id=project_id)
if tab_dashboard.open:
    with tab_dashboard:
        _render(views.reports, project=project, project_id=project_id, _char_count=_char_count, _loc_count=_loc_count, _scene_count=_scene_count, _shot_count=_shot_count)
if tab_settings.open:
    with tab_settings:
        _render(views.project_settings, project_id=project_id, current_user=_current_user,
               company_id=company_id, role=_role, tier=_tier, board_url=_board_url)
