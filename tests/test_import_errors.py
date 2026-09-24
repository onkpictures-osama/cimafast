#!/usr/bin/env python3
"""اختبار رسايل الفشل في تبويب استيراد السيناريو.

الخاصية اللي بنحميها: أي خطأ بيحصل جوّه الشاشة دي لازم يوصل للمستخدم
بكلام يفهمه، والتفاصيل التقنية تروح للوج السيرفر — مش للشاشة.

الشرارة: يوزر رفع سيناريو على /v1 وضغط "ابدأ التحليل"، فطلع له على طول
"Read-only file system: '/var/lib/cimafast/ai-jobs/inbox/…txt.tmp' [Errno 30]".
ده مبيقولش لمخرج يعمل إيه، وكمان بيكشف مسارات السيرفر.
"""
import errno
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "views"))

import i18n
import import_tab

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"{'✅' if cond else '❌'} {name}" + (f" → {detail}" if detail else ""))


_logged = []


class _Capture(logging.Handler):
    def emit(self, record):
        _logged.append(self.format(record))


logging.getLogger("cimafast.import").addHandler(_Capture())


def _raise(exc):
    """لازم نرميه فعلًا: _user_error بتستخدم logging.exception اللي
    محتاجة استثناء شغال عشان تسجّل الـ traceback."""
    try:
        raise exc
    except Exception as e:                                   # noqa: BLE001
        return import_tab._user_error(e, "ai start")


# --- 1) خطأ نظام التشغيل ما يوصلش للشاشة -------------------------------
_logged.clear()
msg = _raise(OSError(errno.EROFS, "Read-only file system",
                     "/var/lib/cimafast/ai-jobs/inbox/11-f63e43c2.txt.tmp"))
check("مفيش رقم errno على الشاشة", "Errno" not in msg, msg)
check("مفيش نص الخطأ الإنجليزي على الشاشة", "Read-only" not in msg, msg)
check("مفيش مسار سيرفر على الشاشة", "/var/lib" not in msg, msg)
check("المستخدم بيشوف رسالة عربي مفهومة", import_tab._ERR_TITLE in msg, msg)

logged = "\n".join(_logged)
check("الخطأ الحقيقي اتسجّل في اللوج",
      "Read-only file system" in logged and "ai start" in logged)
check("اللوج فيه traceback", "Traceback" in logged)

ref = msg.rsplit("`", 2)[-2] if "`" in msg else ""
check("الكود المرجعي بيظهر للمستخدم", len(ref) == 8, ref)
check("نفس الكود موجود في اللوج عشان الدعم يلاقيه", ref and ref in logged, ref)

# --- 2) رسايلنا العربية بتعدّي زي ما هي --------------------------------
_own = "فيه تحليل شغال بالفعل لنفس المشروع."
check("رسالة RuntimeError العربية بتوصل زي ما هي",
      _raise(RuntimeError(_own)) == _own)

# --- 3) كل مفتاح عربي جديد له إنجليزي ----------------------------------
for _key in (import_tab._ERR_TITLE, import_tab._ERR_BODY,
             "مقدرناش نكمّل التحليل. ملفك زي ما هو، تقدر تجرّب تاني.",
             "تفاصيل تقنية"):
    check(f"ترجمة إنجليزي موجودة: {_key[:28]}…",
          bool(i18n.TRANSLATIONS.get(_key, "").strip()))

# --- 4) مفيش st.error بيعرض الاستثناء الخام راجع تاني -------------------
# بنفحص الشجرة نفسها بـ ast مش بـ grep على النص، عشان التعليقات والـ
# docstrings اللي بتشرح الباج القديم ما تعديش كأنها الباج.
import ast

_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "views", "import_tab.py")
_tree = ast.parse(open(_path, encoding="utf-8").read(), _path)

# أسامي الاستثناءات المتمسكة في الملف: except ... as <name>
_caught = {n.name for n in ast.walk(_tree)
           if isinstance(n, ast.ExceptHandler) and n.name}


def _uses_raw_exception(node):
    """اسم استثناء بيتعرض على الشاشة من غير ما يعدّي على _user_error."""
    if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_user_error":
        return False                      # ده بالظبط الطريق الآمن
    if isinstance(node, ast.Name) and node.id in _caught:
        return True
    return any(_uses_raw_exception(child) for child in ast.iter_child_nodes(node))


_leaks = [(n.lineno, ast.unparse(a)[:60])
          for n in ast.walk(_tree)
          if isinstance(n, ast.Call)
          and getattr(n.func, "attr", "") in ("error", "warning", "exception")
          for a in n.args if _uses_raw_exception(a)]

check("مفيش st.error بيعرض الاستثناء الخام", not _leaks, str(_leaks))

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
