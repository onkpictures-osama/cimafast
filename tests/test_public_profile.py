"""البروفايل العام للممثل/ة (مشاركة على السوشيال ميديا) — public_profile.py.

    venv/bin/python tests/test_public_profile.py

بيقفل: كل عمود في جدول actors متصنّف صراحةً (عام / باختيار الممثل/ة / خاص)،
اللينك مقفول افتراضيًا ومحدش يفتحه غير اللي يقدر يعدّل البروفايل، اللينك الجديد
والإيقاف بيموّتوا القديم، ومفيش ولا قيمة خاصة بتطلع في الصفحة العامة — لا في
HTML الـ Starlette ولا في صفحة Streamlit ‎?profile=‎. وكمان إن الصورة ماتطلعش
غير صورة الممثل/ة ده.

قاعدة بيانات مؤقتة — عمرها ما بتلمس الإنتاج.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_TMP = tempfile.mkdtemp(prefix="cimafast-public-profile-")
os.environ["STUDIO_DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ.pop("DATABASE_URL", None)
os.environ.pop("CIMAFAST_BOARD_URL", None)

import database  # noqa: E402
import permissions  # noqa: E402
import public_profile  # noqa: E402
import repo  # noqa: E402

database.init_db()
_results = []


def test(fn):
    _results.append(fn)
    return fn


def _company(name):
    database.run_query("INSERT INTO companies (name) VALUES (?)", (name,))
    return database.fetch_all("SELECT MAX(id) AS id FROM companies")[0]["id"]


A = _company("شركة أ")
B = _company("شركة ب")

# قيم خاصة مميزة — لو أي واحدة فيهم ظهرت في الصفحة يبقى فيه تسريب
PRIVATE = {
    "full_name": "PRIV-REALNAME-4417",       # فيه اسم شهرة، فالحقيقي خاص
    "contact_phone": "PRIV-PHONE-01009988776",
    "contact_email": "priv-mail-5521@example.test",
    "agent_name": "PRIV-AGENT-NAME-8812",
    "agent_contact": "PRIV-AGENT-CONTACT-3390",
    "hobbies": "PRIV-HOBBIES-6604",
    "link_other": "https://wa.me/PRIV-OTHER-LINK-2201",
    "weight_kg": 197,
    "chest_cm": 173,
    "waist_cm": 169,
    "hips_cm": 181,
    "shoe_size_eu": 53,
    "skills_notes": "PRIV-SKILLNOTES-7070",   # مش مختار "للكل" هنا
    "eye_color": "PRIV-EYES-1188",           # مش مختار
}
PUBLIC = {
    "stage_name": "نجمة الاختبار", "bio": "بيو عام للاختبار PUB-BIO",
    # فيديو يوتيوب بيتضمّن؛ لينك واتساب في نفس السطر لازم يتشال من الصفحة العامة
    "credits_text": "فيلم الاختبار (2025) PUB-CREDIT https://youtu.be/dQw4w9WgXcQ https://wa.me/PRIV-CREDITLINK-555\n"
                    "https://vimeo.com/76979871", "category": "بطولة", "gender": "أنثى",
    "link_showreel": "https://example.test/reel", "link_instagram": "javascript:alert(1)",
    "height_cm": 167, "hair_color": "PUB-HAIR-أسود",
}


def _leaky_actor(owner=A):
    values = dict(PRIVATE, **PUBLIC)
    # الممثل/ة مختار التليفون والوزن "ظاهرين للكل" جوه المنصة — ده مايخليهمش
    # يطلعوا على النت. الطول والشعر مختارين وهما في القايمة المسموحة.
    values["always_public_fields"] = "contact_phone,weight_kg,height_cm,hair_color,smokes,swims"
    values.update(smokes=1, swims=1, drives_car=1)   # drives_car مش مختار
    return repo.add_actor(values, owner_company_id=owner, created_by="test")


def _assert_no_private(page):
    for key, value in PRIVATE.items():
        assert str(value) not in page, f"leaked {key}: {value}"
    for word in ("مدخّن", "Smokes", "يقود عربية", "javascript:", "PRIV-CREDITLINK", "wa.me/PRIV"):
        assert word not in page, f"leaked {word}"


@test
def test_every_actor_column_is_classified_exactly_once():
    if database.USE_POSTGRES:
        return
    conn = database.get_connection()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(actors)").fetchall()}
    conn.close()
    groups = (public_profile.PUBLIC_FIELDS, public_profile.OPT_IN_FIELDS, public_profile.PRIVATE_FIELDS)
    classified = set().union(*groups)
    assert cols - classified == set(), f"unclassified actor columns: {cols - classified}"
    assert sum(len(g) for g in groups) == len(classified), "a column is in two groups"


@test
def test_sharing_is_off_by_default_and_garbage_tokens_find_nothing():
    aid = _leaky_actor()
    assert repo.actor_by_id(aid)["public_share_token"] is None
    for bad in (None, "", "x", "' OR 1=1 --", "../../etc/passwd", "a" * 200):
        assert repo.actor_by_public_token(bad) is None


@test
def test_only_the_editing_company_can_share():
    aid = _leaky_actor(owner=A)
    assert repo.share_actor_publicly(aid, B, "admin") is None          # شركة تانية
    with permissions.acting_as("viewer"):
        assert repo.share_actor_publicly(aid, A, "viewer") is None     # مشاهدة بس
    assert repo.actor_by_id(aid)["public_share_token"] is None
    assert repo.stop_sharing_actor(aid, B, "admin") is False
    token = repo.share_actor_publicly(aid, A, "admin")
    assert public_profile.valid_token(token)
    assert repo.actor_by_public_token(token)["id"] == aid
    # الشركة التانية مش قادرة توقفه برضو
    repo.stop_sharing_actor(aid, B, "admin")
    assert repo.actor_by_public_token(token)["id"] == aid
    # مشغّل المنصة يقدر (بروفايلات مضافة من الإدارة)
    admin_made = repo.add_actor({"full_name": "من الإدارة"})
    assert repo.share_actor_publicly(admin_made, A, "admin") is None
    assert repo.share_actor_publicly(admin_made, None, "operator")


@test
def test_new_link_kills_the_old_one_and_stop_kills_everything():
    aid = _leaky_actor()
    first = repo.share_actor_publicly(aid, A, "admin")
    second = repo.share_actor_publicly(aid, A, "admin")
    assert first != second
    assert repo.actor_by_public_token(first) is None
    assert repo.actor_by_public_token(second)["id"] == aid
    assert repo.stop_sharing_actor(aid, A, "admin")
    assert repo.actor_by_public_token(second) is None
    assert repo.actor_by_id(aid)["public_share_token"] is None


@test
def test_public_view_holds_only_whitelisted_values():
    view = public_profile.public_view(repo.actor_by_id(_leaky_actor()))
    assert view["name"] == "نجمة الاختبار"
    assert dict(view["details"]) == {"height_cm": 167, "hair_color": "PUB-HAIR-أسود"}
    assert view["skills"] == ["swims"]
    assert view["skills_notes"] is None
    assert [u for _, u in view["links"]] == ["https://example.test/reel"]   # javascript: اتشال
    _assert_no_private(repr(view))


@test
def test_rendered_pages_leak_nothing_in_either_language():
    token = repo.share_actor_publicly(_leaky_actor(), A, "admin")
    view = public_profile.public_view(repo.actor_by_public_token(token))
    for lang in ("ar", "en"):
        page = public_profile.render_page(view, lang, photo_url="https://x.test/p/photo",
                                          share_url=f"https://x.test/p/{token}")
        assert "نجمة الاختبار" in page and "PUB-BIO" in page and "PUB-CREDIT" in page
        assert "PUB-HAIR" in page and "167" in page
        assert ('dir="rtl"' in page) == (lang == "ar")
        assert 'property="og:title"' in page and 'property="og:description"' in page
        assert 'src="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"' in page
        assert 'src="https://player.vimeo.com/video/76979871"' in page
        _assert_no_private(page)


@test
def test_starlette_page_404s_uniformly_and_serves_only_this_actors_photo():
    from starlette.requests import Request
    import board.app as board

    def call(handler, token, path_suffix=""):
        scope = {"type": "http", "method": "GET", "path": f"/p/{token}{path_suffix}",
                 "path_params": {"token": token}, "query_string": b"", "scheme": "https",
                 "headers": [(b"host", b"cimafast.test")], "server": ("cimafast.test", 443)}
        return asyncio.run(handler(Request(scope)))

    aid = _leaky_actor()
    token = repo.share_actor_publicly(aid, A, "admin")
    ok = call(board.public_actor_page, token)
    assert ok.status_code == 200
    page = ok.body.decode()
    assert "نجمة الاختبار" in page
    assert f"https://cimafast.test/v1/board/p/{token}/photo" not in page   # مفيش صورة لسه
    _assert_no_private(page)
    assert ok.headers["cache-control"] == "no-store"
    csp = ok.headers["content-security-policy"]
    assert "frame-src https://www.youtube-nocookie.com" in csp and "default-src 'none'" in csp
    assert "youtube-nocookie.com/embed/dQw4w9WgXcQ" in page

    # توكن غلط، توكن اتلغى: نفس الرد بالظبط
    wrong = call(board.public_actor_page, "A" * 22)
    repo.stop_sharing_actor(aid, A, "admin")
    revoked = call(board.public_actor_page, token)
    assert wrong.status_code == revoked.status_code == 404
    assert wrong.body == revoked.body

    # الصورة: بتاعته بس، ومسار بيطلع برّه مجلده مرفوض
    aid2 = _leaky_actor()
    token2 = repo.share_actor_publicly(aid2, A, "admin")
    folder = os.path.join(ROOT, "uploads", "actors", str(aid2))
    os.makedirs(folder, exist_ok=True)
    img = os.path.join(folder, "test-headshot.png")
    with open(img, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n")
    try:
        repo.set_actor_photo(aid2, f"uploads/actors/{aid2}/test-headshot.png")
        photo = call(board.public_actor_photo, token2, "/photo")
        assert photo.status_code == 200 and os.path.realpath(photo.path) == os.path.realpath(img)
        page2 = call(board.public_actor_page, token2).body.decode()
        assert f"https://cimafast.test/v1/board/p/{token2}/photo" in page2      # og:image مطلق
        for evil in ("uploads/../app.py", f"uploads/actors/{aid2}/../../../app.py",
                     f"uploads/actors/{aid}/x.png", "/etc/passwd", "studio.db"):
            repo.set_actor_photo(aid2, evil)
            assert call(board.public_actor_photo, token2, "/photo").status_code == 404, evil
    finally:
        os.remove(img)
        os.rmdir(folder)


@test
def test_streamlit_profile_param_renders_before_login_without_private_data():
    from streamlit.testing.v1 import AppTest
    import auth
    import json
    # فيه حسابات، يعني بوابة الدخول شغالة — الصفحة العامة لازم تتعرض قبلها
    os.environ[auth.USERS_ENV] = json.dumps({"someone": auth.hash_password("pw-long-enough", iterations=1000)})
    token = repo.share_actor_publicly(_leaky_actor(), A, "admin")

    at = AppTest.from_file(os.path.join(ROOT, "app.py"), default_timeout=120)
    at.query_params["profile"] = token
    at.run()
    assert not at.exception, at.exception
    # عناصر الصفحة العامة بس (cf-pp) — باقي عناصر html هي حقن الثيم نفسه
    htmls = " ".join(str(e.proto) for e in at.get("html") if "cf-pp" in str(e.proto))
    assert "نجمة الاختبار" in htmls and "PUB-BIO" in htmls
    _assert_no_private(htmls)
    assert not any(w.key == "_login_username" for w in at.text_input)   # مش شاشة الدخول

    at = AppTest.from_file(os.path.join(ROOT, "app.py"), default_timeout=120)
    at.query_params["profile"] = "B" * 22
    at.run()
    htmls = " ".join(str(e.proto) for e in at.get("html"))
    assert "البروفايل ده مش متاح" in htmls
    assert not any(w.key == "_login_username" for w in at.text_input)


def _internal_profile_script():
    import os
    import sys
    sys.path.insert(0, os.environ["_PP_ROOT"])
    import permissions
    import streamlit as st
    import views.actors as actors
    permissions.set_resolver(lambda: "operator")
    st.session_state["ui_lang"] = os.environ.get("_PP_LANG", "ar")
    st.session_state[actors._SELECTED_KEY] = int(os.environ["_PP_ACTOR"])
    actors.render_library("x", None, None)     # البروفايل بقى في صفحة مكتبة الممثلين


@test
def test_internal_profile_embeds_videos_and_flags_unknown_links():
    from streamlit.testing.v1 import AppTest
    aid = _leaky_actor()
    os.environ.update(_PP_ROOT=ROOT, _PP_ACTOR=str(aid))
    for lang in ("ar", "en"):
        os.environ["_PP_LANG"] = lang
        at = AppTest.from_function(_internal_profile_script, default_timeout=60)
        at.run()
        assert not at.exception, at.exception
        frames = [str(e.proto) for e in at.get("iframe")]
        assert any("youtube-nocookie.com/embed/dQw4w9WgXcQ" in f for f in frames), frames
        assert any("player.vimeo.com/video/76979871" in f for f in frames), frames
        flagged = " ".join(c.value for c in at.caption)
        assert "wa.me/PRIV-CREDITLINK-555" in flagged
        assert ("Not recognised as a video link" in flagged) == (lang == "en")
        # المشغّل بتاعنا بس — مش لينك الواتساب
        assert not any("wa.me" in f for f in frames)


if __name__ == "__main__":
    failed = 0
    for fn in _results:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            import traceback
            traceback.print_exc()
            print(f"FAIL {fn.__name__}: {exc}")
    print(f"\n{len(_results) - failed}/{len(_results)} passed")
    sys.exit(1 if failed else 0)
