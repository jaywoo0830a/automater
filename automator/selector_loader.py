"""
automator/selector_loader.py
-----------------------------
Loads a superselect-format JSON file and resolves Playwright locators from it.

Supported pw string formats (produced by the superselect Chrome extension):
  page.locator('<css>')
  page.locator('<css>').first
  page.get_by_text('<text>', exact=True)
  page.get_by_label('<label>')
  page.get_by_test_id('<testid>')
  page.locator('xpath=<xpath>')
  page.locator('xpath=<xpath>').first

The ``ctx`` argument to locator() accepts any object that exposes the same
Playwright API: a sync Page, a FrameLocator, or a Frame.  This lets callers
pass a plain page (login flow) or a frame_locator (editor flow) without any
extra wrapping.

Usage:
    from automator.selector_loader import SelectorLoader

    login   = SelectorLoader.load("selectors/naver/login.json")
    editor  = SelectorLoader.load("selectors/naver/editor.json")

    # Outside an iframe — pass the page directly
    login.locator(page, "naver_login_id").fill(naver_id)

    # Inside an iframe — pass a FrameLocator
    frame = page.frame_locator("#mainFrame").first
    editor.locator(frame, "editor_title").click()
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Regex patterns for each supported pw string format
# ---------------------------------------------------------------------------

# page.locator('#id')  /  page.locator('#id').first
_RE_LOCATOR = re.compile(r"^page\.locator\((['\"])(.+?)\1\)(?:\.first)?$")

# page.get_by_text('텍스트', exact=True)  /  without exact=True
_RE_GET_BY_TEXT = re.compile(
    r"^page\.get_by_text\((['\"])(.+?)\1(?:,\s*exact\s*=\s*(True|False))?\)(?:\.first)?$"
)

# page.get_by_label('라벨')
_RE_GET_BY_LABEL = re.compile(r"^page\.get_by_label\((['\"])(.+?)\1\)(?:\.first)?$")

# page.get_by_test_id('testid')
_RE_GET_BY_TEST_ID = re.compile(r"^page\.get_by_test_id\((['\"])(.+?)\1\)(?:\.first)?$")


def _resolve(ctx: Any, pw: str) -> Any:
    """
    Parse a single superselect ``pw`` string and call the matching
    Playwright method on ``ctx`` (Page, Frame, or FrameLocator).

    Returns the resulting Playwright Locator.
    Raises ValueError if the pw string format is unrecognised.
    """
    # get_by_test_id — highest priority, most stable
    m = _RE_GET_BY_TEST_ID.match(pw)
    if m:
        return ctx.get_by_test_id(m.group(2))

    # get_by_text
    m = _RE_GET_BY_TEXT.match(pw)
    if m:
        exact = m.group(3) != "False" if m.group(3) else True
        return ctx.get_by_text(m.group(2), exact=exact)

    # get_by_label
    m = _RE_GET_BY_LABEL.match(pw)
    if m:
        return ctx.get_by_label(m.group(2))

    # locator (CSS or xpath)
    m = _RE_LOCATOR.match(pw)
    if m:
        selector = m.group(2)
        return ctx.locator(selector)

    raise ValueError(f"Unrecognised pw format: {pw!r}")


class SelectorLoader:
    """
    Wraps a superselect-format JSON registry and resolves Playwright locators.

    Attributes:
        _data:  Raw dict loaded from JSON — keys are selector aliases.
        _path:  Source file path (for error messages).
    """

    def __init__(self, data: dict[str, Any], path: Path) -> None:
        self._data = data
        self._path = path

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path) -> "SelectorLoader":
        """
        Load a superselect JSON file and return a SelectorLoader.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError:        If the file is not valid JSON.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Selector file not found: {p}")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {p}: {e}") from e
        return cls(data, p)

    # ------------------------------------------------------------------
    # Inspection helpers
    # ------------------------------------------------------------------

    def keys(self) -> list[str]:
        """Return all selector keys defined in the JSON."""
        return list(self._data.keys())

    def primary(self, key: str) -> str:
        """
        Return the raw ``primary`` pw string for a given key.

        Raises KeyError if the key is not found.
        """
        if key not in self._data:
            raise KeyError(f"Selector key {key!r} not found in {self._path}")
        return self._data[key]["primary"]

    def best_selector(self, key: str) -> dict[str, Any]:
        """
        Return the selector entry (label, pw, score) with the highest score.

        Raises KeyError if the key is not found.
        """
        if key not in self._data:
            raise KeyError(f"Selector key {key!r} not found in {self._path}")
        selectors = self._data[key]["selectors"]
        return max(selectors, key=lambda s: s["score"])

    # ------------------------------------------------------------------
    # Core: locator resolution
    # ------------------------------------------------------------------

    def locator(self, ctx: Any, key: str) -> Any:
        """
        Resolve the best available Playwright locator for ``key`` on ``ctx``.

        Strategy:
          1. Try the highest-score selector entry first.
          2. On ValueError (unrecognised format), fall back to the primary string.

        Args:
            ctx: A Playwright Page, Frame, or FrameLocator.
            key: Selector alias defined in the JSON file.

        Returns:
            A Playwright Locator.

        Raises:
            KeyError:   If ``key`` is not defined in the JSON.
            ValueError: If no selector format can be parsed.
        """
        if key not in self._data:
            raise KeyError(f"Selector key {key!r} not found in {self._path}")

        best = self.best_selector(key)
        try:
            return _resolve(ctx, best["pw"])
        except ValueError:
            # Fallback: try the primary string
            return _resolve(ctx, self._data[key]["primary"])
