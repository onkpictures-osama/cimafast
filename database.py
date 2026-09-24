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
import datetime as dt
import re
import sqlite3

import audit
import permissions

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
    "memberships": "(company_id, user_id)",
    "project_members": "(project_id, user_id)",
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
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL: القراية مبتستناش الكتابة. في الوضع القديم (delete) أي حفظ من أي مستخدم
    # كان بيقفل قاعدة البيانات كلها على الباقيين لحد ما يخلص. الإعداد ده بيتخزن
    # في الملف نفسه، فالنداء بعد أول مرة مبيعملش حاجة.
    # ‎busy_timeout‎: لو في كتابة تانية شغالة، استنى بدل ما ترمي "database is locked".
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.row_factory = sqlite3.Row
    return conn


def fetch_all(query, params=()):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(_adapt_query(query), params)
        rows = cur.fetchall()
        # Convert Row objects to dicts for consistent .get() access
        if rows and hasattr(rows[0], 'keys'):
            return [dict(row) for row in rows]
        return rows
    finally:
        conn.close()


def run_query(query, params=()):
    """بينفذ INSERT/UPDATE/DELETE، وبيرجع الـ id بتاع الصف اللي اتضاف لو
    كان السؤال INSERT (زي lastrowid بتاعة SQLite، بس بطريقة تشتغل مع
    Postgres برضو عن طريق RETURNING id)."""
    permissions.require("edit")          # F2: المشاهد بس مايكتبش، من أي شاشة
    conn = get_connection()
    try:
        cur = conn.cursor()
        q = _adapt_query(query)
        is_insert = q.strip().upper().startswith("INSERT")
        if USE_POSTGRES and is_insert and "RETURNING" not in q.upper():
            q = q.rstrip().rstrip(";") + " RETURNING id"
        # F3: السجل بيتقري الحالة القديمة قبل التنفيذ وبيتكتب بعده على نفس
        # الاتصال — يعني جوه نفس الـ transaction بتاعت التغيير.
        _watch = audit.watch(cur, query, params)
        cur.execute(q, params)
        last_id = None
        if USE_POSTGRES:
            if is_insert:
                row = cur.fetchone()
                if row:
                    last_id = row["id"] if isinstance(row, dict) else row[0]
        else:
            last_id = cur.lastrowid
        audit.record(cur, _watch, last_id)
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
            parent_location_id INTEGER REFERENCES locations(id),
            maps_url TEXT
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

        -- P9 "خزانة المواهب": ممثل حقيقي (بحسابه أو مضاف من الإدارة)، مش
        -- تابع لمشروع ولا شركة بعينها - العزل بين الشركات (F1) خاص
        -- بالمشاريع، وده استثناء متعمّد (production، القرار المحسوم بتاريخ
        -- 2026-09-23): مسبح ممثلين واحد كل الشركات على المنصة بتدوّر فيه.
        -- discoverable: تبديل الممثل/ة "ظاهر في البحث" من إيقافه. always_public_fields:
        -- أسماء حقول حساسة (مفصولة بفاصلة) اختار الممثل/ة يفضلوا ظاهرين
        -- للكل من غير ما يستنوا ترشيح. is_demo: علامة بيانات تجريبية آمنة
        -- (مش شخص حقيقي) - مايتلخبطش مع بروفايلات حقيقية.
        CREATE TABLE IF NOT EXISTS actors (
            id SERIAL PRIMARY KEY,
            full_name TEXT NOT NULL,
            stage_name TEXT,
            category TEXT,
            gender TEXT,
            bio TEXT,
            credits_text TEXT,
            photo_path TEXT,
            photo_updated_at TEXT,
            height_cm INTEGER,
            weight_kg INTEGER,
            chest_cm INTEGER,
            waist_cm INTEGER,
            hips_cm INTEGER,
            shoe_size_eu INTEGER,
            hair_color TEXT,
            eye_color TEXT,
            contact_phone TEXT,
            contact_email TEXT,
            agent_name TEXT,
            agent_contact TEXT,
            hobbies TEXT,
            drives_car INTEGER NOT NULL DEFAULT 0,
            drives_motorcycle INTEGER NOT NULL DEFAULT 0,
            swims INTEGER NOT NULL DEFAULT 0,
            smokes INTEGER NOT NULL DEFAULT 0,
            skills_notes TEXT,
            link_showreel TEXT,
            link_instagram TEXT,
            link_other TEXT,
            discoverable INTEGER NOT NULL DEFAULT 1,
            always_public_fields TEXT,
            is_demo INTEGER NOT NULL DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        );

        -- ربط ممثل بشخصية جوه مشروع معيّن (كاستينج) - نفس شكل جداول الربط
        -- التانية (scene_characters...) بس عابر للشركات: actor_id من جدول
        -- actors المنصّي، وproject_id بيحدد شركة مين طلبت الربط. الصف ده
        -- نفسه هو "الشورت-ليست" اللي بيفتح الحقول الحساسة لشركة الـ
        -- project_id ده (نفس القرار)، فمفيش داعي لجدول منفصل بس عشان نسجل
        -- مين شاف بيانات الاتصال.
        CREATE TABLE IF NOT EXISTS character_actor_casting (
            id SERIAL PRIMARY KEY,
            actor_id INTEGER NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'shortlisted',
            role_note TEXT,
            created_by TEXT,
            created_at TEXT,
            cast_at TEXT
        );

        -- P10 الملابس: الغيار = المظهر (character_looks) بعد ما اترقّم
        -- (change_number). المشهد بيحدد كل شخصية لابسة أنهي غيار - مش
        -- اللقطة، عشان المشهد اللي لسه ماتفرّغش يبقى معروف فيه اللبس.
        -- وكل غيار ليه قطعه بتفاصيل الشراء/التفصيل/التجهيز.
        CREATE TABLE IF NOT EXISTS scene_character_looks (
            id SERIAL PRIMARY KEY,
            scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
            character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
            look_id INTEGER NOT NULL REFERENCES character_looks(id) ON DELETE CASCADE,
            note TEXT,
            UNIQUE(scene_id, character_id)
        );

        CREATE TABLE IF NOT EXISTS wardrobe_items (
            id SERIAL PRIMARY KEY,
            look_id INTEGER NOT NULL REFERENCES character_looks(id) ON DELETE CASCADE,
            item_name TEXT NOT NULL,
            category TEXT,
            color TEXT,
            material TEXT,
            size TEXT,
            source TEXT,
            multiples INTEGER DEFAULT 1,
            story_state TEXT,
            cost REAL,
            status TEXT,
            notes TEXT,
            position INTEGER DEFAULT 0,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS episodes (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            episode_number INTEGER NOT NULL,
            title TEXT,
            description TEXT,
            air_date TEXT,
            status TEXT DEFAULT 'planning'
        );

        CREATE TABLE IF NOT EXISTS scenes (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            episode_id INTEGER REFERENCES episodes(id) ON DELETE SET NULL,
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

        -- جدول التصوير (الـ stripboard): أيام تصوير، وكل مشهد في يوم واحد بالكتير.
        CREATE TABLE IF NOT EXISTS shooting_days (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            day_number INTEGER NOT NULL,
            shoot_date TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS shooting_day_scenes (
            id SERIAL PRIMARY KEY,
            day_id INTEGER NOT NULL REFERENCES shooting_days(id) ON DELETE CASCADE,
            scene_id INTEGER NOT NULL UNIQUE REFERENCES scenes(id) ON DELETE CASCADE,
            position INTEGER NOT NULL DEFAULT 0
        );

        -- F1: الشركات والمستخدمين وعضوية كل مستخدم في كل شركة. CimaFast نظام ERP
        -- بتستخدمه شركات إنتاج كتير؛ كل مشروع تبع شركة، وكل مستخدم بيشوف مشاريع
        -- الشركات اللي هو عضو فيها بس.
        CREATE TABLE IF NOT EXISTS companies (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            -- B5: نوع الاشتراك (creator / studio / enterprise) — بيحدد إمكانية
            -- إضافة فريق. مبدئي لحد ما B5 يتقفل مع المالك.
            subscription_tier TEXT DEFAULT 'creator'
        );

        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            email TEXT,
            job_title TEXT,
            is_operator INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            must_change_password INTEGER NOT NULL DEFAULT 0,
            created_at TEXT,
            last_login_at TEXT
        );

        CREATE TABLE IF NOT EXISTS memberships (
            id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role TEXT NOT NULL DEFAULT 'department',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            UNIQUE(company_id, user_id)
        );

        -- (أ) أعضاء لكل مشروع (موافقة المالك 2026-09-24): مدير المشروع
        -- والمشغّل بيشوفوا كل مشاريع مساحة العمل؛ الباقي بيشوف المشاريع اللي
        -- اتضافوا ليها بس. projects.members_scoped = 0 → مشروع قديم مفتوح لكل
        -- الأعضاء لحد ما المدير يحدد أعضاءه أول مرة (محدش بيخسر دخول).
        -- دعوة لفريق مشروع (المالك 2026-09-24): لينك بيتبعت (واتساب/نسخ)،
        -- اللي بيفتحه يدخل أو يعمل حساب ويلاقي المشروع. التوكن نفسه مش متخزن
        -- - الـ hash بتاعه بس - فتسريب القاعدة مايديش لينكات شغالة.
        -- مكتبة مواقع التصوير (المالك 2026-09-24): موقع حقيقي (شقة، فيلا، نادي،
        -- محطة مترو...) بمساحاته اللي جواه، وكل مساحة "ينفع كـ" إيه. بتاع مساحة
        -- العمل اللي ضافته (السكاوتنج شغل فريقك) - وممكن ينتشر للمنصة (discoverable).
        -- العنوان بالظبط وتليفون صاحبه والسعر حساسين: لصاحب المساحة ولأي فريق
        -- رشّحه أو حجزه بس.
        CREATE TABLE IF NOT EXISTS venues (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            venue_type TEXT,
            city TEXT,
            area TEXT,
            description TEXT,
            maps_url TEXT,
            photo_path TEXT,
            photo_updated_at TEXT,
            address TEXT,
            contact_name TEXT,
            contact_phone TEXT,
            price_per_day REAL,
            power TEXT,
            parking TEXT,
            noise TEXT,
            max_crew INTEGER,
            permits TEXT,
            owner_company_id INTEGER,
            discoverable INTEGER DEFAULT 0,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS venue_spaces (
            id SERIAL PRIMARY KEY,
            venue_id INTEGER NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            space_type TEXT,
            suitable_for TEXT,
            int_ext TEXT,
            photo_path TEXT,
            notes TEXT
        );

        -- مكان في المشروع (شقة نادية أو ديكور جواها) ← موقع حقيقي: ترشيح أو
        -- حجز، والديكور بيتربط بالمساحة اللي هتقوم بدوره (space_id).
        CREATE TABLE IF NOT EXISTS location_venue_booking (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            location_id INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
            venue_id INTEGER NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
            space_id INTEGER,
            status TEXT NOT NULL DEFAULT 'shortlisted',
            note TEXT,
            created_by TEXT,
            created_at TEXT,
            booked_at TEXT
        );

        CREATE TABLE IF NOT EXISTS project_invites (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            invitee_name TEXT,
            contact TEXT,
            job_title TEXT,
            permission TEXT NOT NULL DEFAULT 'edit',
            created_by TEXT,
            created_at TEXT,
            expires_at TEXT,
            accepted_by TEXT,
            accepted_at TEXT,
            revoked INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS project_members (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            added_by TEXT,
            added_at TEXT,
            UNIQUE(project_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS user_profile (
            username TEXT PRIMARY KEY,
            last_project_id INTEGER,
            last_tab TEXT,
            updated_at TEXT
        );

        -- H4: التنبيهات اتشافت لحد أنهي صف في audit_log، لكل مستخدم. جدول لوحده
        -- مش عمود في user_profile: ده بيتمسح ويتكتب تاني مع كل تبويب بيتفتح.
        CREATE TABLE IF NOT EXISTS notification_seen (
            username TEXT PRIMARY KEY,
            last_seen_id INTEGER,
            updated_at TEXT
        );

        -- F3: سجل التدقيق وأحداث الاستخدام (audit.py). من غير مفاتيح خارجية عن
        -- قصد: السجل لازم يفضل موجود حتى لو المشروع أو الشركة اتمسحوا — ده
        -- بالظبط الوقت اللي بيتسأل فيه "مين مسح ده".
        CREATE TABLE IF NOT EXISTS audit_log (
            id SERIAL PRIMARY KEY,
            at TEXT NOT NULL,
            username TEXT,
            company_id INTEGER,
            project_id INTEGER,
            entity TEXT NOT NULL,
            entity_id INTEGER,
            action TEXT NOT NULL,
            summary TEXT,
            changes TEXT,
            source TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_audit_company_at ON audit_log (company_id, at DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log (entity, entity_id);
        CREATE INDEX IF NOT EXISTS idx_audit_username ON audit_log (username, at DESC);

        CREATE TABLE IF NOT EXISTS usage_events (
            id SERIAL PRIMARY KEY,
            at TEXT NOT NULL,
            username TEXT,
            company_id INTEGER,
            project_id INTEGER,
            event TEXT NOT NULL,
            target TEXT,
            detail TEXT,
            source TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_usage_company_at ON usage_events (company_id, at DESC);
        CREATE INDEX IF NOT EXISTS idx_usage_event_at ON usage_events (event, at DESC);
        -- مكتبة التحليلات (analysis_library.py): كل تحليل سيناريو خلص بيتحفظ هنا
        -- على مستوى الحساب، بره أي مشروع، عشان يتستورد في أي مشروع تاني بعدين.
        -- من غير مفاتيح خارجية عن قصد: التحليل لازم يفضل موجود لو المشروع اللي
        -- جه منه اتمسح — ده بالظبط سيناريو "استوردته في المشروع الغلط".
        CREATE TABLE IF NOT EXISTS analysis_library (
            id SERIAL PRIMARY KEY,
            company_id INTEGER,
            owner_username TEXT,
            script_name TEXT NOT NULL,
            source_project_id INTEGER,
            source_project_name TEXT,
            analysed_at TEXT,
            saved_at TEXT NOT NULL,
            origin TEXT NOT NULL DEFAULT 'ai',
            job_id TEXT,
            content_hash TEXT NOT NULL,
            scene_count INTEGER NOT NULL DEFAULT 0,
            character_count INTEGER NOT NULL DEFAULT 0,
            location_count INTEGER NOT NULL DEFAULT 0,
            payload TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_library_company ON analysis_library (company_id, saved_at);
        CREATE INDEX IF NOT EXISTS idx_library_owner ON analysis_library (owner_username);
        CREATE INDEX IF NOT EXISTS idx_library_hash ON analysis_library (content_hash);
        CREATE INDEX IF NOT EXISTS idx_library_job ON analysis_library (job_id);
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
            maps_url TEXT,
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

        -- P9 "خزانة المواهب" - نفس الجدولين بتوع نسخة Postgres فوق، بشرحهم
        -- هناك. مفيش FOREIGN KEY على شركة عمدًا - المسبح عابر للشركات.
        CREATE TABLE IF NOT EXISTS actors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            stage_name TEXT,
            category TEXT,
            gender TEXT,
            bio TEXT,
            credits_text TEXT,
            photo_path TEXT,
            photo_updated_at TEXT,
            height_cm INTEGER,
            weight_kg INTEGER,
            chest_cm INTEGER,
            waist_cm INTEGER,
            hips_cm INTEGER,
            shoe_size_eu INTEGER,
            hair_color TEXT,
            eye_color TEXT,
            contact_phone TEXT,
            contact_email TEXT,
            agent_name TEXT,
            agent_contact TEXT,
            hobbies TEXT,
            drives_car INTEGER NOT NULL DEFAULT 0,
            drives_motorcycle INTEGER NOT NULL DEFAULT 0,
            swims INTEGER NOT NULL DEFAULT 0,
            smokes INTEGER NOT NULL DEFAULT 0,
            skills_notes TEXT,
            link_showreel TEXT,
            link_instagram TEXT,
            link_other TEXT,
            discoverable INTEGER NOT NULL DEFAULT 1,
            always_public_fields TEXT,
            is_demo INTEGER NOT NULL DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS character_actor_casting (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL,
            character_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'shortlisted',
            role_note TEXT,
            created_by TEXT,
            created_at TEXT,
            cast_at TEXT,
            FOREIGN KEY (actor_id) REFERENCES actors(id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
        );

        -- P10 الملابس: الغيار = المظهر (character_looks) بعد ما اترقّم
        -- (change_number). المشهد بيحدد كل شخصية لابسة أنهي غيار - مش
        -- اللقطة، عشان المشهد اللي لسه ماتفرّغش يبقى معروف فيه اللبس.
        -- وكل غيار ليه قطعه بتفاصيل الشراء/التفصيل/التجهيز.
        CREATE TABLE IF NOT EXISTS scene_character_looks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id INTEGER NOT NULL,
            character_id INTEGER NOT NULL,
            look_id INTEGER NOT NULL,
            note TEXT,
            UNIQUE(scene_id, character_id),
            FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
            FOREIGN KEY (look_id) REFERENCES character_looks(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS wardrobe_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            look_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            category TEXT,
            color TEXT,
            material TEXT,
            size TEXT,
            source TEXT,
            multiples INTEGER DEFAULT 1,
            story_state TEXT,
            cost REAL,
            status TEXT,
            notes TEXT,
            position INTEGER DEFAULT 0,
            updated_at TEXT,
            FOREIGN KEY (look_id) REFERENCES character_looks(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            episode_number INTEGER NOT NULL,
            title TEXT,
            description TEXT,
            air_date TEXT,
            status TEXT DEFAULT 'planning',
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS scenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            episode_id INTEGER,
            scene_number INTEGER NOT NULL,
            int_ext TEXT,
            day_night TEXT,
            weather TEXT,
            location_variant_id INTEGER,
            notes TEXT,
            is_one_shot INTEGER DEFAULT 0,
            is_fully_storyboarded INTEGER DEFAULT 0,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE SET NULL,
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

        -- جدول التصوير (الـ stripboard): أيام تصوير، وكل مشهد في يوم واحد بالكتير.
        CREATE TABLE IF NOT EXISTS shooting_days (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            day_number INTEGER NOT NULL,
            shoot_date TEXT,
            notes TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS shooting_day_scenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_id INTEGER NOT NULL,
            scene_id INTEGER NOT NULL UNIQUE,
            position INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (day_id) REFERENCES shooting_days(id) ON DELETE CASCADE,
            FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
        );

        -- F1: الشركات والمستخدمين وعضوية كل مستخدم في كل شركة. CimaFast نظام ERP
        -- بتستخدمه شركات إنتاج كتير؛ كل مشروع تبع شركة، وكل مستخدم بيشوف مشاريع
        -- الشركات اللي هو عضو فيها بس.
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            -- B5: نوع الاشتراك (creator / studio / enterprise) — بيحدد إمكانية
            -- إضافة فريق. مبدئي لحد ما B5 يتقفل مع المالك.
            subscription_tier TEXT DEFAULT 'creator'
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            email TEXT,
            job_title TEXT,
            is_operator INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            must_change_password INTEGER NOT NULL DEFAULT 0,
            created_at TEXT,
            last_login_at TEXT
        );

        CREATE TABLE IF NOT EXISTS memberships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'department',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(company_id, user_id)
        );

        -- مكتبة مواقع التصوير (المالك 2026-09-24): موقع حقيقي (شقة، فيلا، نادي،
        -- محطة مترو...) بمساحاته اللي جواه، وكل مساحة "ينفع كـ" إيه. بتاع مساحة
        -- العمل اللي ضافته (السكاوتنج شغل فريقك) - وممكن ينتشر للمنصة (discoverable).
        -- العنوان بالظبط وتليفون صاحبه والسعر حساسين: لصاحب المساحة ولأي فريق
        -- رشّحه أو حجزه بس.
        CREATE TABLE IF NOT EXISTS venues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            venue_type TEXT,
            city TEXT,
            area TEXT,
            description TEXT,
            maps_url TEXT,
            photo_path TEXT,
            photo_updated_at TEXT,
            address TEXT,
            contact_name TEXT,
            contact_phone TEXT,
            price_per_day REAL,
            power TEXT,
            parking TEXT,
            noise TEXT,
            max_crew INTEGER,
            permits TEXT,
            owner_company_id INTEGER,
            discoverable INTEGER DEFAULT 0,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS venue_spaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venue_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            space_type TEXT,
            suitable_for TEXT,
            int_ext TEXT,
            photo_path TEXT,
            notes TEXT,
            FOREIGN KEY (venue_id) REFERENCES venues(id) ON DELETE CASCADE
        );

        -- مكان في المشروع (شقة نادية أو ديكور جواها) ← موقع حقيقي: ترشيح أو
        -- حجز، والديكور بيتربط بالمساحة اللي هتقوم بدوره (space_id).
        CREATE TABLE IF NOT EXISTS location_venue_booking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            location_id INTEGER NOT NULL,
            venue_id INTEGER NOT NULL,
            space_id INTEGER,
            status TEXT NOT NULL DEFAULT 'shortlisted',
            note TEXT,
            created_by TEXT,
            created_at TEXT,
            booked_at TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE,
            FOREIGN KEY (venue_id) REFERENCES venues(id) ON DELETE CASCADE
        );

        -- دعوات فريق المشروع - نفس الشرح في نسخة Postgres فوق
        CREATE TABLE IF NOT EXISTS project_invites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            invitee_name TEXT,
            contact TEXT,
            job_title TEXT,
            permission TEXT NOT NULL DEFAULT 'edit',
            created_by TEXT,
            created_at TEXT,
            expires_at TEXT,
            accepted_by TEXT,
            accepted_at TEXT,
            revoked INTEGER DEFAULT 0,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        -- (أ) أعضاء لكل مشروع - نفس الشرح في نسخة Postgres فوق
        CREATE TABLE IF NOT EXISTS project_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            added_by TEXT,
            added_at TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(project_id, user_id)
        );

        -- الصفحة الرئيسية: "كمّل من مكان ما وقفت" (آخر مشروع وتبويب لكل مستخدم)
        CREATE TABLE IF NOT EXISTS user_profile (
            username TEXT PRIMARY KEY,
            last_project_id INTEGER,
            last_tab TEXT,
            updated_at TEXT
        );

        -- H4: التنبيهات اتشافت لحد أنهي صف في audit_log، لكل مستخدم. جدول لوحده
        -- مش عمود في user_profile: ده بيتمسح ويتكتب تاني مع كل تبويب بيتفتح.
        CREATE TABLE IF NOT EXISTS notification_seen (
            username TEXT PRIMARY KEY,
            last_seen_id INTEGER,
            updated_at TEXT
        );

        -- F3: سجل التدقيق وأحداث الاستخدام (audit.py). من غير مفاتيح خارجية عن
        -- قصد: السجل لازم يفضل موجود حتى لو المشروع أو الشركة اتمسحوا — ده
        -- بالظبط الوقت اللي بيتسأل فيه "مين مسح ده".
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            at TEXT NOT NULL,                 -- ISO-8601 بتوقيت UTC
            username TEXT,                    -- مين عمل الحركة (NULL = النظام نفسه)
            company_id INTEGER,               -- العزل بين الشركات (F1)
            project_id INTEGER,
            entity TEXT NOT NULL,             -- اسم الجدول، أو auth / team
            entity_id INTEGER,
            action TEXT NOT NULL,             -- create / update / delete / login / role_change …
            summary TEXT,                     -- سطر عربي جاهز للعرض
            changes TEXT,                     -- JSON: القديم والجديد
            source TEXT                       -- app / board / system
        );
        CREATE INDEX IF NOT EXISTS idx_audit_company_at ON audit_log (company_id, at DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log (entity, entity_id);
        CREATE INDEX IF NOT EXISTS idx_audit_username ON audit_log (username, at DESC);

        -- تحليلات الاستخدام: أخف وأكتر عددًا، وبتتقري مجمّعة مش صف صف.
        CREATE TABLE IF NOT EXISTS usage_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            at TEXT NOT NULL,
            username TEXT,
            company_id INTEGER,
            project_id INTEGER,
            event TEXT NOT NULL,              -- login / screen / export / ai / search
            target TEXT,                      -- التبويب أو نوع الملف أو اسم الشاشة
            detail TEXT,                      -- JSON اختياري
            source TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_usage_company_at ON usage_events (company_id, at DESC);
        CREATE INDEX IF NOT EXISTS idx_usage_event_at ON usage_events (event, at DESC);
        -- مكتبة التحليلات (analysis_library.py): كل تحليل سيناريو خلص بيتحفظ هنا
        -- على مستوى الحساب، بره أي مشروع، عشان يتستورد في أي مشروع تاني بعدين.
        -- من غير مفاتيح خارجية عن قصد: التحليل لازم يفضل موجود لو المشروع اللي
        -- جه منه اتمسح — ده بالظبط سيناريو "استوردته في المشروع الغلط".
        CREATE TABLE IF NOT EXISTS analysis_library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            owner_username TEXT,
            script_name TEXT NOT NULL,
            source_project_id INTEGER,
            source_project_name TEXT,
            analysed_at TEXT,
            saved_at TEXT NOT NULL,
            origin TEXT NOT NULL DEFAULT 'ai',
            job_id TEXT,
            content_hash TEXT NOT NULL,
            scene_count INTEGER NOT NULL DEFAULT 0,
            character_count INTEGER NOT NULL DEFAULT 0,
            location_count INTEGER NOT NULL DEFAULT 0,
            payload TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_library_company ON analysis_library (company_id, saved_at);
        CREATE INDEX IF NOT EXISTS idx_library_owner ON analysis_library (owner_username);
        CREATE INDEX IF NOT EXISTS idx_library_hash ON analysis_library (content_hash);
        CREATE INDEX IF NOT EXISTS idx_library_job ON analysis_library (job_id);
        """)
    conn.commit()
    _migrate_schema(conn)
    _backfill_default_looks(conn)
    _rename_project_types(conn)
    _scope_all_projects(conn)
    conn.close()


# أعمدة اتضافت بعد أول نسخة من قاعدة البيانات - المهاجرة دي بتضيفها لأي
# قاعدة بيانات قديمة موجودة عند المستخدم من غير ما تأثر على بياناته
_MIGRATIONS = {
    # H4: الأقسام اللي التغيير يخصّها (",art,camera," أو ",*,"). الصفوف القديمة
    # بتفضل NULL — مابتطلعش كتنبيهات، ودي بالظبط الحاجة الصح: دي تاريخ مش جديد.
    "audit_log": [
        ("departments", "TEXT"),
    ],
    # P9: مين أضاف بروفايل الممثل/ة. المسبح عابر للشركات في القراءة، بس
    # التعديل للشركة اللي أضافته (أو مشغّل المنصة) بس. NULL = اتضاف من
    # الإدارة (زي بيانات العرض التجريبية) - المشغّل بس يعدّله.
    "actors": [
        ("owner_company_id", "INTEGER"),
        ("created_by", "TEXT"),
        # بروفايل عام بلينك سري (public_profile.py). NULL = مش منشور (الافتراضي).
        # إلغاء المشاركة بيرجّعه NULL، فاللينك القديم بيموت فورًا.
        ("public_share_token", "TEXT"),
        ("public_share_at", "TEXT"),
    ],
    "companies": [
        # B5: نوع الاشتراك (creator / studio / enterprise). مبدئي — لحد ما
        # B5 يتقفل مع المالك، كل الشركات الموجودة بتاخد creator.
        ("subscription_tier", "TEXT DEFAULT 'creator'"),
    ],
    "projects": [
        # F1: كل مشروع تبع شركة. المشاريع القديمة بتتربط بالشركة الافتراضية في
        # accounts.migrate_accounts() أول ما البرنامج يشتغل.
        ("company_id", "INTEGER"),
        ("owner_name", "TEXT"),
        ("owner_role", "TEXT"),
        ("data_version", "INTEGER DEFAULT 1"),
        # تفاصيل خاصة بنوع المشروع (JSON): مدة الحلقة للمسلسل، المنصة للفيديو
        # القصير... - عمود واحد بدل عمود لكل نوع، لأن كل نوع أسئلته غير التاني.
        ("type_details", "TEXT"),
        # (أ) 1 = المشروع ليه أعضاء محددين (project_members). 0/NULL = مشروع
        # قديم مفتوح لكل أعضاء مساحة العمل زي ما كان قبل الميزة.
        ("members_scoped", "INTEGER DEFAULT 0"),
        # فريق المشروع (2026-09-24): اللي أنشأ المشروع = مدير المشروع. القديم
        # (NULL) مديره أدمن مساحة العمل اللي هو فيها.
        ("created_by", "TEXT"),
    ],
    # دور كل واحد في المشروع (شغلانته: مدير تصوير، مونتير...) وصلاحيته فيه
    "project_members": [
        ("job_title", "TEXT"),
        ("permission", "TEXT DEFAULT 'edit'"),
    ],
    "locations": [
        ("parent_location_id", "INTEGER"),
        # صورة للمكان نفسه، مستقلة عن صور حالاته: مرفوعة أو من الكاميرا أو
        # متولّدة بالذكاء الاصطناعي.
        ("reference_image_path", "TEXT"),
        # لينك الموقع الجغرافي: Google Maps أو Waze أو أي خريطة تانية. نص حر
        # عن قصد — اليوزر بيلزق اللينك اللي عنده، مش بنقيّده بخدمة واحدة.
        ("maps_url", "TEXT"),
    ],
    # حرف المشهد المقسوم (35A / 35B). scene_number فضل رقم صحيح عن قصد:
    # فيه حسابات بتعتمد عليه (scene_number + 1 وقت الإدراج) وكانت هتتكسر لو
    # بقى نص. الحرف بيتخزن لوحده والعرض بيجمعهم.
    "scenes": [
        ("scene_suffix", "TEXT"),
        # حقول البرومبت الجديد (2026-09-21). من غيرها الـ AI بيرجّعها
        # وبتتقري صح وبعدين بتترمي عند الاستيراد لأن مفيش مكان تتخزن فيه.
        ("episode_number", "INTEGER"),
        ("look_change_notes", "TEXT"),
        ("suggested_shot_size", "TEXT"),
        ("suggested_camera_movement", "TEXT"),
        # الجدول الأصلي فيه episode_id بس القواعد القديمة (/v1 والإنتاج)
        # اتعملت قبله ومفيش مهاجرة كانت بتضيفه - فـ repo.add_scene كانت
        # بتقع بـ "no such column" في أي "إضافة مشهد" يدوي (اتلقط 2026-09-24).
        # مصدر الحقيقة للحلقة هو episode_number؛ ده بيتملى جنبه.
        ("episode_id", "INTEGER"),
        # مجاميع/كومبارس الخلفية (طلب المالك 2026-09-24): زرار ملاحظات بسيط
        # لكل مشهد، مش شخصيات جديدة في جدول characters - المجموعة مالهاش
        # هوية فردية ولا مظهر ولا كاستينج زي الشخصية، إنما عدد تقريبي ووصف
        # لبس وفعل جماعي بس. has_background_group بثلاث حالات عن قصد:
        # NULL = لسه محدّش راجع المشهد ده، 0 = اتراجع وفعلاً مفيهوش مجاميع،
        # 1 = فيه (والتفاصيل في الأعمدة اللي بعدها). الفرق بين NULL و0 هو
        # اللي بيوريّنا مشاهد البريكداون اللي لسه محتاجة مراجعة.
        ("has_background_group", "INTEGER"),
        ("background_group_headcount", "TEXT"),
        ("background_group_wardrobe", "TEXT"),
        ("background_group_action", "TEXT"),
    ],
    "location_variants": [
        ("reference_image_path", "TEXT"),
    ],
    # الإكسسوار (اتفاق المالك 2026-09-24): إكسسوار الديكور تابع للمكان/الديكور
    # (location_id)، واللي بيتمسك في الإيد (زي المسدس) تابع للشخصية
    # (character_id - موجود من الأول). اللي بيتلبس بيروح للملابس، مش هنا.
    # location_id من غير FK عن قصد: مكان اتمسح = الإكسسوار يرجع "محتاج مكان"
    # بدل ما يختفي (repo.unplaced_props).
    "props": [
        ("location_id", "INTEGER"),
        ("quantity", "INTEGER DEFAULT 1"),
        ("source", "TEXT"),
        ("cost", "REAL"),
        ("status", "TEXT"),
        ("notes", "TEXT"),
    ],
    "characters": [
        ("species", "TEXT"),
        ("gender", "TEXT"),
        ("reference_image_path", "TEXT"),
        # رقم الممثل في الكول شيت والتفريغ (Cast ID): ثابت بعد ما يتحط، عشان
        # "رقم 3" يفضل نفس الشخص في كل ورقة حتى لو شخصيات اتضافت بعدين.
        ("cast_number", "INTEGER"),
    ],
    "character_looks": [
        ("reference_image_path", "TEXT"),
        # P10: رقم الغيار (غيار 1، 2، 3...) - بيتملى للقديم بـ repo.ensure_change_numbers
        ("change_number", "INTEGER"),
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


def scene_label(scene):
    """رقم المشهد زي ما بيتكتب في الورق: 35 أو 35A، وفي المسلسل 3/35
    (الحلقة 3، المشهد 35).

    كل حتة بتعرض رقم مشهد لازم تعدي من هنا، عشان الرقم في البرنامج يفضل هو
    نفسه الرقم اللي الفريق ماسكه في التصوير. رقم الحلقة بيتكتب بس لو
    موجود في الصف - والاستيراد مابيحطهوش غير لمشاريع المسلسلات."""
    if scene is None:
        return ""
    try:
        number = scene["scene_number"]
        keys = scene.keys()
        suffix = scene["scene_suffix"] if "scene_suffix" in keys else None
        episode = scene["episode_number"] if "episode_number" in keys else None
    except (TypeError, KeyError, AttributeError):
        number = scene.get("scene_number") if hasattr(scene, "get") else scene
        suffix = scene.get("scene_suffix") if hasattr(scene, "get") else None
        episode = scene.get("episode_number") if hasattr(scene, "get") else None
    label = f"{number}{suffix or ''}"
    return f"{episode}/{label}" if episode is not None else label


def next_free_number(numbers):
    """الرقم اللي المفروض يقترحه فورم الإضافة: أكبر رقم موجود + 1.

    الفورم كان بيبدأ من 1 دايمًا، ففي مشروع فيه 165 مشهد أي إضافة سريعة كانت
    بتطلع مشهد 1 مكرر. الحروف (35A) مش بتأثر — الرقم الصحيح بس هو اللي بيتعد.
    """
    values = [int(n) for n in numbers if n is not None]
    return max(values) + 1 if values else 1


def _existing_columns(conn, table):
    if USE_POSTGRES:
        cur = conn.cursor()
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name=%s", (table,)
        )
        return {row["column_name"] for row in cur.fetchall()}
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


# فهارس على أعمدة اتضافت بعدين — لازم تتعمل بعد _MIGRATIONS مش مع إنشاء الجداول،
# لأن العمود نفسه لسه مش موجود في قاعدة قديمة وقت الإنشاء.
_INDEXES = [
    # H4: جرس التنبيهات بيسأل كل ٣٠ ثانية "إيه الجديد في مشاريعي".
    ("idx_audit_project_at", "audit_log (project_id, at)"),
    # كل قراءة مشاريع بتفلتر بالشركة (accounts.projects_for)، فده الفهرس اللي
    # العزل بين الشركات بيقف عليه.
    ("idx_projects_company", "projects (company_id)"),
    ("idx_props_location", "props (location_id)"),
    ("idx_project_members_user", "project_members (user_id)"),
    ("idx_venues_company", "venues (owner_company_id)"),
    ("idx_venue_spaces_venue", "venue_spaces (venue_id)"),
    ("idx_venue_booking_project", "location_venue_booking (project_id)"),
    ("idx_venue_booking_location", "location_venue_booking (location_id)"),
    # قايمة خزانة المواهب بتفلتر بـ discoverable، وصف الكاستينج بيتقري
    # بالممثل/بالمشروع/بالشخصية - نفس منطق شركة المشاريع فوق.
    ("idx_actors_discoverable", "actors (discoverable)"),
    # الصفحة العامة بتدوّر بالتوكن في كل زيارة (من غير دخول)
    ("idx_actors_public_share", "actors (public_share_token)"),
    ("idx_casting_actor", "character_actor_casting (actor_id)"),
    ("idx_casting_project", "character_actor_casting (project_id)"),
    ("idx_casting_character", "character_actor_casting (character_id)"),
    ("idx_scene_looks_scene", "scene_character_looks (scene_id)"),
    ("idx_scene_looks_look", "scene_character_looks (look_id)"),
    ("idx_wardrobe_items_look", "wardrobe_items (look_id)"),
]


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
    for name, target in _INDEXES:
        sql = f"CREATE INDEX IF NOT EXISTS {name} ON {target}"
        if USE_POSTGRES:
            conn.cursor().execute(sql)
        else:
            conn.execute(sql)
    conn.commit()


# P5: اسم المظهر اللي بيتعمل أوتوماتيك لكل شخصية - نفس الاسم اللي الاستيراد
# (importer.py) بيستعمله من الأول، عشان الشخصية المضافة باليد تبان زي المستوردة.
DEFAULT_LOOK_NAME = "المظهر الافتراضي"


def _backfill_default_looks(conn):
    """P5: كل شخصية لازم يبقى ليها مظهر أساسي واحد بالظبط.

    من غير مظهر الشخصية مبتظهرش في اختيار الشخصيات بتاع اللقطة خالص - ده
    كان البلاغ ("إضافة مظهر لشخصية مش شغالة كويس"): الشخصية المضافة باليد
    كانت بتتعمل من غير أي مظهر. الدالة دي بتتنده مع كل تشغيل، ومش بتعمل أي
    حاجة لو كل حاجة سليمة (idempotent):
    1) شخصية ملهاش ولا مظهر → بيتعملها المظهر الافتراضي وعليه is_default=1.
    2) شخصية ليها مظاهر بس ولا واحد أساسي → أقدم مظهر يبقى الأساسي.
    3) شخصية ليها أكتر من مظهر أساسي → أقدمهم بس يفضل أساسي.
    SQL عادي بيشتغل على SQLite وPostgres الاتنين زي ما هو.
    """
    statements = [
        ("INSERT INTO character_looks (character_id, look_name, apparent_age, makeup_state, "
         "hair_state, wardrobe_description, description, is_default) "
         "SELECT c.id, ?, '', '', '', '', '', 1 FROM characters c "
         "WHERE NOT EXISTS (SELECT 1 FROM character_looks l WHERE l.character_id = c.id)",
         (DEFAULT_LOOK_NAME,)),
        ("UPDATE character_looks SET is_default = 1 WHERE id IN ("
         "SELECT MIN(id) FROM character_looks GROUP BY character_id "
         "HAVING SUM(COALESCE(is_default, 0)) = 0)", ()),
        ("UPDATE character_looks SET is_default = 0 WHERE COALESCE(is_default, 0) <> 0 "
         "AND id NOT IN (SELECT MIN(id) FROM character_looks "
         "WHERE COALESCE(is_default, 0) <> 0 GROUP BY character_id)", ()),
    ]
    cur = conn.cursor()
    for sql, params in statements:
        cur.execute(_adapt_query(sql), params)
    conn.commit()


def _scope_all_projects(conn):
    """الفريق بقى على المشروع بس (المالك 2026-09-24): كل مشروع لسه "مفتوح لكل
    مساحة العمل" (members_scoped=0) بيتقفل على الناس اللي كانوا شايفينه -
    أعضاء مساحة العمل غير المديرين بيتسجلوا في فريقه - فمحدش بيخسر دخول.
    المديرين بيشوفوا كل حاجة أصلًا. idempotent."""
    cur = conn.cursor()
    cur.execute(_adapt_query(
        "INSERT OR IGNORE INTO project_members (project_id, user_id, added_by, added_at, permission) "
        "SELECT p.id, m.user_id, 'migration', ?, CASE WHEN m.role = 'viewer' THEN 'view' ELSE 'edit' END "
        "FROM projects p JOIN memberships m ON m.company_id = p.company_id AND m.active = 1 "
        "WHERE COALESCE(p.members_scoped, 0) = 0 AND m.role NOT IN ('admin', 'operator')"),
        (dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),))
    # مشروع لسه مالوش مساحة عمل (بيتربط بيها بعدين في accounts.migrate_accounts)
    # مايتقفلش دلوقتي - كان هيتقفل على فريق فاضي ويختفي من أصحابه
    cur.execute(_adapt_query("UPDATE projects SET members_scoped = 1 "
                             "WHERE COALESCE(members_scoped, 0) = 0 AND company_id IS NOT NULL"))
    conn.commit()


def _rename_project_types(conn):
    """"فيديو قصير" ← "فيديو" (المالك 2026-09-24). بيتنده مع كل تشغيل ومش
    بيعمل حاجة لو مفيش حاجة تتغيّر."""
    cur = conn.cursor()
    cur.execute(_adapt_query("UPDATE projects SET project_type = ? WHERE project_type = ?"),
                ("فيديو", "فيديو قصير"))
    conn.commit()


# ---------- نصوص شرح الحقول (نظام field_definitions المبسط) ----------
FIELD_HELP = {
    "project_type": "نوع المشروع: فيلم، مسلسل، إعلان، أو فيديو (ريلز، شورتس، يوتيوب...). ده بيأثر على القيم الافتراضية زي المدة والنسبة.",
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
    # P9 - خزانة المواهب
    "actor_category": "تصنيف الممثل/ة الأساسي: بطولة، أدوار مساعدة، كومبارس، أطفال.",
    "actor_measurements": "مقاسات قياسية بتستخدمها إدارة الأزياء والكاستينج وقت الترشيح: الطول والوزن ومحيط الصدر والخصر والورك ومقاس الحذاء.",
    "actor_skills": "مهارات بتفرق في اختيار الدور: قيادة عربية أو موتوسيكل، سباحة، تدخين.",
    "actor_sensitive_gate": "البيانات دي (المقاسات، التواصل، العادات) بتفضل مخفية عن أي فريق لحد ما يرشّح أو يتعاقد مع الممثل/ة لدور في مشروع عنده - أو لحد ما الممثل/ة نفسه يختار يبينها للكل.",
    "actor_discoverable": "لو متبوّت، البروفايل ميظهرش في بحث الكاستينج لأي فريق تاني - يفضل موجود بس مش قابل للاكتشاف.",
    "actor_photo_freshness": "الصورة لازم تتجدد كل 3 شهور تقريبًا عشان تفضل ممثلة الشكل الحالي للممثل/ة وقت الترشيح.",
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

# P9 "خزانة المواهب" -------------------------------------------------------
ACTOR_CATEGORY_OPTIONS = ["بطولة", "أدوار مساعدة", "كومبارس", "أطفال", "غير محدد"]

# حقول حساسة (production، القرار المحسوم 2026-09-23): مخفية عن أي شركة لحد ما
# ترشّح/تتعاقد مع الممثل/ة لدور في مشروع عندها (character_actor_casting)، إلا
# لو الممثل/ة نفسه ضايفها في actors.always_public_fields. اسم الحقل هنا لازم
# يبقى نفس اسم العمود بالظبط في جدول actors.
ACTOR_SENSITIVE_FIELDS = [
    "height_cm", "weight_kg", "chest_cm", "waist_cm", "hips_cm", "shoe_size_eu",
    "hair_color", "eye_color", "contact_phone", "contact_email", "agent_name",
    "agent_contact", "hobbies", "drives_car", "drives_motorcycle", "swims", "smokes",
    "skills_notes",
]

# حالات صف الكاستينج. "شورت-ليست" هو نفسه اللي بيفتح الحقول الحساسة (فوق)،
# "تم التعاقد" بعد ما يتأكد الدور فعليًا.
ACTOR_CASTING_STATUS_OPTIONS = ["shortlisted", "cast"]
ACTOR_CASTING_STATUS_LABELS = {
    "shortlisted": "مرشّح/ة",
    "cast": "متعاقد/ة",
}

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
