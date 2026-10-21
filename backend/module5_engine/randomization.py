"""Stratified block randomization (1:1, block size from constants).

Reads the participants table (Module 2) through the listed columns only.
"""
from __future__ import annotations

import hashlib
import random
import secrets
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from module5_engine.audit import lock_chain, record_audit_event
from module5_engine.models import AllocationBlock, Assignment
from shared.config import get_settings
from shared.constants import (
    ARMS,
    BLOCK_SIZE,
    HBA1C_CATEGORIES,
    RAND_NUMBER_PREFIX,
    THERAPY_VALUES,
    USE_THERAPY_FACTOR,
)
from shared.db import get_session_factory

NUMBER_LOCK_KEY = 727002  # Postgres advisory lock for randomization numbers / slot hand-out

PARTICIPANT_COLUMNS = (
    "participant_id, site_id, hba1c_cat, therapy, eligibility_status, consent_status, baseline_complete"
)


class RandomizationError(Exception):
    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ParticipantNotFound(RandomizationError):
    status_code = 404


class PrerequisiteNotMet(RandomizationError):
    status_code = 400


class AlreadyRandomized(RandomizationError):
    status_code = 409


def build_stratum_key(site_id: str, hba1c_cat: str, therapy: Optional[str]) -> str:
    """site_id|hba1c_cat|therapy, e.g. SITE-01|HIGH|STABLE (therapy dropped if the factor is off)."""
    parts = [site_id, hba1c_cat]
    if USE_THERAPY_FACTOR:
        parts.append(therapy)
    return "|".join(parts)


def block_arms_from_seed(seed: str) -> List[str]:
    """Deterministic shuffled block for a seed: the same seed always gives the same order."""
    arms = [a for a in ARMS for _ in range(BLOCK_SIZE // len(ARMS))]
    random.Random(seed).shuffle(arms)
    return arms


def _new_block_seed(stratum_key: str, block_no: int) -> str:
    master = get_settings().randomization_seed
    if master:
        return hashlib.sha256(f"{master}|{stratum_key}|{block_no}".encode("utf-8")).hexdigest()[:32]
    return secrets.token_hex(16)


def _create_block(db: Session, stratum_key: str, block_no: int) -> None:
    seed = _new_block_seed(stratum_key, block_no)
    for position, arm in enumerate(block_arms_from_seed(seed), start=1):
        db.add(AllocationBlock(stratum_key=stratum_key, block_no=block_no, position=position,
                               arm=arm, used=False, seed=seed))
    db.flush()


def _next_slot(db: Session, stratum_key: str) -> AllocationBlock:
    def first_unused():
        return db.scalar(
            select(AllocationBlock)
            .where(AllocationBlock.stratum_key == stratum_key, AllocationBlock.used.is_(False))
            .order_by(AllocationBlock.block_no, AllocationBlock.position)
            .limit(1)
            .with_for_update()
        )

    slot = first_unused()
    if slot is None:
        last_block = db.scalar(
            select(func.max(AllocationBlock.block_no)).where(AllocationBlock.stratum_key == stratum_key)
        ) or 0
        _create_block(db, stratum_key, last_block + 1)
        slot = first_unused()
    return slot


def _read_participant(db: Session, participant_id: str):
    row = db.execute(
        text(f"SELECT {PARTICIPANT_COLUMNS} FROM participants WHERE participant_id = :pid"),
        {"pid": participant_id},
    ).mappings().first()
    if row is None:
        raise ParticipantNotFound(f"Participant {participant_id} not found")
    return row


def _check_prerequisites(row) -> None:
    problems = []
    if row["eligibility_status"] != "ELIGIBLE":
        problems.append("eligibility is not ELIGIBLE")
    if row["consent_status"] != "OBTAINED":
        problems.append("consent is not OBTAINED")
    if not row["baseline_complete"]:
        problems.append("baseline data is incomplete")
    if not row["site_id"]:
        problems.append("site is missing")
    if row["hba1c_cat"] not in HBA1C_CATEGORIES:
        problems.append("HbA1c category is missing or invalid")
    if USE_THERAPY_FACTOR and row["therapy"] not in THERAPY_VALUES:
        problems.append("therapy value is missing or invalid")
    if problems:
        raise PrerequisiteNotMet("Cannot randomize: " + "; ".join(problems))


def _randomize(db: Session, participant_id: str, actor_id: str) -> dict:
    lock_chain(db)  # also serialises everything below on PostgreSQL
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": NUMBER_LOCK_KEY})

    row = _read_participant(db, participant_id)
    if db.scalar(select(Assignment.id).where(Assignment.participant_id == participant_id)) is not None:
        raise AlreadyRandomized(f"Participant {participant_id} is already randomized")
    _check_prerequisites(row)

    stratum_key = build_stratum_key(row["site_id"], row["hba1c_cat"], row["therapy"])
    slot = _next_slot(db, stratum_key)
    slot.used = True

    number = (db.scalar(select(func.count()).select_from(Assignment)) or 0) + 1
    randomization_number = f"{RAND_NUMBER_PREFIX}{number:04d}"
    assigned_at = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")

    db.add(Assignment(
        participant_id=participant_id,
        randomization_number=randomization_number,
        stratum_key=stratum_key,
        block_no=slot.block_no,
        arm=slot.arm,
        assigned_at=assigned_at,
        assigned_by=actor_id,
    ))
    try:
        db.flush()
    except IntegrityError:
        raise AlreadyRandomized(f"Participant {participant_id} is already randomized")

    # Chain entry joins this same transaction. The arm is deliberately NOT in the payload:
    # blinded supervisors can read the audit log.
    record_audit_event(
        "RANDOMIZED",
        actor_id,
        {
            "participant_id": participant_id,
            "randomization_number": randomization_number,
            "stratum_key": stratum_key,
            "block_no": slot.block_no,
        },
        db=db,
    )
    return {
        "message": "Participant randomized successfully",
        "participant_id": participant_id,
        "randomization_number": randomization_number,
        "arm": slot.arm,  # callers MUST pass this through can_see_arm before returning it
    }


def randomize(participant_id: str, actor_id: str, db: Optional[Session] = None) -> dict:
    """Randomize a participant. With `db`, the caller owns the transaction (and commits);
    without it, a session is opened and committed here. Raises RandomizationError subclasses."""
    if db is not None:
        return _randomize(db, participant_id, actor_id)
    with get_session_factory()() as own:
        try:
            result = _randomize(own, participant_id, actor_id)
            own.commit()
            return result
        except Exception:
            own.rollback()
            raise