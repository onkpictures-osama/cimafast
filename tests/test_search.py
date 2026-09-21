"""البحث العربي في المكتبات — أسيرشن عادي، مفيش pytest.

    venv/bin/python tests/test_search.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search import matches, normalize  # noqa: E402

_results = []


def test(fn):
    _results.append(fn)
    return fn


@test
def test_hamza_forms_are_one_letter():
    assert matches("اضاءة", "إضاءة المشهد")
    assert matches("إسكندرية", "كورنيش الاسكندرية")


@test
def test_taa_marbuta_and_alef_maqsura():
    assert matches("شقه", "شقة حسين")
    assert matches("مصطفي", "مصطفى")


@test
def test_diacritics_and_tatweel_are_ignored():
    assert matches("حسين", "حُسَيْن")
    assert matches("شقة", "شـــقة")


@test
def test_every_word_must_appear_somewhere():
    assert matches("حسين نوم", "شقة حسين - غرفة نوم")
    assert not matches("حسين مطبخ", "شقة حسين - غرفة نوم")


@test
def test_words_can_come_from_different_fields():
    assert matches("مريم مطبخ", "شقة مريم", "المطبخ")


@test
def test_empty_query_shows_everything():
    assert matches("", "anything") and matches("   ", "x")


@test
def test_english_is_case_insensitive():
    assert matches("int", "INT - Day")


@test
def test_none_fields_do_not_crash():
    assert not matches("x", None, None)
    assert normalize(None) == ""


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
