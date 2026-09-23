"""طبقة البيانات: كل استعلام بيتكلم مع قاعدة البيانات في مكان واحد.

الموديول ده مش بيستورد Streamlit. هو اللي بيربط الواجهتين بنفس البيانات:
الواجهة القديمة (views/*) والواجهة الجديدة (board/). أي استعلام جديد يتكتب هنا
كدالة باسم بيقول هو بيعمل إيه، مش جوه كود الشاشة.

قواعد:
- الدوال بترجع dicts/lists عادية، مش sqlite3.Row.
- مفيش SQL بيتبني بلصق نصوص من المستخدم — كل القيم parameters.
- أي كتابة متعددة الخطوات بتحصل في transaction واحدة (_tx).
"""

from __future__ import annotations

import datetime as dt
import re
from contextlib import contextmanager

import audit
import permissions
from database import DEFAULT_LOOK_NAME, IntegrityError, _adapt_query, fetch_all, get_connection, run_query, scene_label
from search import normalize

NIGHT_VALUES = {"ليل"}              # فجر وغروب بيتصوروا في يوم النهار عادةً


@contextmanager
def _tx():
    """اتصال واحد وtransaction واحدة: يا كله يتحفظ يا ولا حاجة.

    F3: كل جملة بتعدّي على السجل (audit.watch/record) على نفس الـ cursor، يعني
    صف السجل بيتحفظ مع التغيير أو بيترجع معاه.
    """
    permissions.require("edit")
    conn = get_connection()
    try:
        cur = conn.cursor()

        def _execute(q, p=()):
            token = audit.watch(cur, q, p)
            result = cur.execute(_adapt_query(q), p)
            audit.record(cur, token)
            return result

        yield _execute
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# --- المشاريع -----------------------------------------------------------------

# مفيش دالة هنا بترجّع "كل المشاريع". أي قايمة مشاريع بتيجي من
# accounts.projects_for(username) — اللي بيفلتر بشركات المستخدم. الدوال القديمة
# projects() وall_projects_newest_first() وadd_project() (من غير company_id)
# اتشالت: كانت ميتة بس أي شاشة جديدة كانت ممكن توصّلها وترجّع مشاريع شركة تانية.


def project(project_id):
    rows = fetch_all("SELECT * FROM projects WHERE id=?", (project_id,))
    return rows[0] if rows else None


# --- المكان الفعلي ----------------------------------------------------------------

# مدن بتظهر كجزء من اسم المكان («شقة حسين - القاهرة - المدخل»). بتتقارن بعد
# التوحيد (أ/إ/ا، «ال» في الأول)، فـ«اسكندرية» و«الإسكندرية» واحد.
CITIES = {
    "القاهرة", "الإسكندرية", "الجيزة", "بورسعيد", "السويس", "الإسماعيلية", "الأقصر", "أسوان",
    "طنطا", "المنصورة", "الغردقة", "شرم الشيخ", "دمياط", "الفيوم", "المنيا", "أسيوط", "سوهاج",
    "مرسى مطروح", "الساحل الشمالي", "العين السخنة", "دهب", "الزقازيق", "بنها", "قنا",
}


def _city_key(text):
    k = normalize(text)
    return k[2:] if k.startswith("ال") else k


_CITY_KEYS = {_city_key(c): c for c in CITIES}
# المدينة ككلمة كاملة في أي حتة من الاسم، بـ«ال» أو من غيرها: «كورنيش الإسكندرية»
# زي «شقة حسين - الإسكندرية». النسخة الأولى كانت بتدوّر على جزء مستقل بعد « - »
# بس، ففاتها «كورنيش الإسكندرية» واتحط في نفس يوم شقة في القاهرة.
_CITY_RE = re.compile(
    r"(?<!\w)(?P<pre>طريق\s+)?(?:ال)?(?P<city>" + "|".join(
        re.escape(k) for k in sorted(_CITY_KEYS, key=len, reverse=True)) + r")(?!\w)")


def city_of(location_name):
    """المدينة اللي المكان فيها لو الاسم بيقولها، وإلا None.

    «طريق اسكندرية» مش مكان في إسكندرية — ده الطريق ليها — فمش بيتحسب.
    """
    for m in _CITY_RE.finditer(normalize(location_name)):
        if not m.group("pre"):
            return _CITY_KEYS[m.group("city")]
    return None


def site_of(location_name, parent_name=None):
    """المكان اللي الفريق بيروحه فعلًا، مش الأوضة.

    لو المكان تابع لمكان رئيسي، الرئيسي هو الموقع. غير كده الجزء الأول من الاسم
    ومعاه المدينة لو مذكورة في أي حتة: «شقة حسين - القاهرة - المدخل» →
    «شقة حسين - القاهرة». المدينة مهمة: من غيرها شقة حسين في القاهرة وشقة حسين
    في إسكندرية كانوا بيطلعوا موقع واحد — يعني تنقّل بين محافظتين في يوم.
    ده تقريب لحد ما يبقى فيه أداة دمج الأماكن: 0 من 99 مكان بيستخدموا
    parent_location_id النهارده والأسماء نفسها هي اللي شايلة التقسيمة.
    """
    if parent_name:
        return parent_name.strip()
    head = (location_name or "").split(" - ")[0].strip() or "—"
    city = city_of(location_name)
    if not city or city_of(head) == city:          # «كورنيش الإسكندرية» فيه المدينة أصلًا
        return head
    return f"{head} - {city}"


# --- المشاهد للجدول -------------------------------------------------------------

def board_scenes(project_id):
    """كل مشاهد المشروع بالبيانات اللي الـ strip محتاجها."""
    rows = fetch_all(
        """
        SELECT s.id, s.scene_number, s.scene_suffix, s.int_ext, s.day_night, s.episode_number,
               s.notes, l.name AS location_name, p.name AS parent_name, lv.variant_name
        FROM scenes s
        LEFT JOIN location_variants lv ON lv.id = s.location_variant_id
        LEFT JOIN locations l ON l.id = lv.location_id
        LEFT JOIN locations p ON p.id = l.parent_location_id
        WHERE s.project_id = ?
        ORDER BY s.scene_number, s.scene_suffix
        """,
        (project_id,),
    )
    cast = {}
    for r in fetch_all(
        """
        SELECT sc.scene_id, c.id AS character_id, c.name
        FROM scene_characters sc
        JOIN characters c ON c.id = sc.character_id
        JOIN scenes s ON s.id = sc.scene_id
        WHERE s.project_id = ?
        ORDER BY c.id
        """,
        (project_id,),
    ):
        cast.setdefault(r["scene_id"], []).append({"id": r["character_id"], "name": r["name"]})
    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "label": scene_label(r),
            "int_ext": r["int_ext"] or "",
            "day_night": r["day_night"] or "",
            "night": (r["day_night"] or "") in NIGHT_VALUES,
            "location": r["location_name"] or "",
            "site": site_of(r["location_name"], r["parent_name"]) if r["location_name"] else "—",
            "city": city_of(r["location_name"]),
            "episode": r["episode_number"],
            "cast": cast.get(r["id"], []),
            "notes_len": len(r["notes"] or ""),
        })
    return out


# --- الصفحة الرئيسية (H1) -------------------------------------------------------------

def project_overview(project_id):
    """كل الأرقام اللي كارت المشروع و"محتاجك" بيحتاجوها، في استعلام واحد."""
    rows = fetch_all("""
        SELECT
          (SELECT COUNT(*) FROM locations WHERE project_id=:p) AS locations,
          (SELECT COUNT(*) FROM characters WHERE project_id=:p) AS characters,
          (SELECT COUNT(*) FROM props WHERE project_id=:p) AS props,
          (SELECT COUNT(*) FROM scenes WHERE project_id=:p) AS scenes,
          (SELECT COUNT(*) FROM shots sh JOIN scenes s ON s.id=sh.scene_id WHERE s.project_id=:p) AS shots,
          (SELECT COUNT(*) FROM shots sh JOIN scenes s ON s.id=sh.scene_id
             WHERE s.project_id=:p AND COALESCE(sh.confirmed,0)=1) AS confirmed_shots,
          (SELECT COUNT(*) FROM scenes s WHERE s.project_id=:p
             AND EXISTS (SELECT 1 FROM shots sh WHERE sh.scene_id=s.id)) AS scenes_with_shots,
          (SELECT COUNT(*) FROM scenes s WHERE s.project_id=:p
             AND COALESCE(s.suggested_shot_size,'')<>'') AS scenes_with_ai_shot_hint,
          (SELECT COUNT(*) FROM locations WHERE project_id=:p
             AND COALESCE(reference_image_path,'')='') AS locations_without_image,
          (SELECT COUNT(*) FROM characters WHERE project_id=:p
             AND COALESCE(reference_image_path,'')='') AS characters_without_image,
          (SELECT COUNT(*) FROM characters c WHERE c.project_id=:p
             AND NOT EXISTS (SELECT 1 FROM character_looks l WHERE l.character_id=c.id)) AS characters_without_look,
          (SELECT COUNT(*) FROM scenes WHERE project_id=:p
             AND COALESCE(look_change_notes,'')<>'') AS scenes_with_look_change,
          (SELECT COUNT(*) FROM shooting_days WHERE project_id=:p) AS days,
          (SELECT COUNT(*) FROM shooting_days WHERE project_id=:p
             AND COALESCE(shoot_date,'')='') AS days_without_date,
          (SELECT COUNT(*) FROM shooting_day_scenes x JOIN shooting_days d ON d.id=x.day_id
             WHERE d.project_id=:p) AS scheduled_scenes
    """.replace(":p", "?"), (project_id,) * 15)
    return dict(rows[0])


def last_screen(username):
    rows = fetch_all("SELECT last_project_id, last_tab, updated_at FROM user_profile WHERE username=?",
                     (username,))
    return dict(rows[0]) if rows else None


def remember_screen(username, project_id, tab, when):
    """آخر شاشة فتحها المستخدم. كتابة نظام مش تعديل بيانات — المشاهد كمان
    ليه "كمّل من مكان ما وقفت"، فمش بتتقفل بصلاحية edit."""
    with permissions.system(), _tx() as ex:
        ex("DELETE FROM user_profile WHERE username=?", (username,))
        ex("INSERT INTO user_profile (username, last_project_id, last_tab, updated_at) VALUES (?, ?, ?, ?)",
           (username, project_id, tab, when))


# --- أيام التصوير ------------------------------------------------------------------

def shooting_days(project_id):
    return fetch_all(
        "SELECT id, day_number, shoot_date, notes FROM shooting_days WHERE project_id=? ORDER BY day_number, id",
        (project_id,),
    )


def board(project_id):
    """الجدول كامل: الأيام بترتيبها، كل يوم بمشاهده بترتيبها، والمشاهد اللي لسه مالهاش يوم."""
    scenes = {s["id"]: s for s in board_scenes(project_id)}
    days = [dict(d, scene_ids=[]) for d in shooting_days(project_id)]
    by_id = {d["id"]: d for d in days}
    placed = set()
    for r in fetch_all(
        """
        SELECT ds.day_id, ds.scene_id FROM shooting_day_scenes ds
        JOIN shooting_days d ON d.id = ds.day_id
        WHERE d.project_id = ? ORDER BY ds.day_id, ds.position, ds.id
        """,
        (project_id,),
    ):
        if r["scene_id"] in scenes and r["day_id"] in by_id:
            by_id[r["day_id"]]["scene_ids"].append(r["scene_id"])
            placed.add(r["scene_id"])
    unscheduled = [sid for sid in scenes if sid not in placed]
    return {"scenes": scenes, "days": days, "unscheduled": unscheduled}


def add_day(project_id):
    rows = fetch_all("SELECT COALESCE(MAX(day_number), 0) AS n FROM shooting_days WHERE project_id=?",
                     (project_id,))
    number = rows[0]["n"] + 1
    run_query("INSERT INTO shooting_days (project_id, day_number) VALUES (?, ?)", (project_id, number))
    return number


def delete_day(project_id, day_id):
    """بيمسح اليوم؛ مشاهده بترجع «مش متجدولة» (ON DELETE CASCADE على الربط بس)."""
    with _tx() as ex:
        ex("DELETE FROM shooting_day_scenes WHERE day_id=? AND day_id IN "
           "(SELECT id FROM shooting_days WHERE project_id=?)", (day_id, project_id))
        ex("DELETE FROM shooting_days WHERE id=? AND project_id=?", (day_id, project_id))
    _renumber_days(project_id)


def _renumber_days(project_id):
    with _tx() as ex:
        for i, d in enumerate(shooting_days(project_id), start=1):
            ex("UPDATE shooting_days SET day_number=? WHERE id=?", (i, d["id"]))


def update_day(project_id, day_id, shoot_date=None, notes=None):
    run_query("UPDATE shooting_days SET shoot_date=?, notes=? WHERE id=? AND project_id=?",
              (shoot_date or None, notes or None, day_id, project_id))


class LayoutError(ValueError):
    pass


def save_layout(project_id, layout):
    """بيحفظ ترتيب الجدول كله مرة واحدة.

    layout = [{"day_id": 3, "scene_ids": [12, 7, ...]}, ...] — بترتيب الأيام.
    أي مشهد مش موجود في أي يوم بيبقى «مش متجدول». كل الأيام والمشاهد لازم
    تكون تبع المشروع ده، ومشهد مايظهرش في يومين؛ غير كده مفيش حاجة بتتحفظ.
    """
    own_days = {d["id"] for d in shooting_days(project_id)}
    own_scenes = {r["id"] for r in fetch_all("SELECT id FROM scenes WHERE project_id=?", (project_id,))}
    seen = set()
    for entry in layout:
        if entry.get("day_id") not in own_days:
            raise LayoutError(f"day {entry.get('day_id')} is not in this project")
        for sid in entry.get("scene_ids", []):
            if sid not in own_scenes:
                raise LayoutError(f"scene {sid} is not in this project")
            if sid in seen:
                raise LayoutError(f"scene {sid} appears twice")
            seen.add(sid)
    with _tx() as ex:
        ex("DELETE FROM shooting_day_scenes WHERE day_id IN "
           "(SELECT id FROM shooting_days WHERE project_id=?)", (project_id,))
        for number, entry in enumerate(layout, start=1):
            ex("UPDATE shooting_days SET day_number=? WHERE id=?", (number, entry["day_id"]))
            for pos, sid in enumerate(entry.get("scene_ids", [])):
                ex("INSERT INTO shooting_day_scenes (day_id, scene_id, position) VALUES (?, ?, ?)",
                   (entry["day_id"], sid, pos))


# --- اقتراح جدول ------------------------------------------------------------------

def suggest_layout(project_id, per_day=8, sites_per_day=2):
    """اقتراح أولي، مش قرار — نقطة بداية بيعدّلها الإنسان بالسحب.

    القواعد اللي أي مدير إنتاج بيبدأ بيها:
    - نهار وليل مايتخلطوش في نفس اليوم.
    - الموقع الواحد بيتصوّر ورا بعضه، والنهار قبل الليل.
    - مسموح بتنقّل (company move) لحد sites_per_day مواقع في اليوم، بس جوه نفس
      المدينة. من غير التنقّل، 76 مكان مستخدمين في مشهد واحد كانوا بيعملوا 58 يوم
      تصوير لـ 143 مشهد — يوم لكل مشهد تقريبًا.
    - سقف per_day مشهد في اليوم.
    المواقع اللي فيها مشاهد أكتر بتتحط الأول عشان الأيام الكبيرة تتثبت بدري.
    """
    per_day = max(1, min(int(per_day or 8), 40))
    sites_per_day = max(1, min(int(sites_per_day or 2), 6))
    groups = {}
    for s in board_scenes(project_id):
        groups.setdefault((s["night"], s["site"]), []).append(s)
    size = {}
    for (_, site), items in groups.items():
        size[site] = size.get(site, 0) + len(items)

    days = []
    for night in (False, True):
        # المدينة الأول عشان مواقعها تبقى جنب بعض وتقدر تتجمع في يوم؛ المواقع اللي
        # مدينتها مش معروفة في الآخر (بتتجمع مع أي يوم). جوه المدينة الأكبر الأول.
        city_of_site = {k[1]: groups[k][0]["city"] for k in groups}
        keys = sorted((k for k in groups if k[0] == night),
                      key=lambda k: (city_of_site[k[1]] is None, city_of_site[k[1]] or "", -size[k[1]], k[1]))
        day, day_sites, day_city = [], [], None
        for key in keys:
            items = groups[key]
            city = items[0]["city"]
            while items:
                room = per_day - len(day)
                compatible = (day_city is None or city is None or city == day_city)
                if room == 0 or len(day_sites) >= sites_per_day or not compatible or \
                        (day and len(items) > room and len(items) <= per_day):
                    # يوم جديد: اليوم الحالي مليان، أو وصل لأقصى تنقّلات، أو مدينة
                    # تانية، أو الموقع ده يتصوّر كامل في يوم لوحده أحسن ما يتقسم.
                    if day:
                        days.append(day)
                    day, day_sites, day_city = [], [], None
                    continue
                take, items = items[:room], items[room:]
                day.extend(s["id"] for s in take)
                day_sites.append(key[1])
                day_city = day_city or city
        if day:
            days.append(day)
    return days


def apply_suggestion(project_id, per_day=8, sites_per_day=2):
    """بيستبدل الجدول الحالي بالاقتراح: بيمسح الأيام ويعمل أيام جديدة."""
    proposal = suggest_layout(project_id, per_day, sites_per_day)
    with _tx() as ex:
        ex("DELETE FROM shooting_day_scenes WHERE day_id IN "
           "(SELECT id FROM shooting_days WHERE project_id=?)", (project_id,))
        ex("DELETE FROM shooting_days WHERE project_id=?", (project_id,))
    for number, scene_ids in enumerate(proposal, start=1):
        run_query("INSERT INTO shooting_days (project_id, day_number) VALUES (?, ?)", (project_id, number))
    days = shooting_days(project_id)
    save_layout(project_id, [{"day_id": d["id"], "scene_ids": ids} for d, ids in zip(days, proposal)])
    return len(proposal)


# --- أيام شغل كل ممثل (Day Out of Days) -------------------------------------------

def day_out_of_days(project_id):
    """مين بيشتغل أي يوم، بالرموز القياسية.

    SW = أول يوم شغل، WF = آخر يوم، SWF = يوم وحيد، W = شغل، H = انتظار
    (يوم بين أول وآخر يوم للممثل مش مطلوب فيه — بيتدفع غالبًا).
    """
    b = board(project_id)
    days = b["days"]
    working = {}
    names = {}
    for idx, d in enumerate(days):
        for sid in d["scene_ids"]:
            for c in b["scenes"][sid]["cast"]:
                working.setdefault(c["id"], set()).add(idx)
                names[c["id"]] = c["name"]
    rows = []
    for cid, idxs in working.items():
        first, last = min(idxs), max(idxs)
        codes = []
        for i in range(len(days)):
            if i in idxs:
                codes.append("SWF" if first == last else "SW" if i == first else "WF" if i == last else "W")
            elif first < i < last:
                codes.append("H")
            else:
                codes.append("")
        rows.append({"character_id": cid, "name": names[cid], "codes": codes,
                     "work_days": len(idxs), "hold_days": codes.count("H"),
                     "first_day": first + 1, "last_day": last + 1})
    rows.sort(key=lambda r: (-r["work_days"], r["first_day"], r["name"]))
    return {"days": [d["day_number"] for d in days], "rows": rows}


# ----------------------------------------------------------------------------
# الاستعلامات اللي كانت مكتوبة جوه شاشات Streamlit (views/*, ui.py, app.py).
# كل دالة هنا بتشغّل نفس الـ SQL بالظبط اللي كان في الشاشة، بنفس الـ parameters —
# النقل ميكانيكي ومتحقق منه. أي شاشة جديدة تستعمل الدوال دي أو تضيف دالة، مش SQL.
#
# **العزل بين المشاريع في طبقة البيانات نفسها.** أي UPDATE أو DELETE على مشهد
# أو لقطة أو شخصية أو مكان أو إكسسوار (وحالاتهم وارتباطاتهم) بياخد project_id
# كأول باراميتر وبيربطه في شرط WHERE — بالظبط زي update_day/delete_day فوق.
# الجداول اللي مفيهاش project_id (shots, character_looks, location_variants،
# وجداول الربط) بتوصل للمشروع بـ subquery على أبوها، زي ما count_shots بتعمل.
#
# ليه، والشاشات أصلًا بتجيب الـ id من استعلام مفلتر بالمشروع؟ عشان ده يفضل
# صح من غير ما نعتمد على إن كل شاشة جديدة هتفضل تعمل كده. رقم غلط (باج، لينك
# قديم، شاشة بتاخد id من الطلب) بيعدّل صفر صفوف بدل ما يلمس بيانات شركة تانية.
#
# الإنشاء (add_shot / add_character_look / add_location_state) سايب زي ما هو
# عن قصد: بيرجّع الـ id بتاع الصف الجديد اللي الشاشة بتكمّل بيه، و«مفيش صف
# اتضاف» كان هيبقى فشل صامت. الأب بتاعه جاي أصلًا من قايمة مفلترة بالمشروع.
# جداول الربط بترجّع حاجة محدش بيستعملها، فدي اتقفلت بـ EXISTS على الطرفين.
# ----------------------------------------------------------------------------


def project_by_id(*params):
    return fetch_all('SELECT * FROM projects WHERE id=?', params)


def episodes_of_project(*params):
    return fetch_all('SELECT * FROM episodes WHERE project_id=? ORDER BY episode_number', params)


def delete_project(*params):
    """المسح نفسه. الفحص إن المشروع تبع شركة المستخدم بيحصل في
    accounts.delete_project — الشاشات بتنده دي هي، مش الدالة دي."""
    permissions.require("delete_project")
    return run_query('DELETE FROM projects WHERE id=?', params)


def count_locations(*params):
    return fetch_all('SELECT COUNT(*) c FROM locations WHERE project_id=?', params)


def count_characters(*params):
    return fetch_all('SELECT COUNT(*) c FROM characters WHERE project_id=?', params)


def count_scenes(*params):
    return fetch_all('SELECT COUNT(*) c FROM scenes WHERE project_id=?', params)


def count_shots(*params):
    return fetch_all('SELECT COUNT(*) c FROM shots sh JOIN scenes s ON sh.scene_id=s.id WHERE s.project_id=?', params)


def count_confirmed_shots(*params):
    return fetch_all('SELECT COUNT(*) c FROM shots sh JOIN scenes s ON sh.scene_id=s.id WHERE s.project_id=? AND sh.confirmed=1', params)


def count_scenes_with_shots(*params):
    return fetch_all('SELECT COUNT(DISTINCT s.id) c FROM scenes s JOIN shots sh ON sh.scene_id=s.id WHERE s.project_id=?', params)


def update_project_settings(*params):
    return run_query('UPDATE projects SET name=?, project_type=?, default_resolution=?, default_orientation=?, default_aspect_ratio=? WHERE id=?', params)


def update_project_owner(*params):
    return run_query('UPDATE projects SET owner_name=?, owner_role=? WHERE id=?', params)


def add_episode(*params):
    return run_query('INSERT INTO episodes (project_id, episode_number, title, description) VALUES (?,?,?,?)', params)


def delete_episode(project_id, *params):
    return run_query('DELETE FROM episodes WHERE id=? AND project_id=?', params + (project_id,))


def bump_project_data_version(*params):
    return run_query('UPDATE projects SET data_version = COALESCE(data_version, 1) + 1 WHERE id=?', params)


def shift_scene_numbers_up_except(*params):
    return run_query('UPDATE scenes SET scene_number = scene_number + 1 WHERE project_id=? AND scene_number >= ? AND id != ?', params)


def shift_scene_numbers_up(*params):
    return run_query('UPDATE scenes SET scene_number = scene_number + 1 WHERE project_id=? AND scene_number >= ?', params)


def shift_shot_numbers_up_except(project_id, *params):
    return run_query('UPDATE shots SET shot_number = shot_number + 1 WHERE scene_id=? AND shot_number >= ? AND id != ? '
                     'AND scene_id IN (SELECT id FROM scenes WHERE project_id=?)', params + (project_id,))


def shift_shot_numbers_up(project_id, *params):
    return run_query('UPDATE shots SET shot_number = shot_number + 1 WHERE scene_id=? AND shot_number >= ? '
                     'AND scene_id IN (SELECT id FROM scenes WHERE project_id=?)', params + (project_id,))


def character_ids_of_project(*params):
    return fetch_all('SELECT id FROM characters WHERE project_id=?', params)


def characters_of_project(*params):
    return fetch_all('SELECT * FROM characters WHERE project_id=?', params)


def looks_of_character(*params):
    # P5: المظهر الأساسي الأول دايمًا، وبعده الباقي بترتيب الإضافة
    return fetch_all('SELECT * FROM character_looks WHERE character_id=? '
                     'ORDER BY COALESCE(is_default, 0) DESC, id', params)


def add_character(project_id, name, role_type, species, gender, personality_notes):
    """شخصية جديدة + مظهرها الأساسي، زي الاستيراد بالظبط (P5).

    من غير المظهر ده الشخصية المضافة باليد مكانتش بتظهر في اختيار شخصيات
    اللقطة خالص. لو المظهر وقع لأي سبب، database._backfill_default_looks
    بتكمّله مع أول تشغيل."""
    char_id = run_query("""INSERT INTO characters
                        (project_id, name, role_type, species, gender, personality_notes)
                        VALUES (?,?,?,?,?,?)""",
                        (project_id, name, role_type, species, gender, personality_notes))
    run_query("""INSERT INTO character_looks
                 (character_id, look_name, apparent_age, makeup_state, hair_state, wardrobe_description, description, is_default)
                 VALUES (?,?,?,?,?,?,?,1)""",
              (char_id, DEFAULT_LOOK_NAME, '', '', '', '', ''))
    return char_id


def add_character_look(*params):
    # P5: لو دي أول مظهر للشخصية (مفروض مايحصلش بعد الـ backfill) يبقى هو الأساسي
    return run_query("""INSERT INTO character_looks
                        (character_id, look_name, apparent_age, makeup_state, hair_state, wardrobe_description, description, reference_image_path, is_default)
                        VALUES (?,?,?,?,?,?,?,?,
                                CASE WHEN EXISTS (SELECT 1 FROM character_looks WHERE character_id=?) THEN 0 ELSE 1 END)""",
                     tuple(params) + (params[0],))


class LastLookError(IntegrityError):
    """P5: آخر مظهر للشخصية مينفعش يتمسح — من غيره الشخصية بتختفي من اللقطات.
    فرع من IntegrityError عشان ui.guarded_delete يمسكه ويوري الرسالة دي."""
    user_message = "ده المظهر الوحيد للشخصية، ومينفعش تفضل من غير مظهر. ضيف مظهر تاني الأول لو عايز تمسحه، أو امسح الشخصية نفسها."

    def __init__(self):
        super().__init__(self.user_message)


def set_default_look(project_id, look_id):
    """P5: يخلّي المظهر ده هو الأساسي لشخصيته، والباقي يبطل أساسي — جملة واحدة."""
    return run_query(
        'UPDATE character_looks SET is_default = CASE WHEN id=? THEN 1 ELSE 0 END '
        'WHERE character_id = (SELECT character_id FROM character_looks WHERE id=?) '
        'AND character_id IN (SELECT id FROM characters WHERE project_id=?)',
        (look_id, look_id, project_id))


def delete_character(project_id, *params):
    return run_query('DELETE FROM characters WHERE id=? AND project_id=?', params + (project_id,))


def set_character_image(project_id, *params):
    return run_query('UPDATE characters SET reference_image_path=? WHERE id=? AND project_id=?',
                     params + (project_id,))


def update_character(project_id, *params):
    return run_query("""UPDATE characters SET name=?, role_type=?, species=?, gender=?,
                            personality_notes=?, reference_image_path=?
                        WHERE id=? AND project_id=?""", params + (project_id,))


def set_character_look_image(project_id, *params):
    return run_query('UPDATE character_looks SET reference_image_path=? WHERE id=? '
                     'AND character_id IN (SELECT id FROM characters WHERE project_id=?)', params + (project_id,))


def update_character_look(project_id, *params):
    return run_query("""UPDATE character_looks SET look_name=?, apparent_age=?, makeup_state=?,
                            hair_state=?, wardrobe_description=?, description=?, reference_image_path=?
                        WHERE id=? AND character_id IN (SELECT id FROM characters WHERE project_id=?)""",
                     params + (project_id,))


def delete_character_look(project_id, look_id):
    """P5: آخر مظهر مبيتمسحش (LastLookError). لو المظهر الممسوح كان الأساسي،
    أقدم مظهر فاضل بياخد مكانه في نفس الـ transaction."""
    rows = fetch_all(
        'SELECT cl.character_id, (SELECT COUNT(*) FROM character_looks x WHERE x.character_id = cl.character_id) AS n '
        'FROM character_looks cl JOIN characters c ON c.id = cl.character_id '
        'WHERE cl.id=? AND c.project_id=?', (look_id, project_id))
    if not rows:
        return None
    if rows[0]["n"] <= 1:
        raise LastLookError()
    character_id = rows[0]["character_id"]
    with _tx() as ex:
        ex('DELETE FROM character_looks WHERE id=? '
           'AND character_id IN (SELECT id FROM characters WHERE project_id=?)', (look_id, project_id))
        ex('UPDATE character_looks SET is_default = 1 '
           'WHERE id = (SELECT MIN(id) FROM character_looks WHERE character_id=?) '
           'AND NOT EXISTS (SELECT 1 FROM character_looks WHERE character_id=? AND COALESCE(is_default, 0) = 1) '
           'AND character_id IN (SELECT id FROM characters WHERE project_id=?)',
           (character_id, character_id, project_id))
    return None


def character_names_of_project(*params):
    return fetch_all('SELECT name FROM characters WHERE project_id=?', params)


def locations_of_project(*params):
    return fetch_all('SELECT * FROM locations WHERE project_id=?', params)


def states_of_location(*params):
    return fetch_all('SELECT * FROM location_variants WHERE location_id=?', params)


def add_location(*params):
    return run_query('INSERT INTO locations (project_id, name, base_description, parent_location_id, maps_url) VALUES (?,?,?,?,?)', params)


def set_location_image(project_id, *params):
    return run_query('UPDATE locations SET reference_image_path=? WHERE id=? AND project_id=?',
                     params + (project_id,))


def delete_location(project_id, *params):
    return run_query('DELETE FROM locations WHERE id=? AND project_id=?', params + (project_id,))


def update_location(project_id, *params):
    return run_query('UPDATE locations SET name=?, base_description=?, parent_location_id=?, maps_url=? '
                     'WHERE id=? AND project_id=?', params + (project_id,))


def set_location_maps_url(project_id, *params):
    return run_query('UPDATE locations SET maps_url=? WHERE id=? AND project_id=?', params + (project_id,))


def update_location_state(project_id, variant_name, description, location_id, variant_id):
    """تعديل حالة مكان، ونقلها لمكان تاني لو اليوزر غيّر المكان.

    الاتنين لازم يكونوا في نفس المشروع: المكان اللي الحالة فيه دلوقتي، والمكان
    اللي رايحة له. من غير الشرط التاني رقم مكان من مشروع تاني كان هياخد الحالة.
    """
    return run_query(
        'UPDATE location_variants SET variant_name=?, description=?, location_id=? WHERE id=? '
        'AND location_id IN (SELECT id FROM locations WHERE project_id=?) '
        'AND ? IN (SELECT id FROM locations WHERE project_id=?)',
        (variant_name, description, location_id, variant_id, project_id, location_id, project_id))


def delete_location_state(project_id, *params):
    return run_query('DELETE FROM location_variants WHERE id=? '
                     'AND location_id IN (SELECT id FROM locations WHERE project_id=?)', params + (project_id,))


def set_location_state_image(project_id, *params):
    return run_query('UPDATE location_variants SET reference_image_path=? WHERE id=? '
                     'AND location_id IN (SELECT id FROM locations WHERE project_id=?)', params + (project_id,))


def add_location_state(*params):
    return run_query('INSERT INTO location_variants (location_id, variant_name, description) VALUES (?,?,?)', params)


def characters_of_project_by_id(*params):
    return fetch_all('SELECT * FROM characters WHERE project_id=? ORDER BY id', params)


def prop_ids_of_project(*params):
    return fetch_all('SELECT id FROM props WHERE project_id=?', params)


def props_of_project(*params):
    return fetch_all('SELECT * FROM props WHERE project_id=? ORDER BY id', params)


def add_prop(*params):
    return run_query('INSERT INTO props (project_id, name, continuity_sensitive, character_id) VALUES (?,?,?,?)', params)


def delete_prop(project_id, *params):
    return run_query('DELETE FROM props WHERE id=? AND project_id=?', params + (project_id,))


def update_prop(project_id, *params):
    return run_query('UPDATE props SET name=?, continuity_sensitive=?, character_id=? WHERE id=? AND project_id=?',
                     params + (project_id,))


def shot_summaries_of_project(*params):
    return fetch_all("""
        SELECT s.scene_number, sh.shot_number, sh.shot_size, sh.camera_movement, sh.confirmed
        FROM shots sh JOIN scenes s ON sh.scene_id = s.id
        WHERE s.project_id = ? ORDER BY s.scene_number, sh.shot_number
    """, params)


def scenes_without_shots(*params):
    return fetch_all('SELECT s.* FROM scenes s WHERE s.project_id=? AND NOT EXISTS (SELECT 1 FROM shots sh WHERE sh.scene_id=s.id) ORDER BY s.scene_number', params)


def scenes_without_characters(*params):
    return fetch_all('SELECT s.* FROM scenes s WHERE s.project_id=? AND NOT EXISTS (SELECT 1 FROM scene_characters x WHERE x.scene_id=s.id) ORDER BY s.scene_number', params)


def locations_without_image(*params):
    return fetch_all("SELECT name FROM locations WHERE project_id=? AND COALESCE(reference_image_path,'')='' ORDER BY name", params)


def characters_without_image(*params):
    return fetch_all("SELECT name FROM characters WHERE project_id=? AND COALESCE(reference_image_path,'')='' ORDER BY name", params)


def unreviewed_shots(*params):
    return fetch_all('SELECT s.scene_number, s.scene_suffix, sh.shot_number FROM shots sh JOIN scenes s ON s.id=sh.scene_id WHERE s.project_id=? AND COALESCE(sh.confirmed,0)=0 ORDER BY s.scene_number, sh.shot_number', params)


def location_state_labels(*params):
    return fetch_all("""
        SELECT lv.id, l.name || ' - ' || lv.variant_name AS label
        FROM location_variants lv JOIN locations l ON lv.location_id = l.id
        WHERE l.project_id = ?
    """, params)


def scene_ids_of_project(*params):
    return fetch_all('SELECT id FROM scenes WHERE project_id=?', params)


def scenes_of_project(*params):
    return fetch_all('SELECT * FROM scenes WHERE project_id=? ORDER BY scene_number', params)


def scene_character_names(*params):
    return fetch_all('SELECT sc.scene_id, c.name FROM scene_characters sc JOIN characters c ON c.id = sc.character_id JOIN scenes s ON s.id = sc.scene_id WHERE s.project_id=?', params)


def character_names_by_id(*params):
    return fetch_all('SELECT id, name FROM characters WHERE project_id=? ORDER BY id', params)


def prop_names_by_id(*params):
    return fetch_all('SELECT id, name FROM props WHERE project_id=? ORDER BY id', params)


def shot_counts_per_scene(*params):
    return fetch_all('SELECT sh.scene_id, COUNT(*) n FROM shots sh JOIN scenes s ON s.id = sh.scene_id WHERE s.project_id=? GROUP BY sh.scene_id', params)


def episode_labels(*params):
    return fetch_all('SELECT id, episode_number, title FROM episodes WHERE project_id=? ORDER BY episode_number', params)


def add_scene(*params):
    return run_query('INSERT INTO scenes (project_id, episode_id, scene_number, int_ext, day_night, weather, location_variant_id, notes) VALUES (?,?,?,?,?,?,?,?)', params)


def link_character_to_scene(project_id, scene_id, character_id):
    """ربط شخصية بمشهد — الاتنين لازم يكونوا في المشروع ده."""
    return run_query(
        'INSERT OR IGNORE INTO scene_characters (scene_id, character_id) SELECT ?, ? '
        'WHERE EXISTS (SELECT 1 FROM scenes WHERE id=? AND project_id=?) '
        'AND EXISTS (SELECT 1 FROM characters WHERE id=? AND project_id=?)',
        (scene_id, character_id, scene_id, project_id, character_id, project_id))


def link_prop_to_scene(project_id, scene_id, prop_id):
    """ربط إكسسوار بمشهد — الاتنين لازم يكونوا في المشروع ده."""
    return run_query(
        'INSERT OR IGNORE INTO scene_props (scene_id, prop_id) SELECT ?, ? '
        'WHERE EXISTS (SELECT 1 FROM scenes WHERE id=? AND project_id=?) '
        'AND EXISTS (SELECT 1 FROM props WHERE id=? AND project_id=?)',
        (scene_id, prop_id, scene_id, project_id, prop_id, project_id))


def update_scene(project_id, *params):
    return run_query('UPDATE scenes SET scene_number=?, int_ext=?, day_night=?, weather=?, '
                     'location_variant_id=?, notes=? WHERE id=? AND project_id=?', params + (project_id,))


def unlink_scene_characters(project_id, *params):
    return run_query('DELETE FROM scene_characters WHERE scene_id=? '
                     'AND scene_id IN (SELECT id FROM scenes WHERE project_id=?)', params + (project_id,))


def unlink_scene_props(project_id, *params):
    return run_query('DELETE FROM scene_props WHERE scene_id=? '
                     'AND scene_id IN (SELECT id FROM scenes WHERE project_id=?)', params + (project_id,))


def delete_scene(project_id, *params):
    return run_query('DELETE FROM scenes WHERE id=? AND project_id=?', params + (project_id,))


def scene_numbers_of_project(*params):
    return fetch_all('SELECT scene_number FROM scenes WHERE project_id=?', params)


def other_scene_with_number(*params):
    return fetch_all('SELECT id FROM scenes WHERE project_id=? AND scene_number=? AND id != ?', params)


def character_ids_in_scene(*params):
    return fetch_all('SELECT character_id FROM scene_characters WHERE scene_id=?', params)


def prop_ids_in_scene(*params):
    return fetch_all('SELECT prop_id FROM scene_props WHERE scene_id=?', params)


def shots_of_scene(*params):
    return fetch_all('SELECT * FROM shots WHERE scene_id=? ORDER BY shot_number', params)


def scene_notes_and_time(*params):
    return fetch_all('SELECT notes, day_night FROM scenes WHERE id=?', params)


def look_labels_of_project(*params):
    return fetch_all("""
                SELECT cl.id, ch.name || ' - ' || cl.look_name AS label
                FROM character_looks cl JOIN characters ch ON cl.character_id = ch.id
                WHERE ch.project_id = ?
            """, params)


def add_shot(*params):
    return run_query("""INSERT INTO shots
                    (scene_id, shot_number, shot_size, camera_movement, camera_angle, duration_seconds,
                     day_night, weather, action_description,
                     emotion_intensity, emotion_label, dialogue_text, visual_style_notes, include_music, confirmed)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", params)


def set_shot_storyboard(project_id, *params):
    return run_query('UPDATE shots SET storyboard_image_path=? WHERE id=? '
                     'AND scene_id IN (SELECT id FROM scenes WHERE project_id=?)', params + (project_id,))


def add_shot_character(project_id, shot_id, look_id, has_dialogue):
    """ربط مظهر شخصية بلقطة — اللقطة والمظهر لازم يكونوا في المشروع ده."""
    return run_query(
        'INSERT INTO shot_characters (shot_id, look_id, has_dialogue) SELECT ?, ?, ? '
        'WHERE EXISTS (SELECT 1 FROM shots sh JOIN scenes s ON s.id=sh.scene_id '
        '              WHERE sh.id=? AND s.project_id=?) '
        'AND EXISTS (SELECT 1 FROM character_looks cl JOIN characters c ON c.id=cl.character_id '
        '            WHERE cl.id=? AND c.project_id=?)',
        (shot_id, look_id, has_dialogue, shot_id, project_id, look_id, project_id))


def add_shot_prop(project_id, shot_id, prop_id):
    """ربط إكسسوار بلقطة — اللقطة والإكسسوار لازم يكونوا في المشروع ده."""
    return run_query(
        'INSERT INTO shot_props (shot_id, prop_id) SELECT ?, ? '
        'WHERE EXISTS (SELECT 1 FROM shots sh JOIN scenes s ON s.id=sh.scene_id '
        '              WHERE sh.id=? AND s.project_id=?) '
        'AND EXISTS (SELECT 1 FROM props WHERE id=? AND project_id=?)',
        (shot_id, prop_id, shot_id, project_id, prop_id, project_id))


def characters_in_shot(*params):
    return fetch_all('SELECT look_id, has_dialogue FROM shot_characters WHERE shot_id=?', params)


def shot_numbers_of_scene(*params):
    return fetch_all('SELECT shot_number FROM shots WHERE scene_id=?', params)


def update_shot(project_id, *params):
    return run_query("""UPDATE shots SET shot_number=?, shot_size=?, camera_movement=?, camera_angle=?,
                            duration_seconds=?, day_night=?, weather=?, action_description=?,
                            emotion_intensity=?, emotion_label=?, dialogue_text=?,
                            visual_style_notes=?, include_music=?, confirmed=?, storyboard_image_path=?
                        WHERE id=? AND scene_id IN (SELECT id FROM scenes WHERE project_id=?)""",
                     params + (project_id,))


def unlink_shot_characters(project_id, *params):
    return run_query('DELETE FROM shot_characters WHERE shot_id=? AND shot_id IN '
                     '(SELECT sh.id FROM shots sh JOIN scenes s ON s.id=sh.scene_id WHERE s.project_id=?)',
                     params + (project_id,))


def unlink_shot_props(project_id, *params):
    return run_query('DELETE FROM shot_props WHERE shot_id=? AND shot_id IN '
                     '(SELECT sh.id FROM shots sh JOIN scenes s ON s.id=sh.scene_id WHERE s.project_id=?)',
                     params + (project_id,))


def delete_shot(project_id, *params):
    return run_query('DELETE FROM shots WHERE id=? '
                     'AND scene_id IN (SELECT id FROM scenes WHERE project_id=?)', params + (project_id,))


def prop_ids_in_shot(*params):
    return fetch_all('SELECT prop_id FROM shot_props WHERE shot_id=?', params)


def other_shot_with_number(*params):
    return fetch_all('SELECT id FROM shots WHERE scene_id=? AND shot_number=? AND id != ?', params)


# --- خزانة المواهب: الممثلين وربطهم بالشخصيات (P9) --------------------------
# actors عابر للشركات عمدًا (مفيش company_id على الجدول) - production، القرار
# المحسوم 2026-09-23: مسبح ممثلين واحد كل شركات المنصة بتدوّر فيه، مش جدول
# تابع لشركة زي باقي الجداول. character_actor_casting هي حلقة الوصل
# بالمشروع/الشخصية، وهي نفسها صف "الشورت-ليست" اللي بيفتح الحقول الحساسة.

def _now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


_ACTOR_COLUMNS = (
    "full_name", "stage_name", "category", "gender", "bio", "credits_text",
    "height_cm", "weight_kg", "chest_cm", "waist_cm", "hips_cm", "shoe_size_eu",
    "hair_color", "eye_color", "contact_phone", "contact_email", "agent_name",
    "agent_contact", "hobbies", "drives_car", "drives_motorcycle", "swims", "smokes",
    "skills_notes", "link_showreel", "link_instagram", "link_other", "discoverable",
    "always_public_fields",
)


def actors_directory():
    """كل الممثلين الظاهرين في البحث (discoverable) - القايمة اللي شاشة البحث
    بالحرف بتحمّلها مرة واحدة وتفلترها في الذاكرة (مفيش استعلام لكل حرف).

    مفيش شرط صورة أو وسيلة تواصل عشان يظهر: الممثل/ة الحقيقي المضاف من
    مصدر عام بيبقى من غير تواصل بالقصد (ACTOR-CASTING-PLAN)، وممثل/ة اتضاف
    من غير صورة كان بيختفي من القايمة وكأنه اتمسح. الصورة الناقصة بتبان
    أيقونة + تنبيه "الصورة محتاجة تحديث" بدل ما البروفايل يستخبى."""
    return fetch_all("""
        SELECT id, full_name, stage_name, category, photo_path, photo_updated_at, is_demo
        FROM actors
        WHERE discoverable=1 AND full_name IS NOT NULL AND full_name != ''
        ORDER BY full_name
    """)


def all_actors():
    """كل الممثلين من غير فلترة ظهور - للسكريبتات والاختبارات."""
    return fetch_all("SELECT id, full_name, stage_name, photo_path, discoverable, is_demo "
                     "FROM actors ORDER BY full_name")


def actors_owned_by_company(company_id):
    """بروفايلات الشركة دي أضافتها - منهم اللي مخفي من البحث، عشان
    "مش ظاهر في البحث" ميبقاش معناه إن الشركة نفسها مش لاقياه."""
    return fetch_all("SELECT id, full_name, stage_name, category, photo_path, photo_updated_at, is_demo "
                     "FROM actors WHERE owner_company_id=? AND discoverable=0 ORDER BY full_name",
                     (company_id,))


def actor_by_id(*params):
    rows = fetch_all("SELECT * FROM actors WHERE id=?", params)
    return rows[0] if rows else None


def can_edit_actor(actor, company_id, role):
    """التعديل للشركة اللي أضافت البروفايل (بصلاحية تعديل) أو لمشغّل المنصة.
    المسبح عابر للشركات في القراءة بس، مش في الكتابة."""
    if not actor:
        return False
    if role == "operator":
        return True
    return (actor.get("owner_company_id") is not None
            and actor["owner_company_id"] == company_id
            and permissions.can(role, "edit"))


_ACTOR_FLAG_DEFAULTS = {"drives_car": 0, "drives_motorcycle": 0, "swims": 0, "smokes": 0, "discoverable": 1}


def _actor_params(values):
    """قيم الأعمدة بالترتيب. الأعلام (NOT NULL) بتاخد افتراضيها لو ناقصة."""
    out = []
    for c in _ACTOR_COLUMNS:
        v = values.get(c)
        if c in _ACTOR_FLAG_DEFAULTS:
            v = _ACTOR_FLAG_DEFAULTS[c] if v is None else int(bool(v))
        out.append(v)
    return tuple(out)


def add_actor(values, owner_company_id=None, created_by=None, is_demo=0):
    """values: dict بأعمدة _ACTOR_COLUMNS (الناقص بيتحط NULL). الصورة
    بتتحط بعدين بـ set_actor_photo عشان تاريخها يتسجل معاها."""
    now = _now_iso()
    cols = list(_ACTOR_COLUMNS) + ["is_demo", "owner_company_id", "created_by", "created_at", "updated_at"]
    params = _actor_params(values) + (int(is_demo), owner_company_id, created_by, now, now)
    return run_query(f"INSERT INTO actors ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", params)


def update_actor(actor_id, values, company_id, role):
    """نفس أعمدة add_actor. الفحص جوه الجملة نفسها كمان (مش في الشاشة بس):
    شركة تانية مينفعش تعدّل بروفايل مش بتاعها حتى لو نادت الدالة مباشرة."""
    sets = ", ".join(f"{c}=?" for c in _ACTOR_COLUMNS)
    params = _actor_params(values) + (
        _now_iso(), actor_id, 1 if role == "operator" else 0, company_id)
    return run_query(f"UPDATE actors SET {sets}, updated_at=? WHERE id=? "
                     "AND (?=1 OR owner_company_id=?)", params)


def set_actor_photo(actor_id, photo_path, updated_at=None):
    """بيحدّث صورة الممثل/ة وتاريخ آخر تحديث للصورة مع بعض - ده الأساس اللي
    تنبيه "الصورة قديمة" (أكتر من 3 شهور) بيتحسب عليه."""
    now = _now_iso()
    return run_query("UPDATE actors SET photo_path=?, photo_updated_at=?, updated_at=? WHERE id=?",
                     (photo_path, updated_at or now, now, actor_id))


def share_actor_publicly(actor_id, company_id, role):
    """بيفتح (أو بيجدد) لينك البروفايل العام. أي توكن قديم بيموت مع التجديد.
    بيرجّع التوكن الجديد، أو None لو المستخدم مش من حقه يعدّل البروفايل ده.

    الفحص مرتين زي update_actor: can_edit_actor هنا، وشرط الشركة جوه الجملة."""
    import public_profile
    if not can_edit_actor(actor_by_id(actor_id), company_id, role):
        return None
    token = public_profile.new_token()
    run_query("UPDATE actors SET public_share_token=?, public_share_at=? WHERE id=? "
              "AND (?=1 OR owner_company_id=?)",
              (token, _now_iso(), actor_id, 1 if role == "operator" else 0, company_id))
    return token


def stop_sharing_actor(actor_id, company_id, role):
    """بيقفل البروفايل العام: اللينك بيرجع "مش متاح" من أول زيارة جاية."""
    if not can_edit_actor(actor_by_id(actor_id), company_id, role):
        return False
    run_query("UPDATE actors SET public_share_token=NULL, public_share_at=NULL WHERE id=? "
              "AND (?=1 OR owner_company_id=?)",
              (actor_id, 1 if role == "operator" else 0, company_id))
    return True


def actor_by_public_token(token):
    """الصف بالتوكن، أو None — من غير دخول، فالتوكن لازم يعدّي فحص الشكل الأول."""
    import public_profile
    if not public_profile.valid_token(token):
        return None
    rows = fetch_all("SELECT * FROM actors WHERE public_share_token=?", (token,))
    return rows[0] if rows else None


def actor_unlocked_for_company(actor_id, company_id):
    """True لو الشركة دي رشّحت أو تعاقدت مع الممثل/ة ده في أي مشروع من
    مشاريعها، أو هي اللي أضافت البروفايل - وقتها بس الحقول الحساسة بتتعرض
    لمستخدمينها (production، القرار المحسوم 2026-09-23). صف الكاستينج نفسه
    بيسجل مين فتحها وإمتى (created_by/created_at)."""
    rows = fetch_all("""
        SELECT 1 FROM character_actor_casting cac
        JOIN projects p ON p.id = cac.project_id
        WHERE cac.actor_id=? AND p.company_id=? AND cac.status IN ('shortlisted', 'cast')
        UNION ALL
        SELECT 1 FROM actors WHERE id=? AND owner_company_id=?
        LIMIT 1
    """, (actor_id, company_id, actor_id, company_id))
    return bool(rows)


class AlreadyCastError(IntegrityError):
    """الشخصية دي متعاقد لها ممثل/ة تاني - لازم يتشال الأول."""
    user_message = "الشخصية دي متعاقد لها ممثل/ة تاني بالفعل. شيل التعاقد ده الأول لو عايز تغيّره."

    def __init__(self):
        super().__init__(self.user_message)


def cast_actor(actor_id, project_id, character_id, status, role_note, created_by):
    """بيرشّح (shortlisted) أو بيتعاقد (cast) مع ممثل/ة لشخصية في مشروع.

    صف واحد لكل (ممثل، شخصية): الترشيح اللي بعده تعاقد بيتحدّث مكانه بدل
    ما يتكرر. الشخصية لازم تبقى تبع المشروع فعلًا (فحص جوه الجملة)، وتعاقد
    شخصية متعاقد لها حد تاني بيترفض (AlreadyCastError)."""
    if status not in ("shortlisted", "cast"):
        raise ValueError(status)
    if status == "cast":
        other = fetch_all("SELECT 1 FROM character_actor_casting WHERE character_id=? AND project_id=? "
                          "AND status='cast' AND actor_id != ?", (character_id, project_id, actor_id))
        if other:
            raise AlreadyCastError()
    now = _now_iso()
    cast_at = now if status == "cast" else None
    existing = fetch_all("SELECT id, status FROM character_actor_casting "
                         "WHERE actor_id=? AND project_id=? AND character_id=?",
                         (actor_id, project_id, character_id))
    if existing:
        # تعاقد مبيرجعش ترشيح لو حد داس "رشّح" تاني بالغلط
        if existing[0]["status"] == "cast" and status == "shortlisted":
            return existing[0]["id"]
        run_query("UPDATE character_actor_casting SET status=?, role_note=COALESCE(NULLIF(?, ''), role_note), "
                  "cast_at=? WHERE id=? AND project_id=?",
                  (status, role_note, cast_at, existing[0]["id"], project_id))
        return existing[0]["id"]
    return run_query(
        """INSERT INTO character_actor_casting
            (actor_id, project_id, character_id, status, role_note, created_by, created_at, cast_at)
           SELECT ?, ?, ?, ?, ?, ?, ?, ?
           WHERE EXISTS (SELECT 1 FROM characters WHERE id=? AND project_id=?)""",
        (actor_id, project_id, character_id, status, role_note, created_by, now, cast_at,
         character_id, project_id))


def remove_casting(project_id, casting_id):
    """بيشيل ترشيح/تعاقد - جوه المشروع ده بس."""
    return run_query("DELETE FROM character_actor_casting WHERE id=? AND project_id=?",
                     (casting_id, project_id))


def castings_of_actor_in_project(actor_id, project_id):
    return fetch_all("""
        SELECT cac.id, cac.status, cac.role_note, cac.created_by, cac.created_at, c.name AS character_name
        FROM character_actor_casting cac
        JOIN characters c ON c.id = cac.character_id
        WHERE cac.actor_id=? AND cac.project_id=?
        ORDER BY c.name
    """, (actor_id, project_id))


def casting_for_character(*params):
    """الممثل/ة المتعاقد للشخصية لو فيه، وإلا آخر ترشيح - أو None."""
    rows = fetch_all("""
        SELECT cac.id AS casting_id, cac.status, cac.actor_id,
               a.full_name, a.stage_name, a.photo_path
        FROM character_actor_casting cac
        JOIN actors a ON a.id = cac.actor_id
        WHERE cac.character_id=?
        ORDER BY CASE cac.status WHEN 'cast' THEN 0 ELSE 1 END, cac.created_at DESC
    """, params)
    return rows[0] if rows else None


def shortlist_count_for_character(*params):
    rows = fetch_all("SELECT COUNT(*) AS n FROM character_actor_casting "
                     "WHERE character_id=? AND status='shortlisted'", params)
    return rows[0]["n"] if rows else 0
