"""Module 5 endpoints: POST /randomization, GET /audit/entries, GET /audit/verify."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from module4_auth.dependencies import require_permission
from module4_auth.models import User
from module4_auth.permissions import RANDOMIZE, VIEW_AUDIT, can_see_arm
from module5_engine.audit import verify_chain
from module5_engine.models import AuditEntry
from module5_engine.randomization import RandomizationError, randomize
from shared.db import get_db

router = APIRouter(prefix="/api/v1", tags=["randomization-audit"])


class RandomizeRequest(BaseModel):
    participant_id: str = Field(min_length=1, max_length=16)


@router.post("/randomization", status_code=201)
def post_randomization(
    body: RandomizeRequest,
    user: User = Depends(require_permission(RANDOMIZE)),
    db: Session = Depends(get_db),
):
    try:
        result = randomize(body.participant_id, user.id, db=db)
        db.commit()  # assignment + chain entry land together
    except RandomizationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except Exception:
        db.rollback()
        raise
    # Concealment: blinded callers get arm = null, never the stored arm.
    if not can_see_arm(user):
        result["arm"] = None
    return result


@router.get("/audit/entries")
def list_audit_entries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _user: User = Depends(require_permission(VIEW_AUDIT)),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count()).select_from(AuditEntry)) or 0
    rows = db.scalars(
        select(AuditEntry).order_by(AuditEntry.seq).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        {
            "seq": r.seq,
            "event_type": r.event_type,
            "actor_id": r.actor_id,
            "payload": r.payload,
            "created_at": r.created_at,
            "prev_hash": r.prev_hash,
            "hash": r.hash,
        }
        for r in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/audit/verify")
def verify_audit_chain(
    _user: User = Depends(require_permission(VIEW_AUDIT)),
    db: Session = Depends(get_db),
):
    return verify_chain(db)
