"""
cli/session_store.py
-----------------------
Browser session persistence — load/save Playwright storage_state.

Single backend:
    FileSessionStore — JSON files, one per account.

Factory:
    create_session_store(url) → FileSessionStore

Usage in YAML:
    # (생략하면 기본 — 파일 백엔드)
    session_store: file
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, override


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


def create_session_store(
    url: str | None = None,
    *,
    base_dir: str = ".",
) -> SessionStore:
    """
    Factory — always returns a FileSessionStore.

    Args:
        url:      None / "" / "file" 만 허용. 그 외 값은 에러.
        base_dir: File store base directory.
    """
    if not url or url == "file":
        return FileSessionStore(base_dir=base_dir)

    raise ValueError(
        f"Unsupported session_store: {url!r} — 'file' 만 지원됩니다."
    )
