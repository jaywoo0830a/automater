"""
factory/storage.py
-------------------
LocalStorage — save, read, delete files on local filesystem.

Files are stored as {base_dir}/{user_id}/{uuid}.{ext} to avoid
collisions. The relative path (user_id/uuid.ext) is what gets
stored in Media.storage_path.

Usage:
    storage = LocalStorage(base_dir=Path("uploads"))
    rel_path = storage.save(user_id=1, filename="photo.jpg", data=raw_bytes)
    data     = storage.read(rel_path)
    storage.delete(rel_path)
"""

from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path


class LocalStorage:
    """Local filesystem media storage."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)

    def save(self, user_id: int, filename: str, data: bytes) -> str:
        """
        Save file data and return the relative storage path.

        Creates {base_dir}/{user_id}/ if it doesn't exist.
        Generates a UUID filename to avoid collisions.
        """
        ext = Path(filename).suffix.lower() or ".bin"
        unique_name = f"{uuid.uuid4().hex}{ext}"
        rel_path = f"{user_id}/{unique_name}"

        full_path = self.base_dir / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(data)

        return rel_path

    def read(self, rel_path: str) -> bytes:
        """
        Read file data by relative storage path.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        full_path = self.base_dir / rel_path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {rel_path}")
        return full_path.read_bytes()

    def delete(self, rel_path: str) -> None:
        """Delete a file by relative path. Silent if file doesn't exist."""
        full_path = self.base_dir / rel_path
        full_path.unlink(missing_ok=True)

    def resolve(self, rel_path: str) -> Path:
        """Return the absolute filesystem path for a relative storage path."""
        return (self.base_dir / rel_path).resolve()

    @staticmethod
    def guess_content_type(filename: str) -> str:
        """Guess MIME type from filename extension."""
        ct, _ = mimetypes.guess_type(filename)
        return ct or "application/octet-stream"
