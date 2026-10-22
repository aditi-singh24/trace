"""Module 3: Reporting & Export (Disha). Read-only.

Any response or export that could contain an arm passes through can_see_arm().
Blinded users never get arm-specific numbers. Missing data is reported separately,
never filled in.
"""
import csv
import io
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from statistics import mean
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from module2_core import rules as c
from shared.db import get_db
from module4_auth import permissions as perm
from module4_auth.dependencies import get_current_user
from module4_auth.models import User
from module4_auth.permissions import can_see_arm, check_permission
from module5_engine.audit import record_audit_event
from module2_core import workflow as wf
from module2_core.models import AdverseEvent, Measurement, Participant, Trial, Visit

router = APIRouter(prefix="/api/v1", tags=["reports"])

VITAL_FIELDS = ("systolic", "diastolic", "heart_rate", "resp_rate", "temperature_c", "spo2",
                "hba1c", "fasting_glucose", "weight_kg", "bmi", "adherence_pct")

NOT_BUILT_YET = [
    "protocol deviations", "open data queries", "data-lock readiness",
    "baseline balance by arm (needs Module 5 assignments)",
]


# ---------------- helpers ----------------
def _need(user: User, action: str):
    if not check_permission(user, action):
        raise HTTPException(status_code=403, detail="Not allowed for your role")


def _latest_by_week(db: Session) -> dict:
    """(participant_id, week) -> most recent measurement row."""
    out = {}
    for m in db.scalars(select(Measurement).order_by(Measurement.id)):
        out[(m.participant_id, m.visit_week)] = m
    return out


def _series(db: Session, field: str, pids: Optional[set] = None) -> list:
    """Per-week n, mean and mean change from baseline, pooled over `pids` (all if None)."""
    lm = _latest_by_week(db)
    rows = [(k, m) for k, m in lm.items() if pids is None or k[0] in pids]
    base = {k[0]: getattr(m, field) for k, m in rows if k[1] == 0 and getattr(m, field) is not None}
    out = []
    for w in c.VISIT_WEEKS:
        vals = [getattr(m, field) for k, m in rows if k[1] == w and getattr(m, field) is not None]
        deltas = [getattr(m, field) - base[k[0]] for k, m in rows
                  if w > 0 and k[1] == w and k[0] in base and getattr(m, field) is not None]
        out.append({"week": w, "n": len(vals),
                    "mean": round(mean(vals), 2) if vals else None,
                    "mean_change_from_baseline": round(mean(deltas), 2) if deltas else None})
    return out


def _vitals(m: Measurement) -> dict:
    d = {f: getattr(m, f) for f in VITAL_FIELDS}
    d.update({"visit_week": m.visit_week, "recorded_at": m.recorded_at,
              "abnormal_flags": wf.abnormal_flags(m)})
    return d


def _participants(db: Session) -> list:
    return db.scalars(select(Participant).order_by(Participant.participant_id)).all()


def _counts(people: list, randomized: set) -> dict:
    return {
        "registered": len(people),
        "awaiting_screening": sum(p.eligibility_status == c.PENDING_REVIEW for p in people),
        "eligible": sum(p.eligibility_status == c.ELIGIBLE for p in people),
        "screen_failures": sum(p.eligibility_status == c.SCREEN_FAILURE for p in people),
        "enrolled": sum(p.trial_status == c.ENROLLED for p in people),
        "withdrawn": sum(p.trial_status == c.WITHDRAWN for p in people),
        "completed": sum(p.trial_status == c.COMPLETED for p in people),
        "awaiting_randomization": sum(
            p.eligibility_status == c.ELIGIBLE and p.consent_status == c.OBTAINED
            and p.baseline_complete and p.trial_status not in (c.WITHDRAWN, c.COMPLETED)
            and p.participant_id not in randomized for p in people),
    }


def _data_quality(db: Session) -> list:
    issues = []
    meas = {}
    for m in db.scalars(select(Measurement)):
        meas.setdefault((m.participant_id, m.visit_week), []).append(m)
    for p in _participants(db):
        if p.consent_status == c.OBTAINED and p.eligibility_status == c.PENDING_REVIEW \
                and p.trial_status == c.SCREENING:
            issues.append({"type": "CONSENTED_NOT_SCREENED", "participant_id": p.participant_id,
                           "detail": "Consent recorded but screening not done"})
        if p.eligibility_status == c.ELIGIBLE and not p.baseline_complete \
                and p.trial_status != c.WITHDRAWN:
            issues.append({"type": "BASELINE_INCOMPLETE", "participant_id": p.participant_id,
                           "detail": "Eligible but baseline data incomplete"})
    for v in db.scalars(select(Visit).where(Visit.status == c.COMPLETED)):
        ms = meas.get((v.participant_id, v.visit_week), [])
        if not ms:
            issues.append({"type": "VISIT_WITHOUT_DATA", "participant_id": v.participant_id,
                           "detail": f"Week {v.visit_week} marked completed but nothing recorded"})
        elif not any(m.hba1c is not None for m in ms):
            issues.append({"type": "MISSING_HBA1C", "participant_id": v.participant_id,
                           "detail": f"Week {v.visit_week}: HbA1c missing"})
    return issues


def _visit_stats(db: Session, today: date) -> dict:
    visits = db.scalars(select(Visit)).all()
    people = {p.participant_id: p for p in _participants(db)}
    live = [v for v in visits if people[v.participant_id].trial_status
            not in (c.WITHDRAWN, c.COMPLETED)]
    open_states = (c.SCHEDULED, c.RESCHEDULED)
    overdue = [v for v in live if v.status in open_states and v.scheduled_date and v.scheduled_date < today]
    due_soon = [v for v in live if v.status in open_states and v.scheduled_date
                and today <= v.scheduled_date <= today + timedelta(days=7)]
    by_week = []
    for w in c.VISIT_WEEKS:
        vs = [v for v in visits if v.visit_week == w]
        by_week.append({
            "week": w,
            "completed": sum(v.status == c.COMPLETED for v in vs),
            "scheduled": sum(v.status in open_states for v in vs),
            "missed": sum(v.status == c.MISSED for v in vs),
            "overdue": sum(v in overdue for v in vs),
        })
    return {"overdue": overdue, "due_soon": due_soon, "by_week": by_week}


def _ae_summary(db: Session) -> dict:
    aes = db.scalars(select(AdverseEvent)).all()
    return {
        "total": len(aes),
        "serious": sum(a.serious for a in aes),
        "by_severity": dict(Counter(a.severity for a in aes)),
        "by_status": dict(Counter(a.status for a in aes)),
        "by_relationship": dict(Counter(a.relationship_to_treatment or "NOT_ASSESSED" for a in aes)),
        "awaiting_review": sum(a.status == c.SUBMITTED for a in aes),
        "serious_awaiting_review": sum(a.status == c.SUBMITTED and a.serious for a in aes),
    }


# ---------------- dashboards ----------------
def _patient_dashboard(db: Session, user: User) -> dict:
    if not user.participant_id:
        raise HTTPException(status_code=400, detail="This patient user is not linked to a participant")
    p = db.get(Participant, user.participant_id)
    if not p:
        raise HTTPException(status_code=404, detail="Participant not found")
    today = date.today()
    week = 0
    if p.enrolled_at:
        enrolled = p.enrolled_at.date()
        week = min(c.TRIAL_WEEKS, max(0, (today - enrolled).days // 7))
    if p.trial_status == c.COMPLETED:
        week = c.TRIAL_WEEKS
    visits = db.scalars(select(Visit).where(Visit.participant_id == p.participant_id)
                        .order_by(Visit.visit_week)).all()
    upcoming = [v for v in visits if v.status in (c.SCHEDULED, c.RESCHEDULED)]
    ms = db.scalars(select(Measurement).where(Measurement.participant_id == p.participant_id)
                    .order_by(Measurement.id.desc()).limit(2)).all()
    pending = []
    if p.consent_status != c.OBTAINED:
        pending.append("Informed consent")
    if p.eligibility_status == c.ELIGIBLE and not p.baseline_complete:
        pending.append("Baseline data")
    aes = db.scalars(select(AdverseEvent).where(AdverseEvent.participant_id == p.participant_id)
                     .order_by(AdverseEvent.id.desc())).all()
    return {
        "role": c.PATIENT,
        "participant_id": p.participant_id,
        "trial_status": p.trial_status,
        "consent_status": p.consent_status,
        "current_week": week,
        "total_weeks": c.TRIAL_WEEKS,
        "progress_pct": round(week / c.TRIAL_WEEKS * 100),
        "next_visit": ({"visit_week": upcoming[0].visit_week, "scheduled_date": upcoming[0].scheduled_date}
                       if upcoming else None),
        "latest_vitals": _vitals(ms[0]) if ms else None,
        "previous_vitals": _vitals(ms[1]) if len(ms) > 1 else None,
        "visit_history": [{"visit_week": v.visit_week, "status": v.status,
                           "scheduled_date": v.scheduled_date, "completed_date": v.completed_date}
                          for v in visits],
        "pending_forms": pending,
        "adverse_events": [{"id": a.id, "status": a.status, "severity": a.severity,
                            "reported_at": a.reported_at} for a in aes],
    }


def _coordinator_dashboard(db: Session, user: User) -> dict:
    today = date.today()
    people = _participants(db)
    stats = _visit_stats(db, today)
    lm = _latest_by_week(db)
    latest_per_person = {}
    for (pid, w), m in lm.items():
        if pid not in latest_per_person or w >= latest_per_person[pid][0]:
            latest_per_person[pid] = (w, m)
    abnormal = [{"participant_id": pid, "visit_week": w, "flags": f}
                for pid, (w, m) in sorted(latest_per_person.items())
                if (f := wf.abnormal_flags(m))]
    queue = sorted(wf.compute_alerts(db, today), key=lambda a: (a["priority"], a["due_date"] or today))[:10]
    return {
        "role": c.COORDINATOR,
        "counts": _counts(people, wf.randomized_ids(db)),
        "visits_due_next_7_days": len(stats["due_soon"]),
        "visits_overdue": len(stats["overdue"]),
        "abnormal_readings": abnormal,
        "adverse_events_awaiting_review": _ae_summary(db)["awaiting_review"],
        "data_quality_issues": len(_data_quality(db)),
        "priority_action_queue": queue,
    }


def _supervisor_dashboard(db: Session, user: User) -> dict:
    today = date.today()
    people = _participants(db)
    randomized = wf.randomized_ids(db)
    trial = db.scalars(select(Trial)).first()
    target = trial.target_enrollment if trial else None
    actual = sum(p.baseline_complete for p in people)
    consented = sum(p.consent_status in (c.OBTAINED, c.WITHDRAWN) for p in people)
    withdrawn = sum(p.trial_status == c.WITHDRAWN for p in people)

    # outcome completeness: due visits vs HbA1c actually recorded (missing is shown, never filled)
    lm = _latest_by_week(db)
    completeness = []
    for w in c.VISIT_WEEKS:
        vs = [v for v in db.scalars(select(Visit).where(Visit.visit_week == w))
              if v.status == c.COMPLETED or (v.scheduled_date and v.scheduled_date <= today
                                             and v.status != c.MISSED)]
        recorded = sum(1 for v in vs if getattr(lm.get((v.participant_id, w)), "hba1c", None) is not None)
        completeness.append({"week": w, "expected": len(vs), "recorded": recorded,
                             "missing": len(vs) - recorded})

    arm_breakdown = None
    if can_see_arm(user):
        arms = wf.arm_map(db)
        arm_breakdown = {
            "counts": dict(Counter(arms.values())),
            "hba1c_by_arm": {a: _series(db, "hba1c", {p for p, x in arms.items() if x == a})
                             for a in c.ARMS},
        }

    stats = _visit_stats(db, today)
    return {
        "role": c.SUPERVISOR,
        "enrollment": {"target": target, "actual": actual,
                       "pct_of_target": round(actual / target * 100) if target else None},
        "funnel": {
            "registered": len(people),
            "screened": sum(p.eligibility_status != c.PENDING_REVIEW for p in people),
            "eligible": sum(p.eligibility_status == c.ELIGIBLE for p in people),
            "randomized": len(randomized),
            "completed": sum(p.trial_status == c.COMPLETED for p in people),
        },
        "dropout": {"withdrawn": withdrawn, "consented": consented,
                    "rate_pct": round(withdrawn / consented * 100, 1) if consented else None},
        "outcomes_all_participants": {
            "hba1c": _series(db, "hba1c"),
            "fasting_glucose": _series(db, "fasting_glucose"),
            "weight_kg": _series(db, "weight_kg"),
        },
        "outcome_completeness": completeness,
        "adverse_events": _ae_summary(db),
        "consent": dict(Counter(p.consent_status for p in people)),
        "overdue_visits": len(stats["overdue"]),
        "arm_breakdown": arm_breakdown,   # None unless can_see_arm(user)
        "not_built_yet": NOT_BUILT_YET,
    }


@router.get("/reports/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role == c.PATIENT:
        _need(user, perm.VIEW_OWN_RECORD)
        return _patient_dashboard(db, user)
    if user.role == c.COORDINATOR:
        _need(user, perm.OPERATIONAL_DASHBOARD)
        return _coordinator_dashboard(db, user)
    _need(user, perm.OVERSIGHT_DASHBOARD)
    return _supervisor_dashboard(db, user)


# ---------------- reports ----------------
@router.get("/reports/enrollment")
def enrollment_report(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _need(user, perm.OPERATIONAL_DASHBOARD)
    people = _participants(db)
    randomized = wf.randomized_ids(db)
    trial = db.scalars(select(Trial)).first()
    sites = sorted({p.site_id for p in people})
    return {
        "target": trial.target_enrollment if trial else None,
        "actual": sum(p.baseline_complete for p in people),
        "overall": _counts(people, randomized),
        "by_site": [{"site_id": s, **_counts([p for p in people if p.site_id == s], randomized)}
                    for s in sites],
        "by_hba1c_category": dict(Counter(p.hba1c_cat for p in people if p.hba1c_cat)),
        "by_therapy": dict(Counter(p.therapy for p in people if p.therapy)),
    }


@router.get("/reports/safety")
def safety_report(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _need(user, perm.OPERATIONAL_DASHBOARD)
    out = _ae_summary(db)
    out["serious_events"] = [
        {"id": a.id, "participant_id": a.participant_id, "severity": a.severity,
         "status": a.status, "onset_date": a.onset_date}
        for a in db.scalars(select(AdverseEvent).where(AdverseEvent.serious.is_(True))
                            .order_by(AdverseEvent.id.desc()))]
    return out


@router.get("/reports/visits")
def visits_report(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _need(user, perm.OPERATIONAL_DASHBOARD)
    s = _visit_stats(db, date.today())
    return {
        "by_week": s["by_week"],
        "overdue": [{"participant_id": v.participant_id, "visit_week": v.visit_week,
                     "scheduled_date": v.scheduled_date} for v in s["overdue"]],
        "due_next_7_days": [{"participant_id": v.participant_id, "visit_week": v.visit_week,
                             "scheduled_date": v.scheduled_date} for v in s["due_soon"]],
    }


@router.get("/reports/data-quality")
def data_quality_report(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _need(user, perm.OPERATIONAL_DASHBOARD)
    issues = _data_quality(db)
    return {"total": len(issues), "by_type": dict(Counter(i["type"] for i in issues)), "issues": issues}


# ---------------- export ----------------
CSV_COLUMNS = ["participant_id", "site_id", "age", "sex", "t2dm_confirmed", "baseline_hba1c",
               "hba1c_cat", "therapy", "eligibility_status", "trial_status", "consent_status",
               "consent_date", "baseline_complete", "enrolled_at", "withdrawn_at", "arm"]


@router.get("/exports/participants.csv")
def export_participants(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _need(user, perm.EXPORT_CSV)
    show_arm = can_see_arm(user)
    arms = wf.arm_map(db) if show_arm else {}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_COLUMNS)
    people = _participants(db)
    for p in people:
        row = []
        for col in CSV_COLUMNS:
            if col == "arm":
                row.append(arms.get(p.participant_id, "") if show_arm else "")
                continue
            v = getattr(p, col)
            if isinstance(v, bool):
                v = "true" if v else "false"
            elif isinstance(v, (date, datetime)):
                v = v.isoformat()
            row.append("" if v is None else v)
        w.writerow(row)
    record_audit_event("EXPORT_PARTICIPANTS_CSV", user.id, {"rows": len(people), "arm_included": show_arm})
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="participants.csv"'})
