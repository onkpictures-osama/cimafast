"""فلاج الشكل: ‎?theme=glass‎ بيشغّل التصميم الجديد.

الافتراضي دايمًا ‎classic‎ — الـ 12 مستخدم على الهوا بيفضلوا شايفين نفس
الشكل لحد ما المالك يوافق على التبديل. مفيش أي مسار بيرجّع ‎glass‎ من غير
طلب صريح في الـ URL (أو متغير بيئة للاختبار المحلي).
"""

from __future__ import annotations

import os

GLASS = "glass"
CLASSIC = "classic"

_SESSION_KEY = "_cf_theme_variant"


def resolve_variant(st=None):
    """بترجّع ‎"glass"‎ أو ‎"classic"‎ وتفضل ثابتة على طول الجلسة.

    الترتيب: الـ query param الأول (لأنه اللي المستخدم كتبه)، وبعدين آخر
    قيمة متذكرة في الجلسة (عشان أي rerun مش شايل الـ param ميرجعش الشكل
    القديم في نص الشغل)، وبعدين متغير البيئة ‎CIMAFAST_THEME‎ للاختبار.
    """
    if st is None:
        import streamlit as st  # noqa: PLC0415

    raw = None
    try:
        raw = st.query_params.get("theme")
    except Exception:
        # ‎AppTest‎ وبعض السياقات مفيهاش query params
        raw = None
    if not raw:
        raw = st.session_state.get(_SESSION_KEY)
    if not raw:
        raw = os.environ.get("CIMAFAST_THEME")

    variant = GLASS if str(raw or "").strip().lower() == GLASS else CLASSIC
    st.session_state[_SESSION_KEY] = variant
    return variant


def is_glass(st=None):
    return resolve_variant(st) == GLASS
