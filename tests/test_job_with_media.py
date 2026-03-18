"""
tests/test_job_with_media.py
-----------------------------
PostingJob + MediaOption 연동 검증.

검증 항목
---------
1. MediaOption 없으면 원본 경로가 그대로 execute() 에 전달된다.
2. MediaOption 있으면 변환된 임시 파일 경로가 execute() 에 전달된다.
3. run() 완료 후 임시 파일이 정리된다 (tempfile 추적).
"""

from __future__ import annotations

import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from automator.editor import BlogEditor, ImageStep, ThumbnailStep
from automator.job import PostingJob
from automator.options import (
    AccountOption, TitleOption,
    ImageBlock, FeaturedBlock, TextBlock,
    MediaOption,
)

# 최소 유효 JPEG (SOI + EOI)
_JPEG = bytes([0xFF, 0xD8, 0xFF, 0xD9])


def _account():
    return AccountOption(username="id", password="pw", meta={"blog_id": "blog"})


def _base():
    return (PostingJob.for_account(_account())
            .with_title(TitleOption(fixed_title="T")))


# ---------------------------------------------------------------------------
# MediaOption 없을 때
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_no_media__original_image_path_passed_to_execute(tmp_path):
    img = tmp_path / "img.jpg"
    img.write_bytes(_JPEG)

    editor = MagicMock(spec=BlogEditor)
    _base().with_body([ImageBlock(str(img))]).run(editor)

    image_steps = [
        c.args[0] for c in editor.execute.call_args_list
        if isinstance(c.args[0], ImageStep)
    ]
    assert len(image_steps) == 1
    assert image_steps[0].path == str(img)


@pytest.mark.unit
def test_no_media__original_thumbnail_path_passed_to_execute(tmp_path):
    thumb = tmp_path / "thumb.jpg"
    thumb.write_bytes(_JPEG)

    editor = MagicMock(spec=BlogEditor)
    _base().with_body([FeaturedBlock(str(thumb))]).run(editor)

    thumb_steps = [
        c.args[0] for c in editor.execute.call_args_list
        if isinstance(c.args[0], ThumbnailStep)
    ]
    assert len(thumb_steps) == 1
    assert thumb_steps[0].path == str(thumb)


# ---------------------------------------------------------------------------
# MediaOption 있을 때
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_with_media__processed_path_differs_from_original(tmp_path):
    img = tmp_path / "img.jpg"
    img.write_bytes(_JPEG)

    editor   = MagicMock(spec=BlogEditor)
    captured = []
    editor.execute.side_effect = lambda s: captured.append(s)

    with patch("automator.image_processor.ImageProcessor.process_preview",
               return_value=_JPEG):
        _base() \
            .with_body([ImageBlock(str(img))]) \
            .with_media(MediaOption(upload_delay_ms=0)) \
            .run(editor)

    image_steps = [s for s in captured if isinstance(s, ImageStep)]
    assert len(image_steps) == 1
    assert image_steps[0].path != str(img)       # 임시 파일 경로로 교체됨


@pytest.mark.unit
def test_with_media__featured_image_calls_process_featured(tmp_path):
    thumb = tmp_path / "thumb.jpg"
    thumb.write_bytes(_JPEG)

    editor = MagicMock(spec=BlogEditor)

    with patch("automator.image_processor.ImageProcessor.process_featured",
               return_value=_JPEG) as mock_proc:
        _base() \
            .with_body([FeaturedBlock(str(thumb))]) \
            .with_media(MediaOption(upload_delay_ms=0)) \
            .run(editor)

    mock_proc.assert_called_once()


# ---------------------------------------------------------------------------
# 임시 파일 정리
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_tmp_files_are_cleaned_after_successful_run(tmp_path):
    """run() 완료 후 job 이 생성한 임시 파일이 모두 삭제된다."""
    img = tmp_path / "img.jpg"
    img.write_bytes(_JPEG)

    created_tmp: list[str] = []
    real_ntf = tempfile.NamedTemporaryFile

    def spy_ntf(*args, **kwargs):
        f = real_ntf(*args, **kwargs)
        created_tmp.append(f.name)
        return f

    editor = MagicMock(spec=BlogEditor)

    with patch("automator.job.tempfile.NamedTemporaryFile", spy_ntf), \
         patch("automator.image_processor.ImageProcessor.process_preview",
               return_value=_JPEG):
        _base() \
            .with_body([ImageBlock(str(img))]) \
            .with_media(MediaOption(upload_delay_ms=0)) \
            .run(editor)

    assert len(created_tmp) > 0, "임시 파일이 생성되지 않았습니다"
    for p in created_tmp:
        assert not Path(p).exists(), f"임시 파일이 정리되지 않았습니다: {p}"


@pytest.mark.unit
def test_tmp_files_are_cleaned_even_when_execute_raises(tmp_path):
    """execute() 중 예외가 발생해도 임시 파일이 정리된다."""
    img = tmp_path / "img.jpg"
    img.write_bytes(_JPEG)

    created_tmp: list[str] = []
    real_ntf = tempfile.NamedTemporaryFile

    def spy_ntf(*args, **kwargs):
        f = real_ntf(*args, **kwargs)
        created_tmp.append(f.name)
        return f

    editor = MagicMock(spec=BlogEditor)
    editor.execute.side_effect = RuntimeError("editor 오류")

    with patch("automator.job.tempfile.NamedTemporaryFile", spy_ntf), \
         patch("automator.image_processor.ImageProcessor.process_preview",
               return_value=_JPEG):
        with pytest.raises(RuntimeError):
            _base() \
                .with_body([ImageBlock(str(img))]) \
                .with_media(MediaOption(upload_delay_ms=0)) \
                .run(editor)

    for p in created_tmp:
        assert not Path(p).exists(), f"예외 발생 후에도 임시 파일이 남아있습니다: {p}"
