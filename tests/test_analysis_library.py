"""مكتبة التحليلات — الحفظ، الملف، الاستيراد والدمج، والعزل بين الشركات.

    venv/bin/python tests/test_analysis_library.py

قاعدة بيانات مؤقتة وطابور تحليل مؤقت جنبها — عمرها ما بتلمس الإنتاج.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_TMP = tempfile.mkdtemp(prefix="cimafast-library-")
os.environ["STUDIO_DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ["CIMAFAST_AI_SPOOL"] = os.path.join(_TMP, "ai-jobs")
os.environ.pop("DATABASE_URL", None)

import accounts  # noqa: E402
import analysis_library as lib  # noqa: E402
import audit  # noqa: E402
import auth  # noqa: E402
import database  # noqa: E402
import permissions  # noqa: E402

database.init_db()
_results = []

LEGACY = {"melzayat": auth.hash_password("owner-pass-123", iterations=1000),
          "producer": auth.hash_password("producer-pass-1", iterations=1000)}
accounts.migrate_accounts(LEGACY)
COMPANY_A = accounts.companies_for("producer")[0]["id"]
# شركة تانية بأدمن لوحدها، ومشاهد (viewer) في الشركة الأولى
COMPANY_B, _ = accounts.create_company("melzayat", "شركة تانية", "other_admin")
accounts.add_member("melzayat", COMPANY_A, "watcher", role="viewer")
accounts.add_member("melzayat", COMPANY_A, "dept", role="department")


def _project(name, company_id):
    with permissions.system():
        return database.run_query(
            "INSERT INTO projects (name, project_type, company_id) VALUES (?, 'فيلم', ?)",
            (name, company_id))


WRONG = _project("المشروع الغلط", COMPANY_A)
RIGHT = _project("المشروع الصح", COMPANY_A)
OTHER = _project("مشروع شركة تانية", COMPANY_B)

ANALYSIS = {
    "scenes": [
        {"scene_number": 1, "int_ext": "INT", "day_night": "نهار", "location_name": "شقة حسين",
         "characters": ["حسين", "نادين"], "props": ["فنجان قهوة"], "notes": "حسين: صباح الخير"},
        {"scene_number": 2, "int_ext": "EXT", "day_night": "ليل", "location_name": "الكورنيش",
         "characters": ["السويسي", "نادين"], "props": [], "notes": ""},
        {"scene_number": 3, "int_ext": "INT", "day_night": "ليل", "location_name": "شقه حسين",
         "characters": ["أحمد", "يونس (ابن حسين)"], "props": [], "notes": ""},
    ],
    "warnings": [],
    "meta": {"model": "sonnet", "cost_usd": 0.5},
}


def test(fn):
    _results.append(fn)
    return fn


def _raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc as e:
        return e
    raise AssertionError(f"{getattr(fn, '__name__', fn)} did not raise {exc.__name__}")


def _names(table, project_id):
    return sorted(r["name"] for r in database.fetch_all(
        f"SELECT name FROM {table} WHERE project_id=?", (project_id,)))


def _write_spool_job(jid, project_id, filename, result):
    root = os.environ["CIMAFAST_AI_SPOOL"]
    for d in ("inbox", "status", "outbox", "done"):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    with open(os.path.join(root, "inbox", f"{jid}.json"), "w", encoding="utf-8") as fh:
        json.dump({"job_id": jid, "project_id": project_id, "filename": filename,
                   "created_at": 1790178973.0}, fh, ensure_ascii=False)
    with open(os.path.join(root, "status", f"{jid}.json"), "w", encoding="utf-8") as fh:
        json.dump({"state": "done", "detail": "ok", "heartbeat": 1790179260.0}, fh)
    with open(os.path.join(root, "outbox", f"{jid}.result.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False)


# --- الحفظ التلقائي --------------------------------------------------------------------

@test
def test_completed_job_is_saved_to_the_runners_library():
    """تحليل خلص في الطابور بيتحفظ لوحده باسم اللي شغّله (من حدث "ai") وتبع شركة المشروع."""
    jid = f"{WRONG}-abc123"
    audit.event("ai", target="script_analysis", project_id=WRONG, username="producer",
                company_id=COMPANY_A, detail={"file": "الحلقة الاولى.pdf", "job_id": jid})
    _write_spool_job(jid, WRONG, "الحلقة الاولى.pdf", ANALYSIS)
    # نتيجة فاشلة (صفر مشاهد) ماتتحفظش
    _write_spool_job(f"{WRONG}-empty", WRONG, "فاضي.pdf", {"scenes": [], "warnings": [], "meta": {}})
    added = lib.sync_from_spool()
    assert added == 1, added
    assert lib.sync_from_spool() == 0, "الـ sync التاني المفروض مايكررش"
    rows = lib.list_for("producer")
    assert len(rows) == 1, rows
    r = rows[0]
    assert r["owner_username"] == "producer" and r["company_id"] == COMPANY_A, r
    assert r["script_name"] == "الحلقة الاولى.pdf" and r["source_project_name"] == "المشروع الغلط"
    assert (r["scene_count"], r["character_count"], r["location_count"]) == (3, 5, 3), r
    assert r["job_id"] == jid and r["analysed_at"].startswith("2026-09-2"), r


@test
def test_spool_of_another_database_is_ignored():
    """طابور مش جنب قاعدة البيانات دي (نسخة الإنتاج مثلًا) مابيتقراش — أرقام المشاريع بتتكرر."""
    other = tempfile.mkdtemp(prefix="cimafast-foreign-")
    os.makedirs(os.path.join(other, "ai-jobs", "outbox"))
    assert lib.sync_from_spool(os.path.join(other, "ai-jobs")) == 0


# --- الملف: من المكتبة لمشروع تاني ------------------------------------------------------

def _entry_id():
    return lib.list_for("producer")[0]["id"]


@test
def test_export_file_is_versioned_utf8_json():
    name, data = lib.to_file(lib.get("producer", _entry_id()))
    assert name.endswith(lib.FILE_SUFFIX) and "الحلقة الاولى" in name, name
    text = data.decode("utf-8")
    assert "حسين" in text and "\\u" not in text, "العربي لازم يفضل زي ما هو (ensure_ascii=False)"
    doc = json.loads(text)
    assert doc["format"] == lib.FORMAT and doc["version"] == lib.VERSION
    assert doc["script"]["name"] == "الحلقة الاولى.pdf"
    assert len(doc["analysis"]["scenes"]) == 3


@test
def test_round_trip_export_then_import_into_a_different_project():
    """نزّل الملف، ارفعه في شركة تانية، واستورده في مشروع هناك — نفس المشاهد."""
    _, data = lib.to_file(lib.get("producer", _entry_id()))
    new_id, created = lib.add_upload("other_admin", COMPANY_B, data)
    assert created
    again, created2 = lib.add_upload("other_admin", COMPANY_B, data)
    assert again == new_id and not created2, "نفس الملف مرتين مايتكررش"
    summary = lib.import_into_project("other_admin", new_id, OTHER, lib.MODE_NEW)
    assert summary["scenes_added"] == 3, summary
    nums = sorted(r["scene_number"] for r in database.fetch_all(
        "SELECT scene_number FROM scenes WHERE project_id=?", (OTHER,)))
    assert nums == [1, 2, 3], nums
    assert "نادين" in _names("characters", OTHER)
    rows = database.fetch_all("SELECT summary, username, company_id FROM audit_log "
                              "WHERE action='import_script' AND project_id=?", (OTHER,))
    assert rows and "مكتبة التحليلات" in rows[-1]["summary"] and rows[-1]["username"] == "other_admin", rows


@test
def test_merge_does_not_duplicate_characters_or_locations():
    """مشروع فيه بيانات: «احمد»/«سويسي»/«شقة حسين» موجودين — الدمج يربطهم بدل ما يكررهم."""
    with permissions.system():
        for name in ("احمد", "سويسي", "حسين", "يونس (والد نادين)"):
            database.run_query("INSERT INTO characters (project_id, name, role_type) VALUES (?,?,?)",
                               (RIGHT, name, "غير محدد"))
        database.run_query("INSERT INTO locations (project_id, name, base_description) VALUES (?,?,?)",
                           (RIGHT, "شقة حسين", ""))
        database.run_query("INSERT INTO scenes (project_id, scene_number, int_ext, day_night) "
                           "VALUES (?, 1, 'INT', 'نهار')", (RIGHT,))
    plan = lib.plan_import("producer", _entry_id(), RIGHT, lib.MODE_MERGE)
    pairs = {(a, b) for a, b, _ in plan["char_matches"]}
    assert ("أحمد", "احمد") in pairs and ("السويسي", "سويسي") in pairs, pairs
    # قوسين مختلفين = شخصيتين مختلفتين، حتى لو الاسم واحد
    assert not any(a == "يونس (ابن حسين)" for a, _, _ in plan["char_matches"]), pairs
    assert ("شقه حسين", "شقة حسين") in {(a, b) for a, b, _ in plan["loc_matches"]}
    assert plan["skipped_scenes"] == ["1"], plan["skipped_scenes"]

    summary = lib.import_into_project("producer", _entry_id(), RIGHT, lib.MODE_MERGE)
    assert summary["scenes_added"] == 2, summary
    chars = _names("characters", RIGHT)
    assert chars.count("احمد") == 1 and "أحمد" not in chars, chars
    assert "السويسي" not in chars and "سويسي" in chars, chars
    assert "يونس (ابن حسين)" in chars and "يونس (والد نادين)" in chars, chars
    locs = _names("locations", RIGHT)
    assert locs.count("شقة حسين") == 1 and "شقه حسين" not in locs, locs
    # تاني مرة: كل المشاهد موجودة، مفيش ولا شخصية بتتكرر
    again = lib.import_into_project("producer", _entry_id(), RIGHT, lib.MODE_MERGE)
    assert again["scenes_added"] == 0 and not again["characters_added"], again
    assert _names("characters", RIGHT) == chars


@test
def test_extra_report_sections_survive_the_round_trip():
    """تقرير بيتولد بعد التحليل (زي البناء الدرامي) بيتخزن ويتصدّر مع التحليل."""
    report = {"model": "freytag", "acts": [{"name": "الذروة", "scene": 2}]}
    payload = dict(ANALYSIS, reports={"dramatic_structure": report})
    eid, _ = lib.save(payload, script_name="بتقرير.docx", owner="producer", company_id=COMPANY_A)
    _, data = lib.to_file(lib.get("producer", eid))
    doc = json.loads(data)
    assert doc["analysis"]["reports"]["dramatic_structure"] == report, doc["analysis"].keys()
    parsed = lib.parse_file(data)
    assert parsed["payload"]["reports"]["dramatic_structure"]["acts"][0]["name"] == "الذروة"
    # نفس المشاهد = نفس التحليل: التقرير اتضاف على الصف الموجود مش صف جديد
    assert eid == _entry_id() and len(lib.list_for("producer")) == 1


@test
def test_match_name_rules():
    assert lib.match_name("أحمد", ["احمد"]) == ("احمد", True)
    assert lib.match_name("سيد السويسي", ["السويسي"]) == ("السويسي", False)
    assert lib.match_name("يونس (ابن حسين)", ["يونس (والد نادين)"]) is None
    assert lib.match_name("عجوز", ["عجوز 1", "عجوز 2"]) is None, "أكتر من احتمال: مانخمّنش"
    assert lib.match_name("هالة (والدة حسين)", ["حسين"]) is None


# --- ملفات بايظة ----------------------------------------------------------------------

@test
def test_malformed_files_are_rejected_with_arabic_messages():
    good = json.loads(lib.to_file(lib.get("producer", _entry_id()))[1])
    cases = {
        "empty": b"",
        "not json": b"{not json",
        "latin1": "مشهد".encode("cp1256"),
        "foreign format": json.dumps({"format": "other", "version": 1}).encode(),
        "future version": json.dumps(dict(good, version=lib.VERSION + 1), ensure_ascii=False).encode(),
        "string version": json.dumps(dict(good, version="1"), ensure_ascii=False).encode(),
        "no scenes": json.dumps(dict(good, analysis={"scenes": []}), ensure_ascii=False).encode(),
        "bad scene": json.dumps(dict(good, analysis={"scenes": [{"scene_number": "x"}]}),
                                ensure_ascii=False).encode(),
        "no name": json.dumps(dict(good, script={}), ensure_ascii=False).encode(),
        "list top": b"[]",
    }
    for label, data in cases.items():
        e = _raises(lib.LibraryError, lib.parse_file, data)
        msg = str(e)
        assert msg and any("؀" <= ch <= "ۿ" for ch in msg), f"{label}: {msg!r}"
        assert "Traceback" not in msg and "Error" not in msg, f"{label}: {msg!r}"
    assert "أحدث" in str(_raises(lib.LibraryError, lib.parse_file, cases["future version"]))
    e = _raises(lib.LibraryError, lib.parse_file, json.dumps(
        dict(good, analysis=dict(good["analysis"], reports="x")), ensure_ascii=False).encode())
    assert "التقارير" in str(e)
    # ملف سليم لسه بيعدّي
    assert lib.parse_file(json.dumps(good, ensure_ascii=False).encode())["payload"]["scenes"]


# --- العزل والصلاحيات ------------------------------------------------------------------

@test
def test_company_isolation():
    mine = {r["id"] for r in lib.list_for("producer")}
    theirs = {r["id"] for r in lib.list_for("other_admin")}
    assert mine and theirs and not (mine & theirs), (mine, theirs)
    their_id = next(iter(theirs))
    _raises(lib.LibraryError, lib.get, "producer", their_id)
    _raises(lib.LibraryError, lib.delete, "producer", their_id)
    _raises(lib.LibraryError, lib.plan_import, "producer", _entry_id(), OTHER)
    _raises(lib.LibraryError, lib.import_into_project, "other_admin", _entry_id(), OTHER)
    # زمايل نفس الشركة بيشوفوه، والمشغّل بيشوف الكل
    assert mine <= {r["id"] for r in lib.list_for("dept")}
    assert (mine | theirs) <= {r["id"] for r in lib.list_for("melzayat")}
    assert lib.count_for("producer") == len(mine)


@test
def test_viewer_can_browse_and_download_but_not_import_or_upload():
    rows = lib.list_for("watcher")
    assert rows, "المشاهد المفروض يشوف تحليلات شركته"
    lib.to_file(lib.get("watcher", rows[0]["id"]))
    before = database.fetch_all("SELECT COUNT(*) AS n FROM scenes WHERE project_id=?", (WRONG,))[0]["n"]
    _raises(permissions.Denied, lib.import_into_project, "watcher", rows[0]["id"], WRONG)
    after = database.fetch_all("SELECT COUNT(*) AS n FROM scenes WHERE project_id=?", (WRONG,))[0]["n"]
    assert before == after
    _, data = lib.to_file(lib.get("watcher", rows[0]["id"]))
    _raises(permissions.Denied, lib.add_upload, "watcher", COMPANY_A, data)
    assert not lib.importable_projects("watcher")
    assert {p["id"] for p in lib.importable_projects("producer")} >= {WRONG, RIGHT}


@test
def test_delete_needs_owner_or_admin_and_is_audited():
    eid = _entry_id()
    _raises(lib.LibraryError, lib.delete, "dept", eid)        # زميل مش صاحبه ومش أدمن
    lib.delete("producer", eid)
    assert eid not in {r["id"] for r in lib.list_for("producer")}
    rows = database.fetch_all("SELECT action, username FROM audit_log WHERE entity='analysis_library' "
                              "AND action='library_delete'")
    assert rows and rows[-1]["username"] == "producer", rows


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
