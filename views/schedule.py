"""تبويب «جدول التصوير» — أول باب في مرحلة الإنتاج (اتفاق المالك 2026-09-24).

الجدول نفسه شاشة لوحدها (board/، سحب وإفلات للمشاهد على الأيام). هنا
ملخّص الحالة وزرار يفتحه على المشروع ده، وأيام الممثلين. أبواب الإنتاج
التانية (الكول شيت، التقارير اليومية...) هتتضاف هنا بعدين.
"""

import pandas as pd
import streamlit as st

import repo
from i18n import t, tr
from ui import ltr, nav_link
from views.looks import can_edit


def _toggle_day(project_id, day_id, key):
    repo.set_day_shot(project_id, day_id, st.session_state.get(key, False))


def _days_shot(project_id):
    """علّم كل يوم لما يتصور - شريط التقدّم فوق بيعد الأيام دي (المالك 2026-09-24)."""
    days = repo.shooting_days(project_id)
    if not days:
        return
    done = sum(1 for d in days if d["shot_done"])
    st.markdown(f"#### 🎬 {t('أيام اتصورت')} — {ltr(done)} {t('من')} {ltr(len(days))}")
    st.caption(t("علّم على اليوم أول ما يخلص تصويره."))
    editable = can_edit()
    cols = st.columns(4)
    for i, d in enumerate(days):
        key = f"day_shot_{d['id']}"
        st.session_state[key] = bool(d["shot_done"])
        label = f"{t('يوم')} {ltr(d['day_number'])}" + (f" · {ltr(d['shoot_date'])}" if d["shoot_date"] else "")
        cols[i % 4].checkbox(label, key=key, disabled=not editable,
                             on_change=_toggle_day, args=(project_id, d["id"], key))


def render(project, project_id, board_url):
    st.subheader(tr("tab_schedule"))
    ov = repo.project_overview(project_id)
    scenes, scheduled = ov["scenes"] or 0, ov["scheduled_scenes"] or 0
    c1, c2, c3 = st.columns(3)
    c1.metric(t("أيام التصوير"), ltr(ov["days"] or 0))
    c2.metric(t("مشاهد متجدولة"), f"{ltr(scheduled)} {t('من')} {ltr(scenes)}")
    c3.metric(t("أيام من غير تاريخ"), ltr(ov["days_without_date"] or 0))
    if not scenes:
        st.info(t("لسه مفيش مشاهد في المشروع — الجدول بيتعمل من المشاهد. ارجع لمرحلة «ما قبل الإنتاج» "
                  "وضيف المشاهد أو استورد السيناريو."))
    elif scheduled < scenes:
        st.caption(f"⚠️ {ltr(scenes - scheduled)} {t('مشهد لسه مش في أي يوم تصوير.')}")
    if board_url:
        # نفس التاب (مش تاب جديد) - الرجوع بزرار الرجوع في المتصفح
        nav_link(f"🗓️ {t('افتح جدول التصوير')}", f"{board_url}?project={project_id}")
    else:
        st.caption(t("شاشة جدول التصوير مش متاحة في التشغيلة دي."))

    _days_shot(project_id)

    dood = repo.day_out_of_days(project_id)
    if dood["rows"]:
        st.markdown(f"#### 👥 {t('أيام الممثلين')}")
        df = pd.DataFrame([{
            t("رقم"): r["cast_number"] or "",
            t("الشخصية"): r["name"],
            t("الممثل"): r["actor"] or "—",
            t("أيام تصوير"): r["work_days"],
            t("أيام انتظار"): r["hold_days"],
            t("من يوم"): r["first_day"],
            t("لـ يوم"): r["last_day"],
        } for r in dood["rows"]])
        if st.session_state.get("ui_lang", "ar") == "ar":
            df = df[df.columns[::-1]]
        st.dataframe(df, hide_index=True, use_container_width=True, height=min(38 + 35 * len(df), 420))
    st.caption(t("قريب هنا: الكول شيت، والتقارير اليومية، وباقي أقسام إدارة التصوير."))
