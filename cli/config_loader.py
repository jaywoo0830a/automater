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
    _resolve_tree_keyword_files(config)
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
    config.setdefault("variations", {})
    config.setdefault("post", [])
    config.setdefault("assets", ".")
    config.setdefault("publish", {})
    config.setdefault("run", {})
    config["title_check"] = _normalize_title_check(config.get("title_check"))
    return config


def _normalize_title_check(raw: Any) -> dict[str, Any]:
    """Normalize title_check to a dict with defaults.

    Accepted forms::

        title_check: true               → enabled, defaults
        title_check: false              → disabled
        title_check:                    → disabled (None)
          max_attempts: 10
          match: exact
          delay: 1s ~ 2s
    """
    if raw is None or raw is False:
        return {"enabled": False}

    if raw is True:
        return {
            "enabled": True,
            "max_attempts": 10,
            "match": "exact",
            "delay": "1s ~ 2s",
        }

    if isinstance(raw, dict):
        return {
            "enabled": True,
            "max_attempts": int(raw.get("max_attempts", 10)),
            "match": str(raw.get("match", "exact")),
            "delay": str(raw.get("delay", "1s ~ 2s")),
        }

    return {"enabled": False}


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

    # keywords — must be non-empty mapping; values are list (flat) or dict (tree)
    keywords = config.get("keywords")
    if not keywords or not isinstance(keywords, dict):
        raise ConfigError("'keywords' must be a non-empty mapping")
    for slug, values in keywords.items():
        if isinstance(values, list):
            if not values:
                raise ConfigError(f"keywords['{slug}'] must not be empty")
        elif isinstance(values, dict):
            if not values:
                raise ConfigError(f"keywords['{slug}'] must not be empty")
        else:
            raise ConfigError(
                f"keywords['{slug}']는 리스트(평면) 또는 dict(트리)여야 합니다: "
                f"{type(values).__name__}"
            )


def _resolve_tree_keyword_files(config: dict[str, Any]) -> None:
    """For tree-shaped keywords with a `file:` field, load file content into `by:`.

    After this step every tree keyword has an inline `by:` mapping, so the
    rest of the validation and combo-building pipeline sees a uniform shape.
    """
    keywords = config.get("keywords")
    if not isinstance(keywords, dict):
        return
    base_dir = config.get("_base_dir", ".")

    for slug, value in keywords.items():
        if not isinstance(value, dict):
            continue  # flat keyword
        has_by = "by" in value and value["by"] is not None
        has_file = "file" in value and value["file"] is not None
        if has_by and has_file:
            raise ConfigError(
                f"keywords['{slug}']: 'by'와 'file'은 동시에 지정할 수 없습니다. "
                f"하나만 사용하세요."
            )
        if not has_by and not has_file:
            raise ConfigError(
                f"keywords['{slug}']: 'by' 또는 'file' 중 하나는 필수입니다 "
                f"(트리 키워드)."
            )
        if not has_file:
            continue

        file_path = value["file"]
        if not isinstance(file_path, str) or not file_path.strip():
            raise ConfigError(
                f"keywords['{slug}'].file은 비어있지 않은 문자열이어야 합니다: {file_path!r}"
            )

        p = (
            Path(file_path) if Path(file_path).is_absolute()
            else Path(base_dir) / file_path
        )
        if not p.exists():
            raise ConfigError(
                f"keywords['{slug}'].file이 존재하지 않습니다: {p} "
                f"(file={file_path!r}, base_dir={base_dir!r})"
            )
        if not p.is_file():
            raise ConfigError(
                f"keywords['{slug}'].file이 파일이 아닙니다: {p}"
            )

        try:
            data = _parse_yaml(p.read_text(encoding="utf-8"), str(p))
        except ConfigError:
            raise
        if data is None:
            raise ConfigError(f"keywords['{slug}'].file이 비어있습니다: {p}")
        if not isinstance(data, dict):
            raise ConfigError(
                f"keywords['{slug}'].file 내용은 key:value 매핑이어야 합니다: {p} "
                f"(got {type(data).__name__})"
            )

        value["by"] = data


def _enumerate_keyword_values(slug: str, keywords: dict[str, Any]) -> list[str]:
    """Return the concrete values a keyword can take.

    Flat keyword → its list, deduped/stripped.
    Tree keyword → union of all children across `by` entries (incl. _default).
    """
    value = keywords.get(slug)
    if isinstance(value, list):
        seen: set[str] = set()
        out: list[str] = []
        for v in value:
            s = str(v).strip()
            if s and s not in seen:
                seen.add(s)
                out.append(s)
        return out
    if isinstance(value, dict):
        by = value.get("by")
        if not isinstance(by, dict):
            return []
        seen2: set[str] = set()
        out2: list[str] = []
        for k, children in by.items():
            if not isinstance(children, list):
                continue
            for c in children:
                s = str(c).strip()
                if s and s not in seen2:
                    seen2.add(s)
                    out2.append(s)
        return out2
    return []


def _validate_semantic(config: dict[str, Any]) -> None:
    """Check cross-field references resolve."""
    keywords = config.get("keywords", {})
    pools = config.get("pools", {})
    maps = config.get("maps", {}) or {}
    variations = config.get("variations", {}) or {}

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
            if token_type == "variation":
                _validate_variation_token_ref(slug, variations)

    _validate_accounts(config)
    _validate_tree_keywords(config)
    _validate_maps(config, keywords)
    _validate_pools(config)
    _validate_variations(config)
    _validate_post_blocks(config)
    _validate_post_image_paths(config)
    _validate_publish(config)
    _validate_run(config)
    _validate_style(config)
    _validate_title_check(config, pools)


def _validate_variation_token_ref(slug: str, variations: dict[str, Any]) -> None:
    """Resolve a {variation:name} or {variation:name.axis} token reference.

    Both the profile name and (when present) the axis must be defined.
    """
    if "." in slug:
        name, axis = slug.split(".", 1)
    else:
        name, axis = slug, None

    if name not in variations:
        raise ConfigError(
            f"Token '{{variation:{slug}}}' references undefined variation profile. "
            f"Available: {sorted(variations.keys())}"
        )

    if axis is not None:
        profile = variations[name]
        axes = (profile.get("axes") or {}) if isinstance(profile, dict) else {}
        if axis not in axes:
            raise ConfigError(
                f"Token '{{variation:{slug}}}' references undefined axis '{axis}' "
                f"on profile '{name}'. Available axes: {sorted(axes.keys())}"
            )


_IMAGE_BLOCK_TYPES = ("image", "featured_image")


def _validate_post_image_paths(config: dict[str, Any]) -> None:
    """image / featured_image 블록에 path가 명시되어 있는지 정적으로 검사.

    DSL 규칙: image / featured_image 블록은 path 필드가 필수다.
    빈 문자열, '.', 공백만 있는 값은 허용하지 않는다.

    interpolation 전(토큰이 그대로인 상태)에서 검사하므로,
    {keyword:x}, {pool:y}, {map:z} 같은 토큰이 포함되어 있으면 통과한다.
    (실제 값이 비어있는지는 spec_builder가 interpolation 후에 검사)
    """
    post = config.get("post", [])
    if not isinstance(post, list):
        return

    for i, entry in enumerate(post):
        if isinstance(entry, str):
            # bare string: "divider" 등 — image 블록이 아님
            continue
        if not isinstance(entry, dict):
            continue

        # 블록 타입 찾기 (when/wait 제외)
        block_type = next(
            (k for k in entry.keys() if k not in ("when", "wait")),
            None,
        )
        if block_type not in _IMAGE_BLOCK_TYPES:
            continue

        value = entry.get(block_type)
        raw_path = _extract_image_path(value)

        if raw_path is None:
            raise ConfigError(
                f"post[{i}] {block_type} 블록에 'path' 필드가 없습니다. "
                f"예: {{{block_type}: {{path: 'photo.jpg'}}}} "
                f"또는 단축형 {{{block_type}: 'photo.jpg'}}. "
                f"현재 값: {value!r}"
            )

        stripped = raw_path.strip()
        if not stripped or stripped == ".":
            raise ConfigError(
                f"post[{i}] {block_type} 블록의 'path'가 비어있거나 '.' 입니다: {raw_path!r}. "
                f"유효한 이미지 파일 경로를 지정하세요."
            )


def _extract_image_path(value: Any) -> str | None:
    """image 블록 값에서 path 문자열을 추출한다.

    Returns:
        path 문자열 (빈 문자열 포함) 또는 path 필드 자체가 없으면 None.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if "path" not in value:
            return None
        return str(value["path"]) if value["path"] is not None else ""
    return None


# ---------------------------------------------------------------------------
# Strict validators
# ---------------------------------------------------------------------------

def _validate_accounts(config: dict[str, Any]) -> None:
    """accounts의 각 필드 타입/범위 엄격 검증.

    - weight, min_posts, max_posts는 0 이상 정수
    - max_posts > 0 이면 min_posts <= max_posts
    - proxy는 문자열이어야 함
    """
    accounts = config.get("accounts", [])
    for i, acc in enumerate(accounts):
        if not isinstance(acc, dict):
            continue

        for key in ("weight", "min_posts", "max_posts"):
            if key in acc:
                val = acc[key]
                if not isinstance(val, int) or isinstance(val, bool):
                    raise ConfigError(
                        f"accounts[{i}].{key}는 정수여야 합니다: {val!r}"
                    )
                if val < 0:
                    raise ConfigError(
                        f"accounts[{i}].{key}는 0 이상이어야 합니다: {val}"
                    )

        min_p = int(acc.get("min_posts", 0))
        max_p = int(acc.get("max_posts", 0))
        if max_p > 0 and min_p > max_p:
            raise ConfigError(
                f"accounts[{i}]: min_posts({min_p}) > max_posts({max_p}) — "
                f"min_posts는 max_posts 이하여야 합니다."
            )

        if "proxy" in acc and not isinstance(acc["proxy"], str):
            raise ConfigError(
                f"accounts[{i}].proxy는 문자열이어야 합니다: {acc['proxy']!r}"
            )

        if "session" in acc and not isinstance(acc["session"], str):
            raise ConfigError(
                f"accounts[{i}].session은 문자열이어야 합니다: {acc['session']!r}"
            )


def _validate_maps(config: dict[str, Any], keywords: dict) -> None:
    """maps 섹션 엄격 검증.

    각 map 항목에 대해:
    - dict 형식이어야 함
    - file 필드 필수 (빈 값 불가)
    - by 필드 필수 — {keyword:X} 형식이며 X가 존재하는 keyword 카테고리여야 함
    - 파일 존재 여부 체크
    """
    maps = config.get("maps")
    if maps is None:
        return
    if not isinstance(maps, dict):
        raise ConfigError(f"'maps'는 매핑이어야 합니다: {type(maps).__name__}")

    base_dir = config.get("_base_dir", ".")

    for slug, entry in maps.items():
        loc = f"maps['{slug}']"
        if not isinstance(entry, dict):
            raise ConfigError(
                f"{loc}는 dict여야 합니다 (file, by 필드 포함): {entry!r}"
            )

        # file 필수
        file_path = entry.get("file")
        if not file_path or not isinstance(file_path, str):
            raise ConfigError(
                f"{loc}.file 필드가 없거나 비어있습니다. "
                f"예: {{file: 'maps/region_photo.yaml', by: '{{keyword:region}}'}}"
            )

        # by 필수
        by = entry.get("by")
        if by is None:
            raise ConfigError(
                f"{loc}.by 필드가 없습니다. "
                f"맵 조회 키를 지정하는 {{keyword:X}} 형식이 필요합니다. "
                f"예: by: '{{keyword:region}}'"
            )
        if not isinstance(by, str) or not by.strip():
            raise ConfigError(
                f"{loc}.by는 비어있지 않은 문자열이어야 합니다: {by!r}"
            )

        # by 토큰 형식 검증
        by_match = re.fullmatch(r"\{keyword:(\w+)\}", by.strip())
        if not by_match:
            raise ConfigError(
                f"{loc}.by는 '{{keyword:슬러그}}' 형식이어야 합니다: {by!r}. "
                f"예: by: '{{keyword:region}}'"
            )

        by_slug = by_match.group(1)
        if by_slug not in keywords:
            raise ConfigError(
                f"{loc}.by = '{{keyword:{by_slug}}}'가 존재하지 않는 keyword를 참조합니다. "
                f"정의된 keywords: {sorted(keywords.keys())}"
            )

        # file 존재 여부
        p = Path(file_path) if Path(file_path).is_absolute() else Path(base_dir) / file_path
        if not p.exists():
            raise ConfigError(
                f"{loc}.file이 존재하지 않습니다: {p} "
                f"(config의 file={file_path!r}, base_dir={base_dir!r})"
            )
        if not p.is_file():
            raise ConfigError(
                f"{loc}.file이 파일이 아닙니다 (디렉터리일 수 있음): {p}"
            )

        # YAML 파싱 가능 여부
        try:
            import yaml as _yaml
            data = _yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ConfigError(
                f"{loc}.file YAML 파싱 실패: {p} — {exc}"
            )

        if data is None:
            raise ConfigError(f"{loc}.file이 비어있습니다: {p}")
        if not isinstance(data, dict):
            raise ConfigError(
                f"{loc}.file 내용은 key:value 매핑이어야 합니다: {p} "
                f"(got {type(data).__name__})"
            )

        # 현재 keyword 값들이 맵에 있는지(또는 _default 있는지) 체크
        # 트리 키워드도 지원: 모든 가능한 자식 값을 enumerate
        keyword_values = _enumerate_keyword_values(by_slug, keywords)
        has_default = "_default" in data
        missing = [v for v in keyword_values if v not in data]
        if missing and not has_default:
            raise ConfigError(
                f"{loc}: keyword '{by_slug}'의 값 {missing}가 맵에 없고 '_default'도 없습니다. "
                f"맵 파일({p})에 해당 키를 추가하거나 '_default' 항목을 정의하세요."
            )


def _validate_tree_keywords(config: dict[str, Any]) -> None:
    """트리 키워드(부모-자식 의존 관계) 엄격 검증.

    형식::

        keywords:
          region: [강남, 서초]
          district:                       # 트리 키워드
            parent: region                # 부모 슬러그 (필수)
            by:                           # 인라인 (또는 file)
              강남: [대치동, 목동]
              서초: [반포동]
              _default: [전지역]          # 선택

    검증 항목:
      - 트리 키워드는 dict이고 parent + (by 또는 file) 필수
        (load 시점에 file → by로 정규화됨)
      - parent 슬러그가 keywords에 존재
      - parent의 모든 가능한 값이 by에 있거나 _default 정의
      - 각 자식 리스트는 비어있지 않고 항목은 비어있지 않은 문자열
      - 의존성 사이클 금지 (자기 자신 포함)
      - 중첩 허용 (region → district → dong)
    """
    keywords = config.get("keywords", {})
    if not isinstance(keywords, dict):
        return

    trees: dict[str, dict] = {}
    for slug, value in keywords.items():
        if isinstance(value, dict):
            trees[slug] = value

    if not trees:
        return

    # 1) 각 트리 프로파일의 형태 검증
    for slug, profile in trees.items():
        loc = f"keywords['{slug}']"
        parent = profile.get("parent")
        if not isinstance(parent, str) or not parent.strip():
            raise ConfigError(
                f"{loc}.parent가 없거나 문자열이 아닙니다: {parent!r}. "
                f"부모 키워드의 슬러그를 지정하세요."
            )
        if parent == slug:
            raise ConfigError(
                f"{loc}: 자기 자신을 parent로 지정할 수 없습니다."
            )
        if parent not in keywords:
            raise ConfigError(
                f"{loc}.parent='{parent}'가 정의되지 않은 keyword를 참조합니다. "
                f"정의된 keywords: {sorted(keywords.keys())}"
            )

        by = profile.get("by")
        if not isinstance(by, dict) or not by:
            raise ConfigError(
                f"{loc}.by는 비어있지 않은 매핑이어야 합니다. "
                f"(file이 지정됐다면 파일이 비어있는지 확인)"
            )

        for parent_value, children in by.items():
            child_loc = f"{loc}.by['{parent_value}']"
            if not isinstance(children, list):
                raise ConfigError(
                    f"{child_loc}는 리스트여야 합니다: {type(children).__name__}"
                )
            if not children:
                raise ConfigError(f"{child_loc}가 빈 리스트입니다.")
            for j, c in enumerate(children):
                if not isinstance(c, (str, int, float)):
                    raise ConfigError(
                        f"{child_loc}[{j}]는 문자열이어야 합니다: {c!r}"
                    )
                if not str(c).strip():
                    raise ConfigError(f"{child_loc}[{j}]가 빈 문자열입니다.")

    # 2) 사이클 검출 (DFS)
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {s: WHITE for s in trees}

    def visit(node: str, path: list[str]) -> None:
        if node not in trees:
            return  # flat keyword — 끝
        if color[node] == GRAY:
            cycle = " → ".join(path + [node])
            raise ConfigError(
                f"keywords 트리 의존성에 사이클이 있습니다: {cycle}"
            )
        if color[node] == BLACK:
            return
        color[node] = GRAY
        parent = trees[node]["parent"]
        visit(parent, path + [node])
        color[node] = BLACK

    for s in trees:
        visit(s, [])

    # 3) 부모 값 커버리지 체크
    for slug, profile in trees.items():
        loc = f"keywords['{slug}']"
        parent = profile["parent"]
        by = profile["by"]
        parent_values = _enumerate_keyword_values(parent, keywords)
        has_default = "_default" in by
        missing = [v for v in parent_values if v not in by]
        if missing and not has_default:
            raise ConfigError(
                f"{loc}: parent '{parent}'의 값 {missing}가 by에 없고 '_default'도 없습니다. "
                f"by에 해당 키를 추가하거나 '_default' 항목을 정의하세요."
            )


def _validate_pools(config: dict[str, Any]) -> None:
    """pools 엄격 검증.

    - dict 형식
    - 각 pool은 리스트여야 함
    - 각 항목은 비어있지 않은 문자열
    """
    pools = config.get("pools", {})
    if pools is None:
        return
    if not isinstance(pools, dict):
        raise ConfigError(f"'pools'는 매핑이어야 합니다: {type(pools).__name__}")

    for slug, items in pools.items():
        if not isinstance(items, list):
            raise ConfigError(
                f"pools['{slug}']는 리스트여야 합니다: {type(items).__name__}"
            )
        for j, item in enumerate(items):
            if not isinstance(item, (str, int, float)):
                raise ConfigError(
                    f"pools['{slug}'][{j}]는 문자열이어야 합니다: {item!r}"
                )
            if not str(item).strip():
                raise ConfigError(
                    f"pools['{slug}'][{j}]가 빈 문자열입니다."
                )


_VARIATION_TEMPLATE_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def _validate_variations(config: dict[str, Any]) -> None:
    """variations 엄격 검증.

    형식::

        variations:
          blog_review:
            axes:
              intro:   ["...", "..."]
              body:    ["...", "..."]
              closing: ["...", "..."]
            template: |          # 선택. 생략 시 자동 포맷.
              [작성 지침]
              - 도입: {intro}
              - 본론: {body}
              - 마무리: {closing}

    - profile은 dict
    - axes는 비어있지 않은 dict, 각 축은 비어있지 않은 문자열 리스트
    - template이 있으면 문자열, 그 안의 {axis} 자리표시자는 모두 axes에 정의돼야 함
    """
    variations = config.get("variations")
    if variations is None or variations == {}:
        return
    if not isinstance(variations, dict):
        raise ConfigError(
            f"'variations'는 매핑이어야 합니다: {type(variations).__name__}"
        )

    for name, profile in variations.items():
        loc = f"variations['{name}']"
        if not isinstance(name, str) or not name.strip():
            raise ConfigError(f"variations 프로파일 이름이 비어있습니다: {name!r}")
        if not isinstance(profile, dict):
            raise ConfigError(
                f"{loc}는 dict여야 합니다 (axes, optional template 포함): {profile!r}"
            )

        axes = profile.get("axes")
        if not isinstance(axes, dict) or not axes:
            raise ConfigError(
                f"{loc}.axes는 비어있지 않은 매핑이어야 합니다: {axes!r}. "
                f"예: axes: {{intro: [...], body: [...]}}"
            )

        for axis_name, items in axes.items():
            axis_loc = f"{loc}.axes['{axis_name}']"
            if not isinstance(axis_name, str) or not axis_name.strip():
                raise ConfigError(f"{loc}.axes의 축 이름이 비어있습니다: {axis_name!r}")
            if not _VARIATION_TEMPLATE_PLACEHOLDER_RE.fullmatch("{" + axis_name + "}"):
                # 축 이름은 {axis} 자리표시자로 쓰이므로 영숫자/_ 만 허용
                raise ConfigError(
                    f"{loc}.axes의 축 이름은 영숫자와 '_'만 허용됩니다: {axis_name!r}"
                )
            if not isinstance(items, list) or not items:
                raise ConfigError(
                    f"{axis_loc}는 비어있지 않은 리스트여야 합니다: {items!r}"
                )
            for j, item in enumerate(items):
                if not isinstance(item, (str, int, float)):
                    raise ConfigError(
                        f"{axis_loc}[{j}]는 문자열이어야 합니다: {item!r}"
                    )
                if not str(item).strip():
                    raise ConfigError(f"{axis_loc}[{j}]가 빈 문자열입니다.")

        template = profile.get("template")
        if template is not None:
            if not isinstance(template, str):
                raise ConfigError(
                    f"{loc}.template은 문자열이어야 합니다: {template!r}"
                )
            for placeholder in _VARIATION_TEMPLATE_PLACEHOLDER_RE.findall(template):
                if placeholder not in axes:
                    raise ConfigError(
                        f"{loc}.template이 정의되지 않은 축 '{{{placeholder}}}'을 참조합니다. "
                        f"정의된 축: {sorted(axes.keys())}"
                    )


_HEADING_RE = re.compile(r"^h([1-6])$")
_KNOWN_BLOCK_TYPES = {
    "paragraph", "text", "image", "featured_image",
    "quote", "list", "divider", "newline", "ai_section",
    "h1", "h2", "h3", "h4", "h5", "h6",
}
_AI_SECTION_STRUCTURE_KEYS = {
    "heading", "h1", "h2", "h3", "h4", "h5", "h6",
    "list", "ordered_list", "quote", "divider", "paragraph", "text",
}
_AI_SECTION_MISMATCH_MODES = {"lenient", "strict"}


def _validate_post_blocks(config: dict[str, Any]) -> None:
    """post 블록 전체 엄격 검증.

    - 각 entry는 str('divider') 또는 dict
    - dict는 알려진 블록 타입 키 1개 (+ when/wait) 필요
    - quote/divider type 범위 검증
    - heading level 검증
    - list items 검증
    - text/paragraph 문자열 검증
    """
    post = config.get("post", [])
    if post is None:
        return
    if not isinstance(post, list):
        raise ConfigError(f"'post'는 리스트여야 합니다: {type(post).__name__}")

    for i, entry in enumerate(post):
        loc = f"post[{i}]"

        if isinstance(entry, str):
            if entry != "divider":
                raise ConfigError(
                    f"{loc}: 문자열 단축형은 'divider'만 허용됩니다: {entry!r}"
                )
            continue

        if not isinstance(entry, dict):
            raise ConfigError(
                f"{loc}는 dict 또는 'divider' 문자열이어야 합니다: {entry!r}"
            )

        # when/wait 키 제외한 첫 번째 키를 블록 타입으로 판단
        block_keys = [k for k in entry.keys() if k not in ("when", "wait")]
        if not block_keys:
            raise ConfigError(
                f"{loc}: 블록 타입 키가 없습니다 (when/wait만 있음). "
                f"알려진 블록 타입: {sorted(_KNOWN_BLOCK_TYPES)}"
            )
        if len(block_keys) > 1:
            raise ConfigError(
                f"{loc}: 여러 블록 타입 키가 섞여있습니다: {block_keys}. "
                f"한 블록에는 하나의 타입만 지정하세요."
            )

        block_type = block_keys[0]
        if block_type not in _KNOWN_BLOCK_TYPES:
            raise ConfigError(
                f"{loc}: 알려지지 않은 블록 타입 '{block_type}'. "
                f"허용: {sorted(_KNOWN_BLOCK_TYPES)}"
            )

        value = entry[block_type]

        # wait 형식 — 숫자 또는 문자열
        if "wait" in entry:
            w = entry["wait"]
            if not isinstance(w, (int, float, str)):
                raise ConfigError(
                    f"{loc}.wait는 숫자 또는 문자열이어야 합니다: {w!r}"
                )

        # when 형식 — 문자열
        if "when" in entry:
            wh = entry["when"]
            if not isinstance(wh, str):
                raise ConfigError(
                    f"{loc}.when은 문자열이어야 합니다: {wh!r}"
                )

        # 블록 타입별 상세 검증
        if block_type == "quote":
            _check_quote(value, loc)
        elif block_type == "divider":
            _check_divider(value, loc)
        elif block_type == "list":
            _check_list(value, loc)
        elif _HEADING_RE.match(block_type):
            _check_heading_value(value, loc, block_type)
        elif block_type == "paragraph":
            _check_paragraph(value, loc)
        elif block_type == "text":
            _check_text(value, loc)
        elif block_type == "newline":
            _check_newline(value, loc)
        elif block_type == "ai_section":
            _check_ai_section(value, loc)
        # image / featured_image는 _validate_post_image_paths에서 처리


def _check_quote(value: Any, loc: str) -> None:
    if value is None or value == "":
        raise ConfigError(f"{loc}: quote 블록이 비어있습니다.")
    if isinstance(value, str):
        return
    if not isinstance(value, dict):
        raise ConfigError(
            f"{loc}: quote 값이 문자열도 dict도 아닙니다: {value!r}"
        )
    text = value.get("text", "")
    if not isinstance(text, str) or not text.strip():
        raise ConfigError(
            f"{loc}: quote.text가 비어있습니다: {text!r}"
        )
    qtype = value.get("type")
    if qtype is not None:
        if not isinstance(qtype, int) or not (1 <= qtype <= 6):
            raise ConfigError(
                f"{loc}: quote.type은 1~6 정수여야 합니다: {qtype!r}"
            )
    attr = value.get("attribution")
    if attr is not None and not isinstance(attr, str):
        raise ConfigError(
            f"{loc}: quote.attribution은 문자열이어야 합니다: {attr!r}"
        )


def _check_divider(value: Any, loc: str) -> None:
    # 허용: None (기본 type=2), int (단축형 type), dict {type: N}
    if value is None:
        return
    if isinstance(value, int):
        if not (1 <= value <= 8):
            raise ConfigError(
                f"{loc}: divider type은 1~8 정수여야 합니다: {value}"
            )
        return
    if isinstance(value, dict):
        dtype = value.get("type")
        if dtype is not None:
            if not isinstance(dtype, int) or not (1 <= dtype <= 8):
                raise ConfigError(
                    f"{loc}: divider.type은 1~8 정수여야 합니다: {dtype!r}"
                )
        return
    raise ConfigError(
        f"{loc}: divider 값이 잘못되었습니다: {value!r}. "
        f"허용: null, 1~8 정수, {{type: N}}"
    )


def _check_list(value: Any, loc: str) -> None:
    if isinstance(value, list):
        if not value:
            raise ConfigError(f"{loc}: list items가 비어있습니다.")
        for j, item in enumerate(value):
            if not isinstance(item, (str, int, float)) or not str(item).strip():
                raise ConfigError(
                    f"{loc}.items[{j}]: 비어있지 않은 문자열이어야 합니다: {item!r}"
                )
        return
    if isinstance(value, dict):
        items = value.get("items")
        if not isinstance(items, list) or not items:
            raise ConfigError(
                f"{loc}.items는 비어있지 않은 리스트여야 합니다: {items!r}"
            )
        for j, item in enumerate(items):
            if not isinstance(item, (str, int, float)) or not str(item).strip():
                raise ConfigError(
                    f"{loc}.items[{j}]: 비어있지 않은 문자열이어야 합니다: {item!r}"
                )
        if "ordered" in value and not isinstance(value["ordered"], bool):
            raise ConfigError(
                f"{loc}.ordered는 bool이어야 합니다: {value['ordered']!r}"
            )
        return
    raise ConfigError(
        f"{loc}: list 값은 리스트 또는 dict여야 합니다: {value!r}"
    )


def _check_heading_value(value: Any, loc: str, block_type: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(
            f"{loc}: {block_type} 텍스트가 비어있습니다: {value!r}"
        )


def _check_paragraph(value: Any, loc: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(
            f"{loc}: paragraph 프롬프트가 비어있습니다: {value!r}. "
            f"AI에게 전달할 프롬프트 문자열을 지정하세요."
        )


def _check_text(value: Any, loc: str) -> None:
    # 인라인 문자열 또는 dict {file: ..., format: ...}
    if isinstance(value, str):
        if not value.strip():
            raise ConfigError(f"{loc}: text 내용이 비어있습니다.")
        return
    if isinstance(value, dict):
        has_file = "file" in value and value["file"]
        has_content = "content" in value and value["content"]
        if not has_file and not has_content:
            raise ConfigError(
                f"{loc}: text는 'file' 또는 'content' 중 하나가 필요합니다: {value!r}"
            )
        if "format" in value:
            fmt = value["format"]
            if fmt not in ("plain", "html"):
                raise ConfigError(
                    f"{loc}.format은 'plain' 또는 'html'이어야 합니다: {fmt!r}"
                )
        return
    raise ConfigError(
        f"{loc}: text 값이 문자열도 dict도 아닙니다: {value!r}"
    )


def _check_newline(value: Any, loc: str) -> None:
    if value is None:
        return
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigError(
            f"{loc}: newline 값은 정수여야 합니다: {value!r}"
        )
    if value < 1:
        raise ConfigError(
            f"{loc}: newline 값은 1 이상이어야 합니다: {value}"
        )


def _check_ai_section(value: Any, loc: str) -> None:
    """ai_section 블록 검증.

    형식:
        ai_section:
          prompt: "..."
          structure: [heading, list, paragraph]
          on_mismatch: lenient    # lenient | strict
          auto_prompt: true
    """
    if not isinstance(value, dict):
        raise ConfigError(
            f"{loc}: ai_section 값은 dict여야 합니다: {value!r}"
        )

    prompt = value.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ConfigError(
            f"{loc}: ai_section.prompt가 비어있거나 문자열이 아닙니다: {prompt!r}"
        )

    structure = value.get("structure")
    if structure is None:
        raise ConfigError(
            f"{loc}: ai_section.structure 필드가 없습니다. "
            f"예: structure: [heading, list, paragraph]"
        )
    if not isinstance(structure, list) or not structure:
        raise ConfigError(
            f"{loc}: ai_section.structure는 비어있지 않은 리스트여야 합니다: {structure!r}"
        )
    for j, item in enumerate(structure):
        if not isinstance(item, str):
            raise ConfigError(
                f"{loc}.structure[{j}]는 문자열이어야 합니다: {item!r}"
            )
        if item.lower() not in _AI_SECTION_STRUCTURE_KEYS:
            raise ConfigError(
                f"{loc}.structure[{j}]는 알려지지 않은 블록 타입입니다: {item!r}. "
                f"허용: {sorted(_AI_SECTION_STRUCTURE_KEYS)}"
            )

    if "on_mismatch" in value:
        m = value["on_mismatch"]
        if m not in _AI_SECTION_MISMATCH_MODES:
            raise ConfigError(
                f"{loc}.on_mismatch는 {sorted(_AI_SECTION_MISMATCH_MODES)} 중 하나여야 합니다: {m!r}"
            )

    if "auto_prompt" in value and not isinstance(value["auto_prompt"], bool):
        raise ConfigError(
            f"{loc}.auto_prompt는 true/false여야 합니다: {value['auto_prompt']!r}"
        )


_VISIBILITY_VALUES = {"public", "private"}
# from 구문: from +1d, from +1d 09:00, from 2026-04-14 09:00
_FROM_PAT = r"(\s+from\s+(\+\s*\d+\s*[smhd](\s+\d{1,2}:\d{2})?|\d{4}-\d{2}-\d{2}(\s+\d{1,2}:\d{2})?))?"""
_SCHEDULE_RE = re.compile(
    r"^(now|immediate|"
    r"now\s*\+\s*\d+\s*[smhd](\s*~\s*\d+\s*[smhd])?|"
    r"at\s+\d{4}-\d{2}-\d{2}\s+\d{1,2}|"
    r"\+\+(\s*\d+\s*[smhd](\s*~\s*\d+\s*[smhd])?)?" + _FROM_PAT + r")\s*$",
    re.IGNORECASE,
)


def _validate_publish(config: dict[str, Any]) -> None:
    """publish 섹션 엄격 검증."""
    publish = config.get("publish", {})
    if not publish:
        return
    if not isinstance(publish, dict):
        raise ConfigError(f"'publish'는 dict여야 합니다: {type(publish).__name__}")

    # schedule
    if "schedule" in publish:
        sch = publish["schedule"]
        if sch is not None and sch != "":
            if not isinstance(sch, str):
                raise ConfigError(
                    f"publish.schedule은 문자열이어야 합니다: {sch!r}"
                )
            if not _SCHEDULE_RE.match(sch):
                raise ConfigError(
                    f"publish.schedule 형식이 잘못되었습니다: {sch!r}. "
                    f"허용 형식: 'now', 'now + 15m', 'now + 15m ~ 30m', "
                    f"'at 2026-05-28 09', "
                    f"'++', '++ 15m', '++ 15m ~ 30m', "
                    f"'++ 15m from +1d', '++ 15m from +1d 09:00' (단위: s/m/h/d)"
                )

    # visibility
    if "visibility" in publish:
        vis = publish["visibility"]
        if vis not in _VISIBILITY_VALUES:
            raise ConfigError(
                f"publish.visibility는 {sorted(_VISIBILITY_VALUES)} 중 하나여야 합니다: {vis!r}"
            )

    # tags
    if "tags" in publish:
        tags = publish["tags"]
        if not isinstance(tags, list):
            raise ConfigError(
                f"publish.tags는 리스트여야 합니다: {type(tags).__name__}"
            )
        for j, t in enumerate(tags):
            if not isinstance(t, str) or not t.strip():
                raise ConfigError(
                    f"publish.tags[{j}]는 비어있지 않은 문자열이어야 합니다: {t!r}"
                )


_INTERVAL_RE = re.compile(
    r"^\d+(\.\d+)?\s*(ms|s|m|min|h)?\s*$",
    re.IGNORECASE,
)
_ON_FAILURE_VALUES = {"stop", "continue"}
_ON_RESUME_VALUES = {"restart", "skip"}


def _validate_run(config: dict[str, Any]) -> None:
    """run 섹션 엄격 검증."""
    run = config.get("run", {})
    if not run:
        return
    if not isinstance(run, dict):
        raise ConfigError(f"'run'은 dict여야 합니다: {type(run).__name__}")

    if "interval" in run:
        iv = run["interval"]
        if isinstance(iv, (int, float)):
            if iv < 0:
                raise ConfigError(f"run.interval은 0 이상이어야 합니다: {iv}")
        elif isinstance(iv, str):
            if not _INTERVAL_RE.match(iv.strip()):
                raise ConfigError(
                    f"run.interval 형식이 잘못되었습니다: {iv!r}. "
                    f"예: '30s', '2m', '500ms', '1h', 또는 숫자(초)"
                )
        else:
            raise ConfigError(
                f"run.interval은 숫자 또는 문자열이어야 합니다: {iv!r}"
            )

    if "on_failure" in run:
        v = run["on_failure"]
        if v not in _ON_FAILURE_VALUES:
            raise ConfigError(
                f"run.on_failure는 {sorted(_ON_FAILURE_VALUES)} 중 하나여야 합니다: {v!r}"
            )

    if "on_resume" in run:
        v = run["on_resume"]
        if v not in _ON_RESUME_VALUES:
            raise ConfigError(
                f"run.on_resume은 {sorted(_ON_RESUME_VALUES)} 중 하나여야 합니다: {v!r}"
            )

    for key in ("headless", "parallel"):
        if key in run and not isinstance(run[key], bool):
            raise ConfigError(
                f"run.{key}는 true/false여야 합니다: {run[key]!r}"
            )

    if "max_workers" in run:
        mw = run["max_workers"]
        if not isinstance(mw, int) or isinstance(mw, bool) or mw < 1:
            raise ConfigError(
                f"run.max_workers는 1 이상 정수여야 합니다: {mw!r}"
            )


_ALIGN_VALUES = {"left", "center", "right"}


def _validate_style(config: dict[str, Any]) -> None:
    """style 섹션 엄격 검증."""
    style = config.get("style")
    if style is None:
        return
    if not isinstance(style, dict):
        raise ConfigError(f"'style'은 dict여야 합니다: {type(style).__name__}")

    if "align" in style:
        a = style["align"]
        if a not in _ALIGN_VALUES:
            raise ConfigError(
                f"style.align은 {sorted(_ALIGN_VALUES)} 중 하나여야 합니다: {a!r}"
            )


def _validate_title_check(config: dict[str, Any], pools: dict) -> None:
    """Validate title_check config against titles and pools."""
    tc = config.get("title_check", {})
    if not tc.get("enabled"):
        return

    # match must be "exact" or "contains"
    match_mode = tc.get("match", "exact")
    if match_mode not in ("exact", "contains"):
        raise ConfigError(
            f"title_check.match must be 'exact' or 'contains', "
            f"got '{match_mode}'"
        )

    # max_attempts must be positive
    max_attempts = tc.get("max_attempts", 10)
    if not isinstance(max_attempts, int) or max_attempts < 1:
        raise ConfigError(
            f"title_check.max_attempts must be a positive integer, "
            f"got {max_attempts!r}"
        )

    # titles must contain at least one {pool:*} token for re-rolling
    titles = config.get("titles", [])
    has_pool = any(
        "pool:" in raw
        for t in titles
        for raw in _DSL_TOKEN_RE.findall(t)
    )
    if not has_pool:
        raise ConfigError(
            "title_check requires at least one {pool:*} token in titles — "
            "without pools there is nothing to re-roll on duplicate"
        )

    # Warn (not error) if pool sizes are small relative to max_attempts
    import logging
    _logger = logging.getLogger(__name__)
    for t in titles:
        pool_slugs = [
            raw.split(":", 1)[1]
            for raw in _DSL_TOKEN_RE.findall(t)
            if ":" in raw and raw.split(":", 1)[0] == "pool"
        ]
        total_combos = 1
        for slug in pool_slugs:
            total_combos *= len(pools.get(slug, []))
        if total_combos < max_attempts:
            _logger.warning(
                "title_check: pool combinations (%d) < max_attempts (%d) "
                "for template %r — some attempts may repeat",
                total_combos, max_attempts, t,
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
