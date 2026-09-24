"""شريط التقدّم فوق التبويبات — بيتبع المرحلة اللي اليوزر واقف فيها (المالك 2026-09-24).

- ما قبل الإنتاج: الخطوات الخمسة (المشروع ← الأماكن والشخصيات ← المشاهد ←
  اللقطات ← المراجعة).
- الإنتاج: حتة لكل يوم تصوير، بتتملي لما اليوم يتعلّم «اتصور».
- ما بعد الإنتاج: حتة لكل قسم (مونتاج، تلوين...) مليانة بنسبة إنجازه، والرقم
  الكبير = متوسط الأقسام.
"""

import streamlit as st

import post_production
import repo
from i18n import t, tr
from ui import ltr


def _seg(state, label, fill=None):
    """state: done / current / pending. fill: نسبة (0-100) لحتة مليانة جزئيًا."""
    inner = f'<span class="cf-progress-fill" style="width:{fill}%"></span>' if fill is not None else ""
    return f'<span class="cf-progress-seg cf-progress-seg--{state}" title="{label}">{inner}</span>'


def _bar(dir_, segments, headline, detail, dense=False):
    cls = "cf-progress-bar cf-progress-bar--dense" if dense else "cf-progress-bar"
    st.markdown(
        f'<div class="cf-progress" dir="{dir_}">'
        f'<div class="{cls}" aria-hidden="true">{"".join(segments)}</div>'
        f'<div class="cf-progress-text"><strong>{headline}</strong> — {detail}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _pre(dir_, project_id, c):
    stages = [tr("stage_project"), tr("stage_locations_chars"), tr("stage_scenes"),
              tr("stage_shots"), tr("stage_review")]
    done = [True, c["locations"] > 0 and c["characters"] > 0, c["scenes"] > 0, c["shots"] > 0,
            c["shots"] > 0 and c["confirmed"] == c["shots"]]
    current = next((i for i, d in enumerate(done) if not d), len(done) - 1)
    all_done = all(done)
    # السطر بيقول المرحلة الحالية وإيه اللي فاضل فيها بالأرقام
    if all_done:
        detail = t("كل اللقطات اتراجعت واتأكدت")
    elif current == 1:
        detail = f"{ltr(c['locations'])} {t('مكان')} · {ltr(c['characters'])} {t('شخصية')}"
    elif current == 2:
        detail = t("لسه مفيش مشاهد — ابدأ من «إضافة سيناريو»")
    elif current == 3:
        with_shots = repo.count_scenes_with_shots(project_id)[0]["c"]
        detail = f"{ltr(with_shots)} {t('من')} {ltr(c['scenes'])} {t('مشهد ليهم لقطات')}"
    else:
        detail = f"{ltr(c['confirmed'])} {t('من')} {ltr(c['shots'])} {t('لقطة اتراجعت')}"
    segs = [_seg("done" if d else ("current" if i == current else "pending"), lbl)
            for i, (lbl, d) in enumerate(zip(stages, done))]
    step = len(stages) if all_done else current + 1
    headline = f"{t('الخطوة')} {ltr(step)} {t('من')} {ltr(len(stages))} · {stages[step - 1]}"
    _bar(dir_, segs, headline, detail)


def _prod(dir_, project_id):
    days = repo.shooting_days(project_id)
    p = repo.production_progress(project_id)
    if not days:
        _bar(dir_, [_seg("pending", "")], t("التصوير لسه مابدأش"),
             t("مفيش أيام تصوير — اعمل الأيام من «افتح جدول التصوير»"))
        return
    first_open = next((i for i, d in enumerate(days) if not d["shot_done"]), None)
    segs = [_seg("done" if d["shot_done"] else ("current" if i == first_open else "pending"),
                 f"{t('يوم')} {d['day_number']}") for i, d in enumerate(days)]
    pct = round(100 * p["days_shot"] / p["days"]) if p["days"] else 0
    headline = f"{t('التصوير')} {ltr(pct)}% · {ltr(p['days_shot'])} {t('من')} {ltr(p['days'])} {t('يوم تصوير')}"
    detail = f"{ltr(p['scenes_shot'])} {t('من')} {ltr(p['scenes'])} {t('مشهد اتصور')}"
    _bar(dir_, segs, headline, detail, dense=len(days) > 30)


def _post(dir_, project_id):
    s = post_production.summary(repo.post_departments(project_id))
    segs = []
    for i in s["items"]:
        label = f"{t(i['name'])} {i['progress']}%"
        if i["progress"] >= 100:
            segs.append(_seg("done", label))
        else:
            segs.append(_seg("pending", label, fill=i["progress"] if i["progress"] else None))
    headline = f"{t('ما بعد الإنتاج')} {ltr(s['overall'])}%"
    detail = f"{ltr(s['approved'])} {t('من')} {ltr(s['total'])} {t('قسم معتمد')}"
    stale = [i for i in s["items"] if i["stale"]]
    if stale:
        detail += f" · ⚠️ {ltr(len(stale))} {t('قسم ماتحدّثش من أسبوع')}"
    _bar(dir_, segs, headline, detail)


def render(dir_, project_id, counts):
    phase = st.session_state.get("_cf_phase", "pre")
    if phase == "prod":
        _prod(dir_, project_id)
    elif phase == "post":
        _post(dir_, project_id)
    else:
        _pre(dir_, project_id, counts)
