"""
tests/unit/cli/test_config_loader.py
--------------------------------------
Config loading and validation for the campaign DSL.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from cli.config_loader import load_config, ConfigError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL = {
    "accounts": [{"username": "u1", "password": "pw1", "blog_id": "b1"}],
    "titles": ["{keyword:region} {keyword:subject} 과외"],
    "keywords": {"region": ["강남"], "subject": ["수학"]},
}

FULL = {
    "accounts": [
        {"username": "u1", "password": "pw1", "blog_id": "b1", "session": "s.json"},
        {"username": "u2", "password": "pw2", "blog_id": "b2"},
    ],
    "titles": [
        "{pool:prefix} {keyword:region} {keyword:subject} 과외 {pool:suffix}",
        "{pool:prefix} {keyword:region}{keyword:subject}과외",
    ],
    "keywords": {"region": ["강남", "서초"], "subject": ["수학", "영어"]},
    "pools": {"prefix": ["검증된", "전문"], "suffix": ["강력 추천"]},
    "post": [
        {"h2": "{keyword:region} {keyword:subject} 소개"},
        {"paragraph": "{keyword:region} {keyword:subject}"},
        {"image": "body.jpg"},
        {"paragraph": {"keyword": "{keyword:region} {keyword:subject}", "tone": "review"}},
        {"thumbnail": {"src": "thumb.jpg", "overlay": "{keyword:region} {keyword:subject}"}},
    ],
    "images": "./images",
    "publish": {"schedule": "now + 15m ~ 30m", "tags": ["교육"], "visibility": "public"},
    "run": {"interval": "60s", "max_daily": 10, "headless": True},
}


@pytest.fixture
def write_yaml(tmp_path: Path):
    def _write(data, filename="campaign.yaml"):
        path = tmp_path / filename
        path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
        return str(path)
    return _write


@pytest.fixture
def write_json(tmp_path: Path):
    def _write(data, filename="campaign.json"):
        path = tmp_path / filename
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return str(path)
    return _write


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestLoadFull:

    def test_returns_dict(self, write_yaml):
        config = load_config(write_yaml(FULL))
        assert isinstance(config, dict)

    def test_accounts(self, write_yaml):
        config = load_config(write_yaml(FULL))
        assert len(config["accounts"]) == 2
        assert config["accounts"][0]["username"] == "u1"

    def test_titles(self, write_yaml):
        config = load_config(write_yaml(FULL))
        assert len(config["titles"]) == 2

    def test_keywords(self, write_yaml):
        config = load_config(write_yaml(FULL))
        assert config["keywords"]["region"] == ["강남", "서초"]

    def test_pools(self, write_yaml):
        config = load_config(write_yaml(FULL))
        assert config["pools"]["prefix"] == ["검증된", "전문"]

    def test_post(self, write_yaml):
        config = load_config(write_yaml(FULL))
        assert len(config["post"]) == 5

    def test_images(self, write_yaml):
        config = load_config(write_yaml(FULL))
        assert config["images"] == "./images"

    def test_publish(self, write_yaml):
        config = load_config(write_yaml(FULL))
        assert config["publish"]["schedule"] == "now + 15m ~ 30m"

    def test_run(self, write_yaml):
        config = load_config(write_yaml(FULL))
        assert config["run"]["headless"] is True


class TestLoadMinimal:

    def test_succeeds(self, write_yaml):
        config = load_config(write_yaml(MINIMAL))
        assert config["titles"] == ["{keyword:region} {keyword:subject} 과외"]

    def test_optional_fields_absent(self, write_yaml):
        config = load_config(write_yaml(MINIMAL))
        assert config.get("pools") == {}
        assert config.get("post") == []
        assert config.get("publish") == {}
        assert config.get("run") == {}


class TestJsonSupport:

    def test_json_loads(self, write_json):
        config = load_config(write_json(MINIMAL))
        assert config["keywords"]["region"] == ["강남"]


# ---------------------------------------------------------------------------
# File errors
# ---------------------------------------------------------------------------

class TestFileErrors:

    def test_missing_file(self):
        with pytest.raises(ConfigError, match="not found"):
            load_config("/nonexistent.yaml")

    def test_invalid_yaml(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text(":\n  [invalid", encoding="utf-8")
        with pytest.raises(ConfigError, match="YAML"):
            load_config(str(bad))

    def test_invalid_json(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{invalid", encoding="utf-8")
        with pytest.raises(ConfigError, match="JSON"):
            load_config(str(bad))

    def test_non_object_root(self, write_yaml):
        path = write_yaml([1, 2, 3], "array.yaml")
        with pytest.raises(ConfigError, match="object"):
            load_config(path)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestSchemaValidation:

    def test_missing_accounts(self, write_yaml):
        data = {**MINIMAL}; del data["accounts"]
        with pytest.raises(ConfigError, match="accounts"):
            load_config(write_yaml(data))

    def test_empty_accounts(self, write_yaml):
        with pytest.raises(ConfigError, match="accounts"):
            load_config(write_yaml({**MINIMAL, "accounts": []}))

    def test_account_missing_username(self, write_yaml):
        with pytest.raises(ConfigError, match="username"):
            load_config(write_yaml({**MINIMAL, "accounts": [{"password": "p"}]}))

    def test_account_missing_password(self, write_yaml):
        with pytest.raises(ConfigError, match="password"):
            load_config(write_yaml({**MINIMAL, "accounts": [{"username": "u"}]}))

    def test_missing_titles(self, write_yaml):
        data = {**MINIMAL}; del data["titles"]
        with pytest.raises(ConfigError, match="titles"):
            load_config(write_yaml(data))

    def test_empty_titles(self, write_yaml):
        with pytest.raises(ConfigError, match="titles"):
            load_config(write_yaml({**MINIMAL, "titles": []}))

    def test_missing_keywords(self, write_yaml):
        data = {**MINIMAL}; del data["keywords"]
        with pytest.raises(ConfigError, match="keywords"):
            load_config(write_yaml(data))

    def test_empty_keywords(self, write_yaml):
        with pytest.raises(ConfigError, match="keywords"):
            load_config(write_yaml({**MINIMAL, "keywords": {}}))

    def test_empty_keyword_list(self, write_yaml):
        with pytest.raises(ConfigError, match="region"):
            load_config(write_yaml({**MINIMAL, "keywords": {"region": []}}))


# ---------------------------------------------------------------------------
# Semantic validation
# ---------------------------------------------------------------------------

class TestSemanticValidation:

    def test_pool_ref_without_pools(self, write_yaml):
        data = {**MINIMAL, "titles": ["{pool:missing} {keyword:region} {keyword:subject}"]}
        with pytest.raises(ConfigError, match="missing"):
            load_config(write_yaml(data))

    def test_keyword_ref_without_category(self, write_yaml):
        data = {**MINIMAL, "titles": ["{keyword:nonexistent}"]}
        with pytest.raises(ConfigError, match="nonexistent"):
            load_config(write_yaml(data))

    def test_empty_pool_list(self, write_yaml):
        data = {
            **MINIMAL,
            "titles": ["{pool:prefix} {keyword:region} {keyword:subject}"],
            "pools": {"prefix": []},
        }
        with pytest.raises(ConfigError, match="prefix"):
            load_config(write_yaml(data))
