"""
tests/test_generator_assets.py
--------------------------------
AssetLoader — assets/ 디렉토리 스캔 및 Block 목록 생성 검증.
"""

import pytest
from pathlib import Path
from automator.asset_loader import AssetLoader
from automator.options import ImageBlock, FeaturedImageBlock, ParagraphBlock


@pytest.fixture
def asset_dir(tmp_path):
    """표준 assets/ 계층을 tmp_path 아래에 생성한다."""
    (tmp_path / "assets" / "images").mkdir(parents=True)
    (tmp_path / "assets" / "thumbnails").mkdir(parents=True)
    (tmp_path / "assets" / "images" / "1.jpg").write_bytes(b"img1")
    (tmp_path / "assets" / "images" / "2.jpg").write_bytes(b"img2")
    (tmp_path / "assets" / "thumbnails" / "1.jpg").write_bytes(b"thumb1")
    return tmp_path


# ---------------------------------------------------------------------------
# 파일 감지
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_images_property__returns_all_images_in_assets_images(asset_dir):
    loader = AssetLoader(root=asset_dir)
    assert len(loader.images) == 2


@pytest.mark.unit
def test_thumbnails_property__returns_all_images_in_assets_thumbnails(asset_dir):
    loader = AssetLoader(root=asset_dir)
    assert len(loader.thumbnails) == 1


@pytest.mark.unit
def test_images_are_sorted_numerically_before_alphabetically(asset_dir):
    (asset_dir / "assets" / "images" / "10.jpg").write_bytes(b"img10")
    loader = AssetLoader(root=asset_dir)
    stems  = [Path(p).stem for p in loader.images]
    numeric = [s for s in stems if s.isdigit()]
    assert numeric == sorted(numeric, key=int)
    assert stems.index("1") < stems.index("2") < stems.index("10")


@pytest.mark.unit
def test_missing_assets_dir__returns_empty_lists(tmp_path):
    loader = AssetLoader(root=tmp_path)
    assert loader.images == []
    assert loader.thumbnails == []


@pytest.mark.unit
def test_unsupported_extension__not_included(asset_dir):
    (asset_dir / "assets" / "images" / "3.gif").write_bytes(b"gif")
    loader = AssetLoader(root=asset_dir)
    assert not any(p.endswith(".gif") for p in loader.images)


# ---------------------------------------------------------------------------
# default_blocks
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_default_blocks__structure_is_images_then_texts_then_featured(asset_dir):
    loader = AssetLoader(root=asset_dir)
    blocks = loader.default_blocks(prompt="test", n_paragraphs=2)
    types  = [type(b).__name__ for b in blocks]
    assert types == ["ImageBlock", "ImageBlock", "ParagraphBlock", "ParagraphBlock", "FeaturedImageBlock"]


@pytest.mark.unit
def test_default_blocks__text_blocks_carry_given_prompt(asset_dir):
    loader = AssetLoader(root=asset_dir)
    blocks = loader.default_blocks(prompt="내 프롬프트", n_paragraphs=1)
    texts  = [b for b in blocks if isinstance(b, ParagraphBlock)]
    assert all(b.prompt == "내 프롬프트" for b in texts)


@pytest.mark.unit
def test_default_blocks__no_paragraphs_by_default_returns_only_image_blocks(asset_dir):
    """n_paragraphs 미지정 시 ParagraphBlock 이 생성되지 않는다."""
    loader = AssetLoader(root=asset_dir)
    blocks = loader.default_blocks()
    types  = [type(b).__name__ for b in blocks]
    assert "ParagraphBlock" not in types


@pytest.mark.unit
def test_default_blocks__empty_dir_returns_empty_list(tmp_path):
    """assets/ 디렉토리가 없으면 빈 리스트를 반환한다."""
    loader = AssetLoader(root=tmp_path)
    blocks = loader.default_blocks(n_paragraphs=2)
    assert blocks == []
