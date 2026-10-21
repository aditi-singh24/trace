import json

from sqlalchemy import text

from module5_engine.audit import canonical_json, compute_hash, record_audit_event, verify_chain
from module5_engine.models import AuditEntry
from shared.constants import GENESIS_HASH
from tests.conftest import add_participant, auth, make_user


def _chain(db, n=5):
    for i in range(n):
        record_audit_event("RANDOMIZED", "U-0001", {"participant_id": f"SUB-{i:03d}", "n": i}, db=db)
    db.commit()


def test_empty_chain_is_ok(db):
    assert verify_chain(db) == {"ok": True, "first_broken_seq": None, "entries_checked": 0}


def test_genesis_and_linking(db):
    _chain(db, 3)
    rows = db.query(AuditEntry).order_by(AuditEntry.seq).all()
    assert [r.seq for r in rows] == [1, 2, 3]
    assert rows[0].prev_hash == GENESIS_HASH == "0" * 64
    assert rows[1].prev_hash == rows[0].hash and rows[2].prev_hash == rows[1].hash


def test_hash_formula(db):
    _chain(db, 1)
    e = db.query(AuditEntry).one()
    entry = {"seq": e.seq, "event_type": e.event_type, "actor_id": e.actor_id, "payload": e.payload,
             "created_at": e.created_at, "prev_hash": e.prev_hash}
    assert e.hash == compute_hash(GENESIS_HASH, entry)
    assert canonical_json({"b": 1, "a": [1, 2]}) == '{"a":[1,2],"b":1}'
    assert created_at_is_utc_iso(e.created_at)


def created_at_is_utc_iso(value):
    return value.endswith("Z") and "T" in value


def test_valid_chain_passes(db):
    _chain(db, 5)
    assert verify_chain(db) == {"ok": True, "first_broken_seq": None, "entries_checked": 5}


def test_edited_payload_detected(db):
    _chain(db, 5)
    db.execute(text("UPDATE audit_chain SET payload = :p WHERE seq = 3"),
               {"p": json.dumps({"participant_id": "SUB-999", "n": 2})})
    db.commit()
    assert verify_chain(db) == {"ok": False, "first_broken_seq": 3, "entries_checked": 2}


def test_edited_actor_and_hash_detected(db):
    _chain(db, 4)
    db.execute(text("UPDATE audit_chain SET actor_id = 'U-9999' WHERE seq = 2"))
    db.commit()
    assert verify_chain(db)["first_broken_seq"] == 2


def test_recomputed_hash_still_breaks_next_link(db):
    """An attacker who fixes the edited row's own hash is caught by the next row's prev_hash."""
    _chain(db, 4)
    e = db.query(AuditEntry).filter_by(seq=2).one()
    new_payload = {"participant_id": "SUB-777", "n": 1}
    fields = {"seq": 2, "event_type": e.event_type, "actor_id": e.actor_id, "payload": new_payload,
              "created_at": e.created_at, "prev_hash": e.prev_hash}
    db.execute(text("UPDATE audit_chain SET payload = :p, hash = :h WHERE seq = 2"),
               {"p": json.dumps(new_payload), "h": compute_hash(e.prev_hash, fields)})
    db.commit()
    assert verify_chain(db)["first_broken_seq"] == 3


def test_deleted_entry_detected(db):
    _chain(db, 5)
    db.execute(text("DELETE FROM audit_chain WHERE seq = 3"))
    db.commit()
    assert verify_chain(db) == {"ok": False, "first_broken_seq": 3, "entries_checked": 2}


def test_orm_blocks_update_and_delete(db):
    import pytest
    from module5_engine.models import AuditChainImmutableError

    _chain(db, 2)
    entry = db.query(AuditEntry).first()
    entry.actor_id = "U-0666"
    with pytest.raises(AuditChainImmutableError):
        db.commit()
    db.rollback()
    db.delete(db.query(AuditEntry).first())
    with pytest.raises(AuditChainImmutableError):
        db.commit()
    db.rollback()
    assert verify_chain(db)["ok"] is True


def test_unchained_event_types_are_not_stored(db):
    assert record_audit_event("LOGIN_SUCCESS", "U-0001", {"username": "x"}, db=db) is None
    assert db.query(AuditEntry).count() == 0


def test_audit_endpoints_supervisor_only(client, db):
    sup = make_user(db, "sup", "SUPERVISOR")
    coord = make_user(db, "coord", "COORDINATOR")
    pat = make_user(db, "pat", "PATIENT", participant_id="SUB-001")
    _chain(db, 3)
    for path in ("/api/v1/audit/entries", "/api/v1/audit/verify"):
        assert client.get(path).status_code == 401
        assert client.get(path, headers=auth(coord)).status_code == 403
        assert client.get(path, headers=auth(pat)).status_code == 403
    r = client.get("/api/v1/audit/entries?page=1&page_size=2", headers=auth(sup))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3 and body["page"] == 1 and body["page_size"] == 2 and len(body["items"]) == 2
    assert client.get("/api/v1/audit/verify", headers=auth(sup)).json()["ok"] is True
    db.execute(text("UPDATE audit_chain SET actor_id = 'U-9999' WHERE seq = 2"))
    db.commit()
    assert client.get("/api/v1/audit/verify", headers=auth(sup)).json() == {
        "ok": False, "first_broken_seq": 2, "entries_checked": 1}


def test_arm_never_in_audit_or_blinded_responses(client, db):
    """Blinding: no arm in the randomize response or anywhere in the audit log."""
    coord = make_user(db, "coord", "COORDINATOR")
    sup = make_user(db, "sup", "SUPERVISOR")  # blinded
    add_participant(db, "SUB-001")
    resp = client.post("/api/v1/randomization", json={"participant_id": "SUB-001"}, headers=auth(coord))
    assert resp.json()["arm"] is None
    entries = client.get("/api/v1/audit/entries", headers=auth(sup)).json()["items"]
    assert len(entries) == 1 and entries[0]["event_type"] == "RANDOMIZED"
    assert "arm" not in entries[0]["payload"]
    assert entries[0]["payload"]["randomization_number"] == "RAND-0001"
