"""Request/response models for Module 2. These show up in /docs, keep them accurate."""
from datetime import date, datetime
from typing import Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from shared.constants import THERAPY_VALUES, VISIT_WEEKS

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- participants ----
class ParticipantCreate(BaseModel):
    site_id: str
    age: int = Field(ge=0, le=120)
    sex: Literal["M", "F", "OTHER"]


class ParticipantOut(ORM):
    participant_id: str
    site_id: str
    age: Optional[int]
    sex: Optional[str]
    t2dm_confirmed: Optional[bool]
    baseline_hba1c: Optional[float]
    hba1c_cat: Optional[str]
    therapy: Optional[str]
    eligibility_status: str
    trial_status: str
    consent_status: str
    consent_date: Optional[date]
    baseline_complete: bool
    enrolled_at: Optional[datetime]
    withdrawn_at: Optional[datetime]
    withdrawal_reason: Optional[str]


class ConsentIn(BaseModel):
    status: Literal["OBTAINED", "WITHDRAWN"] = "OBTAINED"
    consent_date: Optional[date] = None


class WithdrawIn(BaseModel):
    reason: str = Field(min_length=3)


class ScreeningIn(BaseModel):
    t2dm_confirmed: bool
    hba1c: float = Field(ge=3, le=20, description="HbA1c percent")
    therapy: Literal["STABLE", "NONE"]


class EligibilityOut(ORM):
    participant_id: str
    criteria_results: dict
    result: str
    reason: Optional[str]
    checked_by: str
    checked_at: datetime


# ---- visits / measurements ----
class VisitIn(BaseModel):
    visit_week: int
    scheduled_date: Optional[date] = None
    completed_date: Optional[date] = None
    status: Optional[Literal["SCHEDULED", "COMPLETED", "MISSED", "RESCHEDULED"]] = None

    @field_validator("visit_week")
    @classmethod
    def _week_ok(cls, v):
        if v not in VISIT_WEEKS:
            raise ValueError(f"visit_week must be one of {VISIT_WEEKS}")
        return v


class VisitOut(ORM):
    id: int
    participant_id: str
    visit_week: int
    scheduled_date: Optional[date]
    completed_date: Optional[date]
    status: str


class MeasurementIn(BaseModel):
    visit_week: int
    systolic: Optional[float] = Field(default=None, ge=40, le=300, description="mmHg")
    diastolic: Optional[float] = Field(default=None, ge=20, le=200, description="mmHg")
    heart_rate: Optional[float] = Field(default=None, ge=20, le=250, description="bpm")
    resp_rate: Optional[float] = Field(default=None, ge=4, le=60, description="breaths/min")
    temperature_c: Optional[float] = Field(default=None, ge=30, le=45)
    spo2: Optional[float] = Field(default=None, ge=50, le=100, description="percent")
    hba1c: Optional[float] = Field(default=None, ge=3, le=20, description="percent")
    fasting_glucose: Optional[float] = Field(default=None, ge=20, le=800, description="mg/dL")
    weight_kg: Optional[float] = Field(default=None, ge=20, le=300)
    bmi: Optional[float] = Field(default=None, ge=10, le=80)
    adherence_pct: Optional[float] = Field(default=None, ge=0, le=100)

    @field_validator("visit_week")
    @classmethod
    def _week_ok(cls, v):
        if v not in VISIT_WEEKS:
            raise ValueError(f"visit_week must be one of {VISIT_WEEKS}")
        return v

    @model_validator(mode="after")
    def _has_a_value(self):
        vals = self.model_dump(exclude={"visit_week"})
        if all(v is None for v in vals.values()):
            raise ValueError("at least one measurement value is required")
        return self


class MeasurementOut(ORM):
    id: int
    participant_id: str
    visit_week: int
    recorded_at: datetime
    systolic: Optional[float]
    diastolic: Optional[float]
    heart_rate: Optional[float]
    resp_rate: Optional[float]
    temperature_c: Optional[float]
    spo2: Optional[float]
    hba1c: Optional[float]
    fasting_glucose: Optional[float]
    weight_kg: Optional[float]
    bmi: Optional[float]
    adherence_pct: Optional[float]
    abnormal_flags: List[str] = []
    baseline_complete: Optional[bool] = None


# ---- adverse events / alerts ----
class AdverseEventIn(BaseModel):
    participant_id: str
    onset_date: date
    duration: Optional[str] = None
    severity: Literal["MILD", "MODERATE", "SEVERE"]
    serious: bool = False
    relationship_to_treatment: Optional[Literal["NOT_RELATED", "POSSIBLY_RELATED", "RELATED"]] = None
    action_taken: Optional[str] = None
    description: str = Field(min_length=3)


class AdverseEventOut(ORM):
    id: int
    participant_id: str
    onset_date: date
    duration: Optional[str]
    severity: str
    serious: bool
    relationship_to_treatment: Optional[str]
    action_taken: Optional[str]
    status: str
    description: str
    reported_by: Optional[str]
    reported_at: datetime
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]


class AEReviewIn(BaseModel):
    status: Literal["UNDER_REVIEW", "CLOSED"]
    relationship_to_treatment: Optional[Literal["NOT_RELATED", "POSSIBLY_RELATED", "RELATED"]] = None
    action_taken: Optional[str] = None


class AlertOut(ORM):
    id: int
    type: str
    participant_id: str
    assigned_to: Optional[str]
    status: str
    due_date: Optional[date]
    detail: Optional[str]
