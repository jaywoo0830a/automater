"""
tests/test_generator_assets.py
--------------------------------
AssetLoader 단위 테스트.

책임: assets/images/ 와 assets/thumbnails/ 를 스캔해 경로 목록을 반환한다.
"""

import pytest
from pathlib import Path
from automator.asset_loader import AssetLoader


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def asset_dir(tmp_path):
    """표준 assets/ 계층 생성."""
    (tmp_path / "assets" / "images").mkdir(parents=True)
    (tmp_path / "assets" / "thumbnails").mkdir(parents=True)
    (tmp_path / "assets" / "images" / "1.jpg").write_bytes(b"img1")
    (tmp_path / "assets" / "images" / "2.jpg").write_bytes(b"img2")
    (tmp_path / "assets" / "thumbnails" / "1.jpg").write_bytes(b"thumb1")
    return tmp_path


# ---------------------------------------------------------------------------
# 기본 탐색
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_images_returns_all_images(asset_dir):
    assert len(AssetLoader(root=asset_dir).images) == 2


@pytest.mark.unit
def test_thumbnails_returns_all_thumbnails(asset_dir):
    assert len(AssetLoader(root=asset_dir).thumbnails) == 1


@pytest.mark.unit
def test_images_are_absolute_paths(asset_dir):
    for path in AssetLoader(root=asset_dir).images:
        assert Path(path).is_absolute()


@pytest.mark.unit
def test_thumbnails_are_absolute_paths(asset_dir):
    for path in AssetLoader(root=asset_dir).thumbnails:
        assert Path(path).is_absolute()


# ---------------------------------------------------------------------------
# 정렬
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_images_sorted_numerically_before_alphabetically(asset_dir):
    """숫자 파일명은 정수 순으로, 문자 파일명은 그 다음에 온다."""
    (asset_dir / "assets" / "images" / "10.jpg").write_bytes(b"img10")
    stems   = [Path(p).stem for p in AssetLoader(root=asset_dir).images]
    numeric = [s for s in stems if s.isdigit()]
    assert numeric == sorted(numeric, key=int)
    assert stems.index("1") < stems.index("2") < stems.index("10")


@pytest.mark.unit
def test_alphabetic_filenames_sorted_case_insensitive(tmp_path):
    (tmp_path / "assets" / "images").mkdir(parents=True)
    for name in ("banana.jpg", "Apple.jpg", "cherry.jpg"):
        (tmp_path / "assets" / "images" / name).write_bytes(b"x")
    stems = [Path(p).stem.lower() for p in AssetLoader(root=tmp_path).images]
    assert stems == sorted(stems)


# ---------------------------------------------------------------------------
# 지원 확장자 필터링
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_unsupported_extension_excluded(asset_dir):
    (asset_dir / "assets" / "images" / "3.gif").write_bytes(b"gif")
    assert not any(p.endswith(".gif") for p in AssetLoader(root=asset_dir).images)


@pytest.mark.unit
def test_all_supported_extensions_included(tmp_path):
    """jpg, jpeg, png, webp 네 가지 확장자를 모두 인식한다."""
    (tmp_path / "assets" / "images").mkdir(parents=True)
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        (tmp_path / "assets" / "images" / f"file{ext}").write_bytes(b"x")
    assert len(AssetLoader(root=tmp_path).images) == 4


@pytest.mark.unit
def test_extension_check_is_case_insensitive(tmp_path):
    (tmp_path / "assets" / "images").mkdir(parents=True)
    (tmp_path / "assets" / "images" / "photo.JPG").write_bytes(b"x")
    assert len(AssetLoader(root=tmp_path).images) == 1


# ---------------------------------------------------------------------------
# 엣지 케이스
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_missing_assets_dir_returns_empty(tmp_path):
    loader = AssetLoader(root=tmp_path)
    assert loader.images == []
    assert loader.thumbnails == []


@pytest.mark.unit
def test_empty_images_dir_returns_empty(tmp_path):
    (tmp_path / "assets" / "images").mkdir(parents=True)
    assert AssetLoader(root=tmp_path).images == []


@pytest.mark.unit
def test_images_property_returns_independent_copy(asset_dir):
    """외부에서 반환된 리스트를 수정해도 내부 상태가 변하지 않는다."""
    loader      = AssetLoader(root=asset_dir)
    first_call  = loader.images
    first_call.clear()
    assert len(loader.images) == 2


@pytest.mark.unit
def test_thumbnails_property_returns_independent_copy(asset_dir):
    loader     = AssetLoader(root=asset_dir)
    first_call = loader.thumbnails
    first_call.clear()
    assert len(loader.thumbnails) == 1


@pytest.mark.unit
def test_subdirectories_not_included(tmp_path):
    """하위 디렉토리는 파일 목록에 포함되지 않는다."""
    (tmp_path / "assets" / "images" / "subdir").mkdir(parents=True)
    (tmp_path / "assets" / "images" / "1.jpg").write_bytes(b"img")
    assert len(AssetLoader(root=tmp_path).images) == 1


@pytest.mark.unit
def test_default_root_uses_cwd(monkeypatch, asset_dir):
    """root 미지정 시 CWD 를 사용한다."""
    monkeypatch.chdir(asset_dir)
    loader = AssetLoader()
    assert len(loader.images) == 2
