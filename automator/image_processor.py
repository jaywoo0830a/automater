"""
automator/image_processor.py
------------------------------
이미지 변환 파이프라인. ImageBlock / FeaturedImageBlock 을 직접 받는다.

Usage:
    from automator.image_processor import process_image

    processed_bytes = process_image(raw_bytes, block)
"""

from __future__ import annotations

import io
import logging
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from automator.options import (
    AILayer,
    EffectLayer,
    FeaturedImageBlock,
    ImageBlock,
    ImageLayer,
    Layer,
)
from automator.exif_optimizer import optimize_exif
from automator.ports import ImageGenerator
from automator.region_effect import apply_regional_effect


_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JPEG encoding helper
# ---------------------------------------------------------------------------

def _to_jpeg(img: Image.Image, quality: int = 92) -> bytes:
    """Encode a PIL Image to JPEG bytes."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def process_image(
    src: bytes,
    block: ImageBlock | FeaturedImageBlock,
    *,
    image_generator: ImageGenerator | None = None,
) -> bytes:
    """
    이미지 변환 파이프라인.

    공통:      size_jitter → pixel_jitter → effects → layers → exif
    Featured:  + overlay (layers 후)

    layers는 선언 순서대로 합성된다 (ai / image / effect 혼합 가능).
    AI 레이어 생성 실패 시 원본을 그대로 사용하고 경고만 남긴다.
    """
    img = Image.open(io.BytesIO(src)).convert("RGB")
    img = _apply_size_jitter(img, block.size_jitter_px)
    img = _apply_pixel_jitter(img, block.pixel_jitter)

    # 기존 effects (레이어 도입 전 호환)
    for fx in block.effects:
        if fx.effect:
            img = apply_regional_effect(img, fx.region, fx.effect)

    # 레이어 합성 — 선언 순서대로
    layers = getattr(block, "layers", ())
    if layers:
        img = _compose_layers(img, layers, image_generator)

    if isinstance(block, FeaturedImageBlock):
        img = _apply_text_overlay(
            img,
            text=block.overlay_text,
            color=block.overlay_color,
            background=block.overlay_background,
            position=block.overlay_position,
        )

    jpeg_bytes = _to_jpeg(img)
    return optimize_exif(
        jpeg_bytes,
        enabled=block.exif_optimization,
        description=block.exif_description,
        gps_lat=block.exif_gps_lat,
        gps_lng=block.exif_gps_lng,
    )


# ---------------------------------------------------------------------------
# Pipeline steps (private)
# ---------------------------------------------------------------------------

def _compose_layers(
    base: Image.Image,
    layers: tuple[Layer, ...],
    generator: ImageGenerator | None,
) -> Image.Image:
    """Apply a stack of AI/image/effect layers on top of ``base`` in order.

    On any failure (network, missing file, bad bytes), skip that layer and
    continue — matches the "just use the base image on failure" policy.
    """
    canvas = base.convert("RGBA")

    for layer in layers:
        if isinstance(layer, EffectLayer):
            if not layer.effect:
                continue
            rgb = canvas.convert("RGB")
            rgb = apply_regional_effect(rgb, layer.region, layer.effect)
            canvas = rgb.convert("RGBA")
            continue

        if isinstance(layer, AILayer):
            if generator is None:
                _log.warning("AILayer declared but no ImageGenerator injected; skipping")
                continue
            w, h = canvas.size
            try:
                img_bytes = generator.generate(
                    layer.prompt,
                    width=layer.width or w,
                    height=layer.height or h,
                    seed=layer.seed,
                    model=layer.model,
                )
            except Exception as e:
                _log.warning("AILayer generator raised %s: %s", type(e).__name__, e)
                img_bytes = None
            if not img_bytes:
                _log.warning(
                    "AILayer generation returned empty — falling back to base image "
                    "(prompt=%r)", layer.prompt[:80],
                )
                continue
            try:
                overlay = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
            except Exception as e:
                _log.warning("AILayer invalid image bytes: %s", e)
                continue
            canvas = _composite_layer(canvas, overlay, layer.opacity, layer.blend, layer.fit)
            continue

        if isinstance(layer, ImageLayer):
            try:
                overlay = Image.open(layer.path).convert("RGBA")
            except (FileNotFoundError, OSError) as e:
                _log.warning("ImageLayer load failed (%s): %s", layer.path, e)
                continue
            canvas = _composite_layer(canvas, overlay, layer.opacity, layer.blend, layer.fit)
            continue

    return canvas.convert("RGB")


def _composite_layer(
    base:    Image.Image,
    overlay: Image.Image,
    opacity: float,
    blend:   str,
    fit:     str,
) -> Image.Image:
    """Resize + alpha-adjust + composite a single layer over ``base`` (RGBA)."""
    sized = _fit_overlay(overlay, base.size, fit)

    if opacity < 1.0:
        alpha = sized.split()[3] if sized.mode == "RGBA" else Image.new("L", sized.size, 255)
        alpha = alpha.point(lambda v: int(v * opacity))
        sized = sized.copy()
        sized.putalpha(alpha)

    if blend != "normal":
        _log.warning("blend mode %r not yet implemented, using 'normal'", blend)

    return Image.alpha_composite(base, sized)


def _fit_overlay(overlay: Image.Image, size: tuple[int, int], fit: str) -> Image.Image:
    w, h = size
    ow, oh = overlay.size

    if fit == "stretch":
        return overlay.resize((w, h), Image.LANCZOS)

    if fit == "contain":
        scale = min(w / ow, h / oh)
        nw, nh = max(1, int(ow * scale)), max(1, int(oh * scale))
        resized = overlay.resize((nw, nh), Image.LANCZOS)
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        canvas.paste(resized, ((w - nw) // 2, (h - nh) // 2))
        return canvas

    if fit == "tile":
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        for y in range(0, h, oh):
            for x in range(0, w, ow):
                canvas.paste(overlay, (x, y))
        return canvas

    # default: cover
    scale = max(w / ow, h / oh)
    nw, nh = max(1, int(ow * scale)), max(1, int(oh * scale))
    resized = overlay.resize((nw, nh), Image.LANCZOS)
    left = (nw - w) // 2
    top = (nh - h) // 2
    return resized.crop((left, top, left + w, top + h))


def _apply_pixel_jitter(img: Image.Image, enabled: bool) -> Image.Image:
    if not enabled:
        return img
    pixels = img.load()
    w, h   = img.size
    for _ in range(random.randint(1, 3)):
        x = random.randint(0, w - 1)
        y = random.randint(0, h - 1)
        r, g, b = pixels[x, y]
        pixels[x, y] = (
            max(0, min(255, r + random.choice([-1, 1]))),
            max(0, min(255, g + random.choice([-1, 1]))),
            max(0, min(255, b + random.choice([-1, 1]))),
        )
    return img


def _apply_size_jitter(img: Image.Image, jitter_px: int) -> Image.Image:
    if jitter_px == 0:
        return img
    w, h  = img.size
    new_w = max(1, w + random.randint(-jitter_px, jitter_px))
    new_h = max(1, h + random.randint(-jitter_px, jitter_px))
    if (new_w, new_h) == (w, h):
        return img
    return img.resize((new_w, new_h), Image.LANCZOS)


def _apply_text_overlay(
    img:        Image.Image,
    text:       str | list,
    color:      str,
    background: float,
    position:   str,
) -> Image.Image:
    if not text:
        return img

    chunks = text.split() if isinstance(text, str) else [str(c) for c in text if c]
    if not chunks:
        return img

    draw = ImageDraw.Draw(img)
    w, h = img.size
    font = _resolve_overlay_font(draw, chunks, w, h)

    line_heights = [_text_height(draw, c, font) for c in chunks]
    line_widths  = [_text_width(draw, c, font) for c in chunks]
    line_spacing = max(4, font.size // 4) if hasattr(font, "size") else 8
    total_h      = sum(line_heights) + line_spacing * (len(chunks) - 1)
    padding_y    = max(16, font.size // 2) if hasattr(font, "size") else 16

    # Position: top / center / bottom
    if position == "top":
        start_y = padding_y
    elif position == "bottom":
        start_y = h - total_h - padding_y
    else:
        start_y = (h - total_h) // 2

    # Background banner
    if background > 0.0:
        banner_top    = max(0, start_y - padding_y)
        banner_bottom = min(h, start_y + total_h + padding_y)
        overlay_img   = Image.new("RGBA", img.size, (0, 0, 0, 0))
        overlay_draw  = ImageDraw.Draw(overlay_img)
        alpha = int(min(1.0, background) * 255)
        overlay_draw.rectangle(
            [(0, banner_top), (w, banner_bottom)],
            fill=(0, 0, 0, alpha),
        )
        img = Image.alpha_composite(img.convert("RGBA"), overlay_img).convert("RGB")
        draw = ImageDraw.Draw(img)

    # Text shadow
    shadow_offset = max(1, font.size // 18) if hasattr(font, "size") else 1
    shadow_color  = "#000000" if color.upper() in ("#FFFFFF", "#FFF") else "#FFFFFF"

    y = start_y
    for i, chunk in enumerate(chunks):
        x = (w - line_widths[i]) // 2
        draw.text((x + shadow_offset, y + shadow_offset), chunk,
                  font=font, fill=shadow_color)
        draw.text((x, y), chunk, font=font, fill=color)
        y += line_heights[i] + line_spacing

    return img


def _resolve_overlay_font(
    draw: ImageDraw.ImageDraw,
    chunks: list[str],
    img_w: int,
    img_h: int,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load the best available CJK font and scale it to fit the image."""
    fonts_dir = Path(__file__).parent.parent / "assets" / "fonts"
    font_candidates = [
        (str(fonts_dir / "NotoSansKR.ttf"), 0),
        (str(fonts_dir / "NotoSansKR.otf"), 0),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 1),
        ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 1),
        ("/System/Library/Fonts/AppleSDGothicNeo.ttc",             0),
        ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf",        0),
    ]

    def _load(size: int):
        for fp, idx in font_candidates:
            if Path(fp).exists():
                try:
                    return ImageFont.truetype(fp, size, index=idx)
                except Exception:
                    continue
        return ImageFont.load_default()

    target_w = int(img_w * 0.60)
    longest  = max(chunks, key=len)
    font_size = max(20, int(img_h * 0.20))
    font = _load(font_size)

    while font_size > 14:
        bbox = draw.textbbox((0, 0), longest, font=font)
        if (bbox[2] - bbox[0]) <= target_w:
            break
        font_size -= 2
        font = _load(font_size)

    return font


def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    """Calculate rendered width of a text string."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _text_height(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    """Calculate rendered height of a text string."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]
