from tests.core.helpers import API, baselined, enrolled, new_participant, randomize


def _keys(obj, found=None):
    found = set() if found is None else found
    if isinstance(obj, dict):
        for k, v in obj.items():
            found.add(k)
            _keys(v, found)
    elif isinstance(obj, list):
        for v in obj:
            _keys(v, found)
    return found


def test_patient_dashboard_own_data_no_arm(client, H):
    pid = enrolled(client, H)
    d = client.get(f"{API}/reports/dashboard", headers=H.patient(pid)).json()
    assert d["participant_id"] == pid and d["total_weeks"] == 16
    assert d["latest_vitals"]["hba1c"] == 9.0 and d["next_visit"]["visit_week"] == 4
    assert "arm" not in _keys(d)


def test_patient_dashboard_requires_linked_participant(client, db):
    from shared.constants import PATIENT
    from tests.conftest import auth, make_user
    headers = auth(make_user(db, "unlinked", PATIENT))
    assert client.get(f"{API}/reports/dashboard", headers=headers).status_code == 400


def test_coordinator_dashboard_counts(client, H):
    enrolled(client, H)
    baselined(client, H)              # baseline done, not yet randomized
    new_participant(client, H)
    c = client.get(f"{API}/reports/dashboard", headers=H.coord).json()["counts"]
    assert c["registered"] == 3 and c["enrolled"] == 2 and c["awaiting_screening"] == 1
    assert c["awaiting_randomization"] == 1


def test_supervisor_dashboard_blinded_has_no_arm(client, H):
    enrolled(client, H)
    d = client.get(f"{API}/reports/dashboard", headers=H.sup).json()
    assert d["arm_breakdown"] is None and "A" not in d["funnel"]
    assert d["enrollment"] == {"target": 10, "actual": 1, "pct_of_target": 10}
    assert d["funnel"]["randomized"] == 1
    assert d["outcomes_all_participants"]["hba1c"][0]["mean"] == 9.0


def test_unblinded_supervisor_sees_arm_breakdown(client, H):
    enrolled(client, H)
    enrolled(client, H)
    d = client.get(f"{API}/reports/dashboard", headers=H.sup_unblinded).json()
    assert sum(d["arm_breakdown"]["counts"].values()) == 2


def test_operational_reports_forbidden_for_patient(client, H):
    pid = enrolled(client, H)
    for path in ("enrollment", "safety", "visits", "data-quality"):
        assert client.get(f"{API}/reports/{path}", headers=H.patient(pid)).status_code == 403
        assert client.get(f"{API}/reports/{path}", headers=H.coord).status_code == 200
        assert client.get(f"{API}/reports/{path}", headers=H.sup).status_code == 200


def test_data_quality_flags_consented_not_screened(client, H):
    pid = new_participant(client, H)
    client.post(f"{API}/participants/{pid}/consent", json={}, headers=H.coord)
    d = client.get(f"{API}/reports/data-quality", headers=H.coord).json()
    assert d["by_type"].get("CONSENTED_NOT_SCREENED") == 1


def test_csv_supervisor_only_blinded_hides_arm(client, H):
    enrolled(client, H)
    assert client.get(f"{API}/exports/participants.csv", headers=H.coord).status_code == 403
    r = client.get(f"{API}/exports/participants.csv", headers=H.sup)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0].split(",")[0] == "participant_id" and lines[0].split(",")[-1] == "arm"
    assert lines[1].split(",")[-1] == ""            # randomized, but blinded: arm column empty


def test_csv_unblinded_supervisor_sees_arm(client, H):
    enrolled(client, H)
    line = client.get(f"{API}/exports/participants.csv", headers=H.sup_unblinded).text.strip().splitlines()[1]
    assert line.split(",")[-1] in ("A", "B")


def test_no_arm_anywhere_for_blinded_users(client, H):
    pid = enrolled(client, H)
    for headers in (H.coord, H.sup, H.patient(pid)):
        d = client.get(f"{API}/reports/dashboard", headers=headers).json()
        assert "arm" not in _keys(d)
