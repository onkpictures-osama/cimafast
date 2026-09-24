"""تبويب إعدادات المشروع.

كانت كل الحاجات دي (تعديل/حذف المشروع، الحلقات، اسمك ودورك، لينكات الفريق
وجدول التصوير) فورمات وروابط عايمة في الشريط الجانبي — المالك طلب إن أي
تفاصيل تنفيذية خاصة بمشروع معيّن متبقاش في الـ sidebar خالص، وتتنقل جوه
المشروع نفسه. هنا مكانها الجديد."""

import streamlit as st
from i18n import t, tr
from ui import nav_link, guarded_delete, mark_saved, safe_index, show_saved_badge
import accounts
import permissions
import project_types
import repo


def render(project_id, current_user, company_id, role, tier, board_url):
    project = repo.project_by_id(project_id)[0]
    can_edit = permissions.can(role, "edit")

    # لينكات الفريق وجدول التصوير — كانت في الشريط الجانبي، بقت هنا لأنها
    # تفاصيل خاصة بإدارة المشروع/الشركة، مش تنقّل عام.
    # جدول التصوير اتنقل لمرحلة الإنتاج (تبويب لوحده) - مش هنا. واللينكات
    # بتفتح في نفس التاب (nav_link) بدل تاب جديد يسيب القديمة وراه.
    if board_url:
        # B5: إدارة الفريق مش متاحة لاشتراك Creator خالص — شغال لوحده دايمًا.
        if accounts.TIER_ALLOWS_TEAM.get(tier, True):
            team_label = t("إدارة الفريق") if role in ("admin", "operator") else t("الفريق وحسابي")
            nav_link(f"👥 {team_label}", f"{board_url}team/")
        elif role in ("admin", "operator"):
            st.caption(t("إدارة الفريق مش متاحة في باقة Creator — شغال لوحدك. رقّي الاشتراك لـ Studio أو Enterprise عشان تضيف فريق."))
        if permissions.can(role, "view_audit"):
            nav_link(f"🧾 {t('سجل النشاط')}", f"{board_url}activity/?company_id={company_id}")
        st.divider()

    # (أ) أعضاء المشروع: مين يشوف المشروع ده من أعضاء مساحة العمل - للمدير بس
    if permissions.can(role, "manage_team") and accounts.TIER_ALLOWS_TEAM.get(tier, True):
        _render_project_team(project_id, current_user)
        st.divider()

    # دورك في المشروع ده — لحد ما يبقى فيه نظام أدوار لكل مشروع لوحده، ده
    # أقرب حاجة متاحة: دورك في الشركة (F2). لو أنت المالك (admin/operator)
    # الشاشة كلها تحت أمرك أصلًا فمفيش داعي لبادچ يوضحلك دورك.
    if role not in ("admin", "operator"):
        st.info(f"{t('دورك في المشروع ده')}: **{accounts.ROLE_LABELS.get(role, role)}**")

    if project["owner_name"]:
        owner_line = f"👤 {project['owner_name']}"
        if project["owner_role"]:
            owner_line += f" · {t(project['owner_role'])}"
        st.caption(owner_line)

    if not can_edit:
        return

    st.subheader(t("اسمك ووظيفتك في المشروع ده"))
    from database import PROJECT_ROLE_OPTIONS
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
        repo.update_project_owner(e_owner_name, None if e_owner_role == "—" else e_owner_role, project_id)
        mark_saved(f"settings_{project_id}")
        st.rerun()
    show_saved_badge(f"settings_{project_id}")

    st.divider()

    # الحلقات (للمسلسلات بس)
    if project["project_type"] == "مسلسل":
        st.subheader(f"📺 {t('الحلقات')}")
        episodes = repo.episodes_of_project(project_id)

        # عدد الحلقات: بيكمّل الناقص من 1 لحد الرقم ده. مابيمسحش حلقات لو
        # الرقم قلّ - مسح حلقة (ومشاهدها) قرار لوحده، من الحلقة نفسها تحت.
        _have = max((e["episode_number"] for e in episodes), default=0)
        c_n, c_b = st.columns([2, 1], vertical_alignment="bottom")
        _target = c_n.number_input(t("عدد الحلقات"), min_value=1, max_value=500, step=1,
                                   value=max(_have, 1), key=f"ep_count_{project_id}",
                                   disabled=not can_edit)
        if c_b.button(t("تحديث العدد"), key=f"ep_count_btn_{project_id}", disabled=not can_edit,
                      use_container_width=True):
            made = repo.ensure_episodes(project_id, _target)
            st.toast(f"{t('اتضاف')} {made} {t('حلقة')}" if made else t("كل الحلقات موجودة بالفعل"), icon="📺")
            st.rerun()
        if not episodes:
            st.warning(t("المسلسل ده لسه مالوش حلقات — حدد العدد فوق عشان تقدر ترفع سكريبت كل حلقة."))

        st.markdown(f"**{t('إنشاء حلقة جديدة')}**")
        new_ep_num = st.number_input(t("رقم الحلقة"), min_value=1, value=len(episodes) + 1, key=f"new_ep_num_{project_id}")
        new_ep_title = st.text_input(t("عنوان الحلقة"), key=f"new_ep_title_{project_id}")
        new_ep_desc = st.text_area(t("وصف الحلقة"), key=f"new_ep_desc_{project_id}")

        if st.button(t("إضافة حلقة"), key=f"add_ep_btn_{project_id}", disabled=not can_edit):
            if any(e["episode_number"] == int(new_ep_num) for e in episodes):
                st.warning(t("الحلقة دي موجودة بالفعل"))
            else:
                repo.add_episode(project_id, int(new_ep_num), new_ep_title.strip() or None, new_ep_desc)
                st.success(t("تم إضافة الحلقة"))
                st.rerun()

        if episodes:
            st.markdown(f"**{t('الحلقات')} ({len(episodes)})**")
            for ep in episodes:
                with st.expander(f"الحلقة {ep['episode_number']}: {ep['title'] or '(بدون عنوان)'}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**رقم:** {ep['episode_number']}")
                    with col2:
                        st.write(f"**الحالة:** {ep.get('status', 'planning')}")
                    if ep["description"]:
                        st.write(f"**الوصف:** {ep['description']}")
                    if st.button(t("حذف الحلقة"), key=f"del_ep_{ep['id']}", disabled=not can_edit):
                        repo.delete_episode(project_id, ep["id"])
                        st.success(t("تم حذف الحلقة"))
                        st.rerun()
        st.divider()

    # تعديل/حذف المشروع
    st.subheader(tr("edit_delete_project"))
    e_proj_name = st.text_input(t("اسم المشروع"), value=project["name"], key=f"edit_proj_name_{project_id}")
    e_proj_type = st.selectbox(
        t("نوع المشروع"), project_types.TYPES,
        index=safe_index(project_types.TYPES, project_types.normalize_type(project["project_type"])),
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
            repo.update_project_settings(e_proj_name, e_proj_type, e_proj_res, e_proj_orient, e_proj_ratio, project_id)
            st.success(t("تم تعديل بيانات المشروع"))
            st.rerun()
        else:
            st.warning(t("اسم المشروع مينفعش يبقى فاضي"))

    st.markdown("---")
    if permissions.can(role, "delete_project"):
        st.caption(t("⚠️ حذف المشروع بيمسح كل الأماكن والشخصيات والمشاهد واللقطات بتاعته نهائيًا."))
        confirm_delete_project = st.checkbox(
            f"{t('متأكد إني عايز أمسح مشروع')} \"{project['name']}\" {t('وكل بياناته')}",
            key=f"confirm_delete_project_{project_id}",
        )
        if st.button(t("🗑️ حذف المشروع نهائيًا"), disabled=not confirm_delete_project, key=f"delete_proj_btn_{project_id}"):
            # guarded_delete بيمسك أي IntegrityError (بيانات قديمة عندها ارتباط
            # مش متغطّى بـ cascade) ويوري رسالة واضحة بدل ما الحذف "يفشل بصمت"
            ok = guarded_delete(
                accounts.delete_project, (current_user, project_id),
                t("معرفش أمسح المشروع ده — فيه بيانات قديمة فيه مرتبطة بحاجة تانية بشكل مش متوقع. قول لمهندس النظام."),
            )
            if ok:
                st.session_state.pop("project_selector", None)
                st.session_state.pop(f"confirm_delete_project_{project_id}", None)
                st.success(t("تم حذف المشروع"))
                st.rerun()
    else:
        st.caption(t("حذف مشروع لمدير المشروع بس."))


def _render_project_team(project_id, current_user):
    """أعضاء مساحة العمل، وقدام كل واحد "في المشروع ده". مدير المشروع
    والمشغّل بيشوفوا كل المشاريع دايمًا (الخانة مقفولة عليهم)."""
    st.subheader(f"👥 {t('أعضاء المشروع')}")
    try:
        team = accounts.project_team(current_user, project_id)
    except accounts.AccessDenied as exc:
        st.caption(str(exc))
        return
    others = [m for m in team["members"] if not m["sees_all"]]
    if not team["scoped"]:
        st.info(t("المشروع ده مفتوح لكل أعضاء مساحة العمل (اتعمل قبل ميزة أعضاء المشروع). "
                  "أول ما تحفظ اختيارك هنا، هيبقى للي تختارهم بس."))
    else:
        st.caption(t("اللي مش متعلّم عليه مش هيشوف المشروع ده خالص. مدير المشروع بيشوف كل المشاريع دايمًا."))
    if not others:
        st.caption(t("مفيش أعضاء تانيين في مساحة العمل لسه. ضيفهم من «إدارة الفريق» وبعدين اختارهم هنا."))
        return
    chosen = []
    for m in team["members"]:
        label = f"{m['display_name'] or m['username']} · {t(accounts.ROLE_LABELS.get(m['role'], m['role']))}"
        if m["sees_all"]:
            st.checkbox(label + f" — {t('بيشوف كل المشاريع')}", value=True, disabled=True,
                        key=f"pm_{project_id}_{m['username']}_all")
            continue
        if st.checkbox(label, value=m["in_project"], key=f"pm_{project_id}_{m['username']}"):
            chosen.append(m["username"])
    if st.button(f"💾 {t('حفظ أعضاء المشروع')}", key=f"pm_save_{project_id}", type="primary"):
        added, removed = accounts.set_project_team(current_user, project_id, chosen)
        st.toast(f"{t('اتضاف')} {len(added)} · {t('اتشال')} {len(removed)}", icon="👥")
        st.rerun()
