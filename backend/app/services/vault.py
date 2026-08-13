"""Fernet encryption for stored API keys (key derived from JWT_SECRET)."""
import base64
import hashlib

from cryptography.fernet import Fernet

from ..config import settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.JWT_SECRET.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


def masked(value: str) -> str:
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:2]}••••••{value[-4:]}"
