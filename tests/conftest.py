import os

os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production-0123456789")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
os.environ.pop("RANDOMIZATION_SEED", None)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import module2_core.models  # noqa: F401  (register tables)
import module4_auth.models  # noqa: F401
import module5_engine.models  # noqa: F401
from main import app
from module4_auth.models import User
from module4_auth.security import create_access_token, hash_password
from shared.config import get_settings
from shared.db import Base, get_db

PASSWORD = "correct-horse-battery"

# The real `participants` table now comes from Module 2 (module2_core.models) through
# Base.metadata.create_all, so the old stand-in table is gone.


@pytest.fixture(autouse=True)
def _fresh_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        yield session


@pytest.fixture()
def client(engine):
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def _get_db():
        with Session() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_user(db, username, role, *, unblinded=False, active=True, participant_id=None, uid=None):
    n = db.query(User).count() + 1
    user = User(id=uid or f"U-{n:04d}", username=username, password_hash=hash_password(PASSWORD),
                role=role, unblinded=unblinded, active=active, participant_id=participant_id)
    db.add(user)
    db.commit()
    return user


def auth(user, minutes=None):
    token, _ = create_access_token(user.id, user.role, expires_minutes=minutes)
    return {"Authorization": f"Bearer {token}"}


def add_participant(db, pid, site="SITE-01", cat="HIGH", therapy="STABLE",
                    eligibility="ELIGIBLE", consent="OBTAINED", baseline=True):
    db.execute(
        text("INSERT INTO participants (participant_id, site_id, hba1c_cat, therapy, "
             "eligibility_status, consent_status, baseline_complete) "
             "VALUES (:p, :s, :c, :t, :e, :cs, :b)"),
        {"p": pid, "s": site, "c": cat, "t": therapy, "e": eligibility, "cs": consent, "b": baseline},
    )
    db.commit()
