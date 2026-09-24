"""F2 — مين يقدر يعمل إيه جوه الشركة.

الجدول CAPABILITIES هو المكان الوحيد اللي بيحدد صلاحيات كل دور. التطبيق بيقول
"المستخدم ده بدوره كذا" مرة واحدة في كل تشغيل، وكل كتابة في قاعدة البيانات
(database.run_query وrepo._tx) بتسأل require("edit") قبل ما تكتب — فمفيش شاشة
تقدر تنسى الفحص.

    permissions.acting_as("viewer")   # طلب واحد في الواجهة الجديدة
    permissions.set_resolver(fn)      # Streamlit: الدور من session_state
    permissions.system()              # كتابات النظام نفسه (آخر دخول، كلمة سرّي)

من غير دور (worker، سكريبتات، اختبارات قديمة) مفيش قيود: القيود على المستخدمين
مش على السيرفر نفسه.
"""
from __future__ import annotations

import contextlib
import contextvars

_ALL = {"operator", "admin", "producer", "manager", "department"}

CAPABILITIES = {
    "edit": _ALL,                                             # أي تعديل في بيانات المشاريع
    "run_ai": _ALL,                                           # تحليل سكريبت / توليد صور (بيكلّف فلوس)
    "create_project": {"operator", "admin", "producer", "manager"},
    "delete_project": {"operator", "admin"},
    "manage_team": {"operator", "admin"},
    "view_audit": {"operator", "admin"},                      # F3: سجل النشاط بيكشف شغل كل الفريق
}

MESSAGES = {
    "edit": "حسابك مشاهدة فقط في الشركة دي — مينفعش تعدّل. كلّم مدير المشروع لو محتاج صلاحية تعديل.",
    "run_ai": "حسابك مشاهدة فقط — مينفعش تشغّل تحليل أو توليد صور.",
    "create_project": "إنشاء مشروع جديد لمدير المشروع أو المنتج أو مدير الإنتاج بس.",
    "delete_project": "حذف مشروع لمدير المشروع بس.",
    "manage_team": "إدارة الفريق لمدير المشروع بس.",
    "view_audit": "سجل النشاط لمدير المشروع بس.",
}


class Denied(PermissionError):
    def __init__(self, capability):
        self.capability = capability
        super().__init__(MESSAGES.get(capability, "مش مسموح"))


_ROLE = contextvars.ContextVar("cimafast_role", default=None)
_SYSTEM = contextvars.ContextVar("cimafast_system", default=False)
_resolver = None


def can(role, capability):
    return role in CAPABILITIES[capability]


def set_resolver(fn):
    """Streamlit بيشغّل كل rerun (والـ callbacks قبله) في thread جديد، فالـ
    contextvar مش بيعيش بين الـ runs. الـ resolver بيقرا الدور من session_state."""
    global _resolver
    _resolver = fn


def current_role():
    if _SYSTEM.get():
        return None
    role = _ROLE.get()
    if role is not None:
        return role
    if _resolver is not None:
        try:
            return _resolver()
        except Exception:  # noqa: BLE001 — مفيش جلسة Streamlit في الـ thread ده
            return None
    return None


def require(capability):
    role = current_role()
    if role is not None and not can(role, capability):
        raise Denied(capability)


def act_as(role):
    """للطلب الحالي بس (كل طلب في Starlette ليه context منفصل)."""
    _ROLE.set(role)


@contextlib.contextmanager
def acting_as(role):
    token = _ROLE.set(role)
    try:
        yield
    finally:
        _ROLE.reset(token)


@contextlib.contextmanager
def system():
    token = _SYSTEM.set(True)
    try:
        yield
    finally:
        _SYSTEM.reset(token)
