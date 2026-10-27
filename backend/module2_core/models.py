"""Module 2 tables (spec section 5.1). Only Disha writes to these."""
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer,
                        String, Text, UniqueConstraint, false, func)
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Site(Base):
    __tablename__ = "sites"
    site_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))


class Trial(Base):
    __tablename__ = "trials"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    target_enrollment: Mapped[int] = mapped_column(Integer, default=40)
    protocol_version: Mapped[str] = mapped_column(String(20), default="1.0")


class Participant(Base):
    __tablename__ = "participants"
    participant_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.site_id"))
    age: Mapped[Optional[int]] = mapped_column(Integer)
    sex: Mapped[Optional[str]] = mapped_column(String(10))
    t2dm_confirmed: Mapped[Optional[bool]] = mapped_column(Boolean)
    baseline_hba1c: Mapped[Optional[float]] = mapped_column(Float)
    hba1c_cat: Mapped[Optional[str]] = mapped_column(String(10))
    therapy: Mapped[Optional[str]] = mapped_column(String(10))
    eligibility_status: Mapped[str] = mapped_column(String(20), default="PENDING_REVIEW",
                                                    server_default="PENDING_REVIEW")
    trial_status: Mapped[str] = mapped_column(String(20), default="SCREENING",
                                              server_default="SCREENING")
    consent_status: Mapped[str] = mapped_column(String(20), default="NOT_OBTAINED",
                                                server_default="NOT_OBTAINED")
    consent_date: Mapped[Optional[date]] = mapped_column(Date)
    baseline_complete: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    enrolled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    withdrawal_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now,
                                                 server_default=func.now())


class EligibilityCheck(Base):
    __tablename__ = "eligibility_checks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.participant_id"), index=True)
    criteria_results: Mapped[dict] = mapped_column(JSON)
    result: Mapped[str] = mapped_column(String(20))
    reason: Mapped[Optional[str]] = mapped_column(Text)
    checked_by: Mapped[str] = mapped_column(String(20))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Visit(Base):
    __tablename__ = "visits"
    __table_args__ = (UniqueConstraint("participant_id", "visit_week"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.participant_id"), index=True)
    visit_week: Mapped[int] = mapped_column(Integer)
    scheduled_date: Mapped[Optional[date]] = mapped_column(Date)
    completed_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="SCHEDULED")


class Measurement(Base):
    __tablename__ = "measurements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.participant_id"), index=True)
    visit_week: Mapped[int] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    recorded_by: Mapped[Optional[str]] = mapped_column(String(20))
    systolic: Mapped[Optional[float]] = mapped_column(Float)
    diastolic: Mapped[Optional[float]] = mapped_column(Float)
    heart_rate: Mapped[Optional[float]] = mapped_column(Float)
    resp_rate: Mapped[Optional[float]] = mapped_column(Float)
    temperature_c: Mapped[Optional[float]] = mapped_column(Float)
    spo2: Mapped[Optional[float]] = mapped_column(Float)
    hba1c: Mapped[Optional[float]] = mapped_column(Float)
    fasting_glucose: Mapped[Optional[float]] = mapped_column(Float)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float)
    bmi: Mapped[Optional[float]] = mapped_column(Float)
    adherence_pct: Mapped[Optional[float]] = mapped_column(Float)


class AdverseEvent(Base):
    __tablename__ = "adverse_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.participant_id"), index=True)
    onset_date: Mapped[date] = mapped_column(Date)
    duration: Mapped[Optional[str]] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20))
    serious: Mapped[bool] = mapped_column(Boolean, default=False)
    relationship_to_treatment: Mapped[Optional[str]] = mapped_column(String(20))
    action_taken: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="SUBMITTED")
    description: Mapped[str] = mapped_column(Text)
    reported_by: Mapped[Optional[str]] = mapped_column(String(20))
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(20))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(30))
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.participant_id"), index=True)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    detail: Mapped[Optional[str]] = mapped_column(Text)
