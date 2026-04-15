"""
cli/layer_spec.py
------------------
Layer DSL — flexible stacking of base/AI/effect layers for featured images.

The DSL accepts a `layers:` list where each entry is a dict with a `type:`
discriminator. Layers are composed top-down in list order.

Example:
    featured_image:
      path: "thumb.jpg"        # base image (rendered first)
      layers:
        - type: ai
          prompt: "{keyword:topic} aesthetic background"
          opacity: 0.1
          provider: together
        - type: image
          path: "watermark.png"
          opacity: 0.3
        - type: effect
          region: "border:20"
          effect: "brightness:0.5"

Parsing only — composition/rendering lives in the automator layer.
"""

from __future__ import annotations

import random
from typing import Any

from automator.options import AILayer, EffectLayer, ImageLayer, Layer

from cli.config_loader import ConfigError
from cli.dsl import interpolate_deep


VALID_BLEND_MODES = ("normal", "multiply", "screen", "overlay")
VALID_FIT_MODES = ("cover", "contain", "stretch", "tile")

__all__ = [
    "AILayer",
    "EffectLayer",
    "ImageLayer",
    "Layer",
    "VALID_BLEND_MODES",
    "VALID_FIT_MODES",
    "parse_layers",
]


def parse_layers(
    raw:        Any,
    values:     dict[str, str],
    pools:      dict[str, list[str]],
    images_dir: str,
    index:      int = 0,
    rng:        random.Random | None = None,
    maps:       dict[str, str] | None = None,
) -> tuple[Layer, ...]:
    """Parse a `layers:` list from DSL config into structured Layer objects.

    Args:
        raw:        The raw value of the `layers:` key (expected: list of dicts).
        values:     Keyword slug → value mapping for token interpolation.
        pools:      Pool slug → value list for token interpolation.
        images_dir: Base directory used to resolve ImageLayer relative paths.
        index:      1-based combo index for `{i}` token.
        rng:        Optional RNG for deterministic pool selection.
        maps:       Optional resolved map values.

    Returns:
        Tuple of Layer dataclass instances in declared order.

    Raises:
        ConfigError: Invalid shape, missing discriminator, or unknown type.
    """
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ConfigError(
            f"`layers`는 리스트여야 합니다. 받은 값: {type(raw).__name__}"
        )

    out: list[Layer] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ConfigError(
                f"`layers[{i}]`는 dict여야 합니다. 받은 값: {entry!r}"
            )

        cfg = interpolate_deep(dict(entry), values, pools, index, rng, maps)

        layer_type = cfg.get("type")
        if not layer_type:
            raise ConfigError(
                f"`layers[{i}]`에 `type` 필드가 없습니다. "
                f"허용되는 값: 'ai', 'image', 'effect'. 받은 값: {entry!r}"
            )

        if layer_type == "ai":
            out.append(_parse_ai_layer(cfg, i))
        elif layer_type == "image":
            out.append(_parse_image_layer(cfg, i, images_dir))
        elif layer_type == "effect":
            out.append(_parse_effect_layer(cfg, i))
        else:
            raise ConfigError(
                f"`layers[{i}]`의 `type`이 알 수 없는 값입니다: {layer_type!r}. "
                f"허용: 'ai', 'image', 'effect'."
            )

    return tuple(out)


def _parse_ai_layer(cfg: dict[str, Any], i: int) -> AILayer:
    prompt = str(cfg.get("prompt", "")).strip()
    if not prompt:
        raise ConfigError(
            f"`layers[{i}]` (type=ai)에 `prompt`가 비어있습니다."
        )

    return AILayer(
        prompt=prompt,
        opacity=_parse_opacity(cfg.get("opacity", 1.0), i),
        blend=_parse_blend(cfg.get("blend", "normal"), i),
        fit=_parse_fit(cfg.get("fit", "cover"), i),
        provider=str(cfg.get("provider", "together")),
        model=str(cfg.get("model", "")),
        seed=_parse_optional_int(cfg.get("seed"), i, "seed"),
        width=_parse_optional_int(cfg.get("width"), i, "width"),
        height=_parse_optional_int(cfg.get("height"), i, "height"),
    )


def _parse_image_layer(cfg: dict[str, Any], i: int, images_dir: str) -> ImageLayer:
    raw_path = str(cfg.get("path", "")).strip()
    if not raw_path:
        raise ConfigError(
            f"`layers[{i}]` (type=image)에 `path`가 비어있습니다."
        )

    from pathlib import PurePosixPath
    resolved = raw_path if not images_dir else str(PurePosixPath(images_dir) / raw_path)

    return ImageLayer(
        path=resolved,
        opacity=_parse_opacity(cfg.get("opacity", 1.0), i),
        blend=_parse_blend(cfg.get("blend", "normal"), i),
        fit=_parse_fit(cfg.get("fit", "cover"), i),
    )


def _parse_effect_layer(cfg: dict[str, Any], i: int) -> EffectLayer:
    effect = str(cfg.get("effect", "")).strip("'\"")
    if not effect:
        raise ConfigError(
            f"`layers[{i}]` (type=effect)에 `effect`가 비어있습니다."
        )
    region = str(cfg.get("region", "all")).strip("'\"")
    return EffectLayer(region=region, effect=effect)


def _parse_opacity(value: Any, i: int) -> float:
    try:
        opacity = float(value)
    except (TypeError, ValueError):
        raise ConfigError(
            f"`layers[{i}].opacity`가 숫자가 아닙니다: {value!r}"
        )
    if not 0.0 <= opacity <= 1.0:
        raise ConfigError(
            f"`layers[{i}].opacity`는 0.0~1.0 범위여야 합니다: {opacity}"
        )
    return opacity


def _parse_blend(value: Any, i: int) -> str:
    blend = str(value).strip().lower()
    if blend not in VALID_BLEND_MODES:
        raise ConfigError(
            f"`layers[{i}].blend`가 알 수 없는 값입니다: {value!r}. "
            f"허용: {VALID_BLEND_MODES}"
        )
    return blend


def _parse_fit(value: Any, i: int) -> str:
    fit = str(value).strip().lower()
    if fit not in VALID_FIT_MODES:
        raise ConfigError(
            f"`layers[{i}].fit`가 알 수 없는 값입니다: {value!r}. "
            f"허용: {VALID_FIT_MODES}"
        )
    return fit


def _parse_optional_int(value: Any, i: int, field: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ConfigError(
            f"`layers[{i}].{field}`가 정수가 아닙니다: {value!r}"
        )
