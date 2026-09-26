"""📍 مكتبة مواقع التصوير (المالك 2026-09-24).

صفحة لوحدها بتتفتح من الشريط الجانبي (تصفّح وإضافة وسكاوتنج)، أو من كارت
مكان في المشروع (?pick=<location_id>): "بتدوّر على موقع لـ شقة نادية"،
والمواقع مترتبة بالأنسب (بتغطي كام ديكور من اللي المكان محتاجه)، وبعد الترشيح
أو الحجز بترجع لتبويب الأماكن لوحدك.

الموقع بتاع مساحة العمل اللي ضافته (شغل السكاوتنج بتاع فريقك)، وممكن
ينتشر للمنصة. العنوان وتليفون صاحبه والسعر بيتفتحوا لصاحبه أو بعد الترشيح.
"""

import pandas as pd
import streamlit as st

import permissions
import repo
from i18n import t
import os
import re

from ui import IMAGE_TYPES, close_page, delete_image_file, image_abs_path, ltr, multiselect, save_uploaded_image, thumb_uri

_SELECTED = "_cf_selected_venue"
# اسم الملف لو معناه حاجة (kitchen.jpg ← kitchen، مطبخ.jpg ← مطبخ)؛ أسامي الكاميرا
# والواتساب (IMG_1234، WhatsApp Image …) مالهاش معنى فبتبقى «مساحة ٣»
_CAMERA_PREFIX = re.compile(r"(?i)^(img|dsc|dscn|pxl|photo|image|whatsapp|screenshot|snapchat|signal|mvimg)\b")


def _space_name(filename, n):
    stem = os.path.splitext(os.path.basename(filename or ""))[0]
    clean = re.sub(r"[_\-.]+", " ", stem).strip()
    if not clean or re.fullmatch(r"[\d\s]+", clean) or _CAMERA_PREFIX.match(clean):
        return f"{t('مساحة')} {n}"
    return clean[:60]


def _add_space_photos(venue_id, company_id, files, start_n):
    """كل صورة = مساحة جديدة بصورتها (لحد repo.MAX_SPACE_PHOTOS في المرة)."""
    files = list(files or [])[:repo.MAX_SPACE_PHOTOS]
    items = [(_space_name(f.name, start_n + i), save_uploaded_image(f, f"venues/{venue_id}/spaces"))
             for i, f in enumerate(files)]
    return repo.add_venue_spaces_from_photos(venue_id, company_id, items)


def _photos_uploader(key, help_text=None):
    files = st.file_uploader(f"📷 {t('صور المساحات — لحد 20 صورة، كل صورة = ديكور أو أوضة')}", type=IMAGE_TYPES,
                             accept_multiple_files=True, key=key, help=help_text)
    if files and len(files) > repo.MAX_SPACE_PHOTOS:
        st.warning(f"{t('اخترت')} {ltr(len(files))} {t('صورة — هيتضاف أول 20 بس. ارفع الباقي في مرة تانية.')}")
    return files


def _can_write():
    role = permissions.current_role()
    return role is None or permissions.can(role, "edit")


def _is_ar():
    return st.session_state.get("ui_lang", "ar") == "ar"


def render(project_id=None, company_id=None, pick=None):
    st.subheader(f"📍 {t('مكتبة مواقع التصوير')}")
    loc = None
    if pick and project_id:
        try:
            loc = next((l for l in repo.locations_of_project(project_id) if l["id"] == int(pick)), None)
        except (TypeError, ValueError):
            loc = None
    if loc:
        needs = [n for n, _ in repo.location_needs(project_id, loc["id"])]
        c1, c2 = st.columns([3, 1], vertical_alignment="center")
        c1.info(f"🎯 {t('بتدوّر على موقع لـ')} **{loc['name']}**"
                + (f" — {t('محتاج')}: {'، '.join(needs)}" if needs else ""))
        c2.button(f"↩ {t('رجوع للأماكن')}", key="vpick_back", use_container_width=True,
                  on_click=close_page, args=("locations",))

    selected = st.session_state.get(_SELECTED)
    if selected:
        _profile(selected, project_id, company_id, loc)
        return

    q = st.text_input(t("بحث"), key="venue_q", label_visibility="collapsed",
                      placeholder=f"🔎 {t('اكتب اللي محتاجه: أوضة نوم، نادي، محطة مترو، كافيه...')}")
    if loc:
        venues = repo.rank_venues_for(project_id, loc["id"], company_id)
        if q:
            keep = {v["id"] for v in repo.venues_visible_to(company_id, q)}
            venues = [v for v in venues if v["id"] in keep]
    else:
        venues = repo.venues_visible_to(company_id, q)
    if not venues:
        st.info(t("لسه مفيش مواقع في المكتبة — ضيف أول موقع من «📸 موقع جديد» تحت.") if not q
                else t("مفيش مواقع بالبحث ده — جرّب كلمة تانية."))
    for v in venues:
        _row(v, company_id)
    st.divider()
    _add_form(company_id)


def _row(v, company_id):
    with st.container(border=True, key=f"venue_row_{v['id']}"):
        c1, c2 = st.columns([1, 5], vertical_alignment="center")
        img = image_abs_path(v.get("photo_path")) if v.get("photo_path") else None
        if img:
            c1.image(img, width=72)
        else:
            c1.markdown("### 🏠")
        bits = [t(v["venue_type"]) if v.get("venue_type") else None, v.get("city"),
                f"{ltr(len(v['spaces']))} {t('مساحة')}"]
        head = f"**{v['name']}**  \n" + " · ".join(b for b in bits if b)
        if "covered" in v and v["total"]:
            mark = "✅" if len(v["covered"]) == v["total"] else ("🟡" if v["covered"] else "⚪")
            head += f"  \n{mark} {t('بيغطي')} {ltr(len(v['covered']))} {t('من')} {ltr(v['total'])}"
            if v["covered"]:
                head += f" ({'، '.join(v['covered'])})"
        if v.get("owner_company_id") != company_id:
            head += f"  \n🌐 {t('منشور على المنصة')}"
        c2.markdown(head)
        if c2.button(t("افتح"), key=f"venue_open_{v['id']}"):
            st.session_state[_SELECTED] = v["id"]
            st.rerun()


def _profile(venue_id, project_id, company_id, loc):
    v = repo.venue_for(venue_id, company_id)
    if not v:
        st.session_state.pop(_SELECTED, None)
        st.warning(t("الموقع ده مش متاح"))
        return
    if st.button(f"⬅️ {t('رجوع لقايمة المواقع')}", key="venue_back"):
        st.session_state.pop(_SELECTED, None)
        st.rerun()
    shown = repo.public_venue(v, company_id)
    c1, c2 = st.columns([1, 2], vertical_alignment="top")
    img = image_abs_path(v.get("photo_path")) if v.get("photo_path") else None
    if img:
        c1.image(img, use_container_width=True)
        if v.get("photo_updated_at"):
            c1.caption(f"📷 {t('آخر تحديث للصورة')}: {ltr(str(v['photo_updated_at'])[:10])}")
    else:
        c1.markdown("## 🏠")
    with c2:
        st.markdown(f"## {v['name']}")
        st.caption(" · ".join(x for x in (t(v["venue_type"]) if v.get("venue_type") else None,
                                           v.get("city"), v.get("area")) if x))
        if v.get("description"):
            st.write(v["description"])
        if v.get("maps_url"):
            st.link_button(f"🗺️ {t('الموقع على الخريطة')}", v["maps_url"])
        practical = [(t("الكهربا"), v.get("power")), (t("الركنة"), v.get("parking")),
                     (t("الدوشة"), v.get("noise")), (t("أقصى طاقم"), v.get("max_crew")),
                     (t("التصاريح"), v.get("permits"))]
        lines = [f"- **{k}:** {val}" for k, val in practical if val]
        if lines:
            st.markdown("\n".join(lines))
        if repo.venue_unlocked(v["id"], company_id):
            sens = [(t("العنوان"), shown.get("address")), (t("صاحب المكان"), shown.get("contact_name")),
                    (t("التليفون"), shown.get("contact_phone")),
                    (t("السعر في اليوم"), f"{shown['price_per_day']:,.0f}" if shown.get("price_per_day") else None)]
            got = [f"- **{k}:** {val}" for k, val in sens if val]
            if got:
                st.markdown("\n".join(got))
        else:
            st.caption(f"🔒 {t('العنوان والتواصل والسعر بيبانوا بعد ما ترشّح الموقع لمكان في مشروعك.')}")

    st.markdown(f"#### {t('المساحات اللي جواه')}")
    if v["spaces"]:
        with_photos = any(sp.get("photo_path") for sp in v["spaces"])
        df = pd.DataFrame([dict(({t("الصورة"): thumb_uri(sp.get("photo_path"))} if with_photos else {}),
                                **{t("المساحة"): sp["name"], t("النوع"): t(sp["space_type"]) if sp["space_type"] else "",
                                   t("ينفع كـ"): sp["suitable_for"] or "", t("د/خ"): sp["int_ext"] or ""})
                           for sp in v["spaces"]])
        if _is_ar():
            df = df[df.columns[::-1]]
        st.dataframe(df, hide_index=True, use_container_width=True,
                     row_height=70 if with_photos else None,
                     column_config={t("الصورة"): st.column_config.ImageColumn(t("الصورة"), width="small")})
    else:
        st.caption(t("لسه مفيش مساحات متسجلة للموقع ده."))

    if loc and project_id:
        _pick_actions(v, project_id, loc)
    if v.get("owner_company_id") == company_id and _can_write():
        _edit(v, company_id)


def _book_and_return(project_id, location_id, venue_id, status, user):
    """كولباك وضع "اختار لـ...": رشّح/احجز، وارجع لتبويب الأماكن على طول."""
    try:
        repo.book_venue(project_id, location_id, venue_id, status, "", user)
    except repo.AlreadyBookedError as exc:
        st.session_state["_cf_book_error"] = exc.user_message
        return
    st.session_state.pop(_SELECTED, None)
    close_page("locations")


def _pick_actions(v, project_id, loc):
    err = st.session_state.pop("_cf_book_error", None)
    if err:
        st.error(t(err))
    user = st.session_state.get("_auth_user")
    st.markdown(f"**{t('لـ')} {loc['name']}**")
    b1, b2 = st.columns(2)
    b1.button(f"⭐ {t('رشّح للمكان ده')}", key=f"vp_short_{v['id']}", use_container_width=True,
              disabled=not _can_write(), on_click=_book_and_return,
              args=(project_id, loc["id"], v["id"], "shortlisted", user))
    b2.button(f"✅ {t('احجزه للمكان ده')}", key=f"vp_book_{v['id']}", use_container_width=True, type="primary",
              disabled=not _can_write(), on_click=_book_and_return,
              args=(project_id, loc["id"], v["id"], "booked", user))


def _fields(prefix, v=None):
    v = v or {}
    c1, c2, c3 = st.columns(3)
    name = c1.text_input(t("اسم الموقع"), value=v.get("name") or "", key=f"{prefix}_name",
                         placeholder=t("مثال: فيلا المعادي"))
    vtype = c2.selectbox(t("النوع"), repo.VENUE_TYPES, format_func=t, key=f"{prefix}_type",
                         index=repo.VENUE_TYPES.index(v["venue_type"]) if v.get("venue_type") in repo.VENUE_TYPES else 0)
    city = c3.text_input(t("المدينة"), value=v.get("city") or "", key=f"{prefix}_city", placeholder=t("القاهرة"))
    c4, c5 = st.columns(2)
    area = c4.text_input(t("المنطقة"), value=v.get("area") or "", key=f"{prefix}_area")
    maps = c5.text_input(t("رابط الخريطة"), value=v.get("maps_url") or "", key=f"{prefix}_maps",
                         placeholder=t("الصق رابط Google Maps"))
    desc = st.text_area(t("وصف"), value=v.get("description") or "", key=f"{prefix}_desc", height=80)
    with st.expander(t("معلومات عملية وتواصل (اختياري)")):
        d1, d2, d3 = st.columns(3)
        power = d1.text_input(t("الكهربا"), value=v.get("power") or "", key=f"{prefix}_power",
                              placeholder=t("كهربا المكان / محتاج مولد"))
        parking = d2.text_input(t("الركنة"), value=v.get("parking") or "", key=f"{prefix}_parking")
        noise = d3.text_input(t("الدوشة"), value=v.get("noise") or "", key=f"{prefix}_noise")
        e1, e2 = st.columns(2)
        crew = e1.number_input(t("أقصى طاقم"), min_value=0, step=5, value=int(v.get("max_crew") or 0),
                               key=f"{prefix}_crew")
        permits = e2.text_input(t("التصاريح"), value=v.get("permits") or "", key=f"{prefix}_permits")
        st.caption(f"🔒 {t('الخانات دي بتبان لفريقك بس، وللي يرشّح الموقع بعد كده:')}")
        f1, f2, f3, f4 = st.columns(4)
        address = f1.text_input(t("العنوان"), value=v.get("address") or "", key=f"{prefix}_address")
        cname = f2.text_input(t("صاحب المكان"), value=v.get("contact_name") or "", key=f"{prefix}_cname")
        phone = f3.text_input(t("التليفون"), value=v.get("contact_phone") or "", key=f"{prefix}_phone")
        price = f4.number_input(t("السعر في اليوم"), min_value=0, step=500, value=int(v.get("price_per_day") or 0),
                                key=f"{prefix}_price")
    return {"name": name, "venue_type": vtype, "city": city, "area": area, "maps_url": maps, "description": desc,
            "power": power, "parking": parking, "noise": noise, "max_crew": crew or None, "permits": permits,
            "address": address, "contact_name": cname, "contact_phone": phone, "price_per_day": price or None}


def _add_form(company_id):
    with st.expander(f"📸 {t('موقع جديد (سكاوتنج)')}", expanded=False):
        st.caption(t("من الموبايل: صوّر المكان، اكتب اسمه ونوعه، واختار المساحات اللي جواه — والموقع بيبقى "
                     "في مكتبة فريقك على طول."))
        with st.form("venue_add", clear_on_submit=True):
            values = _fields("vnew")
            photo = st.file_uploader(t("صورة الموقع"), type=IMAGE_TYPES, key="vnew_photo")
            space_photos = _photos_uploader("vnew_space_photos")
            spaces = multiselect(t("أو اختار المساحات اللي جواه من غير صور"), repo.SPACE_TYPES, format_func=t,
                                 key="vnew_spaces")
            go = st.form_submit_button(f"➕ {t('إضافة الموقع')}", type="primary", disabled=not _can_write())
        if go:
            if not values["name"].strip():
                st.warning(t("اسم الموقع مطلوب"))
                return
            vid = repo.add_venue(values, company_id, st.session_state.get("_auth_user"))
            if photo is not None:
                repo.set_venue_photo(vid, company_id, save_uploaded_image(photo, f"venues/{vid}"))
            if spaces:
                repo.save_venue_spaces(vid, company_id, [{"name": s, "space_type": s} for s in spaces])
            if space_photos:
                _add_space_photos(vid, company_id, space_photos, len(spaces or []) + 1)
            st.session_state[_SELECTED] = vid
            st.toast(t("اتضاف الموقع للمكتبة"), icon="📍")
            st.rerun()


def _edit(v, company_id):
    st.divider()
    with st.expander(f"✏️ {t('تعديل الموقع ومساحاته')}"):
        with st.form(f"venue_edit_{v['id']}"):
            values = _fields(f"vedit_{v['id']}", v)
            publish = st.checkbox(t("انشره على المنصة (يبان لكل الفرق — من غير العنوان والتواصل والسعر)"),
                                  value=bool(v.get("discoverable")), key=f"vpub_{v['id']}")
            photo = st.file_uploader(t("صورة جديدة"), type=IMAGE_TYPES, key=f"vphoto_{v['id']}")
            save = st.form_submit_button(f"💾 {t('حفظ')}", type="primary")
        if save:
            repo.update_venue(v["id"], values, company_id, discoverable=publish)
            if photo is not None:
                repo.set_venue_photo(v["id"], company_id, save_uploaded_image(photo, f"venues/{v['id']}"))
            st.rerun()
        # 📷 صور كتير مرة واحدة: كل صورة بتبقى صف جديد في الجدول بمعاينتها، وتكمّل بياناته
        st.markdown(f"**{t('المساحات (الديكورات والأوض)')}**")
        nonce = st.session_state.get(f"_vsp_nonce_{v['id']}", 0)
        files = _photos_uploader(f"vsp_up_{v['id']}_{nonce}")
        if files and st.button(f"➕ {t('ضيف')} {ltr(min(len(files), repo.MAX_SPACE_PHOTOS))} {t('مساحة من الصور')}",
                               key=f"vsp_add_{v['id']}", type="primary"):
            n = _add_space_photos(v["id"], company_id, files, len(v["spaces"]) + 1)
            st.session_state[f"_vsp_nonce_{v['id']}"] = nonce + 1
            st.toast(f"📷 {t('اتضافت')} {n} {t('مساحة — كمّل بياناتها في الجدول')}")
            st.rerun()
        photo_col = t("الصورة")
        cols = {"name": t("المساحة"), "space_type": t("النوع"), "suitable_for": t("ينفع كـ"), "int_ext": t("د/خ"),
                "notes": t("ملاحظات")}
        df = pd.DataFrame([dict({"_id": sp["id"], photo_col: thumb_uri(sp.get("photo_path"))},
                                **{c: sp[k] for k, c in cols.items()}) for sp in v["spaces"]],
                          columns=["_id", photo_col] + list(cols.values()))
        # الخانات الفاضية كانت بتتكتب «None» في الجدول
        df[list(cols.values())] = df[list(cols.values())].astype(object).where(df[list(cols.values())].notna(), "")
        df[photo_col] = df[photo_col].astype(object).where(df[photo_col].notna(), "")
        order = [photo_col] + list(cols.values())
        edited = st.data_editor(
            df, key=f"vspaces_{v['id']}", num_rows="dynamic", hide_index=True, use_container_width=True,
            column_order=order[::-1] if _is_ar() else order, disabled=[photo_col],
            row_height=70 if any(sp.get("photo_path") for sp in v["spaces"]) else None,
            column_config={photo_col: st.column_config.ImageColumn(photo_col, width="small",
                                                                  help=t("صورة واحدة لكل مساحة — تتغيّر من تحت الجدول")),
                           cols["name"]: st.column_config.TextColumn(required=True),
                           cols["space_type"]: st.column_config.SelectboxColumn(options=repo.SPACE_TYPES),
                           cols["suitable_for"]: st.column_config.TextColumn(
                               help=t("المساحة دي تنفع تمثّل إيه؟ مثلًا: أوضة ولاد، عيادة، مكتب محامي")),
                           cols["int_ext"]: st.column_config.SelectboxColumn(options=["INT", "EXT", "INT/EXT"])})
        if st.button(f"💾 {t('حفظ المساحات')}", key=f"vspaces_save_{v['id']}"):
            back = {c: k for k, c in cols.items()}
            rows = [dict({"_id": r["_id"]}, **{back[c]: (r[c] if isinstance(r[c], str) else None)
                                                for c in edited.columns if c in back})
                    for _, r in edited.iterrows()]
            repo.save_venue_spaces(v["id"], company_id, rows)
            st.rerun()
        _replace_photo(v, company_id)
        if st.button(f"🗑️ {t('امسح الموقع من المكتبة')}", key=f"vdel_{v['id']}"):
            repo.delete_venue(v["id"], company_id)
            st.session_state.pop(_SELECTED, None)
            st.rerun()


def _replace_photo(v, company_id):
    """صورة واحدة لكل مساحة: تغيّرها (الجديدة بتحل محل القديمة)."""
    if not v["spaces"]:
        return
    names = {sp["id"]: sp["name"] for sp in v["spaces"]}
    c1, c2, c3 = st.columns([2, 3, 1], vertical_alignment="bottom")
    sid = c1.selectbox(t("غيّر صورة مساحة"), list(names), format_func=names.get, key=f"vsp_pick_{v['id']}")
    nonce = st.session_state.get(f"_vsp_rep_{v['id']}", 0)
    photo = c2.file_uploader(t("الصورة الجديدة"), type=IMAGE_TYPES, key=f"vsp_rep_up_{v['id']}_{nonce}")
    if c3.button(f"📷 {t('غيّر')}", key=f"vsp_rep_go_{v['id']}", disabled=photo is None, use_container_width=True):
        old = repo.set_space_photo(v["id"], company_id, sid, save_uploaded_image(photo, f"venues/{v['id']}/spaces"))
        if old:
            delete_image_file(old)
        st.session_state[f"_vsp_rep_{v['id']}"] = nonce + 1
        st.rerun()
