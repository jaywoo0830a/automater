"""
factory/db.py
--------------
SQLAlchemy 2.0 engine factory and schema management.

Schema is defined entirely by the ORM models in factory/models.py.
No external .sql files are needed.

    engine = get_engine()
    create_schema(engine)   # CREATE TABLE IF NOT EXISTS …

    with Session(engine) as session, session.begin():
        session.add(obj)

Ref: https://docs.sqlalchemy.org/en/20/orm/session_basics.html
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def build_mysql_url() -> str:
    """Build a MySQL+PyMySQL connection URL from DB_* env vars."""
    host     = os.environ.get("DB_HOST",     "127.0.0.1")
    port     = os.environ.get("DB_PORT",     "3306")
    database = os.environ.get("DB_NAME",     "automator")
    user     = os.environ.get("DB_USER",     "automator")
    password = os.environ.get("DB_PASSWORD", "automatorpass")
    return (
        f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
        "?charset=utf8mb4"
    )


def get_engine(url: str | None = None, **kwargs: object) -> Engine:
    """
    Create a SQLAlchemy Engine.

    Args:
        url:    Connection URL. Falls back to DB_* env vars when None.
        kwargs: Extra keyword arguments forwarded to create_engine().
    """
    if url is None:
        url = build_mysql_url()
    return create_engine(url, pool_pre_ping=True, **kwargs)


def create_schema(engine: Engine) -> None:
    """Create all tables defined in factory.models (IF NOT EXISTS)."""
    from factory.models import Base
    Base.metadata.create_all(engine)


def drop_schema(engine: Engine) -> None:
    """Drop all tables defined in factory.models."""
    from factory.models import Base
    Base.metadata.drop_all(engine)
