"""Request/response models for /auth."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from module4_auth.security import MAX_PASSWORD_BYTES
from shared.constants import PATIENT, ROLES

MIN_PASSWORD_LENGTH = 8


def _check_password(value: str) -> str:
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"password must be at most {MAX_PASSWORD_BYTES} bytes")
    return value


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    role: str
    unblinded: bool
    participant_id: Optional[str]
    active: bool
    created_at: datetime
    last_login_at: Optional[datetime]


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str
    role: str
    participant_id: Optional[str] = Field(default=None, max_length=16)

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        return _check_password(v)

    @field_validator("role")
    @classmethod
    def _role(cls, v: str) -> str:
        if v not in ROLES:
            raise ValueError(f"role must be one of {ROLES}")
        return v

    @model_validator(mode="after")
    def _participant_link(self):
        if self.role == PATIENT and not self.participant_id:
            raise ValueError("PATIENT users require participant_id")
        if self.role != PATIENT and self.participant_id:
            raise ValueError("participant_id is only for PATIENT users")
        return self


class UserUpdate(BaseModel):
    """Only these fields can change. `unblinded` is deliberately not here."""

    model_config = ConfigDict(extra="forbid")

    active: Optional[bool] = None
    password: Optional[str] = None

    @field_validator("password")
    @classmethod
    def _password(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _check_password(v)
