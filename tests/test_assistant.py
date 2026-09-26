"""🤖 مساعد البرنامج: البرومبت، قراءة الرد، الطابور، والسجل (المالك 2026-09-26)."""
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_TMP = tempfile.mkdtemp()
os.environ["STUDIO_DB_PATH"] = os.path.join(_TMP, "t.db")
os.environ["CIMAFAST_ASSISTANT_SPOOL"] = os.path.join(_TMP, "spool")
for d in ("inbox", "status", "outbox"):
    os.makedirs(os.path.join(_TMP, "spool", d))

import database  # noqa: E402

database.init_db()

import assistant  # noqa: E402
import assistant_jobs  # noqa: E402
from database import fetch_all  # noqa: E402

TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


@test
def test_prompt_has_rules_guide_context_and_question():
    p = assistant.build_prompt("إزاي أحط الكاميرا؟", {"الشاشة": "🎥 اللقطات", "المشروع": "فيلم تجربة"},
                               [{"q": "أبدأ منين؟", "a": "من إنشاء مشروع"}])
    assert "ماتخترعش" in p and "طاولة التقطيع" in p and "🎥 اللقطات" in p
    assert p.rstrip().endswith("إزاي أحط الكاميرا؟") and "أبدأ منين؟" in p


@test
def test_guide_mentions_every_destination_label():
    g = assistant.guide()
    for slug, (_kind, label) in assistant.DESTINATIONS.items():
        name = label.split(" ", 1)[1]
        assert name in g, f"{slug}: «{name}» مش في الدليل"


@test
def test_answer_navigation_lines_are_whitelisted():
    body, goes = assistant.parse_answer("روح للمشاهد ودوس «إضافة مشهد».\nGO: scenes\nGO: admin_panel\nGO: scenes\nGO: account")
    assert body == "روح للمشاهد ودوس «إضافة مشهد»." and goes == ["scenes", "account"]


@test
def test_ask_and_poll_round_trip_is_logged():
    jid = assistant_jobs.ask("u1", "  أبدأ منين؟ ", {"الشاشة": "الرئيسية"}, project_id=None)
    m = json.load(open(os.path.join(_TMP, "spool", "inbox", f"{jid}.json")))
    assert "أبدأ منين؟" in m["prompt"]
    assert assistant_jobs.poll(jid)["state"] == "waiting"
    json.dump({"answer": "اعمل مشروع من الشريط الجانبي.\nGO: import", "cost_usd": 0.002},
              open(os.path.join(_TMP, "spool", "outbox", f"{jid}.result.json"), "w"))
    json.dump({"state": "done"}, open(os.path.join(_TMP, "spool", "status", f"{jid}.json"), "w"))
    res = assistant_jobs.poll(jid)
    assert res == {"state": "done", "answer": "اعمل مشروع من الشريط الجانبي.", "goes": ["import"]}
    row = fetch_all("SELECT question, answer, state, screen FROM assistant_messages WHERE job_id=?", (jid,))[0]
    assert (row["question"], row["state"], row["screen"]) == ("أبدأ منين؟", "answered", "الرئيسية")
    assert row["answer"] == "اعمل مشروع من الشريط الجانبي."


@test
def test_empty_question_and_daily_limit():
    try:
        assistant_jobs.ask("u2", "   ", {})
    except ValueError:
        pass
    else:
        raise AssertionError("empty question accepted")
    for _ in range(assistant_jobs.DAILY_LIMIT):
        assistant_jobs.ask("u3", "سؤال", {})
    try:
        assistant_jobs.ask("u3", "سؤال زيادة", {})
    except assistant_jobs.LimitReached:
        return
    raise AssertionError("no daily limit")


if __name__ == "__main__":
    passed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
            passed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{passed}/{len(TESTS)} passed")
    sys.exit(0 if passed == len(TESTS) else 1)
