"""Password hashing (bcrypt) and JWT helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import bcrypt
import jwt

from shared.config import get_settings

JWT_ALGORITHM = "HS256"
MAX_PASSWORD_BYTES = 72  # bcrypt limit


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# Used to keep login timing similar when the username does not exist.
DUMMY_HASH = hash_password("not-a-real-password")


def create_access_token(user_id: str, role: str, expires_minutes: Optional[int] = None) -> Tuple[str, int]:
    """Return (token, expires_in_seconds)."""
    settings = get_settings()
    minutes = settings.jwt_expire_minutes if expires_minutes is None else expires_minutes
    now = datetime.now(timezone.utc)
    claims = {"sub": user_id, "role": role, "iat": now, "exp": now + timedelta(minutes=minutes)}
    token = jwt.encode(claims, settings.jwt_secret, algorithm=JWT_ALGORITHM)
    return token, minutes * 60


def decode_token(token: str) -> dict:
    """Raise jwt.PyJWTError if the token is invalid or expired."""
    return jwt.decode(
        token,
        get_settings().jwt_secret,
        algorithms=[JWT_ALGORITHM],
        options={"require": ["exp", "sub"]},
    )
