"""فيديوهات الأعمال السابقة — videos.py: تحويل لينك لرابط تضمين من قايمة معروفة.

    venv/bin/python tests/test_videos.py

بيقفل: أشكال لينكات يوتيوب/فيميو/ديلي موشن/فيسبوك/ملف mp4 بتتحول لرابط تضمين
إحنا بانينه، وأي حاجة تانية (javascript:، دومين شبيه، رقم فيديو فيه حروف غريبة،
HTML) بترجع None ومابتتضمّنش أبدًا.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import videos  # noqa: E402

YT = "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"
VALID = {
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ": YT,
    "https://youtube.com/watch?v=dQw4w9WgXcQ&t=42s&list=PL123": YT,
    "http://m.youtube.com/watch?v=dQw4w9WgXcQ": YT,
    "https://youtu.be/dQw4w9WgXcQ": YT,
    "https://youtu.be/dQw4w9WgXcQ?si=abc": YT,
    "https://www.youtube.com/shorts/dQw4w9WgXcQ": YT,
    "https://www.youtube.com/embed/dQw4w9WgXcQ": YT,
    "https://www.youtube.com/live/dQw4w9WgXcQ": YT,
    "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ": YT,
    "https://vimeo.com/76979871": "https://player.vimeo.com/video/76979871",
    "https://vimeo.com/76979871/abc123def0": "https://player.vimeo.com/video/76979871?h=abc123def0",
    "https://vimeo.com/channels/staffpicks/76979871": "https://player.vimeo.com/video/76979871",
    "https://player.vimeo.com/video/76979871?h=abc123def0": "https://player.vimeo.com/video/76979871?h=abc123def0",
    "https://www.dailymotion.com/video/x8abc12": "https://www.dailymotion.com/embed/video/x8abc12",
    "https://www.dailymotion.com/video/x8abc12_some-title": "https://www.dailymotion.com/embed/video/x8abc12",
    "https://dai.ly/x8abc12": "https://www.dailymotion.com/embed/video/x8abc12",
    "https://www.facebook.com/somepage/videos/1234567890123/":
        "https://www.facebook.com/plugins/video.php?href=https%3A%2F%2Fwww.facebook.com%2Fwatch%2F%3Fv%3D1234567890123&show_text=false",
    "https://www.facebook.com/watch/?v=1234567890123":
        "https://www.facebook.com/plugins/video.php?href=https%3A%2F%2Fwww.facebook.com%2Fwatch%2F%3Fv%3D1234567890123&show_text=false",
    "https://cdn.example.com/reels/actor-reel_2025.mp4": "https://cdn.example.com/reels/actor-reel_2025.mp4",
}
INVALID = [
    None, "", "not a url", "javascript:alert(1)", "JaVaScRiPt:alert(1)//youtube.com/watch?v=dQw4w9WgXcQ",
    "data:text/html,<script>alert(1)</script>", "ftp://youtu.be/dQw4w9WgXcQ",
    "https://youtube.com.evil.com/watch?v=dQw4w9WgXcQ",       # دومين شبيه
    "https://evilyoutube.com/watch?v=dQw4w9WgXcQ",
    "https://youtu.be.evil.com/dQw4w9WgXcQ",
    "https://evil.com/youtu.be/dQw4w9WgXcQ",
    "https://www.youtube.com@evil.com/watch?v=dQw4w9WgXcQ",   # userinfo
    "https://evil.com#https://youtu.be/dQw4w9WgXcQ",
    "https://www.youtube.com:8443/watch?v=dQw4w9WgXcQ",
    "https://www.youtube.com/watch?v=dQw4w9WgXc",              # 10 حروف
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ\"><script>",
    "https://www.youtube.com/watch?v=<script>alert(1)</script>",
    "https://youtu.be/dQw4w9WgXcQ/../../evil",
    "https://www.youtube.com/channel/UC123",
    "https://vimeo.com/abc", "https://vimeo.com.evil.com/76979871", "https://vimeo.com/76979871/NOT-HEX!",
    "https://player.vimeo.com/video/76979871?h=\"onload=alert(1)",
    "https://dailymotion.com.evil.com/video/x8abc12", "https://www.dailymotion.com/video/../x8",
    "https://facebook.com.evil.com/watch/?v=1234567890123", "https://www.facebook.com/watch/?v=abc",
    "https://fb.watch/abcd/",
    "http://cdn.example.com/reel.mp4",                         # ملف لازم https
    "https://127.0.0.1/reel.mp4", "https://localhost/reel.mp4", "https://cdn.example.com/reel.mp4?x=1",
    "https://cdn.example.com/reel.html", "https://wa.me/201000000000",
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ " + "x" * 600,
]


def test_valid_urls_become_our_own_embed_urls():
    for url, embed in VALID.items():
        got = videos.parse(url)
        assert got and got["embed_url"] == embed, (url, got)


def test_everything_else_is_refused():
    for url in INVALID:
        assert videos.parse(url) is None, url


def test_embed_urls_only_point_at_allowlisted_hosts():
    for url in VALID:
        v = videos.parse(url)
        if v["kind"] == "iframe":
            assert any(v["embed_url"].startswith(h + "/") for h in videos.EMBED_HOSTS), v


def test_credit_lines_split_text_videos_and_unknown_links():
    items = videos.credits("فيلم كذا (2023) - دور كذا https://youtu.be/dQw4w9WgXcQ, https://wa.me/2010\n\n"
                           "مسلسل تاني https://vimeo.com/76979871")
    assert len(items) == 2
    assert items[0]["text"] == "فيلم كذا (2023) - دور كذا"
    assert [v["provider"] for v in items[0]["videos"]] == ["youtube"]
    assert items[0]["unrecognised"] == ["https://wa.me/2010"]
    assert items[1]["videos"][0]["provider"] == "vimeo" and not items[1]["unrecognised"]
    assert videos.unrecognised("بس نص من غير لينكات") == []


if __name__ == "__main__":
    fns = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {exc!r}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
