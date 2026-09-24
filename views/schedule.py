"""تبويب «جدول التصوير» — أول باب في مرحلة الإنتاج (اتفاق المالك 2026-09-24).

الجدول نفسه شاشة لوحدها (board/، سحب وإفلات للمشاهد على الأيام). هنا
ملخّص الحالة وزرار يفتحه على المشروع ده، وأيام الممثلين. أبواب الإنتاج
التانية (الكول شيت، التقارير اليومية...) هتتضاف هنا بعدين.
"""

import pandas as pd
import streamlit as st

import repo
from i18n import t, tr
from ui import ltr


def render(project, project_id, board_url):
    st.subheader(tr("tab_schedule"))
    ov = repo.project_overview(project_id)
    scenes, scheduled = ov["scenes"] or 0, ov["scheduled_scenes"] or 0
    c1, c2, c3 = st.columns(3)
    c1.metric(t("أيام التصوير"), ltr(ov["days"] or 0))
    c2.metric(t("مشاهد متجدولة"), f"{ltr(scheduled)} / {ltr(scenes)}")
    c3.metric(t("أيام من غير تاريخ"), ltr(ov["days_without_date"] or 0))
    if not scenes:
        st.info(t("لسه مفيش مشاهد في المشروع — الجدول بيتعمل من المشاهد. ارجع لمرحلة «ما قبل الإنتاج» "
                  "وضيف المشاهد أو استورد السيناريو."))
    elif scheduled < scenes:
        st.caption(f"⚠️ {ltr(scenes - scheduled)} {t('مشهد لسه مش في أي يوم تصوير.')}")
    if board_url:
        st.link_button(f"🗓️ {t('افتح جدول التصوير')}", f"{board_url}?project={project_id}",
                       type="primary", use_container_width=True)
    else:
        st.caption(t("شاشة جدول التصوير مش متاحة في التشغيلة دي."))

    dood = repo.day_out_of_days(project_id)
    if dood["rows"]:
        st.markdown(f"#### 👥 {t('أيام الممثلين')}")
        df = pd.DataFrame([{
            t("رقم"): r["cast_number"] or "",
            t("الشخصية"): r["name"],
            t("الممثل/ة"): r["actor"] or "—",
            t("أيام تصوير"): r["work_days"],
            t("أيام انتظار"): r["hold_days"],
            t("من يوم"): r["first_day"],
            t("لـ يوم"): r["last_day"],
        } for r in dood["rows"]])
        if st.session_state.get("ui_lang", "ar") == "ar":
            df = df[df.columns[::-1]]
        st.dataframe(df, hide_index=True, use_container_width=True, height=min(38 + 35 * len(df), 420))
    st.caption(t("قريب هنا: الكول شيت، والتقارير اليومية، وباقي أقسام إدارة التصوير."))
