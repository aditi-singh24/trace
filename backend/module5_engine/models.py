"""Module 5 tables: allocation_blocks, assignments, audit_chain."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class AllocationBlock(Base):
    """One slot of a shuffled block. `seed` is the block's RNG seed (reproducibility)."""

    __tablename__ = "allocation_blocks"
    __table_args__ = (UniqueConstraint("stratum_key", "block_no", "position", name="uq_block_slot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stratum_key: Mapped[str] = mapped_column(String(64), index=True)
    block_no: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    arm: Mapped[str] = mapped_column(String(1))
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    seed: Mapped[str] = mapped_column(String(64))


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_id: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    randomization_number: Mapped[str] = mapped_column(String(16), unique=True)
    stratum_key: Mapped[str] = mapped_column(String(64))
    block_no: Mapped[int] = mapped_column(Integer)
    arm: Mapped[str] = mapped_column(String(1))
    assigned_at: Mapped[str] = mapped_column(String(32))  # ISO 8601 UTC
    assigned_by: Mapped[str] = mapped_column(String(16))


class AuditEntry(Base):
    """Append-only hash chain. created_at is stored as an ISO 8601 UTC string so the
    exact text that was hashed is the exact text that is read back."""

    __tablename__ = "audit_chain"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    event_type: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(String(16))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(32))
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)


class AuditChainImmutableError(RuntimeError):
    pass


@event.listens_for(AuditEntry, "before_update")
def _block_update(mapper, connection, target):
    raise AuditChainImmutableError("audit_chain is append-only: updates are not allowed")


@event.listens_for(AuditEntry, "before_delete")
def _block_delete(mapper, connection, target):
    raise AuditChainImmutableError("audit_chain is append-only: deletes are not allowed")
