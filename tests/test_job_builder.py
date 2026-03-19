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
    ParagraphBlock, ImageBlock, FeaturedImageBlock, Section,
    PublishOption, RunSetting,
)


def _account():
    return AccountOption(username="id", password="pw", meta={"blog_id": "blog"})


def _section(*blocks):
    return Section(blocks=tuple(blocks))


# ---------------------------------------------------------------------------
# AccountOption.session_exists
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_session_exists__returns_false_for_missing_file():
    acc = AccountOption(username="id", password="pw", session_path="/nonexistent/path.json")
    assert acc.session_exists() is False


@pytest.mark.unit
def test_session_exists__returns_true_for_existing_file(tmp_path):
    session = tmp_path / "session.json"
    session.write_text("{}")
    acc = AccountOption(username="id", password="pw", session_path=str(session))
    assert acc.session_exists() is True


@pytest.mark.unit
def test_resolved_session_path__defaults_to_username():
    acc = AccountOption(username="myuser", password="pw")
    assert acc.resolved_session_path == "myuser_session.json"


# ---------------------------------------------------------------------------
# for_account
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_for_account__returns_posting_job_instance():
    assert isinstance(PostingJob.for_account(_account()), PostingJob)


@pytest.mark.unit
def test_for_account__stores_account_option():
    acc = _account()
    assert PostingJob.for_account(acc)._account is acc


# ---------------------------------------------------------------------------
# with_title
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_with_title__does_not_mutate_base_job():
    base = PostingJob.for_account(_account())
    _    = base.with_title(TitleOption(fixed_title="A"))
    assert base._title is None


@pytest.mark.unit
def test_with_title__new_instance_has_title():
    derived = PostingJob.for_account(_account()).with_title(TitleOption(fixed_title="A"))
    assert derived._title.fixed_title == "A"


# ---------------------------------------------------------------------------
# with_body
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_with_body__stores_sections():
    sections = [_section(ParagraphBlock(prompt="p"), ImageBlock(path="img.jpg"))]
    job      = PostingJob.for_account(_account()).with_body(sections)
    assert len(job._body) == 1
    assert len(job._body[0].blocks) == 2


@pytest.mark.unit
def test_with_body__stores_independent_copy_of_list():
    sections = [_section(ParagraphBlock())]
    job      = PostingJob.for_account(_account()).with_body(sections)
    sections.append(_section(ImageBlock(path="extra.jpg")))  # 원본 수정
    assert len(job._body) == 1                                # job 은 영향받지 않음


@pytest.mark.unit
def test_with_body__does_not_mutate_base_job():
    base = PostingJob.for_account(_account())
    _    = base.with_body([_section(ParagraphBlock())])
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
    ja   = base.with_body([_section(ParagraphBlock(prompt="for A"))])
    jb   = base.with_body([
        _section(ImageBlock(path="for_b.jpg")),
        _section(ParagraphBlock()),
    ])
    assert len(ja._body) == 1
    assert len(jb._body) == 2


# ---------------------------------------------------------------------------
# 나머지 with_* 메서드
# ---------------------------------------------------------------------------


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
