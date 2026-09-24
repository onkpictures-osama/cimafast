"""
إدخال المشاهد اللي اتحللت من ملف السكريبت في قاعدة البيانات:
بيتخطى المشاهد اللي أرقامها موجودة بالفعل، وبينشئ الأماكن والشخصيات
الجديدة اللي اتكشفت تلقائيًا لو مش موجودة.
"""


# اسم الحالة الافتراضية لأي مكان. على مستوى الموديول عشان app.py بيحتاجه يشيله
# من العرض (مش كل مشهد يتكتب «... - الشكل الأساسي»).
DEFAULT_VARIANT = 'الشكل الأساسي'


def import_parsed_scenes(project_id, scenes, fetch_all, run_query):
    """المسلسل: كل مشهد لازم يكون عليه episode_number قبل ما يوصل هنا (الشاشة
    بتحدده - الحلقة اللي اليوزر اختارها أو اللي جوه الملف). أي نوع تاني:
    رقم الحلقة بيتشال، عشان فيلم مايطلعش فيه "1/35" لو الـ AI حط حلقة بالغلط.
    المشهد المكرر = نفس (الحلقة، الرقم، الحرف): مشهد 1 في الحلقة 2 مش نسخة
    من مشهد 1 في الحلقة 1."""
    summary = {
        'scenes_added': 0,
        'scenes_skipped': [],
        'characters_added': [],
        'locations_added': [],
        'props_added': [],
    }

    # المفتاح هو (الرقم، الحرف) مش الرقم لوحده: مشهد 35 ومشهد 35A مشهدين
    # مختلفين، ولو اعتبرناهم واحد إعادة الاستيراد بتتخطى المشهد الغلط.
    _proj = fetch_all("SELECT project_type FROM projects WHERE id=?", (project_id,))
    series = bool(_proj) and _proj[0]['project_type'] == 'مسلسل'
    existing_scene_keys = {
        (row['episode_number'] if series else None, row['scene_number'],
         (row['scene_suffix'] if 'scene_suffix' in row.keys() else None) or None)
        for row in fetch_all(
            "SELECT episode_number, scene_number, scene_suffix FROM scenes WHERE project_id=?",
            (project_id,)
        )
    }
    if series:
        # الحلقات اللي المشاهد جاية فيها لازم يبقى ليها صف في episodes
        _eps = {int(sc['episode_number']) for sc in scenes if sc.get('episode_number') is not None}
        _have = {r['episode_number'] for r in fetch_all(
            "SELECT episode_number FROM episodes WHERE project_id=?", (project_id,))}
        for _n in sorted(_eps - _have):
            run_query("INSERT INTO episodes (project_id, episode_number) VALUES (?, ?)", (project_id, _n))
    episode_ids = {r['episode_number']: r['id'] for r in fetch_all(
        "SELECT id, episode_number FROM episodes WHERE project_id=?", (project_id,))} if series else {}

    existing_characters = {
        row['name']: row['id'] for row in fetch_all(
            "SELECT id, name FROM characters WHERE project_id=?", (project_id,)
        )
    }

    location_ids_by_name = {
        row['name']: row['id'] for row in fetch_all(
            "SELECT id, name FROM locations WHERE project_id=?", (project_id,)
        )
    }

    existing_props = {
        row['name']: row['id'] for row in fetch_all(
            "SELECT id, name FROM props WHERE project_id=?", (project_id,)
        )
    }

    variant_cache = {}

    def get_or_create_prop(name):
        if name in existing_props:
            return existing_props[name]
        prop_id = run_query(
            "INSERT INTO props (project_id, name) VALUES (?,?)",
            (project_id, name),
        )
        existing_props[name] = prop_id
        summary['props_added'].append(name)
        return prop_id

    def get_or_create_location(name):
        if name in location_ids_by_name:
            return location_ids_by_name[name]
        new_id = run_query(
            "INSERT INTO locations (project_id, name, base_description) VALUES (?,?,?)",
            (project_id, name, ''),
        )
        location_ids_by_name[name] = new_id
        summary['locations_added'].append(name)
        return new_id

    # الحالة (Variant) بتوصف المكان نفسه دراميًا — محروق، بعد التجديد، بعد
    # سنين. داخلي/خارجي ونهار/ليل بتاعة المشهد مش المكان، ومتخزنة على المشهد
    # نفسه. كنا بنعمل حالة لكل تركيبة منهم («داخلي - نهار»، «داخلي - ليل»...)
    # فالمكان الواحد كان بيطلع بأربع حالات مالهاش أي معنى درامي.
    def get_or_create_variant(location_id, variant_hint=None):
        variant_name = variant_hint or DEFAULT_VARIANT
        key = (location_id, variant_name)
        if key in variant_cache:
            return variant_cache[key]
        # الاسم الأصلي قبل الدمج (زي "سطح اليخت بعد لحظات") بيتسجل كاسم
        # الحالة نفسه، عشان يفضل واضح إيه اللي اختلف عن المكان الرئيسي
        rows = fetch_all(
            "SELECT id FROM location_variants WHERE location_id=? AND variant_name=?",
            (location_id, variant_name),
        )
        if rows:
            variant_id = rows[0]['id']
        else:
            variant_id = run_query(
                "INSERT INTO location_variants (location_id, variant_name, description) VALUES (?,?,?)",
                (location_id, variant_name, ''),
            )
        variant_cache[key] = variant_id
        return variant_id

    def get_or_create_character(name):
        if name in existing_characters:
            return existing_characters[name]
        char_id = run_query(
            "INSERT INTO characters (project_id, name, role_type, personality_notes) VALUES (?,?,?,?)",
            (project_id, name, 'غير محدد', ''),
        )
        run_query(
            """INSERT INTO character_looks
            (character_id, look_name, apparent_age, makeup_state, hair_state, wardrobe_description, description, is_default)
            VALUES (?,?,?,?,?,?,?,?)""",
            (char_id, 'المظهر الافتراضي', '', '', '', '', '', 1),
        )
        existing_characters[name] = char_id
        summary['characters_added'].append(name)
        return char_id

    for sc in scenes:
        _suffix = sc.get('scene_suffix') or None
        _episode = int(sc['episode_number']) if series and sc.get('episode_number') is not None else None
        _key = (_episode, sc['scene_number'], _suffix)
        if _key in existing_scene_keys:
            summary['scenes_skipped'].append(
                (f"{_episode}/" if _episode is not None else "") + f"{sc['scene_number']}{_suffix or ''}")
            continue

        location_variant_id = None
        if sc.get('location_name'):
            loc_id = get_or_create_location(sc['location_name'])
            location_variant_id = get_or_create_variant(loc_id, sc.get('location_variant_hint'))

        new_scene_id = run_query(
            """INSERT INTO scenes
            (project_id, scene_number, scene_suffix, int_ext, day_night, weather,
             location_variant_id, notes, episode_number, episode_id, look_change_notes,
             suggested_shot_size, suggested_camera_movement)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (project_id, sc['scene_number'], _suffix, sc['int_ext'], sc['day_night'],
             sc.get('weather'), location_variant_id, sc.get('notes', ''),
             _episode, episode_ids.get(_episode), sc.get('look_change_notes') or None,
             sc.get('suggested_shot_size') or None,
             sc.get('suggested_camera_movement') or None),
        )
        existing_scene_keys.add(_key)
        summary['scenes_added'] += 1

        # بنسجل رابط المشهد بكل شخصية وإكسسوار ظهر فيه من وقت الاستيراد -
        # ده بيفضل المصدر الأساسي لعدد/أرقام مشاهد كل شخصية في التقارير، حتى
        # قبل ما أي لقطات تتفرغ فعليًا للمشهد ده
        for char_name in sc.get('characters', []):
            char_id = get_or_create_character(char_name)
            run_query(
                "INSERT OR IGNORE INTO scene_characters (scene_id, character_id) VALUES (?,?)",
                (new_scene_id, char_id),
            )

        for prop_name in sc.get('props', []):
            prop_id = get_or_create_prop(prop_name)
            run_query(
                "INSERT OR IGNORE INTO scene_props (scene_id, prop_id) VALUES (?,?)",
                (new_scene_id, prop_id),
            )

    return summary
