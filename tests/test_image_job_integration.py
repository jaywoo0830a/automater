"""
tests/test_image_job_integration.py
--------------------------------------
NaverBlogJob + ImageOption 연동 테스트.

핵심 계약
---------
1. with_image() 로 ImageOption 을 주입할 수 있다.
2. ImageOption 이 있으면 업로드 전 ImageProcessor 로 이미지를 변환한다.
3. 변환된 이미지는 임시 파일로 저장되고 그 경로가 upload_image() 에 전달된다.
4. 원본 이미지 경로가 아닌 임시 파일 경로가 upload_image() 에 전달된다.
5. ImageOption 이 없으면 원본 경로 그대로 upload_image() 에 전달된다.
6. upload_delay_ms 만큼 업로드 사이에 sleep 이 호출된다.
7. 임시 파일은 job.run() 완료 후 정리된다.
"""

import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
from PIL import Image
import io

from automator.job import NaverBlogJob
from automator.options import (
    AccountOption, TitleOption, ContentOption, MetaOption, ImageOption
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _account():
    return AccountOption(naver_id="id", naver_pw="pw", blog_id="blog")


def _solid_image_file(tmp_path, name="test.jpg", w=100, h=100) -> str:
    """단색 JPEG 파일을 tmp_path 에 생성하고 경로를 반환."""
    img = Image.new("RGB", (w, h), (180, 180, 180))
    path = tmp_path / name
    img.save(str(path), format="JPEG")
    return str(path)


def _run(layout, image_option=None, preview_images=None, thumbnail_images=None,
         tmp_path=None):
    """
    Job 을 실행하고 (editor, upload_calls, sleep_calls) 를 반환.
    """
    editor = MagicMock()
    sleep_calls = []

    with patch("automator.job.time") as mock_time:
        mock_time.sleep.side_effect = lambda s: sleep_calls.append(s)

        job = (
            NaverBlogJob
            .for_account(_account())
            .with_title(TitleOption(fixed_title="T"))
            .with_content(ContentOption(
                layout            = layout,
                preview_images    = preview_images or [],
                thumbnail_images  = thumbnail_images or [],
            ))
            .with_meta(MetaOption())
        )
        if image_option:
            job = job.with_image(image_option)
        job.run(editor)

    upload_calls = [c.args[0] for c in editor.upload_image.call_args_list]
    return editor, upload_calls, sleep_calls


# ---------------------------------------------------------------------------
# with_image() builder
# ---------------------------------------------------------------------------

class TestWithImageBuilder:

    def test_with_image_returns_new_job(self):
        job  = NaverBlogJob.for_account(_account())
        job2 = job.with_image(ImageOption())
        assert job2 is not job

    def test_with_image_does_not_mutate_original(self):
        job = NaverBlogJob.for_account(_account())
        job.with_image(ImageOption())
        assert job._image is None

    def test_with_image_stores_option(self):
        opt = ImageOption()
        job = NaverBlogJob.for_account(_account()).with_image(opt)
        assert job._image is opt


# ---------------------------------------------------------------------------
# 이미지 변환 — ImageOption 있을 때
# ---------------------------------------------------------------------------

class TestImageProcessing:

    def test_upload_path_differs_from_original(self, tmp_path):
        """변환된 임시 파일 경로가 원본 경로와 다르다."""
        src = _solid_image_file(tmp_path, "preview.jpg")
        _, upload_calls, _ = _run(
            layout          = ["Paragraph 1", "Image 1"],
            image_option    = ImageOption(pixel_jitter=True, size_jitter_px=0,
                                          upload_delay_ms=0),
            preview_images  = [src],
        )
        assert len(upload_calls) == 1
        assert upload_calls[0] != src

    def test_uploaded_file_exists_during_run(self, tmp_path):
        """upload_image() 호출 시 임시 파일이 실제로 존재한다."""
        src = _solid_image_file(tmp_path, "preview.jpg")
        paths_during_upload = []

        def capture_upload(path):
            paths_during_upload.append((path, os.path.exists(path)))

        editor = MagicMock()
        editor.upload_image.side_effect = capture_upload

        with patch("automator.job.time"):
            job = (
                NaverBlogJob.for_account(_account())
                .with_title(TitleOption(fixed_title="T"))
                .with_content(ContentOption(
                    layout         = ["Image 1"],
                    preview_images = [src],
                ))
                .with_meta(MetaOption())
                .with_image(ImageOption(pixel_jitter=True, upload_delay_ms=0))
            )
            job.run(editor)

        assert all(exists for _, exists in paths_during_upload)

    def test_thumbnail_processed_separately(self, tmp_path):
        """preview 와 thumbnail 이 각각 별도로 처리된다."""
        preview   = _solid_image_file(tmp_path, "prev.jpg")
        thumbnail = _solid_image_file(tmp_path, "thumb.jpg")

        _, upload_calls, _ = _run(
            layout           = ["Image 1", "Thumbnail 1"],
            image_option     = ImageOption(pixel_jitter=True, upload_delay_ms=0),
            preview_images   = [preview],
            thumbnail_images = [thumbnail],
        )
        assert len(upload_calls) == 2
        # 둘 다 원본과 다른 임시 경로
        assert upload_calls[0] != preview
        assert upload_calls[1] != thumbnail
        # 서로 다른 파일
        assert upload_calls[0] != upload_calls[1]


# ---------------------------------------------------------------------------
# 하위 호환 — ImageOption 없을 때
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:

    def test_no_image_option_uses_original_path(self, tmp_path):
        """ImageOption 없으면 원본 경로 그대로 upload_image() 에 전달."""
        src = _solid_image_file(tmp_path, "preview.jpg")
        _, upload_calls, _ = _run(
            layout         = ["Image 1"],
            preview_images = [src],
        )
        assert upload_calls[0] == src

    def test_no_image_option_no_sleep(self, tmp_path):
        """ImageOption 없으면 upload 간 sleep 없음."""
        src = _solid_image_file(tmp_path, "preview.jpg")
        _, _, sleep_calls = _run(
            layout         = ["Image 1", "Image 2"],
            preview_images = [src, src],
        )
        # upload_delay 관련 sleep 없음
        assert not sleep_calls


# ---------------------------------------------------------------------------
# upload_delay_ms — 업로드 간 대기
# ---------------------------------------------------------------------------

class TestUploadDelay:

    def test_sleep_called_after_each_upload(self, tmp_path):
        """이미지 2개 업로드 시 sleep 이 2번 호출된다."""
        src = _solid_image_file(tmp_path, "preview.jpg")
        delay_s = 0.5  # 500ms
        _, _, sleep_calls = _run(
            layout         = ["Image 1", "Image 2"],
            image_option   = ImageOption(
                pixel_jitter=False, size_jitter_px=0,
                upload_delay_ms=500,
            ),
            preview_images = [src, src],
        )
        assert sleep_calls.count(delay_s) == 2

    def test_sleep_not_called_when_delay_zero(self, tmp_path):
        """upload_delay_ms=0 이면 sleep 없음."""
        src = _solid_image_file(tmp_path, "preview.jpg")
        _, _, sleep_calls = _run(
            layout         = ["Image 1"],
            image_option   = ImageOption(
                pixel_jitter=False, size_jitter_px=0,
                upload_delay_ms=0,
            ),
            preview_images = [src],
        )
        assert not sleep_calls

    def test_delay_applied_to_thumbnail_too(self, tmp_path):
        """thumbnail 업로드에도 동일하게 delay 가 적용된다."""
        preview   = _solid_image_file(tmp_path, "prev.jpg")
        thumbnail = _solid_image_file(tmp_path, "thumb.jpg")
        _, _, sleep_calls = _run(
            layout           = ["Image 1", "Thumbnail 1"],
            image_option     = ImageOption(
                pixel_jitter=False, size_jitter_px=0,
                upload_delay_ms=300,
            ),
            preview_images   = [preview],
            thumbnail_images = [thumbnail],
        )
        assert sleep_calls.count(0.3) == 2
