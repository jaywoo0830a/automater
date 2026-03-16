"""
tests/test_asset_loader.py
----------------------------
Unit tests for AssetLoader.
"""

import pytest
from pathlib import Path
from automator.asset_loader import AssetLoader
from automator.options import ContentOption


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_assets(tmp_path, images=(), thumbnails=()):
    (tmp_path / "assets" / "images").mkdir(parents=True, exist_ok=True)
    (tmp_path / "assets" / "thumbnails").mkdir(parents=True, exist_ok=True)
    for name in images:
        (tmp_path / "assets" / "images" / name).write_bytes(b"")
    for name in thumbnails:
        (tmp_path / "assets" / "thumbnails" / name).write_bytes(b"")
    return tmp_path


# ---------------------------------------------------------------------------
# 파일 감지
# ---------------------------------------------------------------------------

class TestFileDetection:

    def test_detects_jpg_files(self, tmp_path):
        _make_assets(tmp_path, images=["1.jpg", "2.jpg"])
        assert len(AssetLoader(tmp_path).images) == 2

    def test_detects_png_files(self, tmp_path):
        _make_assets(tmp_path, images=["1.png", "2.png", "3.png"])
        assert len(AssetLoader(tmp_path).images) == 3

    def test_detects_mixed_extensions(self, tmp_path):
        _make_assets(tmp_path, images=["1.jpg", "2.png", "3.jpeg"])
        assert len(AssetLoader(tmp_path).images) == 3

    def test_ignores_non_image_files(self, tmp_path):
        _make_assets(tmp_path, images=["1.jpg", "readme.txt", ".DS_Store"])
        assert len(AssetLoader(tmp_path).images) == 1

    def test_detects_thumbnails(self, tmp_path):
        _make_assets(tmp_path, thumbnails=["1.jpg", "2.jpg"])
        assert len(AssetLoader(tmp_path).thumbnails) == 2

    def test_empty_dir_returns_empty(self, tmp_path):
        _make_assets(tmp_path)
        assert AssetLoader(tmp_path).images == []

    def test_missing_dir_returns_empty(self, tmp_path):
        assert AssetLoader(tmp_path).images == []
        assert AssetLoader(tmp_path).thumbnails == []


# ---------------------------------------------------------------------------
# 정렬 — 숫자 순서
# ---------------------------------------------------------------------------

class TestSorting:

    def test_images_sorted_numerically(self, tmp_path):
        _make_assets(tmp_path, images=["10.jpg", "2.jpg", "1.jpg"])
        names = [Path(p).name for p in AssetLoader(tmp_path).images]
        assert names == ["1.jpg", "2.jpg", "10.jpg"]

    def test_thumbnails_sorted_numerically(self, tmp_path):
        _make_assets(tmp_path, thumbnails=["3.png", "1.png", "2.png"])
        names = [Path(p).name for p in AssetLoader(tmp_path).thumbnails]
        assert names == ["1.png", "2.png", "3.png"]

    def test_mixed_numeric_non_numeric_sorted(self, tmp_path):
        _make_assets(tmp_path, images=["banner.jpg", "2.jpg", "1.jpg"])
        names = [Path(p).name for p in AssetLoader(tmp_path).images]
        assert names[0] == "1.jpg"
        assert names[1] == "2.jpg"
        assert names[2] == "banner.jpg"


# ---------------------------------------------------------------------------
# to_content_option() — 명시적 레이아웃
# ---------------------------------------------------------------------------

class TestToContentOption:

    def test_returns_content_option(self, tmp_path):
        _make_assets(tmp_path, images=["1.jpg"], thumbnails=["1.jpg"])
        opt = AssetLoader(tmp_path).to_content_option(layout=["Image 1", "Thumbnail 1"])
        assert isinstance(opt, ContentOption)

    def test_layout_is_exactly_what_was_passed(self, tmp_path):
        _make_assets(tmp_path, images=["1.jpg", "2.jpg"], thumbnails=["1.jpg"])
        layout = ["Thumbnail 1", "Paragraph 1", "Image 1", "Paragraph 2", "Image 2"]
        opt = AssetLoader(tmp_path).to_content_option(layout=layout)
        assert opt.layout == layout

    def test_thumbnail_can_be_first(self, tmp_path):
        _make_assets(tmp_path, images=["1.jpg"], thumbnails=["1.jpg"])
        layout = ["Thumbnail 1", "Paragraph 1", "Image 1"]
        opt = AssetLoader(tmp_path).to_content_option(layout=layout)
        assert opt.layout[0] == "Thumbnail 1"

    def test_image_can_be_last(self, tmp_path):
        _make_assets(tmp_path, images=["1.jpg"], thumbnails=["1.jpg"])
        layout = ["Thumbnail 1", "Paragraph 1", "Image 1"]
        opt = AssetLoader(tmp_path).to_content_option(layout=layout)
        assert opt.layout[-1] == "Image 1"

    def test_preview_images_populated(self, tmp_path):
        _make_assets(tmp_path, images=["1.jpg", "2.jpg"])
        opt = AssetLoader(tmp_path).to_content_option(layout=["Image 1", "Image 2"])
        assert len(opt.preview_images) == 2

    def test_thumbnail_images_populated(self, tmp_path):
        _make_assets(tmp_path, thumbnails=["1.jpg"])
        opt = AssetLoader(tmp_path).to_content_option(layout=["Thumbnail 1"])
        assert len(opt.thumbnail_images) == 1

    def test_paragraphs_only_layout(self, tmp_path):
        """이미지 없이 단락만으로도 레이아웃 지정 가능."""
        _make_assets(tmp_path)
        layout = ["Paragraph 1", "Paragraph 2", "Paragraph 3"]
        opt = AssetLoader(tmp_path).to_content_option(layout=layout)
        assert opt.layout == layout

    def test_kwargs_forwarded_to_content_option(self, tmp_path):
        _make_assets(tmp_path, images=["1.jpg"])
        opt = AssetLoader(tmp_path).to_content_option(
            layout=["Image 1"],
            paragraph_newlines=3,
        )
        assert opt.paragraph_newlines == 3
