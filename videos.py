"""فيديوهات الأعمال السابقة (P9): لينك يوتيوب/فيميو/... جوه سطر العمل بيتحوّل
لمشغّل متضمّن في بروفايل الممثل (جوه البرنامج وفي الصفحة العامة).

القاعدة: عمرنا ما بنحط HTML ولا لينك اليوزر كتبه في iframe. بنطلّع من اللينك
رقم الفيديو بس (بـ regex صارم لكل خدمة)، وبنبني رابط التضمين إحنا من قايمة
خدمات معروفة (EMBED_HOSTS). أي لينك مش متعرف عليه مابيتضمّنش — بيتعلّم
للمستخدم يصلّحه، ومابيطلعش في الصفحة العامة أصلًا.

    parse("https://youtu.be/dQw4w9WgXcQ")
    → {"provider": "youtube", "id": "dQw4w9WgXcQ", "kind": "iframe",
       "embed_url": "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"}
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

# الهوستات اللي بنضمّن منها — CSP بتاعة الصفحة العامة (frame-src) مبنية من هنا
EMBED_HOSTS = ("https://www.youtube-nocookie.com", "https://player.vimeo.com",
               "https://www.dailymotion.com", "https://www.facebook.com")

PROVIDER_NAMES = {"youtube": "YouTube", "vimeo": "Vimeo", "dailymotion": "Dailymotion",
                  "facebook": "Facebook", "file": "Video"}

_URL_IN_TEXT = re.compile(r"https?://[^\s<>\"'،]+", re.IGNORECASE)

_YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_VIMEO_ID = re.compile(r"^\d{6,12}$")
_VIMEO_HASH = re.compile(r"^[0-9a-f]{6,20}$")
_DM_ID = re.compile(r"^x[a-z0-9]{4,10}$", re.IGNORECASE)
_FB_ID = re.compile(r"^\d{8,20}$")
_FILE_PATH = re.compile(r"^/[A-Za-z0-9._~/%-]{1,300}\.(mp4|webm|m4v|mov)$", re.IGNORECASE)
_HOST_RE = re.compile(r"^[a-z0-9.-]{1,253}$")

_YT_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
             "youtube-nocookie.com", "www.youtube-nocookie.com"}
_VIMEO_HOSTS = {"vimeo.com", "www.vimeo.com", "player.vimeo.com"}
_DM_HOSTS = {"dailymotion.com", "www.dailymotion.com"}
_FB_HOSTS = {"facebook.com", "www.facebook.com", "m.facebook.com", "web.facebook.com"}


def _host(parts):
    """الهوست بالظبط (مقارنة كاملة مش endswith) — كده youtube.com.evil.com
    وevil-youtube.com وuser@youtube.com مايعدّوش."""
    if parts.username or parts.password or parts.port not in (None, 443, 80):
        return None
    host = (parts.hostname or "").lower().rstrip(".")
    return host if _HOST_RE.match(host) else None


def _yt(parts, host):
    segs = [s for s in parts.path.split("/") if s]
    vid = None
    if host == "youtu.be":
        vid = segs[0] if len(segs) == 1 else None
    elif host in _YT_HOSTS:
        if segs == ["watch"]:
            vid = (parse_qs(parts.query).get("v") or [None])[0]
        elif len(segs) == 2 and segs[0] in ("shorts", "embed", "live", "v"):
            vid = segs[1]
    if vid and _YT_ID.match(vid):
        return {"provider": "youtube", "id": vid, "kind": "iframe",
                "embed_url": f"https://www.youtube-nocookie.com/embed/{vid}"}
    return None


def _vimeo(parts, host):
    if host not in _VIMEO_HOSTS:
        return None
    segs = [s for s in parts.path.split("/") if s]
    vid, h = None, (parse_qs(parts.query).get("h") or [None])[0]
    if host == "player.vimeo.com":
        if len(segs) == 2 and segs[0] == "video":
            vid = segs[1]
    elif len(segs) == 1:
        vid = segs[0]
    elif len(segs) == 2 and _VIMEO_ID.match(segs[0]):      # لينك غير مدرج: /ID/HASH
        vid, h = segs[0], segs[1]
    elif len(segs) == 3 and segs[0] == "channels":
        vid = segs[2]
    elif len(segs) == 4 and segs[0] == "groups" and segs[2] == "videos":
        vid = segs[3]
    if not vid or not _VIMEO_ID.match(vid):
        return None
    if h is not None and not _VIMEO_HASH.match(h):
        return None
    return {"provider": "vimeo", "id": vid, "kind": "iframe",
            "embed_url": f"https://player.vimeo.com/video/{vid}" + (f"?h={h}" if h else "")}


def _dailymotion(parts, host):
    segs = [s for s in parts.path.split("/") if s]
    vid = None
    if host == "dai.ly" and len(segs) == 1:
        vid = segs[0]
    elif host in _DM_HOSTS:
        if len(segs) == 2 and segs[0] == "video":
            vid = segs[1]
        elif len(segs) == 3 and segs[:2] == ["embed", "video"]:
            vid = segs[2]
        if vid:
            vid = vid.split("_")[0]          # /video/x8abc12_عنوان-الفيديو
    if vid and _DM_ID.match(vid):
        return {"provider": "dailymotion", "id": vid, "kind": "iframe",
                "embed_url": f"https://www.dailymotion.com/embed/video/{vid}"}
    return None


def _facebook(parts, host):
    if host not in _FB_HOSTS:
        return None
    segs = [s for s in parts.path.split("/") if s]
    vid = None
    if segs == ["watch"]:
        vid = (parse_qs(parts.query).get("v") or [None])[0]
    elif len(segs) >= 3 and segs[-2] == "videos":           # /<صفحة>/videos/<id>
        vid = segs[-1]
    elif len(segs) == 4 and segs[1] == "videos" and segs[2].startswith("vb."):
        vid = segs[3]
    elif len(segs) == 2 and segs[0] == "reel":
        vid = segs[1]
    if vid and _FB_ID.match(vid):
        # رابط الـ plugin بيتبني من الرقم بس — مش من اللينك اللي اتكتب
        href = f"https%3A%2F%2Fwww.facebook.com%2Fwatch%2F%3Fv%3D{vid}"
        return {"provider": "facebook", "id": vid, "kind": "iframe",
                "embed_url": f"https://www.facebook.com/plugins/video.php?href={href}&show_text=false"}
    return None


def _file(parts, host):
    """ملف فيديو مباشر (mp4/webm) على https — بيتعرض بـ <video> مش iframe،
    فمفيش صفحة من برّه بتتفتح جوه البروفايل."""
    if parts.scheme != "https" or parts.query or parts.fragment or not _FILE_PATH.match(parts.path):
        return None
    if host in ("localhost",) or re.match(r"^[\d.]+$", host) or "." not in host:
        return None
    url = f"https://{host}{parts.path}"
    return {"provider": "file", "id": url, "kind": "video", "embed_url": url}


def parse(url):
    """اللينك → dict التضمين، أو None لو مش لينك فيديو متعرف عليه."""
    if not isinstance(url, str):
        return None
    url = url.strip()
    if len(url) > 500 or not re.match(r"^https?://", url, re.IGNORECASE) or re.search(r"[\s<>\"'\\]", url):
        return None
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    host = _host(parts)
    if not host:
        return None
    for fn in (_yt, _vimeo, _dailymotion, _facebook, _file):
        found = fn(parts, host)
        if found:
            return found
    return None


def split_credit(line):
    """سطر عمل سابق → (النص من غير اللينكات، فيديوهات متعرف عليها، لينكات مش متعرف عليها)."""
    urls = [u.rstrip(".,)،؛") for u in _URL_IN_TEXT.findall(line or "")]
    text = _URL_IN_TEXT.sub("", line or "")
    text = re.sub(r"\s{2,}", " ", text).strip(" -–—|·").strip()
    found, bad = [], []
    for u in urls:
        v = parse(u)
        (found if v else bad).append(v or u)
    return text, found, bad


def credits(credits_text):
    """كل سطور الأعمال: [{"text", "videos", "unrecognised"}] — السطور الفاضية بتتشال."""
    out = []
    for line in str(credits_text or "").splitlines():
        if not line.strip():
            continue
        text, found, bad = split_credit(line)
        out.append({"text": text, "videos": found, "unrecognised": bad})
    return out


def unrecognised(credits_text):
    return [u for c in credits(credits_text) for u in c["unrecognised"]]
