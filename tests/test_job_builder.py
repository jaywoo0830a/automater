"""
tests/test_job_builder.py
--------------------------
PostingJob 빌더 패턴 — 불변성과 체이닝 검증.

테스트 범위
-----------
- for_account()  진입점이 PostingJob 인스턴스를 반환한다
- with_*()       호출 후 기반 인스턴스가 변하지 않는다
- with_body()    전달한 리스트의 독립 복사본을 저장한다
- 포크 독립성    같은 base 에서 파생한 두 잡이 서로 영향받지 않는다
"""

import pytest
from automator.job import PostingJob
from automator.options import (
    AccountOption, TitleOption,
    TextBlock, ImageBlock, FeaturedBlock,
    MediaOption, PublishOption, SEOOption, RunSetting,
)


def _account():
    return AccountOption(username="id", password="pw", meta={"blog_id": "blog"})


# ---------------------------------------------------------------------------
# for_account
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_for_account__returns_posting_job_instance():
    job = PostingJob.for_account(_account())
    assert isinstance(job, PostingJob)


@pytest.mark.unit
def test_for_account__stores_account_option():
    acc = _account()
    job = PostingJob.for_account(acc)
    assert job._account is acc


# ---------------------------------------------------------------------------
# with_title
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_with_title__does_not_mutate_base_job():
    base   = PostingJob.for_account(_account())
    _      = base.with_title(TitleOption(fixed_title="A"))
    assert base._title is None


@pytest.mark.unit
def test_with_title__new_instance_has_title():
    derived = PostingJob.for_account(_account()).with_title(TitleOption(fixed_title="A"))
    assert derived._title.fixed_title == "A"


# ---------------------------------------------------------------------------
# with_body
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_with_body__stores_blocks():
    blocks = [TextBlock(prompt="p"), ImageBlock(path="img.jpg")]
    job    = PostingJob.for_account(_account()).with_body(blocks)
    assert len(job._body) == 2


@pytest.mark.unit
def test_with_body__stores_independent_copy_of_list():
    blocks = [TextBlock()]
    job    = PostingJob.for_account(_account()).with_body(blocks)
    blocks.append(ImageBlock(path="extra.jpg"))   # 원본 수정
    assert len(job._body) == 1                     # job 은 영향받지 않음


@pytest.mark.unit
def test_with_body__does_not_mutate_base_job():
    base = PostingJob.for_account(_account())
    _    = base.with_body([TextBlock()])
    assert base._body == []


# ---------------------------------------------------------------------------
# 포크 독립성
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_forked_jobs__have_independent_titles():
    base = PostingJob.for_account(_account())
    ja   = base.with_title(TitleOption(fixed_title="A"))
    jb   = base.with_title(TitleOption(fixed_title="B"))
    assert ja._title.fixed_title == "A"
    assert jb._title.fixed_title == "B"
    assert base._title is None


@pytest.mark.unit
def test_forked_jobs__have_independent_bodies():
    base = PostingJob.for_account(_account())
    ja   = base.with_body([TextBlock(prompt="for A")])
    jb   = base.with_body([ImageBlock(path="for_b.jpg"), TextBlock()])
    assert len(ja._body) == 1
    assert len(jb._body) == 2


# ---------------------------------------------------------------------------
# 나머지 with_* 메서드
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_with_seo__stored_on_new_instance():
    seo = SEOOption(keyword="kw")
    job = PostingJob.for_account(_account()).with_seo(seo)
    assert job._seo is seo


@pytest.mark.unit
def test_with_media__stored_on_new_instance():
    media = MediaOption(pixel_jitter=False)
    job   = PostingJob.for_account(_account()).with_media(media)
    assert job._media is media


@pytest.mark.unit
def test_with_publish__stored_on_new_instance():
    pub = PublishOption(mode="immediate")
    job = PostingJob.for_account(_account()).with_publish(pub)
    assert job._publish is pub


@pytest.mark.unit
def test_with_setting__stored_on_new_instance():
    setting = RunSetting(headless=False)
    job     = PostingJob.for_account(_account()).with_setting(setting)
    assert job._setting is setting
