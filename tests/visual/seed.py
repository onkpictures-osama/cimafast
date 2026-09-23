"""بيبني قاعدة بيانات مؤقتة فيها مشروع حقيقي الشكل، عشان صور المقارنة
البصرية تبان على محتوى فعلي مش على شاشات فاضية.

البيانات دي بيانات إنتاج معقولة (مشروع، أماكن، شخصيات، إكسسوارات، مشاهد،
لقطات) — مش تليمتري مزيّف ولا أرقام زينة. الهدف إن الشاشة تحت الاختبار
تبقى مزنوقة زي ما هي في الشغل الحقيقي: عربي طويل، أسماء أماكن مركّبة،
ولقطات بعضها مأكّد وبعضها لأ.

مبيتشغّلش على قاعدة البيانات الحقيقية أبدًا: بياخد مسار صريح ويعمل عليه.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def build(db_path):
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["STUDIO_DB_PATH"] = db_path
    sys.path.insert(0, ROOT)
    for mod in ("database",):
        sys.modules.pop(mod, None)
    import database  # noqa: PLC0415

    database.init_db()
    q = database.run_query
    one = database.fetch_all

    # مشروع تاني عشان القايمة المنسدلة يبقى فيها أكتر من اختيار. بيتضاف
    # الأول عشان المشروع اللي فيه بيانات يفضل هو المختار افتراضيًا —
    # البرنامج بيرتب المشاريع ‎ORDER BY id DESC‎
    q(
        "INSERT INTO projects (name, project_type, default_resolution, default_orientation,"
        " default_aspect_ratio) VALUES (?,?,?,?,?)",
        ("إعلان الشاي - نسخة ٣٠ ثانية", "إعلان", "1080p", "رأسي", "9:16"),
    )
    q(
        "INSERT INTO projects (name, project_type, default_resolution, default_orientation,"
        " default_aspect_ratio, owner_name, owner_role) VALUES (?,?,?,?,?,?,?)",
        ("عروسة البحر", "فيلم", "4K", "أفقي", "16:9", "أسامة", "مخرج"),
    )
    pid = one("SELECT id FROM projects ORDER BY id DESC")[0]["id"]

    locations = [
        ("شقة نادية - الدقي", "شقة قديمة في الدور الرابع، بلكونة على الشارع، إضاءة طبيعية قوية الصبح."),
        ("كافيه البورصة - وسط البلد", "كافيه في حارة ضيقة، كراسي خشب، ضجة عالية بعد المغرب."),
        ("كورنيش الإسكندرية - الشتبي", "كورنيش مكشوف، بحر هايج شتاءً، عربيات بتمر ورا الكادر."),
    ]
    loc_ids = []
    for name, desc in locations:
        q("INSERT INTO locations (project_id, name, base_description) VALUES (?,?,?)", (pid, name, desc))
        loc_ids.append(one("SELECT id FROM locations ORDER BY id DESC")[0]["id"])

    variants = [
        (loc_ids[0], "الصبح", "داخلي", "نهار", "صافي", "شمس داخلة من البلكونة على الأرض."),
        (loc_ids[1], "بعد المغرب", "داخلي", "ليل", "غير محدد", "نيون أصفر من اللافتة بره."),
        (loc_ids[2], "غروب", "خارجي", "غروب", "غايم", "ريح قوية، الموج بيضرب السور."),
    ]
    var_ids = []
    for lid, vname, ie, dn, weather, desc in variants:
        q(
            "INSERT INTO location_variants (location_id, variant_name, int_ext, day_night, weather, description)"
            " VALUES (?,?,?,?,?,?)",
            (lid, vname, ie, dn, weather, desc),
        )
        var_ids.append(one("SELECT id FROM location_variants ORDER BY id DESC")[0]["id"])

    characters = [
        ("نادية", "بطل", "إنسان", "أنثى", "مدرّسة موسيقى، بتتكلم واطي وبتزن على التفاصيل."),
        ("حسن", "بطل مساعد", "إنسان", "ذكر", "أخوها الأصغر، بيشتغل في ورشة، عصبي وسريع."),
        ("الأستاذ سمير", "ثانوي", "إنسان", "ذكر", "ناظر المدرسة، رسمي ومتحفظ."),
    ]
    char_ids = []
    for name, role, species, gender, notes in characters:
        q(
            "INSERT INTO characters (project_id, name, role_type, species, gender, personality_notes)"
            " VALUES (?,?,?,?,?,?)",
            (pid, name, role, species, gender, notes),
        )
        char_ids.append(one("SELECT id FROM characters ORDER BY id DESC")[0]["id"])

    look_ids = []
    for cid, look, age, makeup, hair, wardrobe in [
        (char_ids[0], "اللوك الأساسي", "٣٤", "طبيعي", "شعر مربوط", "كارديجان كحلي وجيبة طويلة"),
        (char_ids[1], "بعد الورشة", "٢٦", "عرق وتراب", "شعر مبلول", "تي شيرت رمادي متوسّخ"),
        (char_ids[2], "اللوك الأساسي", "٥٨", "طبيعي", "شعر مفروق", "بدلة بيج وكرافت بني"),
    ]:
        q(
            "INSERT INTO character_looks (character_id, look_name, apparent_age, makeup_state,"
            " hair_state, wardrobe_description, is_default) VALUES (?,?,?,?,?,?,1)",
            (cid, look, age, makeup, hair, wardrobe),
        )
        look_ids.append(one("SELECT id FROM character_looks ORDER BY id DESC")[0]["id"])

    for name, sensitive, cid in [
        ("الكمنجة بتاعة نادية", 1, char_ids[0]),
        ("مفتاح الشقة", 1, None),
        ("فنجان القهوة المكسور", 1, None),
        ("موبايل حسن", 0, char_ids[1]),
    ]:
        q(
            "INSERT INTO props (project_id, name, continuity_sensitive, character_id) VALUES (?,?,?,?)",
            (pid, name, sensitive, cid),
        )

    scenes = [
        (1, "داخلي", "نهار", var_ids[0],
         "نادية بتفتح البلكونة وبتبص على الشارع.\nنادية: مفيش حد جه.\nحسن: استني شوية."),
        (2, "داخلي", "ليل", var_ids[1],
         "حسن قاعد في الكافيه لوحده، بيدوّر في الفنجان.\nحسن: أنا مش هرجع تاني."),
        (3, "خارجي", "غروب", var_ids[2],
         "نادية ماشية على الكورنيش والكمنجة في إيدها.\nنادية: البحر بيعمل كده كل سنة."),
    ]
    scene_ids = []
    for num, ie, dn, vid, notes in scenes:
        q(
            "INSERT INTO scenes (project_id, scene_number, int_ext, day_night, location_variant_id, notes)"
            " VALUES (?,?,?,?,?,?)",
            (pid, num, ie, dn, vid, notes),
        )
        scene_ids.append(one("SELECT id FROM scenes ORDER BY id DESC")[0]["id"])

    q("INSERT INTO scene_characters (scene_id, character_id) VALUES (?,?)", (scene_ids[0], char_ids[0]))
    q("INSERT INTO scene_characters (scene_id, character_id) VALUES (?,?)", (scene_ids[0], char_ids[1]))
    q("INSERT INTO scene_characters (scene_id, character_id) VALUES (?,?)", (scene_ids[1], char_ids[1]))
    q("INSERT INTO scene_characters (scene_id, character_id) VALUES (?,?)", (scene_ids[2], char_ids[0]))

    shots = [
        (scene_ids[0], 1, "لقطة واسعة", "ثابتة", "مستوى النظر", 6, "نادية بتفتح ضلفة البلكونة.", 1),
        (scene_ids[0], 2, "لقطة قريبة", "بان", "مستوى النظر", 4, "إيدها على الترابزين.", 1),
        (scene_ids[1], 1, "لقطة متوسطة", "ثابتة", "مستوى النظر", 8, "حسن بيدوّر في الفنجان.", 0),
        (scene_ids[2], 1, "لقطة واسعة جدًا", "دوللي", "مرتفعة", 12, "الكورنيش كله والموج بيضرب.", 0),
    ]
    for sid, num, size, move, angle, dur, action, confirmed in shots:
        q(
            "INSERT INTO shots (scene_id, shot_number, shot_size, camera_movement, camera_angle,"
            " duration_seconds, action_description, confirmed) VALUES (?,?,?,?,?,?,?,?)",
            (sid, num, size, move, angle, dur, action, confirmed),
        )

    # مكتبة التحليلات: تحليل واحد محفوظ باسم حساب التجربة (shotbot)، عشان شاشة
    # المكتبة تتقاس وفيها كارت حقيقي مش فاضية. من غير شركة: لسه مفيش شركات
    # وقت الزرع (بتتعمل أول ما البرنامج يشتغل)، وصاحب التحليل بيشوفه دايمًا.
    import analysis_library  # noqa: PLC0415
    analysis_library.save(
        {"scenes": [
            {"scene_number": 1, "int_ext": "INT", "day_night": "نهار", "location_name": "شقة نادية - الدقي",
             "characters": ["نادية", "حسن"], "props": [], "notes": ""},
            {"scene_number": 2, "int_ext": "EXT", "day_night": "ليل", "location_name": "الكورنيش",
             "characters": ["حسن"], "props": [], "notes": ""},
        ], "warnings": [], "meta": {}},
        script_name="عروسة البحر - المسودة التانية.docx", owner="shotbot", company_id=None,
        source_project_id=pid, source_project_name="عروسة البحر", origin="ai")

    return pid


if __name__ == "__main__":
    print(build(sys.argv[1]))
