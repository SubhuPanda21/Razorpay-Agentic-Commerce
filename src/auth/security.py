"""Password hashing + lightweight signed session tokens. Stdlib only -
no extra dependency, no external auth service."""
import base64
import hashlib
import hmac
import os
import time

from src.config import settings

SESSION_MAX_AGE = 60 * 60 * 24 * 14  # 14 days


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_b64, hash_b64 = stored.split("$")
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def create_session_token(merchant_id: int) -> str:
    payload = f"{merchant_id}:{int(time.time()) + SESSION_MAX_AGE}"
    sig = hmac.new(settings.session_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(payload.encode()).decode() + "." + sig


def verify_session_token(token: str) -> int | None:
    try:
        payload_b64, sig = token.split(".")
        payload = base64.urlsafe_b64decode(payload_b64.encode()).decode()
        expected = hmac.new(settings.session_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        merchant_id_str, expiry_str = payload.split(":")
        if int(time.time()) > int(expiry_str):
            return None
        return int(merchant_id_str)
    except Exception:
        return None
