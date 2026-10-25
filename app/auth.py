"""Accounts and sessions.

Passwords: PBKDF2-SHA256, 200,000 iterations, with a random 16-byte salt per
password. Only the hash is stored.

Sessions: a signed, expiring token in an HttpOnly cookie. The token is
`user_id.timestamp.signature`, where the signature is an HMAC over the first
two parts using SESSION_SECRET. Changing SESSION_SECRET signs everyone out.
"""
import hashlib
import hmac
import re
import secrets
import time

from app import config

COOKIE_NAME = "eg_session"
ITERATIONS = 200_000
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8
MAX_AGE_SECONDS = config.SESSION_MAX_AGE_DAYS * 86400


def validate_signup(email: str, password: str) -> str | None:
    if not EMAIL_PATTERN.match(email or ""):
        return "Enter a valid email address."
    if len(password or "") < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    return None


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
    )
    return hmac.compare_digest(digest.hex(), digest_hex)


def _sign(payload: str) -> str:
    return hmac.new(config.SESSION_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def make_session_token(user_id: int, now: float | None = None) -> str:
    ts = str(int(now if now is not None else time.time()))
    payload = f"{user_id}.{ts}"
    return f"{payload}.{_sign(payload)}"


def read_session_token(token: str, now: float | None = None) -> int | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    user_id_s, ts_s, signature = parts
    payload = f"{user_id_s}.{ts_s}"
    if not hmac.compare_digest(_sign(payload), signature):
        return None
    try:
        user_id, issued = int(user_id_s), int(ts_s)
    except ValueError:
        return None
    current = now if now is not None else time.time()
    if current - issued > MAX_AGE_SECONDS or issued - current > 300:
        return None
    return user_id


TOKEN_TTL_SECONDS = {"verify": 24 * 3600, "reset": 3600}


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_token() -> tuple[str, str]:
    """Returns (raw token for the link, hash to store). Only the hash is kept."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)
