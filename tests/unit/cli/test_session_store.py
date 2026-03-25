"""
tests/unit/cli/test_session_store.py
--------------------------------------
SessionStore — load/save browser session state.

FileSessionStore: JSON file (default, backward compatible).
RedisSessionStore: redis key with TTL.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from cli.session_store import (
    SessionStore,
    FileSessionStore,
    RedisSessionStore,
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
# RedisSessionStore
# ---------------------------------------------------------------------------

class TestRedisSessionStore:

    @pytest.fixture
    def mock_redis(self):
        with patch("cli.session_store.redis") as mock_mod:
            client = MagicMock()
            mock_mod.from_url.return_value = client
            yield client

    def test_save_calls_setex(self, mock_redis):
        store = RedisSessionStore(url="redis://localhost:6379")
        store.save("user1", _FAKE_STATE)
        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args
        assert args[0][0] == "session:user1"
        assert json.loads(args[0][2]) == _FAKE_STATE

    def test_save_default_ttl(self, mock_redis):
        store = RedisSessionStore(url="redis://localhost:6379")
        store.save("user1", _FAKE_STATE)
        args = mock_redis.setex.call_args
        assert args[0][1] == 86400  # 24 hours

    def test_save_custom_ttl(self, mock_redis):
        store = RedisSessionStore(url="redis://localhost:6379", ttl_seconds=3600)
        store.save("user1", _FAKE_STATE)
        args = mock_redis.setex.call_args
        assert args[0][1] == 3600

    def test_load_returns_data(self, mock_redis):
        mock_redis.get.return_value = json.dumps(_FAKE_STATE).encode()
        store = RedisSessionStore(url="redis://localhost:6379")
        loaded = store.load("user1")
        assert loaded == _FAKE_STATE
        mock_redis.get.assert_called_once_with("session:user1")

    def test_load_returns_none_when_missing(self, mock_redis):
        mock_redis.get.return_value = None
        store = RedisSessionStore(url="redis://localhost:6379")
        assert store.load("user1") is None

    def test_custom_prefix(self, mock_redis):
        store = RedisSessionStore(url="redis://localhost:6379", prefix="blog:")
        store.save("user1", _FAKE_STATE)
        args = mock_redis.setex.call_args
        assert args[0][0] == "blog:user1"

    def test_from_url_called(self, mock_redis):
        with patch("cli.session_store.redis") as mock_mod:
            mock_mod.from_url.return_value = mock_redis
            RedisSessionStore(url="redis://myhost:6380/2")
            mock_mod.from_url.assert_called_once_with("redis://myhost:6380/2")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class TestCreateSessionStore:

    def test_none_returns_file_store(self):
        store = create_session_store(None)
        assert isinstance(store, FileSessionStore)

    def test_empty_returns_file_store(self):
        store = create_session_store("")
        assert isinstance(store, FileSessionStore)

    def test_file_returns_file_store(self):
        store = create_session_store("file")
        assert isinstance(store, FileSessionStore)

    def test_redis_url_returns_redis_store(self):
        with patch("cli.session_store.redis"):
            store = create_session_store("redis://localhost:6379")
            assert isinstance(store, RedisSessionStore)

    def test_redis_url_with_options(self):
        with patch("cli.session_store.redis"):
            store = create_session_store(
                "redis://localhost:6379",
                ttl_seconds=7200,
                prefix="app:",
            )
            assert isinstance(store, RedisSessionStore)
            assert store._ttl == 7200
            assert store._prefix == "app:"
