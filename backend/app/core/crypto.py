from cryptography.fernet import Fernet
from fastapi import HTTPException

from app.core.config import get_settings


def cipher() -> Fernet:
    try:
        return Fernet(get_settings().token_encryption_key.encode())
    except ValueError as exc:
        raise HTTPException(503, "OAuth token encryption is not configured") from exc


def encrypt(value: str) -> str:
    return cipher().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return cipher().decrypt(value.encode()).decode()
