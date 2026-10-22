import logging
from datetime import date, timedelta

from module2_core.models import Visit
from tests.core.helpers import (API, baseline, baselined, enrolled, new_participant, randomize,
                                to_eligible)


def test_requires_login(client):
    assert client.get(f"{API}/participants").status_code == 401
    assert client.get(f"{API}/reports/dashboard").status_code == 401


def test_create_participant_and_unknown_site(client, H):
    assert new_participant(client, H) == "SUB-001"
    assert new_participant(client, H) == "SUB-002"
    r = client.post(f"{API}/participants", json={"site_id": "SITE-99", "age": 50, "sex": "M"}, headers=H.coord)
    assert r.status_code == 400
    assert r.json() == {"error": "Unknown site_id SITE-99", "code": 400}


def test_screening_blocked_without_consent(client, H):
    pid = new_participant(client, H)
    r = client.post(f"{API}/participants/{pid}/screening",
                    json={"t2dm_confirmed": True, "hba1c": 9, "therapy": "STABLE"}, headers=H.coord)
    assert r.status_code == 409


def test_eligible_and_screen_failure_with_reason(client, H):
    ok = new_participant(client, H)
    assert to_eligible(client, H, ok, 9.0)["result"] == "ELIGIBLE"
    bad = new_participant(client, H)
    client.post(f"{API}/participants/{bad}/consent", json={}, headers=H.coord)
    r = client.post(f"{API}/participants/{bad}/screening",
                    json={"t2dm_confirmed": True, "hba1c": 12.5, "therapy": "NONE"}, headers=H.coord).json()
    assert r["result"] == "SCREEN_FAILURE" and "hba1c_in_range" in r["reason"]
    assert client.get(f"{API}/participants/{bad}", headers=H.coord).json()["eligibility_status"] == "SCREEN_FAILURE"


def test_measurement_blocked_until_eligible(client, H):
    pid = new_participant(client, H)
    client.post(f"{API}/participants/{pid}/consent", json={}, headers=H.coord)
    r = client.post(f"{API}/participants/{pid}/measurements", json={"visit_week": 0, "hba1c": 9}, headers=H.coord)
    assert r.status_code == 409


def test_followup_blocked_before_baseline(client, H):
    pid = new_participant(client, H)
    to_eligible(client, H, pid)
    r = client.post(f"{API}/participants/{pid}/measurements", json={"visit_week": 4, "hba1c": 8.5}, headers=H.coord)
    assert r.status_code == 409 and "Baseline" in r.json()["error"]


def test_followup_blocked_until_randomized(client, H):
    pid = baselined(client, H)
    r = client.post(f"{API}/participants/{pid}/measurements", json={"visit_week": 4, "hba1c": 8.5}, headers=H.coord)
    assert r.status_code == 409 and "randomized" in r.json()["error"]
    assert randomize(client, H, pid).status_code == 201
    r = client.post(f"{API}/participants/{pid}/measurements", json={"visit_week": 4, "hba1c": 8.5}, headers=H.coord)
    assert r.status_code == 201


def test_partial_baseline_does_not_complete(client, H):
    pid = new_participant(client, H)
    to_eligible(client, H, pid)
    r = client.post(f"{API}/participants/{pid}/measurements", json={"visit_week": 0, "hba1c": 9}, headers=H.coord)
    assert r.json()["baseline_complete"] is False


def test_baseline_completion_sets_stratum_inputs_and_schedules_visits(client, H):
    pid = baselined(client, H, hba1c=9.2)
    p = client.get(f"{API}/participants/{pid}", headers=H.coord).json()
    assert p["baseline_complete"] is True and p["trial_status"] == "ENROLLED"
    assert p["hba1c_cat"] == "HIGH" and p["baseline_hba1c"] == 9.2
    weeks = [v["visit_week"] for v in client.get(f"{API}/participants/{pid}/visits", headers=H.coord).json()]
    assert weeks == [0, 4, 8, 12, 16]


def test_low_hba1c_category(client, H):
    pid = baselined(client, H, hba1c=8.0)
    assert client.get(f"{API}/participants/{pid}", headers=H.coord).json()["hba1c_cat"] == "LOW"


def test_randomization_uses_modules_stratum_inputs(client, H):
    pid = baselined(client, H, hba1c=9.2, site="SITE-02")
    r = randomize(client, H, pid)
    assert r.status_code == 201 and r.json()["arm"] is None      # coordinator is blinded
    assert randomize(client, H, pid).status_code == 409           # only once


def test_week16_completes_trial_and_blocks_more_data(client, H):
    pid = enrolled(client, H)
    for w in (4, 8, 12, 16):
        assert client.post(f"{API}/participants/{pid}/measurements",
                           json={"visit_week": w, "hba1c": 8.0}, headers=H.coord).status_code == 201
    assert client.get(f"{API}/participants/{pid}", headers=H.coord).json()["trial_status"] == "COMPLETED"
    r = client.post(f"{API}/participants/{pid}/measurements", json={"visit_week": 16, "hba1c": 8}, headers=H.coord)
    assert r.status_code == 409


def test_withdrawn_participant_cannot_continue(client, H):
    pid = enrolled(client, H)
    assert client.post(f"{API}/participants/{pid}/withdraw", json={"reason": "Moved away"},
                       headers=H.coord).status_code == 200
    r = client.post(f"{API}/participants/{pid}/measurements", json={"visit_week": 4, "hba1c": 8}, headers=H.coord)
    assert r.status_code == 409
    assert client.post(f"{API}/participants/{pid}/withdraw", json={"reason": "again"},
                       headers=H.coord).status_code == 409


def test_validation_error_shape_and_week(client, H):
    pid = enrolled(client, H)
    r = client.post(f"{API}/participants/{pid}/measurements", json={"visit_week": 5, "hba1c": 8}, headers=H.coord)
    assert r.status_code == 422 and set(r.json()) == {"error", "code"}
    r = client.post(f"{API}/participants/{pid}/measurements", json={"visit_week": 4}, headers=H.coord)
    assert r.status_code == 422


def test_abnormal_flags_returned(client, H):
    pid = enrolled(client, H)
    r = client.post(f"{API}/participants/{pid}/measurements",
                    json={"visit_week": 4, "hba1c": 8, "systolic": 175, "spo2": 90}, headers=H.coord).json()
    assert "systolic_high" in r["abnormal_flags"] and "spo2_low" in r["abnormal_flags"]


def test_adverse_event_flow(client, H):
    pid = enrolled(client, H)
    body = {"participant_id": pid, "onset_date": str(date.today()), "severity": "SEVERE",
            "serious": True, "description": "Synthetic test event"}
    ae = client.post(f"{API}/adverse-events", json=body, headers=H.coord).json()
    assert ae["status"] == "SUBMITTED"
    r = client.post(f"{API}/adverse-events/{ae['id']}/review", json={"status": "UNDER_REVIEW"}, headers=H.coord)
    assert r.json()["status"] == "UNDER_REVIEW"
    r = client.post(f"{API}/adverse-events/{ae['id']}/review",
                    json={"status": "CLOSED", "relationship_to_treatment": "NOT_RELATED"}, headers=H.coord)
    assert r.json()["status"] == "CLOSED"
    assert client.post(f"{API}/adverse-events/{ae['id']}/review", json={"status": "CLOSED"},
                       headers=H.coord).status_code == 409


def test_supervisor_cannot_review_ae_or_enroll_but_can_view(client, H):
    pid = enrolled(client, H)
    ae = client.post(f"{API}/adverse-events", json={
        "participant_id": pid, "onset_date": str(date.today()), "severity": "MILD",
        "description": "Synthetic"}, headers=H.coord).json()
    assert client.post(f"{API}/adverse-events/{ae['id']}/review", json={"status": "CLOSED"},
                       headers=H.sup).status_code == 403
    assert client.post(f"{API}/participants", json={"site_id": "SITE-01", "age": 40, "sex": "M"},
                       headers=H.sup).status_code == 403
    assert client.get(f"{API}/adverse-events", headers=H.sup).status_code == 200


def test_patient_sees_only_own_record(client, H):
    a = new_participant(client, H)
    b = new_participant(client, H)
    assert client.get(f"{API}/participants/{a}", headers=H.patient(a)).status_code == 200
    assert client.get(f"{API}/participants/{b}", headers=H.patient(a)).status_code == 403
    assert client.get(f"{API}/participants", headers=H.patient(a)).status_code == 403
    assert client.get(f"{API}/alerts", headers=H.patient(a)).status_code == 403
    body = {"participant_id": b, "onset_date": str(date.today()), "severity": "MILD", "description": "x y z"}
    assert client.post(f"{API}/adverse-events", json=body, headers=H.patient(a)).status_code == 403


def test_patient_can_report_own_ae_and_list_is_filtered(client, H):
    a, b = enrolled(client, H), enrolled(client, H)
    own = {"participant_id": a, "onset_date": str(date.today()), "severity": "MILD", "description": "Own event"}
    assert client.post(f"{API}/adverse-events", json=own, headers=H.patient(a)).status_code == 201
    client.post(f"{API}/adverse-events", json={**own, "participant_id": b}, headers=H.coord)
    items = client.get(f"{API}/adverse-events", headers=H.patient(a)).json()["items"]
    assert [i["participant_id"] for i in items] == [a]


def test_writes_are_audited(client, H, caplog):
    with caplog.at_level(logging.INFO, logger="trace.audit"):
        enrolled(client, H)
    for event in ("PARTICIPANT_CREATED", "CONSENT_RECORDED", "SCREENING_COMPLETED",
                  "MEASUREMENT_RECORDED", "BASELINE_COMPLETED"):
        assert event in caplog.text


def test_overdue_visit_creates_alert(client, H, db):
    pid = enrolled(client, H)
    v = db.query(Visit).filter_by(participant_id=pid, visit_week=4).one()
    v.scheduled_date = date.today() - timedelta(days=3)
    db.commit()
    items = client.get(f"{API}/alerts", headers=H.coord).json()["items"]
    assert any(a["type"] == "OVERDUE_VISIT" and a["participant_id"] == pid for a in items)


def test_alerts_pagination_shape(client, H):
    for _ in range(3):
        new_participant(client, H)
    r = client.get(f"{API}/alerts?page=1&page_size=2", headers=H.coord).json()
    assert set(r) == {"items", "total", "page", "page_size"} and len(r["items"]) == 2 and r["total"] == 3


def test_participant_list_has_randomization_number_and_hides_arm(client, H):
    pid = enrolled(client, H)
    for headers in (H.coord, H.sup):
        item = client.get(f"{API}/participants", headers=headers).json()["items"][0]
        assert item["participant_id"] == pid and item["randomization_number"].startswith("RAND-")
        assert item["arm"] is None                       # blinded users get null, not an error
    one = client.get(f"{API}/participants/{pid}", headers=H.coord).json()
    assert one["arm"] is None and one["randomization_number"].startswith("RAND-")


def test_unblinded_supervisor_sees_arm_on_participants(client, H):
    enrolled(client, H)
    item = client.get(f"{API}/participants", headers=H.sup_unblinded).json()["items"][0]
    assert item["arm"] in ("A", "B")


def test_patient_never_gets_arm_and_screen_failure_reason_shown(client, H):
    pid = enrolled(client, H)
    assert client.get(f"{API}/participants/{pid}", headers=H.patient(pid)).json()["arm"] is None
    bad = new_participant(client, H, age=70)
    client.post(f"{API}/participants/{bad}/consent", json={}, headers=H.coord)
    client.post(f"{API}/participants/{bad}/screening",
                json={"t2dm_confirmed": True, "hba1c": 9, "therapy": "STABLE"}, headers=H.coord)
    got = client.get(f"{API}/participants/{bad}", headers=H.coord).json()
    assert got["eligibility_status"] == "SCREEN_FAILURE" and "age_in_range" in got["eligibility_reason"]
