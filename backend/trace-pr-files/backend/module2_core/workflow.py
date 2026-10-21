"""Business rules for Module 2 (and read-only helpers Module 3 reuses)."""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from module2_core import rules as c
from module2_core.models import AdverseEvent, Alert, Measurement, Participant, Visit


# ---- identifiers ----
def next_participant_id(db: Session) -> str:
    ids = db.scalars(select(Participant.participant_id)).all()
    nums = [int(i[4:]) for i in ids if i.startswith("SUB-") and i[4:].isdigit()]
    return f"SUB-{(max(nums) if nums else 0) + 1:03d}"


# ---- eligibility (placeholder rules, see constants: OPEN decision 4) ----
def evaluate_eligibility(age: Optional[int], t2dm_confirmed: bool, hba1c: float):
    criteria = {
        "age_in_range": {
            "pass": age is not None and c.ELIGIBILITY_AGE_MIN <= age <= c.ELIGIBILITY_AGE_MAX,
            "value": age, "rule": f"{c.ELIGIBILITY_AGE_MIN}-{c.ELIGIBILITY_AGE_MAX} years"},
        "t2dm_confirmed": {
            "pass": bool(t2dm_confirmed), "value": t2dm_confirmed,
            "rule": "confirmed type 2 diabetes"},
        "hba1c_in_range": {
            "pass": c.ELIGIBILITY_HBA1C_MIN <= hba1c <= c.ELIGIBILITY_HBA1C_MAX, "value": hba1c,
            "rule": f"{c.ELIGIBILITY_HBA1C_MIN}-{c.ELIGIBILITY_HBA1C_MAX} %"},
    }
    failed = [k for k, v in criteria.items() if not v["pass"]]
    if failed:
        return c.SCREEN_FAILURE, criteria, "Failed: " + ", ".join(failed)
    return c.ELIGIBLE, criteria, None


def abnormal_flags(m) -> list:
    """Flags for human review only. Never a diagnosis."""
    flags = []
    for field, (low, high) in c.ABNORMAL_RANGES.items():
        v = getattr(m, field, None)
        if v is None:
            continue
        if v < low:
            flags.append(f"{field}_low")
        elif v > high:
            flags.append(f"{field}_high")
    return flags


# ---- baseline ----
def baseline_values(db: Session, participant_id: str):
    rows = db.scalars(select(Measurement).where(
        Measurement.participant_id == participant_id, Measurement.visit_week == 0
    ).order_by(Measurement.id)).all()
    latest = {}
    for r in rows:
        for f in c.BASELINE_REQUIRED:
            v = getattr(r, f)
            if v is not None:
                latest[f] = v
    return all(f in latest for f in c.BASELINE_REQUIRED), latest


def schedule_followups(db: Session, participant_id: str, start: date):
    for w in c.VISIT_WEEKS[1:]:
        exists = db.scalar(select(Visit).where(
            Visit.participant_id == participant_id, Visit.visit_week == w))
        if not exists:
            db.add(Visit(participant_id=participant_id, visit_week=w,
                         scheduled_date=start + timedelta(weeks=w), status=c.SCHEDULED))


# ---- links to Module 5's tables (read only; tolerate them not existing yet) ----
def _has_assignments(db: Session) -> bool:
    return inspect(db.get_bind()).has_table("assignments")


def arm_map(db: Session) -> dict:
    if not _has_assignments(db):
        return {}
    rows = db.execute(text("SELECT participant_id, arm FROM assignments")).all()
    return {r[0]: r[1] for r in rows}


def assignments_available(db: Session) -> bool:
    return _has_assignments(db)


def is_randomized(db: Session, participant_id: str) -> bool:
    if not _has_assignments(db):
        return False
    row = db.execute(text("SELECT 1 FROM assignments WHERE participant_id = :p"),
                     {"p": participant_id}).first()
    return row is not None


def randomized_ids(db: Session) -> set:
    return set(arm_map(db).keys())


# ---- alerts ----
_PRIORITY = {c.PENDING_AE_REVIEW: 1, c.OVERDUE_VISIT: 2, c.MISSING_LAB_RESULT: 3,
             c.INCOMPLETE_FORM: 4, c.INCOMPLETE_CONSENT: 5}


def compute_alerts(db: Session, today: Optional[date] = None) -> list:
    """Pure read. Module 3 uses this for the action queue, refresh_alerts() stores it."""
    today = today or date.today()
    out = []
    people = {p.participant_id: p for p in db.scalars(select(Participant))}
    live = {pid for pid, p in people.items() if p.trial_status not in (c.WITHDRAWN, c.COMPLETED)}

    def add(kind, pid, due, detail, priority=None):
        out.append({"type": kind, "participant_id": pid, "due_date": due, "detail": detail,
                    "priority": _PRIORITY[kind] if priority is None else priority})

    meas = {}
    for m in db.scalars(select(Measurement)):
        meas.setdefault((m.participant_id, m.visit_week), []).append(m)

    for v in db.scalars(select(Visit)):
        if v.participant_id not in people:
            continue
        if v.status in (c.SCHEDULED, c.RESCHEDULED) and v.scheduled_date and v.scheduled_date < today \
                and v.participant_id in live:
            add(c.OVERDUE_VISIT, v.participant_id, v.scheduled_date, f"Week {v.visit_week} visit overdue")
        if v.status == c.COMPLETED:
            ms = meas.get((v.participant_id, v.visit_week), [])
            if not any(m.hba1c is not None for m in ms):
                add(c.MISSING_LAB_RESULT, v.participant_id, v.completed_date or v.scheduled_date,
                    f"Week {v.visit_week}: no HbA1c recorded")

    for pid, p in people.items():
        created = p.created_at.date() if p.created_at else today
        if p.consent_status == c.NOT_OBTAINED and p.trial_status == c.SCREENING:
            add(c.INCOMPLETE_CONSENT, pid, created, "Consent not yet obtained")
        if p.eligibility_status == c.ELIGIBLE and not p.baseline_complete and pid in live:
            add(c.INCOMPLETE_FORM, pid, created, "Baseline data incomplete")

    for ae in db.scalars(select(AdverseEvent).where(AdverseEvent.status == c.SUBMITTED)):
        due = ae.reported_at.date() + timedelta(days=1 if ae.serious else 7)
        add(c.PENDING_AE_REVIEW, ae.participant_id, due,
            ("SERIOUS adverse event" if ae.serious else f"{ae.severity.title()} adverse event") + " awaiting review",
            priority=0 if ae.serious else 1)
    return out


def refresh_alerts(db: Session) -> None:
    """Sync the alerts table with compute_alerts(). System generated, so not audited."""
    desired = {(a["type"], a["participant_id"], a["due_date"]): a for a in compute_alerts(db)}
    seen = set()
    for row in db.scalars(select(Alert).where(Alert.status == c.ALERT_OPEN)):
        key = (row.type, row.participant_id, row.due_date)
        if key in desired and key not in seen:
            seen.add(key)
        else:
            row.status = c.ALERT_RESOLVED
    for key, a in desired.items():
        if key not in seen:
            db.add(Alert(type=a["type"], participant_id=a["participant_id"], due_date=a["due_date"],
                         detail=a["detail"], status=c.ALERT_OPEN))
    db.commit()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
