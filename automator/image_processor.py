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
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from automator.options import ImageBlock, FeaturedImageBlock
from automator.exif_optimizer import optimize_exif


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

def process_image(src: bytes, block: ImageBlock | FeaturedImageBlock) -> bytes:
    """
    이미지 변환 파이프라인. block 타입에 따라 적용할 변환이 결정된다.

    공통:      size_jitter → pixel_jitter → saturation → exif
    Featured:  + hue → brightness → overlay
    """
    img = Image.open(io.BytesIO(src)).convert("RGB")
    img = _apply_size_jitter(img, block.size_jitter_px)
    img = _apply_pixel_jitter(img, block.pixel_jitter)

    if isinstance(block, FeaturedImageBlock):
        img = _apply_saturation(img, block.saturation_shift)
        img = _apply_hue_shift(img, block.hue_shift)
        img = _apply_brightness(img, block.brightness_shift)
        img = _apply_text_overlay(
            img,
            text=block.overlay_text,
            color=block.overlay_color,
            background=block.overlay_background,
            position=block.overlay_position,
        )
    else:
        img = _apply_saturation(img, block.saturation_jitter)

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


def _apply_saturation(img: Image.Image, jitter: float) -> Image.Image:
    if jitter <= 0.0:
        return img
    from PIL import ImageEnhance
    factor = max(0.0, 1.0 + random.uniform(-jitter, jitter))
    return ImageEnhance.Color(img).enhance(factor)


def _apply_hue_shift(img: Image.Image, shift: float) -> Image.Image:
    """
    Rotate hue by a random amount within ±shift (0.0~1.0 = 0~360°).

    Converts RGB → HSV, shifts hue channel, converts back.
    Pure Pillow — no numpy dependency.
    """
    if shift <= 0.0:
        return img
    offset = random.uniform(-shift, shift)
    hsv = img.convert("HSV")
    h, s, v = hsv.split()
    h = h.point(lambda p: (p + int(offset * 255)) % 256)
    return Image.merge("HSV", (h, s, v)).convert("RGB")


def _apply_brightness(img: Image.Image, shift: float) -> Image.Image:
    """Randomly adjust brightness within ±shift factor."""
    if shift <= 0.0:
        return img
    from PIL import ImageEnhance
    factor = max(0.1, 1.0 + random.uniform(-shift, shift))
    return ImageEnhance.Brightness(img).enhance(factor)


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
