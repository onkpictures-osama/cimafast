import os
import re
import sys
import time
import uuid
import json
import datetime
import streamlit as st
from auth import (
    authenticate, no_login_allowed, resolve_users,
    make_session_token, verify_session_token, SESSION_COOKIE_NAME,
)
from database import (
    init_db, FIELD_HELP,
    fetch_all, run_query, run_delete,
    CAMERA_MOVEMENT_OPTIONS, SHOT_SIZE_OPTIONS, CAMERA_ANGLE_OPTIONS,
    SPECIES_OPTIONS, GENDER_OPTIONS, PROJECT_ROLE_OPTIONS, INT_EXT_OPTIONS,
    INT_EXT_LABELS, DAY_NIGHT_OPTIONS, DAY_NIGHT_LABELS, bilingual_label,
)
from script_parser import (
    parse_script, find_similar_name_groups, apply_character_merges,
    find_similar_location_groups, apply_location_merges,
)
from importer import import_parsed_scenes
from export import (
    build_shot_list_excel, build_shot_list_word, build_shot_list_pdf,
    build_characters_sheet_excel, build_general_breakdown_excel, build_locations_sheet_excel,
    build_props_sheet_excel,
)

st.set_page_config(page_title="CimaFast Studio", page_icon="🎬", layout="wide")

# Global RTL/LTR CSS
st.markdown("""
<style>
    /* Global RTL/LTR styling */
    * { box-sizing: border-box; }
    
    /* Form labels: RTL for Arabic, LTR for English */
    label { direction: auto; text-align: right; }
    
    /* Text areas and inputs: LTR by default */
    textarea, input { direction: ltr !important; text-align: left; }
    
    /* Paragraphs with Arabic: RTL */
    p[dir="rtl"], div[dir="rtl"] { direction: rtl; text-align: right; }
    p[dir="ltr"], div[dir="ltr"] { direction: ltr; text-align: left; }
    
    /* Error messages: auto-direction */
    .stError, .stWarning, .stSuccess, .stInfo { 
        direction: auto; 
        text-align: right;
    }
    
    /* Buttons: center alignment */
    button { text-align: center; }
    
    /* Sidebar: RTL */
    .sidebar .sidebar-content { direction: rtl; }
</style>
""", unsafe_allow_html=True)


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
    st.markdown(
        """
        <style>
        .cf-login h2 { text-align: center; margin-top: 12vh; }
        .cf-login p { text-align: center; opacity: 0.75; margin-bottom: 0; }
        div[data-testid="stForm"] label p { direction: rtl; text-align: right; }
        div[data-testid="stForm"] input { direction: ltr; text-align: left; }
        </style>
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

# ---------------- تبديل لغة الواجهة (عربي/إنجليزي) ----------------
# ملحوظة: ده بيترجم العناوين الرئيسية والأزرار وأسماء التبويبات دلوقتي.
# تفاصيل الحقول جوه كل فورم لسه بالعربي وهتتترجم في تحديث لاحق.
UI_TEXT = {
    "sidebar_projects": {"ar": "المشاريع", "en": "Projects"},
    "new_project": {"ar": "➕ إنشاء مشروع جديد", "en": "➕ New Project"},
    "select_project": {"ar": "اختر مشروع للعمل عليه", "en": "Select a project"},
    "edit_delete_project": {"ar": "✏️ تعديل / حذف المشروع الحالي", "en": "✏️ Edit / Delete Current Project"},
    "settings": {"ar": "⚙️ الإعدادات", "en": "⚙️ Settings"},
    "tab_import": {"ar": "📤 إضافة سيناريو", "en": "📤 Add Screenplay"},
    "tab_locations": {"ar": "📍 الأماكن", "en": "📍 Locations"},
    "tab_characters": {"ar": "🎭 الشخصيات", "en": "🎭 Characters"},
    "tab_props": {"ar": "🎒 الإكسسوارات", "en": "🎒 Props"},
    "tab_scenes": {"ar": "📝 المشاهد", "en": "📝 Scenes"},
    "tab_breakdown": {"ar": "🎥 اللقطات", "en": "🎥 Shots"},
    "tab_dashboard": {"ar": "📊 التقارير النهائية", "en": "📊 Final Reports"},
    "sub_import": {"ar": "استيراد السكريبت من ملف Word أو نصي أو JSON", "en": "Import script from Word, text, or JSON"},
    "sub_locations": {"ar": "مكتبة الأماكن", "en": "Locations Library"},
    "sub_characters": {"ar": "مكتبة الشخصيات", "en": "Characters Library"},
    "sub_props": {"ar": "مكتبة الإكسسوارات", "en": "Props Library"},
    "sub_scenes": {"ar": "المشاهد", "en": "Scenes"},
    "sub_breakdown": {"ar": "تفريغ اللقطات", "en": "Shot Breakdown"},
    "sub_dashboard": {"ar": "نظرة عامة على حالة كل اللقطات", "en": "Overview of all shots' status"},
    "stage_project": {"ar": "المشروع", "en": "Project"},
    "stage_locations_chars": {"ar": "الأماكن والشخصيات", "en": "Locations & Characters"},
    "stage_scenes": {"ar": "المشاهد", "en": "Scenes"},
    "stage_shots": {"ar": "تفريغ اللقطات", "en": "Shot Breakdown"},
    "stage_review": {"ar": "المراجعة والتأكيد", "en": "Review & Confirm"},
    "btn_save": {"ar": "💾 حفظ التعديل", "en": "💾 Save Changes"},
    "btn_export_excel": {"ar": "⬇️ تحميل Excel", "en": "⬇️ Download Excel"},
    "btn_export_word": {"ar": "⬇️ تحميل Word", "en": "⬇️ Download Word"},
    "btn_export_pdf": {"ar": "⬇️ تحميل PDF", "en": "⬇️ Download PDF"},
    "studio_tagline": {"ar": "استوديو الإنتاج بالذكاء الاصطناعي", "en": "AI Production Studio"},
    "sidebar_owner_label": {"ar": "بيستخدمه", "en": "Used by"},
    "logged_in_as": {"ar": "داخل باسم", "en": "Signed in as"},
    "logout": {"ar": "🚪 تسجيل الخروج", "en": "🚪 Log out"},
}


def tr(key):
    lang = st.session_state.get("ui_lang", "ar")
    entry = UI_TEXT.get(key)
    if not entry:
        return key
    return entry.get(lang, entry.get("ar", key))


# قاموس ترجمة مباشر: النص العربي نفسه هو المفتاح، وقيمته الترجمة الإنجليزية.
# بيغطي كل تسميات الحقول والأزرار والرسايل جوه كل الفورمات في البرنامج.
TRANSLATIONS = {
    # عام
    "غير محدد": "Not specified", "بدون تحديد": "None selected",
    "بدون - مكان رئيسي": "None - main location", "اختياري": "optional",
    "💾 حفظ": "💾 Save", "💾 حفظ التعديل": "💾 Save Changes",
    "نهار": "Day", "ليل": "Night", "غروب": "Sunset", "فجر": "Dawn",
    "فيلم": "Feature Film", "مسلسل": "Series", "إعلان": "Ad", "فيديو قصير": "Short Video",
    "أفقي": "Horizontal", "رأسي": "Vertical", "مربع": "Square",
    # المشروع (الشريط الجانبي)
    "اسم المشروع": "Project Name", "نوع المشروع": "Project Type",
    "الدقة الافتراضية": "Default Resolution", "الاتجاه الافتراضي": "Default Orientation",
    "نسبة الأبعاد الافتراضية": "Default Aspect Ratio", "إنشاء المشروع": "Create Project",
    "تم إنشاء المشروع": "Project created", "اكتب اسم المشروع أولًا": "Enter a project name first",
    "ابدأ بإنشاء مشروع جديد من القائمة الجانبية": "Start by creating a new project from the sidebar",
    "💾 حفظ تعديل المشروع": "💾 Save Project Changes",
    "تم تعديل بيانات المشروع": "Project data updated",
    "اسم المشروع مينفعش يبقى فاضي": "Project name can't be empty",
    "⚠️ حذف المشروع بيمسح كل الأماكن والشخصيات والمشاهد واللقطات بتاعته نهائيًا.":
        "⚠️ Deleting the project permanently deletes all its locations, characters, scenes and shots.",
    "متأكد إني عايز أمسح مشروع": "I'm sure I want to delete the project",
    "وكل بياناته": "and all its data",
    "🗑️ حذف المشروع نهائيًا": "🗑️ Delete Project Permanently",
    "تم حذف المشروع": "Project deleted",
    "اسمك ووظيفتك في المشروع ده (بتتحفظ مع المشروع نفسه).":
        "Your name and role in this project (saved with the project itself).",
    "اسم المستخدم": "User Name", "الوظيفة في المشروع": "Role in Project",
    "💾 حفظ الإعدادات": "💾 Save Settings", "تم حفظ الإعدادات": "Settings saved",
    "البرنامج ده بيساعدك تجهز وتنظم بيانات الإنتاج كلها (الأماكن، الشخصيات، المشاهد، تفريغ اللقطات) "
    "وتتأكد إنها متكاملة وجاهزة. مفيش مرحلة توليد فيديو فعلي بالذكاء الاصطناعي جوه البرنامج ده لسه — "
    "دي خطوة مستقبلية محتاجة تطوير إضافي لربطها بأدوات التوليد.":
        "This app helps you prepare and organize all your production data (locations, characters, scenes, "
        "shot breakdown) and make sure it's complete and ready. There's no actual AI video generation stage "
        "in this app yet — that's a future step that needs further development to connect it with generation tools.",
    # تبويب استيراد السكريبت
    "ارفع ملف السيناريو (.docx أو .txt)، والنظام هيحاول يتعرف على رقم كل مشهد، "
    "داخلي/خارجي، النهار/الليل، المكان، والحوار، ويملى تبويب (السكريبت) تلقائيًا. "
    "تقدر تراجع النتيجة وتعدل أو تضيف أي حاجة بعد كده. وفي حالة السكريبتات "
    "الصعبة، تقدر ترفع ملف JSON جاهز من أي AI (شوف التفاصيل تحت).":
        "Upload your screenplay (.docx or .txt), and the system will try to detect each scene's number, "
        "INT/EXT, day/night, location, and dialogue, and auto-fill the Script tab. You can review and edit "
        "or add anything afterwards. For tricky scripts, you can upload a ready-made JSON file from any AI "
        "(see details below).",
    "لأفضل نتيجة، اكتب كل مشهد في سطر بصيغة زي: "
    "\"مشهد 1 - داخلي - نهار - غرفة المعيشة\"، والحوار في سطر منفصل بصيغة "
    "\"اسم الشخصية: الكلام\".":
        "For best results, write each scene on a line like: "
        "\"Scene 1 - INT - Day - Living Room\", and dialogue on a separate line like "
        "\"Character Name: line\".",
    "📋 السكريبت شكله معقد والبرنامج مبيحللوش كويس؟ استخدم أي AI بدله":
        "📋 Script format too complex and the app can't parse it well? Use any AI instead",
    "لو شكل سكريبتك غريب أو التحليل التلقائي مبيطلعش نتيجة كويسة، اتبع الخطوات البسيطة دي:":
        "If your script's format is unusual or the automatic analysis isn't giving good results, follow these simple steps:",
    "**1.** دوس على زرار \"📋 نسخ البرومبت\" تحت (هيتنسخ تلقائي).\n\n"
    "**2.** روح لبرنامج الـ AI اللي بتستخدمه (Claude، ChatGPT، Gemini...) وافتح محادثة جديدة.\n\n"
    "**3.** الصق البرومبت اللي نسخته، وارفق معاه ملف السكريبت (PDF أو نص) أو الصق نص "
    "السكريبت كامل بعد البرومبت.\n\n"
    "**4.** بعد ما الـ AI يرد عليك بالنتيجة، احفظها في ملف اسمه `script.json`.\n\n"
    "**5.** ارفع ملف `script.json` ده من الزرار تحت في الصفحة دي زي أي ملف تاني، وهيتم "
    "استيراده تلقائي.":
        "**1.** Click the \"📋 Copy Prompt\" button below (it copies automatically).\n\n"
        "**2.** Go to the AI app you use (Claude, ChatGPT, Gemini...) and open a new chat.\n\n"
        "**3.** Paste the prompt you copied, and attach the script file (PDF or text) or paste the "
        "full script text after the prompt.\n\n"
        "**4.** Once the AI replies with the result, save it to a file named `script.json`.\n\n"
        "**5.** Upload that `script.json` file from the button below on this page like any other file, "
        "and it will be imported automatically.",
    "اضغط على أيقونة النسخ 📋 اللي هتظهر فوق يمين الصندوق ده عشان تاخد البرومبت كامل دفعة واحدة":
        "Click the 📋 copy icon that appears at the top of this box to copy the whole prompt at once",
    "اختر ملف السكريبت": "Choose script file", "🔍 تحليل الملف": "🔍 Analyze File",
    "🚫 استبعد المشهد ده من الاستيراد (مثلاً لو ده صفحة عنوان مش مشهد حقيقي)":
        "🚫 Exclude this scene from import (e.g. if it's a title page, not a real scene)",
    "الشخصيات المكتشفة — شيل أي حاجة مش اسم شخصية فعلي (زي نوع الفيلم أو التاريخ أو المكان)":
        "Detected characters — remove anything that isn't a real character name (like genre, date, or location)",
    "مفيش شخصيات اتكشفت في المشهد ده": "No characters detected in this scene",
    "مشهد": "Scene", "مكان غير محدد": "Location not specified",
    "🧑‍🤝‍🧑 لقينا أسماء شخصيات متشابهة — هي نفس الشخصية؟":
        "🧑‍🤝‍🧑 We found similar character names — are they the same character?",
    "الأسماء:": "Names:",
    "دمجهم في شخصية واحدة": "Merge into one character", "لأ، شخصيات مختلفة": "No, different characters",
    "اختار الاسم اللي هيتسجل بيه في المشروع": "Choose the name to register in the project",
    "🏠 لقينا أماكن متشابهة — هي حالات مختلفة لنفس المكان؟":
        "🏠 We found similar locations — are they different states of the same place?",
    "مثال: \"سطح اليخت\" و\"سطح اليخت بعد لحظات\" غالبًا نفس المكان في وقتين مختلفين، "
    "مش مكانين منفصلين. لو دمجتهم، الاسم الأصلي هيتسجل كحالة (Variant) تحت المكان الرئيسي.":
        "Example: \"Yacht Deck\" and \"Yacht Deck, moments later\" are usually the same place at two "
        "different times, not two separate locations. If you merge them, the original name will be "
        "registered as a Variant under the main location.",
    "الأماكن:": "Locations:",
    "دمجهم كحالات لنفس المكان الرئيسي": "Merge as variants of the same main location",
    "لأ، أماكن مختلفة فعلاً": "No, they're actually different locations",
    "اختار اسم المكان الرئيسي اللي هيتسجل بيه": "Choose the main location name to register",
    "🔵 تأكيد وإضافة كل المشاهد للمشروع": "🔵 Confirm and Add All Scenes to Project",
    "🗑️ إلغاء ومسح النتائج": "🗑️ Cancel and Clear Results",
    # الأماكن
    "لو عندك مكان رئيسي وجواه أماكن فرعية (زي شقة حسام وجواها غرفة نوم)، "
    "أضف المكان الرئيسي الأول، وبعدين أضف المكان الفرعي واختار له 'تابع لمكان رئيسي'.":
        "If you have a main location with sub-locations inside it (like an apartment with a bedroom "
        "inside), add the main location first, then add the sub-location and set its 'belongs to a main "
        "location' field.",
    "اسم المكان": "Location Name", "تابع لمكان رئيسي؟": "Belongs to a main location?",
    "وصف عام ثابت للمكان": "General Fixed Description",
    "إضافة مكان": "Add Location",
    "اختر مكان لإضافة حالة (Variant) له": "Choose a location to add a Variant for",
    "اسم الحالة": "Variant Name", "داخلي/خارجي": "INT/EXT", "النهار/الليل": "Day/Night",
    "حالة الطقس": "Weather", "وصف التغييرات الخاصة بهذه الحالة": "Description of changes for this variant",
    "صورة مرجعية (اختياري)": "Reference image (optional)", "إضافة الحالة": "Add Variant",
    "مفيش أماكن مضافة لسه": "No locations added yet",
    "🗑️ حذف المكان (وكل حالاته)": "🗑️ Delete Location (and all its variants)",
    "تم تعديل المكان": "Location updated",
    "معرفش أمسح المكان ده لأنه مستخدم في مشهد، أو ليه أماكن فرعية تابعة له. شيل الارتباطات دي الأول.":
        "Can't delete this location because it's used in a scene, or has sub-locations. Remove those links first.",
    "تم حذف المكان": "Location deleted",
    "**الحالات (Variants):**": "**Variants:**",
    "لو نفس المكان بيتكرر في السكريبت بعد وقت (زي 'سطح اليخت' تاني بعد لحظات)، أضف حالة جديدة بدل ما تعمل مكان جديد مكرر.":
        "If the same location recurs later in the script (like 'Yacht Deck' again a bit later), add a new "
        "variant instead of creating a duplicate location.",
    "مفيش حالات مضافة لسه": "No variants added yet",
    "المكان (غيّره لو عايز تنقل الحالة دي لمكان تاني — مفيد لدمج أماكن مكررة)":
        "Location (change it to move this variant to another location — useful for merging duplicates)",
    "تغيير الصورة المرجعية": "Change reference image", "🗑️ حذف الحالة": "🗑️ Delete Variant",
    "تم تعديل الحالة": "Variant updated",
    "معرفش أمسح الحالة دي لأنها مستخدمة في مشهد أو أكتر. شيلها من المشاهد دي الأول من تبويب السكريبت.":
        "Can't delete this variant because it's used in one or more scenes. Remove it from those scenes first from the Script tab.",
    "تم حذف الحالة": "Variant deleted",
    # الشخصيات
    "اسم الشخصية": "Character Name", "نوع الدور": "Role Type",
    "بطل": "Hero", "شرير": "Villain", "مساعد": "Supporting", "كومبارس": "Extra",
    "نوع الكائن": "Species", "الجنس": "Gender",
    "إنسان": "Human", "حيوان": "Animal", "كائن خيالي": "Fantasy Creature",
    "ذكر": "Male", "أنثى": "Female",
    "ملاحظات عامة عن الشخصية": "General Character Notes",
    "زي الوزن والبنية الجسمانية (نحيف/تخين/رياضي...) وأي تفاصيل تانية":
        "Like weight and body type (thin/heavy/athletic...) and any other details",
    "صورة الشخصية المرجعية (اختياري)": "Character reference image (optional)",
    "إضافة شخصية": "Add Character",
    "اختر شخصية لإضافة مظهر إضافي لها": "Choose a character to add an extra look for",
    "المظهر الإضافي بيمثل شكل تاني للشخصية في لحظة مختلفة من القصة (مثال: حلق دقنه، لابس نضارة، اتصاب وبقى في جبس).":
        "An extra look represents a different appearance for the character at a different point in the "
        "story (e.g. shaved his beard, wearing glasses, injured and in a cast).",
    "اسم المظهر الإضافي": "Extra Look Name", "السن الظاهر": "Apparent Age",
    "حالة المكياج": "Makeup State",
    "طبيعي": "Natural", "كامل": "Full", "بدون": "None", "آثار إصابة": "Injury marks", "مكياج شيخوخة": "Aging makeup",
    "حالة الشعر": "Hair State", "وصف الملابس والإكسسوارات": "Wardrobe & Accessories Description",
    "وصف تفصيلي كامل للمظهر (يُستخدم كمرجع للتوليد)": "Full detailed look description (used as a generation reference)",
    "➕ إضافة مظهر إضافي": "➕ Add Extra Look",
    "مفيش شخصيات مضافة لسه": "No characters added yet",
    "🗑️ حذف الشخصية (وكل مظاهرها)": "🗑️ Delete Character (and all its looks)",
    "تم تعديل الشخصية": "Character updated",
    "اسم الشخصية مينفعش يبقى فاضي": "Character name can't be empty",
    "معرفش أمسح الشخصية دي لأن مظهر بتاعها مستخدم في لقطة أو أكتر. شيلها من اللقطات دي الأول من تبويب التفريغ.":
        "Can't delete this character because one of its looks is used in a shot. Remove it from those shots first from the Breakdown tab.",
    "تم حذف الشخصية": "Character deleted",
    "**المظاهر الإضافية:**": "**Extra Looks:**",
    "مفيش مظاهر إضافية متضافة لسه": "No extra looks added yet",
    "تغيير صورة الشخصية المرجعية": "Change character reference image",
    "🗑️ حذف المظهر الإضافي": "🗑️ Delete Extra Look",
    "تم تعديل المظهر الإضافي": "Extra look updated",
    "معرفش أمسح المظهر ده لأنه مستخدم في لقطة أو أكتر. شيله من اللقطات دي الأول من تبويب التفريغ.":
        "Can't delete this look because it's used in one or more shots. Remove it from those shots first from the Breakdown tab.",
    "تم حذف المظهر الإضافي": "Extra look deleted",
    # المشاهد
    "رقم المشهد": "Scene Number", "التوقيت": "Time of Day", "المكان": "Location", "الطقس": "Weather",
    "ملاحظات المشهد العامة": "General Scene Notes", "إضافة مشهد": "Add Scene",
    "🗑️ حذف المشهد (وكل لقطاته)": "🗑️ Delete Scene (and all its shots)",
    "حذف": "Delete", "مشهد مختار (وكل لقطاتهم)": "selected scene(s) (and all their shots)",
    "تم حذف المشاهد المختارة": "Selected scenes deleted",
    "تم تعديل المشهد": "Scene updated", "تم حذف المشهد": "Scene deleted",
    # التفريغ
    "لازم تضيف مشهد واحد على الأقل من تبويب السكريبت أولًا": "You need to add at least one scene from the Script tab first",
    "اختر المشهد": "Choose scene", "رقم اللقطة": "Shot Number", "حجم الكادر": "Shot Size",
    "حركة الكاميرا": "Camera Movement", "زاوية الكاميرا": "Camera Angle", "المدة (ثانية)": "Duration (seconds)",
    "قوة المشاعر": "Emotion Intensity", "وصف المشاعر": "Emotion Description",
    "الحوار (لو موجود)": "Dialogue (if any)", "ملاحظات النمط البصري / المرجع": "Visual Style Notes / Reference",
    "تضمين موسيقى في التوليد نفسه؟ (غير مستحسن)": "Include music in the generation itself? (not recommended)",
    "**الشخصيات الموجودة في اللقطة**": "**Characters in this shot**",
    "اختر مظهر كل شخصية ظاهرة": "Choose the look for each visible character",
    "🔵 تمت المراجعة والموافقة على كل بيانات اللقطة": "🔵 Reviewed and approved all shot data",
    "صورة ستوري بورد مرجعية (اختياري)": "Reference storyboard image (optional)",
    "حفظ اللقطة": "Save Shot", "تم حفظ اللقطة": "Shot saved",
    "🗑️ حذف اللقطة": "🗑️ Delete Shot", "تم تعديل اللقطة": "Shot updated", "تم حذف اللقطة": "Shot deleted",
    "تغيير صورة الستوري بورد المرجعية": "Change reference storyboard image",
    "لقطة": "Shot",
    # لوحة المتابعة
    "📄 تصدير تفريغ اللقطات": "📄 Export Shot Breakdown",
    "ملف تفريغ كامل قابل للطباعة، بفورمات سينمائي احترافي.":
        "A complete, printable breakdown file, in a professional cinema format.",
    "👉 الخطوة الجاية: روح تبويب **الأماكن** و**الشخصيات** وضيف الأماكن والشخصيات الأساسية في مشروعك.":
        "👉 Next step: go to the **Locations** and **Characters** tabs and add your project's core locations and characters.",
    "👉 الخطوة الجاية: روح تبويب **السكريبت (المشاهد)** وضيف مشاهد مشروعك (أو استوردها من ملف في تبويب استيراد السكريبت).":
        "👉 Next step: go to the **Script (Scenes)** tab and add your project's scenes (or import them from a file in the Import Script tab).",
    "👉 الخطوة الجاية: روح تبويب **التفريغ (اللقطات)** وابدأ تفرّغ كل مشهد للقطات كاميرا تفصيلية.":
        "👉 Next step: go to the **Breakdown (Shots)** tab and start breaking down each scene into detailed camera shots.",
    "لسه مفيش لقطات مضافة": "No shots added yet",
    "نسبة اللقطات الجاهزة للتوليد": "Shots ready for generation",
    "🎉 كل اللقطات اتراجعت وأتأكد منها. بيانات مشروعك دلوقتي متكاملة وجاهزة كمرجع كامل للإنتاج. "
    "البرنامج الحالي بيوقف هنا — التوليد الفعلي بالذكاء الاصطناعي مش متاح جوه البرنامج ده لسه، "
    "ومحتاج تطوير إضافي يربطه بأدوات التوليد.":
        "🎉 All shots have been reviewed and confirmed. Your project data is now complete and ready as a "
        "full production reference. The app stops here for now — actual AI generation isn't available in "
        "this app yet, and needs further development to connect it to generation tools.",
    "👉 راجع اللقطات اللي لسه مش متأكد منها (🟡) من تبويب التفريغ، وعلّم 'تمت المراجعة' لما تخلص كل واحدة.":
        "👉 Review the shots that aren't confirmed yet (🟡) from the Breakdown tab, and check 'Reviewed' once you finish each one.",
    "محتاجة مراجعة": "Needs review",
    # أجزاء نصوص ديناميكية (بتتلحق بأرقام أو قوائم وقت التشغيل)
    "حصل خطأ أثناء تحليل الملف:": "Error while analyzing the file:",
    "تم التعرف على": "Detected",
    "مشهد في الملف. راجعهم وعدّل أي حاجة غلط قبل التأكيد:": "scene(s) in the file. Review them and fix anything wrong before confirming:",
    "هيتستبعد": "Will exclude",
    "مشهد من الاستيراد حسب اختيارك فوق.": "scene(s) from the import based on your selection above.",
    "تم إضافة": "Added",
    "مشهد جديد.": "new scene(s).",
    "شخصيات جديدة:": "New characters:",
    "أماكن جديدة:": "New locations:",
    "إكسسوارات جديدة:": "New props:",
    "أي حاجة بيمسكها أو بيستخدمها أي شخصية أو ليها دور في حدث المشهد (سكينة، تليفون، شنطة، سلاح...). "
    "تقدر تربط الإكسسوار بشخصية معينة (زي مسدس البطل)، وتعلّم عليه لو حساس للراكورد (يعني لازم يفضل في "
    "نفس الحالة بين اللقطات المتتالية).":
        "Anything a character holds or uses, or that plays a role in the scene's action (a knife, phone, "
        "bag, weapon...). You can link a prop to a specific character (like the hero's gun), and mark it "
        "as continuity-sensitive (meaning it must stay in the same state across consecutive shots).",
    "اسم الإكسسوار": "Prop Name",
    "مثال: سكينة عم جابر": "e.g. Am Gaber's knife",
    "حساس للراكورد؟ (لازم يفضل في نفس الحالة بين اللقطات)": "Continuity-sensitive? (must stay consistent across shots)",
    "مرتبط بشخصية (اختياري)": "Linked to a character (optional)",
    "إضافة إكسسوار": "Add Prop",
    "اسم الإكسسوار مينفعش يبقى فاضي": "Prop name can't be empty",
    "مفيش إكسسوارات مضافة لسه": "No props added yet",
    "مرتبط بـ": "Linked to",
    "🗑️ حذف الإكسسوار": "🗑️ Delete Prop",
    "تم تعديل الإكسسوار": "Prop updated",
    "تم حذف الإكسسوار": "Prop deleted",
    "بدون - غير مرتبط بشخصية": "None - not linked to a character",
    "لكل شخصية، حدد لو ليها حوار في اللقطة دي (سيبها فاضية لو الشخصية موجودة بس ساكتة)":
        "For each character, mark whether they have dialogue in this shot (leave unchecked if the character is present but silent)",
    "لها حوار في اللقطة دي؟": "Has dialogue in this shot?",
    "الإكسسوارات الموجودة في اللقطة": "Props in this shot",
    "اختر الإكسسوارات الظاهرة في اللقطة": "Choose the props visible in the shot",
    "✅ تم الحفظ": "✅ Saved",
    "الإعدادات": "Settings",
    "الشخصيات الموجودة في المشهد": "Characters in this scene",
    "الإكسسوارات الموجودة في المشهد": "Props in this scene",
    "الرقم ده كان مستخدم - تم نقل باقي المشاهد رقم واحد لقدام عشان تتزبط.":
        "That number was already in use — the rest of the scenes were shifted forward by one to make room.",
    "الرقم ده كان مستخدم - تم نقل باقي اللقطات رقم واحد لقدام عشان تتزبط.":
        "That number was already in use — the rest of the shots were shifted forward by one to make room.",
    "🔄 استخراج الشخصيات من نص المشاهد (لمشاريع قديمة)": "🔄 Extract Characters from Scene Text (for older projects)",
    "لو المشروع ده استوردته قبل ما ميزة ربط الشخصيات بالمشاهد تتضاف، التقارير (كشف الشخصيات، "
    "التفريغ العام) هتبقى فاضية لحد ما تربط كل مشهد بشخصياته يدويًا، أو تدوس هنا عشان نحاول نلاقي "
    "أسماء شخصيات مكتبتك داخل نص كل مشهد ونربطها أوتوماتيك (من غير ما نمسح أي ربط موجود بالفعل).":
        "If you imported this project before the scene-character linking feature was added, the reports "
        "(Characters Sheet, General Breakdown) will stay empty until you manually link each scene to its "
        "characters, or click here so we try to find your character library's names inside each scene's "
        "text and link them automatically (without removing any existing links).",
    "🔍 ابحث واربط الشخصيات دلوقتي": "🔍 Find and Link Characters Now",
    "تم ربط": "Linked",
    "علاقة شخصية-مشهد جديدة.": "new character-scene link(s).",
    "دول سطور الحوار اللي لسه في حوار المشهد ومتحطوش في لقطة تانية - اختار بس اللي موجود في "
    "اللقطة دي (سيبها من غير اختيار لو اللقطة من غير حوار).":
        "These are the scene's dialogue lines not yet placed in another shot — pick only the ones "
        "that are in this shot (leave unselected if this shot has no dialogue).",
    "سطور الحوار المتاحة من حوار المشهد": "Available dialogue lines from the scene",
    "أو اكتب/عدّل الحوار يدويًا بدل الاختيار": "Or write/edit dialogue manually instead of selecting",
    "⚙️ الإعدادات": "⚙️ Settings",
    "تم تخطي مشاهد أرقام": "Skipped scene numbers",
    "لأنها موجودة بالفعل.": "because they already exist.",
    # أمثلة placeholder وعناوين من غير رموز/ماركداون حواليها
    "مثال: عروسة البحر": "e.g. The Sea Bride",
    "مثال: أحمد محمد": "e.g. Ahmed Mohamed",
    "مثال: شقة حسام": "e.g. Hossam's Apartment",
    "مثال: شقة قديمة في حي شعبي، جدرانها بيج فاتح، فيها أثاث خشبي تقيل":
        "e.g. An old apartment in a popular neighborhood, light beige walls, heavy wooden furniture",
    "مثال: أحمد": "e.g. Ahmed",
    "مثال: شتاء مشمس، أو صيف حار وضبابي": "e.g. Sunny winter, or hot hazy summer",
    "مثال: حزن مكتوم": "e.g. Suppressed sadness",
    "مثال: أحمد: إزيك يا سارة؟\nسارة: تمام والحمد لله.": "e.g. Ahmed: How are you, Sara?\nSara: I'm fine, thank God.",
    "مثال: إضاءة دافية، ألوان بيج وبني، حركة كاميرا هادئة": "e.g. Warm lighting, beige and brown tones, calm camera movement",
    "مثال: نهار - أول مرة، أو: بعد لحظات": "e.g. Day - first time, or: moments later",
    "مثال: المكان اتحرق واتهد بعد حريق في نص الأحداث": "e.g. The place burned down and collapsed after a fire mid-story",
    "اسم المكان مينفعش يبقى فاضي": "Location name can't be empty",
    "الحالات (Variants):": "Variants:",
    "مثال: المظهر الرئيسي - حلق دقنه ولابس نضارة": "e.g. Main look - shaved beard and wearing glasses",
    "مثال: 30 سنة": "e.g. 30 years old",
    "مثال: شعر قصير أسود": "e.g. Short black hair",
    "مثال: قميص أبيض وبنطلون جينز وساعة يد": "e.g. White shirt, jeans, and a wristwatch",
    "مثال: راجل في الثلاثينات، نحيف، شعره قصير أسود، لابس نضارة طبية...":
        "e.g. A man in his thirties, thin, short black hair, wearing prescription glasses...",
    "المظاهر الإضافية:": "Extra Looks:",
    "وصف تفصيلي كامل للمظهر": "Full Detailed Look Description",
    "الشخصيات الموجودة في اللقطة": "Characters in this shot",
    "حالة المكان": "Location Condition",
    "مثال: الشكل الرئيسي للمكان، أو: المكان محروق، أو: المكان بعد التجديد":
        "e.g. Main look of the location, or: place burned down, or: place after renovation",
    "وصف الحركة داخل اللقطة": "Action Description Within the Shot",
    "مثال: أحمد بيدخل الأوضة وبيقفل الباب وراه، سارة واقفة جنب الشباك بتبص برة":
        "e.g. Ahmed enters the room and closes the door behind him, Sara is standing by the window looking outside",
    "مثال: أحمد حزين، سارة غير مهتمة": "e.g. Ahmed is sad, Sara is indifferent",
    "مثال: أحمد (حزين): إزيك يا سارة؟\nسارة (غير مبالية): تمام والحمد لله.":
        "e.g. Ahmed (sad): How are you, Sara?\nSara (indifferent): I'm fine, thank God.",
    "🔄 تحديث الملفات": "🔄 Refresh Files",
    "لو عدّلت محتوى لقطة موجودة (حوار، وصف...) من غير ما تضيف أو تمسح لقطات، دوس هنا عشان الملفات تتحدث بآخر بياناتك.":
        "If you edited an existing shot's content (dialogue, description...) without adding or deleting shots, click here to refresh the files with your latest data.",
    "📋 تقارير الإنتاج القياسية": "📋 Standard Production Reports",
    "نفس الأوراق القياسية اللي بيستخدمها مديرو الإنتاج (كشف الشخصيات، التفريغ العام، كشف أماكن "
    "التصوير)، متملية أوتوماتيك من بيانات مشروعك. الخانات اللي محتاجة قرار بشري (زي الترشيح، عدد "
    "أيام التصوير، عدد الصفحات) سايبينها فاضية عشان تملاها إنت وقت التحضير الفعلي للتصوير.":
        "The same standard sheets production managers use (Characters Sheet, General Breakdown, "
        "Filming Locations Sheet), auto-filled from your project data. Fields that need a human "
        "decision (like casting nomination, shooting days, page count) are left blank for you to "
        "fill in during actual production prep.",
    "⬇️ كشف الشخصيات": "⬇️ Characters Sheet",
    "⬇️ التفريغ العام": "⬇️ General Breakdown",
    "⬇️ كشف أماكن التصوير": "⬇️ Filming Locations Sheet",
    "⬇️ كشف الإكسسوار": "⬇️ Props Sheet",
}


def t(text):
    """يترجم نص عربي جاهز (مش مفتاح مجرد) للإنجليزي لو الواجهة إنجليزي دلوقتي،
    وبيرجعه زي ما هو لو مفيش ترجمة متسجلة أو لو اللغة عربي."""
    if st.session_state.get("ui_lang", "ar") != "en":
        return text
    return TRANSLATIONS.get(text, text)


def fmt_int_ext(value):
    """عرض ثنائي اللغة دايمًا لداخلي/خارجي (مصطلح سينمائي عالمي)، إلا لو
    القيمة 'غير محدد' فبتتبع لغة الواجهة العادية."""
    if value == "غير محدد":
        return t("غير محدد")
    return bilingual_label(value, INT_EXT_LABELS)


def fmt_day_night(value):
    """عرض ثنائي اللغة دايمًا لتوقيت المشهد (نهار/ليل/غروب/فجر)، إلا لو
    القيمة 'غير محدد' فبتتبع لغة الواجهة العادية."""
    if value == "غير محدد":
        return t("غير محدد")
    return bilingual_label(value, DAY_NIGHT_LABELS)


_APP_DESCRIPTION = (
    "البرنامج ده بيساعدك تجهز وتنظم بيانات الإنتاج كلها (الأماكن، الشخصيات، المشاهد، تفريغ اللقطات) "
    "وتتأكد إنها متكاملة وجاهزة. مفيش مرحلة توليد فيديو فعلي بالذكاء الاصطناعي جوه البرنامج ده لسه — "
    "دي خطوة مستقبلية محتاجة تطوير إضافي لربطها بأدوات التوليد."
)

_CSS_TEMPLATE = """
        <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;600;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600;700&display=swap" rel="stylesheet">
    
    <style>
    /* اتجاه الواجهة: يمين-لشمال للعربي، شمال-ليمين للإنجليزي - بيتغير
       تلقائيًا مع زرار EN/AR، وبيخلي النص يترتب صح جوه نفسه */
    .stApp {
        direction: __DIR__;
    }
    /* شريط Deploy/القائمة بتاع Streamlit - بيتقلب للناحية المقابلة وقت
       العربي عشان ميتلخبطش مع الشريط الجانبي اللي بيبقى واقف في نفس الناحية */
    header[data-testid="stHeader"] [data-testid="stToolbar"] {
        flex-direction: __ROWDIR__;
    }
    .stApp .stTextInput input,
    .stApp .stTextArea textarea,
    .stApp .stNumberInput input {
        text-align: __ALIGN__;
    }
    /* عناصر لازم تفضل شمال-ليمين زي هي (كود إنجليزي، أرقام قوائم منسدلة) */
    .stApp code, .stApp pre {
        direction: ltr;
        text-align: left;
    }
    /* IBM Plex Sans Arabic for Arabic text */
    .stApp {
        font-family: "IBM Plex Sans Arabic", "IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    [dir="rtl"] {
        font-family: "IBM Plex Sans Arabic", -apple-system, BlinkMacSystemFont, sans-serif;
    }
    [dir="ltr"] {
        font-family: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    /* Streamlit نفسه بيحط text-align: left افتراضيًا على العناوين والنصوص
       التوضيحية (caption) وفقرات الـ markdown، من غير ما يهتم باتجاه
       الصفحة - فبنجبرها تتبع اتجاه اللغة الحالية (يمين للعربي، شمال
       للإنجليزي) عشان النص التوضيحي/العناوين تقرأ صح من نفس جهة القراءة.
       الحاجات اللي إحنا عايزينها في النص بالذات (زي اسم المشروع) ليها
       تنسيق inline خاص بيها بيغلب القاعدة العامة دي */
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
    .stApp [data-testid="stCaptionContainer"],
    .stApp [data-testid="stMarkdownContainer"] p {
        text-align: __ALIGN__;
    }
    /* اسم كل خانة يتحط فوق ومنتصف الخانة، باللون الأصفر (في المحتوى الرئيسي) */
    [data-testid="stWidgetLabel"] {
        width: 100%;
    }
    [data-testid="stWidgetLabel"] p,
    [data-testid="stWidgetLabel"] label {
        width: 100%;
        text-align: center;
        color: #E8B923 !important;
        font-weight: 600;
    }
    /* الشريط الجانبي بالكامل أصفر - نفس اتجاه الواجهة، وبيقلب مكانه
       (يمين للعربي، شمال للإنجليزي) */
    section[data-testid="stSidebar"] {
        direction: __DIR__;
        background-color: #E8B923;
    }
    section[data-testid="stSidebar"] * {
        color: #12203D !important;
    }
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] label {
        color: #12203D !important;
    }
    /* لو الشريط الجانبي بيتقفل/بيتفتح (أنيميشن العرض بيتغير من صفر للكامل)،
       لازم النص ميلفش رأسي حرف تحت حرف - يفضل مقصوص بالعرض بس (…) */
    section[data-testid="stSidebar"] .cf-sidebar-header {
        overflow: hidden;
    }
    section[data-testid="stSidebar"] .cf-sidebar-header .cf-title {
        font-size: 22px;
        font-weight: 800;
        line-height: 1.3;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    section[data-testid="stSidebar"] .cf-sidebar-header .cf-subtitle {
        font-size: 13px;
        opacity: 0.85;
        margin-top: 2px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    section[data-testid="stSidebar"] {
        overflow-x: hidden !important;
    }
    /* صندوق صغير حوالين وصف البرنامج - بيوضح إنه مجرد تنويه، مش اختيار قابل للضغط */
    section[data-testid="stSidebar"] .cf-sidebar-header .cf-desc-box {
        font-size: 11px;
        line-height: 1.5;
        opacity: 0.9;
        margin-top: 10px;
        padding: 8px 10px;
        border: 1px solid rgba(18, 32, 61, 0.35);
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.18);
    }
    /* صندوق صغير لعرض بيانات المستخدم الحالي (الاسم والوظيفة) فوق الإعدادات -
       أبيض صريح، عشان يبقى مميز عن باقي عناصر الشريط الجانبي الأصفر */
    section[data-testid="stSidebar"] .cf-owner-box {
        font-size: 13px;
        font-weight: 600;
        line-height: 1.5;
        margin: 4px 0 10px 0;
        padding: 10px 12px;
        border: 1px solid rgba(18, 32, 61, 0.25);
        border-radius: 8px;
        background: #FFFFFF;
        color: #12203D;
    }
    /* نصوص جوه صناديق الإدخال والأزرار (خلفيتها غامقة من الثيم) لازم تفضل
       فاتحة عشان تتقرا فوق الخلفية الغامقة بتاعتها هي (مش الأصفر اللي حواليها) */
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] textarea,
    section[data-testid="stSidebar"] [data-baseweb="select"] *,
    section[data-testid="stSidebar"] .stButton button,
    section[data-testid="stSidebar"] .stButton button p,
    section[data-testid="stSidebar"] .stButton button span,
    section[data-testid="stSidebar"] .stDownloadButton button {
        color: #F5F1E6 !important;
    }
    /* خلفية غامقة صريحة لكل الأزرار في الشريط الجانبي، عشان النص الفاتح
       يفضل واضح فوقها مهما كان لون الثيم الافتراضي للزرار */
    section[data-testid="stSidebar"] .stButton button,
    section[data-testid="stSidebar"] .stDownloadButton button {
        background-color: #12203D !important;
        border: 1px solid #12203D !important;
    }
    section[data-testid="stSidebar"] .stButton button:hover,
    section[data-testid="stSidebar"] .stDownloadButton button:hover {
        background-color: #1B2E52 !important;
        border-color: #E8B923 !important;
        color: #F5F1E6 !important;
    }
    section[data-testid="stSidebar"] .stButton button:disabled,
    section[data-testid="stSidebar"] .stButton button:disabled p {
        color: #8A93A6 !important;
        background-color: #16233F !important;
        opacity: 0.7;
    }
    /* زرار الإعدادات - مربع وأزرق ومختلف شكلًا ولونًا عن باقي أزرار
       الشريط الجانبي (زي ما طلب المستخدم)، بترس أبيض في النص */
    section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
        background-color: #2D9CDB !important;
        border: 1px solid #2D9CDB !important;
        color: #FFFFFF !important;
        width: 44px !important;
        height: 44px !important;
        min-width: 44px !important;
        padding: 0 !important;
        font-size: 20px !important;
        border-radius: 10px !important;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:hover {
        background-color: #268BC4 !important;
        border-color: #FFFFFF !important;
    }
    section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] p {
        color: #FFFFFF !important;
        font-size: 20px !important;
    }
    .cf-settings-label {
        font-weight: 700;
        padding-top: 10px;
    }
    /* علامة ميكروفون خفيفة على كل خانة كتابة - مجرد تنويه إننا فاكرين
       ميزة الكتابة بالصوت وهنضيفها لاحقًا، مش شغالة فعليًا دلوقتي.
       بنستخدم أيقونة Material Symbols (نفس خط الأيقونات اللي Streamlit
       نفسه بيستخدمه) بدل الإيموجي، عشان تبقى شكلها بسيط وكلاسيكي وتقدر
       تتلوّن أبيض بدل ما تيجي بألوان الإيموجي الثابتة. */
    [data-testid="stTextInputRootElement"], [data-testid="stTextAreaRootElement"] {
        position: relative;
    }
    [data-testid="stTextInputRootElement"]::after,
    [data-testid="stTextAreaRootElement"]::after {
        content: "mic";
        font-family: "Material Symbols Rounded";
        font-weight: normal;
        font-style: normal;
        position: absolute;
        left: 10px;
        font-size: 14px;
        color: #F5F1E6;
        opacity: 0.55;
        pointer-events: none;
        z-index: 1;
    }
    /* في خانة سطر واحد بتتوسط رأسيًا جوه الصندوق؛ في الخانة الطويلة (Textarea)
       بتقف أعلى الصندوق من جوه عشان متتلخبطش مع النص وهو بيكبر لأسفل */
    [data-testid="stTextInputRootElement"]::after { top: 50%; transform: translateY(-50%); }
    [data-testid="stTextAreaRootElement"]::after { top: 8px; }
    /* نص المثال (placeholder) يفضل شفاف أكتر عشان يبان إنه نص مؤقت للتوضيح
       بس، ويختفي تمامًا وقت التركيز/الكتابة في الخانة عشان ميتزنقش مع أي
       تلميح تاني زي "Press Enter to..." - وبيرجع يظهر تاني لو رجعت الخانة فاضية */
    .stApp input::placeholder,
    .stApp textarea::placeholder {
        opacity: 0.4 !important;
    }
    .stApp input:focus::placeholder,
    .stApp textarea:focus::placeholder {
        opacity: 0 !important;
    }
    /* تلميح "Press Enter to apply/submit" بتاع Streamlit - نص إنجليزي قصير،
       فبيفضل من الشمال ولاتجاه LTR، وبخط أصغر، وبمسافة تبعده عن حواف
       الخانة عشان ميتداخلش مع أي نص جوه الخانة نفسها */
    [data-testid="InputInstructions"] {
        text-align: left !important;
        direction: ltr !important;
        font-size: 10px !important;
        opacity: 0.55 !important;
        top: auto !important;
        bottom: -20px !important;
        right: auto !important;
        left: 4px !important;
    }
    /* عنوان أي قسم قابل للطي (expander) في الشريط الجانبي - خلفية وحدود
       واضحة بشكل ثابت، عشان النص والسهم يفضلوا باينين في أي حالة (مقفول،
       مفتوح، عليه الماوس) من غير ما يعتمدوا على خلفية شفافة ممكن تختفي فيها */
    section[data-testid="stSidebar"] [data-testid="stExpander"] {
        background-color: rgba(18, 32, 61, 0.07);
        border: 1px solid rgba(18, 32, 61, 0.3);
        border-radius: 10px;
        margin-bottom: 6px;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary,
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary p,
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary span {
        color: #12203D !important;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover,
    section[data-testid="stSidebar"] [data-testid="stExpander"] details[open] summary {
        background-color: rgba(18, 32, 61, 0.14) !important;
        border-radius: 8px;
    }
    /* علامة "تم الحفظ" - نص رفيع بسيط على أرضية التصميم، مش شكل زرار،
       بتفضل ظاهرة بعد الحفظ لحد ما المستخدم يحفظ سجل تاني */
    .cf-saved-badge {
        font-size: 12px;
        font-weight: 400;
        color: #F5F1E6;
        opacity: 0.75;
        margin-top: -6px;
        margin-bottom: 8px;
    }
    /* فاصل بصري خفيف بين كل اقتراح دمج (شخصيات/أماكن متشابهة) وبعضه،
       عشان القايمة الطويلة متبقاش سايحة من غير حدود واضحة بين الأسئلة */
    hr.cf-soft-sep {
        border: none;
        border-top: 1px solid rgba(245, 241, 230, 0.16);
        margin: 18px 0;
    }
    /* بادج علامة الصح - أزرق فاتح دايمًا (مش أخضر) عشان يفضل متماشي مع
       بالتة ألوان البراند (أصفر / أزرق فاتح / كحلي غامق / أبيض / رمادي) */
    .cf-check-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 16px;
        height: 16px;
        border-radius: 4px;
        background: #2D9CDB;
        color: #FFFFFF;
        font-size: 11px;
        font-weight: 800;
        line-height: 1;
    }
    textarea {
        resize: vertical !important;
        min-height: 90px !important;
    }
    textarea::-webkit-resizer {
        background: repeating-linear-gradient(
            135deg,
            #E8B923, #E8B923 3px,
            #12203D 3px, #12203D 6px
        );
    }
    .cf-stepper {
        display: flex;
        gap: 10px;
        margin: 10px 0 14px 0;
    }
    .cf-stage {
        flex: 1;
        text-align: center;
        padding: 14px 6px;
        border-radius: 14px;
        background: #16233F;
        border: 2px solid transparent;
    }
    .cf-stage-icon { font-size: 16px; margin-bottom: 5px; }
    .cf-stage-icon .cf-check-badge { width: 20px; height: 20px; font-size: 13px; border-radius: 6px; }
    .cf-stage-label { font-size: 12px; font-weight: 600; color: #F5F1E6; }
    .cf-stage-done { background: rgba(45, 156, 219, 0.14); border-color: #2D9CDB; }
    .cf-stage-current { border-color: #E8B923; box-shadow: 0 0 0 1px rgba(232, 185, 35, 0.35); }
    .cf-stage-pending { opacity: 0.5; }
    .cf-copy-hint {
        font-weight: 700;
        color: #E8B923;
        margin-bottom: 6px;
    }
    div[data-testid="stCodeBlock"] button[title="Copy to clipboard"],
    div[data-testid="stCodeBlock"] [data-testid="stCodeCopyButton"] {
        opacity: 1 !important;
        transform: scale(1.4);
        background: #E8B923 !important;
        border-radius: 6px !important;
    }
    /* زرار الحذف الجماعي - بيبقى أحمر تحذيري في أي مكان مستخدم فيه
       (أي عنصر container بمفتاح بيبدأ بـ bulk_delete_) */
    [class*="st-key-bulk_delete_"] button {
        background-color: #DC2626 !important;
        border-color: #DC2626 !important;
    }
    [class*="st-key-bulk_delete_"] button p {
        color: #FFFFFF !important;
    }
    </style>
    """

st.markdown(
    _CSS_TEMPLATE.replace("__DIR__", _dir).replace("__ALIGN__", _text_align).replace("__ROWDIR__", _toolbar_row_dir),
    unsafe_allow_html=True,
)

# ---------------- دوال مساعدة للتعامل مع قاعدة البيانات ----------------
# ملحوظة: fetch_all / run_query / run_delete بقوا متعرّفين مركزيًا في
# database.py (مستوردين فوق) عشان يقدروا يشتغلوا مع SQLite محليًا أو
# Postgres/Supabase وقت النشر أونلاين من غير ما app.py يهتم بالاختلاف.

def safe_index(options, value, default=0):
    """بيرجع مكان القيمة في قايمة اختيارات، أو مكان افتراضي لو القيمة مش موجودة
    (زي بيانات قديمة اتحفظت بقيمة مش موجودة دلوقتي في الاختيارات)."""
    try:
        return options.index(value)
    except (ValueError, TypeError):
        return default


def ltr(value):
    """بيلف أي نص/رقم إنجليزي (زي 720p أو 16:9) بعلامات اتجاه يونيكود (LRI/PDI)
    عشان يتعرض بترتيبه الصح لما يتحط جوه جملة عربية (RTL) - من غيرها الأرقام
    والحروف الإنجليزية ممكن تتقلب مكانها لما تتلف بفواصل زي "·"."""
    if value is None:
        return ""
    return f"⁦{value}⁩"


def mark_saved(tag):
    """بيسجل إن آخر حاجة اتحفظت هي دي (tag فريد للسجل، زي f"loc_{id}")، عشان
    نعرض علامة "تم الحفظ" جنبها بعد الـ rerun. أي حفظ تاني لسجل مختلف بعد كده
    هيمسح العلامة دي، عشان المستخدم يفضل شايف آخر خطوة عملها بالظبط."""
    st.session_state["_cf_last_saved"] = tag


def show_saved_badge(tag):
    """بيعرض "✅ تم الحفظ" بخط رفيع فاتح لو آخر حاجة اتحفظت في البرنامج هي
    نفس السجل ده بالظبط - بتفضل ظاهرة لحد ما المستخدم يحفظ سجل تاني (أو يعمل
    أي حركة حفظ تانية)، عشان يفضل عنده مؤشر واضح لآخر خطوة اتحفظت."""
    if st.session_state.get("_cf_last_saved") == tag:
        st.markdown(
            f'<div class="cf-saved-badge">{t("✅ تم الحفظ")}</div>',
            unsafe_allow_html=True,
        )


def bump_version(project_id):
    """بيزود رقم نسخة بيانات المشروع بواحد - بيتنفذ مع أي إضافة/تعديل/حذف
    لمشهد أو لقطة (خصوصًا إعادة الترقيم)، عشان يظهر في أول كل تقرير ويطلع
    للمستخدم إشارة واضحة إن بيانات المشروع اتغيرت من وقت آخر تقرير طلعه."""
    run_query("UPDATE projects SET data_version = COALESCE(data_version, 1) + 1 WHERE id=?", (project_id,))


def shift_scene_numbers(project_id, from_number, exclude_scene_id=None):
    """لو المستخدم ضاف أو غيّر رقم مشهد لرقم مستخدم قبل كده، بندفع كل المشاهد
    اللي رقمها >= الرقم الجديد رقم واحد لقدام - بما إن اللقطات مربوطة
    بالمشهد عن طريق scene_id (مش رقم المشهد)، الدفع ده آمن ومبيأثرش على أي
    بيانات تانية، بس بيحدث رقم المشهد المعروض بس."""
    if exclude_scene_id is not None:
        run_query(
            "UPDATE scenes SET scene_number = scene_number + 1 WHERE project_id=? AND scene_number >= ? AND id != ?",
            (project_id, from_number, exclude_scene_id),
        )
    else:
        run_query(
            "UPDATE scenes SET scene_number = scene_number + 1 WHERE project_id=? AND scene_number >= ?",
            (project_id, from_number),
        )


def shift_shot_numbers(scene_id, from_number, exclude_shot_id=None):
    """نفس فكرة shift_scene_numbers بس على مستوى اللقطات جوه مشهد واحد."""
    if exclude_shot_id is not None:
        run_query(
            "UPDATE shots SET shot_number = shot_number + 1 WHERE scene_id=? AND shot_number >= ? AND id != ?",
            (scene_id, from_number, exclude_shot_id),
        )
    else:
        run_query(
            "UPDATE shots SET shot_number = shot_number + 1 WHERE scene_id=? AND shot_number >= ?",
            (scene_id, from_number),
        )


_DIALOGUE_LINE_RE = re.compile(r'^([^:：]{1,30})[:：]\s*(.+)$')


def extract_dialogue_lines(notes_text):
    """بيدور جوه نص المشهد (ملاحظات المشهد العامة) عن سطور بصيغة "اسم
    الشخصية: الكلام" ويرجعهم كقائمة سطور، عشان نقدر نوزعهم على اللقطات."""
    lines = []
    for raw in (notes_text or '').split('\n'):
        raw = raw.strip()
        if not raw:
            continue
        if _DIALOGUE_LINE_RE.match(raw):
            lines.append(raw)
    return lines


def unused_dialogue_lines(scene_notes, scene_id, fetch_all, exclude_shot_id=None):
    """بيرجع سطور حوار المشهد اللي لسه متوزعتش على أي لقطة تانية جوه نفس
    المشهد - ده اللي بيتعرض للمستخدم يختار منه وقت ما يضيف لقطة جديدة، لحد
    ما كل حوار المشهد يخلص يتوزع بالكامل. لو بنعدّل لقطة موجودة، بنستثنيها
    من حساب "المستخدم" عشان حوارها الحالي يفضل متاح تعديله."""
    all_lines = extract_dialogue_lines(scene_notes)
    if not all_lines:
        return []
    query = "SELECT dialogue_text FROM shots WHERE scene_id=?"
    params = [scene_id]
    if exclude_shot_id is not None:
        query += " AND id != ?"
        params.append(exclude_shot_id)
    other_shots = fetch_all(query, tuple(params))
    used = set()
    for sh in other_shots:
        for line in (sh["dialogue_text"] or "").split("\n"):
            line = line.strip()
            if line:
                used.add(line)
    return [l for l in all_lines if l not in used]


# ---------------- تخزين الصور المرجعية (لوكاشنز، لوكات الشخصيات، ستوري بورد اللقطات) ----------------

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads")
IMAGE_TYPES = ["png", "jpg", "jpeg", "webp"]


def save_uploaded_image(uploaded_file, subfolder):
    """بيحفظ صورة اترفعت في مجلد uploads جوه فولدر البرنامج، وبيرجع المسار
    النسبي عشان يتخزن في قاعدة البيانات."""
    if uploaded_file is None:
        return None
    folder = os.path.join(UPLOADS_DIR, subfolder)
    os.makedirs(folder, exist_ok=True)
    ext = os.path.splitext(uploaded_file.name)[1] or ".png"
    filename = f"{uuid.uuid4().hex}{ext}"
    abs_path = os.path.join(folder, filename)
    with open(abs_path, "wb") as f:
        f.write(uploaded_file.getvalue())
    return os.path.join("uploads", subfolder, filename)


def image_abs_path(rel_path):
    if not rel_path:
        return None
    abs_path = os.path.join(os.path.dirname(__file__), rel_path)
    return abs_path if os.path.exists(abs_path) else None


def delete_image_file(rel_path):
    abs_path = image_abs_path(rel_path)
    if abs_path:
        try:
            os.remove(abs_path)
        except OSError:
            pass


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
    st.session_state.pop("parsed_script", None)
    st.session_state["parsed_script_project_id"] = project_id

# Episodes section (للمسلسلات)
if project["project_type"] == "مسلسل":
    with st.sidebar.expander("🎬 الحلقات | Episodes"):
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

_stage_html = ['<div class="cf-stepper">']
for _i, ((_icon, _label), _done) in enumerate(zip(_stage_defs, _done_flags)):
    if _done:
        _state, _display_icon = "done", '<span class="cf-check-badge">✓</span>'
    elif _i == _current_idx:
        _state, _display_icon = "current", _icon
    else:
        _state, _display_icon = "pending", _icon
    _stage_html.append(
        f'<div class="cf-stage cf-stage-{_state}">'
        f'<div class="cf-stage-icon">{_display_icon}</div>'
        f'<div class="cf-stage-label">{_label}</div>'
        f'</div>'
    )
_stage_html.append('</div>')
st.markdown("".join(_stage_html), unsafe_allow_html=True)

tab_import, tab_locations, tab_characters, tab_props, tab_scenes, tab_breakdown, tab_dashboard = st.tabs(
    [tr("tab_import"), tr("tab_locations"), tr("tab_characters"), tr("tab_props"),
     tr("tab_scenes"), tr("tab_breakdown"), tr("tab_dashboard")],
    key="main_tabs",
)

# ---------------- تبويب استيراد السكريبت ----------------

AI_JSON_PROMPT = """أنت مساعد إخراج ومدير إنتاج محترف بتحلل سيناريو فيلم/مسلسل تحليل شامل وعميق جدًا،
عشان بياناته هتتحط في برنامج إدارة إنتاج بيبني منه تقارير رسمية (كشوفات تصوير، تفريغ لقطات...).
الدقة هنا مهمة جدًا لأن أي غلطة هتتكرر في كل تقرير بعد كده.

حلل السيناريو المرفق بالكامل، وطلعلي بياناته في صيغة JSON بالشكل ده بالظبط، من غير أي نص زيادة
قبله أو بعده (من غير ```json ولا أي شرح):

{
  "scenes": [
    {
      "scene_number": 1,
      "int_ext": "INT",
      "day_night": "نهار",
      "location_name": "اسم المكان",
      "characters": ["اسم شخصية 1", "اسم شخصية 2"],
      "props": ["اسم إكسسوار 1", "اسم إكسسوار 2"],
      "notes": "وصف الحركة الكامل + الحوار الكامل"
    }
  ]
}

قواعد مهمة لازم تلتزم بيها بالظبط - اقرا كل واحدة كويس، لأن الهدف إنك تذاكر السكريبت زي مساعد إخراج محترف بيحلل كل تفصيلة، مش بس الحوار:

## الشخصيات والإكسسوارات
- "characters": **كل** الشخصيات الموجودة فعليًا في المشهد، سواء كانت شخصية رئيسية أو ثانوية أو حتى كومبارس بدور صغير - حتى لو الشخصية دي **ملهاش أي حوار وساكتة طول المشهد**. لو مشهد فيه شخصية واقفة في الخلفية أو بتعمل حركة من غير ما تتكلم، لازم اسمها يتسجل هنا برضو. استخدم نفس الاسم بالظبط لكل ظهور لنفس الشخصية من غير ما تنوّع في كتابة الاسم (مثلاً "أحمد" في كل مرة، مش "أحمد" وبعدين "الشاب").
- "props": أي إكسسوار أو حاجة بتتلمس أو بتتستخدم أو مذكورة في وصف المشهد ولها دور في الحدث (زي: سكينة، تليفون، شنطة، مفاتيح عربية، سلاح، مجلة، فلوس...). لو مفيش حاجة واضحة سيبها [] فاضية. مش المفروض تسجل حاجات الديكور الثابتة (زي أثاث الغرفة) إلا لو لها دور في الحدث. اكتب في "notes" لو الإكسسوار مرتبط بشخصية معينة (مثلاً "طاسة أحمد" أو "شنطة سارة") عشان يبان واضح إنه ملكها.

## المكان والديكور (مهم جدًا)
كتير المشاهد بتحصل في "ديكور" فرعي جوه "مكان" عام أكبر - مثلاً المكان العام هو "شقة حسين"،
والديكور الفرعي جواه هو "غرفة نوم حسين" أو "صالة شقة حسين". لما ده يحصل:
- اكتب "location_name" بالصيغة: "المكان العام - الديكور الفرعي" بالظبط (مثال: "شقة حسين - غرفة نوم حسين").
- لو المشهد بياخد المكان كله من غير ديكور فرعي محدد، اكتب اسم المكان لوحده من غير شرطة.
- **دمج الأسماء المتكررة بصيغ مختلفة**: السيناريست أحيانًا بيوصف نفس المكان بصيغ مختلفة في أماكن
  مختلفة من السكريبت (مثلاً "شقة صلاح" في مشهد، و"شقة صلاح والد مصطفى" في مشهد تاني - دول نفس
  المكان). لازم تراجع كل أسماء الأماكن في السكريبت كله قبل ما تطلع النتيجة النهائية، وتوحّد كل
  الإشارات لنفس المكان تحت **اسم واحد متسق بالظبط** في كل المشاهد اللي بتحصل فيه، بدل ما تسيبها
  متنوعة زي ما السيناريست كتبها.

## المشاهد اللي فيها أكتر من ديكور أو مكان (زي الفوتومونتاج)
لو مشهد واحد في السكريبت (برقم واحد) فعليًا بيتنقل بين أكتر من مكان أو ديكور مختلف (زي مشهد
فوتومونتاج قصير بيولّف بين عدة أماكن)، **متسيبوش مشهد واحد بمكان غامض** - قسّمه لعدة مشاهد
منفصلة في الناتج، كل واحد برقم صحيح متتابع خاص بيه (يعني لو السكريبت مشهد رقم 35 فوتومونتاج
فيه 4 أماكن، طلّعهم كأربع عناصر منفصلين في "scenes" بأرقام متتالية زي 35، 36، 37، 38 - **مش**
حروف زي 35A/35B، البرنامج لسه ما بيدعمش ترقيم بالحروف). اكتب في "notes" بداية كل واحد منهم
إشارة إنه جزء من مشهد الفوتومونتاج الأصلي (مثلاً "من مونتاج مشهد 35 الأصلي") عشان الترتيب يفضل
مفهوم.

## باقي الحقول
- "int_ext": لازم يكون "INT" (داخلي) أو "EXT" (خارجي) بس - من غير أي قيمة تانية.
- "day_night": لازم يكون واحد من القيم دي بالظبط: "نهار" أو "ليل" أو "غروب" أو "فجر". لو المشهد
  متحدد إنه ليل، أي لقطة جواه هي ليل بالتبعية إلا لو السكريبت نفسه بيقول صراحة إن جزء منه في
  وقت مختلف - في الحالة دي اكتب ده في "notes" بوضوح عشان اليوزر يعدّل اللقطة المعنية يدويًا.
- "scene_number": رقم صحيح بترتيب ظهور المشهد في السكريبت.
- "notes": لازم يشمل كل التفاصيل دي مرتبة ووصفها واضح، من غير ما تلخص أو تختصر أي جزء:
  1. وصف الحركة والفعل الكامل (مين بيعمل إيه، فين، وأي تغيير في الملابس أو المظهر أو الحالة يحصل خلال المشهد).
  2. الحوار الكامل، كل جملة حوار في سطر لوحدها بصيغة "اسم الشخصية: الجملة" بالظبط.
  3. أي تفاصيل بصرية أو تغييرات مهمة في المكان أو الإضاءة أو الجو العام مذكورة في السكريبت.
- رجّعلي كل مشاهد السكريبت كاملة من غير اختصار أو تلخيص لأي مشهد.
- الناتج JSON صحيح وبس، جاهز إني أحفظه في ملف وأرفعه زي ما هو."""

def _render_analysis_dashboard(scenes):
    """لوحة تحليل السيناريو.

    كانت متكتوبة جوه زرار "تأكيد وإضافة المشاهد"، وبعد ما بترسم على طول
    بيتمسح parsed_script ويتعمل rerun — يعني كانت بتترسم في إطار بيتلغي
    قبل ما المستخدم يشوفه أصلًا. دلوقتي بتتعرض عادي وبتفضل ظاهرة."""
    st.markdown("---")
    st.markdown(f"## 📊 {t('تحليل السيناريو')}")
    tabs = st.tabs([t("📝 المشاهد"), t("👥 الشخصيات"), t("🏠 الأماكن"), t("🎬 الإكسسوارات"), t("📑 JSON")])

    with tabs[0]:
        for sc in scenes:
            st.subheader(f"{t('مشهد')} {sc['scene_number']}")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.caption(f"**{t('النوع')}**: {fmt_int_ext(sc.get('int_ext', 'غير محدد'))}")
            with col2:
                st.caption(f"**{t('الوقت')}**: {fmt_day_night(sc.get('day_night', 'غير محدد'))}")
            with col3:
                st.caption(f"**{t('المكان')}**: {sc.get('location_name', t('مكان غير محدد'))}")
            if sc.get('characters'):
                st.caption(f"**{t('الشخصيات')}**: {', '.join(sc['characters'])}")
            if sc.get('props'):
                st.caption(f"**🎬 {t('الإكسسوارات')}**: {', '.join(sc['props'])}")

    with tabs[1]:
        all_chars = set()
        for sc in scenes:
            all_chars.update(sc.get('characters', []))
        st.write(f"**{t('إجمالي الشخصيات')}**: {len(all_chars)}")
        for char in sorted(all_chars):
            appearances = sum(1 for sc in scenes if char in sc.get('characters', []))
            st.caption(f"{char} ({appearances} {t('مشاهد')})")

    with tabs[2]:
        all_locs = set()
        for sc in scenes:
            if sc.get('location_name'):
                all_locs.add(sc['location_name'])
        st.write(f"**{t('إجمالي الأماكن')}**: {len(all_locs)}")
        for loc in sorted(all_locs):
            st.caption(loc)

    with tabs[3]:
        all_props = set()
        for sc in scenes:
            all_props.update(sc.get('props', []))
        st.write(f"**{t('إجمالي الإكسسوارات')}**: {len(all_props)}")
        for prop in sorted(all_props):
            st.caption(prop)

    with tabs[4]:
        import json
        json_output = json.dumps({'scenes': scenes}, ensure_ascii=False, indent=2)
        st.code(json_output, language="json")
        st.download_button(
            label=t("📥 تحميل JSON"),
            data=json_output,
            file_name="analysis.json",
            mime="application/json"
        )


with tab_import:
    st.subheader(tr("sub_import"))
    st.caption(t(
        "ارفع ملف السيناريو (.docx أو .txt)، والنظام هيحاول يتعرف على رقم كل مشهد، "
        "داخلي/خارجي، النهار/الليل، المكان، والحوار، ويملى تبويب (السكريبت) تلقائيًا. "
        "تقدر تراجع النتيجة وتعدل أو تضيف أي حاجة بعد كده. وفي حالة السكريبتات "
        "الصعبة، تقدر ترفع ملف JSON جاهز من أي AI (شوف التفاصيل تحت)."
    ))
    st.caption(t(
        "لأفضل نتيجة، اكتب كل مشهد في سطر بصيغة زي: "
        "\"مشهد 1 - داخلي - نهار - غرفة المعيشة\"، والحوار في سطر منفصل بصيغة "
        "\"اسم الشخصية: الكلام\"."
    ))

    with st.expander(t("📋 السكريبت شكله معقد والبرنامج مبيحللوش كويس؟ استخدم أي AI بدله")):
        st.markdown(t(
            "لو شكل سكريبتك غريب أو التحليل التلقائي مبيطلعش نتيجة كويسة، اتبع الخطوات البسيطة دي:"
        ))
        st.markdown(t(
            "**1.** دوس على زرار \"📋 نسخ البرومبت\" تحت (هيتنسخ تلقائي).\n\n"
            "**2.** روح لبرنامج الـ AI اللي بتستخدمه (Claude، ChatGPT، Gemini...) وافتح محادثة جديدة.\n\n"
            "**3.** الصق البرومبت اللي نسخته، وارفق معاه ملف السكريبت (PDF أو نص) أو الصق نص "
            "السكريبت كامل بعد البرومبت.\n\n"
            "**4.** بعد ما الـ AI يرد عليك بالنتيجة، احفظها في ملف اسمه `script.json`.\n\n"
            "**5.** ارفع ملف `script.json` ده من الزرار تحت في الصفحة دي زي أي ملف تاني، وهيتم "
            "استيراده تلقائي."
        ))

        st.markdown(
            f'<div class="cf-copy-hint">👇 {t("اضغط على أيقونة النسخ 📋 اللي هتظهر فوق يمين الصندوق ده عشان تاخد البرومبت كامل دفعة واحدة")}</div>',
            unsafe_allow_html=True,
        )
        st.code(AI_JSON_PROMPT, language="text")

    uploaded_file = st.file_uploader(t("اختر ملف السكريبت"), type=["docx", "txt", "pdf", "json"], key="script_upload")

    if uploaded_file is not None and st.button(t("🔍 تحليل الملف")):
        try:
            _known = [r["name"] for r in fetch_all(
                "SELECT name FROM characters WHERE project_id=?", (project_id,))]
            st.session_state["parsed_script"] = parse_script(
                uploaded_file.name, uploaded_file.getvalue(), known_characters=_known)
        except Exception as e:
            st.error(f"{t('حصل خطأ أثناء تحليل الملف:')} {e}")

    parsed = st.session_state.get("parsed_script")
    if not parsed and st.session_state.get("last_analysis"):
        # بعد ما المشاهد تتضاف، التحليل يفضل متاح بدل ما يختفي
        _render_analysis_dashboard(st.session_state["last_analysis"])
    if parsed:
        scenes = parsed["scenes"]
        for w in parsed["warnings"]:
            st.warning(w)

        st.success(f"{t('تم التعرف على')} {len(scenes)} {t('مشهد في الملف. راجعهم وعدّل أي حاجة غلط قبل التأكيد:')}")
        excluded_scene_indices = set()
        kept_characters_by_scene = {}
        for idx, sc in enumerate(scenes):
            title = (
                f"{t('مشهد')} {sc['scene_number']} — {ltr(fmt_int_ext(sc['int_ext'] or 'غير محدد'))} / "
                f"{fmt_day_night(sc['day_night'] or 'غير محدد')} — {sc['location_name'] or t('مكان غير محدد')}"
            )
            with st.expander(title):
                exclude = st.checkbox(
                    t("🚫 استبعد المشهد ده من الاستيراد (مثلاً لو ده صفحة عنوان مش مشهد حقيقي)"),
                    key=f"exclude_scene_{idx}",
                )
                if exclude:
                    excluded_scene_indices.add(idx)
                if sc["characters"]:
                    kept_characters_by_scene[idx] = st.multiselect(
                        t("الشخصيات المكتشفة — شيل أي حاجة مش اسم شخصية فعلي (زي نوع الفيلم أو التاريخ أو المكان)"),
                        options=sc["characters"], default=sc["characters"], key=f"chars_{idx}",
                    )
                else:
                    kept_characters_by_scene[idx] = []
                    st.caption(t("مفيش شخصيات اتكشفت في المشهد ده"))
                if sc.get("props"):
                    st.caption(f"🎬 {t('الإكسسوارات')}: {', '.join(sc['props'])}")
                else:
                    st.caption(t("🎬 مفيش إكسسوارات نشطة"))
                st.text(sc["notes"] if sc["notes"] else "—")

        # نسخة معاينة من غير ما نلمس بيانات الجلسة الأصلية، عشان لو المستخدم شال
        # شخصية بالغلط يقدر يرجعها من غير ما يعيد رفع الملف
        preview_scenes = []
        for idx, sc in enumerate(scenes):
            if idx in excluded_scene_indices:
                continue
            sc_view = dict(sc)
            sc_view["characters"] = kept_characters_by_scene.get(idx, sc["characters"])
            preview_scenes.append(sc_view)

        merge_map = {}
        _render_analysis_dashboard(preview_scenes)

        similar_groups = find_similar_name_groups(preview_scenes)
        if similar_groups:
            st.markdown("---")
            st.markdown(f"**{t('🧑‍🤝‍🧑 لقينا أسماء شخصيات متشابهة — هي نفس الشخصية؟')}**")
            for gi, group in enumerate(similar_groups):
                if gi > 0:
                    st.markdown('<hr class="cf-soft-sep">', unsafe_allow_html=True)
                choice = st.radio(
                    f"{t('الأسماء:')} {'، '.join(group)}",
                    options=["دمجهم في شخصية واحدة", "لأ، شخصيات مختلفة"],
                    format_func=t,
                    key=f"merge_choice_{gi}",
                    horizontal=True,
                )
                if choice == "دمجهم في شخصية واحدة":
                    default_canonical = max(group, key=len)
                    canonical = st.selectbox(
                        t("اختار الاسم اللي هيتسجل بيه في المشروع"),
                        options=group,
                        index=group.index(default_canonical),
                        key=f"merge_canonical_{gi}",
                    )
                    for name in group:
                        if name != canonical:
                            merge_map[name] = canonical

        location_merge_map = {}
        similar_location_groups = find_similar_location_groups(preview_scenes)
        if similar_location_groups:
            st.markdown("---")
            st.markdown(f"**{t('🏠 لقينا أماكن متشابهة — هي حالات مختلفة لنفس المكان؟')}**")
            st.caption(t(
                "مثال: \"سطح اليخت\" و\"سطح اليخت بعد لحظات\" غالبًا نفس المكان في وقتين مختلفين، "
                "مش مكانين منفصلين. لو دمجتهم، الاسم الأصلي هيتسجل كحالة (Variant) تحت المكان الرئيسي."
            ))
            for li, group in enumerate(similar_location_groups):
                if li > 0:
                    st.markdown('<hr class="cf-soft-sep">', unsafe_allow_html=True)
                loc_choice = st.radio(
                    f"{t('الأماكن:')} {'، '.join(group)}",
                    options=["دمجهم كحالات لنفس المكان الرئيسي", "لأ، أماكن مختلفة فعلاً"],
                    format_func=t,
                    key=f"loc_merge_choice_{li}",
                    horizontal=True,
                )
                if loc_choice == "دمجهم كحالات لنفس المكان الرئيسي":
                    default_loc_canonical = min(group, key=len)
                    loc_canonical = st.selectbox(
                        t("اختار اسم المكان الرئيسي اللي هيتسجل بيه"),
                        options=group,
                        index=group.index(default_loc_canonical),
                        key=f"loc_merge_canonical_{li}",
                    )
                    for name in group:
                        if name != loc_canonical:
                            location_merge_map[name] = loc_canonical

        if excluded_scene_indices:
            st.caption(f"{t('هيتستبعد')} {len(excluded_scene_indices)} {t('مشهد من الاستيراد حسب اختيارك فوق.')}")

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button(t("🔵 تأكيد وإضافة كل المشاهد للمشروع")):
                scenes_to_import = apply_character_merges(preview_scenes, merge_map)
                scenes_to_import = apply_location_merges(scenes_to_import, location_merge_map)
                summary = import_parsed_scenes(project_id, scenes_to_import, fetch_all, run_query)
                msg = f"{t('تم إضافة')} {summary['scenes_added']} {t('مشهد جديد.')}"
                if summary["characters_added"]:
                    msg += f" {t('شخصيات جديدة:')} {'، '.join(summary['characters_added'])}."
                if summary["locations_added"]:
                    msg += f" {t('أماكن جديدة:')} {'، '.join(summary['locations_added'])}."
                if summary["props_added"]:
                    msg += f" {t('إكسسوارات جديدة:')} {'، '.join(summary['props_added'])}."
                if summary["scenes_skipped"]:
                    skipped = "، ".join(str(n) for n in summary["scenes_skipped"])
                    msg += f" {t('تم تخطي مشاهد أرقام')} ({skipped}) {t('لأنها موجودة بالفعل.')}"
                st.success(msg)

                st.session_state["last_analysis"] = list(scenes_to_import)

                del st.session_state["parsed_script"]
                st.rerun()
        with col_b:
            if st.button(t("🗑️ إلغاء ومسح النتائج")):
                del st.session_state["parsed_script"]
                st.rerun()

# ---------------- تبويب الأماكن ----------------
with tab_locations:
    st.subheader(tr("sub_locations"))
    st.caption(t(
        "لو عندك مكان رئيسي وجواه أماكن فرعية (زي شقة حسام وجواها غرفة نوم)، "
        "أضف المكان الرئيسي الأول، وبعدين أضف المكان الفرعي واختار له 'تابع لمكان رئيسي'."
    ))

    locations = fetch_all("SELECT * FROM locations WHERE project_id=?", (project_id,))
    location_name_by_id = {l["id"]: l["name"] for l in locations}

    col1, col2 = st.columns([1, 2])
    with col1:
        with st.form(f"add_location_{project_id}"):
            loc_name = st.text_input(t("اسم المكان"), placeholder=t("مثال: شقة حسام"))
            parent_add_options = ["بدون - مكان رئيسي"] + [l["name"] for l in locations]
            loc_parent = st.selectbox(t("تابع لمكان رئيسي؟"), parent_add_options, format_func=t)
            loc_desc = st.text_area(
                t("وصف عام ثابت للمكان"),
                placeholder=t("مثال: شقة قديمة في حي شعبي، جدرانها بيج فاتح، فيها أثاث خشبي تقيل"),
            )
            if st.form_submit_button(t("إضافة مكان")):
                if loc_name.strip():
                    parent_id = None
                    if loc_parent != "بدون - مكان رئيسي":
                        parent_id = {l["name"]: l["id"] for l in locations}.get(loc_parent)
                    run_query(
                        "INSERT INTO locations (project_id, name, base_description, parent_location_id) VALUES (?,?,?,?)",
                        (project_id, loc_name, loc_desc, parent_id),
                    )
                    st.rerun()

    with col2:
        if locations:
            loc_map = {l["name"]: l["id"] for l in locations}
            sel_loc = st.selectbox(t("اختر مكان لإضافة حالة (Variant) له"), list(loc_map.keys()))
            loc_id = loc_map[sel_loc]
            with st.form(f"add_variant_{loc_id}"):
                v_name = st.text_input(t("حالة المكان"), placeholder=t("مثال: الشكل الرئيسي للمكان، أو: المكان محروق، أو: المكان بعد التجديد"))
                v_int_ext = st.selectbox(t("داخلي/خارجي"), INT_EXT_OPTIONS,
                                          format_func=fmt_int_ext, help=FIELD_HELP["int_ext"])
                v_desc = st.text_area(
                    t("وصف التغييرات الخاصة بهذه الحالة"),
                    placeholder=t("مثال: المكان اتحرق واتهد بعد حريق في نص الأحداث"),
                )
                v_image = st.file_uploader(t("صورة مرجعية (اختياري)"), type=IMAGE_TYPES, key="new_variant_image")
                if st.form_submit_button(t("إضافة الحالة")):
                    image_path = save_uploaded_image(v_image, f"locations/{loc_id}")
                    run_query(
                        """INSERT INTO location_variants
                        (location_id, variant_name, int_ext, description, reference_image_path)
                        VALUES (?,?,?,?,?)""",
                        (loc_id, v_name, v_int_ext, v_desc, image_path),
                    )
                    st.rerun()
        else:
            st.caption(t("مفيش أماكن مضافة لسه"))

    st.divider()

    children_by_parent = {}
    for l in locations:
        if l["parent_location_id"]:
            children_by_parent.setdefault(l["parent_location_id"], []).append(l)

    def render_location(l, indent=""):
        with st.expander(f"{indent}📍 {l['name']}", key=f"exp_loc_{l['id']}"):
            with st.form(f"edit_location_{l['id']}"):
                e_loc_name = st.text_input(t("اسم المكان"), value=l["name"])
                edit_parent_options = ["بدون - مكان رئيسي"] + [
                    other["name"] for other in locations if other["id"] != l["id"]
                ]
                current_parent_name = location_name_by_id.get(l["parent_location_id"], "بدون - مكان رئيسي")
                e_loc_parent = st.selectbox(
                    t("تابع لمكان رئيسي؟"), edit_parent_options,
                    index=safe_index(edit_parent_options, current_parent_name),
                    format_func=t,
                )
                e_loc_desc = st.text_area(
                    t("وصف عام ثابت للمكان"), value=l["base_description"] or "",
                    placeholder=t("مثال: شقة قديمة في حي شعبي، جدرانها بيج فاتح، فيها أثاث خشبي تقيل"),
                )
                save_col, del_col = st.columns(2)
                with save_col:
                    save_loc = st.form_submit_button(t("💾 حفظ التعديل"))
                with del_col:
                    del_loc = st.form_submit_button(t("🗑️ حذف المكان (وكل حالاته)"))
            if save_loc:
                if e_loc_name.strip():
                    new_parent_id = None
                    if e_loc_parent != "بدون - مكان رئيسي":
                        new_parent_id = {o["name"]: o["id"] for o in locations if o["id"] != l["id"]}.get(e_loc_parent)
                    run_query("UPDATE locations SET name=?, base_description=?, parent_location_id=? WHERE id=?",
                               (e_loc_name, e_loc_desc, new_parent_id, l["id"]))
                    mark_saved(f"loc_{l['id']}")
                    st.rerun()
                else:
                    st.warning(t("اسم المكان مينفعش يبقى فاضي"))
            show_saved_badge(f"loc_{l['id']}")
            if del_loc:
                ok = run_delete(
                    "DELETE FROM locations WHERE id=?", (l["id"],),
                    t("معرفش أمسح المكان ده لأنه مستخدم في مشهد، أو ليه أماكن فرعية تابعة له. شيل الارتباطات دي الأول."),
                )
                if ok:
                    st.success(t("تم حذف المكان"))
                    st.rerun()

            st.markdown(f"**{t('الحالات (Variants):')}**")
            st.caption(t("لو نفس المكان بيتكرر في السكريبت بعد وقت (زي 'سطح اليخت' تاني بعد لحظات)، أضف حالة جديدة بدل ما تعمل مكان جديد مكرر."))
            variants = fetch_all("SELECT * FROM location_variants WHERE location_id=?", (l["id"],))
            if not variants:
                st.caption(t("مفيش حالات مضافة لسه"))
            move_options = {other["name"]: other["id"] for other in locations}
            for v in variants:
                with st.form(f"edit_variant_{v['id']}"):
                    ev_name = st.text_input(t("حالة المكان"), value=v["variant_name"])
                    ev_int_ext = st.selectbox(t("داخلي/خارجي"), INT_EXT_OPTIONS,
                                               index=safe_index(INT_EXT_OPTIONS, v["int_ext"]),
                                               format_func=fmt_int_ext)
                    ev_desc = st.text_area(t("وصف التغييرات الخاصة بهذه الحالة"), value=v["description"] or "")
                    ev_move_to = st.selectbox(
                        t("المكان (غيّره لو عايز تنقل الحالة دي لمكان تاني — مفيد لدمج أماكن مكررة)"),
                        list(move_options.keys()), index=safe_index(list(move_options.keys()), l["name"]),
                    )
                    if v["reference_image_path"]:
                        existing_img = image_abs_path(v["reference_image_path"])
                        if existing_img:
                            st.image(existing_img, width=220)
                    
                    # Generate or Upload menu
                    image_action = st.radio(
                        t("طريقة إضافة الصورة المرجعية"),
                        [t("رفع من الجهاز"), t("توليد (قريباً)")],
                        index=0,
                        key=f"variant_image_action_{v['id']}"
                    )
                    
                    ev_image = None
                    if image_action == t("رفع من الجهاز"):
                        ev_image = st.file_uploader(t("اختر صورة مرجعية"), type=IMAGE_TYPES, key=f"variant_image_{v['id']}")
                    else:
                        st.info("🔒 ميزة التوليد الذكي للصور قيد التطوير — قريباً ستتمكن من توليد صور بناءً على وصف المشهد")
                    vsave_col, vdel_col = st.columns(2)
                    with vsave_col:
                        save_var = st.form_submit_button(t("💾 حفظ"))
                    with vdel_col:
                        del_var = st.form_submit_button(t("🗑️ حذف الحالة"))
                if save_var:
                    target_location_id = move_options[ev_move_to]
                    new_image_path = v["reference_image_path"]
                    if ev_image is not None:
                        new_image_path = save_uploaded_image(ev_image, f"locations/{target_location_id}")
                    run_query(
                        """UPDATE location_variants SET variant_name=?, int_ext=?,
                        description=?, location_id=?, reference_image_path=? WHERE id=?""",
                        (ev_name, ev_int_ext, ev_desc,
                         target_location_id, new_image_path, v["id"]),
                    )
                    mark_saved(f"variant_{v['id']}")
                    st.rerun()
                if del_var:
                    ok = run_delete(
                        "DELETE FROM location_variants WHERE id=?", (v["id"],),
                        t("معرفش أمسح الحالة دي لأنها مستخدمة في مشهد أو أكتر. شيلها من المشاهد دي الأول من تبويب السكريبت."),
                    )
                    if ok:
                        delete_image_file(v["reference_image_path"])
                        st.success(t("تم حذف الحالة"))
                        st.rerun()
                show_saved_badge(f"variant_{v['id']}")

        for child in children_by_parent.get(l["id"], []):
            render_location(child, indent="↳ ")

    top_level_locations = [l for l in locations if not l["parent_location_id"]]
    for l in top_level_locations:
        render_location(l)

# ---------------- تبويب الشخصيات ----------------
with tab_characters:
    st.subheader(tr("sub_characters"))
    col1, col2 = st.columns([1, 2])
    with col1:
        with st.form(f"add_character_{project_id}"):
            ch_name = st.text_input(t("اسم الشخصية"), placeholder=t("مثال: أحمد"))
            ch_role = st.selectbox(t("نوع الدور"), ["بطل", "شرير", "مساعد", "كومبارس"], format_func=t)
            ch_species = st.selectbox(t("نوع الكائن"), SPECIES_OPTIONS, format_func=t, help=FIELD_HELP["species"])
            ch_gender = st.selectbox(t("الجنس"), GENDER_OPTIONS, format_func=t, help=FIELD_HELP["gender"])
            ch_notes = st.text_area(
                t("ملاحظات عامة عن الشخصية"),
                placeholder=t("زي الوزن والبنية الجسمانية (نحيف/تخين/رياضي...) وأي تفاصيل تانية"),
            )
            ch_image = st.file_uploader(t("صورة الشخصية المرجعية (اختياري)"), type=IMAGE_TYPES, key="new_character_image")
            if st.form_submit_button(t("إضافة شخصية")):
                if ch_name.strip():
                    new_char_id = run_query(
                        """INSERT INTO characters
                        (project_id, name, role_type, species, gender, personality_notes)
                        VALUES (?,?,?,?,?,?)""",
                        (project_id, ch_name, ch_role, ch_species, ch_gender, ch_notes),
                    )
                    if ch_image is not None:
                        image_path = save_uploaded_image(ch_image, f"characters/{new_char_id}")
                        run_query("UPDATE characters SET reference_image_path=? WHERE id=?", (image_path, new_char_id))
                    st.rerun()

    characters = fetch_all("SELECT * FROM characters WHERE project_id=?", (project_id,))
    with col2:
        if characters:
            char_map = {c["name"]: c["id"] for c in characters}
            sel_char = st.selectbox(t("اختر شخصية لإضافة مظهر إضافي لها"), list(char_map.keys()))
            char_id = char_map[sel_char]
            with st.form(f"add_look_{char_id}"):
                st.caption(t("المظهر الإضافي بيمثل شكل تاني للشخصية في لحظة مختلفة من القصة (مثال: حلق دقنه، لابس نضارة، اتصاب وبقى في جبس)."))
                look_name = st.text_input(t("اسم المظهر الإضافي"), placeholder=t("مثال: المظهر الرئيسي - حلق دقنه ولابس نضارة"))
                look_age = st.text_input(t("السن الظاهر"), placeholder=t("مثال: 30 سنة"), help=FIELD_HELP["apparent_age"])
                look_makeup = st.selectbox(t("حالة المكياج"), ["طبيعي", "كامل", "بدون", "آثار إصابة", "مكياج شيخوخة"], format_func=t, help=FIELD_HELP["makeup_state"])
                look_hair = st.text_input(t("حالة الشعر"), placeholder=t("مثال: شعر قصير أسود"))
                look_wardrobe = st.text_area(t("وصف الملابس والإكسسوارات"), placeholder=t("مثال: قميص أبيض وبنطلون جينز وساعة يد"))
                look_desc = st.text_area(
                    t("وصف تفصيلي كامل للمظهر (يُستخدم كمرجع للتوليد)"),
                    placeholder=t("مثال: راجل في الثلاثينات، نحيف، شعره قصير أسود، لابس نضارة طبية..."),
                )
                look_image = st.file_uploader(t("صورة مرجعية (اختياري)"), type=IMAGE_TYPES, key="new_look_image")
                if st.form_submit_button(t("➕ إضافة مظهر إضافي")):
                    image_path = save_uploaded_image(look_image, f"characters/{char_id}")
                    run_query(
                        """INSERT INTO character_looks
                        (character_id, look_name, apparent_age, makeup_state, hair_state, wardrobe_description, description, reference_image_path)
                        VALUES (?,?,?,?,?,?,?,?)""",
                        (char_id, look_name, look_age, look_makeup, look_hair, look_wardrobe, look_desc, image_path),
                    )
                    st.rerun()
        else:
            st.caption(t("مفيش شخصيات مضافة لسه"))

    st.divider()
    role_options = ["بطل", "شرير", "مساعد", "كومبارس", "غير محدد"]
    makeup_options = ["طبيعي", "كامل", "بدون", "آثار إصابة", "مكياج شيخوخة"]
    for ch in characters:
        with st.expander(f"🎭 {ch['name']} ({t(ch['role_type'])})", key=f"exp_char_{ch['id']}"):
            with st.form(f"edit_character_{ch['id']}"):
                ech_name = st.text_input(t("اسم الشخصية"), value=ch["name"])
                ech_role = st.selectbox(t("نوع الدور"), role_options,
                                         index=safe_index(role_options, ch["role_type"]), format_func=t)
                ech_species = st.selectbox(t("نوع الكائن"), SPECIES_OPTIONS,
                                            index=safe_index(SPECIES_OPTIONS, ch["species"]), format_func=t, help=FIELD_HELP["species"])
                ech_gender = st.selectbox(t("الجنس"), GENDER_OPTIONS,
                                           index=safe_index(GENDER_OPTIONS, ch["gender"]), format_func=t, help=FIELD_HELP["gender"])
                ech_notes = st.text_area(
                    t("ملاحظات عامة عن الشخصية"), value=ch["personality_notes"] or "",
                    placeholder=t("زي الوزن والبنية الجسمانية (نحيف/تخين/رياضي...) وأي تفاصيل تانية"),
                )
                if ch["reference_image_path"]:
                    existing_ch_img = image_abs_path(ch["reference_image_path"])
                    if existing_ch_img:
                        st.image(existing_ch_img, width=220)
                
                # Generate or Upload menu
                char_image_action = st.radio(
                    t("طريقة إضافة صورة الشخصية"),
                    [t("رفع من الجهاز"), t("توليد (قريباً)")],
                    index=0,
                    key=f"character_image_action_{ch['id']}"
                )
                
                ech_image = None
                if char_image_action == t("رفع من الجهاز"):
                    ech_image = st.file_uploader(
                        t("اختر صورة مرجعية للشخصية"), type=IMAGE_TYPES, key=f"character_image_{ch['id']}"
                    )
                else:
                    st.info("🔒 ميزة توليد صور الشخصيات الذكية قيد التطوير — ستتمكن قريباً من توليد صور بناءً على الوصف والملابس والمكياج")
                csave_col, cdel_col = st.columns(2)
                with csave_col:
                    save_ch = st.form_submit_button(t("💾 حفظ التعديل"))
                with cdel_col:
                    del_ch = st.form_submit_button(t("🗑️ حذف الشخصية (وكل مظاهرها)"))
            if save_ch:
                if ech_name.strip():
                    new_ch_image_path = ch["reference_image_path"]
                    if ech_image is not None:
                        new_ch_image_path = save_uploaded_image(ech_image, f"characters/{ch['id']}")
                    run_query(
                        """UPDATE characters SET name=?, role_type=?, species=?, gender=?,
                        personality_notes=?, reference_image_path=? WHERE id=?""",
                        (ech_name, ech_role, ech_species, ech_gender, ech_notes, new_ch_image_path, ch["id"]),
                    )
                    mark_saved(f"char_{ch['id']}")
                    st.rerun()
                else:
                    st.warning(t("اسم الشخصية مينفعش يبقى فاضي"))
            if del_ch:
                ok = run_delete(
                    "DELETE FROM characters WHERE id=?", (ch["id"],),
                    t("معرفش أمسح الشخصية دي لأن مظهر بتاعها مستخدم في لقطة أو أكتر. شيلها من اللقطات دي الأول من تبويب التفريغ."),
                )
                if ok:
                    delete_image_file(ch["reference_image_path"])
                    st.success(t("تم حذف الشخصية"))
                    st.rerun()
            show_saved_badge(f"char_{ch['id']}")

            st.markdown(f"**{t('المظاهر الإضافية:')}**")
            looks = fetch_all("SELECT * FROM character_looks WHERE character_id=?", (ch["id"],))
            if not looks:
                st.caption(t("مفيش مظاهر إضافية متضافة لسه"))
            for lk in looks:
                with st.form(f"edit_look_{lk['id']}"):
                    elk_name = st.text_input(t("اسم المظهر الإضافي"), value=lk["look_name"])
                    elk_age = st.text_input(t("السن الظاهر"), value=lk["apparent_age"] or "", placeholder=t("مثال: 30 سنة"))
                    elk_makeup = st.selectbox(t("حالة المكياج"), makeup_options,
                                               index=safe_index(makeup_options, lk["makeup_state"]), format_func=t)
                    elk_hair = st.text_input(t("حالة الشعر"), value=lk["hair_state"] or "", placeholder=t("مثال: شعر قصير أسود"))
                    elk_wardrobe = st.text_area(
                        t("وصف الملابس والإكسسوارات"), value=lk["wardrobe_description"] or "",
                        placeholder=t("مثال: قميص أبيض وبنطلون جينز وساعة يد"),
                    )
                    elk_desc = st.text_area(
                        t("وصف تفصيلي كامل للمظهر"), value=lk["description"] or "",
                        placeholder=t("مثال: راجل في الثلاثينات، نحيف، شعره قصير أسود، لابس نضارة طبية..."),
                    )
                    if lk["reference_image_path"]:
                        existing_look_img = image_abs_path(lk["reference_image_path"])
                        if existing_look_img:
                            st.image(existing_look_img, width=220)
                    elk_image = st.file_uploader(t("تغيير الصورة المرجعية"), type=IMAGE_TYPES, key=f"look_image_{lk['id']}")
                    lsave_col, ldel_col = st.columns(2)
                    with lsave_col:
                        save_lk = st.form_submit_button(t("💾 حفظ"))
                    with ldel_col:
                        del_lk = st.form_submit_button(t("🗑️ حذف المظهر الإضافي"))
                if save_lk:
                    new_look_image_path = lk["reference_image_path"]
                    if elk_image is not None:
                        new_look_image_path = save_uploaded_image(elk_image, f"characters/{ch['id']}")
                    run_query(
                        """UPDATE character_looks SET look_name=?, apparent_age=?, makeup_state=?,
                        hair_state=?, wardrobe_description=?, description=?, reference_image_path=? WHERE id=?""",
                        (elk_name, elk_age, elk_makeup, elk_hair, elk_wardrobe, elk_desc, new_look_image_path, lk["id"]),
                    )
                    mark_saved(f"look_{lk['id']}")
                    st.rerun()
                if del_lk:
                    ok = run_delete(
                        "DELETE FROM character_looks WHERE id=?", (lk["id"],),
                        t("معرفش أمسح المظهر ده لأنه مستخدم في لقطة أو أكتر. شيله من اللقطات دي الأول من تبويب التفريغ."),
                    )
                    if ok:
                        delete_image_file(lk["reference_image_path"])
                        st.success(t("تم حذف المظهر الإضافي"))
                        st.rerun()
                show_saved_badge(f"look_{lk['id']}")

# ---------------- تبويب الإكسسوارات ----------------
with tab_props:
    st.subheader(tr("sub_props"))
    st.caption(t(
        "أي حاجة بيمسكها أو بيستخدمها أي شخصية أو ليها دور في حدث المشهد (سكينة، تليفون، شنطة، سلاح...). "
        "تقدر تربط الإكسسوار بشخصية معينة (زي مسدس البطل)، وتعلّم عليه لو حساس للراكورد (يعني لازم يفضل في "
        "نفس الحالة بين اللقطات المتتالية)."
    ))

    characters_for_props = fetch_all("SELECT * FROM characters WHERE project_id=? ORDER BY id", (project_id,))
    char_options_for_props = ["بدون - غير مرتبط بشخصية"] + [c["name"] for c in characters_for_props]
    char_id_by_name = {c["name"]: c["id"] for c in characters_for_props}

    with st.form(f"add_prop_{project_id}"):
        prop_name = st.text_input(t("اسم الإكسسوار"), placeholder=t("مثال: سكينة عم جابر"))
        prop_continuity = st.checkbox(t("حساس للراكورد؟ (لازم يفضل في نفس الحالة بين اللقطات)"))
        prop_character = st.selectbox(t("مرتبط بشخصية (اختياري)"), char_options_for_props)
        if st.form_submit_button(t("إضافة إكسسوار")):
            if prop_name.strip():
                linked_char_id = char_id_by_name.get(prop_character)
                run_query(
                    "INSERT INTO props (project_id, name, continuity_sensitive, character_id) VALUES (?,?,?,?)",
                    (project_id, prop_name, int(prop_continuity), linked_char_id),
                )
                st.rerun()
            else:
                st.warning(t("اسم الإكسسوار مينفعش يبقى فاضي"))

    st.divider()
    props_list = fetch_all("SELECT * FROM props WHERE project_id=? ORDER BY id", (project_id,))
    if not props_list:
        st.caption(t("مفيش إكسسوارات مضافة لسه"))
    for pr in props_list:
        char_label = next((c["name"] for c in characters_for_props if c["id"] == pr["character_id"]), None)
        badge = f" — {t('مرتبط بـ')} {char_label}" if char_label else ""
        with st.expander(f"🎒 {pr['name']}{badge}", key=f"exp_prop_{pr['id']}"):
            with st.form(f"edit_prop_{pr['id']}"):
                ep_name = st.text_input(t("اسم الإكسسوار"), value=pr["name"])
                ep_continuity = st.checkbox(
                    t("حساس للراكورد؟ (لازم يفضل في نفس الحالة بين اللقطات)"),
                    value=bool(pr["continuity_sensitive"]),
                )
                ep_char_options = ["بدون - غير مرتبط بشخصية"] + [c["name"] for c in characters_for_props]
                current_char_name = char_label or "بدون - غير مرتبط بشخصية"
                ep_character = st.selectbox(
                    t("مرتبط بشخصية (اختياري)"), ep_char_options,
                    index=safe_index(ep_char_options, current_char_name),
                )
                psave_col, pdel_col = st.columns(2)
                with psave_col:
                    save_pr = st.form_submit_button(t("💾 حفظ التعديل"))
                with pdel_col:
                    del_pr = st.form_submit_button(t("🗑️ حذف الإكسسوار"))
            if save_pr:
                if ep_name.strip():
                    new_linked_char_id = char_id_by_name.get(ep_character)
                    run_query(
                        "UPDATE props SET name=?, continuity_sensitive=?, character_id=? WHERE id=?",
                        (ep_name, int(ep_continuity), new_linked_char_id, pr["id"]),
                    )
                    mark_saved(f"prop_{pr['id']}")
                    st.rerun()
                else:
                    st.warning(t("اسم الإكسسوار مينفعش يبقى فاضي"))
            if del_pr:
                run_query("DELETE FROM props WHERE id=?", (pr["id"],))
                st.success(t("تم حذف الإكسسوار"))
                st.rerun()
            show_saved_badge(f"prop_{pr['id']}")

# ---------------- تبويب السكريبت (المشاهد) ----------------
with tab_scenes:
    st.subheader(tr("sub_scenes"))

    with st.expander(t("🔄 استخراج الشخصيات من نص المشاهد (لمشاريع قديمة)")):
        st.caption(t(
            "لو المشروع ده استوردته قبل ما ميزة ربط الشخصيات بالمشاهد تتضاف، التقارير (كشف الشخصيات، "
            "التفريغ العام) هتبقى فاضية لحد ما تربط كل مشهد بشخصياته يدويًا، أو تدوس هنا عشان نحاول نلاقي "
            "أسماء شخصيات مكتبتك داخل نص كل مشهد ونربطها أوتوماتيك (من غير ما نمسح أي ربط موجود بالفعل)."
        ))
        if st.button(t("🔍 ابحث واربط الشخصيات دلوقتي")):
            all_chars_backfill = fetch_all("SELECT id, name FROM characters WHERE project_id=?", (project_id,))
            all_scenes_backfill = fetch_all("SELECT id, notes FROM scenes WHERE project_id=?", (project_id,))
            links_added = 0
            for _sc in all_scenes_backfill:
                _notes = _sc["notes"] or ""
                if not _notes:
                    continue
                for _ch in all_chars_backfill:
                    if _ch["name"] and _ch["name"] in _notes:
                        _before = fetch_all(
                            "SELECT id FROM scene_characters WHERE scene_id=? AND character_id=?",
                            (_sc["id"], _ch["id"]),
                        )
                        if not _before:
                            run_query(
                                "INSERT OR IGNORE INTO scene_characters (scene_id, character_id) VALUES (?,?)",
                                (_sc["id"], _ch["id"]),
                            )
                            links_added += 1
            bump_version(project_id)
            st.success(f"{t('تم ربط')} {links_added} {t('علاقة شخصية-مشهد جديدة.')}")
            st.rerun()

    locations_all = fetch_all("""
        SELECT lv.id, l.name || ' - ' || lv.variant_name AS label
        FROM location_variants lv JOIN locations l ON lv.location_id = l.id
        WHERE l.project_id = ?
    """, (project_id,))
    loc_variant_map = {r["label"]: r["id"] for r in locations_all}

    with st.form(f"add_scene_{project_id}"):
        col1, col2, col3 = st.columns(3)
        with col1:
            sc_number = st.number_input(t("رقم المشهد"), min_value=1, step=1)
            sc_int_ext = st.selectbox(t("داخلي/خارجي"), INT_EXT_OPTIONS, format_func=fmt_int_ext, key="scene_int_ext")
        with col2:
            sc_day_night = st.selectbox(t("التوقيت"), DAY_NIGHT_OPTIONS, format_func=fmt_day_night, key="scene_day_night")
            sc_location = st.selectbox(t("المكان"), ["بدون تحديد"] + list(loc_variant_map.keys()), format_func=t)
        with col3:
            sc_weather = st.text_input(t("الطقس"), placeholder=t("مثال: شتاء مشمس، أو صيف حار وضبابي"))
        
        # Episode selection for series
        sc_episode_id = None
        if project["project_type"] == "مسلسل":
            episodes = fetch_all("SELECT id, episode_number, title FROM episodes WHERE project_id=? ORDER BY episode_number", (project_id,))
            if episodes:
                ep_options = ["بدون حلقة"] + [f"الحلقة {ep['episode_number']}: {ep['title']}" for ep in episodes]
                sc_episode_choice = st.selectbox(t("اختر الحلقة"), ep_options, key=f"scene_episode_{project_id}")
                if sc_episode_choice != "بدون حلقة":
                    ep_idx = ep_options.index(sc_episode_choice) - 1
                    sc_episode_id = episodes[ep_idx]['id']
        sc_notes = st.text_area(t("ملاحظات المشهد العامة"), height=150)
        all_chars_for_scene = fetch_all("SELECT id, name FROM characters WHERE project_id=? ORDER BY id", (project_id,))
        char_map_for_scene = {c["name"]: c["id"] for c in all_chars_for_scene}
        sc_characters = st.multiselect(t("الشخصيات الموجودة في المشهد"), list(char_map_for_scene.keys()))
        all_props_for_scene = fetch_all("SELECT id, name FROM props WHERE project_id=? ORDER BY id", (project_id,))
        prop_map_for_scene = {p["name"]: p["id"] for p in all_props_for_scene}
        sc_props = st.multiselect(t("الإكسسوارات الموجودة في المشهد"), list(prop_map_for_scene.keys()))
        if st.form_submit_button(t("إضافة مشهد")):
            loc_id = loc_variant_map.get(sc_location)
            existing_scene_numbers_now = {
                s["scene_number"] for s in fetch_all("SELECT scene_number FROM scenes WHERE project_id=?", (project_id,))
            }
            if sc_number in existing_scene_numbers_now:
                # الرقم ده مستخدم قبل كده - بندفع كل المشاهد اللي رقمها أكبر
                # أو يساويه رقم واحد لقدام، عشان المشهد الجديد يحتل الرقم ده
                # بالظبط من غير ما يبوّظ ترتيب المشاهد التانية
                shift_scene_numbers(project_id, sc_number)
                st.info(t("الرقم ده كان مستخدم - تم نقل باقي المشاهد رقم واحد لقدام عشان تتزبط."))
            new_scene_id = run_query(
                "INSERT INTO scenes (project_id, episode_id, scene_number, int_ext, day_night, weather, location_variant_id, notes) VALUES (?,?,?,?,?,?,?,?)",
                (project_id, sc_episode_id, sc_number, sc_int_ext, sc_day_night, sc_weather, loc_id, sc_notes),
            )
            for _cname in sc_characters:
                run_query("INSERT OR IGNORE INTO scene_characters (scene_id, character_id) VALUES (?,?)",
                           (new_scene_id, char_map_for_scene[_cname]))
            for _pname in sc_props:
                run_query("INSERT OR IGNORE INTO scene_props (scene_id, prop_id) VALUES (?,?)",
                           (new_scene_id, prop_map_for_scene[_pname]))
            bump_version(project_id)
            st.rerun()

    st.divider()
    scenes = fetch_all("SELECT * FROM scenes WHERE project_id=? ORDER BY scene_number", (project_id,))
    id_to_loc_label = {v: k for k, v in loc_variant_map.items()}
    int_ext_edit_options = ["غير محدد"] + INT_EXT_OPTIONS
    day_night_edit_options = ["غير محدد"] + DAY_NIGHT_OPTIONS
    loc_edit_options = ["بدون تحديد"] + list(loc_variant_map.keys())

    selected_scene_ids_for_bulk_delete = []
    for sc in scenes:
        title = (
            f"{t('مشهد')} {sc['scene_number']} — {ltr(fmt_int_ext(sc['int_ext'] or 'غير محدد'))} / "
            f"{fmt_day_night(sc['day_night'] or 'غير محدد')}"
        )
        cb_col, exp_col = st.columns([0.05, 0.95])
        with cb_col:
            st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)
            if st.checkbox("", key=f"bulk_sel_scene_{sc['id']}", label_visibility="collapsed"):
                selected_scene_ids_for_bulk_delete.append(sc["id"])
        with exp_col.expander(title, key=f"exp_scene_{sc['id']}"):
            with st.form(f"edit_scene_{sc['id']}"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    esc_number = st.number_input(t("رقم المشهد"), min_value=1, step=1, value=sc["scene_number"])
                    esc_int_ext = st.selectbox(
                        t("داخلي/خارجي"), int_ext_edit_options,
                        index=safe_index(int_ext_edit_options, sc["int_ext"] or "غير محدد"),
                        format_func=fmt_int_ext,
                    )
                with col2:
                    esc_day_night = st.selectbox(
                        t("التوقيت"), day_night_edit_options,
                        index=safe_index(day_night_edit_options, sc["day_night"] or "غير محدد"),
                        format_func=fmt_day_night,
                    )
                    esc_location = st.selectbox(
                        t("المكان"), loc_edit_options,
                        index=safe_index(loc_edit_options, id_to_loc_label.get(sc["location_variant_id"], "بدون تحديد")),
                        format_func=t,
                    )
                with col3:
                    esc_weather = st.text_input(
                        t("الطقس"), value=sc["weather"] or "",
                        placeholder=t("مثال: شتاء مشمس، أو صيف حار وضبابي"),
                    )
                esc_notes = st.text_area(t("ملاحظات المشهد العامة"), value=sc["notes"] or "", height=180)

                esc_current_char_ids = {
                    r["character_id"] for r in fetch_all(
                        "SELECT character_id FROM scene_characters WHERE scene_id=?", (sc["id"],)
                    )
                }
                esc_current_char_names = [n for n, cid in char_map_for_scene.items() if cid in esc_current_char_ids]
                esc_characters = st.multiselect(
                    t("الشخصيات الموجودة في المشهد"), list(char_map_for_scene.keys()),
                    default=esc_current_char_names,
                )
                esc_current_prop_ids = {
                    r["prop_id"] for r in fetch_all(
                        "SELECT prop_id FROM scene_props WHERE scene_id=?", (sc["id"],)
                    )
                }
                esc_current_prop_names = [n for n, pid in prop_map_for_scene.items() if pid in esc_current_prop_ids]
                esc_props = st.multiselect(
                    t("الإكسسوارات الموجودة في المشهد"), list(prop_map_for_scene.keys()),
                    default=esc_current_prop_names,
                )

                ssave_col, sdel_col = st.columns(2)
                with ssave_col:
                    save_sc = st.form_submit_button(t("💾 حفظ التعديل"))
                with sdel_col:
                    del_sc = st.form_submit_button(t("🗑️ حذف المشهد (وكل لقطاته)"))
            if save_sc:
                new_int_ext = None if esc_int_ext == "غير محدد" else esc_int_ext
                new_day_night = None if esc_day_night == "غير محدد" else esc_day_night
                new_loc_id = loc_variant_map.get(esc_location)
                if esc_number != sc["scene_number"]:
                    colliding = fetch_all(
                        "SELECT id FROM scenes WHERE project_id=? AND scene_number=? AND id != ?",
                        (project_id, esc_number, sc["id"]),
                    )
                    if colliding:
                        shift_scene_numbers(project_id, esc_number, exclude_scene_id=sc["id"])
                        st.info(t("الرقم ده كان مستخدم - تم نقل باقي المشاهد رقم واحد لقدام عشان تتزبط."))
                run_query(
                    "UPDATE scenes SET scene_number=?, int_ext=?, day_night=?, weather=?, location_variant_id=?, notes=? WHERE id=?",
                    (esc_number, new_int_ext, new_day_night, esc_weather, new_loc_id, esc_notes, sc["id"]),
                )
                run_query("DELETE FROM scene_characters WHERE scene_id=?", (sc["id"],))
                for _cname in esc_characters:
                    run_query("INSERT OR IGNORE INTO scene_characters (scene_id, character_id) VALUES (?,?)",
                               (sc["id"], char_map_for_scene[_cname]))
                run_query("DELETE FROM scene_props WHERE scene_id=?", (sc["id"],))
                for _pname in esc_props:
                    run_query("INSERT OR IGNORE INTO scene_props (scene_id, prop_id) VALUES (?,?)",
                               (sc["id"], prop_map_for_scene[_pname]))
                bump_version(project_id)
                mark_saved(f"scene_{sc['id']}")
                st.rerun()
            if del_sc:
                run_query("DELETE FROM scenes WHERE id=?", (sc["id"],))
                bump_version(project_id)
                st.success(t("تم حذف المشهد"))
                st.rerun()
            show_saved_badge(f"scene_{sc['id']}")

    if selected_scene_ids_for_bulk_delete:
        with st.container(key=f"bulk_delete_scenes_{project_id}"):
            if st.button(
                f"🗑️ {t('حذف')} {len(selected_scene_ids_for_bulk_delete)} {t('مشهد مختار (وكل لقطاتهم)')}",
            ):
                for _sid in selected_scene_ids_for_bulk_delete:
                    run_query("DELETE FROM scenes WHERE id=?", (_sid,))
                bump_version(project_id)
                st.success(t("تم حذف المشاهد المختارة"))
                st.rerun()

# ---------------- تبويب التفريغ (اللقطات) ----------------
with tab_breakdown:
    st.subheader(tr("sub_breakdown"))
    scenes = fetch_all("SELECT * FROM scenes WHERE project_id=? ORDER BY scene_number", (project_id,))
    if not scenes:
        st.info(t("لازم تضيف مشهد واحد على الأقل من تبويب السكريبت أولًا"))
    else:
        scene_map = {f"{t('مشهد')} {s['scene_number']}": s["id"] for s in scenes}
        sel_scene = st.selectbox(t("اختر المشهد"), list(scene_map.keys()))
        scene_id = scene_map[sel_scene]
        current_scene_row = fetch_all("SELECT notes, day_night FROM scenes WHERE id=?", (scene_id,))[0]
        available_dialogue_lines = unused_dialogue_lines(current_scene_row["notes"], scene_id, fetch_all)

        with st.form(f"add_shot_{scene_id}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                sh_number = st.number_input(t("رقم اللقطة"), min_value=1, step=1)
                sh_size = st.selectbox(t("حجم الكادر"), SHOT_SIZE_OPTIONS, format_func=t, help=FIELD_HELP["shot_size"])
            with col2:
                sh_movement = st.selectbox(t("حركة الكاميرا"), CAMERA_MOVEMENT_OPTIONS, format_func=t, help=FIELD_HELP["camera_movement"])
                sh_angle = st.selectbox(t("زاوية الكاميرا"), CAMERA_ANGLE_OPTIONS, format_func=t, help=FIELD_HELP["camera_angle"])
            with col3:
                sh_duration = st.number_input(t("المدة (ثانية)"), min_value=1.0, max_value=30.0, value=5.0, step=0.5)
                sh_emotion = st.slider(t("قوة المشاعر"), 1, 5, 3, help=FIELD_HELP["emotion_intensity"])

            col4, col5 = st.columns(2)
            with col4:
                # اللقطة الجديدة بتاخد نهار/ليل المشهد بتاعها كقيمة افتراضية، والمستخدم
                # يقدر يغيّرها لو اللقطة دي بالذات اتصورت في وقت مختلف عن باقي المشهد
                sh_day_night = st.selectbox(t("النهار/الليل"), DAY_NIGHT_OPTIONS,
                                             index=safe_index(DAY_NIGHT_OPTIONS, current_scene_row["day_night"]),
                                             format_func=fmt_day_night,
                                             help=FIELD_HELP["day_night"])
            with col5:
                sh_weather = st.text_input(t("حالة الطقس"), placeholder=t("مثال: شتاء مشمس، أو صيف حار وضبابي"))

            sh_action = st.text_area(
                t("وصف الحركة داخل اللقطة"), height=100,
                placeholder=t("مثال: أحمد بيدخل الأوضة وبيقفل الباب وراه، سارة واقفة جنب الشباك بتبص برة"),
            )
            sh_emotion_label = st.text_input(t("وصف المشاعر"), placeholder=t("مثال: أحمد حزين، سارة غير مهتمة"))
            if available_dialogue_lines:
                st.caption(t(
                    "دول سطور الحوار اللي لسه في حوار المشهد ومتحطوش في لقطة تانية - اختار بس اللي موجود في "
                    "اللقطة دي (سيبها من غير اختيار لو اللقطة من غير حوار)."
                ))
                sh_selected_dialogue = st.multiselect(t("سطور الحوار المتاحة من حوار المشهد"), available_dialogue_lines)
                sh_dialogue = "\n".join(sh_selected_dialogue)
                with st.expander(t("أو اكتب/عدّل الحوار يدويًا بدل الاختيار")):
                    sh_dialogue_manual = st.text_area(
                        t("الحوار (لو موجود)"), height=100,
                        placeholder=t("مثال: أحمد (حزين): إزيك يا سارة؟\nسارة (غير مبالية): تمام والحمد لله."),
                    )
                    if sh_dialogue_manual.strip():
                        sh_dialogue = sh_dialogue_manual
            else:
                sh_dialogue = st.text_area(
                    t("الحوار (لو موجود)"), height=150,
                    placeholder=t("مثال: أحمد (حزين): إزيك يا سارة؟\nسارة (غير مبالية): تمام والحمد لله."),
                )
            sh_style = st.text_area(
                t("ملاحظات النمط البصري / المرجع"), height=120,
                placeholder=t("مثال: إضاءة دافية، ألوان بيج وبني، حركة كاميرا هادئة"),
            )
            sh_music = st.checkbox(t("تضمين موسيقى في التوليد نفسه؟ (غير مستحسن)"), value=False, help=FIELD_HELP["include_music"])

            st.markdown(f"**{t('الشخصيات الموجودة في اللقطة')}**")
            all_looks = fetch_all("""
                SELECT cl.id, ch.name || ' - ' || cl.look_name AS label
                FROM character_looks cl JOIN characters ch ON cl.character_id = ch.id
                WHERE ch.project_id = ?
            """, (project_id,))
            look_map = {r["label"]: r["id"] for r in all_looks}
            selected_looks = st.multiselect(t("اختر مظهر كل شخصية ظاهرة"), list(look_map.keys()))
            dialogue_flags = {}
            if selected_looks:
                st.caption(t("لكل شخصية، حدد لو ليها حوار في اللقطة دي (سيبها فاضية لو الشخصية موجودة بس ساكتة)"))
                for _label in selected_looks:
                    dialogue_flags[_label] = st.checkbox(
                        f"{_label} — {t('لها حوار في اللقطة دي؟')}", value=True, key=f"new_shot_dialogue_{_label}",
                    )

            st.markdown(f"**{t('الإكسسوارات الموجودة في اللقطة')}**")
            all_props = fetch_all("SELECT id, name FROM props WHERE project_id=? ORDER BY id", (project_id,))
            prop_map = {r["name"]: r["id"] for r in all_props}
            selected_props = st.multiselect(t("اختر الإكسسوارات الظاهرة في اللقطة"), list(prop_map.keys()))

            sh_confirmed = st.checkbox(t("🔵 تمت المراجعة والموافقة على كل بيانات اللقطة"), help=FIELD_HELP["confirmed"])
            sh_storyboard = st.file_uploader(t("صورة ستوري بورد مرجعية (اختياري)"), type=IMAGE_TYPES, key="new_shot_storyboard")

            if st.form_submit_button(t("حفظ اللقطة")):
                existing_shot_numbers_now = {
                    s["shot_number"] for s in fetch_all("SELECT shot_number FROM shots WHERE scene_id=?", (scene_id,))
                }
                if sh_number in existing_shot_numbers_now:
                    shift_shot_numbers(scene_id, sh_number)
                    st.info(t("الرقم ده كان مستخدم - تم نقل باقي اللقطات رقم واحد لقدام عشان تتزبط."))
                shot_id = run_query(
                    """INSERT INTO shots
                    (scene_id, shot_number, shot_size, camera_movement, camera_angle, duration_seconds,
                     day_night, weather, action_description,
                     emotion_intensity, emotion_label, dialogue_text, visual_style_notes, include_music, confirmed)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (scene_id, sh_number, sh_size, sh_movement, sh_angle, sh_duration,
                     sh_day_night, sh_weather, sh_action,
                     sh_emotion, sh_emotion_label, sh_dialogue, sh_style, int(sh_music), int(sh_confirmed)),
                )
                bump_version(project_id)
                if sh_storyboard is not None:
                    storyboard_path = save_uploaded_image(sh_storyboard, f"shots/{shot_id}")
                    run_query("UPDATE shots SET storyboard_image_path=? WHERE id=?", (storyboard_path, shot_id))
                for label in selected_looks:
                    run_query("INSERT INTO shot_characters (shot_id, look_id, has_dialogue) VALUES (?,?,?)",
                               (shot_id, look_map[label], int(dialogue_flags.get(label, True))))
                for prop_label in selected_props:
                    run_query("INSERT INTO shot_props (shot_id, prop_id) VALUES (?,?)",
                               (shot_id, prop_map[prop_label]))
                st.success(t("تم حفظ اللقطة"))
                st.rerun()

        st.divider()
        shots = fetch_all("SELECT * FROM shots WHERE scene_id=? ORDER BY shot_number", (scene_id,))
        for sh in shots:
            status_icon = "🔵" if sh["confirmed"] else "🟡"
            with st.expander(f"{status_icon} {t('لقطة')} {sh['shot_number']} — {ltr(t(sh['shot_size']))} / {ltr(t(sh['camera_movement']))}", key=f"exp_shot_{sh['id']}"):
                current_looks = fetch_all(
                    "SELECT look_id, has_dialogue FROM shot_characters WHERE shot_id=?", (sh["id"],)
                )
                current_dialogue_by_look_id = {r["look_id"]: bool(r["has_dialogue"]) for r in current_looks}
                current_look_ids = set(current_dialogue_by_look_id.keys())
                current_labels = [label for label, lid in look_map.items() if lid in current_look_ids]
                current_prop_ids = {
                    r["prop_id"] for r in fetch_all("SELECT prop_id FROM shot_props WHERE shot_id=?", (sh["id"],))
                }
                current_prop_labels = [name for name, pid in prop_map.items() if pid in current_prop_ids]

                with st.form(f"edit_shot_{sh['id']}"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        esh_number = st.number_input(t("رقم اللقطة"), min_value=1, step=1, value=sh["shot_number"])
                        esh_size = st.selectbox(t("حجم الكادر"), SHOT_SIZE_OPTIONS,
                                                 index=safe_index(SHOT_SIZE_OPTIONS, sh["shot_size"]), format_func=t)
                    with col2:
                        esh_movement = st.selectbox(t("حركة الكاميرا"), CAMERA_MOVEMENT_OPTIONS,
                                                     index=safe_index(CAMERA_MOVEMENT_OPTIONS, sh["camera_movement"]), format_func=t)
                        esh_angle = st.selectbox(t("زاوية الكاميرا"), CAMERA_ANGLE_OPTIONS,
                                                  index=safe_index(CAMERA_ANGLE_OPTIONS, sh["camera_angle"]), format_func=t)
                    with col3:
                        esh_duration = st.number_input(
                            t("المدة (ثانية)"), min_value=1.0, max_value=30.0,
                            value=float(sh["duration_seconds"] or 5.0), step=0.5,
                        )
                        esh_emotion = st.slider(t("قوة المشاعر"), 1, 5, value=sh["emotion_intensity"] or 3)

                    ecol4, ecol5 = st.columns(2)
                    with ecol4:
                        esh_day_night = st.selectbox(
                            t("النهار/الليل"), DAY_NIGHT_OPTIONS,
                            index=safe_index(DAY_NIGHT_OPTIONS, sh["day_night"]),
                            format_func=fmt_day_night,
                        )
                    with ecol5:
                        esh_weather = st.text_input(
                            t("حالة الطقس"), value=sh["weather"] or "",
                            placeholder=t("مثال: شتاء مشمس، أو صيف حار وضبابي"),
                        )

                    esh_action = st.text_area(
                        t("وصف الحركة داخل اللقطة"), value=sh["action_description"] or "", height=100,
                        placeholder=t("مثال: أحمد بيدخل الأوضة وبيقفل الباب وراه، سارة واقفة جنب الشباك بتبص برة"),
                    )
                    esh_emotion_label = st.text_input(
                        t("وصف المشاعر"), value=sh["emotion_label"] or "", placeholder=t("مثال: أحمد حزين، سارة غير مهتمة"),
                    )
                    esh_edit_available_lines = unused_dialogue_lines(
                        current_scene_row["notes"], scene_id, fetch_all, exclude_shot_id=sh["id"]
                    )
                    if esh_edit_available_lines:
                        esh_current_dialogue_lines = [
                            l.strip() for l in (sh["dialogue_text"] or "").split("\n") if l.strip()
                        ]
                        st.caption(t(
                            "دول سطور الحوار اللي لسه في حوار المشهد ومتحطوش في لقطة تانية - اختار بس اللي موجود في "
                            "اللقطة دي (سيبها من غير اختيار لو اللقطة من غير حوار)."
                        ))
                        esh_selected_dialogue = st.multiselect(
                            t("سطور الحوار المتاحة من حوار المشهد"), esh_edit_available_lines,
                            default=[l for l in esh_current_dialogue_lines if l in esh_edit_available_lines],
                        )
                        esh_dialogue = "\n".join(esh_selected_dialogue)
                        with st.expander(t("أو اكتب/عدّل الحوار يدويًا بدل الاختيار")):
                            esh_dialogue_manual = st.text_area(
                                t("الحوار (لو موجود)"), value="", height=100,
                                placeholder=t("مثال: أحمد (حزين): إزيك يا سارة؟\nسارة (غير مبالية): تمام والحمد لله."),
                            )
                            if esh_dialogue_manual.strip():
                                esh_dialogue = esh_dialogue_manual
                    else:
                        esh_dialogue = st.text_area(
                            t("الحوار (لو موجود)"), value=sh["dialogue_text"] or "", height=150,
                            placeholder=t("مثال: أحمد (حزين): إزيك يا سارة؟\nسارة (غير مبالية): تمام والحمد لله."),
                        )
                    esh_style = st.text_area(
                        t("ملاحظات النمط البصري / المرجع"), value=sh["visual_style_notes"] or "", height=120,
                        placeholder=t("مثال: إضاءة دافية، ألوان بيج وبني، حركة كاميرا هادئة"),
                    )
                    esh_music = st.checkbox(t("تضمين موسيقى في التوليد نفسه؟ (غير مستحسن)"), value=bool(sh["include_music"]))

                    st.markdown(f"**{t('الشخصيات الموجودة في اللقطة')}**")
                    esh_selected_looks = st.multiselect(
                        t("اختر مظهر كل شخصية ظاهرة"), list(look_map.keys()), default=current_labels
                    )
                    esh_dialogue_flags = {}
                    if esh_selected_looks:
                        st.caption(t("لكل شخصية، حدد لو ليها حوار في اللقطة دي (سيبها فاضية لو الشخصية موجودة بس ساكتة)"))
                        for _label in esh_selected_looks:
                            _default = current_dialogue_by_look_id.get(look_map[_label], True)
                            esh_dialogue_flags[_label] = st.checkbox(
                                f"{_label} — {t('لها حوار في اللقطة دي؟')}", value=_default,
                                key=f"edit_shot_dialogue_{sh['id']}_{_label}",
                            )

                    st.markdown(f"**{t('الإكسسوارات الموجودة في اللقطة')}**")
                    esh_selected_props = st.multiselect(
                        t("اختر الإكسسوارات الظاهرة في اللقطة"), list(prop_map.keys()), default=current_prop_labels
                    )

                    esh_confirmed = st.checkbox(t("🔵 تمت المراجعة والموافقة على كل بيانات اللقطة"), value=bool(sh["confirmed"]))

                    if sh["storyboard_image_path"]:
                        existing_storyboard = image_abs_path(sh["storyboard_image_path"])
                        if existing_storyboard:
                            st.image(existing_storyboard, width=260)
                    esh_storyboard = st.file_uploader(
                        t("تغيير صورة الستوري بورد المرجعية"), type=IMAGE_TYPES, key=f"shot_storyboard_{sh['id']}"
                    )

                    hsave_col, hdel_col = st.columns(2)
                    with hsave_col:
                        save_sh = st.form_submit_button(t("💾 حفظ التعديل"))
                    with hdel_col:
                        del_sh = st.form_submit_button(t("🗑️ حذف اللقطة"))

                if save_sh:
                    if esh_number != sh["shot_number"]:
                        colliding_shot = fetch_all(
                            "SELECT id FROM shots WHERE scene_id=? AND shot_number=? AND id != ?",
                            (sh["scene_id"], esh_number, sh["id"]),
                        )
                        if colliding_shot:
                            shift_shot_numbers(sh["scene_id"], esh_number, exclude_shot_id=sh["id"])
                            st.info(t("الرقم ده كان مستخدم - تم نقل باقي اللقطات رقم واحد لقدام عشان تتزبط."))
                    new_storyboard_path = sh["storyboard_image_path"]
                    if esh_storyboard is not None:
                        new_storyboard_path = save_uploaded_image(esh_storyboard, f"shots/{sh['id']}")
                    run_query(
                        """UPDATE shots SET shot_number=?, shot_size=?, camera_movement=?, camera_angle=?,
                        duration_seconds=?, day_night=?, weather=?, action_description=?,
                        emotion_intensity=?, emotion_label=?, dialogue_text=?,
                        visual_style_notes=?, include_music=?, confirmed=?, storyboard_image_path=? WHERE id=?""",
                        (esh_number, esh_size, esh_movement, esh_angle, esh_duration,
                         esh_day_night, esh_weather, esh_action, esh_emotion,
                         esh_emotion_label, esh_dialogue, esh_style, int(esh_music), int(esh_confirmed),
                         new_storyboard_path, sh["id"]),
                    )
                    run_query("DELETE FROM shot_characters WHERE shot_id=?", (sh["id"],))
                    for label in esh_selected_looks:
                        run_query("INSERT INTO shot_characters (shot_id, look_id, has_dialogue) VALUES (?,?,?)",
                                   (sh["id"], look_map[label], int(esh_dialogue_flags.get(label, True))))
                    run_query("DELETE FROM shot_props WHERE shot_id=?", (sh["id"],))
                    for prop_label in esh_selected_props:
                        run_query("INSERT INTO shot_props (shot_id, prop_id) VALUES (?,?)",
                                   (sh["id"], prop_map[prop_label]))
                    bump_version(project_id)
                    mark_saved(f"shot_{sh['id']}")
                    st.rerun()
                if del_sh:
                    run_query("DELETE FROM shots WHERE id=?", (sh["id"],))
                    bump_version(project_id)
                    delete_image_file(sh["storyboard_image_path"])
                    st.success(t("تم حذف اللقطة"))
                    st.rerun()
                show_saved_badge(f"shot_{sh['id']}")

# ---------------- تبويب لوحة المتابعة ----------------
with tab_dashboard:
    st.subheader(tr("sub_dashboard"))

    if _scene_count > 0:
        st.markdown(f"#### {t('📄 تصدير تفريغ اللقطات')}")
        st.caption(t("ملف تفريغ كامل قابل للطباعة، بفورمات سينمائي احترافي."))

        # مهم جدًا: بناء ملفات التصدير (خصوصًا الـ PDF) عملية بطيئة، وتبويبات
        # Streamlit كلها بتتنفذ في كل مرة الصفحة تتحدث (حتى التبويبات المقفولة
        # وقت اللمحة)، فلو استدعينا build_shot_list_* من غير أي حماية، هيتكرر
        # التصدير الكامل مع أي حركة في أي مكان في البرنامج - وده كان بيسبب
        # التهنيج/التجمد اللي حصل. الحل: نخزن النتيجة في session_state ونعيد
        # التصدير بس لو عدد المشاهد/اللقطات/المؤكدة اتغير فعلاً.
        _export_cache_key = (project_id, _loc_count, _char_count, _scene_count, _shot_count, _confirmed_count)
        if st.session_state.get("_export_cache_key") != _export_cache_key:
            st.session_state["_export_excel_bytes"] = build_shot_list_excel(project, project_id, fetch_all)
            st.session_state["_export_word_bytes"] = build_shot_list_word(project, project_id, fetch_all)
            st.session_state["_export_pdf_bytes"] = build_shot_list_pdf(project, project_id, fetch_all)
            st.session_state["_export_characters_bytes"] = build_characters_sheet_excel(project, project_id, fetch_all)
            st.session_state["_export_general_breakdown_bytes"] = build_general_breakdown_excel(project, project_id, fetch_all)
            st.session_state["_export_locations_bytes"] = build_locations_sheet_excel(project, project_id, fetch_all)
            st.session_state["_export_props_bytes"] = build_props_sheet_excel(project, project_id, fetch_all)
            st.session_state["_export_cache_key"] = _export_cache_key

        exp_col1, exp_col2, exp_col3, exp_col4 = st.columns(4)
        with exp_col1:
            st.download_button(
                tr("btn_export_excel"),
                data=st.session_state["_export_excel_bytes"],
                file_name=f"{project['name']}_تفريغ_اللقطات.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_excel_{project_id}",
            )
        with exp_col2:
            st.download_button(
                tr("btn_export_word"),
                data=st.session_state["_export_word_bytes"],
                file_name=f"{project['name']}_تفريغ_اللقطات.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"dl_word_{project_id}",
            )
        with exp_col3:
            st.download_button(
                tr("btn_export_pdf"),
                data=st.session_state["_export_pdf_bytes"],
                file_name=f"{project['name']}_تفريغ_اللقطات.pdf",
                mime="application/pdf",
                key=f"dl_pdf_{project_id}",
            )
        with exp_col4:
            if st.button(t("🔄 تحديث الملفات"), key=f"refresh_export_{project_id}",
                         help=t("لو عدّلت محتوى لقطة موجودة (حوار، وصف...) من غير ما تضيف أو تمسح لقطات، دوس هنا عشان الملفات تتحدث بآخر بياناتك.")):
                st.session_state["_export_cache_key"] = None
                st.rerun()

        st.markdown(f"#### {t('📋 تقارير الإنتاج القياسية')}")
        st.caption(t(
            "نفس الأوراق القياسية اللي بيستخدمها مديرو الإنتاج (كشف الشخصيات، التفريغ العام، كشف أماكن "
            "التصوير)، متملية أوتوماتيك من بيانات مشروعك. الخانات اللي محتاجة قرار بشري (زي الترشيح، عدد "
            "أيام التصوير، عدد الصفحات) سايبينها فاضية عشان تملاها إنت وقت التحضير الفعلي للتصوير."
        ))
        rep_col1, rep_col2, rep_col3, rep_col4 = st.columns(4)
        with rep_col1:
            st.download_button(
                t("⬇️ كشف الشخصيات"),
                data=st.session_state["_export_characters_bytes"],
                file_name=f"{project['name']}_كشف_الشخصيات.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_characters_sheet_{project_id}",
            )
        with rep_col2:
            st.download_button(
                t("⬇️ التفريغ العام"),
                data=st.session_state["_export_general_breakdown_bytes"],
                file_name=f"{project['name']}_التفريغ_العام.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_general_breakdown_{project_id}",
            )
        with rep_col3:
            st.download_button(
                t("⬇️ كشف أماكن التصوير"),
                data=st.session_state["_export_locations_bytes"],
                file_name=f"{project['name']}_كشف_اماكن_التصوير.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_locations_sheet_{project_id}",
            )
        with rep_col4:
            st.download_button(
                t("⬇️ كشف الإكسسوار"),
                data=st.session_state["_export_props_bytes"],
                file_name=f"{project['name']}_كشف_الإكسسوار.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_props_sheet_{project_id}",
            )
        st.divider()

    if _loc_count == 0 or _char_count == 0:
        st.info(t("👉 الخطوة الجاية: روح تبويب **الأماكن** و**الشخصيات** وضيف الأماكن والشخصيات الأساسية في مشروعك."))
    elif _scene_count == 0:
        st.info(t("👉 الخطوة الجاية: روح تبويب **السكريبت (المشاهد)** وضيف مشاهد مشروعك (أو استوردها من ملف في تبويب استيراد السكريبت)."))
    elif _shot_count == 0:
        st.info(t("👉 الخطوة الجاية: روح تبويب **التفريغ (اللقطات)** وابدأ تفرّغ كل مشهد للقطات كاميرا تفصيلية."))

    all_shots = fetch_all("""
        SELECT s.scene_number, sh.shot_number, sh.shot_size, sh.camera_movement, sh.confirmed
        FROM shots sh JOIN scenes s ON sh.scene_id = s.id
        WHERE s.project_id = ? ORDER BY s.scene_number, sh.shot_number
    """, (project_id,))
    if not all_shots:
        st.caption(t("لسه مفيش لقطات مضافة"))
    else:
        total = len(all_shots)
        confirmed = sum(1 for s in all_shots if s["confirmed"])
        st.metric(t("نسبة اللقطات الجاهزة للتوليد"), f"{confirmed} / {total}")
        st.progress(confirmed / total if total else 0)

        if total and confirmed == total:
            st.success(t(
                "🎉 كل اللقطات اتراجعت وأتأكد منها. بيانات مشروعك دلوقتي متكاملة وجاهزة كمرجع كامل للإنتاج. "
                "البرنامج الحالي بيوقف هنا — التوليد الفعلي بالذكاء الاصطناعي مش متاح جوه البرنامج ده لسه، "
                "ومحتاج تطوير إضافي يربطه بأدوات التوليد."
            ))
        else:
            st.caption(t("👉 راجع اللقطات اللي لسه مش متأكد منها (🟡) من تبويب التفريغ، وعلّم 'تمت المراجعة' لما تخلص كل واحدة."))

        for s in all_shots:
            icon = "🔵" if s["confirmed"] else f"🟡 {t('محتاجة مراجعة')}"
            st.write(f"{t('مشهد')} {s['scene_number']} / {t('لقطة')} {s['shot_number']} — {ltr(t(s['shot_size']))} — {icon}")
