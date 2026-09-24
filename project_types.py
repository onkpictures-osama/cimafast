"""أنواع المشاريع الأربعة وافتراضياتها الفنية — مصدر واحد للفورم في البرنامج
(views/new_project.py) وفورم الصفحة الرئيسية (board/app.py). من غير Streamlit
عشان الاتنين يقدروا يستوردوه."""

TYPES = ["فيلم", "مسلسل", "إعلان", "فيديو قصير"]
SERIES = "مسلسل"
TYPE_ICONS = {"فيلم": "🎬", "مسلسل": "📺", "إعلان": "📢", "فيديو قصير": "📱"}

PLATFORMS = ["ريلز", "تيك توك", "يوتيوب شورتس", "يوتيوب"]
VERTICAL_PLATFORMS = {"ريلز", "تيك توك", "يوتيوب شورتس"}


def technical_defaults(project_type, platform=None):
    """(الدقة، الاتجاه، النسبة) الافتراضية لكل نوع."""
    if project_type == "فيديو قصير" and (platform is None or platform in VERTICAL_PLATFORMS):
        return "1080p", "رأسي", "9:16"
    if project_type in ("فيلم", "إعلان"):
        return "4K", "أفقي", "16:9"
    return "1080p", "أفقي", "16:9"
