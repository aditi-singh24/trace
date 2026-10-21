import time

import pytest

from module4_auth.permissions import ALL_ACTIONS, can_access_participant, can_see_arm, check_permission
from module4_auth.security import create_access_token
from tests.conftest import PASSWORD, auth, make_user

P, C, S = "PATIENT", "COORDINATOR", "SUPERVISOR"

# Independent copy of the spec's permission matrix (Section 6, Module 4).
EXPECTED = {
    "view_own_record": {P: True, C: True, S: True},
    "view_participants": {P: False, C: True, S: True},
    "enroll_consent_screen": {P: False, C: True, S: False},
    "record_visits_measurements": {P: False, C: True, S: False},
    "report_adverse_event": {P: True, C: True, S: False},
    "review_adverse_events": {P: False, C: True, S: False},
    "view_adverse_events": {P: False, C: True, S: True},
    "randomize": {P: False, C: True, S: False},
    "operational_dashboard": {P: False, C: True, S: True},
    "oversight_dashboard": {P: False, C: False, S: True},
    "export_csv": {P: False, C: False, S: True},
    "view_audit": {P: False, C: False, S: True},
    "manage_users": {P: False, C: False, S: True},
}


class _U:
    def __init__(self, role, unblinded=False, active=True, participant_id=None):
        self.role, self.unblinded, self.active, self.participant_id = role, unblinded, active, participant_id


@pytest.mark.parametrize("action", sorted(EXPECTED))
@pytest.mark.parametrize("role", [P, C, S])
def test_permission_matrix(action, role):
    assert check_permission(_U(role), action) is EXPECTED[action][role]


def test_matrix_covers_every_action():
    assert set(ALL_ACTIONS) == set(EXPECTED) | {"see_arm"}


def test_unknown_action_and_inactive_user_denied():
    assert check_permission(_U(S), "does_not_exist") is False
    assert check_permission(_U(S, active=False), "view_audit") is False
    assert check_permission(None, "view_audit") is False


@pytest.mark.parametrize("user,expected", [
    (_U(P), False), (_U(C), False), (_U(S), False), (_U(S, unblinded=True), True),
    (_U(C, unblinded=True), False), (_U(P, unblinded=True), False),
    (_U(S, unblinded=True, active=False), False), (None, False),
])
def test_can_see_arm(user, expected):
    assert can_see_arm(user) is expected
    assert check_permission(user, "see_arm") is expected


def test_patient_only_own_record():
    patient = _U(P, participant_id="SUB-001")
    assert can_access_participant(patient, "SUB-001")
    assert not can_access_participant(patient, "SUB-002")
    assert not can_access_participant(_U(P), "SUB-001")
    assert can_access_participant(_U(C), "SUB-002")


def test_login_success_and_me(client, db):
    make_user(db, "coord", C)
    r = client.post("/api/v1/auth/login", json={"username": "Coord", "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 3600
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["username"] == "coord" and me.json()["role"] == C
    assert "password_hash" not in me.json()


def test_login_failures(client, db):
    make_user(db, "coord", C)
    make_user(db, "gone", C, active=False)
    assert client.post("/api/v1/auth/login", json={"username": "coord", "password": "wrong"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "nobody", "password": "x"}).status_code == 401
    r = client.post("/api/v1/auth/login", json={"username": "gone", "password": PASSWORD})
    assert r.status_code == 403 and r.json() == {"error": "Account is inactive", "code": 403}


def test_password_stored_as_bcrypt(db):
    user = make_user(db, "coord", C)
    assert user.password_hash.startswith("$2") and PASSWORD not in user.password_hash


def test_missing_bad_and_expired_token(client, db):
    user = make_user(db, "coord", C)
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401
    token, _ = create_access_token(user.id, user.role, expires_minutes=-1)
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_deactivated_user_token_blocked(client, db):
    user = make_user(db, "coord", C)
    headers = auth(user)
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    user.active = False
    db.commit()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 403


def test_only_supervisor_manages_users(client, db):
    coord, sup = make_user(db, "coord", C), make_user(db, "sup", S)
    body = {"username": "newcoord", "password": "long-enough-pw", "role": C}
    assert client.post("/api/v1/auth/users", json=body, headers=auth(coord)).status_code == 403
    r = client.post("/api/v1/auth/users", json=body, headers=auth(sup))
    assert r.status_code == 201 and r.json()["id"].startswith("U-") and r.json()["unblinded"] is False
    assert client.post("/api/v1/auth/users", json=body, headers=auth(sup)).status_code == 409


def test_create_user_validation(client, db):
    sup = make_user(db, "sup", S)
    h = auth(sup)
    base = {"username": "abc", "password": "long-enough-pw", "role": P}
    assert client.post("/api/v1/auth/users", json=base, headers=h).status_code == 422  # patient needs participant_id
    assert client.post("/api/v1/auth/users", json={**base, "role": "ADMIN"}, headers=h).status_code == 422
    assert client.post("/api/v1/auth/users", json={**base, "password": "short"}, headers=h).status_code == 422
    ok = client.post("/api/v1/auth/users", json={**base, "participant_id": "SUB-001"}, headers=h)
    assert ok.status_code == 201 and ok.json()["participant_id"] == "SUB-001"


def test_unblinded_cannot_be_granted_through_api(client, db):
    sup = make_user(db, "sup", S)
    target = make_user(db, "other", S)
    h = auth(sup)
    r = client.post("/api/v1/auth/users", json={"username": "newsup", "password": "long-enough-pw",
                                                "role": S, "unblinded": True}, headers=h)
    assert r.status_code == 201 and r.json()["unblinded"] is False
    r = client.patch(f"/api/v1/auth/users/{target.id}", json={"unblinded": True}, headers=h)
    assert r.status_code == 422


def test_patch_user_and_self_deactivation(client, db):
    sup, coord = make_user(db, "sup", S), make_user(db, "coord", C)
    h = auth(sup)
    assert client.patch(f"/api/v1/auth/users/{sup.id}", json={"active": False}, headers=h).status_code == 400
    assert client.patch(f"/api/v1/auth/users/{coord.id}", json={"active": False}, headers=h).status_code == 200
    assert client.patch("/api/v1/auth/users/U-9999", json={"active": False}, headers=h).status_code == 404
    assert client.patch(f"/api/v1/auth/users/{coord.id}", json={"active": True}, headers=auth(coord)).status_code == 403


def test_error_shape(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401 and set(r.json()) == {"error", "code"}
