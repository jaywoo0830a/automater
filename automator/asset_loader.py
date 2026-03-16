"""
automator/asset_loader.py
--------------------------
AssetLoader — assets/ 디렉토리에서 이미지를 자동 감지하고
ContentOption 을 생성한다.

디렉토리 규칙
-------------
    assets/
    ├── images/       # 본문 이미지  → "Image N" alias
    │   ├── 1.jpg
    │   ├── 2.jpg
    │   └── 3.png
    └── thumbnails/   # 대표 이미지  → "Thumbnail N" alias
        └── 1.jpg

파일명 규칙
-----------
- 숫자 파일명 (1.jpg, 2.png, ...)  → 숫자 순 정렬
- 비숫자 파일명 (banner.jpg, ...)  → 숫자 파일 뒤에 알파벳 순 정렬
- 지원 확장자: .jpg, .jpeg, .png, .webp

Usage
-----
    from automator.asset_loader import AssetLoader

    loader = AssetLoader()

    # 감지된 파일 확인
    print(loader.images)     # ['assets/images/1.jpg', ...]
    print(loader.thumbnails) # ['assets/thumbnails/1.jpg']

    # 레이아웃을 직접 지정해서 ContentOption 생성
    content = loader.to_content_option(layout=[
        "Thumbnail 1",
        "Paragraph 1",
        "Paragraph 2",
        "Image 1",
        "Paragraph 3",
    ])
"""

from __future__ import annotations

from pathlib import Path

from automator.options import ContentOption

_SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_IMAGES_SUBDIR        = "images"
_THUMBNAILS_SUBDIR    = "thumbnails"


def _sort_key(path: Path) -> tuple[int, int, str]:
    """
    Sort key: numeric stem first (numerically), then non-numeric (alphabetically).
    e.g. 1.jpg < 2.jpg < 10.jpg < banner.jpg
    """
    stem = path.stem
    if stem.isdigit():
        return (0, int(stem), "")
    return (1, 0, stem.lower())


def _scan(directory: Path) -> list[str]:
    """
    Return sorted absolute path strings for supported image files in directory.
    Returns [] if directory does not exist.
    """
    if not directory.is_dir():
        return []
    files = [
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in _SUPPORTED_EXTENSIONS
    ]
    return [str(p) for p in sorted(files, key=_sort_key)]


class AssetLoader:
    """
    Scans assets/images/ and assets/thumbnails/ and builds ContentOption.

    Args:
        root: Project root directory. Defaults to current working directory.
              assets/ is resolved relative to this root.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self._root       = Path(root) if root else Path.cwd()
        self._assets_dir = self._root / "assets"
        self._images     = _scan(self._assets_dir / _IMAGES_SUBDIR)
        self._thumbnails = _scan(self._assets_dir / _THUMBNAILS_SUBDIR)

    @property
    def images(self) -> list[str]:
        """Sorted list of preview image paths."""
        return list(self._images)

    @property
    def thumbnails(self) -> list[str]:
        """Sorted list of thumbnail image paths."""
        return list(self._thumbnails)

    def to_content_option(self, layout: list[str], **kwargs) -> ContentOption:
        """
        Build a ContentOption from detected assets with an explicit layout.

        Args:
            layout:   Alias list controlling order and composition.
                      e.g. ["Image 1", "Paragraph 1", "Thumbnail 1", "Paragraph 2"]
            **kwargs: Additional keyword arguments forwarded to ContentOption
                      (e.g. paragraph_prompt, paragraph_newlines).

        Returns:
            ContentOption with preview_images, thumbnail_images, and layout populated.

        Examples:
            loader.to_content_option(layout=[
                "Image 1",
                "Paragraph 1",
                "Image 2",
                "Paragraph 2",
                "Thumbnail 1",
            ])

            loader.to_content_option(layout=[
                "Thumbnail 1",
                "Paragraph 1",
                "Paragraph 2",
                "Paragraph 3",
            ])
        """
        return ContentOption(
            preview_images   = self.images,
            thumbnail_images = self.thumbnails,
            layout           = layout,
            **kwargs,
        )
