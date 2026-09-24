"""صفحات المكتبات (?page=...) — المالك 2026-09-24.

بتتعرض مكان تبويبات المشروع والشريط الجانبي كامل جنبها (المشروع الحالي،
دورك، الفريق). زرار الرجوع بيقفل الصفحة ويرجّع تبويبات المشروع.
"""

import streamlit as st

import permissions
import views.actors
import views.library
import views.locations_library
from i18n import t
from ui import close_page


def render(page, current_user, project_id, project_company_id, home_company_id, role, is_ar):
    st.session_state["_cf_project"] = None     # F3: كتابات المكتبة مش تبع مشروع
    st.button(f"↩ {t('رجوع للمشروع')}" if project_id else f"↩ {t('رجوع')}", key="lib_back",
              on_click=close_page)
    try:
        if page == "library":
            views.library.render(current_user=current_user, company_id=home_company_id, role=role, is_ar=is_ar)
        elif page == "actors":
            views.actors.render_library(current_user, project_id, project_company_id, st.query_params.get("pick"))
        else:
            views.locations_library.render(project_id)
    except permissions.Denied as exc:
        st.warning(t(str(exc)))
