"""
automator/asset_loader.py
--------------------------
AssetLoader — assets/ 디렉토리에서 이미지 파일 경로를 탐색한다.

디렉토리 규칙
-------------
    assets/
    ├── images/       # 본문 이미지 경로 목록
    └── thumbnails/   # 대표 이미지 경로 목록

Usage
-----
    from automator.asset_loader import AssetLoader

    loader = AssetLoader()
    print(loader.images)     # ['assets/images/1.jpg', ...]
    print(loader.thumbnails) # ['assets/thumbnails/1.jpg']
"""

from __future__ import annotations

from pathlib import Path

_SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_IMAGES_SUBDIR        = "images"
_THUMBNAILS_SUBDIR    = "thumbnails"


def _sort_key(path: Path) -> tuple[int, int, str]:
    stem = path.stem
    if stem.isdigit():
        return (0, int(stem), "")
    return (1, 0, stem.lower())


def _scan(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    files = [
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in _SUPPORTED_EXTENSIONS
    ]
    return [str(p) for p in sorted(files, key=_sort_key)]


class AssetLoader:
    """
    assets/images/ 와 assets/thumbnails/ 를 스캔해 경로 목록을 반환한다.

    Args:
        root: 프로젝트 루트. 기본값 = CWD.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self._root       = Path(root) if root else Path.cwd()
        self._assets_dir = self._root / "assets"
        self._images     = _scan(self._assets_dir / _IMAGES_SUBDIR)
        self._thumbnails = _scan(self._assets_dir / _THUMBNAILS_SUBDIR)

    @property
    def images(self) -> list[str]:
        """본문 이미지 경로 목록."""
        return list(self._images)

    @property
    def thumbnails(self) -> list[str]:
        """대표 이미지 경로 목록."""
        return list(self._thumbnails)
