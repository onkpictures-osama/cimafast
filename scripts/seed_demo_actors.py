"""P9 خزانة المواهب - بيانات تجريبية آمنة (2026-09-23).

بيزرع 3 ممثلين وهميين بالكامل (أسامي مخترعة، مش أي شخص حقيقي) بكل الحقول
مليانة، عشان نقدر نعرض غنى الميزة كاملة من غير ما نلمس بيانات شخصية حقيقية.
القرار المحسوم في ACTOR-CASTING-PLAN.md (2026-09-23): الممثلين الحقيقيين
المشهورين (زي اللي المالك سمّاهم) بياخدوا بس اسم + بيو/فيلموجرافي من مصدر
عام موثوق فعلاً - مفيش حد من دول متضاف هنا، وده مقصود.

آمن يتشغّل أكتر من مرة: بيتفادى إضافة نفس الاسم تاني لو موجود بالفعل.

الاستخدام:
    STUDIO_DB_PATH=/var/lib/cimafast-v1/studio.db venv/bin/python scripts/seed_demo_actors.py
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
import repo
from ui import UPLOADS_DIR

database.init_db()


def _months_ago(n):
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30 * n)).isoformat(timespec="seconds")


def _make_avatar(path, initials, bg):
    """أفتار بسيط بلون + حروف أولى - مش صورة شخص حقيقي ولا صورة اتولّدت
    بذكاء اصطناعي بتقلّد حد، مجرد أيقونة بصرية عشان نعرض شكل الكارت والبروفايل."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (480, 480), bg)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 180)
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), initials, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((480 - w) / 2 - bbox[0], (480 - h) / 2 - bbox[1]), initials, fill="white", font=font)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, "PNG")


ALL_SENSITIVE = ",".join(database.ACTOR_SENSITIVE_FIELDS)

DEMO_ACTORS = [
    {
        "full_name": "ندى إبراهيم الفارس",
        "stage_name": "ندى الفارس",
        "category": "بطولة",
        "gender": "أنثى",
        "bio": "🧪 ممثلة تجريبية بالكامل لعرض خزانة المواهب - بيانات وهمية مش تخص أي شخص حقيقي. "
               "البروفايل ده مفتوح بالكامل (كل الحقول الحساسة ظاهرة) عشان يوضح شكل بروفايل ممثل "
               "اختار يبين بياناته للكل.",
        "credits_text": "مسلسل «ليالي القاهرة» (2023) - دور سلمى\n"
                         "فيلم «على الحافة» (2022) - البطولة النسائية\n"
                         "إعلان «بنك الأمل» (2024)",
        "height_cm": 165, "weight_kg": 54, "chest_cm": 84, "waist_cm": 62, "hips_cm": 90,
        "shoe_size_eu": 38, "hair_color": "أسود", "eye_color": "عسلي",
        "contact_phone": "000-0000-0001 (رقم وهمي)", "contact_email": "nada.demo@example.com",
        "agent_name": "مكتب النجوم للفنون (تجريبي)", "agent_contact": "agent.demo1@example.com",
        "hobbies": "الرسم، القراءة، ركوب الخيل",
        "drives_car": 1, "drives_motorcycle": 0, "swims": 1, "smokes": 0,
        "skills_notes": "لغة إشارة أساسية، رقص شرقي",
        "link_showreel": "https://example.com/demo/nada-reel",
        "link_instagram": "https://instagram.com/demo_nada",
        "link_other": "قناة يوتيوب تجريبية: https://example.com/demo/nada-yt",
        "discoverable": 1, "always_public_fields": ALL_SENSITIVE, "is_demo": 1,
        "avatar_bg": (196, 90, 60), "avatar_initials": "ند",
        "photo_age_months": 0,
    },
    {
        "full_name": "عمر خالد الدسوقي",
        "stage_name": "عمر الدسوقي",
        "category": "أدوار مساعدة",
        "gender": "ذكر",
        "bio": "🧪 ممثل تجريبي بالكامل لعرض خزانة المواهب - بيانات وهمية مش تخص أي شخص حقيقي. "
               "البروفايل ده مقفول بالكامل (زي أي ممثل حقيقي عادي) عشان يوضح شكل الحقول الحساسة "
               "قبل ما شركة ترشّحه لدور.",
        "credits_text": "مسلسل «صفقة العمر» (2021) - دور المحقق سامي\n"
                         "فيلم قصير «آخر قطار» (2020)",
        "height_cm": 180, "weight_kg": 78, "chest_cm": 100, "waist_cm": 84, "hips_cm": 98,
        "shoe_size_eu": 43, "hair_color": "بني غامق", "eye_color": "بني",
        "contact_phone": "000-0000-0002 (رقم وهمي)", "contact_email": "omar.demo@example.com",
        "agent_name": "استوديو الحلم للمواهب (تجريبي)", "agent_contact": "agent.demo2@example.com",
        "hobbies": "كرة القدم، التصوير الفوتوغرافي",
        "drives_car": 1, "drives_motorcycle": 1, "swims": 1, "smokes": 1,
        "skills_notes": "فروسية، فنون قتالية خفيفة",
        "link_showreel": "https://example.com/demo/omar-reel",
        "link_instagram": "https://instagram.com/demo_omar",
        "link_other": "",
        "discoverable": 1, "always_public_fields": "", "is_demo": 1,
        "avatar_bg": (46, 90, 130), "avatar_initials": "عم",
        "photo_age_months": 0,
    },
    {
        "full_name": "ريم عادل شوقي",
        "stage_name": "ريم شوقي",
        "category": "بطولة",
        "gender": "أنثى",
        "bio": "🧪 ممثلة تجريبية بالكامل لعرض خزانة المواهب - بيانات وهمية مش تخص أي شخص حقيقي. "
               "البروفايل ده نص مفتوح: الممثلة اختارت تبيّن مهاراتها وهواياتها للكل، وسايبة "
               "المقاسات وبيانات التواصل مقفولة لحد الترشيح. كمان صورتها هنا قديمة عمدًا عشان "
               "توضح شكل تنبيه «الصورة قديمة».",
        "credits_text": "مسلسل «بنت البلد» (2024) - الدور الرئيسي\n"
                         "فيلم «قبل الفجر» (2019) - دور مساعد",
        "height_cm": 160, "weight_kg": 52, "chest_cm": 82, "waist_cm": 60, "hips_cm": 88,
        "shoe_size_eu": 37, "hair_color": "بني فاتح", "eye_color": "أخضر",
        "contact_phone": "000-0000-0003 (رقم وهمي)", "contact_email": "reem.demo@example.com",
        "agent_name": "مكتب النجوم للفنون (تجريبي)", "agent_contact": "agent.demo3@example.com",
        "hobbies": "الغناء، اليوجا",
        "drives_car": 1, "drives_motorcycle": 0, "swims": 1, "smokes": 0,
        "skills_notes": "عزف بيانو، لهجات مصرية متعددة",
        "link_showreel": "https://example.com/demo/reem-reel",
        "link_instagram": "https://instagram.com/demo_reem",
        "link_other": "",
        "discoverable": 1,
        "always_public_fields": "hobbies,skills_notes,drives_car,drives_motorcycle,swims,smokes",
        "is_demo": 1,
        "avatar_bg": (120, 80, 150), "avatar_initials": "ري",
        "photo_age_months": 5,
    },
]


def main():
    existing = {a["full_name"] for a in repo.all_actors()}
    for spec in DEMO_ACTORS:
        if spec["full_name"] in existing:
            print(f"[seed] already exists, skipping: {spec['full_name']}")
            continue
        values = {k: v for k, v in spec.items() if k in repo._ACTOR_COLUMNS}
        # owner_company_id=None: بروفايل عرض من الإدارة - مشغّل المنصة بس يعدّله
        new_id = repo.add_actor(values, owner_company_id=None, created_by="seed_demo_actors", is_demo=1)
        rel_dir = os.path.join("actors", str(new_id))
        rel_path = os.path.join("uploads", rel_dir, "avatar.png")
        abs_path = os.path.join(UPLOADS_DIR, rel_dir, "avatar.png")
        _make_avatar(abs_path, spec["avatar_initials"], spec["avatar_bg"])
        photo_updated_at = _months_ago(spec["photo_age_months"]) if spec["photo_age_months"] else None
        repo.set_actor_photo(new_id, rel_path, updated_at=photo_updated_at)
        print(f"[seed] added actor #{new_id}: {spec['full_name']}")


if __name__ == "__main__":
    main()
