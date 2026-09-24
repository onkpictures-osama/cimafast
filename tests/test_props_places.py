"""الإكسسوار تابع للأماكن — اتفاق المالك 2026-09-24.

    venv/bin/python tests/test_props_places.py

بيقفل: المرصوص تابع للمكان/الديكور، اللي في الإيد تابع للشخصية، واللي
بيتلبس بيتنقل لغيار الشخصية (قطعة "إكسسوار") ويتمسح من الإكسسوار. الحفظ
بيحافظ على الـ id (روابط المشاهد بتفضل)، الاقتراح بييجي من المشاهد، ومكان
اتمسح بيرجّع قطعه لـ "محتاج مكان" بدل ما تختفي. وكل ده جوه المشروع بس.

قاعدة بيانات مؤقتة — عمرها ما بتلمس الإنتاج.
"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_TMP = tempfile.mkdtemp(prefix="cimafast-props-")
os.environ["STUDIO_DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ.pop("DATABASE_URL", None)

import database  # noqa: E402

database.init_db()

import links  # noqa: E402
import repo  # noqa: E402
from database import fetch_all, run_query  # noqa: E402

_results = []


def test(fn):
    _results.append(fn)
    return fn


def _project(name):
    run_query("INSERT INTO companies (name) VALUES (?)", (name,))
    cid = fetch_all("SELECT MAX(id) AS id FROM companies")[0]["id"]
    run_query("INSERT INTO projects (name, project_type, company_id) VALUES (?, 'فيلم', ?)", (name, cid))
    return fetch_all("SELECT MAX(id) AS id FROM projects")[0]["id"]


P = _project("فيلم")
OTHER = _project("تاني")
FLAT = repo.add_location(P, "شقة نادية", "", None, None)
BEDROOM = repo.add_location(P, "أوضة النوم", "", FLAT, None)
CAFE = repo.add_location(P, "كافيه البورصة", "", None, None)
FOREIGN_LOC = repo.add_location(OTHER, "مكان تاني", "", None, None)
NADIA = repo.add_character(P, "نادية", "بطل", "إنسان", "أنثى", "")
HASSAN = repo.add_character(P, "حسن", "مساعد", "إنسان", "ذكر", "")
run_query("INSERT INTO location_variants (location_id, variant_name) VALUES (?, 'الشكل الأساسي')", (BEDROOM,))
V_BED = fetch_all("SELECT MAX(id) AS id FROM location_variants")[0]["id"]
run_query("INSERT INTO location_variants (location_id, variant_name) VALUES (?, 'الشكل الأساسي')", (CAFE,))
V_CAFE = fetch_all("SELECT MAX(id) AS id FROM location_variants")[0]["id"]
S1 = repo.add_scene(P, None, 1, "داخلي", "ليل", None, V_BED, "")
S2 = repo.add_scene(P, None, 2, "داخلي", "نهار", None, V_BED, "")
S3 = repo.add_scene(P, None, 3, "داخلي", "نهار", None, V_CAFE, "")


def _prop(name, char=None):
    run_query("INSERT INTO props (project_id, name, character_id) VALUES (?, ?, ?)", (P, name, char))
    return fetch_all("SELECT MAX(id) AS id FROM props")[0]["id"]


CLOCK = _prop("ساعة منبه")          # على الكومودينو - ظهرت في مشهدين في أوضة النوم
GUN = _prop("مسدس", HASSAN)         # في إيد حسن
NECKLACE = _prop("عقد دهب", NADIA)  # بيتلبس
CUP = _prop("فنجان")                # مشهد في الكافيه
for sid, pid in ((S1, CLOCK), (S2, CLOCK), (S3, CUP), (S1, NECKLACE)):
    repo.link_prop_to_scene(P, sid, pid)


@test
def test_tab_order_and_phases():
    assert list(links.TABS)[:4] == ["import", "locations", "props", "characters"]
    assert links.PHASES["prod"] == ["schedule"] and links.PHASES["post"] == ["post"]
    # الفريق والإعدادات صفحات من الشريط الجانبي، مش تبويبات في أي مرحلة
    assert not any(s in p for p in links.PHASES.values() for s in ("team", "settings"))
    assert "team" in links.TABS and "settings" in links.TABS          # الروابط القديمة لسه بتتقري
    assert links.phase_of("schedule") == "prod" and links.phase_of("props") == "pre"
    assert links.phase_of("post") == "post"
    assert all(s in links.TABS for p in links.PHASES.values() for s in p)


@test
def test_old_props_start_unplaced_or_in_hand():
    g = repo.props_grouped(P)
    assert {p["id"] for p in g["unplaced"]} == {CLOCK, CUP}
    assert {p["id"] for p in g["by_character"][HASSAN]} == {GUN}


@test
def test_location_suggestion_comes_from_the_scenes():
    s = repo.suggest_prop_location(P)
    assert s[CLOCK] == (BEDROOM, 2, 2) and s[CUP][0] == CAFE
    assert GUN not in s
    assert repo.looks_worn("عقد دهب") and repo.looks_worn("نضارة شمس") and not repo.looks_worn("ساعة منبه")


@test
def test_place_props_is_scoped_to_the_project():
    n = repo.place_props(P, [(CLOCK, BEDROOM, None), (CUP, FOREIGN_LOC, None)])
    assert n == 1, n                                           # مكان مشروع تاني اتجاهل
    g = repo.props_grouped(P)
    assert [p["id"] for p in g["by_location"][BEDROOM]] == [CLOCK]
    assert CUP in {p["id"] for p in g["unplaced"]}


@test
def test_saving_a_location_table_keeps_ids_and_scene_links():
    rows = [{"_id": CLOCK, "name": "ساعة منبه نحاس", "quantity": 2, "cost": 150, "status": "اتجاب"},
            {"_id": None, "name": "أباجورة", "source": "إيجار", "cost": float("nan")},
            {"_id": None, "name": "   "}]
    assert repo.save_props_for(P, rows, location_id=BEDROOM) == 2
    items = {p["name"]: p for p in repo.props_grouped(P)["by_location"][BEDROOM]}
    assert items["ساعة منبه نحاس"]["id"] == CLOCK and items["ساعة منبه نحاس"]["quantity"] == 2
    assert items["أباجورة"]["cost"] is None and items["أباجورة"]["source"] == "إيجار"
    assert repo.prop_scene_counts(P)[CLOCK] == 2                  # روابط المشاهد فضلت
    # شيل صف من الجدول = مسح
    repo.save_props_for(P, [rows[0]], location_id=BEDROOM)
    assert [p["name"] for p in repo.props_grouped(P)["by_location"][BEDROOM]] == ["ساعة منبه نحاس"]
    assert repo.save_props_for(P, rows, location_id=FOREIGN_LOC) == 0
    s = repo.props_summary(P)
    assert s["cost"] == 300, s


@test
def test_worn_item_moves_to_the_characters_change():
    look = repo.move_prop_to_wardrobe(P, NECKLACE, NADIA)
    assert look
    items = repo.items_of_change(P, look)
    assert [(i["item_name"], i["category"]) for i in items] == [("عقد دهب", "إكسسوار")]
    assert not fetch_all("SELECT 1 FROM props WHERE id=?", (NECKLACE,))
    assert repo.move_prop_to_wardrobe(P, CUP, 999999) is None


@test
def test_deleted_location_returns_its_props_to_unplaced():
    tmp = repo.add_location(P, "مكان مؤقت", "", None, None)
    repo.save_props_for(P, [{"name": "كرسي"}], location_id=tmp)
    repo.delete_location(P, tmp)
    assert "كرسي" in {p["name"] for p in repo.props_grouped(P)["unplaced"]}


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
