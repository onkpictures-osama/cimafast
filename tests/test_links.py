"""روابط الشاشات (H2) — ?project=&tab=.

    venv/bin/python tests/test_links.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import links  # noqa: E402

_results = []


def test(fn):
    _results.append(fn)
    return fn


@test
def test_a_good_link_is_read():
    assert links.parse({"project": "7", "tab": "scenes"}) == (7, "scenes")
    assert links.parse({"project": ["7"], "tab": ["shots"]}) == (7, "shots")      # parse_qs shape


@test
def test_bad_values_are_ignored_not_fatal():
    assert links.parse({"project": "abc", "tab": "<script>"}) == (None, None)
    assert links.parse({"project": "-3"}) == (None, None)
    assert links.parse({"project": "0"}) == (None, None)
    assert links.parse({}) == (None, None)


@test
def test_links_are_built_the_same_way_they_are_read():
    url = links.screen("/v1/", 12, "reports")
    assert url == "/v1/?project=12&tab=reports"
    from urllib.parse import parse_qs, urlparse
    assert links.parse(parse_qs(urlparse(url).query)) == (12, "reports")
    assert links.screen("/v1/") == "/v1/"


@test
def test_every_tab_has_a_label_and_the_order_matches_the_app():
    assert list(links.TABS) == ["import", "locations", "characters", "actors", "props", "scenes", "shots", "reports", "settings"]
    import i18n
    for key in links.TABS.values():
        assert key in i18n.UI_TEXT, key


@test
def test_unknown_tab_cannot_be_built():
    try:
        links.screen("/v1/", 1, "admin")
    except ValueError:
        return
    raise AssertionError("built a link to a tab that does not exist")


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
