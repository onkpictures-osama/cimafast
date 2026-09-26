"""مصادقة الدخول لـ CimaFast Studio.

الحسابات بتتخزن كـ (اسم مستخدم -> hash لكلمة السر) بصيغة PBKDF2-SHA256.
مفيش كلمة سر مكتوبة صريحة لا في الكود ولا في الريبو — الـ hash نفسه بيتقرا من
`/etc/cimafast/secrets.toml` (برّه شجرة git) أو من متغير بيئة وقت التطوير.

الملف ده منطق خالص من غير أي واجهة، عشان يتجرّب لوحده من غير Streamlit.

لتوليد hash لكلمة سر جديدة:

    venv/bin/python auth.py hash
"""

import base64
import hashlib
import hmac
import json
import os
import time

# الصيغة: pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>
ALGORITHM = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 600_000
SALT_BYTES = 16
_HASH_BYTES = 32

# المتغير ده هو الاستثناء الوحيد اللي بيخلي البرنامج يفتح من غير حسابات أصلًا،
# ولازم يتحط صراحةً. السيرفر المنشور عمره ما هيبقى متظبط عنده، فلو الحسابات
# ضاعت لأي سبب البرنامج بيتقفل بدل ما يفتح للناس (fail closed).
ALLOW_NO_LOGIN_ENV = "CIMAFAST_ALLOW_NO_PASSWORD"
USERS_ENV = "CIMAFAST_USERS"
USERS_SECRET_KEY = "users"


def _b64encode(raw):
    return base64.b64encode(raw).decode("ascii")


def _b64decode(text):
    return base64.b64decode(text.encode("ascii"), validate=True)


def hash_password(password, iterations=DEFAULT_ITERATIONS, salt=None):
    """بيحوّل كلمة السر لـ hash جاهز يتحط في ملف الأسرار."""
    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")
    if salt is None:
        salt = os.urandom(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations, dklen=_HASH_BYTES
    )
    return f"{ALGORITHM}${iterations}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password, stored):
    """بيقارن كلمة السر المكتوبة بالـ hash المتخزن — مقارنة ثابتة الوقت.

    أي hash مكسور أو بصيغة غير معروفة بيرجّع False بدل ما يرمي استثناء، عشان
    غلطة في ملف الأسرار متفتحش الباب ومتوقّعش البرنامج."""
    if not isinstance(password, str) or not isinstance(stored, str):
        return False
    parts = stored.strip().split("$")
    if len(parts) != 4:
        return False
    algorithm, iterations_text, salt_text, hash_text = parts
    if algorithm != ALGORITHM:
        return False
    try:
        iterations = int(iterations_text)
        salt = _b64decode(salt_text)
        expected = _b64decode(hash_text)
    except (ValueError, TypeError, base64.binascii.Error):
        return False
    if iterations < 1 or not salt or not expected:
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations, dklen=len(expected)
    )
    return hmac.compare_digest(candidate, expected)


def normalize_username(username):
    """أسماء المستخدمين مش حساسة لحالة الحروف ولا للمسافات الزيادة — الناس
    بتكتب من الموبايل والكيبورد بيكبّر أول حرف لوحده."""
    if not isinstance(username, str):
        return ""
    return username.strip().lower()


def _clean_users(raw):
    """بيطلّع قاموس نضيف {اسم مستخدم متطبّع: hash} من أي شكل داخل."""
    users = {}
    if not raw:
        return users
    try:
        items = raw.items()
    except AttributeError:
        return users
    for username, stored in items:
        name = normalize_username(username)
        if not name or not isinstance(stored, str) or not stored.strip():
            continue
        users[name] = stored.strip()
    return users


def _users_from_env():
    """وقت التطوير المحلي: CIMAFAST_USERS بصيغة JSON {"osama": "pbkdf2_sha256$..."}"""
    raw = (os.environ.get(USERS_ENV) or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return _clean_users(parsed)


def _users_from_secrets():
    """على السيرفر: قسم [users] جوه secrets.toml. لو الملف ناقص خالص st.secrets
    بيرمي استثناء، فبنمسكه هنا ونرجّع فاضي بدل ما البرنامج يقع."""
    try:
        import streamlit as st

        return _clean_users(dict(st.secrets.get(USERS_SECRET_KEY) or {}))
    except Exception:
        return {}


def resolve_users():
    """بيجيب الحسابات من متغير البيئة الأول وبعدين من st.secrets — نفس ترتيب
    الأولوية القديم بتاع APP_PASSWORD."""
    return _users_from_env() or _users_from_secrets()


def no_login_allowed():
    return os.environ.get(ALLOW_NO_LOGIN_ENV, "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def authenticate(username, password, users):
    """بيرجّع اسم المستخدم المتطبّع لو الدخول صح، وإلا None.

    لو الاسم مش موجود بنعمل hash وهمي برضه عشان الوقت اللي بياخده الرد ميفرقش
    بين "اسم غلط" و"كلمة سر غلط" (منع تخمين أسماء المستخدمين)."""
    name = normalize_username(username)
    stored = (users or {}).get(name)
    if stored is None:
        verify_password(password if isinstance(password, str) else "", _DUMMY_HASH)
        return None
    if verify_password(password, stored):
        return name
    # كلمة سر منسوخة من رسالة بتيجي أحيانًا بمسافة أو سطر في الآخر (أول يوم
    # يوزرز جداد: حد حاول ٥ مرات في ٦ ثواني). بنجرب من غير المسافات اللي على الأطراف.
    if isinstance(password, str) and password.strip() != password and verify_password(password.strip(), stored):
        return name
    return None


# hash وهمي لكلمة سر عشوائية، بيتحسب مرة واحدة وقت التحميل عشان المقارنة
# الوهمية فوق تاخد نفس وقت المقارنة الحقيقية.
_DUMMY_HASH = hash_password(base64.b64encode(os.urandom(18)).decode("ascii"))


# ---------------------------------------------------------------------------
# توكن الجلسة: عشان الريفريش ميطلّعش المستخدم برّه.
#
# حالة الدخول كانت متخزنة في st.session_state بس، وده مربوط بالـ websocket،
# يعني أي ريفريش بيفتح جلسة جديدة فاضية والمستخدم بيتقفل برّه. الحل إننا نسيب
# مع المتصفح توكن موقّع (HMAC) في كوكي. التوكن مفيهوش كلمة السر ولا الـ hash —
# بس اسم المستخدم وتاريخ الانتهاء وتوقيع.
#
# الاسم متخزن base64، مش نص خام: الفاصل بين أجزاء التوكن هو النقطة، فاسم فيه
# نقطة (زي "osama.k") كان هيكسّر التقسيم ويمنع صاحبه من الدخول للأبد.
# ---------------------------------------------------------------------------

SESSION_COOKIE_NAME = "cf_session"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 30   # 30 يوم


def _b64url(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(text):
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text.encode("ascii") + pad.encode("ascii"))


def _session_secret():
    """بندوّر على السر في المتغيرات الأول وبعدين في secrets.toml.

    بنقبل أكتر من اسم عشان أي إعداد قديم أو جديد يفضل شغال. لو مفيش سر خالص
    بنرجّع None والميزة بتتعطّل بهدوء (المستخدم بيسجل دخول عادي)."""
    for name in ("CIMAFAST_SESSION_SECRET", "CIMAFAST_COOKIE_SECRET"):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    try:
        import streamlit as st

        value = st.secrets.get("auth", {}).get("cookie_secret")
        if value:
            return str(value).strip()
        value = st.secrets.get("SESSION_SECRET")
        if value:
            return str(value).strip()
    except Exception:
        pass
    return None


def make_session_token(username, secret=None):
    """بيرجّع توكن جلسة جاهز يتحط في كوكي، أو None لو مفيش سر متظبط."""
    secret = _session_secret() if secret is None else secret
    if not secret:
        return None
    name = normalize_username(username)
    if not name:
        return None
    expiry = int(time.time()) + SESSION_TTL_SECONDS
    payload = f"{_b64url(name.encode('utf-8'))}.{expiry}"
    sig = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_session_token(token, users, secret=None):
    """بيرجّع اسم المستخدم لو التوكن صحيح ولسه ساري وصاحبه لسه له حساب،
    وإلا None. أي شك بسيط بيرجّع None بدل ما يفتح الباب."""
    secret = _session_secret() if secret is None else secret
    if not secret or not token or not isinstance(token, str):
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    name_text, expiry_text, sig = parts
    payload = f"{name_text}.{expiry_text}"
    expected = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        expiry = int(expiry_text)
    except (ValueError, TypeError):
        return None
    if expiry < int(time.time()):
        return None
    try:
        name = _b64url_decode(name_text).decode("utf-8")
    except Exception:
        name = name_text            # توكنات قديمة كانت بتحط الاسم نص خام
    name = normalize_username(name)
    if name not in (users or {}):
        return None
    return name




def _cli():
    import getpass
    import sys

    args = sys.argv[1:]
    if not args or args[0] != "hash":
        print(__doc__.strip())
        print("\nusage: python auth.py hash [--stdin]")
        return 1
    if "--stdin" in args:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Repeat: "):
            print("Passwords do not match.", file=sys.stderr)
            return 1
    if not password:
        print("Empty password.", file=sys.stderr)
        return 1
    print(hash_password(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
