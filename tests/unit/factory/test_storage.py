"""
tests/unit/test_storage.py
-----------------------------
LocalStorage — file save/read/delete on local filesystem.
"""

import io
import pytest
from pathlib import Path

from factory.storage import LocalStorage


@pytest.fixture
def storage(tmp_path) -> LocalStorage:
    return LocalStorage(base_dir=tmp_path)


def test_save_returns_relative_path(storage):
    data = b"fake jpeg content"
    path = storage.save(user_id=1, filename="photo.jpg", data=data)
    assert path.startswith("1/")
    assert path.endswith(".jpg")


def test_save_writes_file_to_disk(storage):
    data = b"jpeg bytes here"
    rel_path = storage.save(user_id=1, filename="test.jpg", data=data)
    full_path = storage.base_dir / rel_path
    assert full_path.exists()
    assert full_path.read_bytes() == data


def test_save_creates_user_subdirectory(storage):
    storage.save(user_id=42, filename="a.png", data=b"png")
    assert (storage.base_dir / "42").is_dir()


def test_save_generates_unique_names(storage):
    path1 = storage.save(user_id=1, filename="same.jpg", data=b"a")
    path2 = storage.save(user_id=1, filename="same.jpg", data=b"b")
    assert path1 != path2


def test_save_preserves_extension(storage):
    assert storage.save(1, "photo.JPEG", b"x").endswith(".jpeg")
    assert storage.save(1, "icon.PNG", b"x").endswith(".png")
    assert storage.save(1, "doc.webp", b"x").endswith(".webp")


def test_read_returns_bytes(storage):
    data = b"original content"
    path = storage.save(user_id=1, filename="read.jpg", data=data)
    assert storage.read(path) == data


def test_read_nonexistent_raises(storage):
    with pytest.raises(FileNotFoundError):
        storage.read("1/nonexistent.jpg")


def test_delete_removes_file(storage):
    path = storage.save(user_id=1, filename="delete_me.jpg", data=b"x")
    storage.delete(path)
    assert not (storage.base_dir / path).exists()


def test_delete_nonexistent_is_silent(storage):
    storage.delete("1/ghost.jpg")


def test_resolve_returns_absolute_path(storage):
    rel = storage.save(user_id=1, filename="abs.jpg", data=b"x")
    full = storage.resolve(rel)
    assert full.is_absolute()
    assert full.exists()


def test_content_type_detection():
    assert LocalStorage.guess_content_type("photo.jpg") == "image/jpeg"
    assert LocalStorage.guess_content_type("photo.JPEG") == "image/jpeg"
    assert LocalStorage.guess_content_type("icon.png") == "image/png"
    assert LocalStorage.guess_content_type("pic.webp") == "image/webp"
    assert LocalStorage.guess_content_type("pic.gif") == "image/gif"
    assert LocalStorage.guess_content_type("unknown.zzzzz") == "application/octet-stream"
