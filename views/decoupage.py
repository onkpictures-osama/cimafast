"""🎬 طاولة التقطيع — فوق فورم اللقطة في تبويب اللقطات (المالك 2026-09-25).

"المخرج لما يجي يحدد اللقطات ويعمل الدِكوباج لازم يكون شايف نص المشهد قدامه،
وشايف plan top angle للوكيشن والشخصيات محطوطة فين." يمين: نص المشهد (يختار
منه حتت ويعمل منها لقطة، ويشوف كل لقطة بتغطي إيه). شمال: الرسمة من فوق —
الديكور (مرة للمكان، افتراضية لكل حالاته) والشخصيات والكاميرات (لكل مشهد).
"""

import streamlit as st

import blocking
import plan_jobs
import repo
from i18n import t
from views.decoupage_components import plan_editor, script_panel
from views.looks import can_edit

# ألوان واضحة على الخلفية الغامقة، بالترتيب
_SHOT_COLORS = ["#ffc828", "#4fc3f7", "#f06292", "#81c784", "#ba68c8", "#ff8a65", "#4db6ac", "#e57373",
                "#aed581", "#9575cd", "#ffd54f", "#64b5f6"]
_CHAR_COLORS = ["#ff7043", "#26c6da", "#d4e157", "#ec407a", "#7e57c2", "#66bb6a", "#ffa726", "#29b6f6"]

# (النوع، الاسم، المقاس الافتراضي بوحدات الرسمة)
_KINDS = [("door", "باب", (90, 12)), ("window", "شباك", (120, 10)), ("wall", "حيطة", (200, 12)),
          ("table", "ترابيزة", (120, 80)), ("chair", "كرسي", (45, 45)), ("sofa", "كنبة", (200, 80)),
          ("bed", "سرير", (160, 200)), ("desk", "مكتب", (140, 70)), ("counter", "بار / كاونتر", (220, 60)),
          ("cabinet", "دولاب", (120, 55)), ("plant", "زرع", (50, 50)), ("car", "عربية", (180, 420)),
          ("block", "قطعة", (80, 60))]


def _labels():
    return {k: t(v) for k, v in {
        "all": "الكل", "dialogue": "الحوار بس", "action": "الوصف بس", "for_new": "لقطة جديدة",
        "for_shot": "تغطية لقطة", "make_shot": "➕ لقطة من المختار", "save_cover": "💾 احفظ التغطية",
        "clear": "إلغاء الاختيار", "no_text": "المشهد ده مالوش نص محفوظ.",
        "hint": "دوس على الجمل وسطور الحوار اللي اللقطة هتغطيها، وبعدين «لقطة من المختار». الخطوط الملوّنة جنب النص = اللقطات اللي بتغطيه.",
        "mode_block": "🎭 الشخصيات والكاميرات", "mode_decor": "🏠 الديكور", "save": "💾 احفظ الرسمة",
        "unsaved": "● فيه تعديل لسه ماتحفظش", "pen": "✏️ كروكي بالإيد", "undo_stroke": "↶ امسح آخر خط",
        "room": "مقاس المكان:", "place_chars": "🎭 حط الشخصيات:", "place_cams": "🎥 حط كاميرا كل لقطة:", "cam_of_shot": "كاميرا لقطة",
        "no_chars": "🎭 مفيش شخصيات مربوطة بالمشهد ده — اربطها من تبويب المشاهد.",
        "no_shots": "🎥 الكاميرات بتيجي من اللقطات: كل لقطة ليها كاميرا. اعمل لقطة الأول (اختار من النص «لقطة من المختار»، أو فورم «لقطة جديدة» تحت)، وزرار كاميرتها هيظهر هنا.",
        "all_cams_placed": "🎥 كل الكاميرات في الرسمة — دوس على كاميرا واسحبها، ولفّها بـ ⟲ ⟳ عشان المثلث يبص على اللي بتصوّره.",
        "label": "اسم", "move": "↝ حركة", "remove": "🗑️ شيل", "item": "قطعة", "shot": "لقطة",
        "hint_decor": "اسحب القطع لمكانها، ودوس على قطعة عشان تلفّها أو تكبّرها أو تسمّيها. «كروكي» = ارسم بإيدك.",
        "hint_block": "اسحب الشخصيات والكاميرات لمكانها. السهم الصغير = الشخصية باصّة فين. الكاميرا = المربع الملوّن برقم اللقطة، والمثلث قدامها = اللي بتصوّره. دوس على أي حاجة عشان تلفّها أو تشيلها، وبعدين «احفظ الرسمة».",
    }.items()}


def _short(name):
    parts = (name or "").split()
    return (parts[0][:2] if parts else "?")


def _plan_header(place, current):
    if not place:
        st.caption(f"⚠️ {t('المشهد ده مالوش مكان — حدد مكانه في تبويب المشاهد عشان رسمة الديكور تتحفظ للمكان.')}")
        return
    where = f"«{place['location']}»" + (f" — {place['variant']}" if place.get("variant") else "")
    if current is None:
        st.caption(f"📐 {where}: {t('لسه مفيش رسمة للمكان ده. ارسمها بإيدك من «الديكور»، أو خلّي الذكاء الاصطناعي يرسمها ليك.')}")
    elif current["is_default"]:
        tag = f" · 🤖 {t('رسمها الذكاء الاصطناعي — عدّلها براحتك')}" if current["source"] == "ai" else ""
        st.caption(f"📐 {where}: **{t('الرسمة الافتراضية للمكان')}** — {t('بتتطبق على كل حالاته')}{tag}")
    else:
        st.caption(f"📐 {where}: **{t('رسمة خاصة بالحالة دي')}**")


def _ai_box(project_id, scene_id, place, current, editable):
    """🤖 ارسمها لي: طلب في الطابور، والنتيجة بتتحفظ رسمة (source=ai) يعدّلها المستخدم."""
    if not (place and editable and plan_jobs.available()):
        return
    job = plan_jobs.latest(project_id, place["location_id"])
    state = (job or {}).get("state")
    if state in ("queued", "running"):
        st.caption(f"⏳ {t('الذكاء الاصطناعي بيرسم المكان… الصفحة هتتحدّث لوحدها.')}")
        _poll()
        return
    if state == "done" and not job.get("applied"):
        try:
            plan_jobs.apply(project_id, job)
            st.toast(f"🤖 {t('الرسمة وصلت — عدّلها براحتك')}")
            st.rerun()
        except ValueError as exc:
            st.warning(f"{t('الرسمة اللي رجعت مش سليمة')}: {exc}")
    if state == "failed" and not job.get("seen"):
        st.warning(f"❌ {t('الذكاء الاصطناعي ماعرفش يرسم المكان')}: {t(job.get('detail') or '')}")
        plan_jobs.mark_seen(job)
    replace = current is not None
    label = f"🤖 {t('ارسمها لي')}" if not replace else f"🤖 {t('ارسمها لي من جديد (بتستبدل الرسمة الافتراضية)')}"
    if st.button(label, key=f"dec_ai_{scene_id}"):
        try:
            plan_jobs.submit(project_id, place["location_id"], st.session_state.get("_auth_user"))
            st.rerun()
        except RuntimeError as exc:
            st.warning(str(exc))


@st.fragment(run_every=5)
def _poll():
    job = plan_jobs.latest(st.session_state.get("_cf_project"), st.session_state.get("_dec_poll_loc"))
    if job and job.get("state") in ("done", "failed"):
        st.rerun(scope="app")


def render(project_id, scene_id, notes, shots):
    editable = can_edit()
    blocks = blocking.script_blocks(notes)
    cov = blocking.coverage(blocks, [dict(s) for s in shots])
    shot_data = [{"id": s["id"], "number": s["shot_number"], "color": _SHOT_COLORS[i % len(_SHOT_COLORS)],
                  "blocks": sorted(blocking.parse_block_ids(s["script_blocks"])), "fov": blocking.fov_for(s["shot_size"])}
                 for i, s in enumerate(shots)]
    labels = _labels()
    lang_dir = "rtl" if st.session_state.get("ui_lang", "ar") == "ar" else "ltr"

    st.markdown(f"#### 🎬 {t('طاولة التقطيع')}")
    c_script, c_plan = st.columns([5, 6], gap="medium")
    with c_script:
        st.markdown(f"**📜 {t('نص المشهد')}**")
        res = script_panel({"scene_id": scene_id, "blocks": [{k: b[k] for k in ("i", "kind", "speaker", "text")} for b in blocks],
                            "coverage": {str(k): v for k, v in cov.items()}, "shots": shot_data, "labels": labels,
                            "editable": editable, "dir": lang_dir}, key=f"dec_script_{scene_id}")
        pick = res.get("pick") if res else None
        if pick and editable:
            ids = [int(i) for i in pick.get("ids") or []]
            if pick.get("target") == "new":
                st.session_state[f"dec_prefill_{scene_id}"] = ids
                st.info(f"⬇️ {t('فورم «لقطة جديدة» تحت اتعبّى بالنص اللي اخترته — كمّل الحجم والزاوية والحركة واحفظ.')}")
            else:
                repo.set_shot_blocks(project_id, int(pick["target"]), ids)
                st.toast(f"✅ {t('اتحفظت تغطية اللقطة')}")
                st.rerun()

    with c_plan:
        st.markdown(f"**📐 {t('الرسمة من فوق')}**")
        place = repo.scene_place(project_id, scene_id)
        st.session_state["_dec_poll_loc"] = place["location_id"] if place else None
        current = repo.location_plan(project_id, place["location_id"], place["variant_id"]) if place else None
        _plan_header(place, current)
        target = "default"
        if place and editable and place.get("variant_id"):
            options = ["default", "variant"]
            own = current is not None and not current["is_default"]
            target = st.radio(t("تعديل الديكور يتحفظ على:"), options, index=1 if own else 0, horizontal=True,
                              key=f"dec_target_{scene_id}",
                              format_func=lambda o: t("الرسمة الافتراضية (كل حالات المكان)") if o == "default"
                              else f"{t('الحالة دي بس')} ({place['variant']})")
            if own and st.button(f"↩ {t('رجّع الحالة دي للرسمة الافتراضية')}", key=f"dec_reset_{scene_id}"):
                repo.drop_variant_plan(project_id, place["location_id"], place["variant_id"])
                st.rerun()
        _ai_box(project_id, scene_id, place, current, editable)

        plan = current["plan"] if current else blocking.empty_plan()
        bl = repo.scene_blocking(project_id, scene_id) or blocking.empty_blocking()
        chars = [{"id": c["id"], "name": c["name"], "short": _short(c["name"]),
                  "color": _CHAR_COLORS[i % len(_CHAR_COLORS)]}
                 for i, c in enumerate(repo.scene_character_rows(project_id, scene_id))]
        res = plan_editor({"scene_id": scene_id, "plan": plan, "blocking": bl, "chars": chars, "shots": shot_data,
                           "labels": labels, "editable": editable, "can_edit_plan": editable and bool(place),
                           "kinds": [[k, t(n)] for k, n, _s in _KINDS], "kind_sizes": {k: s for k, _n, s in _KINDS},
                           "dir": lang_dir, "rev": st.session_state.get(f"dec_rev_{scene_id}", 0)},
                          key=f"dec_plan_{scene_id}")
        save = res.get("save") if res else None
        if save and editable:
            new_plan = blocking.clean_plan(save.get("plan")) or plan
            if save.get("plan_dirty") and place:
                variant = place["variant_id"] if target == "variant" else 0
                repo.save_location_plan(project_id, place["location_id"], variant, new_plan,
                                        updated_by=st.session_state.get("_auth_user"))
            repo.save_scene_blocking(project_id, scene_id, save.get("blocking"), new_plan)
            st.session_state[f"dec_rev_{scene_id}"] = st.session_state.get(f"dec_rev_{scene_id}", 0) + 1
            st.toast(f"✅ {t('اتحفظت الرسمة')}")
            st.rerun()
    return blocks
