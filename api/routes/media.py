"""
api/routes/media.py — uploadMedia, listMedia, getMedia, deleteMedia, serveMedia
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from api.deps import Db, CurrentUser
from api.schemas import MediaOut
from factory.models import Media
from factory.storage import LocalStorage

router = APIRouter(prefix="/media", tags=["media"])

MEDIA_DIR = Path(os.getenv("MEDIA_STORAGE_DIR", "uploads"))
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

_storage = LocalStorage(base_dir=MEDIA_DIR)


def _own(db, user, media_id) -> Media:
    m = db.get(Media, media_id)
    if not m or m.user_id != user.id:
        raise HTTPException(status_code=404, detail="Media not found")
    return m


@router.post("", response_model=MediaOut, status_code=201)
async def upload_media(file: UploadFile, db: Db, user: CurrentUser):
    """Upload an image file. Returns the media record."""
    content_type = LocalStorage.guess_content_type(file.filename or "unknown.bin")
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{content_type}' not allowed. "
                   f"Allowed: {', '.join(sorted(ALLOWED_TYPES))}",
        )

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({len(data)} bytes). Max: {MAX_FILE_SIZE} bytes.",
        )

    rel_path = _storage.save(
        user_id=user.id,
        filename=file.filename or "upload.bin",
        data=data,
    )

    media = Media(
        user_id=user.id,
        original_name=file.filename or "upload",
        content_type=content_type,
        storage_path=rel_path,
        size_bytes=len(data),
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    return media


@router.get("", response_model=list[MediaOut])
def list_media(
    db: Db,
    user: CurrentUser,
    content_type: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """List my uploaded media files."""
    q = db.query(Media).filter(Media.user_id == user.id)
    if content_type:
        q = q.filter(Media.content_type == content_type)
    return q.order_by(Media.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()


@router.get("/{id}", response_model=MediaOut)
def get_media(id: int, db: Db, user: CurrentUser):
    """Get media metadata."""
    return _own(db, user, id)


@router.get("/{id}/file")
def serve_media(id: int, db: Db, user: CurrentUser):
    """Serve the actual file for download/display."""
    m = _own(db, user, id)
    full_path = _storage.resolve(m.storage_path)
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(
        path=str(full_path),
        media_type=m.content_type,
        filename=m.original_name,
    )


@router.delete("/{id}", status_code=204)
def delete_media(id: int, db: Db, user: CurrentUser):
    """Delete media record and file from disk."""
    m = _own(db, user, id)
    _storage.delete(m.storage_path)
    db.delete(m)
    db.commit()
