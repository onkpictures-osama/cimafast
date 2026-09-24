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
from search import matches, normalize

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
    by_char = cast_by_character(project_id)
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
        ch = by_char.get(r["character_id"], {})
        cast.setdefault(r["scene_id"], []).append({
            "id": r["character_id"], "name": r["name"], "num": ch.get("cast_number"),
            "actor": (ch.get("actor") or {}).get("name")})
    for members in cast.values():
        members.sort(key=lambda c: (c["num"] is None, c["num"] or 0, c["id"]))
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
        "SELECT id, day_number, shoot_date, notes, COALESCE(shot_done,0) AS shot_done FROM shooting_days "
        "WHERE project_id=? ORDER BY day_number, id",
        (project_id,),
    )


def set_day_shot(project_id, day_id, done, when=None):
    """مرحلة الإنتاج: اليوم ده اتصور (أو رجّعه لسه ماتصورش)."""
    with _tx() as ex:
        ex("UPDATE shooting_days SET shot_done=?, shot_done_at=? WHERE id=? AND project_id=?",
           (1 if done else 0, (when or dt.datetime.now().isoformat(timespec="seconds")) if done else None,
            day_id, project_id))


def production_progress(project_id):
    """شريط التقدّم في مرحلة الإنتاج: أيام اتصورت من كل الأيام، ومشاهد الأيام دي."""
    rows = fetch_all("""
        SELECT
          (SELECT COUNT(*) FROM shooting_days WHERE project_id=?) AS days,
          (SELECT COUNT(*) FROM shooting_days WHERE project_id=? AND COALESCE(shot_done,0)=1) AS days_shot,
          (SELECT COUNT(*) FROM scenes WHERE project_id=?) AS scenes,
          (SELECT COUNT(DISTINCT x.scene_id) FROM shooting_day_scenes x JOIN shooting_days d ON d.id=x.day_id
             WHERE d.project_id=? AND COALESCE(d.shot_done,0)=1) AS scenes_shot
    """, (project_id,) * 4)
    return dict(rows[0])


# --- ما بعد الإنتاج ------------------------------------------------------------------

_POST_FIELDS = ("status", "progress", "vendor_name", "vendor_contact", "vendor_location",
                "preview_url", "preview_url2", "due_date", "notes")


def post_departments(project_id):
    return fetch_all("SELECT * FROM post_departments WHERE project_id=? ORDER BY id", (project_id,))


def save_post_department(project_id, dept_key, updated_by=None, **fields):
    """بيحفظ قسم (بيعمله لو أول مرة). الحقول الناقصة بتفضل زي ما هي."""
    import post_production
    if dept_key not in post_production.DEPT_KEYS:
        raise ValueError(f"unknown post department {dept_key!r}")
    if "status" in fields and fields["status"] not in post_production.STATUS_KEYS:
        raise ValueError(f"unknown post status {fields['status']!r}")
    if "progress" in fields:
        fields["progress"] = max(0, min(100, int(fields["progress"] or 0)))
    now = dt.datetime.now().isoformat(timespec="seconds")
    current = fetch_all("SELECT * FROM post_departments WHERE project_id=? AND dept_key=?", (project_id, dept_key))
    row = dict(current[0]) if current else {"status": "not_started", "progress": 0}
    row.update({k: v for k, v in fields.items() if k in _POST_FIELDS})
    with _tx() as ex:
        ex("INSERT OR IGNORE INTO post_departments (project_id, dept_key, status, progress, updated_at) "
           "VALUES (?, ?, 'not_started', 0, ?)", (project_id, dept_key, now))
        ex("UPDATE post_departments SET status=?, progress=?, vendor_name=?, vendor_contact=?, "
           "vendor_location=?, preview_url=?, preview_url2=?, due_date=?, notes=?, updated_at=?, updated_by=? "
           "WHERE project_id=? AND dept_key=?",
           tuple((row.get(k) or None) if k not in ("status", "progress") else row.get(k) for k in _POST_FIELDS)
           + (now, updated_by, project_id, dept_key))


def post_comments(project_id, dept_key):
    return fetch_all("SELECT id, author, body, created_at FROM post_comments WHERE project_id=? AND dept_key=? "
                     "ORDER BY id", (project_id, dept_key))


def add_post_comment(project_id, dept_key, author, body):
    body = (body or "").strip()
    if not body:
        return
    with _tx() as ex:
        ex("INSERT INTO post_comments (project_id, dept_key, author, body, created_at) VALUES (?, ?, ?, ?, ?)",
           (project_id, dept_key, author, body, dt.datetime.now().isoformat(timespec="seconds")))


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
            ex("UPDATE shooting_days SET day_number=? WHERE id=? AND project_id=?", (i, d["id"], project_id))


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
            ex("UPDATE shooting_days SET day_number=? WHERE id=? AND project_id=?",
               (number, entry["day_id"], project_id))
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
    scene_counts = {}
    info = {}
    for idx, d in enumerate(days):
        for sid in d["scene_ids"]:
            for c in b["scenes"][sid]["cast"]:
                working.setdefault(c["id"], set()).add(idx)
                scene_counts[c["id"]] = scene_counts.get(c["id"], 0) + 1
                info[c["id"]] = c
    dates = [d.get("shoot_date") or None for d in days]
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
        c = info[cid]
        rows.append({"character_id": cid, "name": c["name"], "codes": codes,
                     "cast_number": c.get("num"), "actor": c.get("actor"),
                     "work_days": len(idxs), "hold_days": codes.count("H"),
                     "scheduled_scenes": scene_counts[cid],
                     "first_day": first + 1, "last_day": last + 1,
                     "first_date": dates[first], "last_date": dates[last]})
    # زي الكول شيت: بالرقم لو فيه، وبعدين الأكتر شغل
    rows.sort(key=lambda r: (r["cast_number"] is None, r["cast_number"] or 0,
                             -r["work_days"], r["first_day"], r["name"]))
    return {"days": [d["day_number"] for d in days], "dates": dates, "rows": rows}


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


# الدفع (رقم مستخدم ← باقي المشاهد رقم لقدام) جوه نفس الحلقة بس: في المسلسل
# مشهد 5 في الحلقة 2 مالوش علاقة بمشهد 5 في الحلقة 7. COALESCE بدل "IS ?"
# عشان نفس الجملة تشتغل على SQLite وPostgres (NULL = فيلم/من غير حلقة).
_SAME_EPISODE = "COALESCE(episode_number, -1) = COALESCE(?, -1)"


def shift_scene_numbers_up_except(project_id, from_number, exclude_id, episode_number=None):
    return run_query('UPDATE scenes SET scene_number = scene_number + 1 WHERE project_id=? AND scene_number >= ? '
                     f'AND id != ? AND {_SAME_EPISODE}', (project_id, from_number, exclude_id, episode_number))


def shift_scene_numbers_up(project_id, from_number, episode_number=None):
    return run_query('UPDATE scenes SET scene_number = scene_number + 1 WHERE project_id=? AND scene_number >= ? '
                     f'AND {_SAME_EPISODE}', (project_id, from_number, episode_number))


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
                 (character_id, look_name, apparent_age, makeup_state, hair_state, wardrobe_description, description,
                  is_default, change_number)
                 VALUES (?,?,?,?,?,?,?,1,1)""",
              (char_id, DEFAULT_LOOK_NAME, '', '', '', '', ''))
    return char_id


def add_character_look(*params):
    # P5: لو دي أول مظهر للشخصية (مفروض مايحصلش بعد الـ backfill) يبقى هو الأساسي
    # P10: كل مظهر جديد = الغيار اللي بعده للشخصية دي
    return run_query("""INSERT INTO character_looks
                        (character_id, look_name, apparent_age, makeup_state, hair_state, wardrobe_description, description, reference_image_path, is_default,
                         change_number)
                        VALUES (?,?,?,?,?,?,?,?,
                                CASE WHEN EXISTS (SELECT 1 FROM character_looks WHERE character_id=?) THEN 0 ELSE 1 END,
                                (SELECT COALESCE(MAX(change_number), 0) + 1 FROM character_looks WHERE character_id=?))""",
                     tuple(params) + (params[0], params[0]))


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
    return run_query('INSERT INTO props (project_id, name, character_id) VALUES (?,?,?)', params)


def delete_prop(project_id, *params):
    return run_query('DELETE FROM props WHERE id=? AND project_id=?', params + (project_id,))


def update_prop(project_id, *params):
    return run_query('UPDATE props SET name=?, character_id=? WHERE id=? AND project_id=?',
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
    # الحلقة الأول (المسلسل)، والمشاهد من غير حلقة في الآخر
    return fetch_all('SELECT * FROM scenes WHERE project_id=? '
                     'ORDER BY CASE WHEN episode_number IS NULL THEN 1 ELSE 0 END, episode_number, '
                     'scene_number, scene_suffix', params)


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


def add_scene(project_id, episode_id, *params):
    """الحلقة بتتكتب رقمها (episode_number - مصدر الحقيقة) جنب الـ id، عشان
    المشهد اليدوي يطلع "3/12" زي المستورد بالظبط."""
    episode_number = None
    if episode_id is not None:
        rows = fetch_all("SELECT episode_number FROM episodes WHERE id=? AND project_id=?",
                         (episode_id, project_id))
        episode_number = rows[0]["episode_number"] if rows else None
        if episode_number is None:
            episode_id = None
    return run_query('INSERT INTO scenes (project_id, episode_id, episode_number, scene_number, int_ext, '
                     'day_night, weather, location_variant_id, notes) VALUES (?,?,?,?,?,?,?,?,?)',
                     (project_id, episode_id, episode_number) + params)


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


def update_scene_background(project_id, scene_id, has_group, headcount, wardrobe, action):
    """حفظ زرار "مجاميع/كومبارس" لوحده، بره فورم تعديل المشهد الكبير - عشان
    يتحفظ فورًا أول ما اليوزر يجاوب أيوه/لأ من غير ما يستنى submit الفورم
    التاني (نفس فكرة popover لينك الموقع الجغرافي في locations.py)."""
    return run_query(
        'UPDATE scenes SET has_background_group=?, background_group_headcount=?, '
        'background_group_wardrobe=?, background_group_action=? WHERE id=? AND project_id=?',
        (has_group, headcount, wardrobe, action, scene_id, project_id))


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


def other_scene_with_number(project_id, number, scene_id, episode_number=None):
    return fetch_all(f'SELECT id FROM scenes WHERE project_id=? AND scene_number=? AND id != ? AND {_SAME_EPISODE}',
                     (project_id, number, scene_id, episode_number))


def scene_numbers_in_episode(project_id, episode_number=None):
    return fetch_all(f'SELECT scene_number FROM scenes WHERE project_id=? AND {_SAME_EPISODE}',
                     (project_id, episode_number))


def set_scene_episode(project_id, scene_id, episode_number):
    """بينقل مشهد لحلقة (أو يشيله من أي حلقة بـ None)، والـ id بيتظبط معاه."""
    ep_id = None
    if episode_number is not None:
        rows = fetch_all("SELECT id FROM episodes WHERE project_id=? AND episode_number=?",
                         (project_id, int(episode_number)))
        ep_id = rows[0]["id"] if rows else None
    return run_query("UPDATE scenes SET episode_number=?, episode_id=? WHERE id=? AND project_id=?",
                     (episode_number, ep_id, scene_id, project_id))


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

    مفيش شرط صورة أو وسيلة تواصل عشان يظهر: الممثل الحقيقي المضاف من
    مصدر عام بيبقى من غير تواصل بالقصد (ACTOR-CASTING-PLAN)، وممثل اتضاف
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
    """بيحدّث صورة الممثل وتاريخ آخر تحديث للصورة مع بعض - ده الأساس اللي
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
    """True لو الشركة دي رشّحت أو تعاقدت مع الممثل ده في أي مشروع من
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
    """الشخصية دي متعاقد لها ممثل تاني - لازم يتشال الأول."""
    user_message = "الشخصية دي متعاقد لها ممثل تاني بالفعل. شيل التعاقد ده الأول لو عايز تغيّره."

    def __init__(self):
        super().__init__(self.user_message)


def cast_actor(actor_id, project_id, character_id, status, role_note, created_by):
    """بيرشّح (shortlisted) أو بيتعاقد (cast) مع ممثل لشخصية في مشروع.

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
    """الممثل المتعاقد للشخصية لو فيه، وإلا آخر ترشيح - أو None."""
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


# --- الممثل جوه باقي السيستم (رقم الكاست، التفريغ، الجدول، التتبع) ---------------
# التعاقد نفسه صف في character_actor_casting؛ هنا بس القراءات اللي بتلزق اسم
# الممثل ورقمه في كل شاشة وورقة فيها الشخصية، في استعلامين للمشروع كله بدل
# استعلام لكل شخصية.

class CastNumberTakenError(IntegrityError):
    """رقم الكاست ده متحط لشخصية تانية في نفس المشروع."""
    user_message = "الرقم ده متحط لشخصية تانية في المشروع. اختار رقم تاني أو فضّي رقمها الأول."

    def __init__(self):
        super().__init__(self.user_message)


# ترتيب الترقيم التلقائي لما عدد المشاهد يتساوى: البطل قبل الشرير قبل المساعد...
_ROLE_RANK = {"بطل": 0, "شرير": 1, "مساعد": 2, "غير محدد": 3, "كومبارس": 4}


def project_cast(project_id):
    """كل شخصيات المشروع برقمها وعدد مشاهدها والممثل المتعاقد والمرشحين.

    مترتبة زي الكول شيت: اللي ليها رقم بالرقم، وبعدين الباقي بعدد المشاهد."""
    chars = fetch_all("""
        SELECT c.id, c.name, c.role_type, c.cast_number, c.reference_image_path,
               (SELECT COUNT(DISTINCT sc.scene_id) FROM scene_characters sc
                 WHERE sc.character_id = c.id) AS scene_count
        FROM characters c WHERE c.project_id = ?
    """, (project_id,))
    castings = fetch_all("""
        SELECT cac.id AS casting_id, cac.character_id, cac.status, cac.actor_id, cac.role_note,
               a.full_name, a.stage_name, a.photo_path
        FROM character_actor_casting cac
        JOIN actors a ON a.id = cac.actor_id
        WHERE cac.project_id = ?
        ORDER BY cac.created_at, cac.id
    """, (project_id,))
    out = {c["id"]: dict(c, actor=None, shortlist=[]) for c in chars}
    for r in castings:
        entry = out.get(r["character_id"])
        if entry is None:
            continue
        person = {"casting_id": r["casting_id"], "actor_id": r["actor_id"],
                  "name": r["stage_name"] or r["full_name"], "photo_path": r["photo_path"],
                  "role_note": r["role_note"]}
        if r["status"] == "cast":
            entry["actor"] = person
        else:
            entry["shortlist"].append(person)
    return sorted(out.values(), key=lambda c: (
        c["cast_number"] is None, c["cast_number"] or 0, -c["scene_count"],
        _ROLE_RANK.get(c["role_type"] or "", 3), c["id"]))


def cast_by_character(project_id):
    """character_id → نفس صف project_cast."""
    return {c["id"]: c for c in project_cast(project_id)}


def cast_label(c, with_actor=True):
    """"#3 سلمى — اسم الممثل" — الشكل الواحد اللي بيظهر في كل مكان."""
    label = f"#{c['cast_number']} {c['name']}" if c.get("cast_number") else c["name"]
    actor = c.get("actor")
    if with_actor and actor:
        label += f" — {actor['name']}"
    return label


def set_cast_number(project_id, character_id, number):
    """number = None بيفضّي الرقم. الرقم لازم يبقى فريد جوه المشروع."""
    if number is not None:
        number = int(number)
        if number < 1:
            raise ValueError(number)
        taken = fetch_all("SELECT 1 FROM characters WHERE project_id=? AND cast_number=? AND id != ?",
                          (project_id, number, character_id))
        if taken:
            raise CastNumberTakenError()
    return run_query("UPDATE characters SET cast_number=? WHERE id=? AND project_id=?",
                     (number, character_id, project_id))


def next_cast_number(project_id):
    rows = fetch_all("SELECT COALESCE(MAX(cast_number), 0) AS n FROM characters WHERE project_id=?",
                     (project_id,))
    return rows[0]["n"] + 1


def auto_number_cast(project_id):
    """بيدّي رقم لكل شخصية لسه مالهاش، بعد أكبر رقم موجود: الأكتر مشاهد
    الأول. الأرقام الموجودة عمرها ما بتتغيّر - الورق اللي اتطبع بيفضل صح.
    بيرجّع عدد الشخصيات اللي اترقّمت."""
    cast = project_cast(project_id)
    next_n = max((c["cast_number"] for c in cast if c["cast_number"]), default=0)
    todo = sorted((c for c in cast if not c["cast_number"]),
                  key=lambda c: (-c["scene_count"], _ROLE_RANK.get(c["role_type"] or "", 3), c["id"]))
    for c in todo:
        next_n += 1
        run_query("UPDATE characters SET cast_number=? WHERE id=? AND project_id=?",
                  (next_n, c["id"], project_id))
    return len(todo)


def character_tracking(project_id, character_id):
    """الشخصية (وممثلها) في الجدول: عدد مشاهدها، كام منها اتجدول، أيام
    الشغل والانتظار، وأول وآخر يوم بتاريخه لو اليوم ليه تاريخ."""
    scene_count = fetch_all("SELECT COUNT(DISTINCT scene_id) AS n FROM scene_characters WHERE character_id=?",
                            (character_id,))[0]["n"]
    dood = day_out_of_days(project_id)
    row = next((r for r in dood["rows"] if r["character_id"] == character_id), None)
    out = {"scene_count": scene_count, "scheduled_scenes": 0, "work_days": 0, "hold_days": 0,
           "first_day": None, "last_day": None, "first_date": None, "last_date": None, "days": []}
    if not row:
        return out
    out.update({k: row[k] for k in ("work_days", "hold_days", "first_day", "last_day",
                                     "first_date", "last_date", "scheduled_scenes")})
    out["days"] = [{"day_number": dood["days"][i], "date": dood["dates"][i], "code": code}
                   for i, code in enumerate(row["codes"]) if code and code != "H"]
    return out



# --- المسلسل: الحلقات ------------------------------------------------------------
# الحلقة بتاعة المشهد = scenes.episode_number (مصدر الحقيقة: موجود في كل
# القواعد، والاستيراد والجدول بيقروه). جدول episodes بيشيل بيانات الحلقة
# نفسها (عنوان، وصف) - وصف المشروع إنه "مسلسل من N حلقة" = صفوفه.

SERIES_TYPE = "مسلسل"


def is_series(project):
    return bool(project) and project["project_type"] == SERIES_TYPE


def ensure_episodes(project_id, count):
    """بيتأكد إن الحلقات من 1 لـ count موجودة (الناقص بس بيتعمل). مابيمسحش
    حاجة لو العدد قلّ - مسح حلقة فيها مشاهد قرار لوحده. بيرجّع عدد اللي اتعمل."""
    have = {r["episode_number"] for r in fetch_all(
        "SELECT episode_number FROM episodes WHERE project_id=?", (project_id,))}
    made = 0
    for n in range(1, int(count) + 1):
        if n not in have:
            run_query("INSERT INTO episodes (project_id, episode_number, title) VALUES (?, ?, ?)",
                      (project_id, n, None))
            made += 1
    return made


def episode_overview(project_id):
    """كل حلقة بعدد مشاهدها: [{episode_number, title, id, scenes}] بالترتيب.
    الحلقات اللي ليها مشاهد ومالهاش صف في episodes (استيراد قديم) بتظهر برضه."""
    eps = {r["episode_number"]: {"episode_number": r["episode_number"], "title": r["title"],
                                 "id": r["id"], "scenes": 0}
           for r in fetch_all("SELECT id, episode_number, title FROM episodes WHERE project_id=?",
                              (project_id,))}
    for r in fetch_all("SELECT episode_number, COUNT(*) AS n FROM scenes WHERE project_id=? "
                       "AND episode_number IS NOT NULL GROUP BY episode_number", (project_id,)):
        eps.setdefault(r["episode_number"], {"episode_number": r["episode_number"], "title": None,
                                             "id": None, "scenes": 0})["scenes"] = r["n"]
    return [eps[k] for k in sorted(eps)]


def scenes_without_episode_count(project_id):
    return fetch_all("SELECT COUNT(*) AS n FROM scenes WHERE project_id=? AND episode_number IS NULL",
                     (project_id,))[0]["n"]


def delete_episode_scenes(project_id, episode_number):
    """بيمسح مشاهد حلقة واحدة (ولقطاتها وروابطها بالـ cascade) - لـ "استبدال
    سكريبت الحلقة". جوه المشروع ده بس."""
    return run_query("DELETE FROM scenes WHERE project_id=? AND episode_number=?",
                     (project_id, int(episode_number)))



# --- الملابس (P10) -----------------------------------------------------------------
# الغيار = المظهر (character_looks) برقمه (change_number). المشهد بيحدد كل
# شخصية لابسة أنهي غيار (scene_character_looks)، وكل غيار ليه قطعه
# (wardrobe_items). كل كتابة بتتأكد إن المشهد/الشخصية/الغيار تبع المشروع ده.

WARDROBE_CATEGORIES = ["قميص", "تيشيرت", "بنطلون", "فستان", "جيبة", "جاكيت", "بدلة", "عباية / جلابية",
                       "طرحة / غطاء راس", "جزمة", "شنطة", "إكسسوار", "ملابس داخلية", "أخرى"]
WARDROBE_SOURCES = ["شراء", "إيجار", "تفصيل", "من الممثل", "من المخزن"]
WARDROBE_STATUSES = ["محتاج شراء", "في التفصيل", "في البروفة", "جاهز", "في الغسيل"]
WARDROBE_READY = "جاهز"


def ensure_change_numbers(project_id):
    """بيرقّم مظاهر الشخصيات اللي لسه مالهاش رقم غيار (المظاهر القديمة أو
    اللي اتعملت من الاستيراد): الأساسي الأول، وبعده بترتيب الإضافة، بعد أكبر
    رقم موجود للشخصية. الأرقام الموجودة مابتتغيّرش. بيرجّع عدد اللي اترقّم."""
    rows = fetch_all("""
        SELECT cl.id, cl.character_id, cl.change_number, COALESCE(cl.is_default, 0) AS is_default
        FROM character_looks cl JOIN characters c ON c.id = cl.character_id
        WHERE c.project_id = ?
        ORDER BY cl.character_id, COALESCE(cl.is_default, 0) DESC, cl.id
    """, (project_id,))
    top = {}
    for r in rows:
        if r["change_number"]:
            top[r["character_id"]] = max(top.get(r["character_id"], 0), r["change_number"])
    todo = [r for r in rows if not r["change_number"]]
    if not todo:
        return 0
    # ترقيم بيانات قديمة مش تعديل من اليوزر: لازم يشتغل حتى لو اللي فاتح
    # التبويب "مشاهدة فقط"
    with permissions.system(), _tx() as ex:
        for r in todo:
            n = top.get(r["character_id"], 0) + 1
            top[r["character_id"]] = n
            ex("UPDATE character_looks SET change_number=? WHERE id=? "
               "AND character_id IN (SELECT id FROM characters WHERE project_id=?)", (n, r["id"], project_id))
    return len(todo)


def wardrobe_changes(project_id):
    """كل غيارات المشروع: الشخصية، رقم ونوع الغيار، عدد قطعه وتكلفتها وكام
    منها لسه مش جاهز، وعدد المشاهد اللي متحدد فيها."""
    return fetch_all("""
        SELECT cl.id, cl.character_id, c.name AS character_name, c.cast_number,
               cl.change_number, cl.look_name, COALESCE(cl.is_default, 0) AS is_default,
               cl.reference_image_path, cl.wardrobe_description,
               (SELECT COUNT(*) FROM wardrobe_items w WHERE w.look_id = cl.id) AS items,
               (SELECT COALESCE(SUM(COALESCE(w.cost, 0) * COALESCE(w.multiples, 1)), 0)
                  FROM wardrobe_items w WHERE w.look_id = cl.id) AS cost,
               (SELECT COUNT(*) FROM wardrobe_items w WHERE w.look_id = cl.id
                  AND COALESCE(w.status, '') <> ?) AS not_ready,
               (SELECT COUNT(*) FROM scene_character_looks s WHERE s.look_id = cl.id) AS scenes
        FROM character_looks cl JOIN characters c ON c.id = cl.character_id
        WHERE c.project_id = ?
        ORDER BY c.id, cl.change_number, cl.id
    """, (WARDROBE_READY, project_id))


def change_label(change):
    """"غيار 2 · بدلة الفرح" - الاسم الافتراضي للمظهر مابيتكتبش."""
    name = change.get("look_name") or ""
    base = f"غيار {change.get('change_number') or '?'}"
    return f"{base} · {name}" if name and name != DEFAULT_LOOK_NAME else base


def add_change(project_id, character_id, name):
    """غيار جديد لشخصية (= مظهر جديد برقم الغيار اللي بعده)."""
    if not fetch_all("SELECT 1 FROM characters WHERE id=? AND project_id=?", (character_id, project_id)):
        return None
    return add_character_look(character_id, (name or "").strip() or None, "", "", "", "", "", None)


def rename_change(project_id, look_id, name):
    return run_query("UPDATE character_looks SET look_name=? WHERE id=? "
                     "AND character_id IN (SELECT id FROM characters WHERE project_id=?)",
                     ((name or "").strip() or DEFAULT_LOOK_NAME, look_id, project_id))


def scene_change_map(project_id):
    """(scene_id, character_id) → look_id لكل المشروع."""
    return {(r["scene_id"], r["character_id"]): r["look_id"] for r in fetch_all("""
        SELECT x.scene_id, x.character_id, x.look_id FROM scene_character_looks x
        JOIN scenes s ON s.id = x.scene_id WHERE s.project_id = ?
    """, (project_id,))}


def character_scenes_for_wardrobe(project_id, character_id):
    """المشاهد اللي الشخصية فيها (scene_characters) بغيارها لو متحدد."""
    return fetch_all("""
        SELECT s.id, s.scene_number, s.scene_suffix, s.episode_number, s.int_ext, s.day_night,
               l.name AS location_name, x.look_id
        FROM scene_characters sc
        JOIN scenes s ON s.id = sc.scene_id
        LEFT JOIN location_variants lv ON lv.id = s.location_variant_id
        LEFT JOIN locations l ON l.id = lv.location_id
        LEFT JOIN scene_character_looks x ON x.scene_id = s.id AND x.character_id = sc.character_id
        WHERE sc.character_id = ? AND s.project_id = ?
        ORDER BY CASE WHEN s.episode_number IS NULL THEN 1 ELSE 0 END, s.episode_number,
                 s.scene_number, s.scene_suffix
    """, (character_id, project_id))


def set_scene_changes(project_id, character_id, assignments):
    """assignments: {scene_id: look_id أو None}. None بيشيل التحديد. أي مشهد
    مش في المشروع أو غيار مش للشخصية دي (في المشروع ده) بيتجاهل. بيرجّع عدد
    اللي اتغيّر."""
    own_looks = {r["id"] for r in fetch_all(
        "SELECT cl.id FROM character_looks cl JOIN characters c ON c.id = cl.character_id "
        "WHERE cl.character_id=? AND c.project_id=?", (character_id, project_id))}
    own_scenes = {r["id"] for r in fetch_all("SELECT id FROM scenes WHERE project_id=?", (project_id,))}
    changed = 0
    with _tx() as ex:
        for scene_id, look_id in assignments.items():
            if scene_id not in own_scenes or (look_id is not None and look_id not in own_looks):
                continue
            ex("DELETE FROM scene_character_looks WHERE scene_id=? AND character_id=? "
               "AND scene_id IN (SELECT id FROM scenes WHERE project_id=?)", (scene_id, character_id, project_id))
            if look_id is not None:
                ex("INSERT INTO scene_character_looks (scene_id, character_id, look_id) SELECT ?, ?, ? "
                   "WHERE EXISTS (SELECT 1 FROM scenes WHERE id=? AND project_id=?) "
                   "AND EXISTS (SELECT 1 FROM character_looks cl JOIN characters c ON c.id = cl.character_id "
                   "WHERE cl.id=? AND cl.character_id=? AND c.project_id=?)",
                   (scene_id, character_id, look_id, scene_id, project_id, look_id, character_id, project_id))
            changed += 1
    return changed


def scenes_missing_change(project_id):
    """عدد (مشهد، شخصية) اللي الشخصية فيهم في المشهد ومالهاش غيار متحدد."""
    return fetch_all("""
        SELECT COUNT(*) AS n FROM scene_characters sc
        JOIN scenes s ON s.id = sc.scene_id
        LEFT JOIN scene_character_looks x ON x.scene_id = sc.scene_id AND x.character_id = sc.character_id
        WHERE s.project_id = ? AND x.id IS NULL
    """, (project_id,))[0]["n"]


_ITEM_FIELDS = ("item_name", "category", "color", "material", "size", "source", "multiples",
                "story_state", "cost", "status", "notes")


def items_of_change(project_id, look_id):
    return fetch_all("""
        SELECT w.* FROM wardrobe_items w
        JOIN character_looks cl ON cl.id = w.look_id JOIN characters c ON c.id = cl.character_id
        WHERE w.look_id = ? AND c.project_id = ? ORDER BY w.position, w.id
    """, (look_id, project_id))


def save_change_items(project_id, look_id, rows):
    """بيستبدل قطع الغيار ده باللي في rows (بالترتيب) - نفس اللي في الجدول
    على الشاشة. الصف من غير اسم قطعة بيتشال. الغيار لازم يبقى تبع المشروع."""
    if not fetch_all("SELECT 1 FROM character_looks cl JOIN characters c ON c.id = cl.character_id "
                     "WHERE cl.id=? AND c.project_id=?", (look_id, project_id)):
        return 0
    now = _now_iso()
    kept = 0
    with _tx() as ex:
        ex("DELETE FROM wardrobe_items WHERE look_id=? AND look_id IN (SELECT cl.id FROM character_looks cl "
           "JOIN characters c ON c.id = cl.character_id WHERE c.project_id=?)", (look_id, project_id))
        for pos, r in enumerate(rows):
            name = (r.get("item_name") or "").strip()
            if not name:
                continue
            vals = []
            for f in _ITEM_FIELDS:
                v = r.get(f)
                if f == "multiples":
                    try:
                        v = max(1, int(v))
                    except (TypeError, ValueError):
                        v = 1
                elif f == "cost":
                    try:
                        v = float(v) if v not in (None, "") else None
                    except (TypeError, ValueError):
                        v = None
                elif isinstance(v, str):
                    v = v.strip() or None
                elif v != v:           # NaN من الجدول
                    v = None
                vals.append(name if f == "item_name" else v)
            ex(f"INSERT INTO wardrobe_items (look_id, {', '.join(_ITEM_FIELDS)}, position, updated_at) "
               f"VALUES (?, {', '.join('?' * len(_ITEM_FIELDS))}, ?, ?)", (look_id, *vals, pos, now))
            kept += 1
    return kept


def wardrobe_items_of_project(project_id):
    """كل قطع الملابس في المشروع مع الشخصية والغيار - لقايمة القطع وكشف الملابس."""
    return fetch_all("""
        SELECT w.*, cl.change_number, cl.look_name, c.id AS character_id, c.name AS character_name,
               c.cast_number
        FROM wardrobe_items w
        JOIN character_looks cl ON cl.id = w.look_id JOIN characters c ON c.id = cl.character_id
        WHERE c.project_id = ?
        ORDER BY CASE WHEN c.cast_number IS NULL THEN 1 ELSE 0 END, c.cast_number, c.id,
                 cl.change_number, w.position, w.id
    """, (project_id,))


def actor_sizes_for_character(project_id, character_id, company_id):
    """مقاسات الممثل المتعاقد للدور - لو الشركة فاتحة بياناته (التعاقد
    نفسه بيفتحها). None لو مفيش تعاقد أو البيانات مقفولة."""
    cast = cast_by_character(project_id).get(character_id) or {}
    actor = cast.get("actor")
    if not actor or not actor_unlocked_for_company(actor["actor_id"], company_id):
        return None
    row = actor_by_id(actor["actor_id"])
    if not row:
        return None
    return {"name": actor["name"], **{k: row.get(k) for k in
            ("height_cm", "weight_kg", "chest_cm", "waist_cm", "hips_cm", "shoe_size_eu")}}



# --- الإكسسوار: تابع للأماكن أو في إيد الشخصيات -----------------------------------
# اتفاق المالك 2026-09-24: اللي بيتلبس (ساعة، عقد، برنيطة) = ملابس. اللي
# بيتمسك (مسدس) = الإكسسواريست، تابع للشخصية. والمرصوص في المكان (ساعة على
# الكومودينو) = الإكسسواريست، تابع للمكان/الديكور.

PROP_SOURCES = ["شراء", "إيجار", "من المكان نفسه", "من المخزن", "تصنيع"]
PROP_STATUSES = ["مطلوب", "اتجاب", "اترص في المكان"]

# كلمات بتقول إن القطعة بتتلبس ← اقتراح نقلها للملابس (اقتراح بس، اليوزر بيأكد)
_WORN_WORDS = ("ساعة يد", "ساعه يد", "عقد", "سلسلة", "سلسله", "خاتم", "دبلة", "دبله", "أسورة", "اسورة", "انسيال",
               "حلق", "برنيطة", "برنيطه", "طاقية", "طاقيه", "كاب", "نضارة", "نضاره", "نظارة", "نظاره",
               "كرافتة", "كرافته", "حزام", "شال", "طرحة", "طرحه", "جوانتي", "قفاز", "بروش", "دبوس صدر")


def looks_worn(name):
    n = (name or "").strip()
    return any(w in n for w in _WORN_WORDS)


def _project_location_ids(project_id):
    return {r["id"] for r in fetch_all("SELECT id FROM locations WHERE project_id=?", (project_id,))}


def props_grouped(project_id):
    """{"by_location": {location_id: [props]}, "by_character": {character_id: [props]},
    "unplaced": [props]} — المكان لو موجود بياخد الأولوية (مسدس مرصوص على
    الترابيزة = إكسسوار المكان)."""
    locs = _project_location_ids(project_id)
    out = {"by_location": {}, "by_character": {}, "unplaced": []}
    for p in fetch_all("SELECT * FROM props WHERE project_id=? ORDER BY name, id", (project_id,)):
        if p["location_id"] in locs:
            out["by_location"].setdefault(p["location_id"], []).append(p)
        elif p["character_id"]:
            out["by_character"].setdefault(p["character_id"], []).append(p)
        else:
            out["unplaced"].append(p)
    return out


def suggest_prop_location(project_id):
    """prop_id → (location_id, عدد المشاهد هناك، إجمالي مشاهد القطعة) من المشاهد
    اللي القطعة ظهرت فيها. اقتراح بس - اليوزر هو اللي بيأكد."""
    counts = {}
    for r in fetch_all("""
        SELECT sp.prop_id, lv.location_id, COUNT(*) AS n
        FROM scene_props sp JOIN scenes s ON s.id = sp.scene_id
        JOIN location_variants lv ON lv.id = s.location_variant_id
        JOIN props p ON p.id = sp.prop_id
        WHERE p.project_id = ? GROUP BY sp.prop_id, lv.location_id
    """, (project_id,)):
        counts.setdefault(r["prop_id"], []).append((r["location_id"], r["n"]))
    out = {}
    for pid, rows in counts.items():
        loc, n = max(rows, key=lambda x: x[1])
        out[pid] = (loc, n, sum(x[1] for x in rows))
    return out


def prop_scene_counts(project_id):
    return {r["prop_id"]: r["n"] for r in fetch_all("""
        SELECT sp.prop_id, COUNT(*) AS n FROM scene_props sp JOIN props p ON p.id = sp.prop_id
        WHERE p.project_id = ? GROUP BY sp.prop_id""", (project_id,))}


_PROP_FIELDS = ("name", "quantity", "source", "cost", "status", "notes")


def _clean_prop(r):
    vals = {}
    for f in _PROP_FIELDS:
        v = r.get(f)
        if isinstance(v, float) and v != v:          # NaN من الجدول
            v = None
        if f == "quantity":
            try:
                v = max(1, int(v))
            except (TypeError, ValueError):
                v = 1
        elif f == "cost":
            try:
                v = float(v) if v not in (None, "") else None
            except (TypeError, ValueError):
                v = None
        elif isinstance(v, str):
            v = v.strip() or None
        vals[f] = v
    return vals


def save_props_for(project_id, rows, location_id=None, character_id=None):
    """جدول الإكسسوار بتاع مكان واحد (location_id) أو شخصية واحدة (character_id)
    زي ما هو على الشاشة. الصفوف القديمة بتتحدّث بالـ id (عشان روابطها
    بالمشاهد واللقطات تفضل)، الجديدة بتتضاف، واللي اتشال من الجدول بيتمسح.
    المكان/الشخصية لازم يبقوا تبع المشروع. بيرجّع عدد الصفوف."""
    if location_id is not None and location_id not in _project_location_ids(project_id):
        return 0
    if character_id is not None and not fetch_all(
            "SELECT 1 FROM characters WHERE id=? AND project_id=?", (character_id, project_id)):
        return 0
    if location_id is not None:
        current = {p["id"] for p in props_grouped(project_id)["by_location"].get(location_id, [])}
    else:
        current = {p["id"] for p in props_grouped(project_id)["by_character"].get(character_id, [])}
    kept = set()
    n = 0
    with _tx() as ex:
        for r in rows:
            vals = _clean_prop(r)
            if not vals["name"]:
                continue
            pid = r.get("_id")
            pid = int(pid) if pid not in (None, "") and pid == pid else None
            cols = list(_PROP_FIELDS)     # نفس ترتيب الأعمدة في الجملة تحت
            if pid in current:
                ex("UPDATE props SET name=?, quantity=?, source=?, cost=?, status=?, "
                   "notes=? WHERE id=? AND project_id=?", tuple(vals[c] for c in cols) + (pid, project_id))
                kept.add(pid)
            else:
                ex(f"INSERT INTO props (project_id, location_id, character_id, {', '.join(cols)}) "
                   f"VALUES (?, ?, ?, {', '.join('?' * len(cols))})",
                   (project_id, location_id, character_id) + tuple(vals[c] for c in cols))
            n += 1
        for pid in current - kept:
            ex("DELETE FROM props WHERE id=? AND project_id=?", (pid, project_id))
    return n


def place_props(project_id, placements):
    """placements: [(prop_id, location_id أو None, character_id أو None)].
    بيحط كل قطعة في مكانها أو في إيد شخصية. أي مكان/شخصية مش تبع المشروع
    بيتجاهل. بيرجّع عدد اللي اتحط."""
    locs = _project_location_ids(project_id)
    chars = {r["id"] for r in fetch_all("SELECT id FROM characters WHERE project_id=?", (project_id,))}
    n = 0
    with _tx() as ex:
        for prop_id, loc, char in placements:
            loc = loc if loc in locs else None
            char = char if char in chars else None
            if loc is None and char is None:
                continue
            ex("UPDATE props SET location_id=?, character_id=COALESCE(?, character_id) WHERE id=? AND project_id=?",
               (loc, char, prop_id, project_id))
            n += 1
    return n


def move_prop_to_wardrobe(project_id, prop_id, character_id):
    """قطعة بتتلبس ← قطعة "إكسسوار" في الغيار الأساسي للشخصية، والإكسسوار
    نفسه بيتمسح من هنا. بيرجّع id الغيار، أو None لو الشخصية/القطعة مش في المشروع."""
    prop = fetch_all("SELECT * FROM props WHERE id=? AND project_id=?", (prop_id, project_id))
    look = fetch_all("""SELECT cl.id FROM character_looks cl JOIN characters c ON c.id = cl.character_id
                        WHERE cl.character_id=? AND c.project_id=?
                        ORDER BY COALESCE(cl.is_default, 0) DESC, cl.change_number, cl.id LIMIT 1""",
                     (character_id, project_id))
    if not prop or not look:
        return None
    p = prop[0]
    with _tx() as ex:
        ex("""INSERT INTO wardrobe_items (look_id, item_name, category, multiples, cost, notes, position, updated_at)
              SELECT ?, ?, 'إكسسوار', ?, ?, ?, COALESCE(MAX(position), -1) + 1, ?
              FROM wardrobe_items WHERE look_id=?""",
           (look[0]["id"], p["name"], p["quantity"] or 1, p["cost"], p["notes"], _now_iso(), look[0]["id"]))
        ex("DELETE FROM props WHERE id=? AND project_id=?", (prop_id, project_id))
    return look[0]["id"]


def props_summary(project_id):
    r = fetch_all("""
        SELECT COUNT(*) AS n,
               COALESCE(SUM(COALESCE(cost, 0) * COALESCE(quantity, 1)), 0) AS cost,
               SUM(CASE WHEN COALESCE(status, 'مطلوب') = 'مطلوب' THEN 1 ELSE 0 END) AS needed
        FROM props WHERE project_id=?""", (project_id,))[0]
    return {"count": r["n"] or 0, "cost": r["cost"] or 0, "needed": r["needed"] or 0}


# --- مكتبة مواقع التصوير (المالك 2026-09-24) -------------------------------------
# موقع حقيقي (venues) بمساحاته (venue_spaces)، ومكان المشروع بيترشح/يتحجز له
# موقع (location_venue_booking) - نفس فكرة الممثل والشخصية. الموقع بتاع مساحة
# العمل اللي ضافته، وبيبان للكل لو اتنشر (discoverable). العنوان والتواصل
# والسعر بيتفتحوا لصاحبه ولأي فريق رشّحه أو حجزه بس.

VENUE_TYPES = ["شقة", "فيلا", "عمارة", "بيت ريفي", "مكتب", "كافيه", "مطعم", "نادي", "مستشفى", "مدرسة",
               "محل", "مصنع/مخزن", "فندق", "شارع", "محطة مترو", "شاطئ", "صحرا", "استوديو", "أخرى"]
SPACE_TYPES = ["أوضة نوم", "مطبخ", "صالة", "حمام", "مكتب", "بلكونة", "جنينة", "سطح", "سلم/مدخل",
               "جراج", "صالة أفراح", "قاعة", "كافيه", "مطعم", "محل", "شارع", "أخرى"]
VENUE_BOOKING_STATUSES = {"shortlisted": "مرشح", "booked": "محجوز"}

# مرادفات: "أوضة نوم" = "غرفة نوم" = bedroom... للبحث وللترتيب بالأنسب
_PLACE_CONCEPTS = {
    "bedroom": ("اوضة نوم", "اوضه نوم", "غرفة نوم", "غرفه نوم", "bedroom", "نوم"),
    "kitchen": ("مطبخ", "kitchen"),
    "bathroom": ("حمام", "توالت", "تواليت", "bathroom"),
    "living": ("صالة", "صاله", "ليفينج", "ريسبشن", "انتريه", "صالون", "living"),
    "office": ("مكتب", "office"),
    "garden": ("جنينة", "جنينه", "حديقة", "حديقه", "garden"),
    "roof": ("سطح", "روف", "roof"),
    "balcony": ("بلكونة", "بلكونه", "شرفة", "شرفه", "balcony"),
    "stairs": ("سلم", "مدخل", "staircase"),
    "street": ("شارع", "حارة", "حاره", "street"),
    "cafe": ("كافيه", "قهوة", "قهوه", "مقهي", "cafe"),
    "restaurant": ("مطعم", "restaurant"),
    "club": ("نادي", "جيم", "gym", "club"),
    "metro": ("مترو", "metro"),
    "hospital": ("مستشفي", "عيادة", "عياده", "hospital"),
    "school": ("مدرسة", "مدرسه", "فصل", "school"),
    "shop": ("محل", "سوبر ماركت", "shop"),
    "hotel": ("فندق", "hotel"),
    "beach": ("بحر", "شاطئ", "كورنيش", "beach"),
    "desert": ("صحرا", "صحراء", "desert"),
    "villa": ("فيلا", "villa"),
    "apartment": ("شقة", "شقه", "apartment"),
    "garage": ("جراج", "garage"),
    "hall": ("قاعة", "قاعه", "صالة افراح", "hall"),
}


_AR_PREFIXES = ("وال", "بال", "فال", "كال", "لل", "ال")


def _place_tokens(text):
    """كلمات كاملة من غير "ال" وأخواتها: "أوضة النوم" ← "اوضة نوم". الكلمة
    كاملة مش جزء منها - عشان "نادية" ماتبقاش "نادي"."""
    out = []
    for w in normalize(text).split():
        for p in _AR_PREFIXES:
            if w.startswith(p) and len(w) - len(p) >= 3:
                w = w[len(p):]
                break
        out.append(w)
    return " ".join(out)


_CONCEPT_TOKENS = {k: tuple(_place_tokens(w) for w in words) for k, words in _PLACE_CONCEPTS.items()}


def place_concepts(*texts):
    """المعاني اللي في النص ("أوضة النوم بتاعة نادية" ← {bedroom})."""
    blob = " " + " ".join(_place_tokens(x) for x in texts if x) + " "
    return {k for k, words in _CONCEPT_TOKENS.items() if any(f" {w} " in blob for w in words)}


_VENUE_SENSITIVE = ("address", "contact_name", "contact_phone", "price_per_day")
_VENUE_FIELDS = ("name", "venue_type", "city", "area", "description", "maps_url", "address", "contact_name",
                 "contact_phone", "price_per_day", "power", "parking", "noise", "max_crew", "permits")


def venues_visible_to(company_id, query=""):
    """مواقع مساحة العمل دي + المنشورة للمنصة، ومعاها مساحاتها. البحث بالنص
    وبالمعنى (غرفة نوم تلاقي أوضة نوم)."""
    rows = fetch_all("SELECT * FROM venues WHERE owner_company_id=? OR COALESCE(discoverable, 0)=1 "
                     "ORDER BY name, id", (company_id,))
    spaces = {}
    if rows:
        ids = [r["id"] for r in rows]
        for sp in fetch_all(f"SELECT * FROM venue_spaces WHERE venue_id IN ({','.join('?' * len(ids))}) "
                            "ORDER BY id", tuple(ids)):
            spaces.setdefault(sp["venue_id"], []).append(sp)
    out = []
    want = place_concepts(query) if query else set()
    for r in rows:
        v = dict(r, spaces=spaces.get(r["id"], []))
        texts = [v["name"], v["venue_type"], v["city"], v["area"], v["description"]] + \
            [x for sp in v["spaces"] for x in (sp["name"], sp["space_type"], sp["suitable_for"])]
        v["concepts"] = place_concepts(*texts)
        if query and not (matches(query, *texts) or (want and want <= v["concepts"])):
            continue
        out.append(v)
    return out


def venue_for(venue_id, company_id):
    """الموقع لو مساحة العمل دي تقدر تشوفه، ومعاه مساحاته، وإلا None."""
    return next((v for v in venues_visible_to(company_id) if v["id"] == venue_id), None)


def venue_unlocked(venue_id, company_id):
    """البيانات الحساسة: لصاحب الموقع، أو لمساحة عمل رشّحته/حجزته في مشروع عندها."""
    return bool(fetch_all("""
        SELECT 1 FROM venues WHERE id=? AND owner_company_id=?
        UNION ALL
        SELECT 1 FROM location_venue_booking b JOIN projects p ON p.id = b.project_id
        WHERE b.venue_id=? AND p.company_id=? LIMIT 1""", (venue_id, company_id, venue_id, company_id)))


def public_venue(v, company_id):
    """نسخة للعرض: الحقول الحساسة بتتشال لو مش مفتوحة."""
    if venue_unlocked(v["id"], company_id):
        return v
    return {k: (None if k in _VENUE_SENSITIVE else val) for k, val in v.items()}


def _venue_values(values):
    out = []
    for f in _VENUE_FIELDS:
        v = values.get(f)
        if isinstance(v, str):
            v = v.strip() or None
        if f in ("price_per_day",) and v not in (None, ""):
            try:
                v = float(v)
            except (TypeError, ValueError):
                v = None
        if f == "max_crew" and v not in (None, ""):
            try:
                v = int(v)
            except (TypeError, ValueError):
                v = None
        out.append(v)
    return tuple(out)


def add_venue(values, company_id, created_by, discoverable=False):
    if not (values.get("name") or "").strip():
        raise ValueError("اسم الموقع مطلوب")
    now = _now_iso()
    return run_query(f"INSERT INTO venues ({', '.join(_VENUE_FIELDS)}, owner_company_id, discoverable, "
                     f"created_by, created_at, updated_at) VALUES ({', '.join('?' * len(_VENUE_FIELDS))}, ?, ?, ?, ?, ?)",
                     _venue_values(values) + (company_id, 1 if discoverable else 0, created_by, now, now))


def update_venue(venue_id, values, company_id, discoverable=None):
    """التعديل لصاحب الموقع بس (الشرط جوه الجملة)."""
    sets = ", ".join(f"{f}=?" for f in _VENUE_FIELDS)
    params = _venue_values(values)
    extra = ""
    if discoverable is not None:
        extra = ", discoverable=?"
        params += (1 if discoverable else 0,)
    return run_query(f"UPDATE venues SET {sets}{extra}, updated_at=? WHERE id=? AND owner_company_id=?",
                     params + (_now_iso(), venue_id, company_id))


def set_venue_photo(venue_id, company_id, photo_path):
    now = _now_iso()
    return run_query("UPDATE venues SET photo_path=?, photo_updated_at=?, updated_at=? WHERE id=? AND owner_company_id=?",
                     (photo_path, now, now, venue_id, company_id))


def delete_venue(venue_id, company_id):
    return run_query("DELETE FROM venues WHERE id=? AND owner_company_id=?", (venue_id, company_id))


def save_venue_spaces(venue_id, company_id, rows):
    """مساحات الموقع زي الجدول على الشاشة - بالـ id عشان ربط الديكورات بيها
    يفضل. لصاحب الموقع بس. بيرجّع عدد المساحات."""
    if not fetch_all("SELECT 1 FROM venues WHERE id=? AND owner_company_id=?", (venue_id, company_id)):
        return 0
    current = {r["id"] for r in fetch_all("SELECT id FROM venue_spaces WHERE venue_id=?", (venue_id,))}
    kept, n = set(), 0
    with _tx() as ex:
        for r in rows:
            name = (r.get("name") or "").strip() if isinstance(r.get("name"), str) else ""
            if not name:
                continue
            vals = tuple((r.get(f).strip() or None) if isinstance(r.get(f), str) else None
                         for f in ("space_type", "suitable_for", "int_ext", "notes"))
            sid = r.get("_id")
            sid = int(sid) if sid not in (None, "") and sid == sid else None
            if sid in current:
                ex("UPDATE venue_spaces SET name=?, space_type=?, suitable_for=?, int_ext=?, notes=? "
                   "WHERE id=? AND venue_id=?", (name,) + vals + (sid, venue_id))
                kept.add(sid)
            else:
                ex("INSERT INTO venue_spaces (venue_id, name, space_type, suitable_for, int_ext, notes) "
                   "VALUES (?, ?, ?, ?, ?, ?)", (venue_id, name) + vals)
            n += 1
        for sid in current - kept:
            ex("DELETE FROM venue_spaces WHERE id=? AND venue_id=?", (sid, venue_id))
    return n


class AlreadyBookedError(IntegrityError):
    """المكان ده محجوز له موقع تاني - لازم يتلغي الأول."""
    user_message = "المكان ده محجوز له موقع تاني بالفعل. الغي الحجز ده الأول لو عايز تغيّره."

    def __init__(self):
        super().__init__(self.user_message)


def book_venue(project_id, location_id, venue_id, status, note, created_by):
    """يرشّح أو يحجز موقع حقيقي لمكان في المشروع. صف واحد لكل (مكان، موقع)،
    والحجز مايرجعش ترشيح. المكان لازم يبقى في المشروع، والموقع لازم مساحة
    عمل المشروع تقدر تشوفه."""
    if status not in VENUE_BOOKING_STATUSES:
        raise ValueError(status)
    proj = fetch_all("SELECT company_id FROM projects WHERE id=?", (project_id,))
    if not proj or not fetch_all("SELECT 1 FROM locations WHERE id=? AND project_id=?", (location_id, project_id)):
        return None
    if not venue_for(venue_id, proj[0]["company_id"]):
        return None
    if status == "booked" and fetch_all(
            "SELECT 1 FROM location_venue_booking WHERE project_id=? AND location_id=? AND status='booked' "
            "AND venue_id != ?", (project_id, location_id, venue_id)):
        raise AlreadyBookedError()
    now = _now_iso()
    existing = fetch_all("SELECT id, status FROM location_venue_booking WHERE project_id=? AND location_id=? "
                         "AND venue_id=?", (project_id, location_id, venue_id))
    if existing:
        if existing[0]["status"] == "booked" and status == "shortlisted":
            return existing[0]["id"]
        run_query("UPDATE location_venue_booking SET status=?, note=COALESCE(NULLIF(?, ''), note), booked_at=? "
                  "WHERE id=? AND project_id=?", (status, note, now if status == "booked" else None,
                                                  existing[0]["id"], project_id))
        return existing[0]["id"]
    return run_query(
        "INSERT INTO location_venue_booking (project_id, location_id, venue_id, status, note, created_by, "
        "created_at, booked_at) SELECT ?, ?, ?, ?, ?, ?, ?, ? "
        "WHERE EXISTS (SELECT 1 FROM locations WHERE id=? AND project_id=?)",
        (project_id, location_id, venue_id, status, note, created_by, now, now if status == "booked" else None,
         location_id, project_id))


def remove_venue_booking(project_id, booking_id):
    return run_query("DELETE FROM location_venue_booking WHERE id=? AND project_id=?", (booking_id, project_id))


def venue_bookings(project_id):
    """location_id → {"booked": row أو None, "shortlist": [rows]} - اسم الموقع معاه."""
    out = {}
    for r in fetch_all("""
        SELECT b.id, b.location_id, b.venue_id, b.status, b.note, v.name AS venue_name, v.city, v.photo_path
        FROM location_venue_booking b JOIN venues v ON v.id = b.venue_id
        WHERE b.project_id = ? ORDER BY b.created_at, b.id""", (project_id,)):
        slot = out.setdefault(r["location_id"], {"booked": None, "shortlist": []})
        if r["status"] == "booked":
            slot["booked"] = r
        else:
            slot["shortlist"].append(r)
    return out


def location_needs(project_id, location_id):
    """اللي المكان محتاجه من موقع حقيقي: المكان نفسه وديكوراته (أسماءهم) ←
    [(الاسم، المعاني)]. شقة نادية + أوضة النوم + المطبخ..."""
    locs = fetch_all("SELECT id, name, parent_location_id FROM locations WHERE project_id=?", (project_id,))
    me = next((l for l in locs if l["id"] == location_id), None)
    if not me:
        return []
    # لو المكان ليه ديكورات، هي اللي محتاجين نلاقيلها مساحات (أوضة نوم، مطبخ...)؛
    # نوع المبنى نفسه (شقة/فيلا) مش شرط - فيلا تنفع تمثّل شقة. من غير
    # ديكورات، المكان نفسه هو المطلوب.
    kids = [l for l in locs if l["parent_location_id"] == location_id]
    return [(l["name"], place_concepts(l["name"])) for l in (kids or [me])]


def rank_venues_for(project_id, location_id, company_id):
    """المواقع مترتبة بالأنسب للمكان ده: بتغطي كام حاجة من اللي محتاجه
    (المكان وديكوراته)، وبعدها نفس مدينة المكان. كل واحد معاه covered/total."""
    needs = [n for n in location_needs(project_id, location_id) if n[1]]
    loc = fetch_all("SELECT name FROM locations WHERE id=?", (location_id,))
    city = city_of(loc[0]["name"]) if loc else None
    ranked = []
    for v in venues_visible_to(company_id):
        covered = [name for name, c in needs if c & v["concepts"]]
        same_city = bool(city and v.get("city") and normalize(city) in normalize(v["city"]))
        ranked.append(dict(v, covered=covered, total=len(needs), same_city=same_city))
    ranked.sort(key=lambda v: (-len(v["covered"]), not v["same_city"], v["name"]))
    return ranked
