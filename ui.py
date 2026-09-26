"""أدوات الواجهة المشتركة بين التبويبات: تنسيق، عناصر، صور، أرقام.

اتنقلت من app.py كما هي."""

import image_gen
import os
import re
import html

import streamlit as st
from database import IntegrityError
import uuid
from database import DAY_NIGHT_LABELS, INT_EXT_LABELS, FIELD_HELP, SHOT_SIZE_OPTIONS, bilingual_label
from i18n import t
from importer import DEFAULT_VARIANT
import repo


def multiselect(*args, **kwargs):
    """st.multiselect بنص فاضي عربي.

    Streamlit بيكتب "Choose options" بالإنجليزي جوه أي multiselect فاضي، وده
    كان بيطلع في نص الواجهة العربي في 11 مكان. كل النداءات بتعدي من هنا بدل
    ما كل واحد يفتكر يحط placeholder لوحده.
    """
    kwargs.setdefault("placeholder", t("اختار واحد أو أكتر"))
    return st.multiselect(*args, **kwargs)


def _loc_display(label):
    """اسم المكان للعرض من غير «الشكل الأساسي».

    كل مكان بيتعمله حالة افتراضية بالاسم ده (importer.DEFAULT_VARIANT)، فكل
    مشهد كان بيتكتب «محطة مصر - الشكل الأساسي». الحالة بتظهر بس لو غير الافتراضية.
    """
    if not label:
        return label
    suffix = " - " + DEFAULT_VARIANT
    return label[: -len(suffix)] if label.endswith(suffix) else label


def library_search(key, total, noun):
    """خانة البحث فوق أي مكتبة. بترجع نص البحث (فاضي = اعرض الكل).

    العدد جوه النص الفاضي نفسه، فالمكتبة بتقول حجمها من غير سطر زيادة.
    """
    return st.text_input(
        t("بحث"), key=key, label_visibility="collapsed",
        placeholder=f"🔍 {t('دوّر في')} {total} {t(noun)}",
    )


def library_result_count(shown, total):
    """سطر «12 من 99» — بيظهر بس وقت البحث."""
    if shown == 0:
        st.caption(t("مفيش نتايج — جرّب كلمة تانية"))
    else:
        st.caption(f"{ltr(shown)} {t('من')} {ltr(total)}")


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
    repo.bump_project_data_version(project_id)


def shift_scene_numbers(project_id, from_number, exclude_scene_id=None, episode_number=None):
    """لو المستخدم ضاف أو غيّر رقم مشهد لرقم مستخدم قبل كده، بندفع كل المشاهد
    اللي رقمها >= الرقم الجديد رقم واحد لقدام - بما إن اللقطات مربوطة
    بالمشهد عن طريق scene_id (مش رقم المشهد)، الدفع ده آمن ومبيأثرش على أي
    بيانات تانية، بس بيحدث رقم المشهد المعروض بس."""
    if exclude_scene_id is not None:
        repo.shift_scene_numbers_up_except(project_id, from_number, exclude_scene_id, episode_number)
    else:
        repo.shift_scene_numbers_up(project_id, from_number, episode_number)


def shift_shot_numbers(project_id, scene_id, from_number, exclude_shot_id=None):
    """نفس فكرة shift_scene_numbers بس على مستوى اللقطات جوه مشهد واحد.

    اللقطات مفيهاش project_id، فالمشروع بيتمرر عشان طبقة البيانات تقفل الكتابة
    على مشاهد المشروع ده بس.
    """
    if exclude_shot_id is not None:
        repo.shift_shot_numbers_up_except(project_id, scene_id, from_number, exclude_shot_id)
    else:
        repo.shift_shot_numbers_up(project_id, scene_id, from_number)


def feature_on(key):
    """🛡️ الميزة دي مفتوحة لليوزر اللي داخل؟ (admin_users.FEATURES — المشغّل بيقفل ويفتح)."""
    import admin_users
    return admin_users.feature_on(st.session_state.get("_auth_user") or "", key)


def feature_locked(key):
    """سطر بيقول إن الميزة مقفولة على الحساب ده."""
    import admin_users
    st.caption(f"🔒 {t(admin_users.FEATURES[key])}: {t(admin_users.FEATURE_DENIED)}")


# الأرقام اللي بتظهر جنب تحليلات الذكاء الاصطناعي تقديرية، والخدمة مجانية دلوقتي
# (المالك 2026-09-26: "عشان محدش يتخض ويخاف يستخدمها").
FREE_NOTE = "تكلفة تقديرية — مجاني دلوقتي"


def free_cost(amount_text):
    """‎$0.12‎ → ‎$0.12 (تكلفة تقديرية — مجاني دلوقتي)‎"""
    return f"{amount_text} ({t(FREE_NOTE)})"


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


def save_image_bytes(data, ext, subfolder):
    """زي save_uploaded_image بس لصورة جاية كـ bytes (من التوليد مثلًا)."""
    folder = os.path.join(UPLOADS_DIR, subfolder)
    os.makedirs(folder, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext or '.png'}"
    with open(os.path.join(folder, filename), "wb") as f:
        f.write(data)
    return os.path.join("uploads", subfolder, filename)


def _openrouter_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key
    try:
        return st.secrets.get("image_gen", {}).get("openrouter_api_key")
    except Exception:
        return None


IMG_SRC_UPLOAD = "📁 رفع من الجهاز"


IMG_SRC_CAMERA = "📷 الكاميرا"


IMG_SRC_GENERATE = "✨ توليد بالذكاء الاصطناعي"

# اختيار سريع لحجم الكادر جوه شاشة التوليد - نفس مفردات SHOT_SIZE_OPTIONS
# المستخدمة أصلًا في تبويب اللقطات، مش قايمة جديدة.
SHOT_SIZE_OPTIONS_WITH_BLANK = ["غير محدد"] + SHOT_SIZE_OPTIONS


def _uploaded_mime(f):
    """MIME من f.type لو موجود، وإلا تخمين من امتداد الاسم - عشان data URL
    التوليد يبقى نوعه صح."""
    if getattr(f, "type", None):
        return f.type
    ext = os.path.splitext(f.name or "")[1].lower().lstrip(".")
    return f"image/{'jpeg' if ext == 'jpg' else ext or 'png'}"


def render_image_picker(key, current_rel, subfolder, prompt_for, on_saved, reference_slots=None):
    """صورة مرجعية بتلات طرق: رفع، كاميرا، أو توليد.

    برّه أي st.form عن قصد: جوه الفورم الاختيار مابيعملش rerun، فكان اختيار
    "توليد" بيفضل عارض خانة الرفع. prompt_for(shot_size, light) بيرجّع
    البرومبت المتجمّع تلقائيًا من بيانات المكان/الشخصية المحفوظة (مش نص فاضي
    اليوزر يكتبه من الصفر) - بيتعرض في خانة قابلة للتعديل قبل التوليد.
    reference_slots: قائمة (مفتاح، تسمية) لصور مرجعية اختيارية بتتبعت للموديل
    كصور مش نص (صورة ممثل/ة، صورة خلفية/مكان) - افتراضيًا خانة عامة واحدة.
    on_saved(rel_path أو None) بيكتب المسار في قاعدة البيانات."""
    current_abs = image_abs_path(current_rel)
    if current_abs:
        st.image(current_abs, width=340)
    source = st.radio(t("مصدر الصورة"), [IMG_SRC_UPLOAD, IMG_SRC_CAMERA, IMG_SRC_GENERATE],
                      horizontal=True, key=f"{key}_src", format_func=t)
    new_bytes, ext = None, ".png"
    if source == IMG_SRC_UPLOAD:
        f = st.file_uploader(t("اختر صورة"), type=IMAGE_TYPES, key=f"{key}_up")
        if f is not None and st.button(t("💾 حفظ الصورة"), key=f"{key}_save_up"):
            new_bytes, ext = f.getvalue(), os.path.splitext(f.name)[1] or ".png"
    elif source == IMG_SRC_CAMERA:
        # الكاميرا بتتفتح بس لما اليوزر يختارها — لو كانت الافتراضي كان
        # المتصفح هيطلب إذن الكاميرا مع كل فتحة للمكان.
        shot = st.camera_input(t("صوّر المكان"), key=f"{key}_cam")
        if shot is not None and st.button(t("💾 حفظ الصورة"), key=f"{key}_save_cam"):
            new_bytes, ext = shot.getvalue(), os.path.splitext(shot.name or "")[1] or ".jpg"
    else:
        st.caption(t("البرومبت اتجمّع تلقائيًا من البيانات المحفوظة — عدّله زي ما تحب."))
        pick_col1, pick_col2 = st.columns(2)
        with pick_col1:
            shot_size = st.selectbox(t("حجم الكادر"), SHOT_SIZE_OPTIONS_WITH_BLANK,
                                     format_func=t, key=f"{key}_shot_size", help=FIELD_HELP.get("shot_size"))
        with pick_col2:
            light = st.selectbox(t("الإضاءة"), image_gen.LIGHT_OPTIONS, format_func=t, key=f"{key}_light")
        default_prompt = prompt_for(shot_size, light)
        prompt_key = f"{key}_prompt"
        if prompt_key not in st.session_state:
            st.session_state[prompt_key] = default_prompt
        if st.button(t("🔄 إعادة التعبئة من البيانات المحفوظة"), key=f"{key}_reset_prompt"):
            st.session_state[prompt_key] = default_prompt
            st.rerun()
        prompt_text = st.text_area(t("وصف الصورة المطلوبة"), key=prompt_key, height=110)
        ref_bytes = []
        for slot_key, label in (reference_slots or [("ref", "صورة مرجعية توجّه الشكل (اختياري)")]):
            rf = st.file_uploader(t(label), type=IMAGE_TYPES, key=f"{key}_ref_{slot_key}")
            if rf is not None:
                ref_bytes.append((rf.getvalue(), _uploaded_mime(rf)))
        if st.button(t("✨ ولّد صورة"), key=f"{key}_gen"):
            with st.spinner(t("بنولّد الصورة... ده بياخد حوالي 10 ثواني")):
                try:
                    new_bytes, ext = image_gen.generate_image(
                        prompt_text, _openrouter_key(), reference_images=ref_bytes or None)
                except image_gen.ImageGenError as e:
                    st.error(t(str(e)))
    if new_bytes:
        on_saved(save_image_bytes(new_bytes, ext, subfolder))
        delete_image_file(current_rel)
        st.rerun()
    if current_abs and st.button(t("🗑️ شيل الصورة"), key=f"{key}_rm"):
        on_saved(None)
        delete_image_file(current_rel)
        st.rerun()


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


def guarded_delete(delete_fn, params, friendly_error):
    """بيمسح عن طريق دالة من repo، ولو الصف مستخدم في حتة تانية (زي حالة مكان
    مربوطة بمشهد، أو لوك مربوط بلقطة) بيوري رسالة واضحة بدل ما البرنامج يقع.

    نفس سلوك database.run_delete بالظبط، بس الـ SQL بقى في repo.py ورسالة
    الواجهة فضلت هنا — طبقة البيانات مابتكلمش Streamlit.
    """
    try:
        delete_fn(*params)
        return True
    except IntegrityError as exc:
        # P5: لو طبقة البيانات عندها سبب أدق (زي "ده آخر مظهر للشخصية")
        # بنوريه هو بدل الرسالة العامة بتاعت الشاشة
        st.error(t(getattr(exc, "user_message", None) or friendly_error))
        return False



# --- مراحل الشغل والتبويبات (اتفاق المالك 2026-09-24) ---------------------------
# مفتاح المرحلة فوق التبويبات: ما قبل الإنتاج / الإنتاج. كل مرحلة بتعرض
# تبويباتها بس (links.PHASES) عشان الشريط مايبقاش 11 تبويب مرة واحدة.

def open_tab_by_slug(slug):
    """بيفتح تبويب معيّن (من رابط أو زرار) — ومرحلته معاه. لازم يتنده قبل ما
    مفتاح المرحلة والتبويبات يتبنوا في الـ run ده. الفريق والإعدادات صفحات
    لوحدها (PROJECT_PAGES) فبتتفتح كصفحة، حتى من رابط قديم ‎?tab=team‎."""
    import links
    from i18n import tr
    if slug in PROJECT_PAGES:
        st.query_params["page"] = slug
        return
    phase = links.phase_of(slug, st.session_state.get("_cf_phase", "pre"))
    st.session_state["_cf_phase"] = phase
    st.session_state[f"main_tabs_{phase}"] = tr(links.TABS[slug])


def phase_tabs():
    """بيرسم مفتاح المرحلة وتبويباتها. بيرجّع ({slug: tab}, slug التبويب المفتوح)."""
    import links
    from i18n import t, tr
    st.session_state.setdefault("_cf_phase", "pre")
    phase = st.segmented_control(
        t("المرحلة"), list(links.PHASES), key="_cf_phase", required=True,
        label_visibility="collapsed", format_func=lambda p: tr(f"phase_{p}")) or "pre"
    slugs = links.PHASES[phase]
    tabs = dict(zip(slugs, st.tabs([tr(links.TABS[s]) for s in slugs], key=f"main_tabs_{phase}",
                                   on_change="rerun")))
    return tabs, next((slug for slug, tab in tabs.items() if tab.open), slugs[0])



def nav_link(label, href, title=None, icon_only=False):
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


# --- التنقّل: الشريط الجانبي بيتقفل لما ننتقل لصفحة (طلب المالك 2026-09-24) ---
# "لما بندوس على ترس الإعدادات ... الـ Side bar المفروض يقفل ونروح" - وكمان بعد
# إنشاء مشروع، تغيير المشروع أو مساحة العمل، وأي زرار بيودّي لصفحة تانية.
# Streamlit مالوش API يقفل الشريط، فبنعلّم إن الـ run الجاي لازم يقفله،
# والسكريبت بيدوس زرار القفل بتاع Streamlit نفسه (الشريط بيتقفل بنفس حركته
# العادية، ويتفتح تاني من نفس الزرار). من غير أي حرف "أصغر من" في السكريبت:
# st.html بيمسحه بصمت لو لقى حاجة شبه تاج HTML.

_CLOSE_KEY = "_cf_close_sidebar"
# data-n: رقم جديد مع كل طلب. من غيره، طلبين ورا بعض (الترس وبعده إنشاء
# مشروع) بيطلعوا نفس العنصر بالظبط في نفس المكان، فـ Streamlit مابيعيدش
# رسمه والسكريبت مابيتنفذش تاني.
_CLOSE_JS = (
    "<script data-n=\"%d\">(function(){var n=0;var iv=setInterval(function(){n++;"
    "var sb=document.querySelector('section[data-testid=stSidebar]');"
    "if(sb&&sb.getAttribute('aria-expanded')==='true'){"
    "var b=document.querySelector('[data-testid=stSidebarCollapseButton] button')"
    "||document.querySelector('[data-testid=stSidebarCollapseButton]');"
    "if(b){b.click();clearInterval(iv);}}"
    "else if(sb){clearInterval(iv);}"
    "if(n>40)clearInterval(iv);},100);})();</script>"
)


def request_close_sidebar():
    """الـ run الجاي يقفل الشريط الجانبي (للكولباك وon_change)."""
    st.session_state[_CLOSE_KEY] = True


def go_to(slug):
    """يفتح تبويب (ومرحلته) ويقفل الشريط - لأي زرار بيودّي لصفحة جوه المشروع.
    لو كان فيه صفحة مكتبة مفتوحة، بيقفلها (التبويب يبان مكانها)."""
    for k in ("page", "pick"):
        if k in st.query_params:
            del st.query_params[k]
    open_tab_by_slug(slug)
    request_close_sidebar()


def close_sidebar_now():
    """بيتنده مرة في كل run: لو فيه طلب قفل، بيبعت السكريبت مرة واحدة."""
    if st.session_state.pop(_CLOSE_KEY, False):
        n = st.session_state.get("_cf_close_n", 0) + 1
        st.session_state["_cf_close_n"] = n
        st.html(_CLOSE_JS % n, unsafe_allow_javascript=True)


# --- صفحات المكتبات (المالك 2026-09-24) -----------------------------------------
# مكتبة الممثلين، مكتبة مواقع التصوير، مكتبة التحليلات: صفحات لوحدها
# (?page=...) بتتفتح من الشريط الجانبي على طول، أو من جوه المشروع في وضع
# "اختار لـ..." (?pick=<id> - زي اختيار ممثل لشخصية). تغيير الـ query params
# مابيعملش reload للصفحة، فالجلسة والشريط بيفضلوا زي ما هم.
LIBRARY_PAGES = ("actors", "locations_lib", "library")
# صفحات المشروع اللي بتتفتح من الشريط الجانبي (👥 فريق العمل، ⚙️ الإعدادات) -
# مش تبويبات جنب المشاهد واللقطات (المالك 2026-09-24): مكان واحد لكل حاجة.
PROJECT_PAGES = ("team", "settings")


def open_page(page, **params):
    """كولباك: يفتح صفحة مكتبة (ومعاها params زي pick) ويقفل الشريط."""
    for k in ("page", "pick", "tab"):
        if k in st.query_params:
            del st.query_params[k]
    st.query_params["page"] = page
    for k, v in params.items():
        st.query_params[k] = str(v)
    request_close_sidebar()


def close_page(tab=None):
    """كولباك: يقفل صفحة المكتبة ويرجع للمشروع (وتبويب معيّن لو اتحدد)."""
    for k in ("page", "pick"):
        if k in st.query_params:
            del st.query_params[k]
    if tab:
        open_tab_by_slug(tab)
    request_close_sidebar()
