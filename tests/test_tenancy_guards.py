"""عزل الشركات — الحراسات اللي لو وقعت، بيانات شركة بتظهر عند شركة تانية.

    venv/bin/python tests/test_tenancy_guards.py

المالك بلّغ إن "بيانات المستخدمين بتتلخبط". العزل نفسه متغطّى في
test_accounts.py؛ الملف ده بيقفل الطرق اللي كانت لسه سايبة العزل يتكسر:

1. مفيش دالة في repo بترجّع "كل المشاريع" — أي قايمة بتعدي على شركات المستخدم.
2. تبنّي المشاريع اليتيمة نقل مرة واحدة، مش قاعدة شغالة للأبد بتدّي أقدم شركة
   أي مشروع من غير company_id.
3. مسح مشروع بيتأكد إن المشروع تبع شركة المستخدم، مش بس إنه أدمن في شركة ما.
4. أي كتابة على مشهد/لقطة/شخصية/مكان/إكسسوار بتفلتر بالمشروع في الـ SQL نفسه،
   مش بس لأن الشاشة جابت الرقم من قايمة مفلترة.

قاعدة بيانات مؤقتة — عمرها ما بتلمس الإنتاج.
"""
from __future__ import annotations

import ast
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_TMP = tempfile.mkdtemp(prefix="cimafast-tenancy-")
os.environ["STUDIO_DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ.pop("DATABASE_URL", None)

import accounts  # noqa: E402
import auth  # noqa: E402
import database  # noqa: E402
import permissions  # noqa: E402
import repo  # noqa: E402

database.init_db()
_results = []

LEGACY = {"melzayat": auth.hash_password("owner-pass-123", iterations=1000),
          "producer": auth.hash_password("producer-pass-1", iterations=1000)}


def test(fn):
    _results.append(fn)
    return fn


def _project(name, company_id=None):
    database.run_query("INSERT INTO projects (name, project_type, company_id) VALUES (?, 'فيلم', ?)",
                       (name, company_id))
    return database.fetch_all("SELECT MAX(id) AS id FROM projects")[0]["id"]


def _raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    raise AssertionError(f"{getattr(fn, '__name__', fn)} did not raise {exc.__name__}")


# --- 1. مفيش قايمة مشاريع غير مفلترة -----------------------------------------------

@test
def test_repo_has_no_unscoped_project_listing():
    """أي دالة بترجّع كل المشاريع هي تسريب مستني شاشة تنده عليه.

    التلاتة دول كانوا موجودين وميتين: projects() وall_projects_newest_first()
    وadd_project() (بتعمل مشروع من غير company_id — يعني يتيم من ساعة ما اتولد).
    """
    for gone in ("projects", "all_projects_newest_first", "add_project"):
        assert not hasattr(repo, gone), f"repo.{gone} رجع تاني — ده مشروع من غير فلتر شركة"


@test
def test_no_select_star_from_projects_without_a_filter():
    """حارس على نص repo.py نفسه: كل SELECT من projects لازم يكون ليه WHERE."""
    with open(os.path.join(ROOT, "repo.py"), encoding="utf-8") as fh:
        for i, line in enumerate(fh, start=1):
            code = line.split("#")[0]
            if "FROM projects" in code and "WHERE" not in code:
                raise AssertionError(f"repo.py:{i} بيقرا من projects من غير WHERE: {line.strip()}")


# --- 1ب. مفيش كتابة على بيانات المشروع من غير project_id --------------------------

# الجداول اللي كل صف فيها تبع مشروع واحد. أي UPDATE/DELETE عليها لازم يربط
# المشروع في شرط WHERE — يا بعمود project_id على طول، يا بـ subquery على أبوه
# (اللقطات عن طريق scenes، المظاهر عن طريق characters، وهكذا).
SCOPED_TABLES = {
    "scenes", "shots", "characters", "character_looks",
    "locations", "location_variants", "props", "episodes",
    "wardrobe_items",          # P10: عن طريق الغيار (character_looks → characters)
}
# جداول الربط: مالهاش بيانات خاصة بيها، بس ربط صف بصف من مشروع تاني هو نفسه
# تسريب. هنا حتى الـ INSERT لازم يتأكد إن الطرفين في المشروع.
LINK_TABLES = {"scene_characters", "scene_props", "shot_characters", "shot_props",
               "scene_character_looks",   # P10: مشهد × شخصية × غيار
               "location_venue_booking"}  # مكتبة المواقع: مكان في المشروع × موقع حقيقي

_UPDATE_DELETE_RE = re.compile(r"\b(?:UPDATE|DELETE\s+FROM)\s+([a-z_]+)", re.IGNORECASE)
_INSERT_RE = re.compile(r"\bINSERT\s+(?:OR\s+IGNORE\s+)?INTO\s+([a-z_]+)", re.IGNORECASE)


def _sql_literals(path):
    """كل نص مكتوب في الملف مع رقم سطره. Python بيلزق النصوص المتجاورة قبل
    التحليل، فاستعلام متقسّم على كذا سطر بيوصل هنا قطعة واحدة."""
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value


@test
def test_no_write_to_project_data_without_a_project_filter():
    """الحارس اللي التذكرة دي اتكتبت عشانه.

    قبل كده update_scene/delete_shot/delete_character... كانوا بيفلتروا بـ id
    لوحده. العزل كان قايم على إن كل شاشة بتجيب الـ id من استعلام مفلتر
    بالمشروع — صح النهارده، بس مفيش حاجة كانت بتمنع شاشة جديدة تاخد id من
    الطلب. دلوقتي الشرط في الـ SQL نفسه، والحارس ده بيمنع رجوعه.
    """
    for lineno, sql in _sql_literals(os.path.join(ROOT, "repo.py")):
        hits = [(m.group(1).lower(), "UPDATE/DELETE") for m in _UPDATE_DELETE_RE.finditer(sql)]
        hits += [(m.group(1).lower(), "INSERT") for m in _INSERT_RE.finditer(sql)]
        for table, verb in hits:
            guarded = table in LINK_TABLES or (verb == "UPDATE/DELETE" and table in SCOPED_TABLES)
            if guarded and "project_id" not in sql:
                raise AssertionError(
                    f"repo.py:{lineno} {verb} على {table} من غير project_id في الشرط: "
                    f"{' '.join(sql.split())[:110]}")


# --- 2. المشاريع اليتيمة ----------------------------------------------------------

@test
def test_legacy_orphans_are_adopted_once_while_there_is_one_company():
    old = _project("مشروع قديم")                       # اتعمل قبل ما يبقى فيه شركات
    done = accounts.migrate_accounts(LEGACY, "الشركة الافتراضية")
    assert done["company_created"] and done["projects_linked"] == 1
    company_id = accounts.companies_for("melzayat")[0]["id"]
    assert repo.project(old)["company_id"] == company_id


@test
def test_an_orphan_is_never_handed_to_the_oldest_company_once_two_exist():
    """الباج اللي الملف ده اتكتب عشانه.

    التبنّي كان بيتنفّذ في كل تشغيل للخدمة. مع شركتين، أي مشروع بـ company_id
    فاضي (باج، صف راجع من باك أب، استيراد غلط) كان بيروح لأقدم شركة — يعني
    بيظهر في قايمة ناس مالهمش دعوة بيه. دلوقتي بيتساب من غير شركة، ومشروع من
    غير شركة مش بيبان لحد.
    """
    accounts.create_company("melzayat", "شركة تانية", "admin_b")
    assert len(accounts.companies_for("melzayat")) == 2

    orphan = _project("مشروع يتيم")                    # company_id = NULL
    done = accounts.migrate_accounts(LEGACY, "الشركة الافتراضية")

    assert done["projects_linked"] == 0, "اتبنى مشروع يتيم وفيه أكتر من شركة"
    assert done.get("orphans_left") == 1
    assert repo.project(orphan)["company_id"] is None
    # والأهم: محدش بيشوفه
    for username in ("melzayat", "producer", "admin_b"):
        ids = [p["id"] for p in accounts.projects_for(username)]
        assert orphan not in ids, f"{username} شاف مشروع مش تبع شركته"


@test
def test_projects_for_never_matches_a_null_company():
    """الفشل الآمن اللي اللي فوق بيعتمد عليه: NULL مابتطابقش IN (...)."""
    orphan = _project("يتيم تاني")
    everybody = {p["id"] for u in ("melzayat", "producer", "admin_b")
                 for p in accounts.projects_for(u)}
    assert orphan not in everybody


# --- 3. مسح مشروع -----------------------------------------------------------------

@test
def test_deleting_another_companys_project_is_refused():
    """أدمن في شركته مش أدمن على المنصة.

    repo.delete_project كان بيفحص الصلاحية بس (أدمن؟) من غير ما يفحص المشروع
    تبع مين، فرقم مشروع من شركة تانية كان بيتمسح بصلاحية أدمن شركتك انت.
    """
    b_id = next(c["id"] for c in accounts.companies_for("admin_b") if c["name"] == "شركة تانية")
    theirs = _project("مشروع شركة ب", b_id)

    # producer عضو في الشركة الافتراضية بس — مالوش دعوة بمشروع شركة ب
    _raises(accounts.AccessDenied, accounts.delete_project, "producer", theirs)
    assert repo.project(theirs) is not None, "المشروع اتمسح رغم الرفض"


@test
def test_a_viewer_cannot_delete_a_project_in_their_own_company():
    a_id = accounts.companies_for("producer")[0]["id"]
    mine = _project("مشروع شركتي", a_id)
    accounts.add_member("melzayat", a_id, "watcher", role="viewer")
    _raises(permissions.Denied, accounts.delete_project, "watcher", mine)
    assert repo.project(mine) is not None


@test
def test_an_admin_deletes_their_own_companys_project():
    a_id = accounts.companies_for("melzayat")[0]["id"]
    mine = _project("مشروع للمسح", a_id)
    accounts.delete_project("melzayat", mine)
    assert repo.project(mine) is None


# --- 3ب. الكتابة برقم مشروع غلط مابتعملش حاجة ---------------------------------------

def _scene(pid, number=1):
    database.run_query("INSERT INTO scenes (project_id, scene_number) VALUES (?, ?)", (pid, number))
    return database.fetch_all("SELECT MAX(id) AS id FROM scenes")[0]["id"]


def _character(pid, name="شخصية"):
    database.run_query("INSERT INTO characters (project_id, name) VALUES (?, ?)", (pid, name))
    return database.fetch_all("SELECT MAX(id) AS id FROM characters")[0]["id"]


@test
def test_a_write_with_the_wrong_project_id_changes_nothing():
    """الدفاع في العمق: حتى لو شاشة بعتت رقم مشهد من مشروع تاني، مفيش صف بيتلمس."""
    mine, theirs = _project("مشروعي"), _project("مشروعهم")
    sid = _scene(theirs, 7)

    repo.update_scene(mine, 99, "INT", "نهار", "", None, "اتغيّر", sid)
    row = database.fetch_all("SELECT scene_number, notes FROM scenes WHERE id=?", (sid,))[0]
    assert row["scene_number"] == 7 and not row["notes"], "مشهد مشروع تاني اتعدّل"

    repo.delete_scene(mine, sid)
    assert database.fetch_all("SELECT id FROM scenes WHERE id=?", (sid,)), "مشهد مشروع تاني اتمسح"

    # وبرقم المشروع الصح بيشتغل عادي — الحارس مش بيكسر الاستخدام الطبيعي
    repo.delete_scene(theirs, sid)
    assert not database.fetch_all("SELECT id FROM scenes WHERE id=?", (sid,))


@test
def test_a_character_is_never_linked_to_a_scene_in_another_project():
    mine, theirs = _project("ربط - مشروعي"), _project("ربط - مشروعهم")
    sid = _scene(mine, 1)
    outsider = _character(theirs, "شخصية شركة تانية")
    insider = _character(mine, "شخصية بتاعتي")

    repo.link_character_to_scene(mine, sid, outsider)
    assert not database.fetch_all("SELECT 1 FROM scene_characters WHERE scene_id=? AND character_id=?",
                                  (sid, outsider)), "شخصية من مشروع تاني اتربطت بمشهد"

    repo.link_character_to_scene(mine, sid, insider)
    assert database.fetch_all("SELECT 1 FROM scene_characters WHERE scene_id=? AND character_id=?",
                              (sid, insider)), "الربط الطبيعي وقع"


@test
def test_deleting_a_character_needs_its_own_project():
    mine, theirs = _project("حذف - مشروعي"), _project("حذف - مشروعهم")
    cid = _character(theirs, "بطل مشروعهم")
    repo.delete_character(mine, cid)
    assert database.fetch_all("SELECT id FROM characters WHERE id=?", (cid,)), "شخصية مشروع تاني اتمسحت"
    repo.delete_character(theirs, cid)
    assert not database.fetch_all("SELECT id FROM characters WHERE id=?", (cid,))


# --- 4. الفهرس اللي العزل بيقف عليه -------------------------------------------------

@test
def test_company_id_is_indexed():
    """كل قراءة مشاريع بتفلتر بالشركة، فلازم يكون عليها فهرس."""
    rows = database.fetch_all(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='projects'")
    assert any(r["name"] == "idx_projects_company" for r in rows), \
        f"مفيش فهرس على projects.company_id: {[r['name'] for r in rows]}"


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
