"""لينك الخريطة بتاع المكان — قاعدة بيانات مؤقتة، عمرها ما بتلمس الإنتاج.

    venv/bin/python tests/test_location_maps.py

اللينك نص حر عن قصد: اليوزر بيلزق لينك Google Maps أو Waze أو أي خدمة تانية،
فالتنضيف الوحيد هو شيل المسافات وإضافة https لو ناقصة. فاضي = None، وده اللي
بيخلي الزرار يختفي من الشاشة بدل ما يفضل زرار مطفي.
"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_TMP = tempfile.mkdtemp(prefix="cimafast-maps-")
os.environ["STUDIO_DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ.pop("DATABASE_URL", None)

import database  # noqa: E402
import repo  # noqa: E402
from views.locations import _clean_maps_url  # noqa: E402

database.init_db()
_results = []


def test(fn):
    _results.append(fn)
    return fn


def _project(name="P"):
    database.run_query("INSERT INTO projects (name, project_type) VALUES (?, 'فيلم')", (name,))
    return database.fetch_all("SELECT MAX(id) AS id FROM projects")[0]["id"]


def _loc(pid, name):
    return [l for l in repo.locations_of_project(pid) if l["name"] == name][0]


# --- تنضيف اللينك -----------------------------------------------------------

@test
def test_empty_input_means_no_link():
    for blank in ("", "   ", None):
        assert _clean_maps_url(blank) is None, blank


@test
def test_a_full_url_is_kept_as_is():
    url = "https://maps.app.goo.gl/AbCd1234"
    assert _clean_maps_url(url) == url
    assert _clean_maps_url(f"  {url}  ") == url


@test
def test_a_bare_domain_gets_https():
    # اليوزر بينسخ من الموبايل وساعات بييجي من غير البروتوكول
    assert _clean_maps_url("maps.google.com/?q=30.0,31.2") == "https://maps.google.com/?q=30.0,31.2"


@test
def test_any_map_service_works_not_just_google():
    for url in ("https://waze.com/ul?ll=30.0,31.2", "https://maps.apple.com/?ll=30.0,31.2"):
        assert _clean_maps_url(url) == url


@test
def test_http_is_left_alone_and_case_does_not_matter():
    assert _clean_maps_url("http://osm.org/x") == "http://osm.org/x"
    assert _clean_maps_url("HTTPS://maps.google.com/x") == "HTTPS://maps.google.com/x"


@test
def test_a_non_http_scheme_is_defused_not_passed_through():
    # مش بنسيب حاجة زي javascript: تعدي لـ link_button
    out = _clean_maps_url("javascript:alert(1)")
    assert out.startswith("https://"), out


# --- الدورة الكاملة في قاعدة البيانات ---------------------------------------

@test
def test_a_location_saves_and_reads_back_its_link():
    pid = _project("مشروع الخريطة")
    repo.add_location(pid, "شقة حسام", "شقة قديمة", None, _clean_maps_url("maps.app.goo.gl/XYZ"))
    assert _loc(pid, "شقة حسام")["maps_url"] == "https://maps.app.goo.gl/XYZ"


@test
def test_a_location_without_a_link_stores_null():
    pid = _project("مشروع من غير خريطة")
    repo.add_location(pid, "مقهى", "", None, _clean_maps_url(""))
    assert _loc(pid, "مقهى")["maps_url"] is None


@test
def test_editing_can_add_then_clear_the_link():
    pid = _project("مشروع التعديل")
    repo.add_location(pid, "استوديو", "", None, None)
    lid = _loc(pid, "استوديو")["id"]

    repo.update_location("استوديو", "", None, _clean_maps_url("waze.com/ul?ll=1,2"), lid)
    assert _loc(pid, "استوديو")["maps_url"] == "https://waze.com/ul?ll=1,2"

    # مسح الحقل لازم يرجّعه None عشان الزرار يختفي تاني
    repo.update_location("استوديو", "", None, _clean_maps_url("  "), lid)
    assert _loc(pid, "استوديو")["maps_url"] is None


@test
def test_the_column_survives_an_old_database():
    # قاعدة قديمة = السكيما الحقيقية من غير العمود. بنشيله وبعدين نشغل
    # المهاجرة، عشان نتأكد إنها بتضيفه من غير ما تلمس بيانات اليوزر.
    import sqlite3
    old = os.path.join(_TMP, "old.db")
    prev, database.DB_PATH = database.DB_PATH, old   # DB_PATH بتتقري وقت الاستيراد
    try:
        database.init_db()
    finally:
        database.DB_PATH = prev

    con = sqlite3.connect(old)
    con.row_factory = sqlite3.Row
    con.execute("ALTER TABLE locations DROP COLUMN maps_url")
    con.execute("INSERT INTO projects (name, project_type) VALUES ('قديم', 'فيلم')")
    con.execute("INSERT INTO locations (project_id, name, base_description) VALUES (1, 'بيت', 'وصف')")
    con.commit()
    assert "maps_url" not in {r["name"] for r in con.execute("PRAGMA table_info(locations)")}

    database._migrate_schema(con)

    cols = {r["name"] for r in con.execute("PRAGMA table_info(locations)")}
    row = con.execute("SELECT * FROM locations").fetchone()
    con.close()
    assert "maps_url" in cols, cols
    assert row["base_description"] == "وصف"   # البيانات القديمة زي ما هي
    assert row["maps_url"] is None


def main():
    failed = 0
    for fn in _results:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except Exception as exc:
            failed += 1
            print(f"  FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(_results) - failed}/{len(_results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
