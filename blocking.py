"""طاولة التقطيع (الدِكوباج) — المنطق من غير Streamlit (طلب المالك 2026-09-25).

المخرج وهو بيقسّم المشهد لقطات محتاج قدامه ٣ حاجات:
1. نص المشهد مقسوم حتت (جمل الوصف وسطور الحوار) يختار منها ويشوف كل لقطة
   بتغطي إيه — زي الـ «lined script» اللي بيتعمل على الورق.
2. رسمة من فوق للمكان (الديكور) — بتترسم مرة للمكان وبتبقى الافتراضية لكل
   حالاته، والحالة تقدر يبقى ليها رسمة خاصة بيها.
3. أماكن الشخصيات (نقط) والكاميرات (لكل لقطة كاميرا بزاوية رؤيتها) في المشهد.

كل حاجة هنا JSON بسيط؛ الدوال دي بتنضّفه قبل ما يتحفظ (أرقام في حدودها،
أنواع معروفة بس، نصوص مقصوصة) لأنه جاي من المتصفح أو من الـ AI.
"""
from __future__ import annotations

import json
import re

DIALOGUE_LINE_RE = re.compile(r'^([^:：]{1,30})[:：]\s*(.+)$')
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?؟…])\s+')

# --- ١. نص المشهد ---------------------------------------------------------------


def script_blocks(notes):
    """نص المشهد → حتت بالترتيب: [{i, kind: action|dialogue, speaker, text}].

    الحوار = سطر «اسم: كلام» (نفس قاعدة توزيع الحوار على اللقطات). الوصف
    بيتقسم جمل عشان المخرج يقدر يختار جزء من الفقرة مش الفقرة كلها."""
    out = []
    for raw in (notes or "").split("\n"):
        line = raw.strip()
        if not line:
            continue
        m = DIALOGUE_LINE_RE.match(line)
        if m:
            out.append({"i": len(out), "kind": "dialogue", "speaker": m.group(1).strip(),
                        "text": m.group(2).strip(), "line": line})
            continue
        for sentence in _SENTENCE_SPLIT_RE.split(line):
            sentence = sentence.strip()
            if sentence:
                out.append({"i": len(out), "kind": "action", "speaker": "", "text": sentence, "line": sentence})
    return out


def parse_block_ids(raw):
    """‎shots.script_blocks‎ (JSON) → set أرقام الحتت. أي حاجة بايظة = فاضي."""
    try:
        data = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return set()
    return {int(x) for x in data if isinstance(x, (int, float)) and 0 <= int(x) < 10000}


def dump_block_ids(ids):
    return json.dumps(sorted({int(i) for i in ids}))


def texts_for(blocks, ids):
    """الحتت المختارة → (وصف الحركة، الحوار) عشان فورم اللقطة يتعبّى بيهم."""
    chosen = [b for b in blocks if b["i"] in set(ids)]
    action = " ".join(b["text"] for b in chosen if b["kind"] == "action")
    dialogue = "\n".join(b["line"] for b in chosen if b["kind"] == "dialogue")
    return action, dialogue


def coverage(blocks, shots):
    """لكل حتة: أرقام اللقطات اللي بتغطيها. shots = [{shot_number, script_blocks}]."""
    cov = {b["i"]: [] for b in blocks}
    for sh in shots:
        for i in parse_block_ids(sh.get("script_blocks")):
            if i in cov:
                cov[i].append(sh["shot_number"])
    return {i: sorted(v) for i, v in cov.items()}


# --- ٢. رسمة الديكور -------------------------------------------------------------

ROOM_MIN, ROOM_MAX = 100, 2000        # وحدات الرسمة (سم تقريبًا - مش مقياس دقيق)
ITEM_KINDS = ("door", "window", "wall", "table", "chair", "sofa", "bed", "desk", "counter",
              "cabinet", "plant", "car", "block")
_MAX_ITEMS = 200
_MAX_STROKES = 300
_MAX_POINTS = 400


def _num(v, lo, hi, default):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    if x != x:            # NaN
        return default
    return round(max(lo, min(hi, x)), 1)


def _text(v, n=40):
    return str(v or "").strip()[:n]


def empty_plan():
    return {"w": 600, "h": 400, "items": [], "strokes": []}


def clean_plan(raw):
    """أي plan (dict أو JSON) → plan نضيف في حدوده. None لو مش plan أصلًا."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None
    if not isinstance(raw, dict):
        return None
    w = _num(raw.get("w"), ROOM_MIN, ROOM_MAX, 600)
    h = _num(raw.get("h"), ROOM_MIN, ROOM_MAX, 400)
    items = []
    for it in (raw.get("items") or [])[:_MAX_ITEMS]:
        if not isinstance(it, dict) or it.get("k") not in ITEM_KINDS:
            continue
        items.append({"k": it["k"], "x": _num(it.get("x"), 0, w, w / 2), "y": _num(it.get("y"), 0, h, h / 2),
                      "w": _num(it.get("w"), 5, ROOM_MAX, 60), "h": _num(it.get("h"), 3, ROOM_MAX, 40),
                      "r": _num(it.get("r"), -360, 360, 0), "label": _text(it.get("label"))})
    strokes = []
    for s in (raw.get("strokes") or [])[:_MAX_STROKES]:
        pts = s.get("pts") if isinstance(s, dict) else None
        if not isinstance(pts, list):
            continue
        clean = [[_num(p[0], 0, w, 0), _num(p[1], 0, h, 0)] for p in pts[:_MAX_POINTS]
                 if isinstance(p, (list, tuple)) and len(p) == 2]
        if len(clean) >= 2:
            strokes.append({"pts": clean})
    return {"w": w, "h": h, "items": items, "strokes": strokes}


# --- ٣. الشخصيات والكاميرات في المشهد --------------------------------------------

# زاوية رؤية تقريبية لكل حجم كادر (درجات) - للرسمة بس
_FOV = {"Extreme Wide": 90, "Wide": 70, "Medium": 45, "Over the Shoulder": 40, "POV": 50,
        "Extreme Close-up": 12, "Close-up": 22}


def fov_for(shot_size):
    s = shot_size or ""
    for key in ("Extreme Wide", "Extreme Close-up", "Close-up", "Wide", "Medium", "Over the Shoulder", "POV"):
        if key in s:
            return _FOV[key]
    return 45


def margin(w, h):
    """المساحة حوالين الأوضة في الرسمة (للكاميرات والشخصيات اللي برّه)."""
    return round(0.2 * max(w, h), 1)


def empty_blocking():
    return {"chars": [], "cams": []}


def clean_blocking(raw, plan, character_ids, shot_ids):
    """النقط لازم تبقى جوه الرسمة، والشخصيات واللقطات لازم تبقى تبع المشهد."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return empty_blocking()
    if not isinstance(raw, dict):
        return empty_blocking()
    w, h = (plan or empty_plan())["w"], (plan or empty_plan())["h"]
    m = margin(w, h)          # كاميرا برّه الشباك أو شخصية داخلة من برّه
    chars, seen = [], set()
    for c in raw.get("chars") or []:
        if not isinstance(c, dict):
            continue
        try:
            cid = int(c.get("id"))
        except (TypeError, ValueError):
            continue
        if cid not in character_ids or cid in seen:
            continue
        seen.add(cid)
        entry = {"id": cid, "x": _num(c.get("x"), -m, w + m, w / 2), "y": _num(c.get("y"), -m, h + m, h / 2),
                 "f": _num(c.get("f"), -360, 360, 0)}
        if c.get("tx") is not None and c.get("ty") is not None:
            entry["tx"], entry["ty"] = _num(c.get("tx"), -m, w + m, 0), _num(c.get("ty"), -m, h + m, 0)
        chars.append(entry)
    cams, seen = [], set()
    for c in raw.get("cams") or []:
        if not isinstance(c, dict):
            continue
        try:
            sid = int(c.get("shot_id"))
        except (TypeError, ValueError):
            continue
        if sid not in shot_ids or sid in seen:
            continue
        seen.add(sid)
        cams.append({"shot_id": sid, "x": _num(c.get("x"), -m, w + m, w / 2), "y": _num(c.get("y"), -m, h + m, h / 2),
                     "r": _num(c.get("r"), -360, 360, 0)})
    return {"chars": chars, "cams": cams}
