"""
tests/unit/cli/test_config_loader.py
--------------------------------------
config_loader — JSON file → CampaignConfig with validation.

Tests cover:
    - Happy path: full JSON → CampaignConfig
    - Minimal JSON: only required fields
    - Schema validation: missing keys, wrong types
    - Semantic validation: dangling references, unknown block types
    - File I/O: missing file, invalid JSON
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cli.campaign_config import (
    AccountEntry,
    CampaignConfig,
    LayoutSlotEntry,
    MediaMap,
    TitleConfig,
    TokenEntry,
)
from cli.config_loader import load_config, validate_config, ConfigError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_JSON = {
    "accounts": [
        {"username": "user1", "password": "pw1"},
    ],
    "title": {
        "tokens": [
            {"slug": "subject", "type": "keyword"},
        ],
    },
    "keywords": {
        "subject": ["math"],
    },
}


FULL_JSON = {
    "accounts": [
        {
            "username": "user1",
            "password": "pw1",
            "meta": {"blog_id": "blog1"},
            "session_path": "user1_session.json",
        },
        {
            "username": "user2",
            "password": "pw2",
            "meta": {"blog_id": "blog2"},
        },
    ],
    "title": {
        "tokens": [
            {"slug": "salt_prefix", "type": "pool"},
            {"slug": "region", "type": "keyword"},
            {"slug": "subject", "type": "keyword"},
            {"slug": "salt_suffix", "type": "pool"},
        ],
        "spacing_rules": [
            {"salt_prefix": 1, "region": 1, "subject": 1, "salt_suffix": 1},
        ],
    },
    "keywords": {
        "region": ["강남", "서초"],
        "subject": ["수학", "영어"],
    },
    "palettes": {
        "salt_prefix": ["검증된", "전문"],
        "salt_suffix": ["강력 추천"],
    },
    "layout": [
        {"block_type": "heading", "config": {"level": 2, "text": "{keyword}"}},
        {"block_type": "paragraph", "config": {"keyword": "{keyword}"}},
    ],
    "media": {
        "base_dir": "./images",
        "files": {"1": "photo.jpg"},
    },
    "publish": {
        "mode": "immediate",
        "tags": ["교육"],
    },
    "run": {
        "post_interval": 60,
        "headless": True,
    },
}


@pytest.fixture
def tmp_json(tmp_path: Path):
    """Write a dict as JSON and return the file path."""
    def _write(data: dict, filename: str = "campaign.json") -> str:
        path = tmp_path / filename
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return str(path)
    return _write


# ---------------------------------------------------------------------------
# Happy path — full JSON
# ---------------------------------------------------------------------------

class TestLoadConfigFull:

    def test_returns_campaign_config(self, tmp_json):
        path = tmp_json(FULL_JSON)
        config = load_config(path)
        assert isinstance(config, CampaignConfig)

    def test_accounts_parsed(self, tmp_json):
        config = load_config(tmp_json(FULL_JSON))
        assert len(config.accounts) == 2
        assert config.accounts[0].username == "user1"
        assert config.accounts[1].meta == {"blog_id": "blog2"}

    def test_account_defaults(self, tmp_json):
        """Account without session_path gets empty string default."""
        config = load_config(tmp_json(FULL_JSON))
        assert config.accounts[1].session_path == ""
        assert config.accounts[1].proxies == []

    def test_title_tokens_parsed(self, tmp_json):
        config = load_config(tmp_json(FULL_JSON))
        assert len(config.title.tokens) == 4
        assert config.title.tokens[0].slug == "salt_prefix"
        assert config.title.tokens[0].type == "pool"

    def test_spacing_rules_parsed(self, tmp_json):
        config = load_config(tmp_json(FULL_JSON))
        assert len(config.title.spacing_rules) == 1
        assert config.title.spacing_rules[0]["region"] == 1

    def test_keywords_parsed(self, tmp_json):
        config = load_config(tmp_json(FULL_JSON))
        assert config.keywords["region"] == ["강남", "서초"]
        assert config.keywords["subject"] == ["수학", "영어"]

    def test_palettes_parsed(self, tmp_json):
        config = load_config(tmp_json(FULL_JSON))
        assert config.palettes["salt_prefix"] == ["검증된", "전문"]

    def test_layout_parsed(self, tmp_json):
        config = load_config(tmp_json(FULL_JSON))
        assert len(config.layout) == 2
        assert config.layout[0].block_type == "heading"
        assert config.layout[0].config["level"] == 2

    def test_media_parsed(self, tmp_json):
        config = load_config(tmp_json(FULL_JSON))
        assert config.media.base_dir == "./images"
        assert config.media.files["1"] == "photo.jpg"

    def test_publish_config_passed_through(self, tmp_json):
        config = load_config(tmp_json(FULL_JSON))
        assert config.publish_config["mode"] == "immediate"

    def test_run_config_passed_through(self, tmp_json):
        config = load_config(tmp_json(FULL_JSON))
        assert config.run_config["headless"] is True


# ---------------------------------------------------------------------------
# Minimal JSON — only required fields
# ---------------------------------------------------------------------------

class TestLoadConfigMinimal:

    def test_minimal_succeeds(self, tmp_json):
        config = load_config(tmp_json(MINIMAL_JSON))
        assert len(config.accounts) == 1
        assert config.keywords["subject"] == ["math"]

    def test_optional_fields_default(self, tmp_json):
        config = load_config(tmp_json(MINIMAL_JSON))
        assert config.palettes == {}
        assert config.layout == ()
        assert config.media.files == {}
        assert config.publish_config == {}
        assert config.run_config == {}


# ---------------------------------------------------------------------------
# File I/O errors
# ---------------------------------------------------------------------------

class TestLoadConfigFileErrors:

    def test_missing_file_raises(self):
        with pytest.raises(ConfigError, match="not found"):
            load_config("/nonexistent/path/campaign.json")

    def test_invalid_json_raises(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid json", encoding="utf-8")
        with pytest.raises(ConfigError, match="JSON"):
            load_config(str(bad_file))

    def test_non_object_root_raises(self, tmp_json):
        path = tmp_json([1, 2, 3], "array.json")
        with pytest.raises(ConfigError, match="object"):
            load_config(path)


# ---------------------------------------------------------------------------
# Schema validation — missing / wrong-type required fields
# ---------------------------------------------------------------------------

class TestValidateSchema:

    def test_missing_accounts_raises(self, tmp_json):
        data = {**MINIMAL_JSON}
        del data["accounts"]
        with pytest.raises(ConfigError, match="accounts"):
            load_config(tmp_json(data))

    def test_empty_accounts_raises(self, tmp_json):
        data = {**MINIMAL_JSON, "accounts": []}
        with pytest.raises(ConfigError, match="accounts"):
            load_config(tmp_json(data))

    def test_account_missing_username_raises(self, tmp_json):
        data = {**MINIMAL_JSON, "accounts": [{"password": "pw"}]}
        with pytest.raises(ConfigError, match="username"):
            load_config(tmp_json(data))

    def test_account_missing_password_raises(self, tmp_json):
        data = {**MINIMAL_JSON, "accounts": [{"username": "u"}]}
        with pytest.raises(ConfigError, match="password"):
            load_config(tmp_json(data))

    def test_missing_keywords_raises(self, tmp_json):
        data = {**MINIMAL_JSON}
        del data["keywords"]
        with pytest.raises(ConfigError, match="keywords"):
            load_config(tmp_json(data))

    def test_empty_keywords_raises(self, tmp_json):
        data = {**MINIMAL_JSON, "keywords": {}}
        with pytest.raises(ConfigError, match="keywords"):
            load_config(tmp_json(data))

    def test_missing_title_raises(self, tmp_json):
        data = {**MINIMAL_JSON}
        del data["title"]
        with pytest.raises(ConfigError, match="title"):
            load_config(tmp_json(data))

    def test_missing_title_tokens_raises(self, tmp_json):
        data = {**MINIMAL_JSON, "title": {}}
        with pytest.raises(ConfigError, match="tokens"):
            load_config(tmp_json(data))

    def test_invalid_token_type_raises(self, tmp_json):
        data = {
            **MINIMAL_JSON,
            "title": {"tokens": [{"slug": "x", "type": "bogus"}]},
        }
        with pytest.raises(ConfigError, match="type"):
            load_config(tmp_json(data))


# ---------------------------------------------------------------------------
# Semantic validation — cross-field consistency
# ---------------------------------------------------------------------------

class TestValidateSemantic:

    def test_keyword_token_without_keyword_category_raises(self, tmp_json):
        """Token type=keyword with slug not in keywords dict."""
        data = {
            **MINIMAL_JSON,
            "title": {
                "tokens": [{"slug": "nonexistent", "type": "keyword"}],
            },
        }
        with pytest.raises(ConfigError, match="nonexistent"):
            load_config(tmp_json(data))

    def test_pool_token_without_palette_raises(self, tmp_json):
        """Token type=pool with slug not in palettes dict."""
        data = {
            **MINIMAL_JSON,
            "title": {
                "tokens": [
                    {"slug": "subject", "type": "keyword"},
                    {"slug": "missing_pool", "type": "pool"},
                ],
            },
        }
        with pytest.raises(ConfigError, match="missing_pool"):
            load_config(tmp_json(data))

    def test_unknown_block_type_raises(self, tmp_json):
        data = {
            **MINIMAL_JSON,
            "layout": [{"block_type": "unknown_block", "config": {}}],
        }
        with pytest.raises(ConfigError, match="unknown_block"):
            load_config(tmp_json(data))

    def test_media_id_without_media_entry_raises(self, tmp_json):
        """Layout slot references media_id not in media.files."""
        data = {
            **MINIMAL_JSON,
            "layout": [
                {"block_type": "image", "config": {"media_id": "99"}},
            ],
            "media": {"base_dir": ".", "files": {"1": "photo.jpg"}},
        }
        with pytest.raises(ConfigError, match="99"):
            load_config(tmp_json(data))

    def test_empty_keyword_list_raises(self, tmp_json):
        data = {**MINIMAL_JSON, "keywords": {"subject": []}}
        with pytest.raises(ConfigError, match="subject"):
            load_config(tmp_json(data))

    def test_empty_palette_list_raises(self, tmp_json):
        data = {
            **MINIMAL_JSON,
            "title": {
                "tokens": [
                    {"slug": "subject", "type": "keyword"},
                    {"slug": "salt", "type": "pool"},
                ],
            },
            "palettes": {"salt": []},
        }
        with pytest.raises(ConfigError, match="salt"):
            load_config(tmp_json(data))


# ---------------------------------------------------------------------------
# validate_config standalone
# ---------------------------------------------------------------------------

class TestValidateConfigStandalone:

    def test_valid_config_returns_none(self):
        config = CampaignConfig(
            accounts=(AccountEntry(username="u", password="p"),),
            title=TitleConfig(
                tokens=(TokenEntry(slug="subject", type="keyword"),),
            ),
            keywords={"subject": ["math"]},
        )
        # Should not raise
        validate_config(config)

    def test_invalid_config_raises(self):
        config = CampaignConfig(
            accounts=(),
            keywords={"subject": ["math"]},
        )
        with pytest.raises(ConfigError, match="accounts"):
            validate_config(config)
