"""Data shapes: SQLAlchemy tables + pydantic verdict schema (the module contract)."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc)
    )
    attack_class: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str] = mapped_column(Text)
    scan_blocked: Mapped[bool] = mapped_column(Boolean)
    scan_detected: Mapped[list] = mapped_column(JSONB)
    scan_score: Mapped[float] = mapped_column(Float)
    agent_action: Mapped[str] = mapped_column(String(64))
    authorized: Mapped[bool] = mapped_column(Boolean)
    bypass: Mapped[bool] = mapped_column(Boolean)
    verdict: Mapped[dict] = mapped_column(JSONB)
    trace_id: Mapped[str] = mapped_column(String(32))


# --- pydantic verdict (JSON returned by the slice) --------------------------


class Verdict(BaseModel):
    bypass: bool
    attack_class: str
    scan_blocked: bool
    scan_detected: list[str]
    agent_action: str
    authorized: bool
    score: int
    band: str
    trace_id: str
    finding_id: int | None = None
    detail: str = ""
