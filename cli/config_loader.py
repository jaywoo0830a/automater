"""
cli/config_loader.py
---------------------
Load and validate a campaign JSON file into CampaignConfig.

Two-phase validation:
    1. Schema — required keys exist, types match
    2. Semantic — cross-field references resolve

Raises ConfigError with a human-readable message on any failure.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from automator.block_factory import FACTORIES as BLOCK_FACTORIES

from cli.campaign_config import (
    AccountEntry,
    CampaignConfig,
    LayoutSlotEntry,
    MediaMap,
    TitleConfig,
    TokenEntry,
)


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------

class ConfigError(Exception):
    """Human-readable configuration error."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_config(path: str) -> CampaignConfig:
    """
    Load a campaign JSON file and return a validated CampaignConfig.

    Raises:
        ConfigError: File not found, invalid JSON, or validation failure.
    """
    raw = _read_json(path)
    config = _parse(raw)
    validate_config(config)
    return config


def validate_config(config: CampaignConfig) -> None:
    """
    Validate a CampaignConfig. Raises ConfigError on failure.

    Usable standalone for configs built programmatically.
    """
    _validate_schema(config)
    _validate_semantic(config)


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def _read_json(path: str) -> dict[str, Any]:
    """Read and parse a JSON file. Returns the root dict."""
    file = Path(path)
    if not file.exists():
        raise ConfigError(f"Config file not found: {path}")

    try:
        text = file.read_text(encoding="utf-8")
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(
            f"Config root must be a JSON object, got {type(data).__name__}"
        )
    return data


# ---------------------------------------------------------------------------
# Parsing — dict → CampaignConfig
# ---------------------------------------------------------------------------

_VALID_TOKEN_TYPES = {"keyword", "pool", "literal"}


def _parse(raw: dict[str, Any]) -> CampaignConfig:
    """Convert raw JSON dict to CampaignConfig without validation."""
    accounts = tuple(
        _parse_account(a)
        for a in raw.get("accounts", [])
    )

    title = _parse_title(raw.get("title", {}))

    keywords = {
        str(k): [str(v) for v in vs]
        for k, vs in raw.get("keywords", {}).items()
    }

    palettes = {
        str(k): [str(v) for v in vs]
        for k, vs in raw.get("palettes", {}).items()
    }

    layout = tuple(
        LayoutSlotEntry(
            block_type=str(slot.get("block_type", "")),
            config=dict(slot.get("config", {})),
        )
        for slot in raw.get("layout", [])
    )

    media_raw = raw.get("media", {})
    media = MediaMap(
        base_dir=str(media_raw.get("base_dir", ".")),
        files={str(k): str(v) for k, v in media_raw.get("files", {}).items()},
    )

    return CampaignConfig(
        accounts=accounts,
        title=title,
        keywords=keywords,
        palettes=palettes,
        layout=layout,
        media=media,
        publish_config=dict(raw.get("publish", {})),
        run_config=dict(raw.get("run", {})),
    )


def _parse_account(raw: dict[str, Any]) -> AccountEntry:
    """Parse one account entry from JSON."""
    return AccountEntry(
        username=str(raw.get("username", "")),
        password=str(raw.get("password", "")),
        meta=dict(raw.get("meta", {})),
        proxies=list(raw.get("proxies", [])),
        session_path=str(raw.get("session_path", "")),
    )


def _parse_title(raw: dict[str, Any]) -> TitleConfig:
    """Parse title configuration from JSON."""
    tokens = tuple(
        TokenEntry(
            slug=str(t.get("slug", "")),
            type=str(t.get("type", "")),
            value=str(t.get("value", "")),
        )
        for t in raw.get("tokens", [])
    )
    spacing_rules = tuple(
        dict(rule)
        for rule in raw.get("spacing_rules", [])
    )
    return TitleConfig(
        tokens=tokens,
        spacing_rules=spacing_rules,
        add_affix=bool(raw.get("add_affix", False)),
        randomize_chars=bool(raw.get("randomize_chars", False)),
        ai_preset_prompt=str(raw.get("ai_preset_prompt", "")),
    )


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def _validate_schema(config: CampaignConfig) -> None:
    """Check required fields exist and have correct types."""
    if not config.accounts:
        raise ConfigError("'accounts' must contain at least one account")

    for i, acc in enumerate(config.accounts):
        if not acc.username:
            raise ConfigError(f"accounts[{i}]: 'username' is required")
        if not acc.password:
            raise ConfigError(f"accounts[{i}]: 'password' is required")

    if not config.keywords:
        raise ConfigError("'keywords' must contain at least one category")

    if not config.title.tokens:
        raise ConfigError("'title.tokens' must contain at least one token")

    for i, token in enumerate(config.title.tokens):
        if token.type not in _VALID_TOKEN_TYPES:
            raise ConfigError(
                f"title.tokens[{i}]: invalid type '{token.type}'. "
                f"Must be one of: {sorted(_VALID_TOKEN_TYPES)}"
            )


# ---------------------------------------------------------------------------
# Semantic validation
# ---------------------------------------------------------------------------

def _validate_semantic(config: CampaignConfig) -> None:
    """Check cross-field references resolve correctly."""
    _validate_keyword_references(config)
    _validate_pool_references(config)
    _validate_keyword_values(config)
    _validate_palette_values(config)
    _validate_layout_block_types(config)
    _validate_media_references(config)


def _validate_keyword_references(config: CampaignConfig) -> None:
    """Every keyword-type token must have a matching keywords entry."""
    for token in config.title.tokens:
        if token.type == "keyword" and token.slug not in config.keywords:
            raise ConfigError(
                f"Token '{token.slug}' (type=keyword) has no matching "
                f"entry in 'keywords'. Available: {sorted(config.keywords.keys())}"
            )


def _validate_pool_references(config: CampaignConfig) -> None:
    """Every pool-type token must have a matching palettes entry."""
    for token in config.title.tokens:
        if token.type == "pool" and token.slug not in config.palettes:
            raise ConfigError(
                f"Token '{token.slug}' (type=pool) has no matching "
                f"entry in 'palettes'. Available: {sorted(config.palettes.keys())}"
            )


def _validate_keyword_values(config: CampaignConfig) -> None:
    """Every keyword category must have at least one value."""
    for slug, values in config.keywords.items():
        if not values:
            raise ConfigError(
                f"keywords['{slug}'] is empty — "
                f"each category must have at least one keyword"
            )


def _validate_palette_values(config: CampaignConfig) -> None:
    """Every palette referenced by a pool token must have values."""
    pool_slugs = {t.slug for t in config.title.tokens if t.type == "pool"}
    for slug in pool_slugs:
        if slug in config.palettes and not config.palettes[slug]:
            raise ConfigError(
                f"palettes['{slug}'] is empty — "
                f"each palette must have at least one value"
            )


def _validate_layout_block_types(config: CampaignConfig) -> None:
    """Every layout slot block_type must be registered in automator."""
    for i, slot in enumerate(config.layout):
        if slot.block_type not in BLOCK_FACTORIES:
            raise ConfigError(
                f"layout[{i}]: unknown block_type '{slot.block_type}'. "
                f"Registered: {sorted(BLOCK_FACTORIES.keys())}"
            )


def _validate_media_references(config: CampaignConfig) -> None:
    """Every media_id in layout configs must exist in media.files."""
    for i, slot in enumerate(config.layout):
        media_id = slot.config.get("media_id")
        if media_id is not None:
            media_key = str(media_id)
            if media_key not in config.media.files:
                raise ConfigError(
                    f"layout[{i}]: media_id '{media_key}' not found in "
                    f"media.files. Available: {sorted(config.media.files.keys())}"
                )
