"""
cli/spec_builder.py
--------------------
Combo + config dict → PostingSpec.

DSL features:
    {keyword:slug}  → keyword value
    {pool:slug}     → random pool pick
    {i}             → 1-based combo index
    when: condition → conditional block inclusion
"""

from __future__ import annotations

import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from automator.contracts import PostingSpec
from automator.options import (
    AccountOption,
    DividerBlock,
    FeaturedImageBlock,
    HeadingBlock,
    ImageBlock,
    ListBlock,
    ParagraphBlock,
    PublishOption,
    QuoteBlock,
    RegionalEffect,
    Section,
    TextBlock,
    TitleOption,
)

from cli.combo_builder import Combo
from cli.dsl import evaluate_condition, interpolate, interpolate_deep
from cli.map_loader import load_maps, resolve_maps

_HEADING_RE = re.compile(r"^h([1-6])$")
_DEFAULT_PARAGRAPH_COUNT = 3


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_spec(
    combo: Combo,
    config: dict[str, Any],
    account_index: int = 0,
) -> PostingSpec:
    """
    Build a PostingSpec from a Combo and campaign config dict.

    {i} in the title template is pre-substituted before TitleOption creation.
    Account-level keys override global run config.
    """
    account_dict = config["accounts"][account_index]
    account_opt = _build_account(account_dict)

    # Pre-substitute {i} in title template so title_generator doesn't need to know about it
    title_template = combo.title_template.replace("{i}", str(combo.index))
    title_opt = _build_title(combo, config, title_template)

    loaded_maps = load_maps(config.get("maps"), base_dir=config.get("_base_dir", "."))
    body = _build_body(combo, config, loaded_maps)
    publish_opt, schedule_at = _build_publish(config.get("publish", {}))

    return PostingSpec(
        account=account_opt,
        title=title_opt,
        body=tuple(body),
        publish=publish_opt,
        schedule_at=schedule_at,
    )


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

def _build_account(acc: dict[str, Any]) -> AccountOption:
    return AccountOption(
        username=str(acc.get("username", "")),
        password=str(acc.get("password", "")),
        weight=int(acc.get("weight", 1)),
        min_posts=int(acc.get("min_posts", 0)),
        max_posts=int(acc.get("max_posts", 0)),
        proxies=[acc["proxy"]] if "proxy" in acc else list(acc.get("proxies", [])),
        session_path=str(acc.get("session", "")),
    )


# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------

def _build_title(
    combo: Combo,
    config: dict[str, Any],
    title_template: str,
) -> TitleOption:
    pools_raw = config.get("pools", {})
    pools = {slug: tuple(values) for slug, values in pools_raw.items()}
    return TitleOption(
        template=title_template,
        values=dict(combo.values),
        pools=pools,
    )


# ---------------------------------------------------------------------------
# Body
# ---------------------------------------------------------------------------

def _build_body(
    combo: Combo,
    config: dict[str, Any],
    loaded_maps: dict[str, Any] | None = None,
) -> list[Section]:
    post = config.get("post", [])
    if not post:
        return _build_default_body(combo)

    values = combo.values
    pools = config.get("pools", {})
    base_dir = config.get("_base_dir", ".")
    images_dir = config.get("images", ".")
    # Resolve images_dir relative to the YAML file's directory
    if images_dir and not Path(images_dir).is_absolute():
        images_dir = str(Path(base_dir) / images_dir)
    exif_opt = config.get("exif_optimization", True)
    idx = combo.index
    resolved = resolve_maps(loaded_maps or {}, values)
    blocks = []

    for entry in post:
        block = _parse_block(entry, values, pools, images_dir, idx, exif_opt, resolved)
        if block is not None:
            blocks.append(block)

    return [Section(blocks=tuple(blocks))] if blocks else _build_default_body(combo)


def _build_default_body(combo: Combo) -> list[Section]:
    keyword = " ".join(combo.values.values())
    prompt = (
        f"{keyword}을(를) 홍보하는 블로그 글을 작성해주세요. "
        f"신뢰감 있는 톤으로 자연스럽게 서술해주세요."
    )
    return [Section(blocks=tuple(
        ParagraphBlock(prompt=prompt) for _ in range(_DEFAULT_PARAGRAPH_COUNT)
    ))]


# ---------------------------------------------------------------------------
# Block parsing — with `when` support
# ---------------------------------------------------------------------------

def _parse_block(
    entry: Any,
    values: dict[str, str],
    pools: dict[str, list[str]],
    images_dir: str,
    index: int,
    exif_opt: bool = True,
    maps: dict[str, str] | None = None,
) -> Any:
    """Parse one post block entry. Returns None if skipped (when=false or unknown)."""
    maps = maps or {}

    # Bare string: "divider"
    if isinstance(entry, str):
        if entry == "divider":
            return DividerBlock()
        return None

    if not isinstance(entry, dict):
        return None

    # Check `when` condition
    when = entry.get("when")
    if when and not evaluate_condition(str(when), values):
        return None

    # Find block_type: first key that isn't "when"
    block_type = None
    value = None
    for k, v in entry.items():
        if k != "when":
            block_type = k
            value = v
            break

    if block_type is None:
        return None

    # Heading: h1~h6
    heading_match = _HEADING_RE.match(block_type)
    if heading_match:
        level = int(heading_match.group(1))
        text = interpolate(str(value), values, pools, index, maps=maps)
        return HeadingBlock(level=level, text=text)

    if block_type == "paragraph":
        return _parse_paragraph(value, values, pools, index, maps)

    if block_type == "text":
        return _parse_text(value, values, pools, images_dir, index, maps)

    if block_type == "image":
        return _parse_image(value, values, pools, images_dir, index, exif_opt, maps)

    if block_type == "featured_image":
        return _parse_featured_image(value, values, pools, images_dir, index, exif_opt, maps)

    if block_type == "quote":
        return _parse_quote(value, values, pools, index, maps)

    if block_type == "list":
        return _parse_list(value, values, pools, index, maps)

    if block_type == "divider":
        return DividerBlock()

    return None  # Unknown block type — skip silently


# ---------------------------------------------------------------------------
# Block parsers
# ---------------------------------------------------------------------------

def _parse_paragraph(
    value: Any,
    values: dict[str, str],
    pools: dict[str, list[str]],
    index: int,
    maps: dict[str, str] | None = None,
) -> ParagraphBlock:
    prompt = interpolate(str(value), values, pools, index, maps=maps)
    return ParagraphBlock(prompt=prompt)


def _parse_text(
    value: Any,
    values: dict[str, str],
    pools: dict[str, list[str]],
    images_dir: str,
    index: int,
    maps: dict[str, str] | None = None,
) -> TextBlock:
    """Parse text block — file content insertion, no AI.

        - text: "{i}.txt"
        - text:
            file: "{keyword:region}/{i}.txt"
            format: html
    """
    if isinstance(value, str):
        filename = interpolate(value, values, pools, index, maps=maps)
        path = _resolve_path(images_dir, filename)
        return TextBlock(file=path, format="plain")

    if isinstance(value, dict):
        cfg = interpolate_deep(dict(value), values, pools, index, maps=maps)
        filename = str(cfg.get("file", ""))
        path = _resolve_path(images_dir, filename)
        fmt = str(cfg.get("format", "plain"))
        if fmt not in ("plain", "html"):
            fmt = "plain"
        return TextBlock(file=path, format=fmt)

    return TextBlock()


def _parse_effects(raw: Any) -> list[RegionalEffect]:
    """Parse effects list from DSL config.

        effects:
          - region: "border:10 ~ 30"
            effect: "brightness:0.3 ~ 0.7"
          - effect: "grayscale"          # region 생략 → "all"
    """
    if not isinstance(raw, list):
        return []
    effects: list[RegionalEffect] = []
    for entry in raw:
        if isinstance(entry, dict):
            effects.append(RegionalEffect(
                region=str(entry.get("region", "all")),
                effect=str(entry.get("effect", "")),
            ))
    return effects


def _parse_image(
    value: Any,
    values: dict[str, str],
    pools: dict[str, list[str]],
    images_dir: str,
    index: int,
    exif_opt: bool = True,
    maps: dict[str, str] | None = None,
) -> ImageBlock:
    if isinstance(value, str):
        filename = interpolate(value, values, pools, index, maps=maps)
        path = _resolve_path(images_dir, filename)
        return ImageBlock(path=path, exif_optimization=exif_opt)

    if isinstance(value, dict):
        cfg = interpolate_deep(dict(value), values, pools, index, maps=maps)
        path = _resolve_path(images_dir, str(cfg.get("path", "")))
        return ImageBlock(
            path=path,
            alt=str(cfg.get("alt", "")),
            link=str(cfg.get("link", "")),
            exif_optimization=exif_opt,
            effects=_parse_effects(cfg.get("effects")),
        )

    return ImageBlock(exif_optimization=exif_opt)


def _parse_featured_image(
    value: Any,
    values: dict[str, str],
    pools: dict[str, list[str]],
    images_dir: str,
    index: int,
    exif_opt: bool = True,
    maps: dict[str, str] | None = None,
) -> FeaturedImageBlock:
    if isinstance(value, str):
        filename = interpolate(value, values, pools, index, maps=maps)
        path = _resolve_path(images_dir, filename)
        return FeaturedImageBlock(path=path, exif_optimization=exif_opt)

    if isinstance(value, dict):
        cfg = interpolate_deep(dict(value), values, pools, index, maps=maps)
        path = _resolve_path(images_dir, str(cfg.get("path", "")))

        gps = cfg.get("gps")
        gps_lat = gps[0] if isinstance(gps, (list, tuple)) and len(gps) >= 2 else None
        gps_lng = gps[1] if isinstance(gps, (list, tuple)) and len(gps) >= 2 else None

        return FeaturedImageBlock(
            path=path,
            overlay_text=cfg.get("overlay_text", ""),
            overlay_color=str(cfg.get("overlay_color", "#FFFFFF")),
            overlay_background=float(cfg.get("overlay_background", 0.0)),
            overlay_position=str(cfg.get("overlay_position", "center")),
            link=str(cfg.get("link", "")),
            exif_optimization=exif_opt,
            exif_description=str(cfg.get("exif_description", "")),
            exif_gps_lat=gps_lat,
            exif_gps_lng=gps_lng,
            filename_keyword=str(cfg.get("filename_keyword", "")),
            effects=_parse_effects(cfg.get("effects")),
        )

    return FeaturedImageBlock(exif_optimization=exif_opt)


def _parse_quote(
    value: Any,
    values: dict[str, str],
    pools: dict[str, list[str]],
    index: int,
    maps: dict[str, str] | None = None,
) -> QuoteBlock:
    if isinstance(value, str):
        text = interpolate(value, values, pools, index, maps=maps)
        return QuoteBlock(text=text)

    if isinstance(value, dict):
        cfg = interpolate_deep(dict(value), values, pools, index, maps=maps)
        return QuoteBlock(
            text=str(cfg.get("text", "")),
            attribution=str(cfg.get("attribution", "")),
        )

    return QuoteBlock()


def _parse_list(
    value: Any,
    values: dict[str, str],
    pools: dict[str, list[str]],
    index: int,
    maps: dict[str, str] | None = None,
) -> ListBlock:
    if isinstance(value, list):
        items = tuple(
            interpolate(str(item), values, pools, index, maps=maps) for item in value
        )
        return ListBlock(items=items)
    return ListBlock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_path(images_dir: str, filename: str) -> str:
    if not filename:
        return ""
    if not images_dir or images_dir == ".":
        return filename
    resolved = Path(images_dir) / filename
    # Normalize to remove .. segments for cleaner paths
    return str(resolved.resolve()) if resolved.is_absolute() else str(resolved)


# ---------------------------------------------------------------------------
# Publish — schedule parsing
# ---------------------------------------------------------------------------

_KST = timezone(timedelta(hours=9))

_UNIT_MAP = {"s": 1, "m": 60, "h": 3600, "d": 86400}

# now + 15m ~ 30m  (range with unit on each side)
_RANGE_RE = re.compile(
    r"now\s*\+\s*(\d+)\s*([smhd])\s*~\s*(\d+)\s*([smhd])",
    re.IGNORECASE,
)
# now + 15m  (fixed offset)
_OFFSET_RE = re.compile(
    r"now\s*\+\s*(\d+)\s*([smhd])",
    re.IGNORECASE,
)
# ++ 15m ~ 30m  (sequential range)
_SEQ_RANGE_RE = re.compile(
    r"\+\+\s*(\d+)\s*([smhd])\s*~\s*(\d+)\s*([smhd])",
    re.IGNORECASE,
)
# ++ 15m  (sequential fixed)
_SEQ_FIXED_RE = re.compile(
    r"\+\+\s*(\d+)\s*([smhd])",
    re.IGNORECASE,
)

_DEFAULT_SEQ_INTERVAL = 900  # 15 minutes


def parse_schedule(raw: Any) -> dict[str, Any]:
    """
    Parse schedule string → {mode, at, ...}.

    Formats:
        'now'              → immediate
        'immediate'        → immediate (backward compat)
        'now + 15s'        → scheduled, at = now + 15 seconds
        'now + 15m'        → scheduled, at = now + 15 minutes
        'now + 1h'         → scheduled, at = now + 1 hour
        'now + 1d'         → scheduled, at = now + 1 day
        'now + 15m ~ 30m'  → scheduled, at = now + random(15min, 30min)
        '++'               → sequential, default 15m interval
        '++ 15m'           → sequential, fixed 15m interval
        '++ 15m ~ 30m'     → sequential, random 15m~30m interval per post
    """
    if not raw:
        return {"mode": "immediate", "at": None}

    s = str(raw).strip()

    if s.lower() in ("now", "immediate", ""):
        return {"mode": "immediate", "at": None}

    # ++ sequential modes
    if s.startswith("++"):
        return _parse_sequential(s)

    now = datetime.now(tz=_KST)

    # now + 15m ~ 30m (random range, each side has its own unit)
    m = _RANGE_RE.match(s)
    if m:
        lo_val, lo_unit = int(m.group(1)), m.group(2).lower()
        hi_val, hi_unit = int(m.group(3)), m.group(4).lower()
        lo_sec = lo_val * _UNIT_MAP[lo_unit]
        hi_sec = hi_val * _UNIT_MAP[hi_unit]
        seconds = random.randint(min(lo_sec, hi_sec), max(lo_sec, hi_sec))
        at = now + timedelta(seconds=seconds)
        return {"mode": "scheduled", "at": at}

    # now + 15m (fixed offset)
    m = _OFFSET_RE.match(s)
    if m:
        amount, unit = int(m.group(1)), m.group(2).lower()
        seconds = amount * _UNIT_MAP[unit]
        at = now + timedelta(seconds=seconds)
        return {"mode": "scheduled", "at": at}

    return {"mode": "immediate", "at": None}


def _parse_sequential(s: str) -> dict[str, Any]:
    """Parse '++', '++ 15m', '++ 15m ~ 30m' → sequential schedule dict."""
    # ++ 15m ~ 30m (range)
    m = _SEQ_RANGE_RE.match(s)
    if m:
        lo = int(m.group(1)) * _UNIT_MAP[m.group(2).lower()]
        hi = int(m.group(3)) * _UNIT_MAP[m.group(4).lower()]
        return {
            "mode": "sequential", "at": None,
            "interval_lo": min(lo, hi), "interval_hi": max(lo, hi),
        }

    # ++ 15m (fixed)
    m = _SEQ_FIXED_RE.match(s)
    if m:
        sec = int(m.group(1)) * _UNIT_MAP[m.group(2).lower()]
        return {
            "mode": "sequential", "at": None,
            "interval_lo": sec, "interval_hi": sec,
        }

    # bare ++ (default 15m)
    return {
        "mode": "sequential", "at": None,
        "interval_lo": _DEFAULT_SEQ_INTERVAL,
        "interval_hi": _DEFAULT_SEQ_INTERVAL,
    }


def _build_publish(publish_config: dict[str, Any]) -> tuple[PublishOption, datetime | None]:
    if not publish_config:
        return PublishOption(), None

    schedule = parse_schedule(publish_config.get("schedule"))
    schedule_at = schedule.get("at")

    opt = PublishOption(
        tags=list(publish_config.get("tags", [])),
        visibility=publish_config.get("visibility", "public"),
    )
    return opt, schedule_at


# ---------------------------------------------------------------------------
# Run — with account override
# ---------------------------------------------------------------------------

_ACCOUNT_IDENTITY_KEYS = {
    "username", "password", "blog_id", "session", "proxy",
    "proxies", "meta", "platform", "api_url", "api_key",
}


def merge_account_run(
    global_run: dict[str, Any],
    account: dict[str, Any],
) -> dict[str, Any]:
    """Merge account-level overrides into global run config."""
    merged = dict(global_run)
    for key, value in account.items():
        if key not in _ACCOUNT_IDENTITY_KEYS:
            merged[key] = value
    return merged


