"""Create the first users for local demos (synthetic accounts only).

    SEED_PASSWORD='something-long' python -m module4_auth.seed

If SEED_PASSWORD is not set, a random one is generated and printed once.
This script is the only place the `unblinded` flag is set (open decision 11).
"""
from __future__ import annotations

import os
import secrets

from sqlalchemy import select

from module4_auth.models import User
from module4_auth.security import hash_password
from shared.constants import COORDINATOR, SUPERVISOR
from shared.db import Base, get_engine, get_session_factory

SEED_USERS = [
    # (id, username, role, unblinded)
    ("U-0001", "supervisor", SUPERVISOR, False),
    ("U-0002", "supervisor_unblinded", SUPERVISOR, True),
    ("U-0003", "coordinator", COORDINATOR, False),
]


def main() -> None:
    password = os.environ.get("SEED_PASSWORD") or secrets.token_urlsafe(12)
    generated = "SEED_PASSWORD" not in os.environ
    Base.metadata.create_all(get_engine(), tables=[User.__table__])
    with get_session_factory()() as db:
        for uid, username, role, unblinded in SEED_USERS:
            if db.scalar(select(User).where(User.username == username)):
                print(f"skip {username} (exists)")
                continue
            db.add(User(id=uid, username=username, password_hash=hash_password(password),
                        role=role, unblinded=unblinded, active=True))
            print(f"created {username} ({role}{', unblinded' if unblinded else ''})")
        db.commit()
    if generated:
        print(f"generated password (shown once): {password}")


if __name__ == "__main__":
    main()
