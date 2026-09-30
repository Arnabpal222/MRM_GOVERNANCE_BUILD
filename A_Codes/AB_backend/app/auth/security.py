from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings


@dataclass(frozen=True)
class Principal:
    """The authenticated caller: one user acting in one of their roles."""

    user_id: str
    role: str
    full_name: str


def create_access_token(user_id: str, role: str) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {"sub": user_id, "role": role, "iat": now, "exp": now + timedelta(minutes=s.jwt_expiry_minutes)}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
