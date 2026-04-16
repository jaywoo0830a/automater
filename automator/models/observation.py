"""Observation model -- one row per observer session execution."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from automator.models.base import Base


class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))

    # Search results
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    found_in: Mapped[str | None] = mapped_column(String(32), nullable=True)
    post_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Visit behaviour
    scroll_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    dwell_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    entered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    exited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Session fingerprint
    session_ip: Mapped[str] = mapped_column(String(45))
    fingerprint: Mapped[str] = mapped_column(String(64))
    user_agent: Mapped[str] = mapped_column(String(512))
    viewport_width: Mapped[int] = mapped_column(Integer)
    viewport_height: Mapped[int] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow,
    )
