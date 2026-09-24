"""البروفايل العام للممثل (P9): صفحة من غير تسجيل دخول، بلينك سري الممثل
يشيره على السوشيال ميديا.

الموديول ده ملوش دعوة بـ Streamlit ولا Starlette: بياخد صف actors ويطلّع منه
dict فيه الحقول المسموحة بس (public_view)، وبيرسمه HTML (render_page/render_body). الواجهتين
(app.py بـ ‎?profile=‎ وboard/app.py بـ ‎/p/<token>‎) بيستخدموا نفس الدالتين، فمفيش
مكان تاني ممكن يسرّب عمود.

القاعدة: قايمة بيضا (whitelist) مش سودا. كل عمود في جدول actors متصنّف هنا
صراحةً في واحدة من التلات مجموعات تحت، والاختبار (tests/test_public_profile.py)
بيوقع لو اتضاف عمود جديد للجدول من غير ما حد يقرر مكانه — يعني عمود "تاريخ
ميلاد" أو "أجر" بكرة مايطلعش على النت لوحده.
"""

from __future__ import annotations

import html
import os
import re
import secrets
from urllib.parse import quote

import videos

# --- التصنيف: كل عمود في جدول actors لازم يبقى في مجموعة واحدة بالظبط -----------

# بيظهر دايمًا في الصفحة العامة: بورتفوليو عام بطبيعته.
# full_name بيظهر بس لو مفيش اسم شهرة (ساعتها هو نفسه الاسم المعروف) — لو فيه
# اسم شهرة، الاسم الحقيقي بيفضل خاص.
PUBLIC_FIELDS = frozenset({
    "full_name", "stage_name", "category", "gender", "bio",
    "credits_text",          # نص الأعمال + فيديوهاتها المتعرف عليها بس (videos.py) — أي لينك تاني بيتشال
    "photo_path",            # الصورة نفسها بس، بتتقدّم من سيرفرنا — المسار عمره ما بيتكتب في الصفحة
    "link_showreel", "link_instagram",
})

# بيظهر بس لو الممثل اختاره في always_public_fields ("بيانات تظهر للكل").
# دي حاجات كارت الكاستينج العادي فيه (طول، شعر، عين، مهارات) — مش مقاسات جسم.
OPT_IN_FIELDS = frozenset({
    "height_cm", "hair_color", "eye_color",
    "drives_car", "drives_motorcycle", "swims", "skills_notes",
})

# عمره ما بيظهر، حتى لو الممثل اختاره "ظاهر للكل" جوه المنصة: الاختيار ده
# معناه "ظاهر للشركات على المنصة"، مش "ظاهر لأي حد على النت".
PRIVATE_FIELDS = frozenset({
    "id",                                           # رقم داخلي — اللينك بالتوكن بس
    "contact_phone", "contact_email", "agent_name", "agent_contact",   # التواصل
    "weight_kg", "chest_cm", "waist_cm", "hips_cm", "shoe_size_eu",    # مقاسات الجسم
    "hobbies", "smokes",                            # عادات شخصية
    "link_other",                                   # نص حر — ممكن يكون واتساب أو رقم
    "photo_updated_at",                             # بيانات داخلية
    "discoverable", "always_public_fields", "is_demo",
    "owner_company_id", "created_by",               # الشركة اللي ضافته — بيانات داخلية
    "created_at", "updated_at",
    "public_share_token", "public_share_at",        # التوكن نفسه ماينطبعش غير في اللينك
})
# ومش عمود في الجدول بس برضو خاص: صفوف الكاستينج (character_actor_casting) —
# ترشيحات وتعاقدات مشاريع شركات تانية. public_view مابتقراهاش أصلًا.

_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{20,64}$")

PROVIDER_LABEL = "🎬"   # عمل من غير عنوان، فيديو بس

_IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}

_ROOT = os.path.dirname(os.path.abspath(__file__))


def new_token():
    """توكن عشوائي 128 بت — مستحيل يتخمّن، ومش مشتق من رقم الممثل."""
    return secrets.token_urlsafe(16)


def valid_token(token):
    """شكل التوكن بس (قبل ما نسأل قاعدة البيانات أصلًا)."""
    return isinstance(token, str) and bool(_TOKEN_RE.match(token))


def _opted_in(actor):
    chosen = {f.strip() for f in (actor.get("always_public_fields") or "").split(",") if f.strip()}
    return chosen & OPT_IN_FIELDS


def _safe_url(url):
    """روابط http/https بس — ‎javascript:‎ وأخواتها مايدخلوش href أبدًا."""
    url = (url or "").strip()
    return url if re.match(r"^https?://[^\s<>\"']+$", url, re.IGNORECASE) else None


def _blank(v):
    return v is None or (isinstance(v, str) and not v.strip())


def public_view(actor):
    """الـ dict الوحيد اللي الصفحة العامة بتشوفه. كل مفتاح هنا جاي من
    PUBLIC_FIELDS أو من OPT_IN_FIELDS اللي الممثل اختارها — ولا حاجة تانية."""
    if not actor:
        return None
    stage = (actor.get("stage_name") or "").strip()
    view = {
        "name": stage or (actor.get("full_name") or "").strip(),
        "category": actor.get("category") if actor.get("category") not in (None, "", "غير محدد") else None,
        "gender": actor.get("gender") if actor.get("gender") not in (None, "", "غير محدد") else None,
        "bio": (actor.get("bio") or "").strip() or None,
        # فيديوهات الأعمال بورتفوليو عام. اللينكات اللي مش فيديو متعرف عليه
        # بتتشال من النص خالص — ممكن تكون wa.me أو لينك شخصي.
        "credits": [{"text": c["text"], "videos": c["videos"]}
                    for c in videos.credits(actor.get("credits_text")) if c["text"] or c["videos"]],
        "has_photo": bool(photo_file(actor)),
        "links": [(label, u) for label, u in (("شوريل", _safe_url(actor.get("link_showreel"))),
                                               ("إنستجرام / سوشيال ميديا", _safe_url(actor.get("link_instagram"))))
                  if u],
        "details": [],
    }
    chosen = _opted_in(actor)
    for key in ("height_cm", "hair_color", "eye_color"):
        if key in chosen and not _blank(actor.get(key)):
            view["details"].append((key, actor[key]))
    view["skills"] = [key for key in ("drives_car", "drives_motorcycle", "swims")
                      if key in chosen and actor.get(key)]
    notes = (actor.get("skills_notes") or "").strip() if "skills_notes" in chosen else ""
    view["skills_notes"] = notes or None
    return view


def photo_file(actor):
    """المسار المطلق لصورة الممثل ده بس، أو None.

    المسار جاي من قاعدة البيانات (مش من الطلب)، وبرضو بنتأكد إنه جوه
    ‎uploads/actors/<id>/‎ بتاع نفس الممثل بعد realpath — فلا symlink ولا ‎../‎
    يقدروا يطلّعوا ملف تاني، ولا صورة ممثل تاني."""
    rel = (actor or {}).get("photo_path")
    if not rel or actor.get("id") is None:
        return None
    allowed = os.path.realpath(os.path.join(_ROOT, "uploads", "actors", str(int(actor["id"]))))
    path = os.path.realpath(os.path.join(_ROOT, rel))
    if not path.startswith(allowed + os.sep):
        return None
    if os.path.splitext(path)[1].lower() not in _IMAGE_TYPES or not os.path.isfile(path):
        return None
    return path


def photo_media_type(path):
    return _IMAGE_TYPES.get(os.path.splitext(path)[1].lower(), "application/octet-stream")


# --- المشاركة ------------------------------------------------------------------

def share_links(url, text):
    """روابط مشاركة عادية (مفيش SDK ولا سكريبت من برّه): اسم الخدمة والرابط."""
    u, tx = quote(url, safe=""), quote(text, safe="")
    return [
        ("WhatsApp", f"https://wa.me/?text={quote(text + ' ' + url, safe='')}"),
        ("Facebook", f"https://www.facebook.com/sharer/sharer.php?u={u}"),
        ("X", f"https://twitter.com/intent/tweet?url={u}&text={tx}"),
        ("LinkedIn", f"https://www.linkedin.com/sharing/share-offsite/?url={u}"),
        ("Telegram", f"https://t.me/share/url?url={u}&text={tx}"),
    ]


# --- الرسم ---------------------------------------------------------------------

_LABELS = {"height_cm": "الطول", "hair_color": "لون الشعر", "eye_color": "لون العين",
           "drives_car": "يقود عربية", "drives_motorcycle": "يقود موتوسيكل", "swims": "يعرف يعوم"}


def _tr(text, lang):
    if lang != "en":
        return text
    import i18n  # متأخر: i18n بيستورد streamlit، ومش لازم لو الصفحة عربي
    return i18n.TRANSLATIONS.get(text, text)


def _e(v):
    return html.escape(str(v), quote=True)


def description(view, lang="ar"):
    """سطر الوصف لمعاينة اللينك (og:description): التصنيف + أول البيو."""
    bits = [_tr(v, lang) for v in (view.get("category"),) if v]
    if view.get("bio"):
        bio = view["bio"].replace("\n", " ")
        bits.append(bio[:180] + ("…" if len(bio) > 180 else ""))
    return " — ".join(bits) or _tr("بروفايل ممثل على CimaFast Studio", lang)


CSS = """
.cf-pp{--y:#FECA05;--ink:#1B254B;--navy:#212F70;--mid:#0F1B45;--card:#1A2860;--mist:#B8BFD9;
 max-width:760px;margin:0 auto;padding:28px 18px 40px;color:#fff;
 font-family:"Cairo","Inter",system-ui,sans-serif;line-height:1.7}
.cf-pp *{box-sizing:border-box}
.cf-pp__card{background:var(--card);border-radius:18px;padding:22px;box-shadow:0 10px 30px rgba(0,0,0,.25)}
.cf-pp__head{display:flex;gap:20px;align-items:center;flex-wrap:wrap}
.cf-pp__photo{width:170px;height:212px;object-fit:cover;border-radius:14px;border:3px solid var(--y);background:var(--mid)}
.cf-pp__nophoto{width:170px;height:212px;border-radius:14px;border:3px dashed var(--mist);display:flex;
 align-items:center;justify-content:center;font-size:56px}
.cf-pp h1{margin:0 0 4px;font-size:30px;line-height:1.25;color:#fff}
.cf-pp__meta{color:var(--mist);font-size:15px}
.cf-pp h2{font-size:17px;color:var(--y);margin:22px 0 6px}
.cf-pp ul{margin:0;padding-inline-start:20px}
.cf-pp p{margin:0;white-space:pre-line}
.cf-pp a{color:#6FA8E0}
.cf-pp__chips{display:flex;flex-wrap:wrap;gap:8px;list-style:none;padding:0 !important}
.cf-pp__chips li{background:var(--mid);border-radius:999px;padding:4px 12px;font-size:14px}
.cf-pp__share{display:flex;flex-wrap:wrap;gap:8px;margin-top:22px}
.cf-pp__share a,.cf-pp__share button{background:var(--y);color:var(--ink);border:0;border-radius:10px;
 padding:8px 14px;font:600 14px "Cairo","Inter",system-ui,sans-serif;text-decoration:none;cursor:pointer}
.cf-pp__video{display:block;width:100%;aspect-ratio:16/9;border:0;border-radius:12px;margin:8px 0 14px;background:#000}
.cf-pp__foot{text-align:center;color:var(--mist);font-size:13px;margin-top:22px}
.cf-pp__foot a{color:var(--mist)}
"""


def video_html(v, title=""):
    """المشغّل من dict بتاع videos.parse — الرابط اتبنى من رقم الفيديو بس."""
    if v["kind"] == "video":
        return (f'<video class="cf-pp__video" src="{_e(v["embed_url"])}" controls preload="none" '
                'playsinline></video>')
    # referrerpolicy هنا مش no-referrer: يوتيوب بيرفض التضمين من غير origin (Error 153)
    return (f'<iframe class="cf-pp__video" src="{_e(v["embed_url"])}" title="{_e(title)}" loading="lazy" '
            'allow="encrypted-media; picture-in-picture; fullscreen" allowfullscreen '
            'referrerpolicy="strict-origin-when-cross-origin"></iframe>')


def render_body(view, lang="ar", photo_url=None, share_url=None, lang_switch_url=None, copy_button=True,
                embed_videos=True):
    """embed_videos=False لـ Streamlit: st.html بيشيل iframe، فالشاشة هناك
    بترسم الفيديوهات بنفسها تحت الجسم."""
    """جسم الصفحة (من غير <html>) — Streamlit بيحطه بـ st.html، وStarlette
    بيلفه بـ render_page. كل قيمة بتعدّي على html.escape."""
    d = "rtl" if lang != "en" else "ltr"
    out = [f'<div class="cf-pp" dir="{d}" lang="{"en" if lang == "en" else "ar"}"><div class="cf-pp__card">',
           '<div class="cf-pp__head">']
    if view["has_photo"] and photo_url:
        out.append(f'<img class="cf-pp__photo" src="{_e(photo_url)}" alt="{_e(view["name"])}">')
    else:
        out.append('<div class="cf-pp__nophoto">🎭</div>')
    meta = " · ".join(_e(_tr(v, lang)) for v in (view.get("category"), view.get("gender")) if v)
    out.append(f'<div><h1 dir="auto">{_e(view["name"])}</h1>'
               + (f'<div class="cf-pp__meta">{meta}</div>' if meta else "") + "</div></div>")
    if view.get("bio"):
        out.append(f'<h2>{_e(_tr("نبذة", lang))}</h2><p dir="auto">{_e(view["bio"])}</p>')
    if view["credits"]:
        out.append(f'<h2>{_e(_tr("أعمال سابقة", lang))}</h2><ul>'
                   + "".join(f'<li dir="auto">{_e(c["text"] or PROVIDER_LABEL)}'
                             + ("".join(video_html(v, c["text"]) for v in c["videos"]) if embed_videos else "")
                             + "</li>" for c in view["credits"]) + "</ul>")
    if view["details"] or view["skills"] or view.get("skills_notes"):
        out.append(f'<h2>{_e(_tr("مواصفات ومهارات", lang))}</h2><ul class="cf-pp__chips">')
        for key, value in view["details"]:
            shown = f"{value} {_tr('سم', lang)}" if key == "height_cm" else value
            out.append(f'<li>{_e(_tr(_LABELS[key], lang))}: <bdi>{_e(shown)}</bdi></li>')
        out.extend(f'<li>{_e(_tr(_LABELS[k], lang))}</li>' for k in view["skills"])
        out.append("</ul>")
        if view.get("skills_notes"):
            out.append(f'<p dir="auto" style="margin-top:8px">{_e(view["skills_notes"])}</p>')
    if view["links"]:
        out.append(f'<h2>{_e(_tr("روابط", lang))}</h2><ul>'
                   + "".join(f'<li><a href="{_e(u)}" target="_blank" rel="noopener noreferrer nofollow">'
                             f'{_e(_tr(label, lang))}</a></li>' for label, u in view["links"])
                   + "</ul>")
    if share_url:
        out.append('<div class="cf-pp__share">')
        if copy_button:  # Streamlit بيشيل onclick من st.html — هناك النسخ بـ st.code
            out.append(f'<button type="button" data-url="{_e(share_url)}" '
                       'onclick="navigator.clipboard&&navigator.clipboard.writeText(this.dataset.url)'
                       f'.then(()=>{{this.textContent={_e(repr(_tr("اتنسخ ✓", lang)))}}})">'
                       f'{_e(_tr("نسخ اللينك", lang))}</button>')
        for name, href in share_links(share_url, view["name"]):
            out.append(f'<a href="{_e(href)}" target="_blank" rel="noopener noreferrer">{_e(name)}</a>')
        out.append("</div>")
    out.append("</div>")
    foot = _e(_tr("بروفايل عام على CimaFast Studio — بيانات التواصل مش بتظهر هنا.", lang))
    switch = (f' · <a href="{_e(lang_switch_url)}">{"العربية" if lang == "en" else "English"}</a>'
              if lang_switch_url else "")
    out.append(f'<div class="cf-pp__foot">{foot}{switch}</div></div>')
    return "".join(out)


def render_page(view, lang="ar", photo_url=None, share_url=None, lang_switch_url=None, asset_base=""):
    """صفحة HTML كاملة بـ Open Graph — ده اللي بيخلّي واتساب وفيسبوك يعرضوا
    الاسم والصورة في معاينة اللينك. photo_url/share_url لازم يبقوا مطلقين هنا."""
    title = f'{view["name"]} — CimaFast Studio'
    desc = description(view, lang)
    d = "rtl" if lang != "en" else "ltr"
    og = [("og:type", "profile"), ("og:site_name", "CimaFast Studio"), ("og:title", title),
          ("og:description", desc), ("og:locale", "en_US" if lang == "en" else "ar_AR")]
    if share_url:
        og.append(("og:url", share_url))
    if view["has_photo"] and photo_url:
        og.append(("og:image", photo_url))
    tw = [("twitter:card", "summary_large_image" if view["has_photo"] and photo_url else "summary"),
          ("twitter:title", title), ("twitter:description", desc)]
    metas = "".join(f'<meta property="{k}" content="{_e(v)}">' for k, v in og)
    metas += "".join(f'<meta name="{k}" content="{_e(v)}">' for k, v in tw)
    fonts = (f'@font-face{{font-family:"Cairo";src:url("{asset_base}fonts/cairo-arabic-var.woff2") format("woff2");'
             'font-weight:200 1000;font-display:swap;unicode-range:U+0600-06FF,U+0750-077F,U+FB50-FDFF,U+FE70-FEFF,U+200C-200F}'
             f'@font-face{{font-family:"Cairo";src:url("{asset_base}fonts/cairo-latin-var.woff2") format("woff2");'
             'font-weight:200 1000;font-display:swap;unicode-range:U+0000-00FF,U+2000-206F}')
    return ("<!doctype html>"
            f'<html lang="{"en" if lang == "en" else "ar"}" dir="{d}"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta name="theme-color" content="#0F1B45">'
            '<meta name="referrer" content="strict-origin-when-cross-origin">'
            f'<title>{_e(title)}</title><meta name="description" content="{_e(desc)}">{metas}'
            f'<link rel="icon" type="image/png" href="{asset_base}brand/app-icon-dark.png">'
            f"<style>{fonts}body{{margin:0;background:#0F1B45}}{CSS}</style></head><body>"
            + render_body(view, lang, photo_url, share_url, lang_switch_url)
            + "</body></html>")


def render_not_found(lang="ar", asset_base=""):
    """نفس الصفحة لأي توكن غلط أو اتلغى أو ممثل اتمسح — مفيش فرق يكشف إنه كان موجود."""
    msg = _e(_tr("البروفايل ده مش متاح.", lang))
    return ("<!doctype html>"
            f'<html lang="{"en" if lang == "en" else "ar"}" dir="{"ltr" if lang == "en" else "rtl"}">'
            '<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta name="robots" content="noindex"><title>CimaFast Studio</title>'
            f"<style>body{{margin:0;background:#0F1B45}}{CSS}</style></head><body>"
            f'<div class="cf-pp"><div class="cf-pp__card"><h1>{msg}</h1></div></div></body></html>')
