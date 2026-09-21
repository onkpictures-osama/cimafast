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

_DATA_URL = re.compile(r"^data:(image/[\w.+-]+);base64,(.+)$", re.S)


class ImageGenError(RuntimeError):
    """خطأ مفهوم لليوزر — الرسالة بتتعرض زي ما هي."""


def build_prompt(location_name, base_description="", state_name="", state_description="", extra=""):
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
    if extra:
        parts.append(f"Additional details requested by the user: {extra}.")
    parts.append(
        "Photorealistic, wide establishing framing, natural production lighting, "
        "no people, no text, no captions, no watermark. The descriptions may be in "
        "Egyptian Arabic; follow them faithfully."
    )
    return " ".join(parts)


def generate_image(prompt, api_key, model=None):
    """بترجع (bytes, امتداد الملف). بترمي ImageGenError برسالة عربي واضحة."""
    if not api_key:
        raise ImageGenError("توليد الصور مش متفعّل على السيرفر (مفيش مفتاح OpenRouter).")
    body = json.dumps({
        "model": model or os.environ.get("CIMAFAST_IMAGE_MODEL", DEFAULT_MODEL),
        "messages": [{"role": "user", "content": prompt}],
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
