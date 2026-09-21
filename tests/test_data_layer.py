"""SQL بيعيش في repo.py بس — أسيرشن عادي، مفيش pytest.

    venv/bin/python tests/test_data_layer.py
"""
from __future__ import annotations

import ast
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_results = []

# المكان الوحيد المسموح: ui.py بيبني استعلام ديناميكي عام (أعمدة متغيرة) — مالوش
# شكل ثابت يتسمّى، فبيفضل هناك وموثق.
ALLOWED = {("ui.py", "fetch_all")}


def test(fn):
    _results.append(fn)
    return fn


def _ui_files():
    return ["app.py", "ui.py", "i18n.py"] + sorted(
        os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, "views", "*.py")))


@test
def test_screens_do_not_run_sql_directly():
    offenders = []
    for f in _ui_files():
        tree = ast.parse(open(os.path.join(ROOT, f), encoding="utf-8").read())
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) in ("fetch_all", "run_query", "run_delete"):
                is_constant_sql = n.args and isinstance(n.args[0], ast.Constant)
                if is_constant_sql or (f, n.func.id) not in ALLOWED:
                    offenders.append(f"{f}:{n.lineno} {n.func.id}")
    assert not offenders, "SQL in a screen — add a function to repo.py instead:\n  " + "\n  ".join(offenders)


@test
def test_every_repo_function_a_screen_calls_exists():
    import repo
    missing = []
    for f in _ui_files():
        tree = ast.parse(open(os.path.join(ROOT, f), encoding="utf-8").read())
        for n in ast.walk(tree):
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "repo":
                if not hasattr(repo, n.attr):
                    missing.append(f"{f}:{n.lineno} repo.{n.attr}")
    assert not missing, missing


@test
def test_repo_does_not_import_streamlit():
    # repo.py is shared with the board (Starlette); pulling Streamlit in would
    # couple the new frontend to the old one.
    src = open(os.path.join(ROOT, "repo.py"), encoding="utf-8").read()
    assert "import streamlit" not in src


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
