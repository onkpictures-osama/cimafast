"""P9 خزانة المواهب — قواعد البيانات اللي الشاشة بتعتمد عليها.

    venv/bin/python tests/test_actors.py

بيقفل: الظهور في البحث، فتح الحقول الحساسة بالترشيح لشركة واحدة بس، مين
يعدّل البروفايل، ترشيح → تعاقد في صف واحد، ورفض تعاقد شخصية متعاقد لها حد
تاني. وكمان إن سكريبت البيانات التجريبية مفيهوش أي اسم حقيقي.

قاعدة بيانات مؤقتة — عمرها ما بتلمس الإنتاج.
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_TMP = tempfile.mkdtemp(prefix="cimafast-actors-")
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


def _company(name):
    database.run_query("INSERT INTO companies (name) VALUES (?)", (name,))
    return database.fetch_all("SELECT MAX(id) AS id FROM companies")[0]["id"]


def _project(company_id, name="مشروع"):
    database.run_query("INSERT INTO projects (name, project_type, company_id) VALUES (?, 'فيلم', ?)",
                       (name, company_id))
    return database.fetch_all("SELECT MAX(id) AS id FROM projects")[0]["id"]


def _actor(name, owner=None, **extra):
    values = {"full_name": name, "discoverable": 1, "contact_phone": "000-TEST"}
    values.update(extra)
    return repo.add_actor(values, owner_company_id=owner, created_by="test")


A = _company("شركة أ")
B = _company("شركة ب")
PA = _project(A, "فيلم أ")
PB = _project(B, "فيلم ب")
CHAR_A = repo.add_character(PA, "سلمى", "بطل", "إنسان", "أنثى", "")
CHAR_A2 = repo.add_character(PA, "سامي", "مساعد", "إنسان", "ذكر", "")


@test
def test_actor_without_photo_or_contact_is_still_searchable():
    # كان بيختفي من القايمة وكأنه اتمسح لو اتضاف من غير صورة/تواصل
    aid = repo.add_actor({"full_name": "بروفايل عام بس", "discoverable": 1}, owner_company_id=A)
    assert aid in {a["id"] for a in repo.actors_directory()}


@test
def test_hidden_actor_leaves_search_but_owner_still_sees_it():
    aid = _actor("مخفي", owner=A, discoverable=0)
    assert aid not in {a["id"] for a in repo.actors_directory()}
    assert aid in {a["id"] for a in repo.actors_owned_by_company(A)}
    assert aid not in {a["id"] for a in repo.actors_owned_by_company(B)}


@test
def test_shortlist_unlocks_sensitive_fields_for_that_company_only():
    aid = _actor("مرشح")
    assert not repo.actor_unlocked_for_company(aid, A)
    repo.cast_actor(aid, PA, CHAR_A, "shortlisted", "", "tester")
    assert repo.actor_unlocked_for_company(aid, A)
    assert not repo.actor_unlocked_for_company(aid, B), "ترشيح شركة أ فتح البيانات لشركة ب"


@test
def test_owner_company_sees_its_own_actor_details():
    aid = _actor("بتاع أ", owner=A)
    assert repo.actor_unlocked_for_company(aid, A)
    assert not repo.actor_unlocked_for_company(aid, B)


@test
def test_shortlist_then_cast_is_one_row_and_cast_is_not_downgraded():
    aid = _actor("تعاقد")
    repo.cast_actor(aid, PA, CHAR_A2, "shortlisted", "", "tester")
    repo.cast_actor(aid, PA, CHAR_A2, "cast", "", "tester")
    repo.cast_actor(aid, PA, CHAR_A2, "shortlisted", "", "tester")
    rows = repo.castings_of_actor_in_project(aid, PA)
    assert len(rows) == 1 and rows[0]["status"] == "cast", rows
    assert repo.casting_for_character(CHAR_A2)["actor_id"] == aid


@test
def test_cannot_cast_a_character_already_cast_with_someone_else():
    other = _actor("تاني")
    try:
        repo.cast_actor(other, PA, CHAR_A2, "cast", "", "tester")
    except repo.AlreadyCastError:
        pass
    else:
        raise AssertionError("اتعاقد على شخصية متعاقد لها حد تاني")
    # الترشيح لسه مسموح (ممكن تبقى بديل)
    repo.cast_actor(other, PA, CHAR_A2, "shortlisted", "", "tester")
    assert repo.casting_for_character(CHAR_A2)["status"] == "cast"


@test
def test_casting_needs_the_character_to_belong_to_the_project():
    aid = _actor("مشروع غلط")
    repo.cast_actor(aid, PB, CHAR_A, "shortlisted", "", "tester")   # CHAR_A تبع PA مش PB
    assert not repo.castings_of_actor_in_project(aid, PB)
    assert not repo.actor_unlocked_for_company(aid, B)


@test
def test_remove_casting_is_scoped_to_the_project():
    aid = _actor("إلغاء")
    repo.cast_actor(aid, PA, CHAR_A, "shortlisted", "", "tester")
    row = repo.castings_of_actor_in_project(aid, PA)[0]
    repo.remove_casting(PB, row["id"])                  # مشروع شركة تانية: مايمسحش
    assert repo.castings_of_actor_in_project(aid, PA)
    repo.remove_casting(PA, row["id"])
    assert not repo.castings_of_actor_in_project(aid, PA)


@test
def test_only_owner_company_or_operator_can_edit():
    aid = _actor("تعديل", owner=A)
    actor = repo.actor_by_id(aid)
    assert repo.can_edit_actor(actor, A, "producer")
    assert not repo.can_edit_actor(actor, A, "viewer")
    assert not repo.can_edit_actor(actor, B, "admin")
    assert repo.can_edit_actor(actor, B, "operator")
    seeded = repo.actor_by_id(_actor("من الإدارة", owner=None))
    assert not repo.can_edit_actor(seeded, A, "admin")
    # والفحص جوه الجملة نفسها كمان: شركة ب مابتعرفش تعدّل حتى لو نادت مباشرة
    values = {c: actor.get(c) for c in repo._ACTOR_COLUMNS}
    values["full_name"] = "اتغيّر"
    repo.update_actor(aid, values, B, "admin")
    assert repo.actor_by_id(aid)["full_name"] == "تعديل"
    repo.update_actor(aid, values, A, "producer")
    assert repo.actor_by_id(aid)["full_name"] == "اتغيّر"


@test
def test_photo_update_stamps_the_date():
    aid = _actor("صورة")
    old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=200)).isoformat(timespec="seconds")
    repo.set_actor_photo(aid, "uploads/actors/x.png", updated_at=old)
    assert repo.actor_by_id(aid)["photo_updated_at"] == old
    repo.set_actor_photo(aid, "uploads/actors/y.png")
    assert repo.actor_by_id(aid)["photo_updated_at"][:10] == dt.date.today().isoformat()


@test
def test_viewer_cannot_add_or_cast():
    aid = _actor("مشاهد")
    with permissions.acting_as("viewer"):
        for fn, args in ((repo.add_actor, ({"full_name": "x"},)),
                         (repo.cast_actor, (aid, PA, CHAR_A, "shortlisted", "", "v"))):
            try:
                fn(*args)
            except permissions.Denied:
                continue
            raise AssertionError(f"{fn.__name__} اشتغلت لمشاهد بس")


@test
def test_demo_seed_holds_only_fictional_people():
    """الحد المحسوم في ACTOR-CASTING-PLAN.md: مفيش ممثل حقيقي في بيانات العرض
    الغنية، وأرقام التواصل التجريبية مش أرقام موبايل ممكن تكون حقيقية."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import seed_demo_actors as seed
    real = ["تامر حسني", "حسين فهمي", "أحمد زاهر", "إبراهيم سمير", "ابرام سمير", "سارة درزاوي",
            "أحمد الرافعي", "أحمد فؤاد سليم", "كريم عفيفي"]
    for spec in seed.DEMO_ACTORS:
        assert spec["is_demo"] == 1
        assert "تجريبي" in spec["bio"]
        for name in real:
            assert name not in spec["full_name"] and name not in (spec["stage_name"] or ""), name
        assert spec["contact_phone"].startswith("000"), spec["contact_phone"]
        assert spec["contact_email"].endswith("@example.com")


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
