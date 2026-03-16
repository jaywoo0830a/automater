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

    loader = AssetLoader()                     # assets/ 를 현재 디렉토리 기준으로 탐색
    loader = AssetLoader(root="my_project/")   # 루트 지정

    # 감지된 파일 확인
    print(loader.images)     # ['assets/images/1.jpg', ...]
    print(loader.thumbnails) # ['assets/thumbnails/1.jpg']

    # 레이아웃만 얻기
    layout = loader.build_layout(paragraphs=3)
    # → ['Image 1', 'Paragraph 1', 'Image 2', 'Paragraph 2', 'Image 3', 'Paragraph 3',
    #    'Thumbnail 1']

    # ContentOption 으로 바로 변환
    content = loader.to_content_option(paragraphs=3)
    # → ContentOption(
    #       preview_images=['assets/images/1.jpg', ...],
    #       thumbnail_images=['assets/thumbnails/1.jpg'],
    #       layout=[...],
    #   )
"""

from __future__ import annotations

from pathlib import Path

from automator.options import ContentOption

_SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_IMAGES_SUBDIR       = "images"
_THUMBNAILS_SUBDIR   = "thumbnails"


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

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def images(self) -> list[str]:
        """Sorted list of preview image paths."""
        return list(self._images)

    @property
    def thumbnails(self) -> list[str]:
        """Sorted list of thumbnail image paths."""
        return list(self._thumbnails)

    # ------------------------------------------------------------------
    # Layout generation
    # ------------------------------------------------------------------

    def build_layout(self, paragraphs: int = 0) -> list[str]:
        """
        Build a layout alias list from detected images.

        Layout pattern (paragraphs > 0):
            Image 1, Paragraph 1, Image 2, Paragraph 2, ..., Thumbnail 1

        If paragraphs > images, remaining paragraphs are appended at the end
        (before thumbnails).

        Args:
            paragraphs: Number of "Paragraph N" aliases to interleave.
                        0 = images only, no paragraph aliases.

        Returns:
            List of alias strings compatible with ContentOption.layout.
        """
        layout: list[str] = []

        n_images    = len(self._images)
        para_cursor = 0

        for i in range(n_images):
            layout.append(f"Image {i + 1}")
            if paragraphs > 0 and para_cursor < paragraphs:
                para_cursor += 1
                layout.append(f"Paragraph {para_cursor}")

        # Remaining paragraphs (more paragraphs than images)
        while para_cursor < paragraphs:
            para_cursor += 1
            layout.append(f"Paragraph {para_cursor}")

        # Thumbnails always last
        for i in range(len(self._thumbnails)):
            layout.append(f"Thumbnail {i + 1}")

        return layout

    # ------------------------------------------------------------------
    # ContentOption factory
    # ------------------------------------------------------------------

    def to_content_option(self, paragraphs: int = 0, **kwargs) -> ContentOption:
        """
        Build a ContentOption from detected assets.

        Args:
            paragraphs: Number of paragraph aliases to interleave in the layout.
            **kwargs:   Additional keyword arguments forwarded to ContentOption
                        (e.g. paragraph_prompt, paragraph_newlines).

        Returns:
            ContentOption with preview_images, thumbnail_images, and layout
            populated from the detected files.
        """
        return ContentOption(
            preview_images   = self.images,
            thumbnail_images = self.thumbnails,
            layout           = self.build_layout(paragraphs=paragraphs),
            **kwargs,
        )
