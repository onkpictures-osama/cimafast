"""P5 المظاهر والراكور — كل شخصية ليها مظهر أساسي واحد بالظبط.

    venv/bin/python tests/test_looks.py

البلاغ: شخصية مضافة باليد كانت بتتعمل من غير أي مظهر، فمكانتش بتظهر في اختيار
شخصيات اللقطة خالص. الاختبارات دي بتقفل الطرق اللي ممكن ترجّع الحالة دي:
الإضافة باليد، الـ backfill للبيانات القديمة، ومسح آخر مظهر.

قاعدة بيانات مؤقتة — عمرها ما بتلمس الإنتاج.
"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_TMP = tempfile.mkdtemp(prefix="cimafast-looks-")
os.environ["STUDIO_DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ.pop("DATABASE_URL", None)

import database  # noqa: E402
import permissions  # noqa: E402
import repo  # noqa: E402

database.init_db()
_results = []


def test(fn):
    _results.append(fn)
    return fn


def _project(name="مشروع اختبار"):
    database.run_query("INSERT INTO projects (name, project_type) VALUES (?, 'فيلم')", (name,))
    return database.fetch_all("SELECT MAX(id) AS id FROM projects")[0]["id"]


def _looks(char_id):
    return repo.looks_of_character(char_id)


def _defaults(char_id):
    return [lk for lk in _looks(char_id) if lk["is_default"]]


def _no_character_without_exactly_one_default():
    rows = database.fetch_all(
        "SELECT c.id, (SELECT COUNT(*) FROM character_looks l WHERE l.character_id=c.id "
        "AND COALESCE(l.is_default,0)=1) AS d FROM characters c")
    bad = [r["id"] for r in rows if r["d"] != 1]
    assert not bad, f"شخصيات من غير مظهر أساسي واحد بالظبط: {bad}"


P = _project()


@test
def test_hand_added_character_gets_one_default_look():
    cid = repo.add_character(P, "سميحة", "بطل", "إنسان", "أنثى", "")
    looks = _looks(cid)
    assert len(looks) == 1, looks
    assert looks[0]["is_default"] == 1
    assert looks[0]["look_name"] == database.DEFAULT_LOOK_NAME
    # ودي كانت المشكلة نفسها: الشخصية لازم تظهر في اختيار شخصيات اللقطة
    labels = [r["label"] for r in repo.look_labels_of_project(P)]
    assert any(lbl.startswith("سميحة") for lbl in labels), labels


@test
def test_backfill_fixes_old_rows_and_is_idempotent():
    # بيانات قديمة: شخصية من غير مظهر، وشخصية ليها مظهرين ولا واحد أساسي،
    # وشخصية ليها مظهرين الاتنين أساسي
    database.run_query("INSERT INTO characters (project_id, name) VALUES (?, ?)", (P, "من غير مظهر"))
    bare = database.fetch_all("SELECT MAX(id) AS id FROM characters")[0]["id"]
    database.run_query("INSERT INTO characters (project_id, name) VALUES (?, ?)", (P, "من غير أساسي"))
    no_def = database.fetch_all("SELECT MAX(id) AS id FROM characters")[0]["id"]
    for n in ("أ", "ب"):
        database.run_query("INSERT INTO character_looks (character_id, look_name, is_default) VALUES (?,?,0)", (no_def, n))
    database.run_query("INSERT INTO characters (project_id, name) VALUES (?, ?)", (P, "أساسيين"))
    two_def = database.fetch_all("SELECT MAX(id) AS id FROM characters")[0]["id"]
    for n in ("أ", "ب"):
        database.run_query("INSERT INTO character_looks (character_id, look_name, is_default) VALUES (?,?,1)", (two_def, n))

    database.init_db()                      # نفس اللي بيحصل مع كل تشغيل
    _no_character_without_exactly_one_default()
    assert len(_looks(bare)) == 1
    assert _defaults(no_def)[0]["look_name"] == "أ"      # الأقدم هو اللي بقى أساسي
    assert _defaults(two_def)[0]["look_name"] == "أ"

    before = database.fetch_all("SELECT COUNT(*) AS n FROM character_looks")[0]["n"]
    database.init_db()                      # تاني مرة: ولا صف زيادة
    after = database.fetch_all("SELECT COUNT(*) AS n FROM character_looks")[0]["n"]
    assert before == after, (before, after)


@test
def test_last_look_cannot_be_deleted():
    cid = repo.add_character(P, "حسين", "بطل", "إنسان", "ذكر", "")
    only = _looks(cid)[0]["id"]
    try:
        repo.delete_character_look(P, only)
    except repo.LastLookError:
        pass
    else:
        raise AssertionError("آخر مظهر اتمسح")
    assert len(_looks(cid)) == 1
    # والاستثناء من نوع IntegrityError، فـ ui.guarded_delete بيمسكه ومبيوقّعش الصفحة
    assert issubclass(repo.LastLookError, database.IntegrityError)


@test
def test_deleting_the_default_promotes_another():
    cid = repo.add_character(P, "مريم", "بطل", "إنسان", "أنثى", "")
    first = _looks(cid)[0]["id"]
    second = repo.add_character_look(cid, "بالنضارة", "", "طبيعي", "", "", "", None)
    assert _defaults(cid)[0]["id"] == first, "المظهر الجديد مايبقاش أساسي لوحده"
    repo.delete_character_look(P, first)
    assert [lk["id"] for lk in _defaults(cid)] == [second]
    _no_character_without_exactly_one_default()


@test
def test_set_default_look_switches_and_stays_single():
    cid = repo.add_character(P, "يونس", "مساعد", "إنسان", "ذكر", "")
    first = _looks(cid)[0]["id"]
    after_surgery = repo.add_character_look(cid, "بعد العملية", "", "آثار إصابة", "", "", "", None)
    repo.set_default_look(P, after_surgery)
    assert [lk["id"] for lk in _defaults(cid)] == [after_surgery]
    assert _looks(cid)[0]["id"] == after_surgery, "الأساسي لازم يبقى أول القايمة"
    repo.set_default_look(P, first)
    assert [lk["id"] for lk in _defaults(cid)] == [first]


@test
def test_another_project_cannot_touch_these_looks():
    other = _project("مشروع تاني")
    cid = repo.add_character(P, "نادين", "بطل", "إنسان", "أنثى", "")
    first = _looks(cid)[0]["id"]
    second = repo.add_character_look(cid, "تاني", "", "طبيعي", "", "", "", None)
    repo.set_default_look(other, second)            # رقم مشروع غلط → ولا صف يتغير
    assert [lk["id"] for lk in _defaults(cid)] == [first]
    repo.delete_character_look(other, second)
    assert len(_looks(cid)) == 2


@test
def test_a_viewer_cannot_change_looks():
    cid = repo.add_character(P, "مشاهد", "كومبارس", "إنسان", "ذكر", "")
    second = repo.add_character_look(cid, "تاني", "", "طبيعي", "", "", "", None)
    with permissions.acting_as("viewer"):
        for fn, args in ((repo.set_default_look, (P, second)),
                         (repo.delete_character_look, (P, second)),
                         (repo.add_character_look, (cid, "تالت", "", "", "", "", "", None))):
            try:
                fn(*args)
            except permissions.Denied:
                continue
            raise AssertionError(f"{fn.__name__} اشتغلت لمشاهد بس")
    assert len(_looks(cid)) == 2


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
