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


def ping() -> bool:
    with engine.connect() as conn:
        return conn.execute(text("SELECT 1")).scalar_one() == 1


if __name__ == "__main__":  # `python -m sentinel.db` -> run migrations
    print("applied migrations:", run_migrations())
