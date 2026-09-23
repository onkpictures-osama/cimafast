"""تقرير البناء الدرامي (هرم فرايتاج) — طلب المالك 2026-09-23.

بعد ما السيناريو يتحلل ويطلع مشاهده، الموديول ده بيبني تقرير تاني فوق نفس
المشاهد: العرض/التمهيد، التصاعد والحدث المحرك، الذروة، الهبوط، الحل والخاتمة
— كل حكم فيه لازم يترجع لأرقام مشاهد حقيقية من التحليل، مش رأي عام.

ليه موديول لوحده: التقرير ده مش جزء من تحليل السكريبت نفسه (اللي برومبته في
ai_prompt.py وممنوع نلمسه غير بطلب المالك) — ده تحليل تاني، بيتطلب بعد كده
واختياري، وبيتخزّن جنب التحليل في ‎analysis_library‎ تحت
‎payload["reports"]["dramatic_structure"]‎. الموديول ده مايستوردش Streamlit
ولا spool ولا AI مباشرة — بيبني البرومبت، بيقيّم التكلفة قبل الطلب، وبيتحقق
من رد الـ AI ويرفضه برسالة عربي واضحة لو مش مضبوط. اللي بيبعت الطلب فعليًا
(ai_jobs.py / worker.py) شغلانة تانية، عشان worker.py مشترك مع البرودكشن ولازم
تعديله يتراجع بعناية.

## إزاي بنضمن إن سكريبت طويل (140+ مشهد) يشتغل من غير ما نبتر آخره بصمت
مابنبعتش نص المشاهد كامل (حوار + حركة) للـ AI — ده حجم التحليل الأصلي نفسه
وده اللي بيغلّيه. بنبني "ملخص" بسطر أو اتنين لكل مشهد (العنوان + الشخصيات +
مقتطف من notes)، وميزانية الحروف لكل مشهد بتتحسب تلقائي من عدد المشاهد
(MAX_DIGEST_CHARS ÷ عدد المشاهد) عشان أي سكريبت -قصير أو طويل جدًا- يفضل
جوه حد أقصى واحد للمكالمة، وكل مشهد بياخد نصيبه بدل ما الآخر يتقطع بصمت.
"""
from __future__ import annotations

import json
import re

# --- مراحل هرم فرايتاج -----------------------------------------------------

STAGE_ORDER = ("exposition", "rising_action", "climax", "falling_action", "resolution")

STAGE_LABELS = {
    "exposition":    {"ar": "العرض والتمهيد",              "en": "Exposition"},
    "rising_action": {"ar": "التصاعد والحدث المحرك",         "en": "Rising Action & Inciting Incident"},
    "climax":        {"ar": "الذروة",                       "en": "Climax"},
    "falling_action": {"ar": "الهبوط",                      "en": "Falling Action"},
    "resolution":    {"ar": "الحل والخاتمة",                "en": "Resolution / Denouement"},
}

REPORT_KEY = "dramatic_structure"      # المفتاح جوه payload["reports"] في analysis_library
SCHEMA_VERSION = 1


class DramaturgyError(ValueError):
    """رسالة عربي جاهزة تتعرض للمستخدم زي ما هي — من غير traceback خام."""


# --- تقدير التكلفة قبل الطلب ------------------------------------------------
# نفس منطق ai_jobs.estimate() (قايمة مرجعية + تكلفة بالحرف) لكن على نص
# الملخص مش السكريبت كامل، لأن المخرجات هنا تقرير قصير (كام كيلوبايت JSON)
# مش إعادة كتابة للحوار كله زي التحليل الأساسي. الأرقام دي نقطة بداية
# محافظة لحد ما نقيس تشغيلات حقيقية (meta.cost_usd بيتسجل من كل تقرير
# فعلي، وده مصدر المعايرة الصح زي ما ai_jobs.py بيعمل بالظبط).
DRAMA_BASE_COST_USD = 0.02
DRAMA_COST_PER_CHAR_USD = 0.000006
DRAMA_MIN_ESTIMATE_USD = 0.04
DRAMA_CEILING_MULTIPLIER = 2.5

MAX_DIGEST_CHARS = 90_000       # سقف حروف الملخص كله مهما كان عدد المشاهد
MIN_SCENE_BUDGET = 70           # أقل نصيب حروف لكل مشهد حتى لو السكريبت ضخم جدًا
SCENE_OVERHEAD_CHARS = 90       # تقريبًا حجم "N. مشهد 12أ — داخلي..." من غير الملخص نفسه


def _scene_label(scene):
    num = scene.get("scene_number")
    suffix = scene.get("scene_suffix") or ""
    return f"{num}{suffix}"


def _scene_heading(scene):
    parts = []
    if scene.get("int_ext"):
        parts.append(str(scene["int_ext"]))
    if scene.get("location_name"):
        parts.append(str(scene["location_name"]))
    if scene.get("day_night"):
        parts.append(str(scene["day_night"]))
    return " - ".join(parts) if parts else "بدون عنوان"


def _scene_budget(n_scenes):
    if n_scenes <= 0:
        return MAX_DIGEST_CHARS
    per_scene = MAX_DIGEST_CHARS // n_scenes
    return max(MIN_SCENE_BUDGET, per_scene - SCENE_OVERHEAD_CHARS)


def build_scene_digest(scenes):
    """ملخص مرقّم لكل مشاهد السكريبت، بترتيب ظهورها.

    كل سطر: index (ترتيب متتالي 1..N بيتحسب منه % الموقع في السكريبت)، رقم
    المشهد الحقيقي (زي ما هو في التحليل، يشمل 35A)، رقم الحلقة لو موجود،
    العنوان، الشخصيات، ومقتطف من notes. الرجوع: (نص الملخص، عدد المشاهد).
    """
    n = len(scenes)
    budget = _scene_budget(n)
    lines = []
    for i, sc in enumerate(scenes, start=1):
        ep = sc.get("episode_number")
        ep_tag = f"ح{ep} " if ep else ""
        chars = "، ".join(sc.get("characters") or []) or "—"
        notes = re.sub(r"\s+", " ", str(sc.get("notes") or "")).strip()
        if len(notes) > budget:
            notes = notes[:budget].rstrip() + "…"
        line = (f"{i}. {ep_tag}مشهد {_scene_label(sc)} — {_scene_heading(sc)} — "
                f"الشخصيات: {chars} — ملخص: {notes or '—'}")
        lines.append(line)
    return "\n".join(lines), n


def estimate(scenes):
    """(عدد المشاهد، التكلفة المتوقعة، السقف) — نفس شكل ai_jobs.estimate()."""
    digest, n = build_scene_digest(scenes)
    cost = max(DRAMA_MIN_ESTIMATE_USD,
               round(DRAMA_BASE_COST_USD + len(digest) * DRAMA_COST_PER_CHAR_USD, 4))
    return n, cost, round(cost * DRAMA_CEILING_MULTIPLIER, 4)


# --- البرومبت ----------------------------------------------------------------

DRAMATURGY_SYSTEM_PROMPT = """أنت مستشار درامي (script consultant) محترف بتحلل البناء الدرامي لسيناريو
فيلم أو مسلسل على أساس هرم فرايتاج (Freytag's Pyramid)، عشان تقريرك هيتحط في
برنامج إدارة إنتاج ويتعرض على صانع السيناريو نفسه.

هتاخد قايمة مرقّمة بملخص كل مشهد بالترتيب اللي ظهر بيه في السكريبت (رقم
ترتيبي متتالي 1 لحد N، ورقم المشهد الحقيقي من السكريبت جنبه). اقرا القايمة
كلها الأول، وابني تحليلك على المشاهد المذكورة فيها بس — ممنوع تخترع مشهد
مش موجود في القايمة، وممنوع تستنتج حاجة مش مذكورة أو ملمّح ليها في الملخصات.

قسّم المشاهد على 5 مراحل هرم فرايتاج بالترتيب ده بالظبط، وكل مرحلة لازم
تاخد مدى متصل من أرقام الترتيب (index) من غير فجوات ولا تداخل، والمراحل
الخمسة مجتمعة لازم تغطي كل المشاهد من 1 لحد N:
1. exposition — العرض والتمهيد
2. rising_action — التصاعد والحدث المحرك (يشمل نقطة الانطلاق/inciting incident)
3. climax — الذروة
4. falling_action — الهبوط
5. resolution — الحل والخاتمة

طلعلي النتيجة بصيغة JSON بالشكل ده بالظبط، من غير أي نص زيادة قبله أو بعده
(من غير ```json ولا أي شرح):

{
  "stages": [
    {"stage": "exposition", "from_index": 1, "to_index": 12,
     "summary": "وصف قصير (2-4 جمل) ليه المرحلة دي شكلها كده، بالإشارة لمشاهد
     بعينها من الملخص",
     "key_indexes": [1, 5, 12]},
    {"stage": "rising_action", "from_index": 13, "to_index": 55, "summary": "...",
     "key_indexes": [20, 34]},
    {"stage": "climax", "from_index": 56, "to_index": 61, "summary": "...",
     "key_indexes": [58]},
    {"stage": "falling_action", "from_index": 62, "to_index": 70, "summary": "...",
     "key_indexes": [65]},
    {"stage": "resolution", "from_index": 71, "to_index": 75, "summary": "...",
     "key_indexes": [74, 75]}
  ],
  "tension_curve": [تقييم توتر رقم صحيح من 0 لـ 100 لكل مشهد بالترتيب، مصفوفة
    طولها لازم يساوي N بالظبط، عنصر واحد لكل index من 1 لحد N],
  "strengths": [
    {"text": "وصف نقطة قوة حقيقية في البناء الدرامي", "indexes": [12, 13]}
  ],
  "weaknesses": [
    {
      "title": "عنوان قصير للمشكلة",
      "stage": "rising_action",
      "from_index": 30, "to_index": 40,
      "issue": "إيه بالظبط الضعف في البناء هنا (منطقة دراما ضعيفة، ترهّل،
        مفيش رهان/conflict، إيقاع بطيء...)",
      "why_it_matters": "إيه اللي هيتأثر في القصة لو الموضوع فضل كده",
      "suggestion": "اقتراح عملي ومحدد لتقوية المنطقة دي، مربوط بمشاهد بعينها
        (مثلاً: زوّد رهان في مشهد كذا، اختصر مشهد كذا وكذا لأنهم بيكرروا نفس
        المعلومة، حط تصعيد في مشهد كذا قبل الذروة)",
      "indexes": [30, 33, 40]
    }
  ],
  "verdict": {
    "strong": true أو false,
    "summary": "حكم عام على البناء الدرامي كله في فقرة أو اتنين: هل هو قوي
      ولا فيه مشاكل بنيوية، وليه"
  }
}

قواعد إلزامية:
- كل رقم index في الرد (from_index / to_index / key_indexes / indexes) لازم
  يكون رقم موجود فعلًا في القايمة اللي اتبعتلك (من 1 لحد N) - ممنوع رقم برا
  المدى ده.
- مصفوفة tension_curve طولها لازم يساوي بالظبط عدد المشاهد اللي اتبعتلك،
  عنصر واحد لكل مشهد بالترتيب من غير أي فجوة.
- كل "weaknesses" لازم يكون ليه "suggestion" محدد وعملي، مش عبارة عامة زي
  "خليه أقوى" من غير تفاصيل.
- لو مفيش نقطة ضعف واضحة في مرحلة معينة، من الآخر متختلقش وحدة - سيب
  "weaknesses" فاضية أو أقل لو الموضوع فعلًا سليم.
- كل النصوص بالعربي المصري بمستوى مستشار درامي محترف، من غير عامية زيادة عن
  اللزوم ومن غير رسمية جافة.
- قبل ما ترسل: راجع إن الـ JSON صحيح 100% وقابل للقراءة مباشرة، وإن كل
  index مذكور فعلاً موجود في القايمة، وإن المراحل الخمسة بترتيبها الصحيح
  وبتغطي كل المشاهد من غير فجوة ولا تداخل."""


# JSON Schema للرد — بيتبعت لـ `claude --json-schema` عشان يقلل احتمال رد
# مش مطابق للشكل من الأساس. ده مش بديل عن _validate() تحت: الشيما بتتأكد من
# النوع والوجود بس، لكن الالتزام بالمعنى (تغطية كل المشاهد، الترتيب، الأرقام
# جوه المدى) شغل _validate() اللي بيرجّع رسالة عربي واضحة لو اتكسر.
RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "required": ["stages", "tension_curve", "strengths", "weaknesses", "verdict"],
    "properties": {
        "stages": {
            "type": "array", "minItems": 5, "maxItems": 5,
            "items": {
                "type": "object",
                "required": ["stage", "from_index", "to_index", "summary"],
                "properties": {
                    "stage": {"type": "string", "enum": list(STAGE_ORDER)},
                    "from_index": {"type": "integer"},
                    "to_index": {"type": "integer"},
                    "summary": {"type": "string"},
                    "key_indexes": {"type": "array", "items": {"type": "integer"}},
                },
            },
        },
        "tension_curve": {"type": "array", "items": {"type": "number"}},
        "strengths": {
            "type": "array",
            "items": {"type": "object", "required": ["text", "indexes"],
                     "properties": {"text": {"type": "string"},
                                    "indexes": {"type": "array", "items": {"type": "integer"}}}},
        },
        "weaknesses": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["title", "issue", "suggestion", "indexes"],
                "properties": {
                    "title": {"type": "string"}, "stage": {"type": "string"},
                    "from_index": {"type": "integer"}, "to_index": {"type": "integer"},
                    "issue": {"type": "string"}, "why_it_matters": {"type": "string"},
                    "suggestion": {"type": "string"},
                    "indexes": {"type": "array", "items": {"type": "integer"}},
                },
            },
        },
        "verdict": {
            "type": "object", "required": ["strong", "summary"],
            "properties": {"strong": {"type": "boolean"}, "summary": {"type": "string"}},
        },
    },
}


def build_prompt(scenes):
    """البرومبت الكامل اللي بيتبعت للـ AI: التعليمات + ملخص كل المشاهد."""
    digest, n = build_scene_digest(scenes)
    if n == 0:
        raise DramaturgyError("مفيش مشاهد في التحليل ده، فمش هيتعمل تقرير بناء درامي.")
    return (DRAMATURGY_SYSTEM_PROMPT
            + f"\n\nعدد المشاهد (N) = {n}\n\nقايمة المشاهد:\n" + digest)


# --- التحقق من رد الـ AI -----------------------------------------------------

def _strip_fences(text):
    text = (text or "").strip()
    m = re.match(r"^```(?:json)?\s*(.*)```\s*$", text, re.DOTALL)
    return m.group(1).strip() if m else text


def _require(cond, msg):
    if not cond:
        raise DramaturgyError(msg)


def _valid_index(v, n):
    return isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= n


def parse_response(raw_text, scenes):
    """بيتحقق من رد الـ AI ويرجّع تقرير متحقق منه، جاهز للتخزين والعرض.

    أي مشكلة في الشكل أو مراجع لمشاهد مش موجودة بترمي DramaturgyError
    برسالة عربي واضحة - عمرها ما بترجع traceback خام للمستخدم."""
    n = len(scenes)
    _require(n > 0, "مفيش مشاهد نتحقق من التقرير عليها.")
    try:
        text = _strip_fences(raw_text)
        data = json.loads(text)
    except (ValueError, TypeError):
        raise DramaturgyError(
            "رد الذكاء الاصطناعي مش JSON سليم — التقرير ده مايتحفظش، جرّب تاني.") from None
    try:
        return _validate(data, scenes)
    except DramaturgyError:
        raise
    except Exception:  # noqa: BLE001 — أي عطل تاني في الشكل يتحول لرسالة عربي واضحة
        raise DramaturgyError(
            "رد الذكاء الاصطناعي جاله شكل غير متوقع ومش قادرين نقرا التقرير منه.") from None


def _validate(data, scenes):
    n = len(scenes)
    _require(isinstance(data, dict), "رد الذكاء الاصطناعي مش object JSON زي ما المفروض.")

    stages_in = data.get("stages")
    _require(isinstance(stages_in, list) and len(stages_in) == 5,
             "التقرير مفيهوش المراحل الخمسة لهرم فرايتاج بالظبط.")
    stages_out = []
    prev_to = 0
    for expected, raw in zip(STAGE_ORDER, stages_in):
        _require(isinstance(raw, dict) and raw.get("stage") == expected,
                 f"ترتيب مراحل التقرير غلط — المفروض «{expected}» في مكانها ({STAGE_LABELS[expected]['ar']}).")
        frm, to = raw.get("from_index"), raw.get("to_index")
        _require(_valid_index(frm, n) and _valid_index(to, n) and frm <= to,
                 f"مدى مشاهد مرحلة «{STAGE_LABELS[expected]['ar']}» في التقرير غير صحيح.")
        _require(frm == prev_to + 1 if prev_to else frm == 1,
                 "مراحل هرم فرايتاج في التقرير فيها فجوة أو تداخل بين المشاهد.")
        prev_to = to
        summary = str(raw.get("summary") or "").strip()
        _require(summary, f"مرحلة «{STAGE_LABELS[expected]['ar']}» في التقرير من غير وصف.")
        keys = [k for k in (raw.get("key_indexes") or []) if _valid_index(k, n)]
        stages_out.append({
            "stage": expected,
            "label_ar": STAGE_LABELS[expected]["ar"],
            "label_en": STAGE_LABELS[expected]["en"],
            "from_index": frm, "to_index": to,
            "from_scene": _scene_label(scenes[frm - 1]), "to_scene": _scene_label(scenes[to - 1]),
            "position_pct": {"from": round((frm - 1) / n * 100, 1), "to": round(to / n * 100, 1)},
            "summary": summary,
            "key_scenes": [_scene_label(scenes[k - 1]) for k in keys],
        })
    _require(prev_to == n, "مراحل هرم فرايتاج في التقرير ماغطتش كل مشاهد السكريبت.")

    curve_in = data.get("tension_curve")
    _require(isinstance(curve_in, list) and len(curve_in) == n,
             f"منحنى التوتر في التقرير طوله لازم يساوي عدد المشاهد ({n}).")
    curve_out = []
    for i, v in enumerate(curve_in, start=1):
        _require(isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 100,
                 "منحنى التوتر فيه قيمة برّه المدى المسموح (0-100).")
        sc = scenes[i - 1]
        curve_out.append({"index": i, "scene": _scene_label(sc), "value": round(float(v), 1)})

    def _claims(key, require_suggestion=False):
        out = []
        for raw in data.get(key) or []:
            if not isinstance(raw, dict):
                continue
            idxs = [k for k in (raw.get("indexes") or []) if _valid_index(k, n)]
            if not idxs:
                continue           # ادّعاء من غير مرجع مشهد حقيقي بيتجاهل، مش بيسقط التقرير كله
            text = str(raw.get("text") or raw.get("issue") or "").strip()
            if not text:
                continue
            item = {"text": text, "scenes": [_scene_label(scenes[k - 1]) for k in idxs]}
            if require_suggestion:
                suggestion = str(raw.get("suggestion") or "").strip()
                if not suggestion:
                    continue        # زي ما البرومبت بيقول: نقطة ضعف من غير اقتراح عملي متتجاهلش تتحفظ
                item.update({
                    "title": str(raw.get("title") or text[:60]).strip(),
                    "stage": raw.get("stage") if raw.get("stage") in STAGE_ORDER else None,
                    "issue": text,
                    "why_it_matters": str(raw.get("why_it_matters") or "").strip(),
                    "suggestion": suggestion,
                })
            out.append(item)
        return out

    weaknesses = _claims("weaknesses", require_suggestion=True)
    strengths = _claims("strengths")

    verdict_in = data.get("verdict") or {}
    _require(isinstance(verdict_in, dict) and str(verdict_in.get("summary") or "").strip(),
             "التقرير من غير حكم عام (verdict) على البناء الدرامي.")
    verdict = {"strong": bool(verdict_in.get("strong")), "summary": str(verdict_in["summary"]).strip()}

    return {
        "version": SCHEMA_VERSION,
        "scene_count": n,
        "stages": stages_out,
        "tension_curve": curve_out,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "verdict": verdict,
    }


def with_meta(report, *, model=None, cost_usd=None, generated_at=None):
    """بيضيف بيانات التشغيل (مش جزء من التحقق) — بتتحفظ مع التقرير للمرجعية والمعايرة."""
    out = dict(report)
    out["meta"] = {"model": model, "cost_usd": cost_usd, "generated_at": generated_at}
    return out


# --- عرض وتصدير ---------------------------------------------------------------

def to_sections(report, lang="ar"):
    """التقرير كقايمة أقسام (عنوان + فقرات/عناصر) — export.py بيستعملها يبني
    PDF/Word من غيرما يعرف شكل الـ JSON، ونفس الشكل يصلح لعرضه في Streamlit."""
    L = lang if lang in ("ar", "en") else "ar"
    T = {
        "ar": {"verdict": "الحكم العام على البناء الدرامي", "stages": "مراحل هرم فرايتاج",
               "strengths": "نقاط القوة", "weaknesses": "مناطق الدراما الضعيفة وإزاي نقويها",
               "strong_yes": "بناء درامي قوي", "strong_no": "البناء الدرامي محتاج شغل",
               "scenes": "مشاهد", "why": "ليه ده مهم", "fix": "إزاي نقويه"},
        "en": {"verdict": "Overall dramatic-structure verdict", "stages": "Freytag's pyramid stages",
               "strengths": "Strengths", "weaknesses": "Weak dramatic zones & how to strengthen them",
               "strong_yes": "Strong dramatic structure", "strong_no": "Structure needs work",
               "scenes": "scenes", "why": "Why it matters", "fix": "How to strengthen it"},
    }[L]
    sections = []
    v = report["verdict"]
    sections.append({"heading": T["verdict"],
                      "paragraphs": [(T["strong_yes"] if v["strong"] else T["strong_no"]) + " — " + v["summary"]]})
    stage_items = []
    for st in report["stages"]:
        label = st["label_ar"] if L == "ar" else st["label_en"]
        rng = f"{st['from_scene']}–{st['to_scene']}" if st["from_scene"] != st["to_scene"] else st["from_scene"]
        pct = f"{st['position_pct']['from']:.0f}%–{st['position_pct']['to']:.0f}%"
        stage_items.append(f"{label} ({T['scenes']} {rng}, {pct}): {st['summary']}")
    sections.append({"heading": T["stages"], "paragraphs": stage_items})
    if report["strengths"]:
        sections.append({"heading": T["strengths"],
                          "paragraphs": [f"{s['text']} ({T['scenes']} {', '.join(s['scenes'])})"
                                        for s in report["strengths"]]})
    weak_items = []
    for w in report["weaknesses"]:
        rng = ", ".join(w["scenes"])
        weak_items.append(f"{w['title']} ({T['scenes']} {rng}) — {w['issue']} "
                          f"| {T['why']}: {w['why_it_matters']} | {T['fix']}: {w['suggestion']}")
    sections.append({"heading": T["weaknesses"], "paragraphs": weak_items})
    return sections


_STAGE_COLORS = {
    "exposition": "#6b8f9e", "rising_action": "#c9a84c", "climax": "#c0463c",
    "falling_action": "#c9a84c", "resolution": "#6b8f9e",
}


def render_svg(report, lang="ar", width=900, height=260):
    """منحنى التوتر عبر المشاهد مع الخمس مراحل - SVG واحد، viewBox نسبي
    (بيرندر على أي عرض شاشة، من الموبايل لسطح المكتب) ومتجاوب مع RTL: في
    العربي بداية القصة (العرض) على اليمين والخاتمة على الشمال."""
    rtl = lang == "ar"
    curve = report["tension_curve"]
    n = len(curve)
    if n == 0:
        return ""
    pad_l, pad_r, pad_t, pad_b = 10, 10, 20, 30
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b

    def x_of(i):  # i: 0-based index على منحنى التوتر
        frac = i / (n - 1) if n > 1 else 0
        if rtl:
            frac = 1 - frac
        return pad_l + frac * plot_w

    def y_of(v):
        return pad_t + (1 - v / 100) * plot_h

    points = " ".join(f"{x_of(i):.1f},{y_of(pt['value']):.1f}" for i, pt in enumerate(curve))
    bands = []
    for st in report["stages"]:
        x1, x2 = x_of(st["from_index"] - 1), x_of(st["to_index"] - 1)
        left, right = min(x1, x2), max(x1, x2)
        color = _STAGE_COLORS.get(st["stage"], "#888")
        label = st["label_ar"] if lang == "ar" else st["label_en"]
        bands.append(
            f'<rect x="{left:.1f}" y="{pad_t}" width="{max(1, right - left):.1f}" height="{plot_h}" '
            f'fill="{color}" fill-opacity="0.12" />'
            f'<text x="{(left + right) / 2:.1f}" y="{height - 8}" font-size="11" fill="{color}" '
            f'text-anchor="middle">{label}</text>'
        )
    svg = (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="auto" '
        f'preserveAspectRatio="xMidYMid meet" role="img" '
        f'aria-label="{"منحنى البناء الدرامي" if lang == "ar" else "Dramatic structure curve"}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        + "".join(bands)
        + f'<polyline points="{points}" fill="none" stroke="#c0463c" stroke-width="2.5" '
          'stroke-linejoin="round" stroke-linecap="round" />'
        + "</svg>"
    )
    return svg
