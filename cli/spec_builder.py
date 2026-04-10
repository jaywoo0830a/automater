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
    AiSectionBlock,
    DividerBlock,
    FeaturedImageBlock,
    HeadingBlock,
    ImageBlock,
    ListBlock,
    NewLineBlock,
    ParagraphBlock,
    PublishOption,
    QuoteBlock,
    RegionalEffect,
    Section,
    TextBlock,
    TitleOption,
)

from cli.combo_builder import Combo
from cli.config_loader import ConfigError
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
    align = _parse_align(config.get("style"))

    return PostingSpec(
        account=account_opt,
        title=title_opt,
        body=tuple(body),
        publish=publish_opt,
        schedule_at=schedule_at,
        align=align,
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
    images_dir = config.get("assets", ".")
    # Resolve images_dir relative to the YAML file's directory
    if images_dir and not Path(images_dir).is_absolute():
        images_dir = str(Path(base_dir) / images_dir)
    exif_opt = config.get("exif_optimization", True)
    idx = combo.index
    resolved = resolve_maps(loaded_maps or {}, values)
    blocks = []

    for entry in post:
        result = _parse_block(entry, values, pools, images_dir, idx, exif_opt, resolved)
        if result is None:
            continue
        if isinstance(result, list):
            blocks.extend(result)
        else:
            blocks.append(result)

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
# Map list expansion (1:N)
# ---------------------------------------------------------------------------

_MAP_TOKEN_RE = re.compile(r"\{map:(\w+)\}")


def _flatten_maps(maps: dict[str, str | list[str]]) -> dict[str, str]:
    """맵 값을 단일 문자열로 정규화. 리스트는 첫 번째 요소만 사용."""
    result: dict[str, str] = {}
    for k, v in maps.items():
        if isinstance(v, list):
            result[k] = v[0] if v else ""
        else:
            result[k] = v
    return result


def _try_expand_map_list(
    entry: dict,
    maps: dict[str, str | list[str]],
) -> list[dict] | None:
    """entry 안에 {map:slug} 토큰이 있고 해당 맵 값이 리스트면 entry를 복제 확장.

    Returns None if no list expansion needed.
    """
    # entry의 모든 문자열 값에서 {map:slug} 찾기
    entry_str = str(entry)
    found_slugs = _MAP_TOKEN_RE.findall(entry_str)
    if not found_slugs:
        return None

    # 리스트 값을 가진 맵 슬러그 찾기
    list_slug = None
    list_values: list[str] = []
    for slug in found_slugs:
        val = maps.get(slug)
        if isinstance(val, list):
            list_slug = slug
            list_values = val
            break

    if list_slug is None:
        return None

    # 리스트 값 각각에 대해 entry를 복제하고, 맵 토큰을 단일 값으로 치환
    import copy
    expanded: list[dict] = []
    for single_val in list_values:
        new_entry = copy.deepcopy(entry)
        _replace_map_token_in_dict(new_entry, list_slug, single_val)
        expanded.append(new_entry)
    return expanded


def _replace_map_token_in_dict(obj: Any, slug: str, value: str) -> None:
    """dict/list 내부의 {map:slug} 토큰을 value로 직접 치환."""
    token = f"{{map:{slug}}}"
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            v = obj[k]
            if isinstance(v, str) and token in v:
                obj[k] = v.replace(token, value)
            elif isinstance(v, (dict, list)):
                _replace_map_token_in_dict(v, slug, value)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, str) and token in item:
                obj[i] = item.replace(token, value)
            elif isinstance(item, (dict, list)):
                _replace_map_token_in_dict(item, slug, value)


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
    maps: dict[str, str | list[str]] | None = None,
) -> Any:
    """Parse one post block entry.

    Returns None if skipped, a single Block, or a list[Block] when
    a map value is a list (1:N expansion).
    """
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

    # 1:N 맵 확장 — entry에 {map:slug}가 있고 해당 맵 값이 리스트면 블록 복제
    expanded = _try_expand_map_list(entry, maps)
    if expanded is not None:
        results = []
        for expanded_entry in expanded:
            # 확장된 각 entry에서 해당 리스트 값은 이미 단일 문자열로 치환됨
            # 나머지 맵의 리스트 값은 첫 번째 요소만 사용
            flat_maps = _flatten_maps(maps)
            block = _parse_block(expanded_entry, values, pools, images_dir, index, exif_opt, flat_maps)
            if block is not None:
                if isinstance(block, list):
                    results.extend(block)
                else:
                    results.append(block)
        return results if results else None

    # 맵 값을 단일 문자열로 정규화 — 리스트는 첫 번째 요소만 사용
    str_maps: dict[str, str] = _flatten_maps(maps)

    # Parse wait annotation
    wait_ms = _parse_wait(entry.get("wait"))

    # Find block_type: first key that isn't "when" or "wait"
    block_type = None
    value = None
    for k, v in entry.items():
        if k not in ("when", "wait"):
            block_type = k
            value = v
            break

    if block_type is None:
        return None

    # Heading: h1~h6
    heading_match = _HEADING_RE.match(block_type)
    if heading_match:
        from typing import cast, Literal
        level = cast(Literal[1,2,3,4,5,6], int(heading_match.group(1)))
        text = interpolate(str(value), values, pools, index, maps=str_maps)
        return HeadingBlock(level=level, text=text, wait_ms=wait_ms)

    if block_type == "paragraph":
        return _parse_paragraph(value, values, pools, index, str_maps, wait_ms)

    if block_type == "text":
        return _parse_text(value, values, pools, images_dir, index, str_maps, wait_ms)

    if block_type == "image":
        return _parse_image(value, values, pools, images_dir, index, exif_opt, str_maps, wait_ms)

    if block_type == "featured_image":
        return _parse_featured_image(value, values, pools, images_dir, index, exif_opt, str_maps, wait_ms)

    if block_type == "quote":
        return _parse_quote(value, values, pools, index, str_maps, wait_ms)

    if block_type == "list":
        return _parse_list(value, values, pools, index, str_maps, wait_ms)

    if block_type == "divider":
        return _parse_divider(value, wait_ms)

    if block_type == "newline":
        count = int(value) if value else 1
        return NewLineBlock(count=count, wait_ms=wait_ms)

    if block_type == "ai_section":
        return _parse_ai_section(value, values, pools, index, str_maps, wait_ms)

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
    wait_ms: int = 0,
) -> ParagraphBlock:
    prompt = interpolate(str(value), values, pools, index, maps=maps)
    return ParagraphBlock(prompt=prompt, wait_ms=wait_ms)


def _parse_ai_section(
    value: Any,
    values: dict[str, str],
    pools: dict[str, list[str]],
    index: int,
    maps: dict[str, str] | None = None,
    wait_ms: int = 0,
) -> AiSectionBlock:
    """ai_section 블록 파싱.

    DSL 형식:
        - ai_section:
            prompt: "..."
            structure: [heading, list, paragraph]
            on_mismatch: lenient    # lenient | strict
            auto_prompt: true
    """
    if not isinstance(value, dict):
        raise ConfigError(
            f"ai_section 블록 값은 dict여야 합니다: {value!r}"
        )

    cfg = interpolate_deep(dict(value), values, pools, index, maps=maps)

    prompt = str(cfg.get("prompt", "")).strip()
    if not prompt:
        raise ConfigError(
            f"ai_section.prompt가 비어있습니다. 조합: {values}"
        )

    raw_structure = cfg.get("structure", [])
    if not isinstance(raw_structure, list):
        raise ConfigError(
            f"ai_section.structure는 리스트여야 합니다: {raw_structure!r}"
        )
    structure = tuple(str(s).lower() for s in raw_structure if s)

    on_mismatch = str(cfg.get("on_mismatch", "lenient")).lower()
    if on_mismatch not in ("lenient", "strict"):
        on_mismatch = "lenient"

    auto_prompt = bool(cfg.get("auto_prompt", True))
    inner_wait = _parse_wait(cfg.get("wait"))

    return AiSectionBlock(
        prompt=prompt,
        structure=structure,
        on_mismatch=on_mismatch,
        auto_prompt=auto_prompt,
        wait_ms=inner_wait or wait_ms,
    )


def _parse_text(
    value: Any,
    values: dict[str, str],
    pools: dict[str, list[str]],
    images_dir: str,
    index: int,
    maps: dict[str, str] | None = None,
    wait_ms: int = 0,
) -> TextBlock:
    """Parse text block — inline text or file content, no AI.

        - text: "인라인 텍스트 {keyword:region} ..."   # 인라인 모드
        - text:
            file: "{keyword:region}/{i}.txt"            # 파일 모드
            format: html
    """
    if isinstance(value, str):
        # 인라인 모드 — 토큰 치환 후 content에 저장
        content = interpolate(value, values, pools, index, maps=maps)
        return TextBlock(content=content, wait_ms=wait_ms)

    if isinstance(value, dict):
        cfg = interpolate_deep(dict(value), values, pools, index, maps=maps)
        inner_wait = _parse_wait(cfg.get("wait"))

        filename = str(cfg.get("file", ""))
        if filename:
            # 파일 모드
            path = _resolve_path(images_dir, filename)
            fmt = str(cfg.get("format", "plain"))
            if fmt not in ("plain", "html"):
                fmt = "plain"
            return TextBlock(file=path, format=fmt, wait_ms=inner_wait or wait_ms)

        # dict이지만 file 없음 → content 필드가 있으면 인라인
        content = str(cfg.get("content", ""))
        return TextBlock(content=content, wait_ms=inner_wait or wait_ms)

    return TextBlock()


_WAIT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([smh]?)(?:\s*~\s*(\d+(?:\.\d+)?)\s*([smh]?))?")

_WAIT_UNIT = {"": 1000, "s": 1000, "ms": 1, "m": 60_000, "h": 3_600_000}


def _parse_wait(raw: Any) -> int:
    """Parse wait annotation → milliseconds.

        "2s"         → 2000
        "1500ms"     → 1500
        "1s ~ 3s"    → random 1000~3000
        None / 0     → 0
    """
    if raw is None or raw == 0:
        return 0
    if isinstance(raw, (int, float)):
        return int(raw * 1000)  # bare number treated as seconds

    s = str(raw).strip().lower()
    if s.endswith("ms"):
        # handle "500ms" or "500ms ~ 1500ms"
        parts = s.replace("ms", "").split("~")
        if len(parts) == 2:
            lo, hi = float(parts[0].strip()), float(parts[1].strip())
            return random.randint(int(lo), int(hi))
        return int(float(parts[0].strip()))

    m = _WAIT_RE.match(s)
    if not m:
        return 0

    lo_val = float(m.group(1))
    lo_unit = m.group(2) or "s"
    lo_ms = int(lo_val * _WAIT_UNIT.get(lo_unit, 1000))

    if m.group(3):
        hi_val = float(m.group(3))
        hi_unit = m.group(4) or lo_unit
        hi_ms = int(hi_val * _WAIT_UNIT.get(hi_unit, 1000))
        return random.randint(min(lo_ms, hi_ms), max(lo_ms, hi_ms))

    return lo_ms


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
                region=str(entry.get("region", "all")).strip("'\""),
                effect=str(entry.get("effect", "")).strip("'\""),
            ))
    return effects


def _require_image_path(raw_path: str, label: str, combo_values: dict[str, str]) -> str:
    """Interpolation 이후 path가 비어있거나 '.'이면 ConfigError.

    정적 검증(config_loader)에서는 {map:X} 같은 토큰이 있으면 통과했을 수 있으나,
    여기서는 실제 interpolation 결과를 검사한다. 토큰이 빈 값으로 치환되는 경우를 잡는다.
    """
    stripped = (raw_path or "").strip()
    if not stripped or stripped == ".":
        raise ConfigError(
            f"{label} 블록의 'path'가 interpolation 이후 비어있거나 '.'이 되었습니다: {raw_path!r}. "
            f"조합 키워드: {combo_values}. "
            f"path에 사용된 토큰({{keyword:*}}, {{pool:*}}, {{map:*}})이 "
            f"이 조합에서 빈 값으로 치환되지 않는지 확인하세요."
        )
    return raw_path


def _parse_image(
    value: Any,
    values: dict[str, str],
    pools: dict[str, list[str]],
    images_dir: str,
    index: int,
    exif_opt: bool = True,
    maps: dict[str, str] | None = None,
    wait_ms: int = 0,
) -> ImageBlock:
    if isinstance(value, str):
        filename = interpolate(value, values, pools, index, maps=maps)
        _require_image_path(filename, "image", values)
        path = _resolve_path(images_dir, filename)
        return ImageBlock(path=path, exif_optimization=exif_opt, wait_ms=wait_ms)

    if isinstance(value, dict):
        cfg = interpolate_deep(dict(value), values, pools, index, maps=maps)
        raw_filename = str(cfg.get("path", ""))
        _require_image_path(raw_filename, "image", values)
        path = _resolve_path(images_dir, raw_filename)
        inner_wait = _parse_wait(cfg.get("wait"))
        return ImageBlock(
            path=path,
            alt=str(cfg.get("alt", "")),
            link=str(cfg.get("link", "")),
            exif_optimization=exif_opt,
            effects=_parse_effects(cfg.get("effects")),
            wait_ms=inner_wait or wait_ms,
        )

    raise ConfigError(
        f"image 블록 값이 문자열도 dict도 아닙니다: {value!r}. "
        f"DSL 예시: {{image: 'photo.jpg'}} 또는 {{image: {{path: 'photo.jpg', link: '...'}}}}"
    )


def _parse_featured_image(
    value: Any,
    values: dict[str, str],
    pools: dict[str, list[str]],
    images_dir: str,
    index: int,
    exif_opt: bool = True,
    maps: dict[str, str] | None = None,
    wait_ms: int = 0,
) -> FeaturedImageBlock:
    if isinstance(value, str):
        filename = interpolate(value, values, pools, index, maps=maps)
        _require_image_path(filename, "featured_image", values)
        path = _resolve_path(images_dir, filename)
        return FeaturedImageBlock(path=path, exif_optimization=exif_opt, wait_ms=wait_ms)

    if isinstance(value, dict):
        cfg = interpolate_deep(dict(value), values, pools, index, maps=maps)
        raw_filename = str(cfg.get("path", ""))
        _require_image_path(raw_filename, "featured_image", values)
        path = _resolve_path(images_dir, raw_filename)

        gps = cfg.get("gps")
        gps_lat = gps[0] if isinstance(gps, (list, tuple)) and len(gps) >= 2 else None
        gps_lng = gps[1] if isinstance(gps, (list, tuple)) and len(gps) >= 2 else None

        inner_wait = _parse_wait(cfg.get("wait"))
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
            wait_ms=inner_wait or wait_ms,
        )

    raise ConfigError(
        f"featured_image 블록 값이 문자열도 dict도 아닙니다: {value!r}. "
        f"DSL 예시: {{featured_image: 'thumb.jpg'}} 또는 {{featured_image: {{path: 'thumb.jpg'}}}}"
    )


def _parse_quote(
    value: Any,
    values: dict[str, str],
    pools: dict[str, list[str]],
    index: int,
    maps: dict[str, str] | None = None,
    wait_ms: int = 0,
) -> QuoteBlock:
    if isinstance(value, str):
        text = interpolate(value, values, pools, index, maps=maps)
        return QuoteBlock(text=text, wait_ms=wait_ms)

    if isinstance(value, dict):
        cfg = interpolate_deep(dict(value), values, pools, index, maps=maps)
        return QuoteBlock(
            text=str(cfg.get("text", "")),
            attribution=str(cfg.get("attribution", "")),
            type=_parse_quote_type(cfg.get("type")),
            wait_ms=wait_ms,
        )

    return QuoteBlock()


def _parse_quote_type(raw: Any) -> int:
    """Parse quote type 1~6, default 1."""
    try:
        v = int(raw)
        return v if 1 <= v <= 6 else 1
    except (TypeError, ValueError):
        return 1


def _parse_divider_type(raw: Any) -> int:
    """Parse divider type 1~8, default 2."""
    try:
        v = int(raw)
        return v if 1 <= v <= 8 else 2
    except (TypeError, ValueError):
        return 2


def _parse_divider(value: Any, wait_ms: int = 0) -> DividerBlock:
    """Parse divider block.

    Forms:
        - divider                    # bare key, default type=2
        - divider: 5                 # shorthand: type number
        - divider:                   # dict form
            type: 5
    """
    if value is None:
        return DividerBlock(wait_ms=wait_ms)

    if isinstance(value, dict):
        return DividerBlock(
            type=_parse_divider_type(value.get("type")),
            wait_ms=wait_ms,
        )

    # 단축형: 숫자만 — divider: 5
    return DividerBlock(
        type=_parse_divider_type(value),
        wait_ms=wait_ms,
    )


def _parse_list(
    value: Any,
    values: dict[str, str],
    pools: dict[str, list[str]],
    index: int,
    maps: dict[str, str] | None = None,
    wait_ms: int = 0,
) -> ListBlock:
    if isinstance(value, list):
        items = tuple(
            interpolate(str(item), values, pools, index, maps=maps) for item in value
        )
        return ListBlock(items=items, wait_ms=wait_ms)
    if isinstance(value, dict):
        cfg = interpolate_deep(dict(value), values, pools, index, maps=maps)
        raw_items = cfg.get("items", [])
        items = tuple(str(item) for item in raw_items) if isinstance(raw_items, list) else ()
        ordered = bool(cfg.get("ordered", False))
        inner_wait = _parse_wait(cfg.get("wait"))
        return ListBlock(items=items, ordered=ordered, wait_ms=inner_wait or wait_ms)
    return ListBlock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_win_path(filename: str) -> str:
    """GUI에서 지정된 윈도우 절대경로를 assets 기준 상대경로로 변환.

    예: 'C:/Users/.../assets/images/photo.png' → 'images/photo.png'
         'D:\\Work\\assets\\img\\a.jpg'         → 'img/a.jpg'
         'images/photo.png'                     → 그대로 반환
    """
    import re
    # 윈도우 절대경로 패턴: C:/ 또는 C:\
    if not re.match(r"^[A-Za-z]:[/\\]", filename):
        return filename

    # 백슬래시 → 슬래시로 통일
    normalized = filename.replace("\\", "/")

    # 'assets/' 이후 부분을 상대경로로 추출
    marker = "/assets/"
    idx = normalized.rfind(marker)
    if idx != -1:
        return normalized[idx + len(marker):]

    # assets 마커가 없으면 파일명만 추출
    return normalized.rsplit("/", 1)[-1]


def _resolve_path(images_dir: str, filename: str) -> str:
    # 빈 값 또는 현재 디렉터리(.) 는 경로 없음으로 처리
    # ImageHandler/FeaturedImageHandler에서 명확한 에러로 잡힌다
    if not filename or filename.strip() in ("", "."):
        return ""
    filename = _normalize_win_path(filename)
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
# Style — align
# ---------------------------------------------------------------------------

_VALID_ALIGNMENTS = {"left", "center", "right"}


def _parse_align(style_config: dict[str, Any] | None) -> str | None:
    """Extract align from style config. Returns None if not specified."""
    if not style_config or not isinstance(style_config, dict):
        return None
    raw = style_config.get("align")
    if raw is None:
        return None
    value = str(raw).strip().lower()
    if value not in _VALID_ALIGNMENTS:
        return None
    return value


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


