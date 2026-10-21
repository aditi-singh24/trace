"""Module 2: Core API (Disha). Participant lifecycle, visits, measurements, AEs, alerts.

Every endpoint: check_permission first, record_audit_event on every write.
Module 2 never returns an arm value (that lives in Module 5's assignments table).
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from module2_core import rules as c
from shared.db import get_db
from module4_auth import permissions as perm
from module4_auth.dependencies import get_current_user, require_participant_access
from module4_auth.models import User
from module4_auth.permissions import check_permission
from module5_engine.audit import record_audit_event
from module2_core import schemas, workflow as wf
from module2_core.models import (AdverseEvent, Alert, EligibilityCheck, Measurement,
                                 Participant, Site, Visit)

router = APIRouter(prefix="/api/v1", tags=["core"])


# ---------------- helpers ----------------
def _need(user: User, action: str):
    if not check_permission(user, action):
        raise HTTPException(status_code=403, detail="Not allowed for your role")


def _own_only(user: User, pid: str):
    """Patients may only touch their own record (Module 4 rule); staff pass."""
    require_participant_access(user, pid)


def _view_access(user: User, pid: str):
    if user.role == c.PATIENT:
        _need(user, perm.VIEW_OWN_RECORD)
        _own_only(user, pid)
    else:
        _need(user, perm.VIEW_PARTICIPANTS)


def _get(db: Session, pid: str) -> Participant:
    p = db.get(Participant, pid)
    if not p:
        raise HTTPException(status_code=404, detail=f"Participant {pid} not found")
    return p


def _page(db: Session, stmt, page: int, page_size: int) -> dict:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


def _withdraw(p: Participant, reason: str):
    p.trial_status = c.WITHDRAWN
    p.withdrawn_at = wf.now_utc()
    p.withdrawal_reason = reason


def _require_can_record(db: Session, p: Participant, week: int):
    """Workflow prerequisites (spec 1.3) for visits and measurements."""
    if p.trial_status == c.WITHDRAWN:
        raise HTTPException(status_code=409, detail="Participant has withdrawn")
    if p.trial_status == c.COMPLETED:
        raise HTTPException(status_code=409, detail="Participant has completed the trial")
    if p.consent_status != c.OBTAINED:
        raise HTTPException(status_code=409, detail="Consent must be obtained first")
    if p.eligibility_status != c.ELIGIBLE:
        raise HTTPException(status_code=409, detail="Participant is not eligible")
    if week > 0 and not p.baseline_complete:
        raise HTTPException(status_code=409, detail="Baseline must be complete before follow-up visits")
    if week > 0 and wf.assignments_available(db) and not wf.is_randomized(db, p.participant_id):
        raise HTTPException(status_code=409, detail="Participant must be randomized before follow-up visits")


# ---------------- participants ----------------
@router.post("/participants", response_model=schemas.ParticipantOut, status_code=201)
def create_participant(body: schemas.ParticipantCreate, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    _need(user, perm.ENROLL_CONSENT_SCREEN)
    if not db.get(Site, body.site_id):
        raise HTTPException(status_code=400, detail=f"Unknown site_id {body.site_id}")
    p = Participant(participant_id=wf.next_participant_id(db), site_id=body.site_id,
                    age=body.age, sex=body.sex)
    db.add(p)
    db.commit()
    wf.refresh_alerts(db)
    record_audit_event("PARTICIPANT_CREATED", user.id,
                       {"participant_id": p.participant_id, "site_id": p.site_id})
    return p


@router.get("/participants", response_model=schemas.Page[schemas.ParticipantOut])
def list_participants(
    q: Optional[str] = Query(None, description="search participant id"),
    eligibility_status: Optional[str] = None,
    trial_status: Optional[str] = None,
    site_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _need(user, perm.VIEW_PARTICIPANTS)
    stmt = select(Participant).order_by(Participant.participant_id)
    if q:
        stmt = stmt.where(Participant.participant_id.ilike(f"%{q}%"))
    if eligibility_status:
        stmt = stmt.where(Participant.eligibility_status == eligibility_status)
    if trial_status:
        stmt = stmt.where(Participant.trial_status == trial_status)
    if site_id:
        stmt = stmt.where(Participant.site_id == site_id)
    return _page(db, stmt, page, page_size)


@router.get("/participants/{pid}", response_model=schemas.ParticipantOut)
def get_participant(pid: str, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    _view_access(user, pid)
    return _get(db, pid)


@router.post("/participants/{pid}/consent", response_model=schemas.ParticipantOut)
def record_consent(pid: str, body: schemas.ConsentIn, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    _need(user, perm.ENROLL_CONSENT_SCREEN)
    p = _get(db, pid)
    before = p.consent_status
    if body.status == "OBTAINED":
        if p.trial_status == c.WITHDRAWN:
            raise HTTPException(status_code=409, detail="Participant has withdrawn")
        p.consent_status = c.OBTAINED
        p.consent_date = body.consent_date or date.today()
    else:
        p.consent_status = c.WITHDRAWN
        _withdraw(p, "Consent withdrawn")
    db.commit()
    wf.refresh_alerts(db)
    record_audit_event("CONSENT_RECORDED", user.id,
                       {"participant_id": pid, "before": before, "after": p.consent_status})
    return p


@router.post("/participants/{pid}/withdraw", response_model=schemas.ParticipantOut)
def withdraw_participant(pid: str, body: schemas.WithdrawIn, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    _need(user, perm.ENROLL_CONSENT_SCREEN)
    p = _get(db, pid)
    if p.trial_status in (c.WITHDRAWN, c.COMPLETED):
        raise HTTPException(status_code=409, detail=f"Participant is already {p.trial_status}")
    before = p.trial_status
    _withdraw(p, body.reason)
    db.commit()
    wf.refresh_alerts(db)
    record_audit_event("PARTICIPANT_WITHDRAWN", user.id,
                       {"participant_id": pid, "before": before, "reason": body.reason})
    return p


@router.post("/participants/{pid}/screening", response_model=schemas.EligibilityOut)
def screen_participant(pid: str, body: schemas.ScreeningIn, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    _need(user, perm.ENROLL_CONSENT_SCREEN)
    p = _get(db, pid)
    if p.consent_status != c.OBTAINED:
        raise HTTPException(status_code=409, detail="Consent must be obtained before screening")
    if p.trial_status == c.WITHDRAWN:
        raise HTTPException(status_code=409, detail="Participant has withdrawn")
    if p.baseline_complete or wf.is_randomized(db, pid):
        raise HTTPException(status_code=409, detail="Participant is already past screening")

    result, criteria, reason = wf.evaluate_eligibility(p.age, body.t2dm_confirmed, body.hba1c)
    before = p.eligibility_status
    p.t2dm_confirmed = body.t2dm_confirmed
    p.baseline_hba1c = body.hba1c            # provisional, confirmed when baseline completes
    p.hba1c_cat = c.hba1c_category(body.hba1c)
    p.therapy = body.therapy
    p.eligibility_status = result
    check = EligibilityCheck(participant_id=pid, criteria_results=criteria, result=result,
                             reason=reason, checked_by=user.id)
    db.add(check)
    db.commit()
    db.refresh(check)
    wf.refresh_alerts(db)
    record_audit_event("SCREENING_COMPLETED", user.id,
                       {"participant_id": pid, "before": before, "after": result, "reason": reason})
    return check


@router.get("/participants/{pid}/eligibility", response_model=list[schemas.EligibilityOut])
def eligibility_history(pid: str, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    _need(user, perm.VIEW_PARTICIPANTS)
    _get(db, pid)
    return db.scalars(select(EligibilityCheck).where(EligibilityCheck.participant_id == pid)
                      .order_by(EligibilityCheck.id.desc())).all()


# ---------------- visits ----------------
@router.post("/participants/{pid}/visits", response_model=schemas.VisitOut)
def upsert_visit(pid: str, body: schemas.VisitIn, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    _need(user, perm.RECORD_VISITS_MEASUREMENTS)
    p = _get(db, pid)
    _require_can_record(db, p, body.visit_week)
    v = db.scalar(select(Visit).where(Visit.participant_id == pid, Visit.visit_week == body.visit_week))
    created = v is None
    if created:
        v = Visit(participant_id=pid, visit_week=body.visit_week, status=body.status or c.SCHEDULED)
        db.add(v)
    elif body.status:
        v.status = body.status
    if body.scheduled_date:
        v.scheduled_date = body.scheduled_date
    if body.completed_date:
        v.completed_date = body.completed_date
    db.commit()
    db.refresh(v)
    wf.refresh_alerts(db)
    record_audit_event("VISIT_CREATED" if created else "VISIT_UPDATED", user.id,
                       {"participant_id": pid, "visit_week": v.visit_week, "status": v.status})
    return v


@router.get("/participants/{pid}/visits", response_model=list[schemas.VisitOut])
def list_visits(pid: str, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    _view_access(user, pid)
    _get(db, pid)
    return db.scalars(select(Visit).where(Visit.participant_id == pid).order_by(Visit.visit_week)).all()


# ---------------- measurements ----------------
@router.post("/participants/{pid}/measurements", response_model=schemas.MeasurementOut, status_code=201)
def add_measurement(pid: str, body: schemas.MeasurementIn, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    _need(user, perm.RECORD_VISITS_MEASUREMENTS)
    p = _get(db, pid)
    _require_can_record(db, p, body.visit_week)

    values = body.model_dump(exclude={"visit_week"})
    m = Measurement(participant_id=pid, visit_week=body.visit_week, recorded_by=user.id, **values)
    db.add(m)

    today = date.today()
    v = db.scalar(select(Visit).where(Visit.participant_id == pid, Visit.visit_week == body.visit_week))
    if not v:
        v = Visit(participant_id=pid, visit_week=body.visit_week, scheduled_date=today)
        db.add(v)
    v.status = c.COMPLETED
    v.completed_date = today
    db.flush()

    baseline_done_now = False
    if body.visit_week == 0 and not p.baseline_complete:
        ready, latest = wf.baseline_values(db, pid)
        if ready:
            p.baseline_complete = True
            p.baseline_hba1c = latest["hba1c"]
            p.hba1c_cat = c.hba1c_category(latest["hba1c"])
            p.trial_status = c.ENROLLED
            p.enrolled_at = wf.now_utc()
            wf.schedule_followups(db, pid, today)
            baseline_done_now = True
    if body.visit_week == c.TRIAL_WEEKS:
        p.trial_status = c.COMPLETED

    db.commit()
    db.refresh(m)
    wf.refresh_alerts(db)
    record_audit_event("MEASUREMENT_RECORDED", user.id,
                       {"participant_id": pid, "visit_week": body.visit_week, "measurement_id": m.id})
    if baseline_done_now:
        record_audit_event("BASELINE_COMPLETED", user.id,
                           {"participant_id": pid, "hba1c_cat": p.hba1c_cat})
    out = schemas.MeasurementOut.model_validate(m)
    out.abnormal_flags = wf.abnormal_flags(m)
    out.baseline_complete = p.baseline_complete
    return out


@router.get("/participants/{pid}/measurements", response_model=list[schemas.MeasurementOut])
def list_measurements(pid: str, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    _view_access(user, pid)
    _get(db, pid)
    rows = db.scalars(select(Measurement).where(Measurement.participant_id == pid)
                      .order_by(Measurement.visit_week, Measurement.id)).all()
    result = []
    for m in rows:
        o = schemas.MeasurementOut.model_validate(m)
        o.abnormal_flags = wf.abnormal_flags(m)
        result.append(o)
    return result


# ---------------- adverse events ----------------
@router.post("/adverse-events", response_model=schemas.AdverseEventOut, status_code=201)
def report_adverse_event(body: schemas.AdverseEventIn, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    _need(user, perm.REPORT_ADVERSE_EVENT)
    _own_only(user, body.participant_id)
    _get(db, body.participant_id)
    ae = AdverseEvent(**body.model_dump(), status=c.SUBMITTED, reported_by=user.id)
    db.add(ae)
    db.commit()
    db.refresh(ae)
    wf.refresh_alerts(db)
    record_audit_event("ADVERSE_EVENT_REPORTED", user.id,
                       {"ae_id": ae.id, "participant_id": ae.participant_id,
                        "severity": ae.severity, "serious": ae.serious})
    return ae


@router.get("/adverse-events", response_model=schemas.Page[schemas.AdverseEventOut])
def list_adverse_events(
    participant_id: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(AdverseEvent).order_by(AdverseEvent.id.desc())
    if user.role == c.PATIENT:
        _need(user, perm.VIEW_OWN_RECORD)
        stmt = stmt.where(AdverseEvent.participant_id == (user.participant_id or "__none__"))
    else:
        _need(user, perm.VIEW_ADVERSE_EVENTS)
        if participant_id:
            stmt = stmt.where(AdverseEvent.participant_id == participant_id)
    if status:
        stmt = stmt.where(AdverseEvent.status == status)
    if severity:
        stmt = stmt.where(AdverseEvent.severity == severity)
    return _page(db, stmt, page, page_size)


@router.post("/adverse-events/{ae_id}/review", response_model=schemas.AdverseEventOut)
def review_adverse_event(ae_id: int, body: schemas.AEReviewIn, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    _need(user, perm.REVIEW_ADVERSE_EVENTS)
    ae = db.get(AdverseEvent, ae_id)
    if not ae:
        raise HTTPException(status_code=404, detail=f"Adverse event {ae_id} not found")
    if ae.status == c.CLOSED:
        raise HTTPException(status_code=409, detail="Adverse event is already closed")
    if body.status == c.UNDER_REVIEW and ae.status != c.SUBMITTED:
        raise HTTPException(status_code=409, detail="Only a SUBMITTED event can move to UNDER_REVIEW")
    before = ae.status
    ae.status = body.status
    ae.reviewed_by = user.id
    ae.reviewed_at = wf.now_utc()
    if body.relationship_to_treatment:
        ae.relationship_to_treatment = body.relationship_to_treatment
    if body.action_taken:
        ae.action_taken = body.action_taken
    db.commit()
    db.refresh(ae)
    wf.refresh_alerts(db)
    record_audit_event("ADVERSE_EVENT_REVIEWED", user.id,
                       {"ae_id": ae.id, "before": before, "after": ae.status})
    return ae


# ---------------- alerts ----------------
@router.get("/alerts", response_model=schemas.Page[schemas.AlertOut])
def list_alerts(
    status: str = Query(c.ALERT_OPEN),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _need(user, perm.OPERATIONAL_DASHBOARD)
    wf.refresh_alerts(db)   # also catches visits that became overdue as time passed
    stmt = select(Alert).where(Alert.status == status).order_by(Alert.due_date, Alert.id)
    return _page(db, stmt, page, page_size)
