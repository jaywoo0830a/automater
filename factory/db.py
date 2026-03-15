"""
factory/db.py
--------------
Thin MySQL connection wrapper using mysql-connector-python.

Usage:
    from factory.db import Database

    with Database.from_env() as db:
        rows = db.fetch_all("SELECT * FROM regions WHERE active = 1")
        db.execute("UPDATE accounts SET last_used_at = %s WHERE id = %s", (now, 1))
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any

try:
    import mysql.connector  # type: ignore[import]
    from mysql.connector import MySQLConnection
except ImportError:
    raise ImportError(
        "mysql-connector-python is required.\n"
        "Run: pip install mysql-connector-python"
    )


class Database:
    """
    Lightweight MySQL wrapper.

    Autocommit is OFF by default — call commit() or use as a context manager
    which commits on clean exit and rolls back on exception.
    """

    def __init__(self, connection: MySQLConnection) -> None:
        self._conn   = connection
        self._cursor = connection.cursor(dictionary=True)

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "Database":
        """Connect using DB_* environment variables (loaded from .env)."""
        conn = mysql.connector.connect(
            host     = os.environ.get("DB_HOST",     "127.0.0.1"),
            port     = int(os.environ.get("DB_PORT", "3306")),
            database = os.environ.get("DB_NAME",     "automator"),
            user     = os.environ.get("DB_USER",     "automator"),
            password = os.environ.get("DB_PASSWORD", "automatorpass"),
            charset  = "utf8mb4",
            autocommit = False,
        )
        return cls(conn)

    @classmethod
    def from_config(cls, **kwargs) -> "Database":
        """Connect with explicit keyword arguments."""
        conn = mysql.connector.connect(
            charset    = "utf8mb4",
            autocommit = False,
            **kwargs,
        )
        return cls(conn)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute a SELECT and return all rows as a list of dicts."""
        self._cursor.execute(sql, params)
        return self._cursor.fetchall()

    def fetch_one(self, sql: str, params: tuple = ()) -> dict | None:
        """Execute a SELECT and return the first row, or None."""
        self._cursor.execute(sql, params)
        return self._cursor.fetchone()

    def execute(self, sql: str, params: tuple = ()) -> int:
        """
        Execute a single DML statement.
        Returns rowcount.
        """
        self._cursor.execute(sql, params)
        return self._cursor.rowcount

    def execute_many(self, sql: str, params_seq: list[tuple]) -> int:
        """
        Execute a DML statement for each row in params_seq.
        Returns total rowcount.
        """
        if not params_seq:
            return 0
        self._cursor.executemany(sql, params_seq)
        return self._cursor.rowcount

    def last_insert_id(self) -> int:
        """Return the AUTO_INCREMENT id of the last INSERT."""
        return self._cursor.lastrowid

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._cursor.close()
        self._conn.close()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()
