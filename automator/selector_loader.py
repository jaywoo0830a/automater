"""
automator/selector_loader.py
-----------------------------
Loads automator-format selector files (YAML or JSON) and resolves
Playwright locators.

Format
------
Each entry is a key -> object with a ``locators`` list ordered from most
stable to least stable.  SelectorLoader tries them in order and returns the
first one that resolves successfully.

    # YAML example
    key_name:
      description: human-readable label (optional)
      locators:
        - type: testid
          value: seOnePublishBtn
        - type: role
          value: button
          name: 발행

Supported locator types and their Playwright equivalents
---------------------------------------------------------
  testid  -> ctx.get_by_test_id(value)
  role    -> ctx.get_by_role(value, name=name)     # name field optional
  label   -> ctx.get_by_label(value)
  text    -> ctx.get_by_text(value, exact=True)
  css     -> ctx.locator(value)
  xpath   -> ctx.locator("xpath=<value>")

Usage
-----
    from automator.selector_loader import SelectorLoader

    login  = SelectorLoader.load("selectors/naver/login.yaml")
    editor = SelectorLoader.load("selectors/naver/editor.yaml")

    # page context (outside iframe)
    login.locator(page, "naver_login_id").fill(naver_id)

    # frame context (inside #mainFrame)
    frame = page.frame_locator("#mainFrame").first
    editor.locator(frame, "editor_title").click()
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Internal: resolve one locator entry -> Playwright locator
# ---------------------------------------------------------------------------

def _resolve_one(ctx: Any, entry: dict) -> Any:
    """
    Resolve a single locator dict entry against ``ctx``.

    Raises:
        ValueError: If ``type`` is unrecognised.
    """
    t     = entry.get("type", "")
    value = entry.get("value", "")

    if t == "testid":
        return ctx.get_by_test_id(value)
    if t == "role":
        name = entry.get("name")
        if name:
            return ctx.get_by_role(value, name=name)
        return ctx.get_by_role(value)
    if t == "label":
        return ctx.get_by_label(value)
    if t == "text":
        return ctx.get_by_text(value, exact=True)
    if t == "placeholder":
        return ctx.get_by_placeholder(value)
    if t == "css":
        return ctx.locator(value)
    if t == "xpath":
        return ctx.locator(f"xpath={value}")

    raise ValueError(f"Unknown locator type: {t!r}")


# ---------------------------------------------------------------------------
# SelectorLoader
# ---------------------------------------------------------------------------

class SelectorLoader:
    """
    Wraps an automator-format selector file (YAML or JSON) and resolves
    Playwright locators from it.
    """

    def __init__(self, data: dict[str, Any], path: Path) -> None:
        self._data = data
        self._path = path

    @classmethod
    def load(cls, path: str | Path) -> "SelectorLoader":
        """
        Load an automator selector file (YAML or JSON).

        상대 경로는 프로젝트 루트(automator/ 패키지의 부모) 기준으로 해석한다.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError:        If the file cannot be parsed.
        """
        p = Path(path)
        if not p.is_absolute():
            project_root = Path(__file__).resolve().parent.parent
            candidate = project_root / p
            if candidate.exists():
                p = candidate
        if not p.exists():
            raise FileNotFoundError(f"Selector file not found: {p}")

        text = p.read_text(encoding="utf-8")

        if p.suffix in (".yaml", ".yml"):
            try:
                raw = yaml.safe_load(text) or {}
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML in {p}: {e}") from e
        else:
            try:
                raw = json.loads(text)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in {p}: {e}") from e

        # Strip comment/metadata keys
        data = {k: v for k, v in raw.items() if not k.startswith("_")}
        return cls(data, p)

    def keys(self) -> list[str]:
        """Return all selector key names defined in the file."""
        return list(self._data.keys())

    def description(self, key: str) -> str:
        """Return the human-readable description for ``key``, or empty string."""
        self._require(key)
        return self._data[key].get("description", "")

    def css(self, key: str) -> str | None:
        """
        Return the first CSS locator value for ``key``, or None.

        Used when a raw CSS string is needed (e.g. inside JS evaluate()).

        Raises:
            KeyError: If ``key`` is not defined in the file.
        """
        self._require(key)
        for entry in self._data[key].get("locators", []):
            if entry.get("type") == "css":
                return entry.get("value")
        return None

    def locator(self, ctx: Any, key: str) -> Any:
        """
        Resolve a Playwright locator for ``key`` on ``ctx``.

        Tries locators in defined order (most stable first).
        Returns the first one that resolves without raising ValueError.

        Raises:
            KeyError:   If ``key`` is not defined in the file.
            ValueError: If the entry has no usable locators.
        """
        self._require(key)
        locators: list[dict] = self._data[key].get("locators", [])

        if not locators:
            raise ValueError(
                f"Selector '{key}' in {self._path} has no locators defined."
            )

        last_err: Exception = ValueError("no locators")
        for entry in locators:
            try:
                return _resolve_one(ctx, entry)
            except ValueError as e:
                last_err = e

        raise ValueError(
            f"No locator for '{key}' could be resolved in {self._path}: {last_err}"
        )

    def _require(self, key: str) -> None:
        if key not in self._data:
            available = ", ".join(self._data.keys())
            raise KeyError(
                f"Selector '{key}' not found in {self._path}. "
                f"Available: {available}"
            )

    def __repr__(self) -> str:
        return f"SelectorLoader({list(self._data.keys())}, source={self._path!r})"
