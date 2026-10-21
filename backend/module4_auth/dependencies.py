"""FastAPI dependencies: current user and permission guards."""
from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from module4_auth.models import User
from module4_auth.permissions import can_access_participant, check_permission
from module4_auth.security import decode_token
from shared.db import get_db

_bearer = HTTPBearer(auto_error=False)
_UNAUTH_HEADERS = {"WWW-Authenticate": "Bearer"}


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """401 if not logged in or token invalid/expired, 403 if the account is inactive."""
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Not authenticated", headers=_UNAUTH_HEADERS)
    try:
        claims = decode_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token", headers=_UNAUTH_HEADERS)
    user = db.get(User, claims["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token", headers=_UNAUTH_HEADERS)
    if not user.active:
        raise HTTPException(status_code=403, detail="Account is inactive")
    return user


def require_permission(action: str):
    """Dependency factory: `user = Depends(require_permission(RANDOMIZE))`."""

    def _dependency(user: User = Depends(get_current_user)) -> User:
        if not check_permission(user, action):
            raise HTTPException(status_code=403, detail="Not allowed")
        return user

    return _dependency


def require_participant_access(user: User, participant_id: str) -> None:
    """Call inside an endpoint: 403 if a patient reaches for someone else's record."""
    if not can_access_participant(user, participant_id):
        raise HTTPException(status_code=403, detail="Not allowed")
