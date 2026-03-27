"""
automator/yaml_selector_source.py
-----------------------------------
YamlSelectorSource — SelectorSource implementation backed by YAML files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from automator.ports import SelectorSource
from automator.selector_loader import SelectorLoader


class YamlSelectorSource(SelectorSource):
    """
    Load selectors from a directory of YAML files.

    Args:
        base_dir: Directory containing selector YAML files.
                  e.g. "selectors/naver/" with "editor.yaml", "login.yaml"
    """

    def __init__(self, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir)
        self._cache: dict[str, SelectorLoader] = {}

    def load(self, name: str) -> Any:
        if name not in self._cache:
            path = self._base_dir / f"{name}.yaml"
            self._cache[name] = SelectorLoader.load(path)
        return self._cache[name]
