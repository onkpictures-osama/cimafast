"""تبويب الإكسسوار — تابع للأماكن (اتفاق المالك 2026-09-24).

الإكسسوار = اللي بيجيبه الإكسسواريست:
  🏠 المرصوص في المكان/الديكور (ساعة على الكومودينو، أباجورة، لوحة) ← تحت
     المكان الرئيسي وديكوراته.
  ✋ اللي بيتمسك في الإيد (مسدس) ← تحت الشخصية.
واللي بيتلبس (ساعة يد، عقد، برنيطة) مش هنا - ده ملابس، في غيار الشخصية.

الإكسسوار القديم (قبل التقسيمة دي) والجديد من تحليل السيناريو بيقعوا في
"📦 محتاج يتحدد مكانه" باقتراحات جاهزة (المكان من المشاهد، "بتتلبس" من الاسم)
- اقتراحات بس، مفيش حاجة بتتنقل غير لما اليوزر يدوس «تطبيق».
"""

import pandas as pd
import streamlit as st

import permissions
import repo
from i18n import t, tr
from search import matches
from ui import library_result_count, library_search, ltr

_NONE = "—"


def _can_edit():
    role = permissions.current_role()
    return role is None or permissions.can(role, "edit")


def _is_ar():
    return st.session_state.get("ui_lang", "ar") == "ar"


def _rtl(cols):
    return cols[::-1] if _is_ar() else cols


def _money(v):
    return f"{v:,.0f}" if v else "0"


_COLS = {"name": "الإكسسوار", "quantity": "الكمية", "source": "المصدر", "cost": "التكلفة",
         "status": "الحالة", "notes": "ملاحظات"}


def render(project_id):
    st.subheader(tr("sub_props"))
    st.caption(t("الإكسسوار هو اللي بيجيبه الإكسسواريست: المرصوص في المكان (زي ساعة على الكومودينو) أو اللي "
                 "بيتمسك في الإيد (زي مسدس). اللي بيتلبس (ساعة يد، عقد، برنيطة) بيتسجّل في الملابس."))

    groups = repo.props_grouped(project_id)
    total = sum(len(v) for v in groups["by_location"].values()) + \
        sum(len(v) for v in groups["by_character"].values()) + len(groups["unplaced"])
    q = library_search(f"prop_search_{project_id}", total, "إكسسوار") if total else ""
    st.caption(f"➕ {t('لإضافة قطعة: افتح المكان (أو الشخصية) واكتب في آخر صف فاضي في الجدول، وبعدين «حفظ».')}")
    summary = repo.props_summary(project_id)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t("القطع"), ltr(summary["count"]))
    m2.metric(t("التكلفة"), ltr(_money(summary["cost"])))
    m3.metric(t("لسه مطلوب"), ltr(summary["needed"]))
    m4.metric(t("محتاج يتحدد مكانه"), (f"📦 {len(groups['unplaced'])}" if groups["unplaced"] else "✅ 0"))

    options = ["places", "hands"] + (["unplaced"] if groups["unplaced"] else [])
    labels = {"places": f"🏠 {t('إكسسوار الأماكن')}", "hands": f"✋ {t('في إيد الشخصيات')}",
              "unplaced": f"📦 {t('محتاج يتحدد مكانه')} ({len(groups['unplaced'])})"}
    key = f"props_section_{project_id}"
    if st.session_state.get(key) not in options:
        st.session_state[key] = "unplaced" if groups["unplaced"] else "places"
    section = st.segmented_control(t("القسم"), options, key=key, required=True,
                                   label_visibility="collapsed", format_func=labels.get)
    if section == "places":
        _render_places(project_id, groups, q)
    elif section == "hands":
        _render_hands(project_id, groups, q)
    else:
        _render_unplaced(project_id, groups, q)


def _table(project_id, props, key, scene_counts):
    df = pd.DataFrame([{
        "_id": p["id"], _COLS["name"]: p["name"], _COLS["quantity"]: p["quantity"] or 1,
        _COLS["source"]: p["source"], _COLS["cost"]: p["cost"], _COLS["status"]: p["status"] or repo.PROP_STATUSES[0],
        _COLS["notes"]: p["notes"],
        t("مشاهد"): scene_counts.get(p["id"], 0),
    } for p in props], columns=["_id"] + list(_COLS.values()) + [t("مشاهد")])
    df[_COLS["cost"]] = pd.to_numeric(df[_COLS["cost"]], errors="coerce")
    df[_COLS["quantity"]] = pd.to_numeric(df[_COLS["quantity"]], errors="coerce")
    return st.data_editor(
        df, key=key, num_rows="dynamic", hide_index=True, use_container_width=True, disabled=not _can_edit(),
        column_order=_rtl(list(_COLS.values()) + [t("مشاهد")]),
        column_config={
            _COLS["name"]: st.column_config.TextColumn(required=True, width="medium"),
            _COLS["quantity"]: st.column_config.NumberColumn(
                min_value=1, step=1, default=1, width="small",
                help=t("عدد النسخ المطلوبة من نفس القطعة (زي أكتر من نسخة من خطاب هيتقطع في أكتر من تيك)")),
            _COLS["source"]: st.column_config.SelectboxColumn(options=repo.PROP_SOURCES, width="small"),
            _COLS["cost"]: st.column_config.NumberColumn(min_value=0, step=50, format="%.0f", width="small",
                                                        help=t("تكلفة القطعة الواحدة — الإجمالي × الكمية")),
            _COLS["status"]: st.column_config.SelectboxColumn(options=repo.PROP_STATUSES, width="small",
                                                             default=repo.PROP_STATUSES[0]),
            _COLS["notes"]: st.column_config.TextColumn(
                width="small", help=t("أي تفاصيل تانية - زي عدد النسخ الاحتياطية أو حالة خاصة للقطعة")),
            t("مشاهد"): st.column_config.NumberColumn(disabled=True, width="small",
                                                      help=t("عدد المشاهد اللي القطعة متسجلة فيها")),
        })


def _save(project_id, edited, **anchor):
    back = {v: k for k, v in _COLS.items()}
    rows = []
    for _, r in edited.iterrows():
        row = {back[c]: r[c] for c in edited.columns if c in back}
        row["_id"] = r.get("_id")
        rows.append(row)
    n = repo.save_props_for(project_id, rows, **anchor)
    st.toast(f"{t('اتحفظ')} {n} {t('قطعة')}", icon="🪑")
    st.rerun()


def _render_places(project_id, groups, q):
    locations = repo.locations_of_project(project_id)
    if not locations:
        st.info(t("لسه مفيش أماكن في المشروع. الإكسسوار بيترص في الأماكن — ضيف الأماكن من تبويب «الأماكن» "
                  "أو استورد السيناريو."))
        return
    counts = repo.prop_scene_counts(project_id)
    children = {}
    for loc in locations:
        children.setdefault(loc["parent_location_id"], []).append(loc)
    ids = {loc["id"] for loc in locations}
    mains = sorted([loc for loc in locations if not loc["parent_location_id"] or loc["parent_location_id"] not in ids],
                   key=lambda x: x["name"])
    by_loc = groups["by_location"]
    st.caption(t("كل مكان رئيسي وتحته ديكوراته — الإكسسوار بيتسجل على الديكور اللي بيترص فيه."))
    for main in mains:
        family = [main] + sorted(children.get(main["id"], []), key=lambda x: x["name"])
        n_items = sum(len(by_loc.get(x["id"], [])) for x in family)
        if q and not any(matches(q, x["name"]) or any(matches(q, p["name"]) for p in by_loc.get(x["id"], []))
                         for x in family):
            continue
        _title = (f"🏠 {main['name']} — {ltr(n_items)} {t('قطعة')}"
                  + (f" · {ltr(len(family) - 1)} {t('ديكور')}" if len(family) > 1 else ""))
        _lazy_exp = st.expander(_title, key=f"exp_prop_loc_{main['id']}", on_change="rerun")
        with _lazy_exp:
            if _lazy_exp.open:
                _render_family(project_id, main, family, by_loc, q, counts)


def _render_family(project_id, main, family, by_loc, q, counts):
    """المكان الرئيسي وديكوراته - جدول إكسسوار لكل واحد."""
    for loc in family:
        props = [p for p in by_loc.get(loc["id"], []) if not q or matches(q, p["name"], loc["name"])]
        st.markdown(f"**{'🏠' if loc is main else '🚪'} {loc['name']}**"
                    + ("" if loc is main else f" <span style='opacity:.6'>({t('ديكور')})</span>"),
                    unsafe_allow_html=True)
        edited = _table(project_id, props, f"props_loc_{loc['id']}", counts)
        if st.button(f"💾 {t('حفظ إكسسوار')} {loc['name']}", key=f"props_loc_save_{loc['id']}",
                     disabled=not _can_edit()):
            _save(project_id, edited, location_id=loc["id"])


def _render_hands(project_id, groups, q):
    cast = repo.project_cast(project_id)
    if not cast:
        st.info(t("لسه مفيش شخصيات في المشروع."))
        return
    counts = repo.prop_scene_counts(project_id)
    st.caption(t("اللي بيتمسك في الإيد ومش بيتلبس (مسدس، موبايل في الإيد، شنطة فلوس...) — بيجيبه الإكسسواريست."))
    by_char = groups["by_character"]
    for c in cast:
        props = [p for p in by_char.get(c["id"], []) if not q or matches(q, p["name"], c["name"])]
        if q and not props and not matches(q, c["name"]):
            continue
        label = (f"#{c['cast_number']} " if c["cast_number"] else "") + c["name"]
        _title = f"✋ {label} — {ltr(len(by_char.get(c['id'], [])))} {t('قطعة')}"
        _lazy_exp = st.expander(_title, key=f"exp_prop_char_{c['id']}", on_change="rerun")
        with _lazy_exp:
            if _lazy_exp.open:
                edited = _table(project_id, props, f"props_char_{c['id']}", counts)
                if st.button(f"💾 {t('حفظ')}", key=f"props_char_save_{c['id']}", disabled=not _can_edit()):
                    _save(project_id, edited, character_id=c["id"])


def _render_unplaced(project_id, groups, q):
    props = [p for p in groups["unplaced"] if not q or matches(q, p["name"])]
    st.info(t("القطع دي لسه مش متحددة: مرصوصة في مكان، ولا في إيد شخصية، ولا بتتلبس (تتنقل للملابس)؟ "
              "الاقتراحات متملية من المشاهد اللي ظهرت فيها ومن اسم القطعة — راجعها ودوس «تطبيق». "
              "مفيش حاجة بتتنقل من غير ما تدوس."))
    if not props:
        library_result_count(0, len(groups["unplaced"]))
        return
    locations = repo.locations_of_project(project_id)
    ids = {loc["id"] for loc in locations}
    name_of = {loc["id"]: loc["name"] for loc in locations}
    parent_of = {loc["id"]: loc["parent_location_id"] for loc in locations}

    def loc_label(lid):
        par = parent_of.get(lid)
        return f"{name_of[par]} ← {name_of[lid]}" if par in ids else name_of[lid]

    loc_opts = [_NONE] + sorted((loc_label(i) for i in ids))
    loc_id_of = {loc_label(i): i for i in ids}
    cast = repo.project_cast(project_id)
    char_opts = [_NONE] + [c["name"] for c in cast]
    char_id_of = {c["name"]: c["id"] for c in cast}
    char_name = {c["id"]: c["name"] for c in cast}
    sugg = repo.suggest_prop_location(project_id)

    rows = []
    for p in props[:200]:
        s = sugg.get(p["id"])
        worn = repo.looks_worn(p["name"])
        rows.append({
            "_id": p["id"],
            t("الإكسسوار"): p["name"],
            t("مرصوص في"): loc_label(s[0]) if (s and s[0] in ids and not worn) else _NONE,
            t("في إيد"): char_name.get(p["character_id"], _NONE) if not worn else _NONE,
            t("بيتلبس ← الملابس"): worn,
            t("لبس مين"): char_name.get(p["character_id"], _NONE),
            t("الاقتراح"): (f"{t('ظهر في')} {s[1]}/{s[2]} {t('مشهد في المكان ده')}" if s else "")
            + (f" · 👗 {t('شكله بيتلبس')}" if worn else ""),
        })
    if len(props) > 200:
        st.caption(f"{t('بيتعرض أول 200 من')} {ltr(len(props))} — {t('طبّق وبعدين هتظهر الباقي.')}")
    cols = [t("الإكسسوار"), t("مرصوص في"), t("في إيد"), t("بيتلبس ← الملابس"), t("لبس مين"), t("الاقتراح")]
    edited = st.data_editor(
        pd.DataFrame(rows), key=f"props_unplaced_{project_id}", hide_index=True, use_container_width=True,
        disabled=not _can_edit(), column_order=_rtl(cols),
        column_config={
            t("الإكسسوار"): st.column_config.TextColumn(disabled=True),
            t("مرصوص في"): st.column_config.SelectboxColumn(options=loc_opts, required=True),
            t("في إيد"): st.column_config.SelectboxColumn(options=char_opts, required=True),
            t("بيتلبس ← الملابس"): st.column_config.CheckboxColumn(),
            t("لبس مين"): st.column_config.SelectboxColumn(options=char_opts, required=True,
                                                          help=t("الشخصية اللي هتلبسها — لازم تتحدد عشان تتنقل لغيارها")),
            t("الاقتراح"): st.column_config.TextColumn(disabled=True),
        })
    if st.button(f"✅ {t('تطبيق')}", key=f"props_unplaced_apply_{project_id}", type="primary",
                 disabled=not _can_edit()):
        placements, moved, skipped = [], 0, 0
        for _, r in edited.iterrows():
            pid = int(r["_id"])
            if r[t("بيتلبس ← الملابس")]:
                who = char_id_of.get(r[t("لبس مين")])
                if who and repo.move_prop_to_wardrobe(project_id, pid, who):
                    moved += 1
                else:
                    skipped += 1
                continue
            loc = loc_id_of.get(r[t("مرصوص في")])
            char = char_id_of.get(r[t("في إيد")])
            if loc or char:
                placements.append((pid, loc, char))
        placed = repo.place_props(project_id, placements) if placements else 0
        msg = f"🏠✋ {placed} · 👗 {moved}"
        if skipped:
            msg += f" · ⚠️ {skipped} {t('محتاجين «لبس مين»')}"
        st.toast(msg, icon="🪑")
        st.rerun()
