"""تقرير البناء الدرامي (dramaturgy.py) — التحقق من الشكل، مراجع المشاهد،
عرض العربي، والتعامل مع رد AI بايظ.

    venv/bin/python tests/test_dramaturgy.py

موديول نقي (من غير Streamlit ولا قاعدة بيانات ولا AI حقيقي) فمفيش أي setup
لقاعدة بيانات هنا - كله في الذاكرة.
"""
from __future__ import annotations

import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import dramaturgy as dr  # noqa: E402

_results = []


def test(fn):
    _results.append(fn)
    return fn


def _raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc as e:
        return e
    raise AssertionError(f"{getattr(fn, '__name__', fn)} did not raise {exc.__name__}")


# --- بيانات تجربة: 10 مشاهد بسيطة --------------------------------------------

def _scene(n, loc="شقة أحمد", chars=("أحمد",), notes="مشهد عادي فيه حوار قصير.", suffix=None):
    return {"scene_number": n, "scene_suffix": suffix, "int_ext": "INT", "day_night": "نهار",
            "location_name": loc, "characters": list(chars), "props": [], "notes": notes}


SCENES = [_scene(i) for i in range(1, 11)]           # 10 مشاهد، N=10


def _stage(stage, frm, to, summary="وصف المرحلة.", keys=None):
    return {"stage": stage, "from_index": frm, "to_index": to, "summary": summary,
            "key_indexes": keys or [frm]}


def _valid_payload():
    return {
        "stages": [
            _stage("exposition", 1, 2),
            _stage("rising_action", 3, 6),
            _stage("climax", 7, 7),
            _stage("falling_action", 8, 9),
            _stage("resolution", 10, 10),
        ],
        "tension_curve": [10, 15, 20, 30, 40, 55, 90, 60, 30, 10],
        "strengths": [{"text": "افتتاحية قوية بتأسس الصراع بسرعة.", "indexes": [1, 2]}],
        "weaknesses": [{
            "title": "ترهّل في وسط التصاعد",
            "stage": "rising_action",
            "from_index": 4, "to_index": 5,
            "issue": "مشهدين بيكرروا نفس المعلومة من غير تصعيد.",
            "why_it_matters": "الإيقاع بيقع قبل الذروة مباشرة.",
            "suggestion": "ادمج المشهدين 4 و5 في مشهد واحد وزوّد فيه رهان جديد.",
            "indexes": [4, 5],
        }],
        "verdict": {"strong": True, "summary": "البناء عمومًا متماسك مع ترهّل بسيط في النص."},
    }


# --- تقدير التكلفة والملخص ----------------------------------------------------

@test
def test_digest_covers_every_scene_and_scales_with_length():
    digest, n = dr.build_scene_digest(SCENES)
    assert n == 10
    for sc in SCENES:
        assert f"مشهد {sc['scene_number']}" in digest, "كل مشهد لازم يظهر في الملخص"
    # سكريبت طويل (140+ مشهد): الملخص كله يفضل تحت السقف، وكل مشهد لسه ظاهر
    long_scenes = [_scene(i, notes="حوار وحركة طويلة جدًا. " * 40) for i in range(1, 181)]
    long_digest, ln = dr.build_scene_digest(long_scenes)
    assert ln == 180
    assert len(long_digest) <= dr.MAX_DIGEST_CHARS + 180 * dr.SCENE_OVERHEAD_CHARS
    assert "مشهد 1 " in long_digest and "مشهد 180" in long_digest, "آخر مشهد متقطعش بصمت"


@test
def test_estimate_returns_scene_count_cost_and_ceiling():
    n, cost, ceiling = dr.estimate(SCENES)
    assert n == 10
    assert cost >= dr.DRAMA_MIN_ESTIMATE_USD
    assert ceiling > cost, "السقف لازم يكون أوسع من التقدير عشان مايقطعش التقرير في نصه"


@test
def test_build_prompt_includes_scene_count_and_rejects_empty():
    prompt = dr.build_prompt(SCENES)
    assert "عدد المشاهد (N) = 10" in prompt
    assert "مشهد 1" in prompt
    _raises(dr.DramaturgyError, dr.build_prompt, [])


# --- التحقق من رد صحيح --------------------------------------------------------

@test
def test_valid_response_parses_and_computes_position_pct():
    report = dr.parse_response(json.dumps(_valid_payload(), ensure_ascii=False), SCENES)
    assert report["scene_count"] == 10
    assert [s["stage"] for s in report["stages"]] == list(dr.STAGE_ORDER)
    exposition = report["stages"][0]
    assert exposition["position_pct"]["from"] == 0.0
    climax = report["stages"][2]
    assert climax["from_scene"] == "7" and climax["to_scene"] == "7"
    assert len(report["tension_curve"]) == 10
    assert report["tension_curve"][6]["value"] == 90        # index 7 (الذروة)
    assert report["weaknesses"][0]["suggestion"]
    assert report["weaknesses"][0]["scenes"] == ["4", "5"]
    assert report["verdict"]["strong"] is True


@test
def test_response_wrapped_in_code_fence_still_parses():
    fenced = "```json\n" + json.dumps(_valid_payload(), ensure_ascii=False) + "\n```"
    report = dr.parse_response(fenced, SCENES)
    assert report["scene_count"] == 10


@test
def test_scene_labels_include_suffix_like_35a():
    scenes = [_scene(i) for i in range(1, 6)]
    scenes[2]["scene_number"], scenes[2]["scene_suffix"] = 2, "A"   # "2A" مشهد فرعي
    payload = {
        "stages": [
            _stage("exposition", 1, 1), _stage("rising_action", 2, 2),
            _stage("climax", 3, 3), _stage("falling_action", 4, 4), _stage("resolution", 5, 5),
        ],
        "tension_curve": [10, 20, 30, 40, 50],
        "strengths": [{"text": "مشهد فرعي 2A واضح في السياق.", "indexes": [3]}],
        "weaknesses": [],
        "verdict": {"strong": True, "summary": "تجربة سليمة."},
    }
    report = dr.parse_response(json.dumps(payload, ensure_ascii=False), scenes)
    assert report["strengths"][0]["scenes"] == ["2A"], report["strengths"]
    assert report["stages"][2]["from_scene"] == "2A"


# --- كل ادّعاء لازم يترجع لمشهد حقيقي -----------------------------------------

@test
def test_out_of_range_index_in_stage_is_rejected():
    bad = _valid_payload()
    bad["stages"][0]["to_index"] = 999
    _raises(dr.DramaturgyError, dr.parse_response, json.dumps(bad, ensure_ascii=False), SCENES)


@test
def test_gap_between_stages_is_rejected():
    bad = _valid_payload()
    bad["stages"][1]["from_index"] = 4     # فجوة: المرحلة اللي قبلها بتخلص عند 2
    _raises(dr.DramaturgyError, dr.parse_response, json.dumps(bad, ensure_ascii=False), SCENES)


@test
def test_overlap_between_stages_is_rejected():
    bad = _valid_payload()
    bad["stages"][1]["from_index"] = 2     # تداخل مع نهاية exposition (لحد 2)
    _raises(dr.DramaturgyError, dr.parse_response, json.dumps(bad, ensure_ascii=False), SCENES)


@test
def test_stages_must_cover_all_scenes_to_the_end():
    bad = _valid_payload()
    bad["stages"][4]["to_index"] = 9       # الخاتمة بتوقف عند 9 مش 10 — مشهد أخير برّه أي مرحلة
    _raises(dr.DramaturgyError, dr.parse_response, json.dumps(bad, ensure_ascii=False), SCENES)


@test
def test_wrong_stage_order_is_rejected():
    bad = _valid_payload()
    bad["stages"][0], bad["stages"][1] = bad["stages"][1], bad["stages"][0]
    _raises(dr.DramaturgyError, dr.parse_response, json.dumps(bad, ensure_ascii=False), SCENES)


@test
def test_tension_curve_wrong_length_is_rejected():
    bad = _valid_payload()
    bad["tension_curve"] = [10, 20, 30]
    _raises(dr.DramaturgyError, dr.parse_response, json.dumps(bad, ensure_ascii=False), SCENES)


@test
def test_tension_curve_out_of_range_value_is_rejected():
    bad = _valid_payload()
    bad["tension_curve"][3] = 150
    _raises(dr.DramaturgyError, dr.parse_response, json.dumps(bad, ensure_ascii=False), SCENES)


@test
def test_weakness_without_out_of_range_indexes_is_dropped_not_fatal():
    payload = _valid_payload()
    payload["weaknesses"].append({
        "title": "ادّعاء مخترع", "stage": "climax", "from_index": 7, "to_index": 7,
        "issue": "مشكلة على مشهد مش موجود.", "why_it_matters": "...",
        "suggestion": "...", "indexes": [999],       # 999 برّه مدى الـ 10 مشاهد
    })
    report = dr.parse_response(json.dumps(payload, ensure_ascii=False), SCENES)
    titles = [w["title"] for w in report["weaknesses"]]
    assert "ادّعاء مخترع" not in titles, "ادّعاء بيشاور على مشهد وهمي لازم يتجاهل"
    assert len(report["weaknesses"]) == 1


@test
def test_weakness_without_suggestion_is_dropped():
    payload = _valid_payload()
    payload["weaknesses"][0].pop("suggestion")
    report = dr.parse_response(json.dumps(payload, ensure_ascii=False), SCENES)
    assert report["weaknesses"] == [], "نقطة ضعف من غير اقتراح عملي مايتحفظش"


# --- ردود بايظة: رسالة عربي واضحة مش traceback خام ----------------------------

@test
def test_non_json_response_fails_with_arabic_message_not_raw_exception():
    exc = _raises(dr.DramaturgyError, dr.parse_response, "مش JSON خالص، ده كلام عادي.", SCENES)
    assert exc.args and any("؀" <= ch <= "ۿ" for ch in exc.args[0]), "الرسالة لازم تكون عربي"


@test
def test_missing_stages_key_fails_gracefully():
    _raises(dr.DramaturgyError, dr.parse_response, json.dumps({"tension_curve": []}), SCENES)


@test
def test_wrong_top_level_type_fails_gracefully():
    _raises(dr.DramaturgyError, dr.parse_response, json.dumps([1, 2, 3]), SCENES)


@test
def test_stage_missing_summary_fails_gracefully():
    bad = _valid_payload()
    bad["stages"][0]["summary"] = ""
    _raises(dr.DramaturgyError, dr.parse_response, json.dumps(bad, ensure_ascii=False), SCENES)


@test
def test_missing_verdict_fails_gracefully():
    bad = _valid_payload()
    del bad["verdict"]
    _raises(dr.DramaturgyError, dr.parse_response, json.dumps(bad, ensure_ascii=False), SCENES)


@test
def test_completely_unexpected_shape_never_raises_raw_exception():
    # قيمة int بدل dict لعنصر في stages - يفجّر IndexError/TypeError عادي لو
    # مفيش حماية؛ هنا لازم يترجم لـ DramaturgyError زي أي عطل تاني في الشكل.
    bad = _valid_payload()
    bad["stages"][2] = 42
    exc = _raises(dr.DramaturgyError, dr.parse_response, json.dumps(bad, ensure_ascii=False), SCENES)
    assert isinstance(exc, dr.DramaturgyError)


# --- العرض بالعربي والإنجليزي، والـ SVG ---------------------------------------

@test
def test_to_sections_arabic_default_and_cites_scenes():
    report = dr.parse_response(json.dumps(_valid_payload(), ensure_ascii=False), SCENES)
    sections = dr.to_sections(report)
    headings = [s["heading"] for s in sections]
    assert "الحكم العام على البناء الدرامي" in headings
    assert "مناطق الدراما الضعيفة وإزاي نقويها" in headings
    weak_section = next(s for s in sections if "ضعيفة" in s["heading"])
    assert any("مشاهد 4, 5" in p for p in weak_section["paragraphs"]), weak_section["paragraphs"]
    assert any("إزاي نقويه" in p for p in weak_section["paragraphs"])


@test
def test_to_sections_english_translates_labels():
    report = dr.parse_response(json.dumps(_valid_payload(), ensure_ascii=False), SCENES)
    sections = dr.to_sections(report, lang="en")
    headings = [s["heading"] for s in sections]
    assert "Weak dramatic zones & how to strengthen them" in headings
    assert "Overall dramatic-structure verdict" in headings


@test
def test_render_svg_is_valid_svg_with_five_stage_bands():
    report = dr.parse_response(json.dumps(_valid_payload(), ensure_ascii=False), SCENES)
    svg = dr.render_svg(report, lang="ar")
    assert svg.startswith("<svg")
    assert svg.count("<rect") == 5, "لازم خمس مراحل مظللة"
    assert "polyline" in svg
    assert 'width="100%"' in svg, "لازم يتمدد على عرض الشاشة (موبايل) مش بيكسل ثابت"


@test
def test_render_svg_mirrors_for_rtl_vs_ltr():
    report = dr.parse_response(json.dumps(_valid_payload(), ensure_ascii=False), SCENES)
    svg_ar = dr.render_svg(report, lang="ar", width=100, height=50)
    svg_en = dr.render_svg(report, lang="en", width=100, height=50)
    assert svg_ar != svg_en, "اتجاه المنحنى لازم يختلف بين عربي (RTL) وإنجليزي"


@test
def test_render_svg_empty_curve_does_not_crash():
    report = dr.parse_response(json.dumps(_valid_payload(), ensure_ascii=False), SCENES)
    report = copy.deepcopy(report)
    report["tension_curve"] = []
    assert dr.render_svg(report) == ""


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
