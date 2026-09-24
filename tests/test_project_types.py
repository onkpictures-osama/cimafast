"""أنواع المشاريع — "فيديو قصير" بقى "فيديو" (المالك 2026-09-24).

    venv/bin/python tests/test_project_types.py

بيقفل: الأنواع الأربعة بالاسم الجديد، الاسم القديم بيتحوّل (في القاعدة مع
التشغيل، وفي أي طلب جاي بيه)، والفيديو على ريلز/تيك توك/شورتس رأسي 9:16.

قاعدة بيانات مؤقتة — عمرها ما بتلمس الإنتاج.
"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_TMP = tempfile.mkdtemp(prefix="cimafast-types-")
os.environ["STUDIO_DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ.pop("DATABASE_URL", None)

import database  # noqa: E402

database.init_db()

import project_types as pt  # noqa: E402
from database import fetch_all, run_query  # noqa: E402

_results = []


def test(fn):
    _results.append(fn)
    return fn


@test
def test_the_four_types():
    assert pt.TYPES == ["فيلم", "مسلسل", "إعلان", "فيديو"]
    assert pt.normalize_type("فيديو قصير") == "فيديو" and pt.normalize_type("فيلم") == "فيلم"
    assert "فيسبوك" in pt.PLATFORMS and "أخرى" in pt.PLATFORMS


@test
def test_old_projects_are_renamed_on_startup():
    run_query("INSERT INTO projects (name, project_type) VALUES ('قديم', 'فيديو قصير')")
    database.init_db()
    kinds = {r["project_type"] for r in fetch_all("SELECT project_type FROM projects")}
    assert kinds == {"فيديو"}, kinds


@test
def test_video_defaults_follow_the_platform():
    assert pt.technical_defaults("فيديو", "ريلز") == ("1080p", "رأسي", "9:16")
    assert pt.technical_defaults("فيديو", "يوتيوب") == ("1080p", "أفقي", "16:9")
    assert pt.technical_defaults("فيديو قصير", "تيك توك") == ("1080p", "رأسي", "9:16")


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
