"""Campaign model -- created by web/api when a blog post is published."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from automator.models.base import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    blog_id: Mapped[str] = mapped_column(String(64))
    keyword: Mapped[str] = mapped_column(String(255))
    post_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    platform: Mapped[str] = mapped_column(String(32), default="naver")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow,
    )
