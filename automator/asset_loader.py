"""
automator/asset_loader.py
--------------------------
AssetLoader — assets/ 디렉토리에서 이미지를 자동 감지하고
Block 목록을 생성한다.

디렉토리 규칙
-------------
    assets/
    ├── images/       # 본문 이미지  → ImageBlock
    └── thumbnails/   # 대표 이미지  → FeaturedImageBlock

Usage
-----
    from automator.asset_loader import AssetLoader

    loader = AssetLoader()
    blocks = loader.default_blocks(prompt="강남 수학 과외 홍보", n_paragraphs=2)
    # → [ImageBlock, ImageBlock, ParagraphBlock, ParagraphBlock, FeaturedImageBlock]
"""

from __future__ import annotations

from pathlib import Path

from automator.options import Block, ImageBlock, FeaturedImageBlock, ParagraphBlock

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
    assets/images/ 와 assets/thumbnails/ 를 스캔해 Block 목록을 빌드한다.

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
        return list(self._images)

    @property
    def thumbnails(self) -> list[str]:
        return list(self._thumbnails)

    def default_blocks(self, prompt: str = "", n_paragraphs: int = 0) -> list[Block]:
        """
        이미지 → 단락들 → 대표이미지 순서의 기본 레이아웃을 반환한다.

        이미지와 썸네일이 모두 없으면 빈 리스트를 반환한다.
        ParagraphBlock 은 n_paragraphs > 0 일 때만 추가된다.

        Args:
            prompt:       각 ParagraphBlock 에 사용할 Gemini 프롬프트.
            n_paragraphs: ParagraphBlock 수. 기본값 0 — 이미지만 있는 구조.
        """
        if not self._images and not self._thumbnails:
            return []

        blocks: list[Block] = []
        for path in self._images:
            blocks.append(ImageBlock(path=path))
        for _ in range(n_paragraphs):
            blocks.append(ParagraphBlock(prompt=prompt))
        for path in self._thumbnails:
            blocks.append(FeaturedImageBlock(path=path))
        return blocks
