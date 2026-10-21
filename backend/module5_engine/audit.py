"""Hash-chained audit trail.

hash = SHA256(prev_hash + canonical_json(entry without hash))
Canonical JSON: sorted keys, no extra spaces, UTF-8. Genesis prev_hash is 64 zeros.
Only event types in CHAINED_EVENT_TYPES are chained; others are written to the
application log (a structured line) so they are not lost.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from module5_engine.models import AuditEntry
from shared.constants import CHAINED_EVENT_TYPES, GENESIS_HASH
from shared.db import get_session_factory

logger = logging.getLogger("trace.audit")

CHAIN_LOCK_KEY = 727001  # Postgres advisory lock: serialises appends to the chain


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_hash(prev_hash: str, entry: dict) -> str:
    """`entry` is the entry WITHOUT its hash field."""
    return hashlib.sha256((prev_hash + canonical_json(entry)).encode("utf-8")).hexdigest()


def _entry_fields(e: AuditEntry) -> dict:
    return {
        "seq": e.seq,
        "event_type": e.event_type,
        "actor_id": e.actor_id,
        "payload": e.payload,
        "created_at": e.created_at,
        "prev_hash": e.prev_hash,
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def lock_chain(db: Session) -> None:
    """Serialise chain appends on PostgreSQL (no-op elsewhere)."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": CHAIN_LOCK_KEY})


def _append(db: Session, event_type: str, actor_id: str, payload: dict) -> AuditEntry:
    lock_chain(db)
    last = db.scalar(select(AuditEntry).order_by(AuditEntry.seq.desc()).limit(1))
    prev_hash = last.hash if last else GENESIS_HASH
    fields = {
        "seq": (last.seq + 1) if last else 1,
        "event_type": event_type,
        "actor_id": actor_id,
        # round-trip through canonical JSON so what we hash is what we read back
        "payload": json.loads(canonical_json(payload)),
        "created_at": _now_iso(),
        "prev_hash": prev_hash,
    }
    entry = AuditEntry(**fields, hash=compute_hash(prev_hash, fields))
    db.add(entry)
    db.flush()
    return entry


def record_audit_event(
    event_type: str,
    actor_id: str,
    payload: dict,
    db: Optional[Session] = None,
) -> Optional[AuditEntry]:
    """Record an audit event.

    Pass `db` to join the caller's transaction (the caller commits); this is how
    randomize() saves the assignment and its chain entry atomically. Without `db`
    the entry is written and committed in its own session.
    Never put the treatment arm in `payload`: the audit page is visible to blinded users.
    """
    if event_type not in CHAINED_EVENT_TYPES:
        logger.info(canonical_json({"event_type": event_type, "actor_id": actor_id, "payload": payload}))
        return None
    if db is not None:
        return _append(db, event_type, actor_id, payload)
    with get_session_factory()() as own:
        entry = _append(own, event_type, actor_id, payload)
        own.commit()
        return entry


def verify_chain(db: Session) -> dict:
    """Walk the chain from genesis. Returns ok, or the first broken seq."""
    expected_seq = 1
    expected_prev = GENESIS_HASH
    checked = 0
    # populate_existing: always compare the rows actually stored in the database, never
    # objects cached in this session (the session factory uses expire_on_commit=False).
    rows = db.scalars(select(AuditEntry).order_by(AuditEntry.seq).execution_options(populate_existing=True))
    for e in rows:
        broken = (
            e.seq != expected_seq  # gap: an entry was removed
            or e.prev_hash != expected_prev
            or e.hash != compute_hash(e.prev_hash, _entry_fields(e))
        )
        if broken:
            return {"ok": False, "first_broken_seq": expected_seq if e.seq != expected_seq else e.seq,
                    "entries_checked": checked}
        expected_prev = e.hash
        expected_seq += 1
        checked += 1
    return {"ok": True, "first_broken_seq": None, "entries_checked": checked}
