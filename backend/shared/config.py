"""Environment-based settings. Secrets are never committed (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

try:  # optional convenience for local development
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    jwt_expire_minutes: int
    cors_origins: list
    # Optional master seed. If unset, every allocation block gets a fresh random
    # seed that is stored with the block so results stay reproducible.
    randomization_seed: Optional[str]


@lru_cache
def get_settings() -> Settings:
    jwt_secret = os.environ.get("JWT_SECRET", "")
    if not jwt_secret or jwt_secret == "xxxx":
        raise RuntimeError("JWT_SECRET must be set in the environment (see .env.example)")
    origins = os.environ.get("CORS_ORIGINS", "")
    return Settings(
        database_url=os.environ.get("DATABASE_URL", ""),
        jwt_secret=jwt_secret,
        jwt_expire_minutes=int(os.environ.get("JWT_EXPIRE_MINUTES", "60")),
        cors_origins=[o.strip() for o in origins.split(",") if o.strip()],
        randomization_seed=os.environ.get("RANDOMIZATION_SEED") or None,
    )
