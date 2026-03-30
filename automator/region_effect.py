"""
automator/region_effect.py
--------------------------
영역 지정 효과 적용기.

마스크 영역에만 변형을 적용하고 나머지는 원본을 유지한다.

지원 효과:
    brightness:0.5       — 밝기 (0.0 어둡게 ~ 2.0 밝게, 1.0=원본)
    brightness:0.3 ~ 0.7 — 밝기 범위 랜덤
    saturation:1.5       — 채도 (0.0 흑백 ~ 2.0 과채도, 1.0=원본)
    hue:0.1              — 색조 회전 (0.0~1.0 = 0~360°)
    blur:5               — 가우시안 블러 반경 (px)
    tint:R,G,B,A         — 컬러 틴트 (RGBA, A=0~255)
    grayscale            — 흑백 변환

파라미터에 ``~`` 가 포함되면 범위 내 랜덤 값을 사용한다.
"""

from __future__ import annotations

import random

from PIL import Image, ImageEnhance, ImageFilter

from automator.region import parse_region


def apply_regional_effect(
    img: Image.Image,
    region: str,
    effect: str,
) -> Image.Image:
    """이미지의 지정 영역에만 효과��� 적용한다.

    Args:
        img:    원본 RGB 이미지.
        region: 영역 spec 문자열 ("all", "border:20", ...).
        effect: 효과 spec 문자열 ("brightness:0.5", "blur:5", ...).

    Returns:
        효과가 적용된 새 이미지 (RGB).
    """
    region = region.strip().strip("'\"")
    w, h = img.size
    mask = parse_region(region, w, h)

    transformed = _apply_effect(img.copy(), effect)

    return Image.composite(transformed, img, mask)


def _resolve_range(param: str) -> float:
    """``'0.3 ~ 0.7'`` → 0.3~0.7 사이 랜덤, ``'0.5'`` → 0.5."""
    if "~" not in param:
        return float(param.strip())
    left, right = param.split("~", 1)
    lo, hi = float(left.strip()), float(right.strip())
    return random.uniform(lo, hi)


def _apply_effect(img: Image.Image, effect: str) -> Image.Image:
    """효과 spec을 파싱하여 이미지 전체에 적용한다."""
    effect = effect.strip().strip("'\"")  # YAML/GUI에서 따옴표가 포함될 수 있음

    if effect == "grayscale":
        return _effect_grayscale(img)

    name, _, param = effect.partition(":")
    name = name.strip().lower()
    param = param.strip()

    if name == "brightness":
        return _effect_brightness(img, _resolve_range(param))
    if name == "saturation":
        return _effect_saturation(img, _resolve_range(param))
    if name == "hue":
        return _effect_hue(img, _resolve_range(param))
    if name == "blur":
        return _effect_blur(img, _resolve_range(param))
    if name == "tint":
        return _effect_tint(img, param)

    raise ValueError(f"Unknown effect: {effect!r}")


# ---------------------------------------------------------------------------
# Effect implementations
# ---------------------------------------------------------------------------

def _effect_brightness(img: Image.Image, factor: float) -> Image.Image:
    return ImageEnhance.Brightness(img).enhance(max(0.0, factor))


def _effect_saturation(img: Image.Image, factor: float) -> Image.Image:
    return ImageEnhance.Color(img).enhance(max(0.0, factor))


def _effect_hue(img: Image.Image, shift: float) -> Image.Image:
    if shift == 0.0:
        return img
    hsv = img.convert("HSV")
    h_ch, s_ch, v_ch = hsv.split()
    offset = int(shift * 255) % 256
    h_ch = h_ch.point(lambda p: (p + offset) % 256)
    return Image.merge("HSV", (h_ch, s_ch, v_ch)).convert("RGB")


def _effect_blur(img: Image.Image, radius: float) -> Image.Image:
    return img.filter(ImageFilter.GaussianBlur(radius=max(0.0, radius)))


def _resolve_range_int(raw: str) -> int:
    """정수용 범위 해석. ``'50 ~ 150'`` → 랜덤 정수."""
    if "~" not in raw:
        return int(raw.strip())
    left, right = raw.split("~", 1)
    return random.randint(int(left.strip()), int(right.strip()))


def _effect_tint(img: Image.Image, param: str) -> Image.Image:
    parts = [p.strip() for p in param.split(",")]
    if len(parts) == 3:
        r, g, b = (_resolve_range_int(p) for p in parts)
        a = 128
    elif len(parts) == 4:
        r, g, b, a = (_resolve_range_int(p) for p in parts)
    else:
        raise ValueError(f"tint requires 3 or 4 values (R,G,B[,A]): {param!r}")
    overlay = Image.new("RGBA", img.size, (r, g, b, a))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def _effect_grayscale(img: Image.Image) -> Image.Image:
    return img.convert("L").convert("RGB")
