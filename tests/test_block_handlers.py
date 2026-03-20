"""
tests/test_block_handlers.py
-----------------------------
ImageBlock / FeaturedImageBlock 의 이미지 변환 파이프라인 검증.

1. 이미지 처리 옵션이 기본값이면 process_image / process_featured 가 호출된다.
2. 변환된 임시 파일 경로가 execute() 에 전달된다.
3. FeaturedImageBlock 은 set_representative_media() 를 트리거한다.
"""

import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path

from automator.job import PostingJob
from automator.options import (
    AccountOption, TitleOption, PublishOption,
    ImageBlock, FeaturedImageBlock, Section,
)


def _account():
    return AccountOption(username="id", password="pw", meta={"blog_id": "blog"})


def _base():
    return (
        PostingJob.for_account(_account())
        .with_title(TitleOption(fixed_title="제목"))
        .with_publish(PublishOption(mode="immediate"))
    )


def _make_jpeg(tmp_path: Path) -> Path:
    from PIL import Image
    p = tmp_path / "test.jpg"
    Image.new("RGB", (100, 100), color=(128, 64, 32)).save(str(p), format="JPEG")
    return p


# ---------------------------------------------------------------------------
# process_image 호출 검증
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_image_block__process_image_called(tmp_path):
    """ImageBlock 이 있으면 process_image() 가 호출된다."""
    img    = _make_jpeg(tmp_path)
    editor = MagicMock()

    with patch("automator.image_processor.process_image",
               return_value=img.read_bytes()) as mock_proc:
        _base().with_body([Section(blocks=(
            ImageBlock(path=str(img)),
        ))]).run(editor)
        assert mock_proc.called


@pytest.mark.unit
def test_featured_block__process_featured_called(tmp_path):
    """FeaturedImageBlock 이 있으면 process_featured() 가 호출된다."""
    thumb  = _make_jpeg(tmp_path)
    editor = MagicMock()

    with patch("automator.image_processor.process_featured",
               return_value=thumb.read_bytes()) as mock_proc:
        _base().with_body([Section(blocks=(
            FeaturedImageBlock(path=str(thumb)),
        ))]).run(editor)
        assert mock_proc.called


@pytest.mark.unit
def test_processed_path_differs_from_original(tmp_path):
    """변환 후 실제 execute() 에 전달되는 경로가 원본과 다르다."""
    img    = _make_jpeg(tmp_path)
    editor = MagicMock()

    with patch("automator.image_processor.process_image",
               return_value=b"\xff\xd8\xff" + b"\x00" * 100):
        _base().with_body([Section(blocks=(
            ImageBlock(path=str(img)),
        ))]).run(editor)

    uploaded_paths = [
        c.args[0]
        for c in editor.upload_file.call_args_list
    ]
    assert any(p != str(img) for p in uploaded_paths)


@pytest.mark.unit
def test_featured_block__sets_representative_image(tmp_path):
    """FeaturedImageBlock 이 있으면 set_representative_media() 가 호출된다."""
    thumb  = _make_jpeg(tmp_path)
    editor = MagicMock()

    with patch("automator.image_processor.process_featured",
               return_value=thumb.read_bytes()):
        _base().with_body([Section(blocks=(
            FeaturedImageBlock(path=str(thumb)),
        ))]).run(editor)

    editor.set_representative_media.assert_called_once()


@pytest.mark.unit
def test_image_block_options_passed_to_processor(tmp_path):
    """ImageBlock 의 pixel_jitter / saturation_jitter 설정이 processor 로 전달된다."""
    img    = _make_jpeg(tmp_path)
    editor = MagicMock()

    block = ImageBlock(
        path=str(img),
        pixel_jitter=False,
        saturation_jitter=0.0,
        exif_description="테스트",
    )
    with patch("automator.image_processor.process_image",
               return_value=img.read_bytes()) as mock_proc:
        _base().with_body([Section(blocks=(block,))]).run(editor)

    called_block = mock_proc.call_args.args[1]
    assert called_block.pixel_jitter is False
    assert called_block.saturation_jitter == 0.0
    assert called_block.exif_description == "테스트"
