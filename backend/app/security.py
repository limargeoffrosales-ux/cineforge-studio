"""Security primitives: PBKDF2 password hashing, JWT tokens, RBAC helpers."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from .config import settings

PBKDF2_ITERATIONS = 210_000


# ---------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$", 1)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS)
        return hmac.compare_digest(digest.hex(), expected)
    except Exception:
        return False


# -------------------------------------------------------------------- tokens
def create_access_token(user_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except Exception:
        return None


# ------------------------------------------------------------------------ RBAC
ROLE_LEVELS = {"viewer": 1, "creator": 2, "pro": 3, "admin": 99}


def role_at_least(role: str, minimum: str) -> bool:
    return ROLE_LEVELS.get(role, 0) >= ROLE_LEVELS.get(minimum, 0)
