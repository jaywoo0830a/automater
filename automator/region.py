"""
automator/region.py
-------------------
영역 지정 문자열을 파싱하여 마스크(L-mode Image)를 생성한다.

지원 영역:
    "all"              — 전체
    "border:20"        — 테두리 20px
    "border:10%"       — 테두리 (짧은 변 기준 10%)
    "border:10 ~ 30"   — 테두리 10~30px 랜덤
    "border:5% ~ 15%"  — 테두리 5~15% 랜덤
    "center:60%"       — 중앙 60% (가로·세로 각각)
    "top:30%"          — 상단 30%
    "bottom:30%"       — 하단 30%
    "left:30%"         — 좌측 30%
    "right:30%"        — 우측 30%
    "rect:x,y,w,h"    — 절대 좌표 (px)

값에 ``~`` 가 포함되면 범위 내 랜덤 값을 사용한다.
"""

from __future__ import annotations

import random
import re

from PIL import Image, ImageDraw


def parse_region(spec: str, width: int, height: int) -> Image.Image:
    """영역 spec 문자열 → L-mode 마스크 (255=적용, 0=미적용).

    Returns:
        ``Image.Image`` mode "L", size ``(width, height)``.
    """
    spec = spec.strip().lower()

    if spec == "all" or not spec:
        return Image.new("L", (width, height), 255)

    if spec.startswith("border:"):
        return _mask_border(spec, width, height)
    if spec.startswith("center:"):
        return _mask_center(spec, width, height)
    if spec.startswith("top:"):
        return _mask_top(spec, width, height)
    if spec.startswith("bottom:"):
        return _mask_bottom(spec, width, height)
    if spec.startswith("left:"):
        return _mask_left(spec, width, height)
    if spec.startswith("right:"):
        return _mask_right(spec, width, height)
    if spec.startswith("rect:"):
        return _mask_rect(spec, width, height)

    raise ValueError(f"Unknown region spec: {spec!r}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_range(raw: str) -> str:
    """``'10 ~ 30'`` → 10~30 사이 랜덤 값 문자열, ``'20'`` → 그대로 반환.

    퍼센트도 지원: ``'5% ~ 15%'`` → ``'11%'`` 등.
    """
    if "~" not in raw:
        return raw.strip()
    left, right = raw.split("~", 1)
    left, right = left.strip(), right.strip()
    is_pct = left.endswith("%") or right.endswith("%")
    lo = float(left.replace("%", ""))
    hi = float(right.replace("%", ""))
    val = random.uniform(lo, hi)
    if is_pct:
        return f"{val}%"
    # px 값은 정수로
    return str(int(round(val)))


def _parse_value(raw: str, reference: int) -> int:
    """'20' → 20px, '10%' → reference의 10%. 범위(~)도 지원."""
    raw = _resolve_range(raw)
    if raw.endswith("%"):
        return max(0, int(reference * float(raw[:-1]) / 100.0))
    return max(0, int(float(raw)))


def _mask_border(spec: str, w: int, h: int) -> Image.Image:
    val = spec.split(":", 1)[1]
    ref = min(w, h)
    thickness = _parse_value(val, ref)
    mask = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(mask)
    # 내부를 0으로 채워서 테두리만 남김
    inner = (thickness, thickness, w - thickness, h - thickness)
    if inner[2] > inner[0] and inner[3] > inner[1]:
        draw.rectangle(inner, fill=0)
    return mask


def _mask_center(spec: str, w: int, h: int) -> Image.Image:
    raw = spec.split(":", 1)[1]
    cw = _parse_value(raw, w)
    ch = _parse_value(raw, h)
    x0 = (w - cw) // 2
    y0 = (h - ch) // 2
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rectangle((x0, y0, x0 + cw, y0 + ch), fill=255)
    return mask


def _mask_top(spec: str, w: int, h: int) -> Image.Image:
    extent = _parse_value(spec.split(":", 1)[1], h)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rectangle((0, 0, w, extent), fill=255)
    return mask


def _mask_bottom(spec: str, w: int, h: int) -> Image.Image:
    extent = _parse_value(spec.split(":", 1)[1], h)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rectangle((0, h - extent, w, h), fill=255)
    return mask


def _mask_left(spec: str, w: int, h: int) -> Image.Image:
    extent = _parse_value(spec.split(":", 1)[1], w)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rectangle((0, 0, extent, h), fill=255)
    return mask


def _mask_right(spec: str, w: int, h: int) -> Image.Image:
    extent = _parse_value(spec.split(":", 1)[1], w)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rectangle((w - extent, 0, w, h), fill=255)
    return mask


def _mask_rect(spec: str, w: int, h: int) -> Image.Image:
    parts = spec.split(":", 1)[1].split(",")
    if len(parts) != 4:
        raise ValueError(f"rect requires 4 values (x,y,w,h): {spec!r}")
    x, y, rw, rh = (int(p.strip()) for p in parts)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rectangle((x, y, x + rw, y + rh), fill=255)
    return mask
