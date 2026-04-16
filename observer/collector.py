"""Session metadata collection: IP, fingerprint, user-agent pools."""

from __future__ import annotations

import hashlib
import json
import logging
import random

logger = logging.getLogger(__name__)

# Common desktop viewports (width, height)
_VIEWPORTS = [
    (1920, 1080),
    (1366, 768),
    (1440, 900),
    (1536, 864),
    (1280, 720),
    (1600, 900),
    (1280, 800),
    (1680, 1050),
]

# Recent Chrome user-agents (Windows / macOS)
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


def generate_random_fingerprint() -> dict:
    """Build a unique fingerprint config for one observation session.

    Returns a dict with ``viewport_width``, ``viewport_height``,
    ``user_agent``, and a short ``hash`` for tracking.
    """
    vp = random.choice(_VIEWPORTS)
    ua = random.choice(_USER_AGENTS)

    cfg = {
        "viewport_width": vp[0],
        "viewport_height": vp[1],
        "user_agent": ua,
    }

    raw = json.dumps(cfg, sort_keys=True)
    cfg["hash"] = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return cfg


def collect_session_ip(page) -> str:
    """Return the external IP visible from this browser session."""
    try:
        page.goto("https://api.ipify.org?format=text", timeout=10_000)
        return page.inner_text("body").strip()
    except Exception:
        logger.warning("Failed to collect session IP")
        return "unknown"
