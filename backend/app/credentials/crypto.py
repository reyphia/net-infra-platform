"""Symmetric encryption for credential material at rest.

Uses Fernet (AES-128-CBC + HMAC) from `cryptography`. The key comes from
`ENCRYPTION_KEY` (never hardcoded, never logged). If it is unset, we refuse
to encrypt/decrypt rather than silently falling back to plaintext.
"""
from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class EncryptionNotConfigured(RuntimeError):
    pass


class DecryptionFailed(RuntimeError):
    pass


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().encryption_key
    if not key:
        raise EncryptionNotConfigured(
            "ENCRYPTION_KEY is not set. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"` "
            "and set it in your .env file before storing credentials."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode("utf-8"))


def decrypt(ciphertext: bytes) -> str:
    try:
        return _fernet().decrypt(ciphertext).decode("utf-8")
    except InvalidToken as exc:
        raise DecryptionFailed("Credential could not be decrypted; key mismatch or corrupted data.") from exc


def generate_key() -> str:
    return Fernet.generate_key().decode("utf-8")
