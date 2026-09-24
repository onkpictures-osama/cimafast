"""تبويب خزانة المواهب (P9 - Talent Vault): بحث كاستينج بالحرف الأول + بروفايل
كل ممثل/ة + ترشيح/تعاقد لشخصيات المشروع المفتوح.

عابر للشركات عمدًا (production، القرار المحسوم 2026-09-23): القايمة والبروفايل
العام هنا مش مفلترين بشركة المستخدم الحالي - مسبح ممثلين واحد كل شركات المنصة
بتدوّر فيه. الحقول الحساسة (مقاسات، تواصل، عادات) بس هي اللي بتتفلتر حسب
الشركة (رشّحت/تعاقدت مع الممثل/ة ده قبل كده ولا لأ) - repo.actor_unlocked_for_company.
التعديل للشركة اللي أضافت البروفايل أو مشغّل المنصة بس - repo.can_edit_actor.

حدود البيانات (ACTOR-CASTING-PLAN.md، محسومة): الممثلين الحقيقيين المعروفين
بياخدوا بس اللي مصدر عام موثوق بيقوله (اسم، بيو، أعمال). رقم تليفون، مقاسات،
عادات شخصية لشخص حقيقي عمرها ما بتتخترع - بتفضل فاضية وتتعرض "غير متوفر".
"""

import base64
import datetime as dt
import os

import streamlit as st

import permissions
import public_profile
import repo
import videos
from database import (ACTOR_CASTING_STATUS_LABELS, ACTOR_CATEGORY_OPTIONS,
                      ACTOR_SENSITIVE_FIELDS, FIELD_HELP, GENDER_OPTIONS)
from i18n import t, tr
from search import normalize
from ui import IMAGE_TYPES, close_page, go_to, guarded_delete, open_page, image_abs_path, ltr, multiselect, save_uploaded_image

# قفز بالحرف الأول: عربي هو الافتراضي (المنتج عربي أولًا)، إنجليزي بس لما
# الواجهة إنجليزي - مش لاتيني وبعدين ترقيع RTL (production، 2026-09-23).
_AR_ALPHABET = list("أبتثجحخدذرزسشصضطظعغفقكلمنهوي")
_EN_ALPHABET = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

_STALE_DAYS = 90  # تقريبًا 3 شهور - مهلة تحديث الصورة اللي المالك طلبها

_SELECTED_KEY = "_cf_selected_actor_id"
_VIDEO_WARN_KEY = "_cf_actor_video_warn"   # لينكات فيديو مش متعرف عليها من آخر حفظ

# أسماء الحقول الحساسة للعرض (البروفايل، واختيار "ظاهر للكل")
_SENSITIVE_LABELS = {
    "height_cm": "الطول", "weight_kg": "الوزن", "chest_cm": "محيط الصدر",
    "waist_cm": "محيط الخصر", "hips_cm": "محيط الورك", "shoe_size_eu": "مقاس الحذاء",
    "hair_color": "لون الشعر", "eye_color": "لون العين", "contact_phone": "رقم التواصل",
    "contact_email": "البريد الإلكتروني", "agent_name": "اسم الوكيل/ة",
    "agent_contact": "وسيلة تواصل الوكيل/ة", "hobbies": "الهوايات",
    "drives_car": "يقود عربية", "drives_motorcycle": "يقود موتوسيكل", "swims": "يعرف يعوم",
    "smokes": "مدخّن/ة", "skills_notes": "مهارات إضافية",
}


def _display_name(actor):
    return actor.get("stage_name") or actor["full_name"]


def _matches(query, actor):
    """فلترة فورية بأول الاسم (الشهرة أو الحقيقي) - في الذاكرة، من غير نداء
    لقاعدة البيانات في كل ضغطة. normalize بيوحّد أ/إ/آ/ا والتشكيل."""
    nq = normalize(query)
    if not nq:
        return True
    return any(normalize(n).startswith(nq)
               for n in (actor.get("stage_name"), actor.get("full_name")) if n)


def _photo_age_days(photo_updated_at):
    """عدد الأيام من آخر تحديث للصورة، أو None لو مفيش تاريخ."""
    if not photo_updated_at:
        return None
    try:
        updated = dt.datetime.fromisoformat(str(photo_updated_at))
    except ValueError:
        return None
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=dt.timezone.utc)
    return (dt.datetime.now(dt.timezone.utc) - updated).days


def _is_stale(actor):
    if not actor.get("photo_path"):
        return True
    age = _photo_age_days(actor.get("photo_updated_at"))
    return age is None or age > _STALE_DAYS


def _can_write():
    role = permissions.current_role()
    return role is None or permissions.can(role, "edit")


def render(project_id, company_id):
    """تبويب «الممثلين» جوه المشروع: ممثلين المشروع ده بس. المكتبة نفسها
    (البحث والبروفايلات والإضافة) صفحة لوحدها - render_library."""
    st.subheader(tr("tab_actors"))
    _render_project_cast(project_id)
    st.button(f"🎭 {t('افتح مكتبة الممثلين')}", key="cast_open_library", on_click=open_page, args=("actors",))


def render_library(current_user, project_id, company_id, pick=None):
    """🎭 مكتبة الممثلين (صفحة لوحدها، المالك 2026-09-24). من الشريط الجانبي:
    تصفّح. من كارت شخصية (?pick=<character_id>): "بتختار ممثل لدور X" -
    الترشيح/التعاقد بيبقى للشخصية دي، وبعده بيرجع لتبويب الشخصيات لوحده."""
    st.subheader(f"🎭 {t('مكتبة الممثلين')}")
    st.caption(tr("sub_actors"))
    char = None
    if pick and project_id:
        try:
            char = next((c for c in repo.characters_of_project_by_id(project_id) if c["id"] == int(pick)), None)
        except (TypeError, ValueError):
            char = None
    if char:
        c1, c2 = st.columns([3, 1], vertical_alignment="center")
        c1.info(f"🎯 {t('بتختار ممثل/ة لدور')} **{char['name']}**")
        c2.button(f"↩ {t('رجوع للشخصية')}", key="pick_back", use_container_width=True,
                  on_click=close_page, args=("characters",))
    selected_id = st.session_state.get(_SELECTED_KEY)
    if selected_id:
        _render_profile(selected_id, project_id, company_id, pick_char=char)
        return
    _render_search_and_list(company_id)
    st.divider()
    _render_add_actor_form(company_id)


# ---------- الفورم (إضافة وتعديل نفس الحقول) ----------

def _num(label, value, max_value, help_text=None, key=None):
    return st.number_input(t(label), min_value=0, max_value=max_value,
                           value=int(value) if value not in (None, "") else None,
                           step=1, help=help_text, key=key)


def _actor_fields(prefix, a=None):
    """الحقول نفسها للإضافة والتعديل. بيرجّع (values dict، الصورة المرفوعة).
    لازم يتنده جوه st.form."""
    a = a or {}
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input(t("الاسم الحقيقي"), value=a.get("full_name") or "",
                             placeholder=t("مثال: أحمد محمد"), key=f"{prefix}_name")
        cat_opts = ACTOR_CATEGORY_OPTIONS
        category = st.selectbox(t("التصنيف"), cat_opts, format_func=t, help=FIELD_HELP["actor_category"],
                                index=cat_opts.index(a["category"]) if a.get("category") in cat_opts else 0,
                                key=f"{prefix}_cat")
        bio = st.text_area(t("نبذة تعريفية (بيو)"), value=a.get("bio") or "", key=f"{prefix}_bio")
    with c2:
        stage = st.text_input(t("اسم الشهرة (اختياري)"), value=a.get("stage_name") or "",
                              placeholder=t("لو مختلف عن الاسم الحقيقي"), key=f"{prefix}_stage")
        gender = st.selectbox(t("الجنس"), GENDER_OPTIONS, format_func=t,
                              index=GENDER_OPTIONS.index(a["gender"]) if a.get("gender") in GENDER_OPTIONS else 0,
                              key=f"{prefix}_gender")
        credits = st.text_area(t("أعمال سابقة (سطر لكل عمل)"), value=a.get("credits_text") or "",
                               placeholder=t("مثال: فيلم كذا (2023) - دور كذا https://youtu.be/..."),
                               help=t("حط لينك فيديو (يوتيوب، فيميو، ديلي موشن، فيسبوك، أو ملف ‎.mp4‎) في نفس سطر العمل — الفيديو هيتعرض في البروفايل تحت العمل ده."),
                               key=f"{prefix}_credits")

    st.markdown(f"**{t('المقاسات (لإدارة الأزياء)')}**")
    m1, m2, m3 = st.columns(3)
    with m1:
        height = _num("الطول (سم)", a.get("height_cm"), 250, FIELD_HELP["actor_measurements"], f"{prefix}_h")
        chest = _num("محيط الصدر (سم)", a.get("chest_cm"), 200, key=f"{prefix}_chest")
    with m2:
        weight = _num("الوزن (كجم)", a.get("weight_kg"), 250, key=f"{prefix}_w")
        waist = _num("محيط الخصر (سم)", a.get("waist_cm"), 200, key=f"{prefix}_waist")
    with m3:
        shoe = _num("مقاس الحذاء (أوروبي)", a.get("shoe_size_eu"), 60, key=f"{prefix}_shoe")
        hips = _num("محيط الورك (سم)", a.get("hips_cm"), 200, key=f"{prefix}_hips")
    hc1, hc2 = st.columns(2)
    hair = hc1.text_input(t("لون الشعر"), value=a.get("hair_color") or "", key=f"{prefix}_hair")
    eyes = hc2.text_input(t("لون العين"), value=a.get("eye_color") or "", key=f"{prefix}_eyes")

    st.markdown(f"**{t('التواصل')}**")
    tc1, tc2 = st.columns(2)
    phone = tc1.text_input(t("رقم التواصل"), value=a.get("contact_phone") or "",
                           help=FIELD_HELP["actor_sensitive_gate"], key=f"{prefix}_phone")
    email = tc2.text_input(t("البريد الإلكتروني"), value=a.get("contact_email") or "", key=f"{prefix}_email")
    agent = tc1.text_input(t("اسم الوكيل/ة (اختياري)"), value=a.get("agent_name") or "", key=f"{prefix}_agent")
    agent_contact = tc2.text_input(t("وسيلة تواصل الوكيل/ة"), value=a.get("agent_contact") or "",
                                   key=f"{prefix}_agent_c")

    st.markdown(f"**{t('مهارات الكاستينج')}**")
    sc1, sc2, sc3, sc4 = st.columns(4)
    car = sc1.checkbox(t("يقود عربية"), value=bool(a.get("drives_car")), key=f"{prefix}_car")
    moto = sc2.checkbox(t("يقود موتوسيكل"), value=bool(a.get("drives_motorcycle")), key=f"{prefix}_moto")
    swims = sc3.checkbox(t("يعرف يعوم"), value=bool(a.get("swims")), key=f"{prefix}_swim")
    smokes = sc4.checkbox(t("مدخّن/ة"), value=bool(a.get("smokes")), key=f"{prefix}_smoke")
    hk1, hk2 = st.columns(2)
    hobbies = hk1.text_area(t("الهوايات"), value=a.get("hobbies") or "", key=f"{prefix}_hobbies")
    skills = hk2.text_area(t("مهارات إضافية"), value=a.get("skills_notes") or "", key=f"{prefix}_skills")

    st.markdown(f"**{t('روابط')}**")
    lc1, lc2 = st.columns(2)
    showreel = lc1.text_input(t("رابط الشوريل"), value=a.get("link_showreel") or "", key=f"{prefix}_reel")
    insta = lc2.text_input(t("رابط إنستجرام أو سوشيال ميديا"), value=a.get("link_instagram") or "",
                           key=f"{prefix}_insta")
    other = st.text_area(t("روابط تانية (سطر لكل رابط)"), value=a.get("link_other") or "", key=f"{prefix}_other")

    st.markdown(f"**{t('الخصوصية')}**")
    discoverable = st.checkbox(t("ظاهر في بحث الكاستينج؟"), value=bool(a.get("discoverable", 1)),
                               help=FIELD_HELP["actor_discoverable"], key=f"{prefix}_disc")
    current_public = [f for f in (a.get("always_public_fields") or "").split(",") if f in ACTOR_SENSITIVE_FIELDS]
    public = multiselect(t("بيانات تظهر للكل من غير ترشيح (اختياري)"), ACTOR_SENSITIVE_FIELDS,
                            default=current_public, format_func=lambda f: t(_SENSITIVE_LABELS[f]),
                            key=f"{prefix}_public")
    photo = st.file_uploader(t("صورة شخصية (لازم تتجدد كل 3 شهور تقريبًا)"), type=IMAGE_TYPES,
                             help=FIELD_HELP["actor_photo_freshness"], key=f"{prefix}_photo")

    values = {
        "full_name": name.strip(), "stage_name": stage.strip() or None, "category": category,
        "gender": gender, "bio": bio.strip(), "credits_text": credits.strip(),
        "height_cm": height, "weight_kg": weight, "chest_cm": chest, "waist_cm": waist,
        "hips_cm": hips, "shoe_size_eu": shoe, "hair_color": hair.strip(), "eye_color": eyes.strip(),
        "contact_phone": phone.strip(), "contact_email": email.strip(), "agent_name": agent.strip(),
        "agent_contact": agent_contact.strip(), "hobbies": hobbies.strip(),
        "drives_car": int(car), "drives_motorcycle": int(moto), "swims": int(swims), "smokes": int(smokes),
        "skills_notes": skills.strip(), "link_showreel": showreel.strip(), "link_instagram": insta.strip(),
        "link_other": other.strip(), "discoverable": int(discoverable),
        "always_public_fields": ",".join(public),
    }
    return values, photo


def _render_add_actor_form(company_id):
    with st.expander(f"➕ {t('إضافة ممثل/ة جديد/ة')}", expanded=False):
        st.caption(t("الحقول اللي مالهاش مصدر عام موثوق (زي رقم التواصل أو المقاسات) سيبها فاضية - متخترعش قيم لها، خصوصًا لو الممثل/ة شخص حقيقي معروف."))
        with st.form("add_actor_form", clear_on_submit=True):
            values, photo = _actor_fields("new_actor")
            submitted = st.form_submit_button(t("إضافة الممثل/ة"), disabled=not _can_write())
        if submitted:
            if not values["full_name"]:
                st.warning(t("اسم الممثل/ة مينفعش يبقى فاضي"))
                return
            new_id = repo.add_actor(values, owner_company_id=company_id,
                                    created_by=st.session_state.get("_auth_user"))
            if photo is not None:
                repo.set_actor_photo(new_id, save_uploaded_image(photo, f"actors/{new_id}"))
            _flag_unrecognised(values["credits_text"])
            st.session_state[_SELECTED_KEY] = new_id
            st.toast(t("تم إضافة الممثل/ة"), icon="✅")
            st.rerun()


# ---------- البحث بالحرف ----------

def _render_search_and_list(company_id):
    directory = repo.actors_directory()
    hidden_own = repo.actors_owned_by_company(company_id)
    if not directory and not hidden_own:
        st.info(t("لسه مفيش ممثلين في خزانة المواهب"))
        return

    is_ar = st.session_state.get("ui_lang", "ar") == "ar"
    alphabet = _AR_ALPHABET if is_ar else _EN_ALPHABET
    search_key = "actor_search_q"
    letter_key = "actor_letter_pill"
    applied_key = f"{letter_key}_applied"

    selected_letter = st.pills(
        t("قفز بالحرف الأول"), alphabet, key=letter_key,
        selection_mode="single", label_visibility="collapsed",
    )
    # الحرف بيكتب نفسه في خانة البحث (قبل ما الخانة تتبني في نفس الـ run).
    # لو الحرف اتشال، خانة البحث تفضى معاه.
    if selected_letter != st.session_state.get(applied_key):
        st.session_state[search_key] = selected_letter or ""
        st.session_state[applied_key] = selected_letter

    query = st.text_input(
        t("بحث"), key=search_key, label_visibility="collapsed", live=True,
        # live=True: القايمة بتتفلتر مع كل ضغطة حرف فورًا - مش لما تدوس Enter.
        # المالك طلب فلترة فورية للكاستينج، عكس خانات البحث التانية
        # (library_search) اللي بتستنى Enter/فقدان التركيز.
        placeholder=f"🔍 {t('اكتب اسم الممثل أو أول حرف')} — {ltr(len(directory))} {t('ممثل متاح')}",
    )
    shown = [a for a in directory if _matches(query, a)]
    if query:
        st.caption(f"{ltr(len(shown))} {t('من')} {ltr(len(directory))}")
    if not shown:
        st.caption(t("مفيش نتايج — جرّب حرف تاني"))
    for a in shown:
        _actor_row(a)

    shown_hidden = [a for a in hidden_own if _matches(query, a)]
    if shown_hidden:
        st.markdown(f"**{t('بروفايلات فريقك المخفية من البحث')}**")
        for a in shown_hidden:
            _actor_row(a)


def _actor_row(a):
    with st.container(key=f"cf_actor_row_{a['id']}"):
        cols = st.columns([1, 7], vertical_alignment="center")
        with cols[0]:
            img = image_abs_path(a.get("photo_path")) if a.get("photo_path") else None
            if img:
                st.image(img, width=48)
            else:
                st.markdown("🎭")
        with cols[1]:
            bits = [_display_name(a)]
            if a.get("category"):
                bits.append(t(a["category"]))
            if a.get("is_demo"):
                bits.append(f"🧪 {t('تجريبي')}")
            if _is_stale(a):
                bits.append(f"📷 {t('الصورة محتاجة تحديث')}")
            if st.button("  ·  ".join(bits), key=f"actor_pick_{a['id']}", use_container_width=True):
                st.session_state[_SELECTED_KEY] = a["id"]
                st.rerun()


# ---------- البروفايل ----------

def _photo_freshness_text(actor):
    """نص التنبيه لو الصورة ناقصة أو أقدم من 3 شهور، وإلا None."""
    if not actor.get("photo_path"):
        return f"📷 {t('مفيش صورة لسه')}"
    age = _photo_age_days(actor.get("photo_updated_at"))
    if age is None:
        return f"📷 {t('تاريخ الصورة مش معروف — محتاجة تحديث')}"
    if age > _STALE_DAYS:
        return "📷 " + t("آخر تحديث للصورة من {n} شهور — محتاجة تحديث").format(n=ltr(age // 30))
    return None


def _render_profile(actor_id, project_id, company_id, pick_char=None):
    actor = repo.actor_by_id(actor_id)
    if not actor:
        st.warning(t("الملف الشخصي ده مش موجود"))
        st.session_state.pop(_SELECTED_KEY, None)
        return

    if st.button(f"⬅️ {t('العودة لقايمة الممثلين')}", key="actor_back_btn"):
        st.session_state.pop(_SELECTED_KEY, None)
        st.rerun()

    col_photo, col_info = st.columns([1, 3], vertical_alignment="top")
    with col_photo:
        img = image_abs_path(actor.get("photo_path")) if actor.get("photo_path") else None
        if img:
            st.image(img, width=180)
        else:
            st.markdown("### 🎭")
        stale = _photo_freshness_text(actor)
        if stale:
            st.warning(stale)
        elif actor.get("photo_updated_at"):
            st.caption(f"{t('آخر تحديث للصورة')}: {ltr(str(actor['photo_updated_at'])[:10])}")
        if actor.get("is_demo"):
            st.caption(f"🧪 {t('بيانات تجريبية آمنة — مش شخص حقيقي')}")

    with col_info:
        st.markdown(f"## 🎬 {_display_name(actor)}")
        if actor.get("stage_name") and actor.get("stage_name") != actor.get("full_name"):
            st.caption(f"{t('الاسم الحقيقي')}: {actor['full_name']}")
        meta_bits = [t(v) for v in (actor.get("category"), actor.get("gender")) if v]
        if meta_bits:
            st.caption(" · ".join(meta_bits))
        if not actor.get("discoverable"):
            st.caption(f"🙈 {t('مخفي من بحث الكاستينج')}")
        if actor.get("bio"):
            st.write(actor["bio"])

    st.markdown(f"**{t('أعمال سابقة')}**")
    flagged = st.session_state.pop(_VIDEO_WARN_KEY, None)
    if flagged:
        _warn_unrecognised(flagged)
    if actor.get("credits_text"):
        render_credits(videos.credits(actor["credits_text"]), show_unrecognised=True)
    else:
        st.caption(t("غير متوفر"))

    links = [(t("شوريل"), actor.get("link_showreel")),
             (t("إنستجرام / سوشيال ميديا"), actor.get("link_instagram"))]
    links = [(label, url) for label, url in links if url]
    if links or actor.get("link_other"):
        st.markdown(f"**{t('روابط')}**")
        for label, url in links:
            st.markdown(f"- [{label}]({url})")
        for line in str(actor.get("link_other") or "").splitlines():
            if line.strip():
                st.markdown(f"- {line.strip()}")

    st.divider()
    _render_sensitive_section(actor, company_id)
    st.divider()
    _render_casting_section(actor, project_id, pick_char)
    _render_public_share_section(actor, company_id)
    _render_edit_section(actor, company_id)


def _render_sensitive_section(actor, company_id):
    unlocked = repo.actor_unlocked_for_company(actor["id"], company_id)
    always_public = {f.strip() for f in (actor.get("always_public_fields") or "").split(",") if f.strip()}

    def visible(key):
        return unlocked or key in always_public

    st.markdown(f"**{t('بيانات القياس والكاستينج')}**")
    if not unlocked and not always_public:
        st.info(t("البيانات دي بتفضل مخفية لحد ما فريقك يرشّح أو يتعاقد مع الممثل/ة ده لدور في أحد مشاريعك."))
    elif not unlocked:
        st.caption(t("جزء من البيانات دي ظاهر لأن الممثل/ة اختار يبينه للكل — الباقي محتاج ترشيح أول."))

    def field(key, formatter=str):
        label = t(_SENSITIVE_LABELS[key])
        if not visible(key):
            st.markdown(f"- {label}: 🔒 {t('مخفي لحد الترشيح')}")
            return
        raw = actor.get(key)
        st.markdown(f"- {label}: {formatter(raw) if raw not in (None, '') else t('غير متوفر')}")

    def bool_field(key):
        label = t(_SENSITIVE_LABELS[key])
        if not visible(key):
            st.markdown(f"- {label}: 🔒 {t('مخفي لحد الترشيح')}")
            return
        st.markdown(f"- {label}: {t('نعم') if actor.get(key) else t('لا')}")

    def cm(v):
        return f"{ltr(v)} {t('سم')}"

    mc1, mc2 = st.columns(2)
    with mc1:
        field("height_cm", cm)
        field("weight_kg", lambda v: f"{ltr(v)} {t('كجم')}")
        field("chest_cm", cm)
        field("waist_cm", cm)
        field("hips_cm", cm)
        field("shoe_size_eu", ltr)
        field("hair_color")
        field("eye_color")
        field("hobbies")
    with mc2:
        field("contact_phone", ltr)
        field("contact_email", ltr)
        field("agent_name")
        field("agent_contact")
        bool_field("drives_car")
        bool_field("drives_motorcycle")
        bool_field("swims")
        bool_field("smokes")
        field("skills_notes")


def _cast_and_return(actor_id, project_id, char_id, status, note, user):
    """كولباك وضع "اختار لـ...": رشّح/تعاقد، وارجع للشخصية على طول."""
    try:
        repo.cast_actor(actor_id, project_id, char_id, status, note, user)
    except repo.AlreadyCastError as exc:
        st.session_state["_cf_cast_error"] = exc.user_message
        return
    # أول ما حد يتعاقد، الشخصية تاخد الرقم اللي بعده لو مالهاش - عشان تظهر
    # في التفريغ على طول (نفس اللي كان بيحصل من كارت الشخصية)
    if status == "cast" and not (repo.cast_by_character(project_id).get(char_id) or {}).get("cast_number"):
        repo.set_cast_number(project_id, char_id, repo.next_cast_number(project_id))
    st.session_state.pop(_SELECTED_KEY, None)
    close_page("characters")


def _render_casting_section(actor, project_id, pick_char=None):
    actor_id = actor["id"]
    if not project_id:
        st.caption(t("اختار مشروع من الشريط الجانبي عشان ترشّح أو تتعاقد."))
        return
    if pick_char:
        # جاي من كارت شخصية: الزرارين للشخصية دي بس، وبعدهم رجوع لها
        err = st.session_state.pop("_cf_cast_error", None)
        if err:
            st.error(t(err))
        user = st.session_state.get("_auth_user")
        st.markdown(f"**{t('لدور')} {pick_char['name']}**")
        note = st.text_input(t("ملاحظة عن الدور (اختياري)"), key=f"pick_note_{actor_id}")
        b1, b2 = st.columns(2)
        b1.button(f"⭐ {t('رشّح للدور ده')}", key=f"pick_short_{actor_id}", disabled=not _can_write(),
                  use_container_width=True, on_click=_cast_and_return,
                  args=(actor_id, project_id, pick_char["id"], "shortlisted", note, user))
        b2.button(f"✅ {t('تعاقد للدور ده')}", key=f"pick_cast_{actor_id}", disabled=not _can_write(),
                  use_container_width=True, type="primary", on_click=_cast_and_return,
                  args=(actor_id, project_id, pick_char["id"], "cast", note, user))
        return
    st.markdown(f"**{t('الترشيح والتعاقد في المشروع ده')}**")
    for r in repo.castings_of_actor_in_project(actor_id, project_id):
        c1, c2 = st.columns([4, 1], vertical_alignment="center")
        c1.markdown(f"- {r['character_name']} — {t(ACTOR_CASTING_STATUS_LABELS.get(r['status'], r['status']))}"
                    + (f" · {r['role_note']}" if r.get("role_note") else ""))
        if c2.button(t("إلغاء"), key=f"uncast_{r['id']}", disabled=not _can_write(), use_container_width=True):
            repo.remove_casting(project_id, r["id"])
            st.rerun()

    characters = repo.characters_of_project_by_id(project_id)
    if not characters:
        st.caption(t("لسه مفيش شخصيات في المشروع ده. ضيف شخصيات الأول من تبويب الشخصيات."))
        return
    _cast = repo.cast_by_character(project_id)
    char_map = {c["id"]: repo.cast_label(_cast[c["id"]]) if c["id"] in _cast else c["name"]
                for c in characters}
    chosen = st.selectbox(t("اختار شخصية"), list(char_map), format_func=char_map.get,
                          key=f"actor_cast_pick_{actor_id}")
    current = repo.casting_for_character(chosen)
    if current and current["status"] == "cast" and current["actor_id"] != actor_id:
        st.caption(f"{t('الشخصية دي متعاقد لها')}: {current.get('stage_name') or current['full_name']}")
    role_note = st.text_input(t("ملاحظة عن الدور (اختياري)"), key=f"actor_cast_note_{actor_id}")
    b1, b2 = st.columns(2)
    user = st.session_state.get("_auth_user")
    if b1.button(f"⭐ {t('رشّح للدور ده')}", key=f"actor_shortlist_btn_{actor_id}",
                 disabled=not _can_write(), use_container_width=True):
        repo.cast_actor(actor_id, project_id, chosen, "shortlisted", role_note, user)
        st.toast(t("تم ترشيح الممثل/ة للشخصية"), icon="⭐")
        st.rerun()
    if b2.button(f"✅ {t('تعاقد للدور ده')}", key=f"actor_cast_btn_{actor_id}",
                 disabled=not _can_write(), use_container_width=True):
        # guarded_delete بيمسك IntegrityError ويعرض رسالته (AlreadyCastError)
        if guarded_delete(repo.cast_actor, (actor_id, project_id, chosen, "cast", role_note, user),
                          t("معرفش أسجّل التعاقد ده.")):
            st.toast(t("تم تعيين الممثل/ة للشخصية"), icon="✅")
            st.rerun()
    st.caption(t("الترشيح بيفتح لفريقك بيانات القياس والتواصل، ومتسجّل باسمك."))


def _render_edit_section(actor, company_id):
    role = permissions.current_role()
    if not repo.can_edit_actor(actor, company_id, role):
        return
    st.divider()
    with st.expander(f"✏️ {t('تعديل البروفايل')}", expanded=False):
        with st.form(f"edit_actor_{actor['id']}"):
            values, photo = _actor_fields(f"edit_actor_{actor['id']}", actor)
            saved = st.form_submit_button(f"💾 {t('حفظ التعديل')}")
        if saved:
            if not values["full_name"]:
                st.warning(t("اسم الممثل/ة مينفعش يبقى فاضي"))
                return
            repo.update_actor(actor["id"], values, company_id, role)
            _flag_unrecognised(values["credits_text"])
            if photo is not None:
                repo.set_actor_photo(actor["id"], save_uploaded_image(photo, f"actors/{actor['id']}"))
            st.toast(t("تم حفظ التعديل"), icon="💾")
            st.rerun()


# ---------- البروفايل العام (مشاركة على السوشيال ميديا) ----------

def _public_share_url(token):
    """اللينك المطلق اللي بيتشير. صفحة Starlette (‎/p/<token>‎ تحت
    CIMAFAST_BOARD_URL) لو موجودة — دي اللي فيها Open Graph فالمعاينة بتطلع
    بالاسم والصورة. من غيرها (تشغيلة من غير الواجهة الجديدة) ‎?profile=‎ هنا."""
    headers = st.context.headers
    host = headers.get("host", "")
    proto = headers.get("x-forwarded-proto") or ("http" if host.startswith(("127.", "localhost")) else "https")
    board = os.environ.get("CIMAFAST_BOARD_URL")
    if board:
        return f"{proto}://{host}{board.rstrip('/')}/p/{token}"
    base = (st.get_option("server.baseUrlPath") or "").strip("/")
    return f"{proto}://{host}/{base + '/' if base else ''}?profile={token}"


def _render_public_share_section(actor, company_id):
    """النشر/الإيقاف لمين يقدر يعدّل البروفايل بس. الافتراضي: مش منشور."""
    role = permissions.current_role()
    if not repo.can_edit_actor(actor, company_id, role):
        return
    st.divider()
    st.markdown(f"**🔗 {t('البروفايل العام')}**")
    token = actor.get("public_share_token")
    if not token:
        st.caption(t("البروفايل مش منشور. لو نشرته، أي حد معاه اللينك يقدر يشوف الاسم والصورة والبيو والأعمال — من غير أي بيانات تواصل."))
        if st.button(f"🌐 {t('انشر البروفايل العام')}", key=f"actor_share_on_{actor['id']}"):
            repo.share_actor_publicly(actor["id"], company_id, role)
            st.toast(t("تم نشر البروفايل العام"), icon="🌐")
            st.rerun()
        st.caption(t("اللي بيظهر: الاسم المعروف، الصورة، البيو، الأعمال، التصنيف، الشوريل وإنستجرام — والطول/الشعر/العين/المهارات لو اخترتها في «بيانات تظهر للكل». عمره ما بيظهر: التليفون، الإيميل، الوكيل، مقاسات الجسم، الهوايات، التدخين، الروابط التانية، ولا أي ترشيحات."))
        return

    url = _public_share_url(token)
    st.success(t("البروفايل منشور — أي حد معاه اللينك ده يقدر يشوفه من غير تسجيل دخول."))
    st.code(url, language=None)          # فيه زرار نسخ جاهز
    st.caption(t("مشاركة على"))
    name = _display_name(actor)
    cols = st.columns(6)
    cols[0].link_button(t("افتح الصفحة العامة"), url, use_container_width=True)
    for col, (label, href) in zip(cols[1:], public_profile.share_links(url, name)):
        col.link_button(label, href, use_container_width=True)
    b1, b2 = st.columns(2)
    if b1.button(f"🔄 {t('لينك جديد')}", key=f"actor_share_new_{actor['id']}",
                 help=t("اللينك الجديد بيلغي القديم فورًا."), use_container_width=True):
        repo.share_actor_publicly(actor["id"], company_id, role)
        st.rerun()
    if b2.button(f"⛔ {t('إيقاف المشاركة')}", key=f"actor_share_off_{actor['id']}", use_container_width=True):
        repo.stop_sharing_actor(actor["id"], company_id, role)
        st.toast(t("تم إيقاف المشاركة — اللينك القديم مابقاش شغال"), icon="⛔")
        st.rerun()
    st.caption(t("اللي بيظهر: الاسم المعروف، الصورة، البيو، الأعمال، التصنيف، الشوريل وإنستجرام — والطول/الشعر/العين/المهارات لو اخترتها في «بيانات تظهر للكل». عمره ما بيظهر: التليفون، الإيميل، الوكيل، مقاسات الجسم، الهوايات، التدخين، الروابط التانية، ولا أي ترشيحات."))


def render_public_profile(token):
    """‎?profile=<token>‎ من غير دخول (app.py بيناديها قبل بوابة الدخول).
    بيرسم نفس HTML الصفحة العامة (public_profile.render_body) — مفيش أي قراءة
    تانية من صف الممثل/ة هنا غير الصورة، ودي بتتقري من public_profile.photo_file."""
    lang = "en" if st.query_params.get("lang") == "en" else st.session_state.get("ui_lang", "ar")
    actor = repo.actor_by_public_token(token)
    if not actor:
        st.html(f"<style>{public_profile.CSS}</style>"
                f'<div class="cf-pp"><div class="cf-pp__card"><h1>'
                f'{public_profile._e(public_profile._tr("البروفايل ده مش متاح.", lang))}</h1></div></div>')
        return
    view = public_profile.public_view(actor)
    photo_url = None
    path = public_profile.photo_file(actor)
    if path:
        with open(path, "rb") as fh:
            photo_url = (f"data:{public_profile.photo_media_type(path)};base64,"
                         + base64.b64encode(fh.read()).decode())
    switch = f"?profile={token}&lang={'ar' if lang == 'en' else 'en'}"
    st.html(f"<style>{public_profile.CSS}</style>"
            + public_profile.render_body(view, lang, photo_url=photo_url, share_url=_public_share_url(token),
                                         lang_switch_url=switch, copy_button=False, embed_videos=False))
    # st.html بيشيل iframe — الفيديوهات هنا (نفس روابط التضمين المبنية في videos.py)
    if any(c["videos"] for c in view["credits"]):
        render_credits([c for c in view["credits"] if c["videos"]])


# ---------- فيديوهات الأعمال السابقة ----------

def _flag_unrecognised(credits_text):
    bad = videos.unrecognised(credits_text)
    if bad:
        st.session_state[_VIDEO_WARN_KEY] = bad


def _warn_unrecognised(urls):
    st.warning(t("اللينكات دي اتحفظت كنص بس ومش هتتعرض كفيديو (ولا هتظهر في البروفايل العام) — استخدم لينك يوتيوب أو فيميو أو ديلي موشن أو فيسبوك أو ملف ‎.mp4‎ مباشر:")
               + "\n\n" + "\n".join(f"- {ltr(u)}" for u in urls))


def render_credits(items, show_unrecognised=False):
    """سطور الأعمال وتحت كل سطر فيديوهاته. المشغّل iframe لرابط اتبنى من رقم
    الفيديو بس (videos.parse) — مفيش HTML ولا لينك من اليوزر بيدخل الصفحة."""
    import streamlit.components.v1 as components
    for c in items:
        st.markdown(f"- {c['text'] or '🎬'}")
        for v in c["videos"]:
            if v["kind"] == "video":
                st.video(v["embed_url"])
            else:
                components.iframe(v["embed_url"], height=340)
        if show_unrecognised and c.get("unrecognised"):
            st.caption("⚠️ " + t("لينك مش متعرف عليه كفيديو") + ": " + " · ".join(ltr(u) for u in c["unrecognised"]))


# ---------- الكاستينج من كارت الشخصية نفسها ----------
# نفس repo.cast_actor اللي بروفايل الممثل/ة بيستعمله - المنطق مكانه واحد،
# بس الاختيار بقى متاح من المكان اللي المنتج بيدوّر فيه فعلًا: الشخصية.

def _open_actor_profile(actor_id):
    st.session_state[_SELECTED_KEY] = actor_id
    open_page("actors")


def _pick_from_library(char_id):
    st.session_state.pop(_SELECTED_KEY, None)
    open_page("actors", pick=char_id)


def _fmt_date(value):
    return value or "—"


def render_character_casting(project_id, company_id, ch, cast_entry):
    """ch: صف الشخصية. cast_entry: صفها من repo.cast_by_character (فيه
    الرقم والممثل/ة والمرشحين)."""
    char_id = ch["id"]
    writable = _can_write()
    user = st.session_state.get("_auth_user")
    actor = cast_entry.get("actor") if cast_entry else None
    shortlist = cast_entry.get("shortlist", []) if cast_entry else []

    st.markdown(f"**🎬 {t('الممثل/ة والكاستينج')}**")

    # الممثل/ة المتعاقد + المرشحين، كل واحد بزرار يفتح بروفايله أو يشيله
    people = ([(actor, "cast")] if actor else []) + [(p, "shortlisted") for p in shortlist]
    for person, status in people:
        c_img, c_name, c_open, c_rm = st.columns([1, 5, 2, 2], vertical_alignment="center")
        img = image_abs_path(person["photo_path"]) if person.get("photo_path") else None
        if img:
            c_img.image(img, width=48)
        else:
            c_img.markdown("🎭")
        badge = "✅" if status == "cast" else "⭐"
        c_name.markdown(f"{badge} **{person['name']}** — {t(ACTOR_CASTING_STATUS_LABELS[status])}"
                        + (f" · {person['role_note']}" if person.get("role_note") else ""))
        # بيودّي للبروفايل على طول (تبويب الممثلين) بدل رسالة "روح افتحه"
        c_open.button(t("البروفايل"), key=f"chcast_open_{char_id}_{person['casting_id']}",
                      use_container_width=True, on_click=_open_actor_profile, args=(person["actor_id"],))
        if status == "shortlisted" and not actor:
            if c_rm.button(f"✅ {t('تعاقد')}", key=f"chcast_promote_{char_id}_{person['casting_id']}",
                           disabled=not writable, use_container_width=True):
                if guarded_delete(repo.cast_actor, (person["actor_id"], project_id, char_id, "cast", "", user),
                                  t("معرفش أسجّل التعاقد ده.")):
                    st.rerun()
        elif c_rm.button(t("إلغاء"), key=f"chcast_rm_{char_id}_{person['casting_id']}",
                         disabled=not writable, use_container_width=True):
            repo.remove_casting(project_id, person["casting_id"])
            st.rerun()
    if not people:
        st.caption(t("لسه مفيش ممثل/ة للدور ده — اختار من خزانة المواهب أو ضيف حد جديد تحت."))

    # رقم الكاست - ثابت، وبيظهر في التفريغ والجدول والكول شيت
    n1, n2 = st.columns([2, 3], vertical_alignment="bottom")
    number = n1.number_input(t("رقم الممثل في التفريغ"), min_value=0, max_value=999, step=1,
                             value=int(cast_entry.get("cast_number") or 0) if cast_entry else 0,
                             key=f"chcast_num_{char_id}", help=t("0 = من غير رقم"),
                             disabled=not writable)
    if number != int((cast_entry or {}).get("cast_number") or 0):
        if guarded_delete(repo.set_cast_number, (project_id, char_id, number or None),
                          t("معرفش أحفظ الرقم ده.")):
            st.rerun()

    # التتبع: الدور ده (وممثله) فين في الجدول
    tr_ = repo.character_tracking(project_id, char_id)
    lines = [f"🎞️ {ltr(tr_['scene_count'])} {t('مشهد في السكريبت')}"]
    if tr_["work_days"]:
        lines.append(f"📅 {ltr(tr_['work_days'])} {t('يوم تصوير')} · {ltr(tr_['hold_days'])} {t('يوم انتظار')}"
                     f" · {t('من يوم')} {ltr(tr_['first_day'])} ({_fmt_date(tr_['first_date'])})"
                     f" {t('لـ يوم')} {ltr(tr_['last_day'])} ({_fmt_date(tr_['last_date'])})")
        if tr_["scheduled_scenes"] < tr_["scene_count"]:
            lines.append(f"⚠️ {ltr(tr_['scene_count'] - tr_['scheduled_scenes'])} {t('مشهد لسه مش متجدول')}")
    elif tr_["scene_count"]:
        lines.append(f"📅 {t('لسه ولا مشهد من مشاهده متجدول في جدول التصوير')}")
    n2.caption("  \n".join(lines))
    if tr_["days"]:
        with st.popover(f"📅 {t('أيام التصوير')}"):
            for d in tr_["days"]:
                st.markdown(f"- {t('يوم')} {ltr(d['day_number'])} · {_fmt_date(d['date'])} · `{d['code']}`")

    # اختيار ممثل/ة: من مكتبة الممثلين نفسها (المالك 2026-09-24) - بتتفتح
    # في وضع "بتختار لدور X"، وبعد الترشيح/التعاقد بترجع هنا لوحدها
    if writable:
        st.button(f"🔎 {t('اختار من مكتبة الممثلين')}", key=f"chcast_lib_{char_id}", type="primary",
                  on_click=_pick_from_library, args=(char_id,))


def _render_project_cast(project_id):
    """كل دور في المشروع: رقمه، والممثل/ة المتعاقد أو المرشحين، ومشاهده
    وأيام تصويره. التعاقد نفسه من كارت الشخصية أو بروفايل الممثل/ة."""
    import pandas as pd
    cast = repo.project_cast(project_id)
    st.markdown(f"#### {t('ممثلين المشروع')}")
    if not cast:
        st.info(t("لسه مفيش شخصيات في المشروع. ضيف الشخصيات (أو استورد السيناريو) الأول، وبعدها عيّن ممثل/ة لكل دور."))
        return
    days = {r["character_id"]: r for r in repo.day_out_of_days(project_id)["rows"]}
    done = sum(1 for c in cast if c["actor"])
    st.caption(f"🎬 {ltr(done)} {t('من')} {ltr(len(cast))} {t('دور اتعاقد له ممثل/ة')}")
    rows = []
    for c in cast:
        d = days.get(c["id"]) or {}
        if c["actor"]:
            who = f"✅ {c['actor']['name']}"
        elif c["shortlist"]:
            who = "⭐ " + "، ".join(p["name"] for p in c["shortlist"])
        else:
            who = "—"
        rows.append({
            t("رقم"): c["cast_number"] or "",
            t("الشخصية"): c["name"],
            t("الممثل/ة"): who,
            t("مشاهد"): c["scene_count"],
            t("أيام تصوير"): d.get("work_days") or "",
        })
    df = pd.DataFrame(rows)
    if st.session_state.get("ui_lang", "ar") == "ar":
        df = df[df.columns[::-1]]
    st.dataframe(df, hide_index=True, use_container_width=True,
                 height=min(38 + 35 * len(df), 360))
    st.caption(t("التعيين والترشيح من كارت الشخصية في تبويب «الشخصيات»، أو من بروفايل الممثل/ة تحت."))
