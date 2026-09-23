"""نصوص الواجهة بالعربي والإنجليزي، وtr()/t() اللي بتختار بينهم.

اتنقلت من app.py كما هي."""

import streamlit as st


UI_TEXT = {
    "sidebar_projects": {"ar": "المشاريع", "en": "Projects"},
    "new_project": {"ar": "➕ إنشاء مشروع جديد", "en": "➕ New Project"},
    "select_project": {"ar": "اختر مشروع للعمل عليه", "en": "Select a project"},
    "current_project_label": {"ar": "📍 المشروع الحالي", "en": "📍 Current project"},
    "role_label": {"ar": "الدور", "en": "Role"},
    "language_label": {"ar": "🌐 اللغة", "en": "🌐 Language"},
    "edit_delete_project": {"ar": "✏️ تعديل / حذف المشروع الحالي", "en": "✏️ Edit / Delete Current Project"},
    "settings": {"ar": "⚙️ الإعدادات", "en": "⚙️ Settings"},
    "tab_import": {"ar": "📤 إضافة سيناريو", "en": "📤 Add Screenplay"},
    "tab_locations": {"ar": "📍 الأماكن", "en": "📍 Locations"},
    "tab_characters": {"ar": "🎭 الشخصيات", "en": "🎭 Characters"},
    "tab_actors": {"ar": "🎬 خزانة المواهب", "en": "🎬 Talent Vault"},
    "tab_props": {"ar": "🎒 الإكسسوارات", "en": "🎒 Props"},
    "tab_scenes": {"ar": "📝 المشاهد", "en": "📝 Scenes"},
    "tab_breakdown": {"ar": "🎥 اللقطات", "en": "🎥 Shots"},
    "tab_dashboard": {"ar": "📊 التقارير النهائية", "en": "📊 Final Reports"},
    "tab_settings": {"ar": "⚙️ إعدادات المشروع", "en": "⚙️ Project Settings"},
    "sub_import": {"ar": "استيراد السكريبت من ملف Word أو نصي أو JSON", "en": "Import script from Word, text, or JSON"},
    "sub_locations": {"ar": "مكتبة الأماكن", "en": "Locations Library"},
    "sub_characters": {"ar": "مكتبة الشخصيات", "en": "Characters Library"},
    "sub_actors": {"ar": "بحث الكاستينج عبر كل شركات المنصة", "en": "Casting search across every company on the platform"},
    "sub_props": {"ar": "مكتبة الإكسسوارات", "en": "Props Library"},
    "sub_scenes": {"ar": "المشاهد", "en": "Scenes"},
    "sub_breakdown": {"ar": "تفريغ اللقطات", "en": "Shot Breakdown"},
    "sub_dashboard": {"ar": "نظرة عامة على حالة كل اللقطات", "en": "Overview of all shots' status"},
    "stage_project": {"ar": "المشروع", "en": "Project"},
    "stage_locations_chars": {"ar": "الأماكن والشخصيات", "en": "Locations & Characters"},
    "stage_scenes": {"ar": "المشاهد", "en": "Scenes"},
    "stage_shots": {"ar": "تفريغ اللقطات", "en": "Shot Breakdown"},
    "stage_review": {"ar": "المراجعة والتأكيد", "en": "Review & Confirm"},
    "btn_save": {"ar": "💾 حفظ التعديل", "en": "💾 Save Changes"},
    "btn_export_excel": {"ar": "⬇️ تحميل Excel", "en": "⬇️ Download Excel"},
    "btn_export_word": {"ar": "⬇️ تحميل Word", "en": "⬇️ Download Word"},
    "btn_export_pdf": {"ar": "⬇️ تحميل PDF", "en": "⬇️ Download PDF"},
    "studio_tagline": {"ar": "استوديو الإنتاج بالذكاء الاصطناعي", "en": "AI Production Studio"},
    "sidebar_owner_label": {"ar": "بيستخدمه", "en": "Used by"},
    "logged_in_as": {"ar": "داخل باسم", "en": "Signed in as"},
    "logout": {"ar": "🚪 تسجيل الخروج", "en": "🚪 Log out"},
}


def tr(key):
    lang = st.session_state.get("ui_lang", "ar")
    entry = UI_TEXT.get(key)
    if not entry:
        return key
    return entry.get(lang, entry.get("ar", key))


TRANSLATIONS = {
    "الشركة": "Company",
    "الحساب": "Account",
    "خروج": "Log out",
    "دورك في المشروع ده": "Your role on this project",
    "إدارة الفريق مش متاحة في باقة Creator — شغال لوحدك. رقّي الاشتراك لـ Studio أو Enterprise عشان تضيف فريق.":
        "Team management isn't available on the Creator plan — you work solo. Upgrade to Studio or Enterprise to add a team.",
    "إدارة الفريق": "Manage team",
    "الفريق وحسابي": "Team & my account",
    "الرئيسية": "Home",
    "مدير الشركة": "Company Admin",
    "منتج": "Producer",
    "مدير إنتاج / مساعد مخرج أول": "Production Manager / 1st AD",
    "رئيس قسم": "Department Head",
    "مشاهدة فقط": "View only",
    "مشغّل المنصة": "Platform Operator",
    "الرابط ده لمشروع مش متاح لحسابك.": "That link is for a project your account cannot open.",
    "مشاهدة فقط — تقدر تتصفح وتصدّر، بس مش تعدّل.": "View only — you can browse and export, but not edit.",
    "مفيش مشاريع في الشركة دي لسه. مدير الشركة أو المنتج هو اللي بينشئ المشاريع.": "This company has no projects yet. The company admin or a producer creates projects.",
    "استيراد السكريبت وتحليله لأعضاء الفريق اللي عندهم صلاحية تعديل. حسابك مشاهدة فقط.": "Importing and analysing scripts is for team members who can edit. Your account is view only.",
    "حسابك مشاهدة فقط في الشركة دي — مينفعش تعدّل. كلّم مدير الشركة لو محتاج صلاحية تعديل.": "Your account is view only in this company — you can't edit. Ask the company admin if you need edit access.",
    "حسابك مشاهدة فقط — مينفعش تشغّل تحليل أو توليد صور.": "Your account is view only — you can't run analysis or generate images.",
    "إنشاء مشروع جديد لمدير الشركة أو المنتج أو مدير الإنتاج بس.": "Only the company admin, a producer or a production manager can create a project.",
    "حذف مشروع لمدير الشركة بس.": "Only the company admin can delete a project.",
    "إدارة الفريق لمدير الشركة بس.": "Only the company admin can manage the team.",
    "سجل النشاط": "Activity log",
    "سجل النشاط لمدير الشركة بس.": "Only the company admin can see the activity log.",
    "حسابك مش مربوط بأي شركة. كلّم مدير الشركة بتاعتك.": "Your account is not linked to any company. Contact your company admin.",
    "جدول التصوير": "Shooting schedule",
    "مفيش حاجة ناقصة — كل المشاهد ليها لقطات وشخصيات، وكل حاجة ليها صورة ومتراجعة.": "Nothing missing — every scene has shots and characters, and everything has an image and is reviewed.",
    "إيه اللي لسه ناقص": "What's still missing",
    "لقطات لسه متراجعتش": "Shots not reviewed yet",
    "شخصيات من غير صورة مرجعية": "Characters with no reference image",
    "أماكن من غير صورة مرجعية": "Locations with no reference image",
    "مشاهد من غير شخصيات": "Scenes with no characters",
    "مشاهد من غير لقطات": "Scenes with no shots",
    "اختار مشهد أو أكتر من الجدول (المربع جنب الصف) عشان تعدّلهم أو تمسحهم.": "Tick one or more scenes in the table to edit or delete them.",
    "مشاهد": "scenes",
    "اللقطات": "Shots",
    "الشخصيات": "Characters",
    "رقم": "No.",
    "إضافة مشهد جديد": "Add a scene",
    "إكسسوار": "props",
    "إضافة إكسسوار جديد": "Add a prop",
    "إضافة مظهر إضافي لشخصية": "Add a look to a character",
    "إضافة شخصية جديدة": "Add a character",
    "مفيش نتايج — جرّب كلمة تانية": "No matches — try another word",
    "إضافة مكان جديد": "Add a location",
    "دوّر في": "Search",
    "بحث": "Search",
    "كل اللقطات اتراجعت واتأكدت": "Every shot reviewed and confirmed",
    "مكان": "locations",
    "شخصية": "characters",
    "لسه مفيش مشاهد — ابدأ من «إضافة سيناريو»": "No scenes yet — start from “Add Screenplay”",
    "من": "of",
    "مشهد ليهم لقطات": "scenes have shots",
    "لقطة اتراجعت": "shots reviewed",
    "الخطوة": "Step",
    "اختار واحد أو أكتر": "Choose one or more",
    "الحلقات": "Episodes",
    # عام
    "غير محدد": "Not specified", "بدون تحديد": "None selected",
    "بدون - مكان رئيسي": "None - main location", "اختياري": "optional",
    "💾 حفظ": "💾 Save", "💾 حفظ التعديل": "💾 Save Changes",
    "نهار": "Day", "ليل": "Night", "غروب": "Sunset", "فجر": "Dawn",
    "فيلم": "Feature Film", "مسلسل": "Series", "إعلان": "Ad", "فيديو قصير": "Short Video",
    "أفقي": "Horizontal", "رأسي": "Vertical", "مربع": "Square",
    # المشروع (الشريط الجانبي)
    "اسم المشروع": "Project Name", "نوع المشروع": "Project Type",
    "الدقة الافتراضية": "Default Resolution", "الاتجاه الافتراضي": "Default Orientation",
    "نسبة الأبعاد الافتراضية": "Default Aspect Ratio", "إنشاء المشروع": "Create Project",
    "تم إنشاء المشروع": "Project created", "اكتب اسم المشروع أولًا": "Enter a project name first",
    "ابدأ بإنشاء مشروع جديد من القائمة الجانبية": "Start by creating a new project from the sidebar",
    "💾 حفظ تعديل المشروع": "💾 Save Project Changes",
    "تم تعديل بيانات المشروع": "Project data updated",
    "اسم المشروع مينفعش يبقى فاضي": "Project name can't be empty",
    "⚠️ حذف المشروع بيمسح كل الأماكن والشخصيات والمشاهد واللقطات بتاعته نهائيًا.":
        "⚠️ Deleting the project permanently deletes all its locations, characters, scenes and shots.",
    "متأكد إني عايز أمسح مشروع": "I'm sure I want to delete the project",
    "وكل بياناته": "and all its data",
    "🗑️ حذف المشروع نهائيًا": "🗑️ Delete Project Permanently",
    "تم حذف المشروع": "Project deleted",
    "اسمك ووظيفتك في المشروع ده (بتتحفظ مع المشروع نفسه).":
        "Your name and role in this project (saved with the project itself).",
    "اسم المستخدم": "User Name", "الوظيفة في المشروع": "Role in Project",
    "💾 حفظ الإعدادات": "💾 Save Settings", "تم حفظ الإعدادات": "Settings saved",
    "البرنامج ده بيساعدك تجهز وتنظم بيانات الإنتاج كلها (الأماكن، الشخصيات، المشاهد، تفريغ اللقطات) "
    "وتتأكد إنها متكاملة وجاهزة. مفيش مرحلة توليد فيديو فعلي بالذكاء الاصطناعي جوه البرنامج ده لسه — "
    "دي خطوة مستقبلية محتاجة تطوير إضافي لربطها بأدوات التوليد.":
        "This app helps you prepare and organize all your production data (locations, characters, scenes, "
        "shot breakdown) and make sure it's complete and ready. There's no actual AI video generation stage "
        "in this app yet — that's a future step that needs further development to connect it with generation tools.",
    # تبويب استيراد السكريبت
    "ارفع ملف السيناريو (.docx أو .txt)، والنظام هيحاول يتعرف على رقم كل مشهد، "
    "داخلي/خارجي، النهار/الليل، المكان، والحوار، ويملى تبويب (السكريبت) تلقائيًا. "
    "تقدر تراجع النتيجة وتعدل أو تضيف أي حاجة بعد كده. وفي حالة السكريبتات "
    "الصعبة، تقدر ترفع ملف JSON جاهز من أي AI (شوف التفاصيل تحت).":
        "Upload your screenplay (.docx or .txt), and the system will try to detect each scene's number, "
        "INT/EXT, day/night, location, and dialogue, and auto-fill the Script tab. You can review and edit "
        "or add anything afterwards. For tricky scripts, you can upload a ready-made JSON file from any AI "
        "(see details below).",
    "لأفضل نتيجة، اكتب كل مشهد في سطر بصيغة زي: "
    "\"مشهد 1 - داخلي - نهار - غرفة المعيشة\"، والحوار في سطر منفصل بصيغة "
    "\"اسم الشخصية: الكلام\".":
        "For best results, write each scene on a line like: "
        "\"Scene 1 - INT - Day - Living Room\", and dialogue on a separate line like "
        "\"Character Name: line\".",
    "🤖 التحليل خارج البرنامج — حلّل السكريبت على أي AI وارجع بالنتيجة":
        "🤖 Analysis outside the app — analyze the script on any AI and bring back the result",
    "لو السكريبت شكله معقد والتحليل اللي جوه البرنامج مش طالع كويس، حلّله بره "
    "على أي AI في أربع خطوات:":
        "If the script's format is complex and the built-in analysis isn't coming out well, "
        "analyze it outside on any AI in four steps:",
    "**1.** دوس «📋 نسخ البرومبت» تحت.\n\n"
    "**2.** افتح Claude أو ChatGPT أو Gemini، الصق البرومبت، وارفق معاه ملف "
    "السكريبت (أو الصق نصه كامل بعد البرومبت).\n\n"
    "**3.** احفظ الـ JSON اللي هيرجعلك في ملف اسمه `script.json`.\n\n"
    "**4.** ارفع `script.json` من زرار رفع الملف تحت — هيتقري ويتستورد زي أي سكريبت.":
        "**1.** Click \"📋 Copy Prompt\" below.\n\n"
        "**2.** Open Claude, ChatGPT or Gemini, paste the prompt, and attach your script file "
        "(or paste its full text after the prompt).\n\n"
        "**3.** Save the JSON it returns to a file named `script.json`.\n\n"
        "**4.** Upload `script.json` from the file uploader below — it is parsed and imported "
        "like any other script.",
    "📋 نسخ البرومبت": "📋 Copy Prompt",
    "✅ اتنسخ": "✅ Copied",
    "⬇️ أو نزّل البرومبت كملف": "⬇️ Or download the prompt as a file",
    "ده نص البرومبت كامل، لو حبيت تراجعه أو تنسخه يدويًا":
        "This is the full prompt text, if you want to review it or copy it manually",
    "اختر ملف السكريبت": "Choose script file", "🔍 تحليل الملف": "🔍 Analyze File",
    "🚫 استبعد المشهد ده من الاستيراد (مثلاً لو ده صفحة عنوان مش مشهد حقيقي)":
        "🚫 Exclude this scene from import (e.g. if it's a title page, not a real scene)",
    "الشخصيات المكتشفة — شيل أي حاجة مش اسم شخصية فعلي (زي نوع الفيلم أو التاريخ أو المكان)":
        "Detected characters — remove anything that isn't a real character name (like genre, date, or location)",
    "مفيش شخصيات اتكشفت في المشهد ده": "No characters detected in this scene",
    "مشهد": "Scene", "مكان غير محدد": "Location not specified",
    "🧑‍🤝‍🧑 لقينا أسماء شخصيات متشابهة — هي نفس الشخصية؟":
        "🧑‍🤝‍🧑 We found similar character names — are they the same character?",
    "الأسماء:": "Names:",
    "دمجهم في شخصية واحدة": "Merge into one character", "لأ، شخصيات مختلفة": "No, different characters",
    "اختار الاسم اللي هيتسجل بيه في المشروع": "Choose the name to register in the project",
    "🏠 لقينا أماكن متشابهة — هي حالات مختلفة لنفس المكان؟":
        "🏠 We found similar locations — are they different states of the same place?",
    "مثال: \"سطح اليخت\" و\"سطح اليخت بعد لحظات\" غالبًا نفس المكان في وقتين مختلفين، "
    "مش مكانين منفصلين. لو دمجتهم، الاسم الأصلي هيتسجل كحالة (Variant) تحت المكان الرئيسي.":
        "Example: \"Yacht Deck\" and \"Yacht Deck, moments later\" are usually the same place at two "
        "different times, not two separate locations. If you merge them, the original name will be "
        "registered as a Variant under the main location.",
    "الأماكن:": "Locations:",
    "دمجهم كحالات لنفس المكان الرئيسي": "Merge as variants of the same main location",
    "لأ، أماكن مختلفة فعلاً": "No, they're actually different locations",
    "اختار اسم المكان الرئيسي اللي هيتسجل بيه": "Choose the main location name to register",
    "🔵 تأكيد وإضافة كل المشاهد للمشروع": "🔵 Confirm and Add All Scenes to Project",
    "🗑️ إلغاء ومسح النتائج": "🗑️ Cancel and Clear Results",
    # الأماكن
    "لو عندك مكان رئيسي وجواه أماكن فرعية (زي شقة حسام وجواها غرفة نوم)، "
    "أضف المكان الرئيسي الأول، وبعدين أضف المكان الفرعي واختار له 'تابع لمكان رئيسي'.":
        "If you have a main location with sub-locations inside it (like an apartment with a bedroom "
        "inside), add the main location first, then add the sub-location and set its 'belongs to a main "
        "location' field.",
    "اسم المكان": "Location Name", "تابع لمكان رئيسي؟": "Belongs to a main location?",
    "وصف عام ثابت للمكان": "General Fixed Description",
    "رابط الموقع على الخريطة (اختياري)": "Map location link (optional)",
    "رابط الموقع على الخريطة": "Map location link",
    "الصق رابط Google Maps أو أي رابط خريطة تاني": "Paste a Google Maps link or any other map link",
    "📍 افتح على الخريطة": "📍 Open on map",
    "📍 الموقع الجغرافي": "📍 Geographic location",
    "عاوز تفتح الموقع الجغرافي ولا تعدله؟": "Do you want to open the location or edit it?",
    "🗺️ فتح": "🗺️ Open",
    "إضافة مكان": "Add Location",
    "اختر مكان لإضافة حالة (Variant) له": "Choose a location to add a Variant for",
    "📁 رفع من الجهاز": "📁 Upload from device",
    "📷 الكاميرا": "📷 Camera",
    "✨ توليد بالذكاء الاصطناعي": "✨ Generate with AI",
    "مصدر الصورة": "Image source",
    "اختر صورة": "Choose an image",
    "💾 حفظ الصورة": "💾 Save image",
    "صوّر المكان": "Photograph the location",
    "الصورة هتتولّد من اسم المكان ووصفه. ضيف أي تفاصيل تحب تشوفها فيها:": "The image is generated from the location's name and description. Add any details you want to see in it:",
    "تفاصيل إضافية (اختياري)": "Extra details (optional)",
    "✨ ولّد صورة": "✨ Generate image",
    "بنولّد الصورة... ده بياخد حوالي 10 ثواني": "Generating the image... this takes about 10 seconds",
    "🗑️ شيل الصورة": "🗑️ Remove image",
    "🖼️ صورة المكان": "🖼️ Location image",
    "الحالة هي شكل المكان نفسه في وقت معيّن من الأحداث (محروق، بعد التجديد، بعد سنين). داخلي/خارجي ونهار/ليل بيتحددوا في المشهد، مش هنا.": "A variant is how the location itself looks at a point in the story (burnt, renovated, years later). INT/EXT and Day/Night are set on the scene, not here.",
    "صورة مرجعية للحالة": "Variant reference image",
    "➕ إضافة حالة": "➕ Add Variant",
    "➕ حالة جديدة لـ": "➕ New variant for",
    "تقدر تضيف صورة للحالة بعد ما تتحفظ — رفع أو كاميرا أو توليد.": "You can add an image for the variant once it's saved — upload, camera, or generate.",
    "إلغاء": "Cancel",
    "اكتب اسم الحالة الأول": "Enter the variant name first",
    "اسم الحالة": "Variant Name", "داخلي/خارجي": "INT/EXT", "النهار/الليل": "Day/Night",
    "حالة الطقس": "Weather", "وصف التغييرات الخاصة بهذه الحالة": "Description of changes for this variant",
    "صورة مرجعية (اختياري)": "Reference image (optional)", "إضافة الحالة": "Add Variant",
    "مفيش أماكن مضافة لسه": "No locations added yet",
    "🗑️ حذف المكان (وكل حالاته)": "🗑️ Delete Location (and all its variants)",
    "تم تعديل المكان": "Location updated",
    "معرفش أمسح المكان ده لأنه مستخدم في مشهد، أو ليه أماكن فرعية تابعة له. شيل الارتباطات دي الأول.":
        "Can't delete this location because it's used in a scene, or has sub-locations. Remove those links first.",
    "تم حذف المكان": "Location deleted",
    "**الحالات (Variants):**": "**Variants:**",
    "لو نفس المكان بيتكرر في السكريبت بعد وقت (زي 'سطح اليخت' تاني بعد لحظات)، أضف حالة جديدة بدل ما تعمل مكان جديد مكرر.":
        "If the same location recurs later in the script (like 'Yacht Deck' again a bit later), add a new "
        "variant instead of creating a duplicate location.",
    "مفيش حالات مضافة لسه": "No variants added yet",
    "المكان (غيّره لو عايز تنقل الحالة دي لمكان تاني — مفيد لدمج أماكن مكررة)":
        "Location (change it to move this variant to another location — useful for merging duplicates)",
    "تغيير الصورة المرجعية": "Change reference image", "🗑️ حذف الحالة": "🗑️ Delete Variant",
    "تم تعديل الحالة": "Variant updated",
    "معرفش أمسح الحالة دي لأنها مستخدمة في مشهد أو أكتر. شيلها من المشاهد دي الأول من تبويب السكريبت.":
        "Can't delete this variant because it's used in one or more scenes. Remove it from those scenes first from the Script tab.",
    "تم حذف الحالة": "Variant deleted",
    # الشخصيات
    "اسم الشخصية": "Character Name", "نوع الدور": "Role Type",
    "بطل": "Hero", "شرير": "Villain", "مساعد": "Supporting", "كومبارس": "Extra",
    "نوع الكائن": "Species", "الجنس": "Gender",
    "إنسان": "Human", "حيوان": "Animal", "كائن خيالي": "Fantasy Creature",
    "ذكر": "Male", "أنثى": "Female",
    "ملاحظات عامة عن الشخصية": "General Character Notes",
    "زي الوزن والبنية الجسمانية (نحيف/تخين/رياضي...) وأي تفاصيل تانية":
        "Like weight and body type (thin/heavy/athletic...) and any other details",
    "صورة الشخصية المرجعية (اختياري)": "Character reference image (optional)",
    "إضافة شخصية": "Add Character",
    "اختر شخصية لإضافة مظهر إضافي لها": "Choose a character to add an extra look for",
    "المظهر الإضافي بيمثل شكل تاني للشخصية في لحظة مختلفة من القصة (مثال: حلق دقنه، لابس نضارة، اتصاب وبقى في جبس).":
        "An extra look represents a different appearance for the character at a different point in the "
        "story (e.g. shaved his beard, wearing glasses, injured and in a cast).",
    "اسم المظهر الإضافي": "Extra Look Name", "السن الظاهر": "Apparent Age",
    "حالة المكياج": "Makeup State",
    "طبيعي": "Natural", "كامل": "Full", "بدون": "None", "آثار إصابة": "Injury marks", "مكياج شيخوخة": "Aging makeup",
    "حالة الشعر": "Hair State", "وصف الملابس والإكسسوارات": "Wardrobe & Accessories Description",
    "وصف تفصيلي كامل للمظهر (يُستخدم كمرجع للتوليد)": "Full detailed look description (used as a generation reference)",
    "➕ إضافة مظهر إضافي": "➕ Add Extra Look",
    "مفيش شخصيات مضافة لسه": "No characters added yet",
    "🗑️ حذف الشخصية (وكل مظاهرها)": "🗑️ Delete Character (and all its looks)",
    "تم تعديل الشخصية": "Character updated",
    "اسم الشخصية مينفعش يبقى فاضي": "Character name can't be empty",
    "معرفش أمسح الشخصية دي لأن مظهر بتاعها مستخدم في لقطة أو أكتر. شيلها من اللقطات دي الأول من تبويب التفريغ.":
        "Can't delete this character because one of its looks is used in a shot. Remove it from those shots first from the Breakdown tab.",
    "تم حذف الشخصية": "Character deleted",
    "**المظاهر الإضافية:**": "**Extra Looks:**",
    "مفيش مظاهر إضافية متضافة لسه": "No extra looks added yet",
    "تغيير صورة الشخصية المرجعية": "Change character reference image",
    "🗑️ حذف المظهر الإضافي": "🗑️ Delete Extra Look",
    "تم تعديل المظهر الإضافي": "Extra look updated",
    "معرفش أمسح المظهر ده لأنه مستخدم في لقطة أو أكتر. شيله من اللقطات دي الأول من تبويب التفريغ.":
        "Can't delete this look because it's used in one or more shots. Remove it from those shots first from the Breakdown tab.",
    "تم حذف المظهر الإضافي": "Extra look deleted",
    # P5 المظاهر والراكور
    "المظهر الافتراضي": "Default look",
    "مظهر من غير اسم": "Unnamed look",
    "👤 المظهر الرئيسي": "👤 Main look",
    "مظاهر تانية": "Other looks",
    "⭐ خليه الأساسي": "⭐ Make it the main look",
    "لسه مفيش مظاهر تانية. ضيف مظهر لما الشخصية يتغير شكلها في القصة.":
        "No other looks yet. Add one when the character's appearance changes in the story.",
    "المظهر الرئيسي هو اللي بيتحط أوتوماتيك في أي مشهد أو لقطة، لحد ما تختار غيره هناك.":
        "The main look is used automatically in every scene and shot, until you pick a different one there.",
    "➕ إضافة مظهر جديد للشخصية دي": "➕ Add a new look for this character",
    "المظهر بيمثل شكل تاني للشخصية في لحظة مختلفة من القصة (مثال: حلق دقنه، لابس نضارة، اتصاب وبقى في جبس).":
        "A look is a different appearance of the character at a different point in the story (e.g. shaved his beard, wears glasses, injured and in a cast).",
    "اسم المظهر": "Look name",
    "مثال: بعد الحادثة - دراعه في جبس": "e.g. After the accident - arm in a cast",
    "➕ إضافة المظهر": "➕ Add look",
    "اكتب اسم للمظهر عشان تعرف تفرّقه عن الباقي": "Give the look a name so you can tell it apart from the others",
    "تم إضافة المظهر": "Look added",
    "تفاصيل كل مظهر (تعديل وصورة):": "Each look's details (edit and image):",
    "ده المظهر الوحيد للشخصية، ومينفعش تفضل من غير مظهر. ضيف مظهر تاني الأول لو عايز تمسحه، أو امسح الشخصية نفسها.":
        "This is the character's only look, and a character can't be left without one. Add another look first if you want to delete it, or delete the character itself.",
    # المشاهد
    "رقم المشهد": "Scene Number", "التوقيت": "Time of Day", "المكان": "Location", "الطقس": "Weather",
    "ملاحظات المشهد العامة": "General Scene Notes", "إضافة مشهد": "Add Scene",
    "🗑️ حذف المشهد (وكل لقطاته)": "🗑️ Delete Scene (and all its shots)",
    "حذف": "Delete", "مشهد مختار (وكل لقطاتهم)": "selected scene(s) (and all their shots)",
    "تم حذف المشاهد المختارة": "Selected scenes deleted",
    "تم تعديل المشهد": "Scene updated", "تم حذف المشهد": "Scene deleted",
    # التفريغ
    "لازم تضيف مشهد واحد على الأقل من تبويب السكريبت أولًا": "You need to add at least one scene from the Script tab first",
    "اختر المشهد": "Choose scene", "رقم اللقطة": "Shot Number", "حجم الكادر": "Shot Size",
    "حركة الكاميرا": "Camera Movement", "زاوية الكاميرا": "Camera Angle", "المدة (ثانية)": "Duration (seconds)",
    "قوة المشاعر": "Emotion Intensity", "وصف المشاعر": "Emotion Description",
    "الحوار (لو موجود)": "Dialogue (if any)", "ملاحظات النمط البصري / المرجع": "Visual Style Notes / Reference",
    "تضمين موسيقى في التوليد نفسه؟ (غير مستحسن)": "Include music in the generation itself? (not recommended)",
    "**الشخصيات الموجودة في اللقطة**": "**Characters in this shot**",
    "اختر مظهر كل شخصية ظاهرة": "Choose the look for each visible character",
    "🔵 تمت المراجعة والموافقة على كل بيانات اللقطة": "🔵 Reviewed and approved all shot data",
    "صورة ستوري بورد مرجعية (اختياري)": "Reference storyboard image (optional)",
    "حفظ اللقطة": "Save Shot", "تم حفظ اللقطة": "Shot saved",
    "🗑️ حذف اللقطة": "🗑️ Delete Shot", "تم تعديل اللقطة": "Shot updated", "تم حذف اللقطة": "Shot deleted",
    "تغيير صورة الستوري بورد المرجعية": "Change reference storyboard image",
    "لقطة": "Shot",
    # لوحة المتابعة
    "📄 تصدير تفريغ اللقطات": "📄 Export Shot Breakdown",
    "ملف تفريغ كامل قابل للطباعة، بفورمات سينمائي احترافي.":
        "A complete, printable breakdown file, in a professional cinema format.",
    "👉 الخطوة الجاية: روح تبويب **الأماكن** و**الشخصيات** وضيف الأماكن والشخصيات الأساسية في مشروعك.":
        "👉 Next step: go to the **Locations** and **Characters** tabs and add your project's core locations and characters.",
    "👉 الخطوة الجاية: روح تبويب **السكريبت (المشاهد)** وضيف مشاهد مشروعك (أو استوردها من ملف في تبويب استيراد السكريبت).":
        "👉 Next step: go to the **Script (Scenes)** tab and add your project's scenes (or import them from a file in the Import Script tab).",
    "👉 الخطوة الجاية: روح تبويب **التفريغ (اللقطات)** وابدأ تفرّغ كل مشهد للقطات كاميرا تفصيلية.":
        "👉 Next step: go to the **Breakdown (Shots)** tab and start breaking down each scene into detailed camera shots.",
    "لسه مفيش لقطات مضافة": "No shots added yet",
    "نسبة اللقطات الجاهزة للتوليد": "Shots ready for generation",
    "🎉 كل اللقطات اتراجعت وأتأكد منها. بيانات مشروعك دلوقتي متكاملة وجاهزة كمرجع كامل للإنتاج. "
    "البرنامج الحالي بيوقف هنا — التوليد الفعلي بالذكاء الاصطناعي مش متاح جوه البرنامج ده لسه، "
    "ومحتاج تطوير إضافي يربطه بأدوات التوليد.":
        "🎉 All shots have been reviewed and confirmed. Your project data is now complete and ready as a "
        "full production reference. The app stops here for now — actual AI generation isn't available in "
        "this app yet, and needs further development to connect it to generation tools.",
    "👉 راجع اللقطات اللي لسه مش متأكد منها (🟡) من تبويب التفريغ، وعلّم 'تمت المراجعة' لما تخلص كل واحدة.":
        "👉 Review the shots that aren't confirmed yet (🟡) from the Breakdown tab, and check 'Reviewed' once you finish each one.",
    "محتاجة مراجعة": "Needs review",
    # أجزاء نصوص ديناميكية (بتتلحق بأرقام أو قوائم وقت التشغيل)
    "حصل خطأ أثناء تحليل الملف:": "Error while analyzing the file:",
    # رسايل الفشل: المستخدم بيشوف كلام مفهوم، والخطأ الأصلي بيروح للوج
    "مشكلة في السيرفر مش في ملفك": "A server problem, not a problem with your file",
    "الملف وصل تمام بس مقدرناش نكمّل. جرّب تاني بعد شوية، ولو المشكلة فضلت ابعت الكود ده للدعم":
        "Your file arrived fine, but we could not finish. Try again shortly; "
        "if it keeps happening, send this code to support",
    "مقدرناش نكمّل التحليل. ملفك زي ما هو، تقدر تجرّب تاني.":
        "We could not finish the analysis. Your file is untouched — you can try again.",
    "تفاصيل تقنية": "Technical details",
    "تم التعرف على": "Detected",
    "مشهد في الملف. راجعهم وعدّل أي حاجة غلط قبل التأكيد:": "scene(s) in the file. Review them and fix anything wrong before confirming:",
    "هيتستبعد": "Will exclude",
    "مشهد من الاستيراد حسب اختيارك فوق.": "scene(s) from the import based on your selection above.",
    "تم إضافة": "Added",
    "مشهد جديد.": "new scene(s).",
    "شخصيات جديدة:": "New characters:",
    "أماكن جديدة:": "New locations:",
    "إكسسوارات جديدة:": "New props:",
    "أي حاجة بيمسكها أو بيستخدمها أي شخصية أو ليها دور في حدث المشهد (سكينة، تليفون، شنطة، سلاح...). "
    "تقدر تربط الإكسسوار بشخصية معينة (زي مسدس البطل)، وتعلّم عليه لو حساس للراكورد (يعني لازم يفضل في "
    "نفس الحالة بين اللقطات المتتالية).":
        "Anything a character holds or uses, or that plays a role in the scene's action (a knife, phone, "
        "bag, weapon...). You can link a prop to a specific character (like the hero's gun), and mark it "
        "as continuity-sensitive (meaning it must stay in the same state across consecutive shots).",
    "اسم الإكسسوار": "Prop Name",
    "مثال: سكينة عم جابر": "e.g. Am Gaber's knife",
    "حساس للراكورد؟ (لازم يفضل في نفس الحالة بين اللقطات)": "Continuity-sensitive? (must stay consistent across shots)",
    "مرتبط بشخصية (اختياري)": "Linked to a character (optional)",
    "إضافة إكسسوار": "Add Prop",
    "اسم الإكسسوار مينفعش يبقى فاضي": "Prop name can't be empty",
    "مفيش إكسسوارات مضافة لسه": "No props added yet",
    "مرتبط بـ": "Linked to",
    "🗑️ حذف الإكسسوار": "🗑️ Delete Prop",
    "تم تعديل الإكسسوار": "Prop updated",
    "تم حذف الإكسسوار": "Prop deleted",
    "بدون - غير مرتبط بشخصية": "None - not linked to a character",
    "لكل شخصية، حدد لو ليها حوار في اللقطة دي (سيبها فاضية لو الشخصية موجودة بس ساكتة)":
        "For each character, mark whether they have dialogue in this shot (leave unchecked if the character is present but silent)",
    "لها حوار في اللقطة دي؟": "Has dialogue in this shot?",
    "الإكسسوارات الموجودة في اللقطة": "Props in this shot",
    "اختر الإكسسوارات الظاهرة في اللقطة": "Choose the props visible in the shot",
    "✅ تم الحفظ": "✅ Saved",
    "الإعدادات": "Settings",
    "الشخصيات الموجودة في المشهد": "Characters in this scene",
    "الإكسسوارات الموجودة في المشهد": "Props in this scene",
    "الرقم ده كان مستخدم - تم نقل باقي المشاهد رقم واحد لقدام عشان تتزبط.":
        "That number was already in use — the rest of the scenes were shifted forward by one to make room.",
    "الرقم ده كان مستخدم - تم نقل باقي اللقطات رقم واحد لقدام عشان تتزبط.":
        "That number was already in use — the rest of the shots were shifted forward by one to make room.",
    "🔄 استخراج الشخصيات من نص المشاهد (لمشاريع قديمة)": "🔄 Extract Characters from Scene Text (for older projects)",
    "لو المشروع ده استوردته قبل ما ميزة ربط الشخصيات بالمشاهد تتضاف، التقارير (كشف الشخصيات، "
    "التفريغ العام) هتبقى فاضية لحد ما تربط كل مشهد بشخصياته يدويًا، أو تدوس هنا عشان نحاول نلاقي "
    "أسماء شخصيات مكتبتك داخل نص كل مشهد ونربطها أوتوماتيك (من غير ما نمسح أي ربط موجود بالفعل).":
        "If you imported this project before the scene-character linking feature was added, the reports "
        "(Characters Sheet, General Breakdown) will stay empty until you manually link each scene to its "
        "characters, or click here so we try to find your character library's names inside each scene's "
        "text and link them automatically (without removing any existing links).",

    "تم ربط": "Linked",
    "علاقة شخصية-مشهد جديدة.": "new character-scene link(s).",
    "دول سطور الحوار اللي لسه في حوار المشهد ومتحطوش في لقطة تانية - اختار بس اللي موجود في "
    "اللقطة دي (سيبها من غير اختيار لو اللقطة من غير حوار).":
        "These are the scene's dialogue lines not yet placed in another shot — pick only the ones "
        "that are in this shot (leave unselected if this shot has no dialogue).",
    "سطور الحوار المتاحة من حوار المشهد": "Available dialogue lines from the scene",
    "أو اكتب/عدّل الحوار يدويًا بدل الاختيار": "Or write/edit dialogue manually instead of selecting",
    "⚙️ الإعدادات": "⚙️ Settings",
    "تم تخطي مشاهد أرقام": "Skipped scene numbers",
    "لأنها موجودة بالفعل.": "because they already exist.",
    # أمثلة placeholder وعناوين من غير رموز/ماركداون حواليها
    "مثال: عروسة البحر": "e.g. The Sea Bride",
    "مثال: أحمد محمد": "e.g. Ahmed Mohamed",
    "مثال: شقة حسام": "e.g. Hossam's Apartment",
    "مثال: شقة قديمة في حي شعبي، جدرانها بيج فاتح، فيها أثاث خشبي تقيل":
        "e.g. An old apartment in a popular neighborhood, light beige walls, heavy wooden furniture",
    "مثال: أحمد": "e.g. Ahmed",
    "مثال: شتاء مشمس، أو صيف حار وضبابي": "e.g. Sunny winter, or hot hazy summer",
    "مثال: حزن مكتوم": "e.g. Suppressed sadness",
    "مثال: أحمد: إزيك يا سارة؟\nسارة: تمام والحمد لله.": "e.g. Ahmed: How are you, Sara?\nSara: I'm fine, thank God.",
    "مثال: إضاءة دافية، ألوان بيج وبني، حركة كاميرا هادئة": "e.g. Warm lighting, beige and brown tones, calm camera movement",
    "مثال: نهار - أول مرة، أو: بعد لحظات": "e.g. Day - first time, or: moments later",
    "مثال: المكان اتحرق واتهد بعد حريق في نص الأحداث": "e.g. The place burned down and collapsed after a fire mid-story",
    "اسم المكان مينفعش يبقى فاضي": "Location name can't be empty",
    "الحالات (Variants):": "Variants:",
    "مثال: المظهر الرئيسي - حلق دقنه ولابس نضارة": "e.g. Main look - shaved beard and wearing glasses",
    "مثال: 30 سنة": "e.g. 30 years old",
    "مثال: شعر قصير أسود": "e.g. Short black hair",
    "مثال: قميص أبيض وبنطلون جينز وساعة يد": "e.g. White shirt, jeans, and a wristwatch",
    "مثال: راجل في الثلاثينات، نحيف، شعره قصير أسود، لابس نضارة طبية...":
        "e.g. A man in his thirties, thin, short black hair, wearing prescription glasses...",
    "المظاهر الإضافية:": "Extra Looks:",
    "وصف تفصيلي كامل للمظهر": "Full Detailed Look Description",
    "الشخصيات الموجودة في اللقطة": "Characters in this shot",
    "حالة المكان": "Location Condition",
    "مثال: الشكل الرئيسي للمكان، أو: المكان محروق، أو: المكان بعد التجديد":
        "e.g. Main look of the location, or: place burned down, or: place after renovation",
    "وصف الحركة داخل اللقطة": "Action Description Within the Shot",
    "مثال: أحمد بيدخل الأوضة وبيقفل الباب وراه، سارة واقفة جنب الشباك بتبص برة":
        "e.g. Ahmed enters the room and closes the door behind him, Sara is standing by the window looking outside",
    "مثال: أحمد حزين، سارة غير مهتمة": "e.g. Ahmed is sad, Sara is indifferent",
    "مثال: أحمد (حزين): إزيك يا سارة؟\nسارة (غير مبالية): تمام والحمد لله.":
        "e.g. Ahmed (sad): How are you, Sara?\nSara (indifferent): I'm fine, thank God.",
    "📋 تقارير الإنتاج القياسية": "📋 Standard Production Reports",
    "نفس الأوراق القياسية اللي بيستخدمها مديرو الإنتاج (كشف الشخصيات، التفريغ العام، كشف أماكن "
    "التصوير)، متملية أوتوماتيك من بيانات مشروعك. الخانات اللي محتاجة قرار بشري (زي الترشيح، عدد "
    "أيام التصوير، عدد الصفحات) سايبينها فاضية عشان تملاها إنت وقت التحضير الفعلي للتصوير.":
        "The same standard sheets production managers use (Characters Sheet, General Breakdown, "
        "Filming Locations Sheet), auto-filled from your project data. Fields that need a human "
        "decision (like casting nomination, shooting days, page count) are left blank for you to "
        "fill in during actual production prep.",
    "⬇️ كشف الشخصيات": "⬇️ Characters Sheet",
    "⬇️ التفريغ العام": "⬇️ General Breakdown",
    "⬇️ كشف أماكن التصوير": "⬇️ Filming Locations Sheet",
    "⬇️ كشف الإكسسوار": "⬇️ Props Sheet",
    # خزانة المواهب (P9) - بحث الكاستينج وبروفايل الممثل/ة
    "غير متوفر": "Not available",
    "بطولة": "Lead", "أدوار مساعدة": "Supporting roles", "أطفال": "Children",
    "إضافة ممثل/ة جديد/ة": "Add a new actor",
    "الحقول اللي مالهاش مصدر عام موثوق (زي رقم التواصل أو المقاسات) سيبها فاضية - متخترعش قيم لها، خصوصًا لو الممثل/ة شخص حقيقي معروف.":
        "Leave fields with no legitimate public source (like contact number or measurements) empty — don't invent values for them, especially for a real, known actor.",
    "الاسم الحقيقي": "Real name",
    "التصنيف": "Category",
    "نبذة تعريفية (بيو)": "Bio",
    "الطول (سم)": "Height (cm)", "الوزن (كجم)": "Weight (kg)",
    "محيط الصدر (سم)": "Chest (cm)", "محيط الخصر (سم)": "Waist (cm)", "محيط الورك (سم)": "Hips (cm)",
    "مقاس الحذاء (أوروبي)": "Shoe size (EU)",
    "لون الشعر": "Hair colour", "لون العين": "Eye colour",
    "اسم الشهرة (اختياري)": "Stage name (optional)", "لو مختلف عن الاسم الحقيقي": "If different from the real name",
    "أعمال سابقة (سطر لكل عمل)": "Past work (one line per credit)",
    "مثال: فيلم كذا (2023) - دور كذا": "e.g. Film Name (2023) - role name",
    "رقم التواصل": "Contact number", "البريد الإلكتروني": "Email",
    "اسم الوكيل/ة (اختياري)": "Agent name (optional)", "اسم الوكيل/ة": "Agent name",
    "وسيلة تواصل الوكيل/ة": "Agent contact",
    "الهوايات": "Hobbies", "مهارات إضافية": "Additional skills",
    "مهارات الكاستينج": "Casting skills",
    "يقود عربية": "Drives a car", "يقود موتوسيكل": "Rides a motorcycle",
    "يعرف يعوم": "Can swim", "مدخّن/ة": "Smokes",
    "روابط": "Links", "رابط الشوريل": "Showreel link", "شوريل": "Showreel",
    "رابط إنستجرام أو سوشيال ميديا": "Instagram / social media link",
    "إنستجرام / سوشيال ميديا": "Instagram / social media",
    "روابط تانية (سطر لكل رابط)": "Other links (one per line)",
    "ظاهر في بحث الكاستينج؟": "Discoverable in casting search?",
    "صورة شخصية (لازم تتجدد كل 3 شهور تقريبًا)": "Headshot photo (should be refreshed roughly every 3 months)",
    "إضافة الممثل/ة": "Add actor",
    "اسم الممثل/ة مينفعش يبقى فاضي": "Actor name can't be empty",
    "تم إضافة الممثل/ة": "Actor added",
    "لسه مفيش ممثلين في خزانة المواهب": "No actors in the Talent Vault yet",
    "قفز بالحرف الأول": "Jump by first letter",
    "اكتب اسم الممثل أو أول حرف": "Type an actor's name or first letter",
    "ممثل متاح": "actors available",
    "مفيش نتايج — جرّب حرف تاني": "No matches — try another letter",
    "العودة لقايمة الممثلين": "Back to the actor list",
    "الملف الشخصي ده مش موجود": "This profile no longer exists",
    "بيانات تجريبية آمنة — مش شخص حقيقي": "Safe demo data — not a real person",
    "الصورة قديمة — محتاجة تحديث (أكتر من 3 شهور)": "Photo is stale — needs an update (over 3 months old)",
    "آخر تحديث للصورة": "Photo last updated",
    "أعمال سابقة": "Past work",
    "بيانات القياس والكاستينج": "Measurements & casting details",
    "البيانات دي بتفضل مخفية لحد ما شركتك ترشّح أو تتعاقد مع الممثل/ة ده لدور في أحد مشاريعك.":
        "These stay hidden until your company shortlists or casts this actor for a role in one of your projects.",
    "جزء من البيانات دي ظاهر لأن الممثل/ة اختار يبينه للكل — الباقي محتاج ترشيح أول.":
        "Some of this is visible because the actor chose to make it public — the rest needs a shortlist first.",
    "سم": "cm", "كجم": "kg",
    "تعيين لشخصية في هذا المشروع": "Cast for a character in this project",
    "كل شخصيات المشروع ده متعيّن لها ممثلين، أو لسه مفيش شخصيات في المشروع.":
        "Every character in this project already has an actor cast, or there are no characters yet.",
    "اختار شخصية": "Choose a character",
    "ملاحظة عن الدور (اختياري)": "Note about the role (optional)",
    "تعيين لهذا الدور": "Cast for this role",
    "تم تعيين الممثل/ة للشخصية": "Actor cast for the character",
    "الممثل/ة المتعاقد معاه/ا": "Actor cast",
    "لسه مفيش ممثل/ة متعيّن لهذا الدور. عيّنه من بروفايله في تبويب «خزانة المواهب».":
        "No actor assigned to this role yet. Cast one from their profile in the Talent Vault tab.",
    "مرشّح/ة": "Shortlisted", "متعاقد/ة": "Cast",
    "الطول": "Height", "الوزن": "Weight", "محيط الصدر": "Chest", "محيط الخصر": "Waist",
    "محيط الورك": "Hips", "مقاس الحذاء": "Shoe size",
    "نعم": "Yes", "لا": "No",
    "آخر تحديث للصورة من {n} شهور — محتاجة تحديث": "Photo last updated {n} months ago — needs an update",
    "المقاسات (لإدارة الأزياء)": "Measurements (for wardrobe)",
    "التواصل": "Contact", "الخصوصية": "Privacy",
    "بيانات تظهر للكل من غير ترشيح (اختياري)": "Details shown to everyone without a shortlist (optional)",
    "بروفايلات شركتك المخفية من البحث": "Your company's profiles hidden from search",
    "تجريبي": "demo",
    "الصورة محتاجة تحديث": "photo needs an update",
    "مفيش صورة لسه": "No photo yet",
    "تاريخ الصورة مش معروف — محتاجة تحديث": "Photo date unknown — needs an update",
    "مخفي من بحث الكاستينج": "Hidden from casting search",
    "مخفي لحد الترشيح": "hidden until shortlisted",
    "الترشيح والتعاقد في المشروع ده": "Shortlist and cast in this project",
    "لسه مفيش شخصيات في المشروع ده. ضيف شخصيات الأول من تبويب الشخصيات.":
        "This project has no characters yet. Add characters first from the Characters tab.",
    "الشخصية دي متعاقد لها": "This character is already cast with",
    "رشّح للدور ده": "Shortlist for this role",
    "تعاقد للدور ده": "Cast for this role",
    "تم ترشيح الممثل/ة للشخصية": "Actor shortlisted for the character",
    "معرفش أسجّل التعاقد ده.": "Couldn't record this casting.",
    "الشخصية دي متعاقد لها ممثل/ة تاني بالفعل. شيل التعاقد ده الأول لو عايز تغيّره.":
        "This character is already cast with another actor. Remove that casting first if you want to change it.",
    "الترشيح بيفتح لشركتك بيانات القياس والتواصل، ومتسجّل باسمك.":
        "Shortlisting unlocks measurements and contact details for your company, and is recorded under your name.",
    "تعديل البروفايل": "Edit profile",
    "حفظ التعديل": "Save changes",
    "تم حفظ التعديل": "Changes saved",
    "مرشّحين للدور ده": "shortlisted for this role",
    "الممثل/ة المرشّح/ة": "Shortlisted actor",
    # البروفايل العام (مشاركة على السوشيال ميديا)
    "البروفايل العام": "Public profile",
    "البروفايل مش منشور. لو نشرته، أي حد معاه اللينك يقدر يشوف الاسم والصورة والبيو والأعمال — من غير أي بيانات تواصل.":
        "This profile isn't shared. Once shared, anyone with the link can see the name, photo, bio and credits — never any contact details.",
    "انشر البروفايل العام": "Share public profile",
    "البروفايل منشور — أي حد معاه اللينك ده يقدر يشوفه من غير تسجيل دخول.":
        "The profile is public — anyone with this link can see it without signing in.",
    "لينك جديد": "New link",
    "اللينك الجديد بيلغي القديم فورًا.": "A new link cancels the old one at once.",
    "إيقاف المشاركة": "Stop sharing",
    "تم نشر البروفايل العام": "Public profile shared",
    "تم إيقاف المشاركة — اللينك القديم مابقاش شغال": "Sharing stopped — the old link no longer works",
    "مشاركة على": "Share on",
    "اللي بيظهر: الاسم المعروف، الصورة، البيو، الأعمال، التصنيف، الشوريل وإنستجرام — والطول/الشعر/العين/المهارات لو اخترتها في «بيانات تظهر للكل». عمره ما بيظهر: التليفون، الإيميل، الوكيل، مقاسات الجسم، الهوايات، التدخين، الروابط التانية، ولا أي ترشيحات.":
        "Shown: stage name, photo, bio, credits, category, showreel and Instagram — plus height/hair/eyes/skills if chosen under “Details shown to everyone”. Never shown: phone, email, agent, body measurements, hobbies, smoking, other links, or any shortlists.",
    "افتح الصفحة العامة": "Open the public page",
    "نبذة": "About", "مواصفات ومهارات": "Details & skills",
    "نسخ اللينك": "Copy link", "اتنسخ ✓": "Copied ✓",
    "بروفايل عام على CimaFast Studio — بيانات التواصل مش بتظهر هنا.":
        "Public profile on CimaFast Studio — contact details are never shown here.",
    "البروفايل ده مش متاح.": "This profile isn't available.",
    "بروفايل ممثل/ة على CimaFast Studio": "Actor profile on CimaFast Studio",
    # فيديوهات الأعمال السابقة
    "مثال: فيلم كذا (2023) - دور كذا https://youtu.be/...": "e.g. Film Name (2023) - role name https://youtu.be/...",
    "حط لينك فيديو (يوتيوب، فيميو، ديلي موشن، فيسبوك، أو ملف ‎.mp4‎) في نفس سطر العمل — الفيديو هيتعرض في البروفايل تحت العمل ده.":
        "Put a video link (YouTube, Vimeo, Dailymotion, Facebook, or an .mp4 file) on the same line as the credit — the video plays on the profile under that credit.",
    "اللينكات دي اتحفظت كنص بس ومش هتتعرض كفيديو (ولا هتظهر في البروفايل العام) — استخدم لينك يوتيوب أو فيميو أو ديلي موشن أو فيسبوك أو ملف ‎.mp4‎ مباشر:":
        "These links were saved as text only and won't play as videos (or appear on the public profile) — use a YouTube, Vimeo, Dailymotion or Facebook link, or a direct .mp4 file:",
    "لينك مش متعرف عليه كفيديو": "Not recognised as a video link",

    # P2 - توليد صور بمرجع (شخصيات + الأماكن)، مسموح 2026-09-23
    "البرومبت اتجمّع تلقائيًا من البيانات المحفوظة — عدّله زي ما تحب.":
        "The prompt is auto-filled from what's already saved — edit it as you like.",
    "الإضاءة": "Lighting",
    "إضاءة نهار داخلية": "Indoor, daylight",
    "إضاءة نهار خارجية": "Outdoor, daylight",
    "إضاءة ليل داخلية": "Indoor, night",
    "إضاءة ليل خارجية": "Outdoor, night",
    "🔄 إعادة التعبئة من البيانات المحفوظة": "🔄 Refill from saved data",
    "وصف الصورة المطلوبة": "Image description",
    "صورة مرجعية توجّه الشكل (اختياري)": "Reference image to guide the look (optional)",
    "صورة حقيقية للمكان (اختياري)": "Real photo of the location (optional)",
    "🖼️ صورة الشخصية المرجعية": "🖼️ Character reference photo",
    "صورة الممثل/ة الحقيقي (اختياري)": "Photo of the real actor (optional)",
    "صورة خلفية/مكان (اختياري)": "Background/location photo (optional)",
    "🖼️ صورة مرجعية للمظهر": "🖼️ Reference photo for this look",
}


def t(text):
    """يترجم نص عربي جاهز (مش مفتاح مجرد) للإنجليزي لو الواجهة إنجليزي دلوقتي،
    وبيرجعه زي ما هو لو مفيش ترجمة متسجلة أو لو اللغة عربي."""
    if st.session_state.get("ui_lang", "ar") != "en":
        return text
    return TRANSLATIONS.get(text, text)
