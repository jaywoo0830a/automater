"""
tests/unit/cli/test_map_loader.py
-------------------------------------
Map file loading and resolution.

    maps:
      photo:
        file: maps/region_photo.yaml
        by: "{keyword:region}"
"""

from __future__ import annotations

import os
import tempfile

import pytest
import yaml

from cli.map_loader import load_maps, resolve_maps


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _write_map(data: dict, name: str = "test_map.yaml") -> str:
    """Write a map YAML file and return its path."""
    d = tempfile.mkdtemp()
    path = os.path.join(d, name)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True)
    return path


# ---------------------------------------------------------------------------
# load_maps — file loading
# ---------------------------------------------------------------------------

class TestLoadMaps:

    def test_loads_single_map(self):
        path = _write_map({"강남": "gangnam.jpg", "서초": "seocho.jpg"})
        maps_config = {"photo": {"file": path, "by": "{keyword:region}"}}
        loaded = load_maps(maps_config)
        assert loaded["photo"]["data"]["강남"] == "gangnam.jpg"
        assert loaded["photo"]["by"] == "{keyword:region}"

    def test_loads_multiple_maps(self):
        photo_path = _write_map({"강남": "gangnam.jpg"}, "photo.yaml")
        link_path = _write_map({"강남": "tel:010"}, "link.yaml")
        maps_config = {
            "photo": {"file": photo_path, "by": "{keyword:region}"},
            "link": {"file": link_path, "by": "{keyword:region}"},
        }
        loaded = load_maps(maps_config)
        assert "photo" in loaded
        assert "link" in loaded

    def test_empty_maps_config(self):
        loaded = load_maps({})
        assert loaded == {}

    def test_none_maps_config(self):
        loaded = load_maps(None)
        assert loaded == {}

    def test_missing_file_raises(self):
        maps_config = {"photo": {"file": "/nonexistent.yaml", "by": "{keyword:region}"}}
        with pytest.raises(FileNotFoundError):
            load_maps(maps_config)


# ---------------------------------------------------------------------------
# resolve_maps — key lookup
# ---------------------------------------------------------------------------

class TestResolveMaps:

    def test_resolves_by_keyword(self):
        path = _write_map({"강남": "gangnam.jpg", "서초": "seocho.jpg"})
        maps_config = {"photo": {"file": path, "by": "{keyword:region}"}}
        loaded = load_maps(maps_config)
        values = {"region": "강남"}
        resolved = resolve_maps(loaded, values)
        assert resolved["photo"] == "gangnam.jpg"

    def test_falls_back_to_default(self):
        path = _write_map({"강남": "gangnam.jpg", "_default": "default.jpg"})
        maps_config = {"photo": {"file": path, "by": "{keyword:region}"}}
        loaded = load_maps(maps_config)
        values = {"region": "송파"}
        resolved = resolve_maps(loaded, values)
        assert resolved["photo"] == "default.jpg"

    def test_missing_key_no_default_returns_empty(self):
        path = _write_map({"강남": "gangnam.jpg"})
        maps_config = {"photo": {"file": path, "by": "{keyword:region}"}}
        loaded = load_maps(maps_config)
        values = {"region": "송파"}
        resolved = resolve_maps(loaded, values)
        assert resolved["photo"] == ""

    def test_resolves_multiple_maps(self):
        photo_path = _write_map({"강남": "gangnam.jpg"}, "photo.yaml")
        link_path = _write_map({"강남": "tel:010"}, "link.yaml")
        maps_config = {
            "photo": {"file": photo_path, "by": "{keyword:region}"},
            "link": {"file": link_path, "by": "{keyword:region}"},
        }
        loaded = load_maps(maps_config)
        values = {"region": "강남"}
        resolved = resolve_maps(loaded, values)
        assert resolved["photo"] == "gangnam.jpg"
        assert resolved["link"] == "tel:010"

    def test_by_with_different_keyword(self):
        path = _write_map({"수학": "math.jpg", "영어": "english.jpg"})
        maps_config = {"icon": {"file": path, "by": "{keyword:subject}"}}
        loaded = load_maps(maps_config)
        values = {"region": "강남", "subject": "수학"}
        resolved = resolve_maps(loaded, values)
        assert resolved["icon"] == "math.jpg"
