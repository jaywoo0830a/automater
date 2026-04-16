"""Human-like behaviour patterns for anti-detection.

Provides scroll, mouse-move and delay primitives that mimic real user
interactions.  All functions are synchronous and operate on a Playwright
*Page* object.
"""

from __future__ import annotations

import logging
import math
import random
import time

logger = logging.getLogger(__name__)


# ── delays ──────────────────────────────────────────────────────────

def human_delay(lo: float, hi: float) -> None:
    """Sleep a random duration between *lo* and *hi* seconds."""
    time.sleep(random.uniform(lo, hi))


# ── scrolling ───────────────────────────────────────────────────────

def _get_scroll_y(page) -> int:
    """Safely read current scroll position."""
    try:
        return page.evaluate("window.scrollY || window.pageYOffset || 0")
    except Exception:
        return 0


def human_scroll(page, content_height: int, viewport_height: int) -> float:
    """Scroll down the page with human-like mouse wheel events.

    Scrolls to a random target between 80-100% of the page.
    Uses small, controlled wheel increments to avoid overshooting.
    Returns the final scroll progress as a fraction (0.0 - 1.0).
    """
    if content_height <= viewport_height:
        return 1.0

    max_y = content_height - viewport_height
    target_pct = random.uniform(0.80, 1.0)
    target_y = int(max_y * target_pct)
    step_count = 0
    pause_every = random.randint(4, 7)
    vw = page.viewport_size.get("width", 1920) if page.viewport_size else 1920

    logger.debug("Scroll target: %d px (%.0f%% of %d)", target_y, target_pct * 100, max_y)

    # move mouse into content area first
    try:
        human_mouse_move(
            page,
            random.randint(int(vw * 0.2), int(vw * 0.8)),
            random.randint(int(viewport_height * 0.3), int(viewport_height * 0.6)),
        )
    except Exception:
        pass

    while True:
        current_y = _get_scroll_y(page)
        remaining_px = target_y - current_y
        if remaining_px <= 0:
            break

        # scale wheel amount to remaining distance — fast at first, gentle near target
        if remaining_px > viewport_height:
            # far from target: fast burst
            amount = random.randint(300, 500)
            page.mouse.wheel(0, amount)
            time.sleep(random.uniform(0.05, 0.12))
            amount = random.randint(200, 400)
            page.mouse.wheel(0, amount)
            time.sleep(random.uniform(0.2, 0.5))
        elif remaining_px > 300:
            # approaching target: moderate
            amount = random.randint(150, 300)
            page.mouse.wheel(0, amount)
            time.sleep(random.uniform(0.3, 0.6))
        else:
            # near target: gentle
            amount = random.randint(50, 150)
            page.mouse.wheel(0, amount)
            time.sleep(random.uniform(0.2, 0.4))

        step_count += 1

        # reading pause every few steps
        if step_count % pause_every == 0:
            time.sleep(random.uniform(0.5, 1.2))
            if random.random() < 0.3:
                try:
                    _mouse_wander(page, vw, viewport_height)
                except Exception:
                    pass
            pause_every = random.randint(4, 7)

        # occasional scroll-back (~8% chance, only when far enough from target)
        if random.random() < 0.08 and remaining_px > viewport_height:
            page.mouse.wheel(0, random.randint(-150, -50))
            time.sleep(random.uniform(0.2, 0.4))

    final_y = _get_scroll_y(page)
    result = min(final_y / max_y, 1.0) if max_y > 0 else 1.0
    logger.debug("Scroll done: %d px (%.0f%%)", final_y, result * 100)
    return result


def scroll_to_bottom(page, *, max_stalls: int = 5) -> float:
    """Scroll down until the page stops moving. No height calculation needed.

    Keeps sending mouse wheel events and checks ``scrollY`` after each burst.
    Stall detection only kicks in after the page has moved at least once,
    so dynamically-loaded pages have time to render.

    Returns approximate scroll progress (0.0 - 1.0).
    """
    vw = page.viewport_size.get("width", 1920) if page.viewport_size else 1920
    vh = page.viewport_size.get("height", 1080) if page.viewport_size else 1080

    try:
        human_mouse_move(
            page,
            random.randint(int(vw * 0.2), int(vw * 0.8)),
            random.randint(int(vh * 0.3), int(vh * 0.6)),
        )
    except Exception:
        pass

    # Wait until page is scrollable (content rendered)
    for _ in range(20):  # up to ~10 seconds
        page.mouse.wheel(0, 300)
        time.sleep(0.5)
        if _get_scroll_y(page) > 0:
            break
    else:
        logger.warning("Page never became scrollable")

    stalls = 0
    step_count = 0
    pause_every = random.randint(4, 7)
    has_moved = _get_scroll_y(page) > 0
    prev_y = _get_scroll_y(page)

    while True:
        # burst scroll
        page.mouse.wheel(0, random.randint(300, 500))
        time.sleep(random.uniform(0.05, 0.10))
        page.mouse.wheel(0, random.randint(200, 400))
        time.sleep(random.uniform(0.2, 0.5))

        current_y = _get_scroll_y(page)

        if current_y > 0:
            has_moved = True

        if has_moved and current_y <= prev_y:
            stalls += 1
            if stalls >= max_stalls:
                break
        else:
            stalls = 0

        prev_y = current_y
        step_count += 1

        # reading pause
        if step_count % pause_every == 0:
            time.sleep(random.uniform(0.5, 1.2))
            if random.random() < 0.3:
                try:
                    _mouse_wander(page, vw, vh)
                except Exception:
                    pass
            pause_every = random.randint(4, 7)

        # occasional scroll-back
        if random.random() < 0.08 and current_y > vh:
            page.mouse.wheel(0, random.randint(-150, -50))
            time.sleep(random.uniform(0.2, 0.4))

    # calculate approximate progress
    final_y = _get_scroll_y(page)
    try:
        max_y = page.evaluate(
            "Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)"
            " - (window.innerHeight || document.documentElement.clientHeight)",
        )
        result = min(final_y / max_y, 1.0) if max_y > 0 else 1.0
    except Exception:
        result = 1.0

    logger.debug("scroll_to_bottom done: %d px (%.0f%%)", final_y, result * 100)
    return result


def _mouse_wander(page, viewport_width: int, viewport_height: int) -> None:
    """Move the mouse to a random spot in the visible viewport."""
    tx = random.randint(int(viewport_width * 0.1), int(viewport_width * 0.9))
    ty = random.randint(int(viewport_height * 0.2), int(viewport_height * 0.8))
    human_mouse_move(page, tx, ty)


# ── mouse movement ──────────────────────────────────────────────────

def human_mouse_move(page, target_x: int, target_y: int, *, steps: int = 0) -> None:
    """Move the mouse along a cubic-Bezier curve to (*target_x*, *target_y*)."""
    try:
        current = page.evaluate(
            "({x: window._mouseX || 0, y: window._mouseY || 0})",
        )
    except Exception:
        current = {"x": 0, "y": 0}

    sx, sy = current.get("x", 0), current.get("y", 0)

    if steps == 0:
        dist = math.hypot(target_x - sx, target_y - sy)
        steps = max(8, min(int(dist / 15), 60))

    # random control points
    cp1x = sx + (target_x - sx) * random.uniform(0.2, 0.4) + random.randint(-40, 40)
    cp1y = sy + (target_y - sy) * random.uniform(0.1, 0.3) + random.randint(-25, 25)
    cp2x = sx + (target_x - sx) * random.uniform(0.6, 0.8) + random.randint(-40, 40)
    cp2y = sy + (target_y - sy) * random.uniform(0.7, 0.9) + random.randint(-25, 25)

    for i in range(steps + 1):
        t = i / steps
        inv = 1 - t
        x = inv**3 * sx + 3 * inv**2 * t * cp1x + 3 * inv * t**2 * cp2x + t**3 * target_x
        y = inv**3 * sy + 3 * inv**2 * t * cp1y + 3 * inv * t**2 * cp2y + t**3 * target_y
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.005, 0.015))

    try:
        page.evaluate(
            f"window._mouseX = {target_x}; window._mouseY = {target_y}",
        )
    except Exception:
        pass


def human_click(page, locator) -> None:
    """Move the mouse to *locator* along a Bezier curve, then click."""
    try:
        box = locator.bounding_box()
    except Exception:
        locator.click()
        return

    if box:
        tx = int(box["x"] + box["width"] * random.uniform(0.2, 0.8))
        ty = int(box["y"] + box["height"] * random.uniform(0.2, 0.8))
        human_mouse_move(page, tx, ty)
        time.sleep(random.uniform(0.05, 0.15))
        page.mouse.click(tx, ty)
    else:
        locator.click()


def human_click_element(page, element) -> None:
    """Move the mouse to an ElementHandle along a Bezier curve, then click.

    Works with raw ElementHandle objects from ``query_selector_all``.
    Scrolls the element into view first so bounding_box() succeeds.
    """
    try:
        element.scroll_into_view_if_needed()
        time.sleep(random.uniform(0.1, 0.3))
        box = element.bounding_box()
    except Exception:
        element.click()
        return

    if box:
        tx = int(box["x"] + box["width"] * random.uniform(0.2, 0.8))
        ty = int(box["y"] + box["height"] * random.uniform(0.2, 0.8))
        human_mouse_move(page, tx, ty)
        time.sleep(random.uniform(0.05, 0.15))
        page.mouse.click(tx, ty)
    else:
        element.click()
