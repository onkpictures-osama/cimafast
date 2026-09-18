"""
إدخال المشاهد اللي اتحللت من ملف السكريبت في قاعدة البيانات:
بيتخطى المشاهد اللي أرقامها موجودة بالفعل، وبينشئ الأماكن والشخصيات
الجديدة اللي اتكشفت تلقائيًا لو مش موجودة.
"""


def import_parsed_scenes(project_id, scenes, fetch_all, run_query):
    summary = {
        'scenes_added': 0,
        'scenes_skipped': [],
        'characters_added': [],
        'locations_added': [],
        'props_added': [],
    }

    existing_scene_numbers = {
        row['scene_number'] for row in fetch_all(
            "SELECT scene_number FROM scenes WHERE project_id=?", (project_id,)
        )
    }

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

    def get_or_create_variant(location_id, int_ext, day_night, variant_hint=None):
        key = (location_id, int_ext, day_night, variant_hint)
        if key in variant_cache:
            return variant_cache[key]

        if variant_hint:
            # الاسم الأصلي قبل الدمج (زي "سطح اليخت بعد لحظات") بيتسجل كاسم
            # الحالة نفسه، عشان يفضل واضح إيه اللي اختلف عن المكان الرئيسي
            rows = fetch_all(
                "SELECT id FROM location_variants WHERE location_id=? AND variant_name=?",
                (location_id, variant_hint),
            )
        else:
            rows = fetch_all(
                "SELECT id FROM location_variants WHERE location_id=? AND int_ext IS ? AND day_night IS ?",
                (location_id, int_ext, day_night),
            )

        if rows:
            variant_id = rows[0]['id']
        else:
            variant_name = variant_hint or f"{int_ext or 'غير محدد'} - {day_night or 'غير محدد'}"
            variant_id = run_query(
                """INSERT INTO location_variants
                (location_id, variant_name, int_ext, day_night, weather, description)
                VALUES (?,?,?,?,?,?)""",
                (location_id, variant_name, int_ext, day_night, None, ''),
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
        if sc['scene_number'] in existing_scene_numbers:
            summary['scenes_skipped'].append(sc['scene_number'])
            continue

        location_variant_id = None
        if sc.get('location_name'):
            loc_id = get_or_create_location(sc['location_name'])
            location_variant_id = get_or_create_variant(
                loc_id, sc['int_ext'], sc['day_night'], sc.get('location_variant_hint')
            )

        new_scene_id = run_query(
            """INSERT INTO scenes
            (project_id, scene_number, int_ext, day_night, weather, location_variant_id, notes)
            VALUES (?,?,?,?,?,?,?)""",
            (project_id, sc['scene_number'], sc['int_ext'], sc['day_night'],
             sc.get('weather'), location_variant_id, sc.get('notes', '')),
        )
        existing_scene_numbers.add(sc['scene_number'])
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
