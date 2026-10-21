"""Synthetic demo data for TRACE (all fictional).

From backend/:   python seed_demo.py --reset

Needs DATABASE_URL and JWT_SECRET in the environment (see .env.example).
SEED_PASSWORD sets the demo password; if unset a random one is generated and printed once.
Goes through the real API (with a coordinator token) so every workflow rule is exercised,
then back-dates dates so some visits look overdue and one participant has completed.
"""
import os
import random
import secrets
import sys
from datetime import date, datetime, time, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

import module2_core.models as m
import module4_auth.models as auth_models
import module5_engine.models  # noqa: F401  (registers tables)
from main import app
from module4_auth.security import create_access_token, hash_password
from shared.constants import COORDINATOR, PATIENT, SITES, SUPERVISOR
from shared.db import Base, get_engine, get_session_factory

API = "/api/v1"
rng = random.Random(42)
client = TestClient(app)
H = {}


def call(method, path, **kw):
    r = getattr(client, method)(f"{API}{path}", headers=H, **kw)
    if r.status_code >= 300:
        raise SystemExit(f"Seed failed: {method.upper()} {path} -> {r.status_code} {r.text}")
    return r.json()


def backdate(pid, weeks):
    with get_session_factory()() as db:
        p = db.get(m.Participant, pid)
        start = datetime.now(timezone.utc) - timedelta(weeks=weeks)
        p.enrolled_at, p.created_at = start, start - timedelta(days=5)
        p.consent_date = (start - timedelta(days=4)).date()
        for v in db.scalars(select(m.Visit).where(m.Visit.participant_id == pid)):
            d = start.date() + timedelta(weeks=v.visit_week)
            v.scheduled_date = d
            if v.status == "COMPLETED":
                v.completed_date = d
        for x in db.scalars(select(m.Measurement).where(m.Measurement.participant_id == pid)):
            day = start.date() + timedelta(weeks=x.visit_week)
            x.recorded_at = datetime.combine(day, time(9, 0), tzinfo=timezone.utc)
        db.commit()


def new(site, age, sex):
    return call("post", "/participants", json={"site_id": site, "age": age, "sex": sex})["participant_id"]


def consent(pid):
    call("post", f"/participants/{pid}/consent", json={})


def screen(pid, hba1c, therapy="STABLE"):
    return call("post", f"/participants/{pid}/screening",
                json={"t2dm_confirmed": True, "hba1c": hba1c, "therapy": therapy})


def measure(pid, week, base_hba1c, base_weight, **extra):
    h = round(base_hba1c - 0.35 * week / 4 + rng.uniform(-0.12, 0.12), 2)
    vals = {"visit_week": week, "hba1c": h, "fasting_glucose": round(100 + 18 * (h - 7) + rng.uniform(-6, 6)),
            "weight_kg": round(base_weight - 0.4 * week / 4 + rng.uniform(-0.3, 0.3), 1),
            "systolic": round(rng.uniform(118, 138)), "diastolic": round(rng.uniform(72, 86)),
            "heart_rate": round(rng.uniform(62, 84)), "spo2": round(rng.uniform(96, 99)),
            "adherence_pct": round(rng.uniform(80, 98))}
    vals.update(extra)
    call("post", f"/participants/{pid}/measurements", json=vals)


def enrol(site, age, sex, hba1c, weight, weeks_done, elapsed, therapy="STABLE", extra=None):
    pid = new(site, age, sex)
    consent(pid)
    screen(pid, hba1c, therapy)
    measure(pid, 0, hba1c, weight)                       # baseline
    call("post", "/randomization", json={"participant_id": pid})   # Module 5
    for w in weeks_done:
        if w:
            measure(pid, w, hba1c, weight, **(extra or {}).get(w, {}))
    backdate(pid, elapsed)
    return pid


def ae(pid, severity, serious, desc, days_ago=3, review=None):
    a = call("post", "/adverse-events", json={
        "participant_id": pid, "onset_date": str(date.today() - timedelta(days=days_ago)),
        "severity": severity, "serious": serious, "duration": "1 day",
        "relationship_to_treatment": "POSSIBLY_RELATED", "description": desc})
    for step in (review or []):
        call("post", f"/adverse-events/{a['id']}/review", json={"status": step})


def main():
    engine = get_engine()
    if "--reset" in sys.argv:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    password = os.environ.get("SEED_PASSWORD") or secrets.token_urlsafe(12)
    generated = "SEED_PASSWORD" not in os.environ

    with get_session_factory()() as db:
        if db.scalars(select(m.Participant)).first():
            raise SystemExit("Database already has data. Run:  python seed_demo.py --reset")
        for i, sid in enumerate(SITES, 1):
            db.add(m.Site(site_id=sid, name=f"Demo Research Site {i}"))
        db.add(m.Trial(name="TRACE simulated Type 2 Diabetes trial (fictional data)",
                       status="ACTIVE", target_enrollment=12, protocol_version="1.0"))
        users = [("U-0001", "supervisor", SUPERVISOR, False, None),
                 ("U-0002", "supervisor_unblinded", SUPERVISOR, True, None),
                 ("U-0003", "coordinator", COORDINATOR, False, None),
                 ("U-0004", "patient_sub010", PATIENT, False, "SUB-010")]
        for uid, name, role, unblinded, pid in users:
            if not db.get(auth_models.User, uid):
                db.add(auth_models.User(id=uid, username=name, password_hash=hash_password(password),
                                        role=role, unblinded=unblinded, participant_id=pid, active=True))
        db.commit()
    H["Authorization"] = "Bearer " + create_access_token("U-0003", COORDINATOR)[0]

    new("SITE-01", 54, "M")                                              # SUB-001 registered only
    new("SITE-02", 61, "F")                                              # SUB-002 registered only
    p3 = new("SITE-01", 47, "F"); consent(p3)                            # SUB-003 awaiting screening
    p4 = new("SITE-02", 58, "M"); consent(p4); screen(p4, 12.4, "NONE")  # SUB-004 screen failure
    p5 = new("SITE-01", 82, "M"); consent(p5); screen(p5, 8.0)           # SUB-005 screen failure (age)
    p6 = new("SITE-02", 52, "F"); consent(p6); screen(p6, 9.4)           # SUB-006 eligible, no baseline

    enrol("SITE-01", 49, "M", 9.1, 92, [0], 2)                                       # SUB-007
    enrol("SITE-02", 63, "F", 7.8, 71, [0, 4], 5)                                    # SUB-008
    p9 = enrol("SITE-01", 57, "M", 8.9, 88, [0, 4], 9)                               # SUB-009 week 8 overdue
    p10 = enrol("SITE-02", 66, "F", 10.2, 79, [0, 4, 8, 12], 13, therapy="NONE")     # SUB-010
    enrol("SITE-01", 45, "M", 8.6, 95, [0, 4, 8, 12, 16], 17)                        # SUB-011 completed
    p12 = enrol("SITE-02", 59, "F", 8.1, 68, [0, 4], 6)                              # SUB-012 withdrawn
    call("post", f"/participants/{p12}/withdraw", json={"reason": "Relocated (synthetic)"})
    p13 = enrol("SITE-01", 51, "F", 8.2, 74, [0, 4, 8], 9,
                extra={8: {"hba1c": 7.6, "systolic": 172}})                          # SUB-013 abnormal BP
    enrol("SITE-02", 55, "M", 7.4, 84, [0], 1)                                       # SUB-014

    ae(p10, "SEVERE", True, "Low blood sugar episode needing assistance (synthetic)", 2)
    ae(p9, "MODERATE", False, "Persistent nausea after dose (synthetic)", 6, ["UNDER_REVIEW"])
    ae(p13, "MILD", False, "Mild headache (synthetic)", 5)
    ae(p10, "MILD", False, "Mild dizziness, resolved (synthetic)", 20, ["UNDER_REVIEW", "CLOSED"])
    call("get", "/alerts")

    print("Seeded 14 synthetic participants (8 randomized) and 4 adverse events.")
    print("Logins: supervisor, supervisor_unblinded, coordinator, patient_sub010")
    if generated:
        print(f"Password (shown once): {password}")


if __name__ == "__main__":
    main()
