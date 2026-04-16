"""SQLAlchemy 2.0 declarative base and factory helpers."""

from __future__ import annotations

from sqlalchemy import create_engine as _create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Shared declarative base for all automator models."""


def create_engine_from_url(url: str, *, echo: bool = False):
    """Create a SQLAlchemy engine from a database URL.

    Defaults are tuned for a long-running daemon:
    - ``pool_pre_ping`` keeps connections healthy across MySQL timeouts.
    - ``pool_recycle`` rotates connections before MySQL's 8-hour default.
    """
    return _create_engine(
        url,
        echo=echo,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


def create_session_factory(engine) -> sessionmaker[Session]:
    """Return a sessionmaker bound to *engine*."""
    return sessionmaker(bind=engine, expire_on_commit=False)
