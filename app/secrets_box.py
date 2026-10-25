"""Encrypts merchant PayPal credentials at rest (Fernet: AES-128-CBC + HMAC).

The key comes from CREDENTIAL_KEY. Without it, credentials cannot be saved.
Losing the key makes saved credentials unreadable; merchants would reconnect.
"""
from cryptography.fernet import Fernet, InvalidToken

from app import config


class KeyMissing(Exception):
    """Raised when credentials cannot be encrypted or decrypted."""


def _fernet() -> Fernet:
    if not config.CREDENTIAL_KEY:
        raise KeyMissing("CREDENTIAL_KEY is not set in .env. Generate one and restart the app.")
    try:
        return Fernet(config.CREDENTIAL_KEY.encode("utf-8"))
    except ValueError:
        raise KeyMissing("CREDENTIAL_KEY is not a valid Fernet key.")


def encrypt(text: str) -> str:
    return _fernet().encrypt(text.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        raise KeyMissing("Saved credentials cannot be read with the current CREDENTIAL_KEY.")
