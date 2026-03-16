"""
tests/test_asset_loader.py
----------------------------
Unit tests for AssetLoader — assets/ 디렉토리에서 이미지를 자동 감지한다.
"""

import pytest
from pathlib import Path
from automator.asset_loader import AssetLoader


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_assets(tmp_path, images=(), thumbnails=()):
    """
    assets/images/ 와 assets/thumbnails/ 디렉토리를 tmp_path 에 생성하고
    지정된 파일명으로 빈 파일을 만든다.
    """
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
        loader = AssetLoader(root=tmp_path)
        assert len(loader.images) == 2

    def test_detects_png_files(self, tmp_path):
        _make_assets(tmp_path, images=["1.png", "2.png", "3.png"])
        loader = AssetLoader(root=tmp_path)
        assert len(loader.images) == 3

    def test_detects_mixed_extensions(self, tmp_path):
        _make_assets(tmp_path, images=["1.jpg", "2.png", "3.jpeg"])
        loader = AssetLoader(root=tmp_path)
        assert len(loader.images) == 3

    def test_ignores_non_image_files(self, tmp_path):
        _make_assets(tmp_path, images=["1.jpg", "readme.txt", ".DS_Store"])
        loader = AssetLoader(root=tmp_path)
        assert len(loader.images) == 1

    def test_detects_thumbnails(self, tmp_path):
        _make_assets(tmp_path, thumbnails=["1.jpg", "2.jpg"])
        loader = AssetLoader(root=tmp_path)
        assert len(loader.thumbnails) == 2

    def test_empty_images_dir_returns_empty(self, tmp_path):
        _make_assets(tmp_path)
        loader = AssetLoader(root=tmp_path)
        assert loader.images == []

    def test_missing_dir_returns_empty(self, tmp_path):
        loader = AssetLoader(root=tmp_path)
        assert loader.images == []
        assert loader.thumbnails == []


# ---------------------------------------------------------------------------
# 정렬 — 숫자 순서
# ---------------------------------------------------------------------------

class TestSorting:

    def test_images_sorted_numerically(self, tmp_path):
        _make_assets(tmp_path, images=["10.jpg", "2.jpg", "1.jpg"])
        loader = AssetLoader(root=tmp_path)
        names = [Path(p).name for p in loader.images]
        assert names == ["1.jpg", "2.jpg", "10.jpg"]

    def test_thumbnails_sorted_numerically(self, tmp_path):
        _make_assets(tmp_path, thumbnails=["3.png", "1.png", "2.png"])
        loader = AssetLoader(root=tmp_path)
        names = [Path(p).name for p in loader.thumbnails]
        assert names == ["1.png", "2.png", "3.png"]

    def test_mixed_numeric_non_numeric_sorted(self, tmp_path):
        """숫자 파일명이 먼저, 비숫자 파일명은 뒤에 알파벳 순."""
        _make_assets(tmp_path, images=["banner.jpg", "2.jpg", "1.jpg"])
        loader = AssetLoader(root=tmp_path)
        names = [Path(p).name for p in loader.images]
        assert names[0] == "1.jpg"
        assert names[1] == "2.jpg"
        assert names[2] == "banner.jpg"


# ---------------------------------------------------------------------------
# 레이아웃 자동 생성
# ---------------------------------------------------------------------------

class TestLayoutGeneration:

    def test_images_only_layout(self, tmp_path):
        _make_assets(tmp_path, images=["1.jpg", "2.jpg"])
        loader = AssetLoader(root=tmp_path)
        layout = loader.build_layout()
        assert layout == ["Image 1", "Image 2"]

    def test_thumbnails_only_layout(self, tmp_path):
        _make_assets(tmp_path, thumbnails=["1.jpg"])
        loader = AssetLoader(root=tmp_path)
        layout = loader.build_layout()
        assert layout == ["Thumbnail 1"]

    def test_images_and_thumbnails_layout(self, tmp_path):
        _make_assets(tmp_path, images=["1.jpg", "2.jpg"], thumbnails=["1.jpg"])
        loader = AssetLoader(root=tmp_path)
        layout = loader.build_layout()
        # Image 들이 먼저, Thumbnail 이 마지막
        assert "Image 1" in layout
        assert "Image 2" in layout
        assert layout[-1] == "Thumbnail 1"

    def test_empty_returns_empty_layout(self, tmp_path):
        _make_assets(tmp_path)
        loader = AssetLoader(root=tmp_path)
        assert loader.build_layout() == []

    def test_build_layout_with_paragraphs(self, tmp_path):
        """단락 수를 지정하면 이미지 사이에 자동 삽입된다."""
        _make_assets(tmp_path, images=["1.jpg", "2.jpg"], thumbnails=["1.jpg"])
        loader = AssetLoader(root=tmp_path)
        layout = loader.build_layout(paragraphs=2)
        # Image 1, Paragraph 1, Image 2, Paragraph 2, Thumbnail 1
        assert "Paragraph 1" in layout
        assert "Paragraph 2" in layout
        assert layout[-1] == "Thumbnail 1"

    def test_paragraphs_interleaved_with_images(self, tmp_path):
        """이미지 하나 다음에 단락 하나씩 교대로 삽입된다."""
        _make_assets(tmp_path, images=["1.jpg", "2.jpg"])
        loader = AssetLoader(root=tmp_path)
        layout = loader.build_layout(paragraphs=2)
        assert layout == ["Image 1", "Paragraph 1", "Image 2", "Paragraph 2"]

    def test_more_paragraphs_than_images(self, tmp_path):
        """단락이 이미지보다 많으면 남은 단락은 마지막에 추가된다."""
        _make_assets(tmp_path, images=["1.jpg"])
        loader = AssetLoader(root=tmp_path)
        layout = loader.build_layout(paragraphs=3)
        assert layout == ["Image 1", "Paragraph 1", "Paragraph 2", "Paragraph 3"]


# ---------------------------------------------------------------------------
# to_content_option() — ContentOption 직접 생성
# ---------------------------------------------------------------------------

class TestToContentOption:

    def test_returns_content_option(self, tmp_path):
        from automator.options import ContentOption
        _make_assets(tmp_path, images=["1.jpg"], thumbnails=["1.jpg"])
        loader = AssetLoader(root=tmp_path)
        opt = loader.to_content_option(paragraphs=1)
        assert isinstance(opt, ContentOption)

    def test_preview_images_populated(self, tmp_path):
        _make_assets(tmp_path, images=["1.jpg", "2.jpg"])
        loader = AssetLoader(root=tmp_path)
        opt = loader.to_content_option()
        assert len(opt.preview_images) == 2

    def test_thumbnail_images_populated(self, tmp_path):
        _make_assets(tmp_path, thumbnails=["1.jpg"])
        loader = AssetLoader(root=tmp_path)
        opt = loader.to_content_option()
        assert len(opt.thumbnail_images) == 1

    def test_layout_matches_detected_files(self, tmp_path):
        _make_assets(tmp_path, images=["1.jpg", "2.jpg"], thumbnails=["1.jpg"])
        loader = AssetLoader(root=tmp_path)
        opt = loader.to_content_option(paragraphs=2)
        assert "Image 1" in opt.layout
        assert "Image 2" in opt.layout
        assert "Thumbnail 1" in opt.layout
        assert "Paragraph 1" in opt.layout
        assert "Paragraph 2" in opt.layout
