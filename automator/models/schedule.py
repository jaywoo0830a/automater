"""ObservationSchedule model -- one row per planned observation time."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from automator.models.base import Base


class ObservationSchedule(Base):
    __tablename__ = "observation_schedules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    observation_id: Mapped[int | None] = mapped_column(
        ForeignKey("observations.id"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow,
    )

    campaign: Mapped["Campaign"] = relationship("Campaign", lazy="joined")  # type: ignore[name-defined]
    observation: Mapped["Observation | None"] = relationship(  # type: ignore[name-defined]
        "Observation", lazy="joined",
    )
