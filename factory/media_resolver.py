"""
factory/media_resolver.py
---------------------------
Build a media_resolver callable from DB session + storage.

The resolver maps media_id (int) → absolute file path (str).
Used by job_builder when layout slots reference uploaded media.

    from factory.media_resolver import build_media_resolver

    resolver = build_media_resolver(session, storage)
    spec = build_posting_spec(combo, account, scheduled_at, media_resolver=resolver)
"""

from __future__ import annotations

from typing import Callable

from sqlalchemy.orm import Session

from factory.models import Media
from factory.storage import LocalStorage


def build_media_resolver(
    session: Session,
    storage: LocalStorage,
) -> Callable[[int], str]:
    """
    Return a callable that resolves media_id → absolute file path.

    Raises FileNotFoundError (via storage.resolve) if the file
    doesn't exist on disk, or ValueError if media_id is not found in DB.
    """
    cache: dict[int, str] = {}

    def resolve(media_id: int) -> str:
        if media_id in cache:
            return cache[media_id]

        media = session.get(Media, media_id)
        if media is None:
            raise ValueError(f"Media id={media_id} not found")

        path = str(storage.resolve(media.storage_path))
        cache[media_id] = path
        return path

    return resolve
