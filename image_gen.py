"""توليد صورة مرجعية لمكان بالذكاء الاصطناعي عن طريق OpenRouter.

الملف ده ملهوش علاقة بـ Streamlit عشان يتختبر لوحده: app.py بيدّيله المفتاح
وبياخد منه bytes جاهزة يحفظها زي أي صورة اترفعت.

ليه OpenRouter: ده الحساب الوحيد على السيرفر اللي عنده موديلات بتطلّع صور.
الموديل قابل للتغيير من CIMAFAST_IMAGE_MODEL من غير ما نلمس الكود.
"""

import base64
import json
import os
import re
import urllib.error
import urllib.request

API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemini-3.1-flash-image"
TIMEOUT = 150

# اختيارات إضاءة سريعة للبرومبت - نفس فكرة SHOT_SIZE_OPTIONS بس للإضاءة.
# "غير محدد" أول عنصر يعني "متتضافش للبرومبت خالص" (زي شوت سايز برضه).
LIGHT_OPTIONS = [
    "غير محدد", "إضاءة نهار داخلية", "إضاءة نهار خارجية",
    "إضاءة ليل داخلية", "إضاءة ليل خارجية",
]

_DATA_URL = re.compile(r"^data:(image/[\w.+-]+);base64,(.+)$", re.S)


class ImageGenError(RuntimeError):
    """خطأ مفهوم لليوزر — الرسالة بتتعرض زي ما هي."""


def _clean(value):
    """يشيل "غير محدد" وأي قيمة فاضية - قيمة الافتراضي في قوائم الاختيار
    السريع (SHOT_SIZE_OPTIONS، LIGHT_OPTIONS) لما اليوزر ميختارش حاجة."""
    value = (value or "").strip()
    return "" if value == "غير محدد" else value


def build_prompt(location_name, base_description="", state_name="", state_description="",
                  shot_size="", light="", extra=""):
    """البرومبت بيطلب صورة ريفرنس للمكان نفسه: من غير ناس، ومن غير كتابة، لأن
    الصورة دي بتستخدم كمرجع للديكور والإضاءة مش كلقطة من الفيلم."""
    parts = [
        "Cinematic location reference photo for a film production design board.",
        f"Location: {location_name}.",
    ]
    if base_description:
        parts.append(f"General description: {base_description}.")
    if state_name:
        parts.append(f"Dramatic state of the location: {state_name}.")
    if state_description:
        parts.append(f"What is different in this state: {state_description}.")
    shot_size = _clean(shot_size)
    if shot_size:
        parts.append(f"Shot size: {shot_size}.")
    light = _clean(light)
    if light:
        parts.append(f"Lighting: {light}.")
    if extra:
        parts.append(f"Additional details requested by the user: {extra}.")
    parts.append(
        "Photorealistic, wide establishing framing, natural production lighting, "
        "no people, no text, no captions, no watermark. If a reference photo of the "
        "location or its background is attached, match its geometry, colours and "
        "materials faithfully instead of inventing a new place. The descriptions may "
        "be in Egyptian Arabic; follow them faithfully."
    )
    return " ".join(parts)


def build_character_prompt(name, role_type="", species="", gender="", personality_notes="",
                            look_name="", apparent_age="", makeup_state="", hair_state="",
                            wardrobe_description="", look_description="",
                            shot_size="", light="", extra=""):
    """برومبت بورتريه مرجعي لشخصية - نفس فلسفة build_prompt بس لشخص مش مكان:
    بيجمع بيانات الشخصية ولوكها (لو اتبعت) في فقرة واحدة، الاستخدام الأساسي هو
    character_looks اللي التحليل الذكي بيطلعها أصلًا (apparent_age، makeup_state،
    hair_state، wardrobe_description، description) عشان اليوزر ميكتبش من الأول."""
    parts = [
        "Cinematic character reference portrait for a film production design board.",
        f"Character: {name}.",
    ]
    if role_type and role_type != "غير محدد":
        parts.append(f"Role in the story: {role_type}.")
    if species and species not in ("إنسان", "غير محدد"):
        parts.append(f"Species: {species}.")
    if gender and gender != "غير محدد":
        parts.append(f"Gender: {gender}.")
    if personality_notes:
        parts.append(f"General notes (build, physique, personality): {personality_notes}.")
    if look_name:
        parts.append(f"Appearance version: {look_name}.")
    if apparent_age:
        parts.append(f"Apparent age: {apparent_age}.")
    if makeup_state:
        parts.append(f"Makeup: {makeup_state}.")
    if hair_state:
        parts.append(f"Hair: {hair_state}.")
    if wardrobe_description:
        parts.append(f"Wardrobe and accessories: {wardrobe_description}.")
    if look_description:
        parts.append(f"Full appearance description: {look_description}.")
    shot_size = _clean(shot_size)
    if shot_size:
        parts.append(f"Shot size: {shot_size}.")
    light = _clean(light)
    if light:
        parts.append(f"Lighting: {light}.")
    if extra:
        parts.append(f"Additional details requested by the user: {extra}.")
    parts.append(
        "Photorealistic, neutral on-set or studio background, natural lighting, no "
        "text, no captions, no watermark. If a reference actor photo is attached, keep "
        "that exact person's face and identity and only change wardrobe, makeup, hair "
        "and age as described above. If a separate background/location photo is "
        "attached, place the character in front of that background. The descriptions "
        "may be in Egyptian Arabic; follow them faithfully."
    )
    return " ".join(parts)


def generate_image(prompt, api_key, model=None, reference_images=None):
    """بترجع (bytes, امتداد الملف). بترمي ImageGenError برسالة عربي واضحة.

    reference_images: قائمة (bytes, mime_type) اختيارية - صورة ممثل/ة حقيقية
    و/أو صورة خلفية/مكان بتتبعت مع البرومبت كصور مش نص بس، عشان الصورة
    المتولدة تتقيّد بيهم (identity/خلفية) مش توصيف نصي بس. من غيرها السلوك
    زي الأول بالظبط (رسالة نصية عادية) - موديل gemini-3.1-flash-image بيعلن
    "image" كمدخل مدعوم على OpenRouter (نفس صيغة content parts القياسية
    بتاعة OpenAI Vision اللي بيستخدمها كل موديل بيقبل صور مدخل)."""
    import permissions
    permissions.require("run_ai")         # قبل ما نصرف على الـ API، مش بعد
    if not api_key:
        raise ImageGenError("توليد الصور مش متفعّل على السيرفر (مفيش مفتاح OpenRouter).")
    if reference_images:
        content = [{"type": "text", "text": prompt}]
        for data, mime in reference_images:
            b64 = base64.b64encode(data).decode("ascii")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime or 'image/png'};base64,{b64}"},
            })
    else:
        content = prompt
    body = json.dumps({
        "model": model or os.environ.get("CIMAFAST_IMAGE_MODEL", DEFAULT_MODEL),
        "messages": [{"role": "user", "content": content}],
        "modalities": ["image", "text"],
    }).encode("utf-8")
    req = urllib.request.Request(API_URL, data=body, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Title": "CimaFast Studio",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        if e.code == 402:
            raise ImageGenError("رصيد OpenRouter خلص — اشحن الحساب وجرب تاني.")
        raise ImageGenError(f"خدمة التوليد رجّعت خطأ {e.code}: {detail}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise ImageGenError(f"مقدرناش نوصل لخدمة التوليد: {e}")

    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        raise ImageGenError(f"رد غير متوقع من خدمة التوليد: {str(data)[:300]}")
    for img in message.get("images") or []:
        url = (img.get("image_url") or {}).get("url", "")
        m = _DATA_URL.match(url)
        if m:
            ext = "." + m.group(1).split("/")[1].replace("jpeg", "jpg")
            return base64.b64decode(m.group(2)), ext
    # الموديل ساعات بيرفض أو يرد بكلام بس — بنعرض كلامه بدل ما نقول "فشل"
    text = message.get("content") or ""
    raise ImageGenError("الموديل مرجّعش صورة" + (f": {text[:300]}" if text else "."))
