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
        {"paragraph": "{keyword:region} {keyword:subject} 과외 소개를 써줘"},
        {"image": "body.jpg"},
        {"paragraph": "{keyword:region} {keyword:subject} 과외 후기를 써줘"},
        {"featured_image": {"path": "thumb.jpg", "overlay_text": "{keyword:region} {keyword:subject}"}},
    ],
    "assets": "./images",
    "publish": {"schedule": "now + 15m ~ 30m", "tags": ["교육"], "visibility": "public"},
    "run": {"interval": "60s", "headless": True},
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
        assert config["assets"] == "./images"

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


# ---------------------------------------------------------------------------
# image / featured_image path validation (static)
# ---------------------------------------------------------------------------

class TestImagePathValidation:
    """image / featured_image 블록은 'path' 필드가 필수."""

    def test_image_shorthand_valid(self, write_yaml):
        """단축형: image: photo.jpg — 통과."""
        data = {**MINIMAL, "post": [{"image": "photo.jpg"}]}
        load_config(write_yaml(data))  # no error

    def test_image_dict_with_path_valid(self, write_yaml):
        data = {**MINIMAL, "post": [{"image": {"path": "photo.jpg"}}]}
        load_config(write_yaml(data))

    def test_image_dict_missing_path(self, write_yaml):
        """dict 형식에 path 필드 없음 → ConfigError."""
        data = {**MINIMAL, "post": [{"image": {"link": "tel:..."}}]}
        with pytest.raises(ConfigError, match="path.*필드"):
            load_config(write_yaml(data))

    def test_image_dict_empty_path(self, write_yaml):
        """path: "" → ConfigError."""
        data = {**MINIMAL, "post": [{"image": {"path": ""}}]}
        with pytest.raises(ConfigError, match="비어있거나"):
            load_config(write_yaml(data))

    def test_image_dict_dot_path(self, write_yaml):
        """path: "." → ConfigError."""
        data = {**MINIMAL, "post": [{"image": {"path": "."}}]}
        with pytest.raises(ConfigError, match="비어있거나"):
            load_config(write_yaml(data))

    def test_image_shorthand_empty(self, write_yaml):
        data = {**MINIMAL, "post": [{"image": ""}]}
        with pytest.raises(ConfigError, match="비어있거나"):
            load_config(write_yaml(data))

    def test_image_empty_value(self, write_yaml):
        """image: (null) → ConfigError."""
        data = {**MINIMAL, "post": [{"image": None}]}
        with pytest.raises(ConfigError, match="path.*필드"):
            load_config(write_yaml(data))

    def test_featured_image_missing_path(self, write_yaml):
        data = {**MINIMAL, "post": [{"featured_image": {"overlay_text": "x"}}]}
        with pytest.raises(ConfigError, match="path.*필드"):
            load_config(write_yaml(data))

    def test_featured_image_empty_path(self, write_yaml):
        data = {**MINIMAL, "post": [{"featured_image": {"path": "   "}}]}
        with pytest.raises(ConfigError, match="비어있거나"):
            load_config(write_yaml(data))

    def test_image_path_with_token_passes_static(self, write_yaml, tmp_path):
        """토큰이 포함된 path는 정적 검증을 통과 (interpolation 후 spec_builder가 검증)."""
        # 실제 map 파일 생성
        map_file = tmp_path / "photo_map.yaml"
        map_file.write_text("강남: gangnam.jpg\n_default: default.jpg\n", encoding="utf-8")
        data = {
            **MINIMAL,
            "maps": {"photo": {"file": str(map_file), "by": "{keyword:region}"}},
            "post": [{"image": {"path": "{map:photo}"}}],
        }
        load_config(write_yaml(data))

    def test_non_image_block_not_validated(self, write_yaml):
        """quote/paragraph 등은 path 검증 대상 아님."""
        data = {
            **MINIMAL,
            "post": [
                {"paragraph": "hello"},
                {"quote": "wise words"},
                "divider",
            ],
        }
        load_config(write_yaml(data))


# ---------------------------------------------------------------------------
# Strict: accounts
# ---------------------------------------------------------------------------

class TestAccountsStrict:

    def test_weight_must_be_int(self, write_yaml):
        data = {**MINIMAL, "accounts": [{"username": "u", "password": "p", "weight": "hi"}]}
        with pytest.raises(ConfigError, match="weight"):
            load_config(write_yaml(data))

    def test_weight_negative(self, write_yaml):
        data = {**MINIMAL, "accounts": [{"username": "u", "password": "p", "weight": -1}]}
        with pytest.raises(ConfigError, match="0 이상"):
            load_config(write_yaml(data))

    def test_min_exceeds_max(self, write_yaml):
        data = {**MINIMAL, "accounts": [
            {"username": "u", "password": "p", "min_posts": 10, "max_posts": 5},
        ]}
        with pytest.raises(ConfigError, match="min_posts.*max_posts"):
            load_config(write_yaml(data))

    def test_min_equals_max_ok(self, write_yaml):
        data = {**MINIMAL, "accounts": [
            {"username": "u", "password": "p", "min_posts": 5, "max_posts": 5},
        ]}
        load_config(write_yaml(data))

    def test_proxy_must_be_string(self, write_yaml):
        data = {**MINIMAL, "accounts": [
            {"username": "u", "password": "p", "proxy": 123},
        ]}
        with pytest.raises(ConfigError, match="proxy"):
            load_config(write_yaml(data))


# ---------------------------------------------------------------------------
# Strict: maps
# ---------------------------------------------------------------------------

class TestMapsStrict:

    def _make_map_file(self, tmp_path, name="test_map.yaml", content="강남: a.jpg\n_default: default.jpg\n"):
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        return str(p)

    def test_missing_by(self, write_yaml, tmp_path):
        """by 필드 누락 — 사용자 실제 삽질 케이스."""
        mf = self._make_map_file(tmp_path)
        data = {**MINIMAL, "maps": {"photo": {"file": mf}}}
        with pytest.raises(ConfigError, match="by 필드가 없습니다"):
            load_config(write_yaml(data))

    def test_missing_file(self, write_yaml):
        data = {**MINIMAL, "maps": {"photo": {"by": "{keyword:region}"}}}
        with pytest.raises(ConfigError, match="file 필드"):
            load_config(write_yaml(data))

    def test_file_not_exists(self, write_yaml):
        data = {**MINIMAL, "maps": {"photo": {"file": "nope.yaml", "by": "{keyword:region}"}}}
        with pytest.raises(ConfigError, match="존재하지 않습니다"):
            load_config(write_yaml(data))

    def test_by_wrong_format(self, write_yaml, tmp_path):
        mf = self._make_map_file(tmp_path)
        data = {**MINIMAL, "maps": {"photo": {"file": mf, "by": "region"}}}
        with pytest.raises(ConfigError, match=r"\{keyword:슬러그\}"):
            load_config(write_yaml(data))

    def test_by_unknown_keyword(self, write_yaml, tmp_path):
        mf = self._make_map_file(tmp_path)
        data = {**MINIMAL, "maps": {"photo": {"file": mf, "by": "{keyword:unknown_slug}"}}}
        with pytest.raises(ConfigError, match="unknown_slug"):
            load_config(write_yaml(data))

    def test_missing_map_key_without_default(self, write_yaml, tmp_path):
        # "강남"은 있지만 "서초"는 없음, _default도 없음
        mf = self._make_map_file(tmp_path, content="강남: a.jpg\n")
        data = {
            **MINIMAL,
            "keywords": {"region": ["강남", "서초"], "subject": ["수학"]},
            "maps": {"photo": {"file": mf, "by": "{keyword:region}"}},
        }
        with pytest.raises(ConfigError, match="서초"):
            load_config(write_yaml(data))

    def test_missing_map_key_with_default_ok(self, write_yaml, tmp_path):
        mf = self._make_map_file(tmp_path, content="강남: a.jpg\n_default: d.jpg\n")
        data = {
            **MINIMAL,
            "keywords": {"region": ["강남", "서초"], "subject": ["수학"]},
            "maps": {"photo": {"file": mf, "by": "{keyword:region}"}},
        }
        load_config(write_yaml(data))

    def test_valid_map(self, write_yaml, tmp_path):
        mf = self._make_map_file(tmp_path)
        data = {**MINIMAL, "maps": {"photo": {"file": mf, "by": "{keyword:region}"}}}
        load_config(write_yaml(data))


# ---------------------------------------------------------------------------
# Strict: post blocks
# ---------------------------------------------------------------------------

class TestPostBlocksStrict:

    def test_unknown_block_type(self, write_yaml):
        data = {**MINIMAL, "post": [{"thumbnail": "x.jpg"}]}
        with pytest.raises(ConfigError, match="알려지지 않은 블록"):
            load_config(write_yaml(data))

    def test_multiple_block_keys(self, write_yaml):
        data = {**MINIMAL, "post": [{"paragraph": "a", "quote": "b"}]}
        with pytest.raises(ConfigError, match="여러 블록 타입"):
            load_config(write_yaml(data))

    def test_empty_paragraph(self, write_yaml):
        data = {**MINIMAL, "post": [{"paragraph": ""}]}
        with pytest.raises(ConfigError, match="paragraph"):
            load_config(write_yaml(data))

    def test_paragraph_must_be_string(self, write_yaml):
        data = {**MINIMAL, "post": [{"paragraph": {"prompt": "x"}}]}
        with pytest.raises(ConfigError, match="paragraph"):
            load_config(write_yaml(data))

    def test_empty_heading(self, write_yaml):
        data = {**MINIMAL, "post": [{"h2": ""}]}
        with pytest.raises(ConfigError, match="h2"):
            load_config(write_yaml(data))

    def test_quote_type_out_of_range(self, write_yaml):
        data = {**MINIMAL, "post": [{"quote": {"text": "w", "type": 7}}]}
        with pytest.raises(ConfigError, match="type.*1~6"):
            load_config(write_yaml(data))

    def test_divider_type_out_of_range(self, write_yaml):
        data = {**MINIMAL, "post": [{"divider": 9}]}
        with pytest.raises(ConfigError, match="1~8"):
            load_config(write_yaml(data))

    def test_divider_type_valid(self, write_yaml):
        data = {**MINIMAL, "post": [{"divider": 5}]}
        load_config(write_yaml(data))

    def test_list_empty(self, write_yaml):
        data = {**MINIMAL, "post": [{"list": []}]}
        with pytest.raises(ConfigError, match="list"):
            load_config(write_yaml(data))

    def test_list_items_empty_string(self, write_yaml):
        data = {**MINIMAL, "post": [{"list": ["ok", ""]}]}
        with pytest.raises(ConfigError, match="items"):
            load_config(write_yaml(data))

    def test_newline_must_be_int(self, write_yaml):
        data = {**MINIMAL, "post": [{"newline": "many"}]}
        with pytest.raises(ConfigError, match="newline"):
            load_config(write_yaml(data))

    def test_divider_string_shorthand_only(self, write_yaml):
        data = {**MINIMAL, "post": ["not-divider"]}
        with pytest.raises(ConfigError, match="divider"):
            load_config(write_yaml(data))

    def test_bare_divider_string_ok(self, write_yaml):
        data = {**MINIMAL, "post": ["divider"]}
        load_config(write_yaml(data))


# ---------------------------------------------------------------------------
# Strict: ai_section
# ---------------------------------------------------------------------------

class TestAiSectionStrict:

    def _ai(self, **overrides):
        cfg = {
            "prompt": "수학학원의 장점",
            "structure": ["heading", "list", "paragraph"],
        }
        cfg.update(overrides)
        return cfg

    def test_valid(self, write_yaml):
        data = {**MINIMAL, "post": [{"ai_section": self._ai()}]}
        load_config(write_yaml(data))

    def test_missing_prompt(self, write_yaml):
        data = {
            **MINIMAL,
            "post": [{"ai_section": {"structure": ["heading"]}}],
        }
        with pytest.raises(ConfigError, match="prompt"):
            load_config(write_yaml(data))

    def test_empty_prompt(self, write_yaml):
        data = {
            **MINIMAL,
            "post": [{"ai_section": self._ai(prompt="")}],
        }
        with pytest.raises(ConfigError, match="prompt"):
            load_config(write_yaml(data))

    def test_missing_structure(self, write_yaml):
        data = {
            **MINIMAL,
            "post": [{"ai_section": {"prompt": "x"}}],
        }
        with pytest.raises(ConfigError, match="structure"):
            load_config(write_yaml(data))

    def test_empty_structure(self, write_yaml):
        data = {
            **MINIMAL,
            "post": [{"ai_section": self._ai(structure=[])}],
        }
        with pytest.raises(ConfigError, match="structure"):
            load_config(write_yaml(data))

    def test_unknown_structure_item(self, write_yaml):
        data = {
            **MINIMAL,
            "post": [{"ai_section": self._ai(structure=["heading", "unknown_block"])}],
        }
        with pytest.raises(ConfigError, match="알려지지 않은"):
            load_config(write_yaml(data))

    def test_invalid_on_mismatch(self, write_yaml):
        data = {
            **MINIMAL,
            "post": [{"ai_section": self._ai(on_mismatch="retry")}],
        }
        with pytest.raises(ConfigError, match="on_mismatch"):
            load_config(write_yaml(data))

    def test_invalid_auto_prompt(self, write_yaml):
        data = {
            **MINIMAL,
            "post": [{"ai_section": self._ai(auto_prompt="yes")}],
        }
        with pytest.raises(ConfigError, match="auto_prompt"):
            load_config(write_yaml(data))

    def test_strict_mode_valid(self, write_yaml):
        data = {
            **MINIMAL,
            "post": [{"ai_section": self._ai(on_mismatch="strict")}],
        }
        load_config(write_yaml(data))

    def test_h2_in_structure(self, write_yaml):
        data = {
            **MINIMAL,
            "post": [{"ai_section": self._ai(structure=["h2", "list", "paragraph"])}],
        }
        load_config(write_yaml(data))


# ---------------------------------------------------------------------------
# Strict: publish
# ---------------------------------------------------------------------------

class TestPublishStrict:

    def test_bad_visibility(self, write_yaml):
        data = {**MINIMAL, "publish": {"visibility": "protected"}}
        with pytest.raises(ConfigError, match="visibility"):
            load_config(write_yaml(data))

    def test_bad_schedule_format(self, write_yaml):
        data = {**MINIMAL, "publish": {"schedule": "15분 뒤"}}
        with pytest.raises(ConfigError, match="schedule"):
            load_config(write_yaml(data))

    def test_valid_schedules(self, write_yaml):
        for s in ("now", "now + 15m", "now + 15m ~ 30m", "++", "++ 10m", "++ 10m ~ 30m"):
            data = {**MINIMAL, "publish": {"schedule": s}}
            load_config(write_yaml(data))  # 전부 통과

    def test_tags_must_be_list(self, write_yaml):
        data = {**MINIMAL, "publish": {"tags": "교육,과외"}}
        with pytest.raises(ConfigError, match="tags"):
            load_config(write_yaml(data))

    def test_empty_tag(self, write_yaml):
        data = {**MINIMAL, "publish": {"tags": ["교육", ""]}}
        with pytest.raises(ConfigError, match="tags"):
            load_config(write_yaml(data))


# ---------------------------------------------------------------------------
# Strict: run
# ---------------------------------------------------------------------------

class TestRunStrict:

    def test_bad_interval_format(self, write_yaml):
        data = {**MINIMAL, "run": {"interval": "잠깐"}}
        with pytest.raises(ConfigError, match="interval"):
            load_config(write_yaml(data))

    def test_negative_interval(self, write_yaml):
        data = {**MINIMAL, "run": {"interval": -5}}
        with pytest.raises(ConfigError, match="interval"):
            load_config(write_yaml(data))

    def test_bad_on_failure(self, write_yaml):
        data = {**MINIMAL, "run": {"on_failure": "panic"}}
        with pytest.raises(ConfigError, match="on_failure"):
            load_config(write_yaml(data))

    def test_bad_on_resume(self, write_yaml):
        data = {**MINIMAL, "run": {"on_resume": "reboot"}}
        with pytest.raises(ConfigError, match="on_resume"):
            load_config(write_yaml(data))

    def test_headless_must_be_bool(self, write_yaml):
        data = {**MINIMAL, "run": {"headless": "yes"}}
        with pytest.raises(ConfigError, match="headless"):
            load_config(write_yaml(data))

    def test_max_workers_positive(self, write_yaml):
        data = {**MINIMAL, "run": {"max_workers": 0}}
        with pytest.raises(ConfigError, match="max_workers"):
            load_config(write_yaml(data))


# ---------------------------------------------------------------------------
# Strict: style
# ---------------------------------------------------------------------------

class TestStyleStrict:

    def test_bad_align(self, write_yaml):
        data = {**MINIMAL, "style": {"align": "justify"}}
        with pytest.raises(ConfigError, match="align"):
            load_config(write_yaml(data))

    def test_valid_aligns(self, write_yaml):
        for a in ("left", "center", "right"):
            data = {**MINIMAL, "style": {"align": a}}
            load_config(write_yaml(data))


# ---------------------------------------------------------------------------
# title_check validation
# ---------------------------------------------------------------------------

WITH_POOL = {
    **MINIMAL,
    "titles": ["{keyword:region} {keyword:subject} {pool:hook}"],
    "pools": {"hook": ["솔직 리뷰", "학부모 후기", "실제 경험담"]},
}


class TestTitleCheckValidation:

    def test_true_shorthand_normalizes(self, write_yaml):
        data = {**WITH_POOL, "title_check": True}
        config = load_config(write_yaml(data))
        tc = config["title_check"]
        assert tc["enabled"] is True
        assert tc["max_attempts"] == 10
        assert tc["match"] == "exact"
        assert tc["delay"] == "1s ~ 2s"

    def test_false_shorthand(self, write_yaml):
        data = {**WITH_POOL, "title_check": False}
        config = load_config(write_yaml(data))
        assert config["title_check"]["enabled"] is False

    def test_absent_defaults_to_disabled(self, write_yaml):
        config = load_config(write_yaml(MINIMAL))
        assert config["title_check"]["enabled"] is False

    def test_dict_form(self, write_yaml):
        data = {
            **WITH_POOL,
            "title_check": {"max_attempts": 5, "match": "contains", "delay": "2s ~ 3s"},
        }
        config = load_config(write_yaml(data))
        tc = config["title_check"]
        assert tc["enabled"] is True
        assert tc["max_attempts"] == 5
        assert tc["match"] == "contains"
        assert tc["delay"] == "2s ~ 3s"

    def test_invalid_match_mode(self, write_yaml):
        data = {
            **WITH_POOL,
            "title_check": {"match": "fuzzy"},
        }
        with pytest.raises(ConfigError, match="match"):
            load_config(write_yaml(data))

    def test_invalid_max_attempts(self, write_yaml):
        data = {
            **WITH_POOL,
            "title_check": {"max_attempts": 0},
        }
        with pytest.raises(ConfigError, match="max_attempts"):
            load_config(write_yaml(data))

    def test_requires_pool_token(self, write_yaml):
        """title_check enabled but no {pool:*} in titles → error."""
        data = {
            **MINIMAL,
            "title_check": True,
        }
        with pytest.raises(ConfigError, match="pool"):
            load_config(write_yaml(data))


# ---------------------------------------------------------------------------
# variations
# ---------------------------------------------------------------------------

VARIATION_BASE = {
    **MINIMAL,
    "post": [
        {"paragraph": "본문 ... {variation:blog_review}"},
    ],
    "variations": {
        "blog_review": {
            "axes": {
                "intro":   ["장면 묘사", "독자 질문"],
                "body":    ["3가지 비교", "단계별 절차"],
                "closing": ["체크리스트", "한 줄 요약"],
            },
        },
    },
}


class TestVariations:

    def test_loads_with_template(self, write_yaml):
        data = {
            **VARIATION_BASE,
            "variations": {
                "blog_review": {
                    **VARIATION_BASE["variations"]["blog_review"],
                    "template": "도입={intro} 본론={body}",
                },
            },
            "post": [{"paragraph": "{variation:blog_review}"}],
        }
        config = load_config(write_yaml(data))
        assert "blog_review" in config["variations"]

    def test_default_empty(self, write_yaml):
        config = load_config(write_yaml(MINIMAL))
        assert config["variations"] == {}

    def test_axis_token_resolves(self, write_yaml):
        data = {
            **VARIATION_BASE,
            "post": [{"paragraph": "프롬프트 {variation:blog_review.intro}"}],
        }
        config = load_config(write_yaml(data))
        assert "blog_review" in config["variations"]

    def test_undefined_profile_token_raises(self, write_yaml):
        data = {
            **VARIATION_BASE,
            "post": [{"paragraph": "{variation:does_not_exist}"}],
        }
        with pytest.raises(ConfigError, match="undefined variation profile"):
            load_config(write_yaml(data))

    def test_undefined_axis_token_raises(self, write_yaml):
        data = {
            **VARIATION_BASE,
            "post": [{"paragraph": "{variation:blog_review.does_not_exist}"}],
        }
        with pytest.raises(ConfigError, match="undefined axis"):
            load_config(write_yaml(data))

    def test_axes_must_be_dict(self, write_yaml):
        data = {
            **MINIMAL,
            "variations": {"blog_review": {"axes": "not a dict"}},
        }
        with pytest.raises(ConfigError, match="axes"):
            load_config(write_yaml(data))

    def test_axes_must_be_non_empty(self, write_yaml):
        data = {
            **MINIMAL,
            "variations": {"blog_review": {"axes": {}}},
        }
        with pytest.raises(ConfigError, match="axes"):
            load_config(write_yaml(data))

    def test_axis_items_must_be_list(self, write_yaml):
        data = {
            **MINIMAL,
            "variations": {"blog_review": {"axes": {"intro": "single string"}}},
        }
        with pytest.raises(ConfigError, match="intro"):
            load_config(write_yaml(data))

    def test_axis_items_must_be_non_empty(self, write_yaml):
        data = {
            **MINIMAL,
            "variations": {"blog_review": {"axes": {"intro": []}}},
        }
        with pytest.raises(ConfigError, match="intro"):
            load_config(write_yaml(data))

    def test_template_unknown_placeholder_raises(self, write_yaml):
        data = {
            **MINIMAL,
            "variations": {
                "blog_review": {
                    "axes": {"intro": ["A"]},
                    "template": "도입={intro} 본론={body}",  # body 미정의
                },
            },
        }
        with pytest.raises(ConfigError, match="body"):
            load_config(write_yaml(data))

    def test_profile_must_be_dict(self, write_yaml):
        data = {
            **MINIMAL,
            "variations": {"blog_review": "not a dict"},
        }
        with pytest.raises(ConfigError, match="blog_review"):
            load_config(write_yaml(data))
