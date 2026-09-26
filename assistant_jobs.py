"""🤖 مساعد البرنامج — جانب التطبيق من الطابور (assistant_worker.py بيرد).

كل سؤال بيتسجل في assistant_messages (مين سأل، من أنهي شاشة، والرد) — عشان
نعرف اليوزرز بيقفوا فين ونحسّن البرنامج والدليل. التطبيق بيكتب في inbox بس،
والـ worker في status وoutbox. الميزة شغالة بس لو CIMAFAST_ASSISTANT_SPOOL متظبط.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
import uuid

import assistant
import permissions
from database import fetch_all, run_query

DAILY_LIMIT = 40
STALE_SECONDS = 150


class LimitReached(RuntimeError):
    pass


def available():
    return bool(os.environ.get("CIMAFAST_ASSISTANT_SPOOL"))


def _dirs():
    root = os.environ.get("CIMAFAST_ASSISTANT_SPOOL")
    if not root:
        raise RuntimeError("المساعد مش متاح على النسخة دي.")
    return tuple(os.path.join(root, d) for d in ("inbox", "status", "outbox"))


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def asked_today(username):
    day = dt.datetime.now(dt.timezone.utc).date().isoformat()
    return fetch_all("SELECT COUNT(*) AS n FROM assistant_messages WHERE username=? AND at >= ?",
                     (username, day))[0]["n"]


def ask(username, question, context, history=(), company_id=None, project_id=None):
    """بيبعت السؤال ويرجّع رقم الطلب."""
    question = (question or "").strip()[:assistant.MAX_QUESTION]
    if not question:
        raise ValueError("اكتب سؤالك الأول")
    import admin_users
    admin_users.require_feature(username, "assistant")
    if asked_today(username) >= admin_users.assistant_limit(username, DAILY_LIMIT):
        raise LimitReached("وصلت لحد الأسئلة النهارده — كمّل بكرة، أو كلّم فريق البرنامج.")
    inbox, _, _ = _dirs()
    jid = f"q{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
    prompt = assistant.build_prompt(question, context, history)
    with permissions.system():
        run_query("INSERT INTO assistant_messages (at, username, company_id, project_id, screen, question, state, job_id) "
                  "VALUES (?, ?, ?, ?, ?, ?, 'asked', ?)",
                  (_now(), username, company_id, project_id, context.get("الشاشة"), question, jid))
    tmp = os.path.join(inbox, f"{jid}.json.tmp.{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"job_id": jid, "prompt": prompt, "created_at": time.time()}, fh, ensure_ascii=False)
    os.replace(tmp, os.path.join(inbox, f"{jid}.json"))
    return jid


def poll(jid):
    """{state: waiting|done|failed, answer, goes} — والرد بيتسجل مرة واحدة."""
    _, status_dir, outbox = _dirs()
    info = _read(os.path.join(status_dir, f"{jid}.json")) or {}
    state = info.get("state") or "waiting"
    if state == "done":
        res = _read(os.path.join(outbox, f"{jid}.result.json")) or {}
        body, goes = assistant.parse_answer(res.get("answer"))
        with permissions.system():
            run_query("UPDATE assistant_messages SET answer=?, state='answered', cost_usd=?, answered_at=? "
                      "WHERE job_id=? AND state='asked'", (body, res.get("cost_usd"), _now(), jid))
        return {"state": "done", "answer": body, "goes": goes}
    created = int(jid[1:].split("-")[0]) / 1000 if jid.startswith("q") else 0
    if state == "failed" or (time.time() - created > STALE_SECONDS):
        with permissions.system():
            run_query("UPDATE assistant_messages SET state='failed' WHERE job_id=? AND state='asked'", (jid,))
        return {"state": "failed", "answer": info.get("detail") or "المساعد مش قادر يرد دلوقتي. جرّب تاني بعد شوية.",
                "goes": []}
    return {"state": "waiting", "answer": "", "goes": []}


def recent(limit=200):
    """آخر الأسئلة — للتحليل (مين سأل عن إيه ومن أنهي شاشة)."""
    return fetch_all("SELECT at, username, project_id, screen, question, answer, state FROM assistant_messages "
                     "ORDER BY id DESC LIMIT ?", (limit,))
