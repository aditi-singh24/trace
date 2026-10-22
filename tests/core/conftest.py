"""Fixtures for Modules 2 and 3. Reuses engine/db/client/make_user/auth from tests/conftest.py."""
import pytest

from module2_core.models import Site, Trial
from shared.constants import COORDINATOR, PATIENT, SUPERVISOR
from tests.conftest import auth, make_user


@pytest.fixture(autouse=True)
def _trial_setup(db):
    db.add_all([Site(site_id="SITE-01", name="Demo Site 1"),
                Site(site_id="SITE-02", name="Demo Site 2"),
                Trial(name="Demo T2D trial", target_enrollment=10)])
    db.commit()


class Heads:
    """Auth headers for each kind of user."""

    def __init__(self, db):
        self._db = db
        self._patients = {}
        self.coord = auth(make_user(db, "coord", COORDINATOR))
        self.sup = auth(make_user(db, "sup", SUPERVISOR))
        self.sup_unblinded = auth(make_user(db, "sup_ub", SUPERVISOR, unblinded=True))

    def patient(self, pid):
        if pid not in self._patients:
            user = make_user(self._db, f"patient_{pid.lower()}", PATIENT, participant_id=pid)
            self._patients[pid] = auth(user)
        return self._patients[pid]


@pytest.fixture()
def H(db):
    return Heads(db)
