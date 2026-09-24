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
    "tab_actors": {"ar": "🎬 الممثلين", "en": "🎬 Cast"},
    "tab_wardrobe": {"ar": "👗 الملابس", "en": "👗 Wardrobe"},
    "tab_schedule": {"ar": "🗓️ جدول التصوير", "en": "🗓️ Shooting schedule"},
    "tab_team": {"ar": "👥 فريق العمل", "en": "👥 Crew"},
    "phase_pre": {"ar": "🎬 ما قبل الإنتاج", "en": "🎬 Pre-production"},
    "phase_prod": {"ar": "🎥 الإنتاج", "en": "🎥 Production"},
    "tab_props": {"ar": "🎒 الإكسسوارات", "en": "🎒 Props"},
    "tab_scenes": {"ar": "📝 المشاهد", "en": "📝 Scenes"},
    "tab_breakdown": {"ar": "🎥 اللقطات", "en": "🎥 Shots"},
    "tab_dashboard": {"ar": "📊 التقارير النهائية", "en": "📊 Final Reports"},
    "tab_settings": {"ar": "⚙️ إعدادات المشروع", "en": "⚙️ Project Settings"},
    "sub_import": {"ar": "استيراد السكريبت من ملف Word أو نصي أو JSON", "en": "Import script from Word, text, or JSON"},
    "sub_locations": {"ar": "مكتبة الأماكن", "en": "Locations Library"},
    "sub_characters": {"ar": "مكتبة الشخصيات", "en": "Characters Library"},
    "sub_actors": {"ar": "بحث الكاستينج في المنصة كلها", "en": "Casting search across the whole platform"},
    "sub_wardrobe": {"ar": "غيارات كل شخصية، مين لابس أنهي غيار في كل مشهد، وقطع كل غيار وتجهيزها",
                     "en": "Each character's changes, who wears which change in every scene, and every piece and its readiness"},
    "sub_props": {"ar": "الإكسسوار — تابع للأماكن", "en": "Props — by location"},
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
    # --- مكتبة التحليلات (analysis_library.py / views/library.py) ---
    "مكتبة التحليلات": "Analysis Library",
    "📚 مكتبة التحليلات": "📚 Analysis Library",
    "كل سيناريو بيتحلل بالذكاء الاصطناعي بيتحفظ هنا لوحده، على حسابك وبره أي مشروع. لو استوردته في المشروع الغلط، استورده من هنا في المشروع الصح — أو ادمجه مع مشروع فيه بيانات، والشخصيات والأماكن المتشابهة بتتربط بالموجود بدل ما تتكرر.":
        "Every screenplay analysed with AI is saved here automatically, on your account and outside any project. If you imported it into the wrong project, import it from here into the right one — or merge it into a project that already has data, and similar characters and locations link to the existing ones instead of being duplicated.",
    "حصلت مشكلة عندنا مش في ملفك. جرّب تاني، ولو فضلت ابعت الكود ده للدعم":
        "Something went wrong on our side, not in your file. Try again, and if it persists send this code to support",
    "⬆️ ارفع ملف تحليل من CimaFast": "⬆️ Upload a CimaFast analysis file",
    "حسابك مشاهدة فقط — تقدر تتصفح وتنزّل التحليلات، بس مش تضيف.":
        "Your account is view-only — you can browse and download analyses, but not add them.",
    "ملف اتنزّل من مكتبة CimaFast (من حسابك أو من حساب تاني) — بيتضاف لمكتبتك في مساحة العمل دي.":
        "A file downloaded from a CimaFast library (yours or another account's) — it is added to your library in this workspace.",
    "اختار الملف": "Choose the file",
    "➕ ضيفه للمكتبة": "➕ Add to the library",
    "اتضاف للمكتبة.": "Added to the library.",
    "التحليل ده موجود في المكتبة بالفعل.": "This analysis is already in the library.",
    "مفيش مشروع تقدر تستورد فيه. محتاج دور تعديل في مشروع (مش مشاهدة فقط).":
        "There is no project you can import into. You need an editing role on a project (not view-only).",
    "المشروع اللي هيتستورد فيه": "Project to import into",
    "المشروع فيه بيانات بالفعل. تحب:": "The project already has data. Do you want to:",
    "🔗 دمج مع الموجود (الشخصيات والأماكن المتشابهة تتربط بالموجود)":
        "🔗 Merge with what's there (similar characters and locations link to the existing ones)",
    "🆕 بيانات جديدة (من غير مطابقة مع الموجود)": "🆕 New data (no matching against what's there)",
    "المشروع فاضي — التحليل هيتضاف زي ما هو.": "The project is empty — the analysis will be added as it is.",
    "مشاهد جديدة": "New scenes",
    "مشاهد أرقامها موجودة في المشروع وهتتخطى": "Scenes whose numbers already exist and will be skipped",
    "شخصيات جديدة": "New characters",
    "أماكن جديدة": "New locations",
    "موجودين بنفس الاسم وهيتربطوا بيهم": "Already there under the same name, will be linked",
    "هيتدمجوا مع الموجود — شيل علامة أي واحد مش هو هو:":
        "These will be merged with what's there — untick any that are not the same:",
    "هو نفسه": "is the same as",
    "حالة تانية من": "is another state of",
    "📥 استورد في المشروع ده": "📥 Import into this project",
    "اتدمج مع الموجود": "Merged with existing",
    "كل مشاهد التحليل ده موجودة في المشروع بالفعل — مفيش حاجة جديدة تتستورد.":
        "Every scene in this analysis is already in the project — nothing new to import.",
    "ملف مرفوع": "Uploaded file",
    "ذكاء اصطناعي": "AI",
    "اتحلل": "Analysed",
    "بواسطة": "by",
    "من مشروع": "from project",
    "📥 استورد في مشروع": "📥 Import into a project",
    "حسابك مشاهدة فقط — مينفعش تستورد في مشروع.": "Your account is view-only — you can't import into a project.",
    "⬇️ نزّل ملف": "⬇️ Download file",
    "🗑️ احذف": "🗑️ Delete",
    "متأكد إنك عايز تحذف التحليل ده من المكتبة؟ المشاريع اللي اتستورد فيها مش هتتأثر، بس الملف نفسه هيروح. نزّله الأول لو ممكن تحتاجه.":
        "Delete this analysis from the library? Projects it was imported into are not affected, but the analysis itself will be gone. Download it first if you might need it.",
    "أيوه، احذفه": "Yes, delete it",
    "اتحذف من المكتبة.": "Deleted from the library.",
    "لأ، سيبه": "No, keep it",
    "افتح المشروع": "Open the project",
    "🔍 دوّر باسم السيناريو أو المشروع أو اللي حلّله": "🔍 Search by screenplay, project or who analysed it",
    "مثال: الحلقة الاولى": "e.g. Episode one",
    "المكتبة فاضية لسه. أول ما تحلل سيناريو بالذكاء الاصطناعي في أي مشروع، التحليل هيتحفظ هنا لوحده.":
        "The library is empty so far. As soon as you analyse a screenplay with AI in any project, the analysis is saved here automatically.",
    "تحليل": "analyses",
    "مفيش تحليل بالاسم ده.": "No analysis matches that.",
    "التحليل ده اتحفظ في مكتبة التحليلات بتاعتك — لو ده مش المشروع الصح، استورده من هناك في أي مشروع تاني.":
        "This analysis is saved in your Analysis Library — if this is not the right project, import it from there into any other project.",
    "افتح المكتبة": "Open the library",
    # رسايل analysis_library.LibraryError الثابتة (اللي فيها أرقام بتتعرض بالعربي)
    "التحليل ده مش موجود أو مش متاح لحسابك.": "This analysis doesn't exist or isn't available to your account.",
    "بيانات التحليل ده بايظة ومش مقروءة.": "This analysis's data is damaged and can't be read.",
    "حذف التحليل لصاحبه أو لمدير المشروع بس.": "Only the analysis's owner or the project manager can delete it.",
    "الملف فاضي.": "The file is empty.",
    "الملف أكبر من المسموح (25 ميجا) — ده مش شكل ملف تحليل.": "The file is over the 25 MB limit — that is not an analysis file.",
    "الملف مش بترميز UTF-8 — ده مش ملف تحليل من CimaFast.": "The file isn't UTF-8 — it is not a CimaFast analysis file.",
    "الملف مش JSON سليم — ممكن يكون اتقطع أو اتعدّل بإيد.": "The file isn't valid JSON — it may be truncated or edited by hand.",
    "ده مش ملف تحليل من CimaFast (لازم يكون ‎.cimafast-analysis.json‎). لو ده JSON من AI تاني، ارفعه من تبويب «إضافة سيناريو» جوه المشروع.":
        "This is not a CimaFast analysis file (it must be .cimafast-analysis.json). If it is JSON from another AI, upload it from the Add Screenplay tab inside the project.",
    "رقم نسخة الملف مش مفهوم — الملف ممكن يكون اتعدّل.": "The file's version number isn't readable — the file may have been edited.",
    "بيانات السيناريو ناقصة في الملف (اسم السيناريو).": "The file is missing the screenplay details (its name).",
    "الملف مفيهوش تحليل (قايمة المشاهد ناقصة).": "The file has no analysis (the scene list is missing).",
    "الملف مفيهوش ولا مشهد.": "The file has no scenes.",
    "التحذيرات في الملف لازم تكون قايمة.": "The warnings in the file must be a list.",
    "بيانات التشغيل (meta) في الملف مش مكتوبة صح.": "The run details (meta) in the file are malformed.",
    "مقدرناش نقرا ولا مشهد من الملف.": "We couldn't read any scene from the file.",
    "التقارير في الملف مش مكتوبة صح.": "The reports in the file are malformed.",
    "حسابك مش عضو في مساحة العمل دي.": "Your account isn't a member of this workspace.",
    "المشروع ده مش متاح لحسابك.": "This project isn't available to your account.",
    "الشركة": "Company",
    "مساحة العمل": "Workspace",
    "الحساب": "Account",
    "خروج": "Log out",
    "دورك في المشروع ده": "Your role on this project",
    "إدارة الفريق مش متاحة في باقة Creator — شغال لوحدك. رقّي الاشتراك لـ Studio أو Enterprise عشان تضيف فريق.":
        "Team management isn't available on the Creator plan — you work solo. Upgrade to Studio or Enterprise to add a team.",
    "إدارة الفريق": "Manage team",
    "الفريق وحسابي": "Team & my account",
    "الرئيسية": "Home",
    "مدير المشروع": "Project Manager",
    "منتج": "Producer",
    "مدير إنتاج / مساعد مخرج أول": "Production Manager / 1st AD",
    "رئيس قسم": "Department Head",
    "مشاهدة فقط": "View only",
    "مشغّل المنصة": "Platform Operator",
    "الرابط ده لمشروع مش متاح لحسابك.": "That link is for a project your account cannot open.",
    "مشاهدة فقط — تقدر تتصفح وتصدّر، بس مش تعدّل.": "View only — you can browse and export, but not edit.",
    "مفيش مشاريع في مساحة العمل دي لسه. مدير المشروع أو المنتج هو اللي بينشئ المشاريع.": "This workspace has no projects yet. The project manager or a producer creates projects.",
    "استيراد السكريبت وتحليله لأعضاء الفريق اللي عندهم صلاحية تعديل. حسابك مشاهدة فقط.": "Importing and analysing scripts is for team members who can edit. Your account is view only.",
    "حسابك مشاهدة فقط في مساحة العمل دي — مينفعش تعدّل. كلّم مدير المشروع لو محتاج صلاحية تعديل.": "Your account is view only in this workspace — you can't edit. Ask the project manager if you need edit access.",
    "حسابك مشاهدة فقط — مينفعش تشغّل تحليل أو توليد صور.": "Your account is view only — you can't run analysis or generate images.",
    "إنشاء مشروع جديد لمدير المشروع أو المنتج أو مدير الإنتاج بس.": "Only the project manager, a producer or a production manager can create a project.",
    "حذف مشروع لمدير المشروع بس.": "Only the project manager can delete a project.",
    "إدارة الفريق لمدير المشروع بس.": "Only the project manager can manage the team.",
    "سجل النشاط": "Activity log",
    "سجل النشاط لمدير المشروع بس.": "Only the project manager can see the activity log.",
    "حسابك مش مربوط بأي مساحة عمل. كلّم مدير المشروع بتاعك.": "Your account is not linked to any workspace. Contact your project manager.",
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
    "فيلم": "Feature Film", "مسلسل": "Series", "إعلان": "Ad", "فيديو": "Video", "فيديو قصير": "Video",
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
    # مجاميع/كومبارس الخلفية
    "مجاميع": "Background extras", "مفيش مجاميع": "No extras", "فيه مجاميع؟": "Extras?",
    "مجاميع/كومبارس": "Background extras",
    "المشهد ده فيه ناس في الخلفية (مجاميع/كومبارس) - مش شخصية باسمها - ولا لأ؟":
        "Does this scene have people in the background (extras) - not a named character - or not?",
    "أيوه فيه": "Yes, there are", "لأ، مفيش": "No, there aren't",
    "العدد التقريبي": "Approximate headcount", "مثال: 10-15 أو حوالي 30": "e.g. 10-15 or about 30",
    "وصف ملابسهم": "What they're wearing",
    "مثال: يونيفورم عمال، جلاليب، بدل رسمية": "e.g. worker uniforms, galabeyas, formal suits",
    "بيعملوا إيه في المشهد": "What they're doing in the scene",
    "مثال: بيمشوا في الخلفية، بيهتفوا، بيشتغلوا": "e.g. walking in the background, chanting, working",
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
    "اسم الإكسسوار": "Prop Name",
    "مثال: سكينة عم جابر": "e.g. Am Gaber's knife",
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
    "البيانات دي بتفضل مخفية لحد ما فريقك يرشّح أو يتعاقد مع الممثل/ة ده لدور في أحد مشاريعك.":
        "These stay hidden until your team shortlists or casts this actor for a role in one of your projects.",
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
    "بروفايلات فريقك المخفية من البحث": "Your team's profiles hidden from search",
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
    "الترشيح بيفتح لفريقك بيانات القياس والتواصل، ومتسجّل باسمك.":
        "Shortlisting unlocks measurements and contact details for your team, and is recorded under your name.",
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
    # H4: التنبيهات
    "التغييرات اللي تخص قسمك": "Changes that concern your department",
    "مفيش تغييرات جديدة في مشاريعك آخر أسبوعين.": "No new changes in your projects in the last two weeks.",
    "بتعرض المشهد اللي اتغيّر بس.": "Showing only the scene that changed.",
    "اعرض كل المشاهد": "Show all scenes",
    "تنبيه جديد": "new notifications",

    # الممثل جوه السيستم: كاستينج من كارت الشخصية، رقم الكاست، التتبع
    "الممثل/ة والكاستينج": "Actor & casting",
    "البروفايل": "Profile",
    "افتح تبويب «الممثلين» تلاقي البروفايل مفتوح": "Open the Cast tab — the profile is waiting there",
    "تعاقد": "Cast",
    "رشّح": "Shortlist",
    "لسه مفيش ممثل/ة للدور ده — اختار من خزانة المواهب أو ضيف حد جديد تحت.":
        "No actor for this role yet — pick one from the Talent Vault or add someone new below.",
    "رقم الممثل في التفريغ": "Cast number",
    "0 = من غير رقم": "0 = no number",
    "معرفش أحفظ الرقم ده.": "Couldn't save that number.",
    "مشهد في السكريبت": "scenes in the script",
    "إعدادات المشروع: تعديل، حذف، الفريق، الحلقات": "Project settings: edit, delete, team, episodes",

    # المسلسل والحلقات (المرحلة الأولى 2026-09-24)
    "عدد الحلقات": "Number of episodes",
    "مثال: 30": "e.g. 30",
    "الحلقات من 1 للعدد ده بتتعمل مع المشروع، وتقدر تزودها بعدين من إعدادات المشروع.":
        "Episodes 1 to this number are created with the project; you can add more later in Project Settings.",
    "مدة الحلقة التقريبية (دقيقة)": "Approx. episode length (min)",
    "المدة التقريبية (دقيقة)": "Approx. runtime (min)",
    "البراند / العميل": "Brand / client",
    "مدة الإعلان": "Ad length",
    "15 ث": "15s", "30 ث": "30s", "45 ث": "45s", "60 ث": "60s",
    "المنصة": "Platform",
    "ريلز": "Reels", "تيك توك": "TikTok", "يوتيوب شورتس": "YouTube Shorts", "يوتيوب": "YouTube",
    "فيسبوك": "Facebook", "أخرى": "Other",
    "إعدادات فنية (الدقة، الاتجاه، النسبة)": "Technical settings (resolution, orientation, ratio)",
    "متظبطة لوحدها حسب نوع المشروع — افتحها بس لو عايز تغيّرها.":
        "Set automatically from the project type — open only to change them.",
    "اكتب عدد حلقات المسلسل": "Enter the number of episodes",
    "ارفع سكريبت أنهي حلقة؟": "Upload the script for which episode?",
    "حلقة ليها سكريبت": "episodes have a script",
    "الحلقة": "Episode",
    "فيها سكريبت": "has a script",
    "لسه": "not yet",
    "مشهد متسجل": "scenes saved",
    "لسه مالهاش سكريبت": "no script yet",
    "مشهد في المشروع من غير حلقة (اتضافوا قبل كده) — حدد حلقتهم من تبويب المشاهد.":
        "scenes in this project have no episode (added earlier) — set their episode in the Scenes tab.",
    "المسلسل ده لسه مالوش حلقات. حدد عدد الحلقات من ⚙️ إعدادات المشروع.":
        "This series has no episodes yet. Set the number of episodes in ⚙️ Project Settings.",
    "اختر ملف سكريبت الحلقة": "Choose the script file for episode",
    "توزيع المشاهد على الحلقات": "Scenes by episode",
    "الملف ده فيه": "This file contains",
    "حلقات": "episodes",
    "مشهد من غير رقم حلقة هيتحطوا في الحلقة": "scenes without an episode number will go to episode",
    "جوه الملف": "inside the file",
    "في اسم الملف": "in the file name",
    "انت اخترت الحلقة": "You chose episode",
    "بس": "but",
    "مكتوب الحلقة": "it says episode",
    "المشاهد دي تبع أنهي حلقة؟": "Which episode do these scenes belong to?",
    "اللي اخترتها": "your choice",
    "اللي في الملف": "from the file",
    "اختار الحلقة الصح عشان تقدر تكمّل.": "Pick the right episode to continue.",
    "فيها": "already has",
    "مشهد بالفعل": "scenes",
    "➕ ضيف الجديد بس (المكرر بيتخطى)": "➕ Add new scenes only (duplicates are skipped)",
    "♻️ استبدل مشاهد الحلقة كلها": "♻️ Replace all scenes in this episode",
    "الاستبدال بيمسح": "Replacing deletes",
    "مشهد من الحلقة": "scenes from episode",
    "بلقطاتهم وروابطهم وجدولتهم نهائيًا، وبعدين يستورد الملف الجديد.":
        "with their shots, links and scheduling, permanently — then imports the new file.",
    "متأكد — استبدل": "I'm sure — replace",
    "كل المشاهد": "All scenes",
    "هتتحط في الحلقة": "will go into episode",
    "كل الحلقات": "All episodes",
    "من غير حلقة": "No episode",
    "ح": "Ep",
    "بدون حلقة": "No episode",
    "تحديث العدد": "Update count",
    "اتضاف": "Added",
    "حلقة": "episodes",
    "كل الحلقات موجودة بالفعل": "All episodes already exist",
    "المسلسل ده لسه مالوش حلقات — حدد العدد فوق عشان تقدر ترفع سكريبت كل حلقة.":
        "This series has no episodes yet — set the count above to upload each episode's script.",
    "الحلقة دي موجودة بالفعل": "That episode already exists",

    # الإكسسوار تابع للأماكن + مراحل الشغل (2026-09-24)
    "المرحلة": "Phase",
    "الإكسسوار هو اللي بيجيبه الإكسسواريست: المرصوص في المكان (زي ساعة على الكومودينو) أو اللي بيتمسك في الإيد (زي مسدس). اللي بيتلبس (ساعة يد، عقد، برنيطة) بيتسجّل في الملابس.":
        "Props are what the props master brings: set dressing (a clock on the nightstand) or hand props (a gun). Anything worn (a wristwatch, necklace, hat) belongs to wardrobe.",
    "لإضافة قطعة: افتح المكان (أو الشخصية) واكتب في آخر صف فاضي في الجدول، وبعدين «حفظ».":
        "To add a prop: open the location (or character), type in the empty last row of the table, then Save.",
    "التكلفة": "Cost",
    "لسه مطلوب": "Still needed",
    "محتاج يتحدد مكانه": "Needs a place",
    "إكسسوار الأماكن": "Set props",
    "في إيد الشخصيات": "Hand props",
    "الإكسسوار": "Prop",
    "الكمية": "Qty",
    "الحالة": "Status",
    "مطلوب": "Needed", "اتجاب": "Acquired", "اترص في المكان": "Dressed on set",
    "من المكان نفسه": "From the location", "من المخزن": "From stock", "تصنيع": "Made",
    "تكلفة القطعة الواحدة — الإجمالي × الكمية": "Cost per piece — total × quantity",
    "عدد النسخ المطلوبة من نفس القطعة (زي أكتر من نسخة من خطاب هيتقطع في أكتر من تيك)":
        "Number of copies needed of the same piece (e.g. several copies of a letter that gets torn in multiple takes)",
    "أي تفاصيل تانية - زي عدد النسخ الاحتياطية أو حالة خاصة للقطعة":
        "Any other details - like backup copies or a special condition for the piece",
    "عدد المشاهد اللي القطعة متسجلة فيها": "Number of scenes this prop is recorded in",
    "لسه مفيش أماكن في المشروع. الإكسسوار بيترص في الأماكن — ضيف الأماكن من تبويب «الأماكن» أو استورد السيناريو.":
        "No locations yet. Props are dressed into locations — add locations in the Locations tab or import the script.",
    "كل مكان رئيسي وتحته ديكوراته — الإكسسوار بيتسجل على الديكور اللي بيترص فيه.":
        "Each main location with its sets underneath — props are recorded on the set they're dressed into.",
    "ديكور": "set",
    "حفظ إكسسوار": "Save props for",
    "اللي بيتمسك في الإيد ومش بيتلبس (مسدس، موبايل في الإيد، شنطة فلوس...) — بيجيبه الإكسسواريست.":
        "Held, not worn (a gun, a phone in hand, a cash bag…) — brought by the props master.",
    "القطع دي لسه مش متحددة: مرصوصة في مكان، ولا في إيد شخصية، ولا بتتلبس (تتنقل للملابس)؟ الاقتراحات متملية من المشاهد اللي ظهرت فيها ومن اسم القطعة — راجعها ودوس «تطبيق». مفيش حاجة بتتنقل من غير ما تدوس.":
        "These aren't sorted yet: dressed on a set, held by a character, or worn (moves to wardrobe)? Suggestions come from the scenes they appear in and their names — review and press Apply. Nothing moves until you do.",
    "مرصوص في": "Dressed in",
    "في إيد": "Held by",
    "بيتلبس ← الملابس": "Worn → wardrobe",
    "لبس مين": "Worn by",
    "الاقتراح": "Suggestion",
    "ظهر في": "In",
    "مشهد في المكان ده": "scenes at this location",
    "شكله بيتلبس": "looks worn",
    "الشخصية اللي هتلبسها — لازم تتحدد عشان تتنقل لغيارها": "The character who wears it — needed to move it to their change",
    "بيتعرض أول 200 من": "Showing the first 200 of",
    "طبّق وبعدين هتظهر الباقي.": "apply, then the rest will show.",
    "تطبيق": "Apply",
    "محتاجين «لبس مين»": "need «Worn by»",
    "مشاهد متجدولة": "Scheduled scenes",
    "أيام من غير تاريخ": "Days without a date",
    "لسه مفيش مشاهد في المشروع — الجدول بيتعمل من المشاهد. ارجع لمرحلة «ما قبل الإنتاج» وضيف المشاهد أو استورد السيناريو.":
        "No scenes yet — the schedule is built from scenes. Go back to Pre-production and add scenes or import the script.",
    "مشهد لسه مش في أي يوم تصوير.": "scenes aren't on any shoot day yet.",
    "افتح جدول التصوير": "Open the shooting schedule",
    "شاشة جدول التصوير مش متاحة في التشغيلة دي.": "The shooting schedule screen isn't available in this deployment.",
    "أيام الممثلين": "Actor days",
    "قريب هنا: الكول شيت، والتقارير اليومية، وباقي أقسام إدارة التصوير.":
        "Coming here: call sheets, daily reports and the rest of production management.",

    # فريق المشروع والدعوات (2026-09-24)
    "فريق العمل": "Crew",
    "في الفريق": "on the crew",
    "اللي أنشأ المشروع هو مدير المشروع.": "Whoever created the project is its manager.",
    "إضافة حد للفريق أو تغيير الأدوار من مدير المشروع.": "The project manager adds people and changes roles.",
    "فريق العمل متاح في باقة Studio أو Enterprise — رقّي الاشتراك عشان تضيف فريق للمشروع.":
        "Crews are available on Studio or Enterprise — upgrade to add a crew to the project.",
    "دعوات لسه ماتقبلتش": "Pending invitations",
    "لحد": "until",
    "الشغلانة في المشروع": "Job on this project",
    "الصلاحية": "Access",
    "يعدّل": "Can edit",
    "مشاهدة بس": "View only",
    "شيل من الفريق": "Remove from crew",
    "أضف حد لفريق العمل": "Add someone to the crew",
    "اسم الدخول لو عنده حساب — أو موبايله/إيميله": "Their username if they have an account — or phone/email",
    "اختار الشغلانة": "Pick the job",
    "لو كتبت اسم دخول حد عنده حساب بيتضاف على طول. غير كده بيتعمل لينك دعوة تبعته له (واتساب أو نسخ) — بيفتحه ويعمل حسابه ويلاقي المشروع.":
        "A username with an account is added right away. Otherwise you get an invite link to send (WhatsApp or copy) — they open it, create an account and find the project.",
    "أضف": "Add",
    "اختار الشغلانة في المشروع": "Pick their job on the project",
    "اتضاف للفريق": "Added to the crew",
    "اكتب اسمه أو رقمه عشان تعرف الدعوة دي لمين": "Enter their name or number so you know who the invite is for",
    "لينك الدعوة جاهز — ابعته للشخص ده. بيشتغل مرة واحدة ولمدة 7 أيام.":
        "The invite link is ready — send it to them. It works once, for 7 days.",
    "انت مدعو لفريق عمل مشروع": "You're invited to the crew of",
    "على CimaFast Studio": "on CimaFast Studio",
    "ابعته واتساب": "Send on WhatsApp",
    "انضميت لفريق العمل — المشروع اتفتح": "You joined the crew — the project is open",
    "لينك الدعوة ده مابقاش صالح — اطلب لينك جديد من مدير المشروع.": "This invite link is no longer valid — ask the project manager for a new one.",
    "لسه مفيش مشاريع. ابدأ بإنشاء مشروع جديد — أو افتح لينك الدعوة اللي وصلك من مدير مشروع.":
        "No projects yet. Create a new one — or open the invite link a project manager sent you.",
    "المنتج": "Producer", "مدير الإنتاج": "Production manager", "المخرج": "Director",
    "مساعد المخرج الأول": "1st AD", "كاتب السيناريو": "Screenwriter", "مدير التصوير": "DoP",
    "مهندس الديكور": "Production designer", "مصمم الملابس": "Costume designer", "الماكيير": "Make-up & hair",
    "مهندس الصوت": "Sound", "المونتير": "Editor", "مسؤول الكاستينج": "Casting", "مشرف الراكور": "Script supervisor",
    "مشرف المؤثرات البصرية": "VFX supervisor", "مدير المواقع": "Location manager", "الإكسسواريست": "Props master",

    # (أ) أعضاء لكل مشروع (2026-09-24)
    "أعضاء المشروع": "Project members",
    "المشروع ده مفتوح لكل أعضاء مساحة العمل (اتعمل قبل ميزة أعضاء المشروع). أول ما تحفظ اختيارك هنا، هيبقى للي تختارهم بس.":
        "This project is open to every workspace member (it predates project members). Once you save a selection here, only the people you pick will see it.",
    "اللي مش متعلّم عليه مش هيشوف المشروع ده خالص. مدير المشروع بيشوف كل المشاريع دايمًا.":
        "Anyone unticked won't see this project at all. The project manager always sees every project.",
    "مفيش أعضاء تانيين في مساحة العمل لسه. ضيفهم من «إدارة الفريق» وبعدين اختارهم هنا.":
        "No other workspace members yet. Add them from «Manage team», then pick them here.",
    "بيشوف كل المشاريع": "sees every project",
    "حفظ أعضاء المشروع": "Save project members",
    "اتشال": "Removed",
    "ضيف كل فريق مساحة العمل للمشروع": "Add the whole workspace team to the project",
    "من غيرها المشروع بيبدأ بيك انت بس، وتضيف الأعضاء من ⚙️ إعدادات المشروع.":
        "Without it the project starts with just you; add members from ⚙️ Project Settings.",
    "يوم تصوير": "shoot days",
    "يوم انتظار": "hold days",
    "من يوم": "from day",
    "لـ يوم": "to day",
    "مشهد لسه مش متجدول": "scenes not scheduled yet",
    "لسه ولا مشهد من مشاهده متجدول في جدول التصوير": "None of these scenes is on the shooting schedule yet",
    "أيام التصوير": "Shoot days",
    "يوم": "Day",
    "ممثل/ة جديد/ة مش في الخزانة": "New actor (not in the vault)",
    "اختار ممثل/ة": "Choose an actor",
    "اكتب أول الاسم...": "Type the start of a name...",
    "الاسم (لو جديد/ة)": "Name (if new)",
    "رقم التواصل (اختياري)": "Contact number (optional)",
    "الممثل/ة الجديد/ة بيتحفظ في خزانة المواهب كبروفايل خاص بفريقك (مش ظاهر لفرق تانية) — تقدر تكمّل بياناته من هناك.":
        "A new actor is saved to the Talent Vault as a profile private to your team (hidden from other teams) — complete it there.",
    "اختار ممثل/ة الأول": "Choose an actor first",
    "اكتب اسم الممثل/ة الجديد/ة": "Type the new actor's name",
    "مرشح": "shortlisted",
    "دور اتعاقد له ممثل/ة": "roles cast",
    "فيه ترشيحات بس": "shortlisted only",
    "ليهم رقم في التفريغ": "have a cast number",
    "رقّم الباقيين": "Number the rest",
    "بيدّي رقم لكل شخصية مالهاش، الأكتر مشاهد الأول. الأرقام الموجودة مش بتتغيّر.":
        "Gives every unnumbered character a cast number, most scenes first. Existing numbers never change.",
    "اترقّمت": "Numbered",
    "أرقام الكاست": "Cast #",
    "الشخصية دي متعاقد لها ممثل/ة تاني بالفعل. شيل التعاقد ده الأول لو عايز تغيّره.":
        "This character is already cast with another actor. Remove that casting first to change it.",
    "الرقم ده متحط لشخصية تانية في المشروع. اختار رقم تاني أو فضّي رقمها الأول.":
        "That number belongs to another character in this project. Pick another or clear theirs first.",
    # --- تقرير البناء الدرامي (dramaturgy.py) ---
    "🎭 اعمل تقرير البناء الدرامي": "🎭 Generate Dramatic-Structure Report",
    "تحليل تاني فوق نتيجة السيناريو: نقط القوة والضعف في البناء الدرامي حسب هرم فرايتاج، وكل حكم فيه بيترجع لأرقام مشاهد حقيقية.":
        "A second pass on top of the analysis: strengths and weaknesses in the dramatic structure per Freytag's pyramid, every claim tied to real scene numbers.",
    "بيحلل البناء الدرامي...": "Analysing dramatic structure…",
    "تقرير البناء الدرامي جاهز": "Dramatic-structure report ready",
    "مقدرناش نطلّع تقرير البناء الدرامي. جرّب تاني.": "Couldn't generate the dramatic-structure report. Try again.",
    "⬇️ تصدير تقرير البناء الدرامي": "⬇️ Export dramatic-structure report",
    "لسه مفيش تقرير بناء درامي لهذا التحليل": "No dramatic-structure report yet for this analysis",
    "🎭 عمل تقرير تاني": "🎭 Regenerate report",
    "🎭 تقرير البناء الدرامي": "🎭 Dramatic-Structure Report",
    "🎭 البناء الدرامي": "🎭 Dramatic structure",
    "تكلفة تقديرية": "Estimated cost",
    "بحد أقصى": "capped at",
    "في الطابور": "Queued",
    "مفيش مشاهد في التحليل ده، فمش هيتعمل تقرير بناء درامي.":
        "This analysis has no scenes, so no dramatic-structure report can be made.",
    "مقدرناش نعمل التقرير المرة دي. التحليل نفسه زي ما هو، جرّب تاني بعد شوية.":
        "We couldn't make the report this time. The analysis itself is untouched; try again shortly.",
    "التقرير وقف قبل ما يخلص لأنه وصل سقف المصروف (اتصرف ${spent:.2f}). التحليل نفسه زي ما هو.":
        "The report stopped partway because it hit the spending cap (spent ${spent:.2f}). The analysis itself is untouched.",
    "رد الذكاء الاصطناعي مش JSON سليم — التقرير ده مايتحفظش، جرّب تاني.":
        "The AI reply wasn't valid JSON, so this report wasn't saved. Try again.",
    "رد الذكاء الاصطناعي جاله شكل غير متوقع ومش قادرين نقرا التقرير منه.":
        "The AI reply came back in an unexpected shape and the report couldn't be read.",
    "مراحل هرم فرايتاج في التقرير فيها فجوة أو تداخل بين المشاهد.":
        "The report's Freytag stages leave a gap or overlap between scenes.",
    "مراحل هرم فرايتاج في التقرير ماغطتش كل مشاهد السكريبت.":
        "The report's Freytag stages don't cover every scene in the script.",
    "التقرير مفيهوش المراحل الخمسة لهرم فرايتاج بالظبط.":
        "The report doesn't have exactly the five Freytag stages.",
    "التقرير من غير حكم عام (verdict) على البناء الدرامي.":
        "The report has no overall verdict on the dramatic structure.",
    "منحنى التوتر فيه قيمة برّه المدى المسموح (0-100).":
        "The tension curve has a value outside the allowed range (0-100).",
    "تقرير البناء الدرامي مش متاح على النسخة دي.":
        "The dramatic-structure report isn't available on this version.",
}


def t(text):
    """يترجم نص عربي جاهز (مش مفتاح مجرد) للإنجليزي لو الواجهة إنجليزي دلوقتي،
    وبيرجعه زي ما هو لو مفيش ترجمة متسجلة أو لو اللغة عربي."""
    if st.session_state.get("ui_lang", "ar") != "en":
        return text
    return TRANSLATIONS.get(text, text)
