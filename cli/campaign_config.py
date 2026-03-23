"""
cli/campaign_config.py
-----------------------
Frozen dataclasses mirroring the campaign JSON schema.

Pure data — no I/O, no validation logic, no imports beyond stdlib.
config_loader.py is responsible for parsing JSON into these types.

Hierarchy
---------
    CampaignConfig          (root)
      ├── AccountEntry[]
      ├── TitleConfig
      │     ├── TokenEntry[]
      │     └── spacing_rules[]
      ├── keywords            dict[str, list[str]]
      ├── palettes            dict[str, list[str]]
      ├── LayoutSlotEntry[]
      ├── MediaMap
      ├── publish_config      dict (-> PublishOption)
      └── run_config          dict (-> RunSetting)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# ---------------------------------------------------------------------------
# AccountEntry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AccountEntry:
    """One blog platform account."""
    username:     str
    password:     str
    meta:         dict[str, Any] = field(default_factory=dict)
    proxies:      list[str]      = field(default_factory=list)
    session_path: str            = ""


# ---------------------------------------------------------------------------
# Title configuration
# ---------------------------------------------------------------------------

TokenType = Literal["keyword", "pool", "literal"]


@dataclass(frozen=True)
class TokenEntry:
    """One token in the title template sequence."""
    slug: str
    type: TokenType
    value: str = ""  # only used for literal tokens


@dataclass(frozen=True)
class TitleConfig:
    """Title generation rules: token sequence + spacing rules."""
    tokens:        tuple[TokenEntry, ...]                 = ()
    spacing_rules: tuple[dict[str, int], ...]             = ()
    add_affix:        bool  = False
    randomize_chars:  bool  = False
    ai_preset_prompt: str   = ""


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LayoutSlotEntry:
    """One block slot in the post layout."""
    block_type: str
    config:     dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Media
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MediaMap:
    """Maps media_id (str key) to file paths relative to base_dir."""
    base_dir: str                = "."
    files:    dict[str, str]     = field(default_factory=dict)


# ---------------------------------------------------------------------------
# CampaignConfig — root
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CampaignConfig:
    """
    Complete campaign specification parsed from JSON.

    All data needed to generate combinations and build PostingSpecs
    without any DB access.
    """
    accounts:       tuple[AccountEntry, ...]      = ()
    title:          TitleConfig                    = field(default_factory=TitleConfig)
    keywords:       dict[str, list[str]]           = field(default_factory=dict)
    palettes:       dict[str, list[str]]           = field(default_factory=dict)
    layout:         tuple[LayoutSlotEntry, ...]    = ()
    media:          MediaMap                        = field(default_factory=MediaMap)
    publish_config: dict[str, Any]                 = field(default_factory=dict)
    run_config:     dict[str, Any]                 = field(default_factory=dict)
