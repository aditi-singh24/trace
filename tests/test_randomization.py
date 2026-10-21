import pytest
from sqlalchemy import select

from module5_engine.models import AllocationBlock, Assignment, AuditEntry
from module5_engine.randomization import (
    AlreadyRandomized,
    ParticipantNotFound,
    PrerequisiteNotMet,
    block_arms_from_seed,
    randomize,
)
from shared.config import get_settings
from tests.conftest import add_participant, auth, make_user

URL = "/api/v1/randomization"


def _arms(db, stratum=None):
    q = select(Assignment).order_by(Assignment.id)
    rows = db.scalars(q).all()
    return [r.arm for r in rows if stratum is None or r.stratum_key == stratum]


def test_balance_within_stratum(db):
    for i in range(40):
        add_participant(db, f"SUB-{i:03d}")
        randomize(f"SUB-{i:03d}", "U-0001", db=db)
    db.commit()
    arms = _arms(db)
    assert arms.count("A") == arms.count("B") == 20
    # after every complete block of 4, arms are exactly balanced; mid-block never off by more than 2
    for n in range(1, 41):
        a = arms[:n].count("A")
        b = n - a
        assert abs(a - b) <= 2
        if n % 4 == 0:
            assert a == b


def test_each_stratum_is_balanced_independently(db):
    strata = [("SITE-01", "LOW", "STABLE"), ("SITE-01", "HIGH", "NONE"), ("SITE-02", "HIGH", "STABLE")]
    i = 0
    for site, cat, therapy in strata:
        for _ in range(8):
            pid = f"SUB-{i:03d}"
            add_participant(db, pid, site, cat, therapy)
            randomize(pid, "U-0001", db=db)
            i += 1
    db.commit()
    for site, cat, therapy in strata:
        arms = _arms(db, f"{site}|{cat}|{therapy}")
        assert len(arms) == 8 and arms.count("A") == arms.count("B") == 4


def test_new_block_created_when_used_up(db):
    for i in range(5):
        add_participant(db, f"SUB-{i}")
        randomize(f"SUB-{i}", "U-0001", db=db)
    db.commit()
    blocks = {b.block_no for b in db.scalars(select(AllocationBlock))}
    assert blocks == {1, 2}


def test_duplicate_randomization_blocked(db):
    add_participant(db, "SUB-001")
    randomize("SUB-001", "U-0001", db=db)
    db.commit()
    with pytest.raises(AlreadyRandomized):
        randomize("SUB-001", "U-0001", db=db)
    assert db.query(Assignment).count() == 1
    assert db.query(AuditEntry).count() == 1


def test_randomization_numbers_unique_and_formatted(db):
    nums = []
    for i in range(6):
        add_participant(db, f"SUB-{i}")
        nums.append(randomize(f"SUB-{i}", "U-0001", db=db)["randomization_number"])
    assert len(set(nums)) == 6 and nums[0] == "RAND-0001" and nums[-1] == "RAND-0006"


@pytest.mark.parametrize("kwargs,fragment", [
    ({"eligibility": "PENDING_REVIEW"}, "eligibility"),
    ({"eligibility": "SCREEN_FAILURE"}, "eligibility"),
    ({"consent": "NOT_OBTAINED"}, "consent"),
    ({"consent": "WITHDRAWN"}, "consent"),
    ({"baseline": False}, "baseline"),
    ({"cat": None}, "HbA1c"),
    ({"therapy": None}, "therapy"),
])
def test_each_prerequisite_blocks_randomization(db, kwargs, fragment):
    add_participant(db, "SUB-001", **kwargs)
    with pytest.raises(PrerequisiteNotMet) as exc:
        randomize("SUB-001", "U-0001", db=db)
    assert fragment in exc.value.message
    assert db.query(Assignment).count() == 0 and db.query(AuditEntry).count() == 0


def test_unknown_participant(db):
    with pytest.raises(ParticipantNotFound):
        randomize("SUB-404", "U-0001", db=db)


def test_reproducible_from_stored_seed(db):
    for i in range(8):
        add_participant(db, f"SUB-{i}")
        randomize(f"SUB-{i}", "U-0001", db=db)
    db.commit()
    for block_no in (1, 2):
        rows = db.scalars(select(AllocationBlock).where(AllocationBlock.block_no == block_no)
                          .order_by(AllocationBlock.position)).all()
        assert len({r.seed for r in rows}) == 1
        assert [r.arm for r in rows] == block_arms_from_seed(rows[0].seed)
        assert sorted(r.arm for r in rows) == ["A", "A", "B", "B"]


def test_master_seed_makes_sequence_repeatable(db, engine, monkeypatch):
    from sqlalchemy.orm import sessionmaker

    monkeypatch.setenv("RANDOMIZATION_SEED", "demo-seed")

    def run(session):
        get_settings.cache_clear()
        out = []
        for i in range(8):
            add_participant(session, f"SUB-{i}")
            out.append(randomize(f"SUB-{i}", "U-0001", db=session)["arm"])
        session.commit()
        return out

    first = run(db)
    session = db
    for table in ("assignments", "allocation_blocks", "audit_chain", "participants"):
        session.execute(__import__("sqlalchemy").text(f"DELETE FROM {table}"))
    session.commit()
    assert run(session) == first


def test_chain_entry_in_same_transaction(db):
    add_participant(db, "SUB-001")
    randomize("SUB-001", "U-0001", db=db)
    db.rollback()  # caller never committed: neither assignment nor chain entry survives
    assert db.query(Assignment).count() == 0 and db.query(AuditEntry).count() == 0


def test_endpoint_blinded_callers_get_no_arm(client, db):
    coord = make_user(db, "coord", "COORDINATOR")
    add_participant(db, "SUB-001")
    r = client.post(URL, json={"participant_id": "SUB-001"}, headers=auth(coord))
    assert r.status_code == 201
    body = r.json()
    assert body["arm"] is None and body["randomization_number"] == "RAND-0001"
    assert "message" in body
    assert db.query(Assignment).count() == 1 and db.query(AuditEntry).count() == 1


def test_endpoint_status_codes(client, db):
    coord = make_user(db, "coord", "COORDINATOR")
    patient = make_user(db, "pat", "PATIENT", participant_id="SUB-001")
    sup = make_user(db, "sup", "SUPERVISOR")
    add_participant(db, "SUB-001")
    add_participant(db, "SUB-002", consent="NOT_OBTAINED")
    body = {"participant_id": "SUB-001"}
    assert client.post(URL, json=body).status_code == 401
    assert client.post(URL, json=body, headers=auth(patient)).status_code == 403
    assert client.post(URL, json=body, headers=auth(sup)).status_code == 403
    assert client.post(URL, json={"participant_id": "SUB-002"}, headers=auth(coord)).status_code == 400
    assert client.post(URL, json={"participant_id": "SUB-404"}, headers=auth(coord)).status_code == 404
    assert client.post(URL, json={}, headers=auth(coord)).status_code == 422
    assert client.post(URL, json=body, headers=auth(coord)).status_code == 201
    dup = client.post(URL, json=body, headers=auth(coord))
    assert dup.status_code == 409 and dup.json()["code"] == 409
    assert db.query(Assignment).count() == 1
