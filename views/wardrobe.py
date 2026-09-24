"""تبويب الملابس (P10) — طلب المالك 2026-09-24: "قايمة الملابس بتحدد كل
شخصية هتلبس إيه في كل المشاهد، وأتحكم بالكامل في كل الملابس لكل الشخصيات في
كل حالاتها".

الغيار = المظهر (character_looks) برقمه: غيار 1، 2، 3... مفهوم واحد، فاللقطات
اللي بتختار مظهر أصلًا مابتتلخبطش. التبويب ليه تلات أجزاء:
  1) لوحة الغيارات: الشخصيات × المشاهد، وكل خانة = الغيار. التعديل بشخصية
     شخصية (جدول بمشاهدها وخانة غيار لكل مشهد).
  2) الغيارات والقطع: غيارات كل شخصية وقطع كل غيار بتفاصيلها، ومقاسات
     الممثل/ة المتعاقد لو متاحة.
  3) قايمة القطع: كل قطع المشروع، التكلفة، اللي لسه مش جاهز، وكشف Excel.
بيشتغل من غير سيناريو كمان: الغيارات والقطع بتتجهز على الشخصيات من دلوقتي،
واللوحة بتتملى أول ما يبقى فيه مشاهد.
"""

import pandas as pd
import streamlit as st

import permissions
import repo
from database import scene_label
from i18n import t, tr
from ui import ltr

_NONE = "—"
# ألوان خفيفة لأرقام الغيارات في اللوحة (بتلف لو الغيارات أكتر)
_CHANGE_COLORS = ["#2b3f8f", "#6b3a8a", "#1f6f5c", "#8a5a1f", "#7a2f3f", "#35607a", "#5a6b2a", "#6a4a2a"]


def _can_edit():
    role = permissions.current_role()
    return role is None or permissions.can(role, "edit")


def _is_ar():
    return st.session_state.get("ui_lang", "ar") == "ar"


def _rtl(columns):
    """الجداول بترسم شمال ← يمين دايمًا: في العربي بنقلب ترتيب العواميد عشان
    أول عمود (المشهد / القطعة) يقف على اليمين، زي جدول المشاهد."""
    return columns[::-1] if _is_ar() else columns


def _money(v):
    return f"{v:,.0f}" if v else "0"


def _char_label(c):
    return (f"#{c['cast_number']} " if c.get("cast_number") else "") + c["name"]


def render(project, project_id, company_id):
    st.subheader(tr("tab_wardrobe"))
    st.caption(tr("sub_wardrobe"))

    cast = repo.project_cast(project_id)
    if not cast:
        st.info(t("لسه مفيش شخصيات في المشروع. ضيف الشخصيات من تبويب «الشخصيات» أو استورد السيناريو من "
                  "«إضافة سيناريو»، وبعدها جهّز غيارات كل شخصية هنا."))
        return
    if repo.ensure_change_numbers(project_id):
        st.rerun()

    changes = repo.wardrobe_changes(project_id)
    missing = repo.scenes_missing_change(project_id)
    items_total = sum(c["items"] for c in changes)
    cost_total = sum(c["cost"] or 0 for c in changes)
    not_ready = sum(c["not_ready"] for c in changes)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t("الغيارات"), ltr(len(changes)))
    m2.metric(t("القطع"), ltr(items_total))
    m3.metric(t("تكلفة الملابس"), ltr(_money(cost_total)))
    m4.metric(t("مشهد من غير غيار"), (f"⚠️ {missing}" if missing else "✅ 0"))
    if not_ready:
        st.caption(f"⏳ {ltr(not_ready)} {t('قطعة لسه مش جاهزة (شوف «قايمة القطع»)')}")

    section = st.segmented_control(
        t("القسم"), ["board", "changes", "items"], default="board", key=f"wardrobe_section_{project_id}",
        label_visibility="collapsed",
        format_func=lambda k: {"board": f"🗂️ {t('لوحة الغيارات')}", "changes": f"👔 {t('الغيارات والقطع')}",
                               "items": f"🧾 {t('قايمة القطع')}"}[k]) or "board"
    if section == "board":
        _render_board(project, project_id, cast, changes)
    elif section == "changes":
        _render_changes(project_id, company_id, cast, changes)
    else:
        _render_items(project, project_id)


# ---------- 1) لوحة الغيارات ----------

def _render_board(project, project_id, cast, changes):
    scenes = repo.scenes_of_project(project_id)
    if not scenes:
        st.info(t("لسه مفيش مشاهد في المشروع — جهّز الغيارات والقطع من «الغيارات والقطع» دلوقتي، واللوحة "
                  "هتتملى أول ما تضيف مشاهد أو تستورد السيناريو من تبويب «إضافة سيناريو»."))
        return
    if repo.is_series(project):
        eps = [e["episode_number"] for e in repo.episode_overview(project_id)]
        if eps:
            ep = st.pills(t("الحلقة"), ["all"] + eps, default="all", key=f"wardrobe_ep_{project_id}",
                          format_func=lambda o: t("كل الحلقات") if o == "all" else f"{t('ح')} {o}") or "all"
            if ep != "all":
                scenes = [s for s in scenes if s["episode_number"] == ep]

    in_scene = {}
    for r in repo.scene_character_names(project_id):
        in_scene.setdefault(r["scene_id"], set()).add(r["name"])
    assigned = repo.scene_change_map(project_id)
    number_of = {c["id"]: c["change_number"] for c in changes}
    shown_chars = [c for c in cast if any(c["name"] in in_scene.get(s["id"], ()) for s in scenes)]
    if not shown_chars:
        st.info(t("المشاهد دي مفيهاش شخصيات متسجلة. حدد الشخصيات في كل مشهد من تبويب «المشاهد»."))
        return

    # المصفوفة: صف لكل شخصية، عمود لكل مشهد. "⚠️" = الشخصية في المشهد ومالهاش غيار
    # الشخصية عمود عادي (مش index - الـ index دايمًا على الشمال): في العربي
    # بيقف على اليمين والمشاهد بتبدأ جنبه، في الإنجليزي العكس
    char_col = t("الشخصية")
    labels = [scene_label(s) for s in scenes]
    records = []
    for c in shown_chars:
        rec = {char_col: _char_label(c)}
        for s, lab in zip(scenes, labels):
            if c["name"] not in in_scene.get(s["id"], ()):
                rec[lab] = ""
            else:
                look = assigned.get((s["id"], c["id"]))
                rec[lab] = str(number_of.get(look, "")) if look else "⚠️"
        records.append(rec)
    order = labels[::-1] + [char_col] if _is_ar() else [char_col] + labels
    df = pd.DataFrame(records)[order]

    def _color(v):
        if v == "⚠️":
            return "background-color: rgba(254,202,5,.18)"
        if v and v.isdigit():
            return f"background-color: {_CHANGE_COLORS[(int(v) - 1) % len(_CHANGE_COLORS)]}; color: #fff; text-align: center"
        return ""

    st.caption(t("كل خانة = رقم الغيار اللي الشخصية لابساه في المشهد. ⚠️ = الشخصية في المشهد ومالهاش غيار. "
                 "فاضي = الشخصية مش في المشهد."))
    st.dataframe(df.style.map(_color, subset=labels), use_container_width=True, hide_index=True,
                 height=min(60 + 35 * len(df), 460))

    # التعديل: شخصية شخصية - جدول بمشاهدها وخانة غيار لكل مشهد
    st.markdown(f"**✏️ {t('حدد الغيارات لشخصية')}**")
    by_id = {c["id"]: c for c in shown_chars}
    char_id = st.pills(t("الشخصية"), list(by_id), default=shown_chars[0]["id"],
                       key=f"wardrobe_board_char_{project_id}", label_visibility="collapsed",
                       format_func=lambda i: _char_label(by_id[i])) or shown_chars[0]["id"]
    _render_character_assignments(project_id, by_id[char_id], changes, {s["id"] for s in scenes})


def _render_character_assignments(project_id, char, changes, scene_ids):
    own = [c for c in changes if c["character_id"] == char["id"]]
    opts = {repo.change_label(c): c["id"] for c in own}
    label_of = {v: k for k, v in opts.items()}
    rows = [r for r in repo.character_scenes_for_wardrobe(project_id, char["id"]) if r["id"] in scene_ids]
    if not rows:
        st.caption(t("الشخصية دي مش متسجلة في أي مشهد من المشاهد دي."))
        return
    df = pd.DataFrame([{
        "_id": r["id"],
        t("المشهد"): scene_label(r),
        t("المكان"): r["location_name"] or "—",
        t("ل/ن"): t(r["day_night"]) if r["day_night"] else "—",
        t("الغيار"): label_of.get(r["look_id"], _NONE),
    } for r in rows])
    key = f"wardrobe_assign_{project_id}_{char['id']}"
    edited = st.data_editor(
        df, key=key, hide_index=True, use_container_width=True, disabled=not _can_edit(),
        column_order=_rtl([t("المشهد"), t("المكان"), t("ل/ن"), t("الغيار")]),
        column_config={
            t("المشهد"): st.column_config.TextColumn(disabled=True),
            t("المكان"): st.column_config.TextColumn(disabled=True),
            t("ل/ن"): st.column_config.TextColumn(disabled=True),
            t("الغيار"): st.column_config.SelectboxColumn(options=[_NONE] + list(opts), required=True),
        })
    c1, c2 = st.columns([1, 1])
    missing_ids = [r["id"] for r in rows if not r["look_id"]]
    if c1.button(f"💾 {t('حفظ الغيارات')}", key=f"{key}_save", disabled=not _can_edit(),
                 use_container_width=True, type="primary"):
        new = {int(r["_id"]): opts.get(r[t("الغيار")]) for _, r in edited.iterrows()}
        old = {r["id"]: r["look_id"] for r in rows}
        n = repo.set_scene_changes(project_id, char["id"], {k: v for k, v in new.items() if v != old.get(k)})
        st.toast(f"{t('اتحفظ')} {n} {t('مشهد')}", icon="👗")
        st.rerun()
    if missing_ids and own:
        first = own[0]
        if c2.button(f"{t('حط')} {repo.change_label(first)} {t('في المشاهد اللي من غير غيار')} ({len(missing_ids)})",
                     key=f"{key}_fill", disabled=not _can_edit(), use_container_width=True):
            repo.set_scene_changes(project_id, char["id"], {sid: first["id"] for sid in missing_ids})
            st.rerun()


# ---------- 2) الغيارات والقطع ----------

def _render_changes(project_id, company_id, cast, changes):
    by_id = {c["id"]: c for c in cast}
    char_id = st.pills(t("الشخصية"), list(by_id), default=cast[0]["id"], key=f"wardrobe_char_{project_id}",
                       label_visibility="collapsed", format_func=lambda i: _char_label(by_id[i])) or cast[0]["id"]
    char = by_id[char_id]
    if char.get("actor"):
        sizes = repo.actor_sizes_for_character(project_id, char_id, company_id)
        bits = []
        if sizes:
            for k, lab, unit in (("height_cm", "الطول", "سم"), ("weight_kg", "الوزن", "كجم"),
                                 ("chest_cm", "الصدر", "سم"), ("waist_cm", "الوسط", "سم"),
                                 ("hips_cm", "الورك", "سم"), ("shoe_size_eu", "الجزمة", "")):
                if sizes.get(k):
                    bits.append(f"{t(lab)} {ltr(sizes[k])} {t(unit)}".strip())
        st.caption(f"🎬 {char['actor']['name']}"
                   + (f" — 📏 {' · '.join(bits)}" if bits else f" — {t('مقاسات الممثل/ة مش متسجلة في بروفايله')}"))
    else:
        st.caption(t("لسه مفيش ممثل/ة متعاقد للدور ده — المقاسات بتظهر هنا أول ما يتعاقد."))

    own = [c for c in changes if c["character_id"] == char_id]
    for ch in own:
        head = (f"{repo.change_label(ch)} — {ltr(ch['items'])} {t('قطعة')} · {ltr(_money(ch['cost']))}"
                f" · {ltr(ch['scenes'])} {t('مشهد')}" + (f" · ⏳ {ltr(ch['not_ready'])}" if ch["not_ready"] else ""))
        exp = st.expander(f"👔 {head}", key=f"exp_change_{ch['id']}", on_change="rerun")
        with exp:
            if exp.open:
                _render_change_body(project_id, ch)

    if _can_edit():
        with st.form(f"add_change_{project_id}_{char_id}", clear_on_submit=True):
            c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
            name = c1.text_input(t("اسم الغيار الجديد (اختياري)"), placeholder=t("مثال: بدلة الفرح"))
            if c2.form_submit_button(f"➕ {t('غيار جديد')}", use_container_width=True):
                repo.add_change(project_id, char_id, name)
                st.rerun()


def _render_change_body(project_id, ch):
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    shown_name = "" if ch["look_name"] == repo.DEFAULT_LOOK_NAME else (ch["look_name"] or "")
    new_name = c1.text_input(t("اسم الغيار"), value=shown_name, key=f"change_name_{ch['id']}",
                             placeholder=t("مثال: بدلة الفرح"), disabled=not _can_edit())
    if c2.button(t("حفظ الاسم"), key=f"change_name_btn_{ch['id']}", disabled=not _can_edit(),
                 use_container_width=True):
        repo.rename_change(project_id, ch["id"], new_name)
        st.rerun()
    if ch["wardrobe_description"]:
        st.caption(f"📝 {t('وصف الملابس من المظهر')}: {ch['wardrobe_description']}")

    items = repo.items_of_change(project_id, ch["id"])
    cols = {"item_name": t("القطعة"), "category": t("النوع"), "color": t("اللون"), "material": t("الخامة"),
            "size": t("المقاس"), "source": t("المصدر"), "multiples": t("النسخ"),
            "story_state": t("الحالة في الحكاية"), "cost": t("التكلفة"), "status": t("التجهيز"),
            "notes": t("ملاحظات")}
    df = pd.DataFrame([{v: it[k] for k, v in cols.items()} for it in items], columns=list(cols.values()))
    df[t("النسخ")] = pd.to_numeric(df[t("النسخ")], errors="coerce")
    df[t("التكلفة")] = pd.to_numeric(df[t("التكلفة")], errors="coerce")
    edited = st.data_editor(
        df, key=f"items_{ch['id']}", num_rows="dynamic", hide_index=True, use_container_width=True,
        disabled=not _can_edit(), column_order=_rtl(list(cols.values())),
        # عواميد ضيقة عشان الجدول كله يبان من غير سكرول - في العربي السكرول
        # بيبدأ من الشمال فعمود "القطعة" (أهم عمود، على اليمين) كان بيستخبى
        column_config={
            t("القطعة"): st.column_config.TextColumn(required=True, width="medium"),
            t("النوع"): st.column_config.SelectboxColumn(options=repo.WARDROBE_CATEGORIES, width="small"),
            t("اللون"): st.column_config.TextColumn(width="small"),
            t("الخامة"): st.column_config.TextColumn(width="small"),
            t("المقاس"): st.column_config.TextColumn(width="small"),
            t("المصدر"): st.column_config.SelectboxColumn(options=repo.WARDROBE_SOURCES, width="small"),
            t("النسخ"): st.column_config.NumberColumn(min_value=1, step=1, default=1, width="small",
                                                      help=t("عدد النسخ من نفس القطعة — للمشاهد اللي فيها دم أو مية أو أكشن")),
            t("الحالة في الحكاية"): st.column_config.TextColumn(width="small",
                                                              help=t("زي: نضيف، متسخ، مبلول، مقطوع")),
            t("التكلفة"): st.column_config.NumberColumn(min_value=0, step=50, format="%.0f", width="small",
                                                        help=t("تكلفة النسخة الواحدة — الإجمالي بيتحسب × عدد النسخ")),
            t("التجهيز"): st.column_config.SelectboxColumn(options=repo.WARDROBE_STATUSES, width="small",
                                                          default=repo.WARDROBE_STATUSES[0]),
            t("ملاحظات"): st.column_config.TextColumn(width="small"),
        })
    if st.button(f"💾 {t('حفظ القطع')}", key=f"items_save_{ch['id']}", disabled=not _can_edit(), type="primary"):
        back = {v: k for k, v in cols.items()}
        rows = [{back[c]: r[c] for c in edited.columns if c in back} for _, r in edited.iterrows()]
        n = repo.save_change_items(project_id, ch["id"], rows)
        st.toast(f"{t('اتحفظت')} {n} {t('قطعة')}", icon="👔")
        st.rerun()


# ---------- 3) قايمة القطع ----------

def _render_items(project, project_id):
    items = repo.wardrobe_items_of_project(project_id)
    if not items:
        st.info(t("لسه مفيش قطع ملابس. ضيف قطع كل غيار من «الغيارات والقطع»."))
    else:
        statuses = sorted({i["status"] or t("من غير حالة") for i in items})
        pick = st.pills(t("التجهيز"), statuses, selection_mode="multi", key=f"items_status_{project_id}")
        shown = [i for i in items if not pick or (i["status"] or t("من غير حالة")) in pick]
        total = sum((i["cost"] or 0) * (i["multiples"] or 1) for i in shown)
        st.caption(f"{ltr(len(shown))} {t('قطعة')} · {t('الإجمالي')} {ltr(_money(total))}")
        df = pd.DataFrame([{
            t("الشخصية"): _char_label({"cast_number": i["cast_number"], "name": i["character_name"]}),
            t("الغيار"): repo.change_label(i),
            t("القطعة"): i["item_name"],
            t("النوع"): i["category"] or "",
            t("المقاس"): i["size"] or "",
            t("المصدر"): i["source"] or "",
            t("النسخ"): i["multiples"] or 1,
            t("التكلفة"): (i["cost"] or 0) * (i["multiples"] or 1),
            t("التجهيز"): i["status"] or "",
        } for i in shown])
        if _is_ar():
            df = df[df.columns[::-1]]
        st.dataframe(df, hide_index=True, use_container_width=True, height=min(38 + 35 * len(df), 480))
    import export
    from database import fetch_all
    st.download_button(
        f"⬇️ {t('كشف الملابس (Excel)')}",
        # بيتبني لما تدوس بس (زي التقارير)، مش مع كل rerun
        data=lambda: export.build_wardrobe_sheet_excel(project, project_id, fetch_all),
        file_name=f"wardrobe_{project_id}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"dl_wardrobe_{project_id}")
