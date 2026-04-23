"""
tests/unit/cli/test_session_store.py
--------------------------------------
SessionStore — load/save browser session state.

FileSessionStore: JSON 파일 (유일한 백엔드).
"""

from __future__ import annotations

import pytest

from cli.session_store import (
    FileSessionStore,
    create_session_store,
)


_FAKE_STATE = {
    "cookies": [{"name": "NID_AUT", "value": "abc123", "domain": ".naver.com"}],
    "origins": [],
}


# ---------------------------------------------------------------------------
# FileSessionStore
# ---------------------------------------------------------------------------

class TestFileSessionStore:

    def test_save_creates_file(self, tmp_path):
        store = FileSessionStore(base_dir=str(tmp_path))
        store.save("user1", _FAKE_STATE)
        path = tmp_path / "user1_session.json"
        assert path.exists()

    def test_load_returns_saved_data(self, tmp_path):
        store = FileSessionStore(base_dir=str(tmp_path))
        store.save("user1", _FAKE_STATE)
        loaded = store.load("user1")
        assert loaded == _FAKE_STATE

    def test_load_returns_none_when_missing(self, tmp_path):
        store = FileSessionStore(base_dir=str(tmp_path))
        assert store.load("nonexistent") is None

    def test_save_overwrites_existing(self, tmp_path):
        store = FileSessionStore(base_dir=str(tmp_path))
        store.save("user1", {"old": True})
        store.save("user1", _FAKE_STATE)
        loaded = store.load("user1")
        assert loaded == _FAKE_STATE

    def test_custom_base_dir(self, tmp_path):
        subdir = tmp_path / "sessions"
        store = FileSessionStore(base_dir=str(subdir))
        store.save("user1", _FAKE_STATE)
        assert (subdir / "user1_session.json").exists()

    def test_default_base_dir_is_cwd(self):
        store = FileSessionStore()
        assert store._base_dir == "."

    def test_explicit_path_in_account(self, tmp_path):
        """Backward compat: account has session: path/to/file.json."""
        path = tmp_path / "custom.json"
        store = FileSessionStore(base_dir=str(tmp_path))
        store.save_path(str(path), _FAKE_STATE)
        loaded = store.load_path(str(path))
        assert loaded == _FAKE_STATE

    def test_load_path_returns_none_when_missing(self, tmp_path):
        store = FileSessionStore(base_dir=str(tmp_path))
        assert store.load_path(str(tmp_path / "nope.json")) is None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class TestCreateSessionStore:

    def test_none_returns_file_store(self):
        assert isinstance(create_session_store(None), FileSessionStore)

    def test_empty_returns_file_store(self):
        assert isinstance(create_session_store(""), FileSessionStore)

    def test_file_returns_file_store(self):
        assert isinstance(create_session_store("file"), FileSessionStore)

    def test_redis_url_rejected(self):
        with pytest.raises(ValueError):
            create_session_store("redis://localhost:6379")

    def test_unknown_url_rejected(self):
        with pytest.raises(ValueError):
            create_session_store("memcached://x")
