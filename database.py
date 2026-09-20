"""
طبقة قاعدة البيانات - بتدعم شكلين:
1) SQLite محلي (studio.db) - الافتراضي، مستخدم في التطوير على جهازك.
2) Postgres (Supabase) - يتفعّل تلقائيًا لو لقى DATABASE_URL متظبط في
   st.secrets أو متغيرات البيئة، وده اللي بيستخدمه البرنامج لما يبقى منشور
   أونلاين (عشان بيانات المشروع تفضل محفوظة حتى لو السيرفر أعاد تشغيل).

كل باقي البرنامج (app.py, export.py, importer.py) بيستخدم fetch_all/run_query
من هنا زي ما هي، من غير ما يهتم إحنا شغالين على أي قاعدة بيانات - الاختلافات
(علامات الاستفهام، RETURNING id، ON CONFLICT) بتتترجم أوتوماتيك هنا.
"""
import os
import re
import sqlite3

DB_PATH = os.environ.get("STUDIO_DB_PATH") or os.path.join(
    os.path.dirname(__file__), "studio.db"
)


def _get_database_url():
    """بيدور على رابط قاعدة بيانات Postgres من متغيرات البيئة الأول (مفيد
    وقت الاختبار المحلي)، وبعدين من st.secrets (طريقة Streamlit Cloud
    القياسية لتخزين الأسرار وقت النشر)."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    try:
        import streamlit as st
        return st.secrets.get("DATABASE_URL")
    except Exception:
        return None


DATABASE_URL = _get_database_url()
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    IntegrityError = psycopg2.IntegrityError
else:
    IntegrityError = sqlite3.IntegrityError


# جداول لها UNIQUE constraint بيسمح بترجمة "INSERT OR IGNORE" السكريبت-ستايل
# لصيغة Postgres "ON CONFLICT (...) DO NOTHING" أوتوماتيك
_ON_CONFLICT_TARGETS = {
    "scene_characters": "(scene_id, character_id)",
    "scene_props": "(scene_id, prop_id)",
}
_INSERT_IGNORE_RE = re.compile(r"INSERT\s+OR\s+IGNORE\s+INTO\s+(\w+)", re.IGNORECASE)


def _adapt_query(query):
    """بيحول سؤال مكتوب بصيغة SQLite (علامة ؟ للـ params، وINSERT OR IGNORE)
    لصيغة Postgres (%s، وON CONFLICT DO NOTHING) - من غير ما نحتاج نلمس مئات
    الاستعلامات المكتوبة في باقي الملفات. لو إحنا شغالين على SQLite، السؤال
    بيرجع زي ما هو من غير أي تغيير."""
    if not USE_POSTGRES:
        return query
    m = _INSERT_IGNORE_RE.search(query)
    if m:
        table = m.group(1)
        conflict_cols = _ON_CONFLICT_TARGETS.get(table)
        query = _INSERT_IGNORE_RE.sub(f"INSERT INTO {table}", query)
        if conflict_cols:
            query = query.rstrip().rstrip(";") + f" ON CONFLICT {conflict_cols} DO NOTHING"
    return query.replace("?", "%s")


def get_connection():
    if USE_POSTGRES:
        return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def fetch_all(query, params=()):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(_adapt_query(query), params)
        return cur.fetchall()
    finally:
        conn.close()


def run_query(query, params=()):
    """بينفذ INSERT/UPDATE/DELETE، وبيرجع الـ id بتاع الصف اللي اتضاف لو
    كان السؤال INSERT (زي lastrowid بتاعة SQLite، بس بطريقة تشتغل مع
    Postgres برضو عن طريق RETURNING id)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        q = _adapt_query(query)
        is_insert = q.strip().upper().startswith("INSERT")
        if USE_POSTGRES and is_insert and "RETURNING" not in q.upper():
            q = q.rstrip().rstrip(";") + " RETURNING id"
        cur.execute(q, params)
        last_id = None
        if USE_POSTGRES:
            if is_insert:
                row = cur.fetchone()
                if row:
                    last_id = row["id"] if isinstance(row, dict) else row[0]
        else:
            last_id = cur.lastrowid
        conn.commit()
        return last_id
    finally:
        conn.close()


def run_delete(query, params, friendly_error):
    """بيمسح صف من قاعدة البيانات، ولو الصف ده مستخدم في مكان تاني (زي حالة
    مكان مربوطة بمشهد، أو لوك مربوط بلقطة) بيوري رسالة واضحة بدل ما البرنامج يقع."""
    try:
        run_query(query, params)
        return True
    except IntegrityError:
        import streamlit as st
        st.error(friendly_error)
        return False


def init_db():
    conn = get_connection()
    c = conn.cursor()

    if USE_POSTGRES:
        c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            project_type TEXT,
            default_resolution TEXT,
            default_orientation TEXT,
            default_aspect_ratio TEXT,
            owner_name TEXT,
            owner_role TEXT
        );

        CREATE TABLE IF NOT EXISTS locations (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            base_description TEXT,
            parent_location_id INTEGER REFERENCES locations(id)
        );

        CREATE TABLE IF NOT EXISTS location_variants (
            id SERIAL PRIMARY KEY,
            location_id INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
            variant_name TEXT NOT NULL,
            int_ext TEXT,
            day_night TEXT,
            weather TEXT,
            description TEXT,
            reference_image_path TEXT
        );

        CREATE TABLE IF NOT EXISTS characters (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            role_type TEXT,
            species TEXT,
            gender TEXT,
            personality_notes TEXT,
            reference_image_path TEXT
        );

        CREATE TABLE IF NOT EXISTS character_looks (
            id SERIAL PRIMARY KEY,
            character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
            look_name TEXT NOT NULL,
            apparent_age TEXT,
            makeup_state TEXT,
            hair_state TEXT,
            wardrobe_description TEXT,
            description TEXT,
            is_default INTEGER DEFAULT 0,
            reference_image_path TEXT
        );

        CREATE TABLE IF NOT EXISTS scenes (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            scene_number INTEGER NOT NULL,
            int_ext TEXT,
            day_night TEXT,
            weather TEXT,
            location_variant_id INTEGER REFERENCES location_variants(id),
            notes TEXT,
            is_one_shot INTEGER DEFAULT 0,
            is_fully_storyboarded INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS camera_setups (
            id SERIAL PRIMARY KEY,
            scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
            setup_number INTEGER NOT NULL,
            camera_name TEXT,
            camera_type TEXT,
            lens TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS reference_images (
            id SERIAL PRIMARY KEY,
            location_id INTEGER REFERENCES locations(id) ON DELETE CASCADE,
            character_id INTEGER REFERENCES characters(id) ON DELETE CASCADE,
            image_type TEXT,
            image_path TEXT,
            is_generated INTEGER DEFAULT 0,
            prompt_used TEXT
        );

        CREATE TABLE IF NOT EXISTS shots (
            id SERIAL PRIMARY KEY,
            scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
            setup_id INTEGER REFERENCES camera_setups(id) ON DELETE SET NULL,
            shot_number INTEGER NOT NULL,
            shot_variant TEXT,
            camera_name TEXT,
            shot_size TEXT,
            camera_movement TEXT,
            camera_angle TEXT,
            duration_seconds REAL,
            emotion_intensity INTEGER,
            emotion_label TEXT,
            resolution_override TEXT,
            aspect_ratio_override TEXT,
            visual_style_notes TEXT,
            dialogue_text TEXT,
            include_music INTEGER DEFAULT 0,
            confirmed INTEGER DEFAULT 0,
            storyboard_image_path TEXT
        );

        CREATE TABLE IF NOT EXISTS shot_characters (
            id SERIAL PRIMARY KEY,
            shot_id INTEGER NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
            look_id INTEGER NOT NULL REFERENCES character_looks(id),
            screen_position TEXT,
            facing_direction TEXT
        );

        CREATE TABLE IF NOT EXISTS props (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            continuity_sensitive INTEGER DEFAULT 0,
            character_id INTEGER REFERENCES characters(id)
        );

        CREATE TABLE IF NOT EXISTS shot_props (
            id SERIAL PRIMARY KEY,
            shot_id INTEGER NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
            prop_id INTEGER NOT NULL REFERENCES props(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS scene_characters (
            id SERIAL PRIMARY KEY,
            scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
            character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
            UNIQUE(scene_id, character_id)
        );

        CREATE TABLE IF NOT EXISTS scene_props (
            id SERIAL PRIMARY KEY,
            scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
            prop_id INTEGER NOT NULL REFERENCES props(id) ON DELETE CASCADE,
            UNIQUE(scene_id, prop_id)
        );
        """)
    else:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            project_type TEXT,
            default_resolution TEXT,
            default_orientation TEXT,
            default_aspect_ratio TEXT,
            owner_name TEXT,
            owner_role TEXT
        );

        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            base_description TEXT,
            parent_location_id INTEGER,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_location_id) REFERENCES locations(id)
        );

        CREATE TABLE IF NOT EXISTS location_variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER NOT NULL,
            variant_name TEXT NOT NULL,
            int_ext TEXT,
            day_night TEXT,
            weather TEXT,
            description TEXT,
            reference_image_path TEXT,
            FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            role_type TEXT,
            species TEXT,
            gender TEXT,
            personality_notes TEXT,
            reference_image_path TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS character_looks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            look_name TEXT NOT NULL,
            apparent_age TEXT,
            makeup_state TEXT,
            hair_state TEXT,
            wardrobe_description TEXT,
            description TEXT,
            is_default INTEGER DEFAULT 0,
            reference_image_path TEXT,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS scenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            scene_number INTEGER NOT NULL,
            int_ext TEXT,
            day_night TEXT,
            weather TEXT,
            location_variant_id INTEGER,
            notes TEXT,
            is_one_shot INTEGER DEFAULT 0,
            is_fully_storyboarded INTEGER DEFAULT 0,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (location_variant_id) REFERENCES location_variants(id)
        );

        CREATE TABLE IF NOT EXISTS camera_setups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id INTEGER NOT NULL,
            setup_number INTEGER NOT NULL,
            camera_name TEXT,
            camera_type TEXT,
            lens TEXT,
            notes TEXT,
            FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS reference_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER,
            character_id INTEGER,
            image_type TEXT,
            image_path TEXT,
            is_generated INTEGER DEFAULT 0,
            prompt_used TEXT,
            FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS shots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id INTEGER NOT NULL,
            setup_id INTEGER,
            shot_number INTEGER NOT NULL,
            shot_variant TEXT,
            camera_name TEXT,
            shot_size TEXT,
            camera_movement TEXT,
            camera_angle TEXT,
            duration_seconds REAL,
            emotion_intensity INTEGER,
            emotion_label TEXT,
            resolution_override TEXT,
            aspect_ratio_override TEXT,
            visual_style_notes TEXT,
            dialogue_text TEXT,
            include_music INTEGER DEFAULT 0,
            confirmed INTEGER DEFAULT 0,
            storyboard_image_path TEXT,
            FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
            FOREIGN KEY (setup_id) REFERENCES camera_setups(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS shot_characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shot_id INTEGER NOT NULL,
            look_id INTEGER NOT NULL,
            screen_position TEXT,
            facing_direction TEXT,
            FOREIGN KEY (shot_id) REFERENCES shots(id) ON DELETE CASCADE,
            FOREIGN KEY (look_id) REFERENCES character_looks(id)
        );

        CREATE TABLE IF NOT EXISTS props (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            continuity_sensitive INTEGER DEFAULT 0,
            character_id INTEGER,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (character_id) REFERENCES characters(id)
        );

        CREATE TABLE IF NOT EXISTS shot_props (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shot_id INTEGER NOT NULL,
            prop_id INTEGER NOT NULL,
            FOREIGN KEY (shot_id) REFERENCES shots(id) ON DELETE CASCADE,
            FOREIGN KEY (prop_id) REFERENCES props(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS scene_characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id INTEGER NOT NULL,
            character_id INTEGER NOT NULL,
            FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
            UNIQUE(scene_id, character_id)
        );

        CREATE TABLE IF NOT EXISTS scene_props (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id INTEGER NOT NULL,
            prop_id INTEGER NOT NULL,
            FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
            FOREIGN KEY (prop_id) REFERENCES props(id) ON DELETE CASCADE,
            UNIQUE(scene_id, prop_id)
        );
        """)
    conn.commit()
    _migrate_schema(conn)
    conn.close()


# أعمدة اتضافت بعد أول نسخة من قاعدة البيانات - المهاجرة دي بتضيفها لأي
# قاعدة بيانات قديمة موجودة عند المستخدم من غير ما تأثر على بياناته
_MIGRATIONS = {
    "projects": [
        ("owner_name", "TEXT"),
        ("owner_role", "TEXT"),
        ("data_version", "INTEGER DEFAULT 1"),
    ],
    "locations": [
        ("parent_location_id", "INTEGER"),
    ],
    "location_variants": [
        ("reference_image_path", "TEXT"),
    ],
    "characters": [
        ("species", "TEXT"),
        ("gender", "TEXT"),
        ("reference_image_path", "TEXT"),
    ],
    "character_looks": [
        ("reference_image_path", "TEXT"),
    ],
    "shots": [
        ("storyboard_image_path", "TEXT"),
        ("day_night", "TEXT"),
        ("weather", "TEXT"),
        ("action_description", "TEXT"),
    ],
    "shot_characters": [
        ("has_dialogue", "INTEGER DEFAULT 1"),
    ],
}


def _existing_columns(conn, table):
    if USE_POSTGRES:
        cur = conn.cursor()
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name=%s", (table,)
        )
        return {row["column_name"] for row in cur.fetchall()}
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _migrate_schema(conn):
    for table, columns in _MIGRATIONS.items():
        existing = _existing_columns(conn, table)
        for col_name, col_type in columns:
            if col_name not in existing:
                if USE_POSTGRES:
                    cur = conn.cursor()
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                else:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
    conn.commit()


# ---------- نصوص شرح الحقول (نظام field_definitions المبسط) ----------
FIELD_HELP = {
    "project_type": "نوع المشروع: فيلم طويل، مسلسل، إعلان، أو فيديو قصير. ده بيأثر على القيم الافتراضية زي المدة والنسبة.",
    "default_resolution": "الدقة الافتراضية لكل مشاهد المشروع. تقدر تستثني مشهد معين بدقة مختلفة لاحقًا.",
    "default_orientation": "أفقي (سينما/تلفزيون) أو رأسي (سوشيال ميديا) أو مربع.",
    "int_ext": "داخلي (جوه مكان مغلق)، خارجي (في الهواء الطلق)، أو داخلي/خارجي (مكان جوه لكنه بيشوف بره زي بلكونة أو شباك محل أو عربية فيها زجاج).",
    "day_night": "توقيت المشهد الدرامي، بيأثر على الإضاءة ولون الصورة.",
    "shot_size": "حجم الكادر: من لقطة عامة جدًا (تُظهر المكان كله) لحد لقطة قريبة جدًا (تفاصيل الوجه).",
    "camera_movement": "إزاي الكاميرا بتتحرك أثناء اللقطة. اختر 'ثابتة' لو مفيش حركة.",
    "camera_angle": "زاوية الكاميرا بالنسبة للموضوع: مستوى العين، منخفضة (توحي بالقوة)، مرتفعة (توحي بالضعف)...",
    "emotion_intensity": "قوة المشاعر من 1 (مكتومة جدًا) لحد 5 (ذروة انفعالية).",
    "include_music": "افتراضيًا متروك فاضي (بدون موسيقى) عشان تتحكم فيها بحرية في مرحلة المونتاج بعدين.",
    "apparent_age": "السن الظاهر للشخصية في هذا اللوك تحديدًا (ممكن يختلف عن سنها الحقيقي في القصة كلها).",
    "makeup_state": "حالة المكياج: طبيعي، كامل، بدون، آثار إصابة، أو مكياج شيخوخة.",
    "screen_position": "مكان الشخصية في الكادر: يمين، يسار، أو منتصف الشاشة — مهم للحفاظ على خط الفعل بين اللقطات.",
    "confirmed": "علّم هنا بعد ما تراجع كل تفاصيل اللقطة وتتأكد إنها جاهزة فعليًا للتوليد.",
    "species": "نوع الكائن: إنسان، حيوان، أو كائن خيالي.",
    "gender": "جنس الشخصية. تفاصيل زي الوزن والبنية الجسمانية اكتبها في الملاحظات العامة عن الشخصية.",
}

CAMERA_MOVEMENT_OPTIONS = [
    "ثابتة (Static)", "بان أفقي (Pan)", "تيلت رأسي (Tilt)", "دولي (Dolly)",
    "كرين (Crane)", "أوربيت دائري (Orbit)", "هاندهيلد (Handheld)",
    "تراكينج (Tracking)", "زووم (Zoom)", "درون FPV",
]

SHOT_SIZE_OPTIONS = [
    "عامة جدًا (Extreme Wide)", "عامة (Wide)", "متوسطة (Medium)",
    "قريبة (Close-up)", "قريبة جدًا (Extreme Close-up)",
    "فوق الكتف (Over the Shoulder)", "منظور شخصية (POV)",
]

CAMERA_ANGLE_OPTIONS = ["مستوى العين (Eye Level)", "منخفضة (Low Angle)", "مرتفعة (High Angle)", "عين الطائر (Bird's Eye)", "مائلة (Dutch Angle)"]

SPECIES_OPTIONS = ["إنسان", "حيوان", "كائن خيالي", "غير محدد"]
GENDER_OPTIONS = ["ذكر", "أنثى", "غير محدد"]

PROJECT_ROLE_OPTIONS = [
    "صانع أفلام (Filmmaker)",
    "مخرج (Director)",
    "منتج (Producer)",
    "كاتب سيناريو (Screenwriter)",
    "مدير تصوير (Director of Photography)",
    "مهندس ديكور (Art Director)",
    "مشرف المؤثرات البصرية (VFX Supervisor)",
    "مونتير (Editor)",
    "مصمم أزياء (Costume Designer)",
    "مسؤول اختيار الممثلين (Casting Director)",
    "مساعد مخرج (Assistant Director)",
    "أخرى (Other)",
]

# داخلي/خارجي مضاف عشان الأماكن اللي بتشوف بره من جواها (بلكونة، فاترينة محل،
# عربية فيها زجاج...) - مش داخلي أو خارجي بس
INT_EXT_OPTIONS = ["INT", "EXT", "INT/EXT"]

# مصطلحات اللغة السينمائية (داخلي/خارجي، توقيت اليوم) لازم تفضل مكتوبة
# بالعربي والإنجليزي مع بعض دايمًا، في أي حالة للواجهة (عربي أو إنجليزي) -
# عشان دي مصطلحات صناعة السينما المعروفة عالميًا بالإنجليزي
INT_EXT_LABELS = {
    "INT": "داخلي (INT)",
    "EXT": "خارجي (EXT)",
    "INT/EXT": "داخلي/خارجي (INT/EXT)",
}

DAY_NIGHT_OPTIONS = ["نهار", "ليل", "غروب", "فجر"]
DAY_NIGHT_LABELS = {
    "نهار": "نهار (Day)",
    "ليل": "ليل (Night)",
    "غروب": "غروب (Sunset)",
    "فجر": "فجر (Dawn)",
}


def bilingual_label(value, labels_map):
    """بيرجع النص ثنائي اللغة (عربي (English)) لقيمة زي INT/EXT أو نهار/ليل،
    ودايمًا بنفس الشكل مهما كانت لغة الواجهة الحالية - لأن دي مصطلحات سينمائية
    عالمية لازم تفضل واضحة باللغتين مع بعض."""
    if value is None:
        return labels_map.get("غير محدد", "غير محدد")
    return labels_map.get(value, value)
