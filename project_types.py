"""أنواع المشاريع الأربعة وافتراضياتها الفنية — مصدر واحد للفورم في البرنامج
(views/new_project.py) وفورم الصفحة الرئيسية (board/app.py). من غير Streamlit
عشان الاتنين يقدروا يستوردوه."""

# "فيديو" كان اسمه "فيديو قصير" (المالك 2026-09-24: "كل دول تحت فيديو" -
# ريلز، شورتس، يوتيوب، أيًا كان). الاسم القديم متخزن في مشاريع موجودة،
# database._rename_project_types بيحوّله، وnormalize_type بيقبله لحد كده.
VIDEO = "فيديو"
TYPES = ["فيلم", "مسلسل", "إعلان", VIDEO]
SERIES = "مسلسل"
TYPE_ICONS = {"فيلم": "🎬", "مسلسل": "📺", "إعلان": "📢", VIDEO: "📱"}
LEGACY_TYPES = {"فيديو قصير": VIDEO}

PLATFORMS = ["ريلز", "تيك توك", "يوتيوب شورتس", "يوتيوب", "فيسبوك", "أخرى"]
VERTICAL_PLATFORMS = {"ريلز", "تيك توك", "يوتيوب شورتس"}


def technical_defaults(project_type, platform=None):
    """(الدقة، الاتجاه، النسبة) الافتراضية لكل نوع."""
    if normalize_type(project_type) == VIDEO and (platform is None or platform in VERTICAL_PLATFORMS):
        return "1080p", "رأسي", "9:16"
    if project_type in ("فيلم", "إعلان"):
        return "4K", "أفقي", "16:9"
    return "1080p", "أفقي", "16:9"


def normalize_type(project_type):
    """الاسم الحالي للنوع (بيحوّل الأسماء القديمة)."""
    return LEGACY_TYPES.get(project_type, project_type)
