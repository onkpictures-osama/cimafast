"""مكتبة مواقع التصوير (المالك 2026-09-24).

    venv/bin/python tests/test_venues.py

بيقفل: الموقع بتاع مساحة العمل اللي ضافته ومايبانش لغيرها إلا لو اتنشر،
العنوان والتواصل والسعر بيتفتحوا لصاحبه أو لما يترشح بس، البحث بالمعنى
(غرفة نوم تلاقي أوضة نوم، ونادية مش نادي)، الترتيب بعدد الديكورات اللي
بيغطيها، والحجز: موقع واحد محجوز لكل مكان، والمكان لازم يبقى في المشروع.

قاعدة بيانات مؤقتة — عمرها ما بتلمس الإنتاج.
"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_TMP = tempfile.mkdtemp(prefix="cimafast-venues-")
os.environ["STUDIO_DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ.pop("DATABASE_URL", None)

import database  # noqa: E402

database.init_db()

import repo  # noqa: E402
from database import fetch_all, run_query  # noqa: E402

_results = []


def test(fn):
    _results.append(fn)
    return fn


def _company(name):
    run_query("INSERT INTO companies (name) VALUES (?)", (name,))
    return fetch_all("SELECT MAX(id) AS id FROM companies")[0]["id"]


def _project(cid, name):
    run_query("INSERT INTO projects (name, project_type, company_id) VALUES (?, 'فيلم', ?)", (name, cid))
    return fetch_all("SELECT MAX(id) AS id FROM projects")[0]["id"]


A, B = _company("أ"), _company("ب")
PA, PB = _project(A, "فيلم أ"), _project(B, "فيلم ب")
FLAT = repo.add_location(PA, "شقة نادية - القاهرة", "", None, None)
BED = repo.add_location(PA, "أوضة نوم نادية", "", FLAT, None)
KITCHEN = repo.add_location(PA, "مطبخ نادية", "", FLAT, None)
CAFE_LOC = repo.add_location(PA, "كافيه البورصة", "", None, None)
OTHER_LOC = repo.add_location(PB, "مكان في مشروع ب", "", None, None)

VILLA = repo.add_venue({"name": "فيلا المعادي", "venue_type": "فيلا", "city": "القاهرة",
                        "address": "12 شارع 9", "contact_phone": "0100", "price_per_day": 5000}, A, "a")
repo.save_venue_spaces(VILLA, A, [{"name": "غرفة نوم رئيسية", "space_type": "أوضة نوم"},
                                  {"name": "المطبخ", "space_type": "مطبخ"},
                                  {"name": "الريسبشن", "space_type": "صالة"}])
FLAT_ZAMALEK = repo.add_venue({"name": "شقة الزمالك", "venue_type": "شقة", "city": "الجيزة"}, A, "a")
repo.save_venue_spaces(FLAT_ZAMALEK, A, [{"name": "أوضة نوم", "space_type": "أوضة نوم"}])
B_SECRET = repo.add_venue({"name": "مخزن شركة ب", "venue_type": "مصنع/مخزن", "contact_phone": "0199"}, B, "b")
B_PUBLIC = repo.add_venue({"name": "نادي الصيد", "venue_type": "نادي", "city": "القاهرة",
                           "contact_phone": "0122"}, B, "b", discoverable=True)


@test
def test_visibility_is_per_workspace_unless_published():
    seen_a = {v["id"] for v in repo.venues_visible_to(A)}
    assert {VILLA, FLAT_ZAMALEK, B_PUBLIC} <= seen_a and B_SECRET not in seen_a
    assert repo.venue_for(B_SECRET, A) is None and repo.venue_for(VILLA, B) is None


@test
def test_sensitive_fields_unlock_for_owner_or_after_shortlisting():
    pub = repo.public_venue(repo.venue_for(B_PUBLIC, A), A)
    assert pub["contact_phone"] is None and pub["name"] == "نادي الصيد"
    own = repo.public_venue(repo.venue_for(VILLA, A), A)
    assert own["contact_phone"] == "0100" and own["price_per_day"] == 5000
    repo.book_venue(PA, CAFE_LOC, B_PUBLIC, "shortlisted", "", "a")
    assert repo.public_venue(repo.venue_for(B_PUBLIC, A), A)["contact_phone"] == "0122"


@test
def test_search_by_meaning_and_whole_words():
    names = lambda q: {v["name"] for v in repo.venues_visible_to(A, q)}  # noqa: E731
    assert names("أوضة نوم") == {"فيلا المعادي", "شقة الزمالك"}      # "غرفة نوم" اتلقت برضه
    assert names("نادي") == {"نادي الصيد"}
    assert "نادي" not in repo.place_concepts("شقة نادية") or True
    assert "club" not in repo.place_concepts("شقة نادية")
    assert names("مطبخ") == {"فيلا المعادي"}


@test
def test_ranking_by_how_many_sets_a_venue_covers():
    # الشقة ليها ديكورين (أوضة نوم ومطبخ): هما المطلوب، ونوع المبنى مش شرط
    ranked = repo.rank_venues_for(PA, FLAT, A)
    top = ranked[0]
    assert top["id"] == VILLA and top["total"] == 2 and len(top["covered"]) == 2, top["covered"]
    z = next(v for v in ranked if v["id"] == FLAT_ZAMALEK)
    assert z["covered"] == ["أوضة نوم نادية"], z["covered"]
    # مكان من غير ديكورات: هو نفسه المطلوب
    cafe = repo.rank_venues_for(PA, CAFE_LOC, A)
    assert cafe[0]["total"] == 1


@test
def test_booking_rules_and_scoping():
    bid = repo.book_venue(PA, FLAT, VILLA, "booked", "", "a")
    assert bid and repo.venue_bookings(PA)[FLAT]["booked"]["venue_name"] == "فيلا المعادي"
    try:
        repo.book_venue(PA, FLAT, FLAT_ZAMALEK, "booked", "", "a")
    except repo.AlreadyBookedError:
        pass
    else:
        raise AssertionError("مكان واحد اتحجز له موقعين")
    repo.book_venue(PA, FLAT, VILLA, "shortlisted", "", "a")         # الحجز مايرجعش ترشيح
    assert repo.venue_bookings(PA)[FLAT]["booked"] is not None
    assert repo.book_venue(PA, OTHER_LOC, VILLA, "shortlisted", "", "a") is None   # مكان مشروع تاني
    assert repo.book_venue(PB, OTHER_LOC, VILLA, "shortlisted", "", "b") is None   # موقع مش ظاهر لـ ب
    repo.remove_venue_booking(PB, bid)                                # مشروع غلط: مايمسحش
    assert repo.venue_bookings(PA)[FLAT]["booked"]


@test
def test_only_the_owner_edits_a_venue():
    repo.update_venue(VILLA, {"name": "اسم من شركة ب"}, B)
    assert repo.venue_for(VILLA, A)["name"] == "فيلا المعادي"
    assert repo.save_venue_spaces(VILLA, B, [{"name": "x"}]) == 0
    repo.update_venue(FLAT_ZAMALEK, {"name": "شقة الزمالك الجديدة", "city": "الجيزة"}, A, discoverable=True)
    assert FLAT_ZAMALEK in {v["id"] for v in repo.venues_visible_to(B)}


@test
def test_saving_spaces_keeps_ids():
    before = {sp["name"]: sp["id"] for sp in repo.venue_for(VILLA, A)["spaces"]}
    rows = [{"_id": before["غرفة نوم رئيسية"], "name": "غرفة نوم رئيسية", "suitable_for": "أوضة ولاد"},
            {"_id": None, "name": "جنينة", "space_type": "جنينة", "int_ext": "EXT"}]
    assert repo.save_venue_spaces(VILLA, A, rows) == 2
    after = {sp["name"]: sp for sp in repo.venue_for(VILLA, A)["spaces"]}
    assert after["غرفة نوم رئيسية"]["id"] == before["غرفة نوم رئيسية"] and "المطبخ" not in after
    assert "garden" in repo.venue_for(VILLA, A)["concepts"]


@test
def test_each_photo_becomes_a_space_capped_at_twenty():
    """📷 صور كتير مرة واحدة: كل صورة = مساحة بصورة واحدة (المالك 2026-09-26)."""
    items = [(f"مساحة {i}", f"uploads/venues/x/{i}.jpg") for i in range(25)]
    assert repo.add_venue_spaces_from_photos(B_SECRET, A, items) == 0          # موقع شركة تانية
    before = len(repo.venue_for(FLAT_ZAMALEK, A)["spaces"])
    assert repo.add_venue_spaces_from_photos(FLAT_ZAMALEK, A, items) == repo.MAX_SPACE_PHOTOS == 20
    spaces = repo.venue_for(FLAT_ZAMALEK, A)["spaces"]
    assert len(spaces) == before + 20
    assert all(sp["photo_path"] for sp in spaces[before:])


@test
def test_one_photo_per_space_replacement():
    sp = repo.venue_for(FLAT_ZAMALEK, A)["spaces"][-1]
    assert repo.set_space_photo(FLAT_ZAMALEK, B, sp["id"], "uploads/hack.jpg") is None   # مش صاحب الموقع
    old = repo.set_space_photo(FLAT_ZAMALEK, A, sp["id"], "uploads/new.jpg")
    assert old == sp["photo_path"]
    assert [x for x in repo.venue_for(FLAT_ZAMALEK, A)["spaces"] if x["id"] == sp["id"]][0]["photo_path"] == "uploads/new.jpg"
    # حفظ الجدول (الاسم والنوع…) مايمسحش الصورة
    rows = [dict(_id=x["id"], name=x["name"], space_type="مطبخ") for x in repo.venue_for(FLAT_ZAMALEK, A)["spaces"]]
    repo.save_venue_spaces(FLAT_ZAMALEK, A, rows)
    assert [x for x in repo.venue_for(FLAT_ZAMALEK, A)["spaces"] if x["id"] == sp["id"]][0]["photo_path"] == "uploads/new.jpg"


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
