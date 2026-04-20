"""
cli/session_store.py
-----------------------
Browser session persistence — load/save Playwright storage_state.

Two backends:
    FileSessionStore   — JSON files (default, backward compatible).
    RedisSessionStore  — Redis keys with TTL (multi-machine, auto-expire).

Factory:
    create_session_store(url) → SessionStore

Usage in YAML:
    # File (default)
    session_store: file

    # Redis
    session_store: redis://localhost:6379
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, override

try:
    import redis
except ImportError:
    redis = None  # type: ignore[assignment]


class SessionStore(ABC):
    """Abstract session persistence."""

    @abstractmethod
    def load(self, key: str) -> dict[str, Any] | None:
        """Load session state by key. Returns None if not found."""

    @abstractmethod
    def save(self, key: str, data: dict[str, Any]) -> None:
        """Save session state by key."""


class FileSessionStore(SessionStore):
    """
    JSON file-based session store.

    Key "user1" → {base_dir}/user1_session.json
    """

    def __init__(self, base_dir: str = ".") -> None:
        self._base_dir = base_dir

    @override
    def load(self, key: str) -> dict[str, Any] | None:
        path = self._key_to_path(key)
        return self.load_path(path)

    @override
    def save(self, key: str, data: dict[str, Any]) -> None:
        path = self._key_to_path(key)
        self.save_path(path, data)

    def load_path(self, path: str) -> dict[str, Any] | None:
        """Load from an explicit file path (backward compat)."""
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_path(self, path: str, data: dict[str, Any]) -> None:
        """Save to an explicit file path (backward compat)."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _key_to_path(self, key: str) -> str:
        return str(Path(self._base_dir) / f"{key}_session.json")


class RedisSessionStore(SessionStore):
    """
    Redis-based session store with TTL.

    Key "user1" → Redis key "session:user1" (or custom prefix).
    TTL defaults to 24 hours (86400 seconds).
    """

    def __init__(
        self,
        url: str = "redis://localhost:6379",
        ttl_seconds: int = 86400,
        prefix: str = "session:",
    ) -> None:
        if redis is None:
            raise ImportError(
                "redis package is required for RedisSessionStore. "
                "Install with: pip install redis"
            )
        self._client = redis.from_url(url)
        self._ttl = ttl_seconds
        self._prefix = prefix

    @override
    def load(self, key: str) -> dict[str, Any] | None:
        raw = self._client.get(self._redis_key(key))
        if raw is None:
            return None
        return json.loads(raw)

    @override
    def save(self, key: str, data: dict[str, Any]) -> None:
        self._client.setex(
            self._redis_key(key),
            self._ttl,
            json.dumps(data, ensure_ascii=False),
        )

    def _redis_key(self, key: str) -> str:
        return f"{self._prefix}{key}"


def create_session_store(
    url: str | None = None,
    *,
    base_dir: str = ".",
    ttl_seconds: int = 86400,
    prefix: str = "session:",
) -> SessionStore:
    """
    Factory — create a SessionStore from a URL string.

    Args:
        url: None/""/file → FileSessionStore,
             redis://... → RedisSessionStore.
        base_dir:     File store base directory.
        ttl_seconds:  Redis TTL (default 24h).
        prefix:       Redis key prefix.
    """
    if not url or url == "file":
        return FileSessionStore(base_dir=base_dir)

    if url.startswith("redis://") or url.startswith("rediss://"):
        return RedisSessionStore(
            url=url,
            ttl_seconds=ttl_seconds,
            prefix=prefix,
        )

    raise ValueError(f"Unsupported session_store URL: {url!r}")
