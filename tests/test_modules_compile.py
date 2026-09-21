"""كل ملف بايثون في المشروع لازم يتكوّمپايل — أسيرشن عادي، مفيش pytest.

    venv/bin/python tests/test_modules_compile.py

ليه الاختبار ده موجود: enhanced_script_prompt.py فضل متكوميت وهو مكسور
(علامة اقتباس تلاتية سايبة جوه نص عربي) دورة كاملة من غير ما حد ياخد باله،
لأن مفيش حاجة بتستورده — فالتطبيق بيشتغل عادي والملف مكسور. أي ملف تاني
دلوقتي أو بعدين ممكن يقع في نفس الفخ، فبنعدّي عليهم كلهم هنا.
"""

from __future__ import annotations

import os
import py_compile
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# مجلدات مش بتاعتنا أو مش كود بيتشغّل
SKIP_DIRS = {"venv", ".git", "__pycache__", "backups", "uploads", ".cache", "node_modules"}

_results = []


def test(fn):
    _results.append(fn)
    return fn


def _project_sources():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in sorted(filenames):
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


@test
def test_every_module_compiles():
    broken = []
    # cfile مؤقت عشان مانلوّثش __pycache__ بتاع المشروع
    with tempfile.TemporaryDirectory() as tmp:
        cfile = os.path.join(tmp, "out.pyc")
        for path in _project_sources():
            try:
                py_compile.compile(path, doraise=True, cfile=cfile)
            except py_compile.PyCompileError as exc:
                broken.append(
                    f"{os.path.relpath(path, ROOT)}: {exc.msg.strip().splitlines()[-1]}")
    assert not broken, "ملفات مش بتكومپايل:\n  " + "\n  ".join(broken)


@test
def test_the_walk_actually_found_the_app():
    found = {os.path.relpath(p, ROOT) for p in _project_sources()}
    # لو الاستثناءات أكلت المشروع كله الاختبار فوق هيعدّي وهو فاضي
    for expected in ("app.py", "script_parser.py", "database.py", "theme/glass.py"):
        assert expected in found, f"المشي على الملفات فات {expected}"


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
