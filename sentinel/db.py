"""DB edge: engine, session factory, and a small idempotent migration runner."""
from __future__ import annotations

import pathlib

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from sentinel.config import DATABASE_URL

_MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "migrations"

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False, future=True)


def run_migrations() -> list[str]:
    """Apply every migrations/*.sql in filename order. SQL is written idempotently
    (IF NOT EXISTS / CREATE EXTENSION IF NOT EXISTS), so re-running is safe."""
    applied: list[str] = []
    files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    with engine.begin() as conn:
        for f in files:
            conn.execute(text(f.read_text()))
            applied.append(f.name)
    return applied


def provision_verifier_role() -> None:
    """Align the firewalled verifier's Postgres role password with the generated
    VERIFIER_DATABASE_URL secret (SOF-170). The role and its least-privilege grants
    are created by migrations/003; on Cloud SQL the password is a strong random value
    from Secret Manager, so we set it here rather than baking it into SQL. Idempotent.
    The role's DATA firewall (no read on corpus/findings) is unchanged."""
    from sqlalchemy.engine import make_url

    from sentinel.config import VERIFIER_DATABASE_URL

    pw = make_url(VERIFIER_DATABASE_URL).password or ""
    if not pw.isalnum():  # generated secrets are alnum; refuse to inline anything else
        raise ValueError("verifier DB password must be alphanumeric to set safely")
    with engine.begin() as conn:
        conn.execute(text(f"ALTER ROLE sentinel_verifier WITH LOGIN PASSWORD '{pw}'"))


def ping() -> bool:
    with engine.connect() as conn:
        return conn.execute(text("SELECT 1")).scalar_one() == 1


if __name__ == "__main__":  # `python -m sentinel.db` -> run migrations
    print("applied migrations:", run_migrations())
