"""Seguridad: hash de contraseñas (bcrypt) y tokens JWT."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import settings

ALGORITHM = "HS256"
COMMON_PASSWORDS = {
    "1234567890",
    "administrador",
    "contraseña",
    "password",
    "password123",
    "qwerty1234",
}


def hash_password(plain: str) -> str:
    if len(plain.encode("utf-8")) > 72:
        raise ValueError("La contraseña no puede superar 72 bytes.")
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def validate_password(plain: str, username: str, current_hash: str | None = None) -> None:
    size = len(plain.encode("utf-8"))
    if len(plain) < 10:
        raise ValueError("La contraseña debe tener al menos 10 caracteres.")
    if size > 72:
        raise ValueError("La contraseña no puede superar 72 bytes.")
    if plain.casefold() in COMMON_PASSWORDS:
        raise ValueError("La contraseña es demasiado común.")
    if username and username.casefold() in plain.casefold():
        raise ValueError("La contraseña no puede contener el nombre de usuario completo.")
    if current_hash and verify_password(plain, current_hash):
        raise ValueError("La nueva contraseña debe ser distinta a la actual.")


def create_access_token(subject: str, token_version: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "ver": token_version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        if not payload.get("sub") or not isinstance(payload.get("ver"), int):
            return None
        return payload
    except jwt.PyJWTError:
        return None
