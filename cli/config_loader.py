"""
cli/config_loader.py
---------------------
Load and validate a campaign YAML/JSON file.

Returns a plain dict — no frozen dataclasses.
Optional keys are normalized with empty defaults.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------

class ConfigError(Exception):
    """Human-readable configuration error."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_config(path: str) -> dict[str, Any]:
    """
    Load a campaign file and return a validated, normalized dict.

    The config includes '_base_dir' — the parent directory of the YAML
    file, used for resolving relative paths (images, maps, etc.).

    Raises:
        ConfigError: File not found, parse error, or validation failure.
    """
    raw = _read_file(path)
    config = _normalize(raw)
    config["_base_dir"] = str(Path(path).resolve().parent)
    config["_config_path"] = str(Path(path).resolve())
    _validate(config)
    return config


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

_YAML_EXT = {".yaml", ".yml"}
_JSON_EXT = {".json"}


def _read_file(path: str) -> dict[str, Any]:
    """Read and parse a YAML or JSON file."""
    file = Path(path)
    if not file.exists():
        raise ConfigError(f"Config file not found: {path}")

    text = file.read_text(encoding="utf-8")
    ext = file.suffix.lower()

    if ext in _YAML_EXT:
        data = _parse_yaml(text, path)
    elif ext in _JSON_EXT:
        data = _parse_json(text, path)
    else:
        try:
            data = _parse_json(text, path)
        except ConfigError:
            data = _parse_yaml(text, path)

    if not isinstance(data, dict):
        raise ConfigError(
            f"Config root must be a YAML/JSON object, got {type(data).__name__}"
        )
    return data


def _parse_json(text: str, path: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc


def _parse_yaml(text: str, path: str) -> Any:
    try:
        import yaml
    except ImportError:
        raise ConfigError(
            "PyYAML is required for .yaml/.yml files. "
            "Install: pip install PyYAML"
        )
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc


# ---------------------------------------------------------------------------
# Normalize — fill in optional keys with empty defaults
# ---------------------------------------------------------------------------

def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize optional keys to empty defaults."""
    config = dict(raw)
    config.setdefault("pools", {})
    config.setdefault("post", [])
    config.setdefault("assets", ".")
    config.setdefault("publish", {})
    config.setdefault("run", {})
    return config


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_DSL_TOKEN_RE = re.compile(r"\{([^}]+)\}")


def _validate(config: dict[str, Any]) -> None:
    """Validate structure and cross-references."""
    _validate_schema(config)
    _validate_semantic(config)


def _validate_schema(config: dict[str, Any]) -> None:
    """Check required keys exist and have correct shape."""
    # accounts
    accounts = config.get("accounts")
    if not accounts or not isinstance(accounts, list):
        raise ConfigError("'accounts' must be a non-empty list")
    for i, acc in enumerate(accounts):
        if not isinstance(acc, dict):
            raise ConfigError(f"accounts[{i}]: must be a mapping")
        if not acc.get("username"):
            raise ConfigError(f"accounts[{i}]: 'username' is required")
        if not acc.get("password"):
            raise ConfigError(f"accounts[{i}]: 'password' is required")

    # titles
    titles = config.get("titles")
    if not titles or not isinstance(titles, list):
        raise ConfigError("'titles' must be a non-empty list of strings")

    # keywords
    keywords = config.get("keywords")
    if not keywords or not isinstance(keywords, dict):
        raise ConfigError("'keywords' must be a non-empty mapping")
    for slug, values in keywords.items():
        if not values:
            raise ConfigError(f"keywords['{slug}'] must not be empty")


def _validate_semantic(config: dict[str, Any]) -> None:
    """Check cross-field references resolve."""
    keywords = config.get("keywords", {})
    pools = config.get("pools", {})
    maps = config.get("maps", {}) or {}

    # Collect all DSL token references from titles and post
    all_templates = list(config.get("titles", []))
    for entry in config.get("post", []):
        all_templates.extend(_extract_strings(entry))

    for template in all_templates:
        for raw in _DSL_TOKEN_RE.findall(template):
            if raw == "i":
                continue
            if ":" not in raw:
                continue
            token_type, slug = raw.split(":", 1)
            if token_type == "keyword" and slug not in keywords:
                raise ConfigError(
                    f"Token '{{keyword:{slug}}}' references undefined keyword "
                    f"category. Available: {sorted(keywords.keys())}"
                )
            if token_type == "pool":
                if slug not in pools:
                    raise ConfigError(
                        f"Token '{{pool:{slug}}}' references undefined pool. "
                        f"Available: {sorted(pools.keys())}"
                    )
                if not pools[slug]:
                    raise ConfigError(
                        f"pools['{slug}'] must not be empty"
                    )
            if token_type == "map" and slug not in maps:
                raise ConfigError(
                    f"Token '{{map:{slug}}}' references undefined map. "
                    f"Available: {sorted(maps.keys())}"
                )


def _extract_strings(obj: Any) -> list[str]:
    """Extract all string values from a nested dict/list/scalar."""
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        result: list[str] = []
        for v in obj.values():
            result.extend(_extract_strings(v))
        return result
    if isinstance(obj, list):
        result = []
        for item in obj:
            result.extend(_extract_strings(item))
        return result
    return []
