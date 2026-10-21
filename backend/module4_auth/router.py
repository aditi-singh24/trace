"""Module 4 endpoints: /api/v1/auth/*"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from module4_auth.dependencies import get_current_user, require_permission
from module4_auth.models import User
from module4_auth.permissions import MANAGE_USERS
from module4_auth.schemas import LoginRequest, TokenResponse, UserCreate, UserOut, UserUpdate
from module4_auth.security import DUMMY_HASH, create_access_token, hash_password, verify_password
from module5_engine.audit import record_audit_event
from shared.constants import SUPERVISOR, USER_ID_PREFIX
from shared.db import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _to_out(user: User) -> UserOut:
    out = UserOut.model_validate(user)
    # The flag only means something for supervisors.
    out.unblinded = bool(user.unblinded) and user.role == SUPERVISOR
    return out


def _next_user_id(db: Session) -> str:
    numbers = [
        int(uid[len(USER_ID_PREFIX):])
        for uid in db.scalars(select(User.id)).all()
        if uid.startswith(USER_ID_PREFIX) and uid[len(USER_ID_PREFIX):].isdigit()
    ]
    return f"{USER_ID_PREFIX}{(max(numbers) + 1 if numbers else 1):04d}"


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    username = body.username.strip().lower()
    user = db.scalar(select(User).where(User.username == username))
    password_ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)

    if user is None or not password_ok:
        record_audit_event("LOGIN_FAILED", user.id if user else "anonymous", {"username": username, "reason": "bad_credentials"})
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not user.active:
        record_audit_event("LOGIN_FAILED", user.id, {"username": username, "reason": "inactive"})
        raise HTTPException(status_code=403, detail="Account is inactive")

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    token, expires_in = create_access_token(user.id, user.role)
    record_audit_event("LOGIN_SUCCESS", user.id, {"username": username})
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return _to_out(user)


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    body: UserCreate,
    actor: User = Depends(require_permission(MANAGE_USERS)),
    db: Session = Depends(get_db),
):
    username = body.username.strip().lower()
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(status_code=409, detail="Username already exists")
    user = User(
        id=_next_user_id(db),
        username=username,
        password_hash=hash_password(body.password),
        role=body.role,
        unblinded=False,  # set only by the seed script, never via the API
        participant_id=body.participant_id,
        active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="User could not be created (conflict)")
    record_audit_event("USER_CREATED", actor.id, {"user_id": user.id, "role": user.role})
    return _to_out(user)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    body: UserUpdate,
    actor: User = Depends(require_permission(MANAGE_USERS)),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    changed = []
    if body.active is not None:
        if user.id == actor.id and body.active is False:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
        user.active = body.active
        changed.append("active")
    if body.password is not None:
        user.password_hash = hash_password(body.password)
        changed.append("password")
    db.commit()
    record_audit_event("USER_UPDATED", actor.id, {"user_id": user.id, "fields": changed})
    return _to_out(user)
