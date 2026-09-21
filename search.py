"""البحث في المكتبات (أماكن، شخصيات، إكسسوارات، مشاهد).

العربي بيتكتب بأكتر من شكل لنفس الكلمة: أ إ آ ا، ة ه، ى ي، وتشكيل اختياري.
لو البحث قارن الحروف زي ما هي، اللي كتب «اضاءة» مش هيلاقي «إضاءة». فالاتنين
(الاستعلام والنص) بيتوحدوا الأول وبعدين بيتقارنوا.
"""

from __future__ import annotations

import re
import unicodedata

_ALEF = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي"})
_TATWEEL = "ـ"
_SPACES = re.compile(r"\s+")


def normalize(text) -> str:
    """نسخة من النص للمقارنة بس — مش للعرض."""
    if text is None:
        return ""
    s = unicodedata.normalize("NFKC", str(text))
    # التشكيل (فتحة، ضمة، شدة...) علامات مركّبة — بتتشال
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace(_TATWEEL, "").translate(_ALEF).casefold()
    return _SPACES.sub(" ", s).strip()


def matches(query, *fields) -> bool:
    """True لو كل كلمة في الاستعلام موجودة في أي حقل من الحقول.

    استعلام فاضي بيطابق كل حاجة، عشان القايمة تبان كاملة قبل ما حد يكتب.
    """
    q = normalize(query)
    if not q:
        return True
    haystack = " ".join(normalize(f) for f in fields if f)
    return all(word in haystack for word in q.split(" "))
