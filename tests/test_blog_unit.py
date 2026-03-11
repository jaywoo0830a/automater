"""
tests/test_blog_unit.py
-----------------------
Unit tests for automator.blog using mocks.
These tests run without a browser — fast and safe for CI.
"""

import pytest
from unittest.mock import MagicMock
from pathlib import Path

from automator.config import settings
from automator import selectors
from automator.blog import (
    BlogPost,
    fill_title,
    fill_body,
    click_publish_trigger,
    click_publish_confirm,
    post_blog,
    wait_for_editor,
    session_exists,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_page() -> MagicMock:
    """Return a MagicMock that mimics a Playwright Page."""
    page = MagicMock()

    frame = MagicMock()
    frame.first = frame
    page.frame_locator.return_value = frame

    locator = MagicMock()
    locator.first = locator
    frame.locator.return_value = locator

    return page


@pytest.fixture()
def sample_post() -> BlogPost:
    return BlogPost(
        title="[자동화 테스트] Playwright로 작성한 포스트",
        content=(
            "안녕하세요! 이 글은 Playwright 자동화 테스트로 작성된 포스트입니다.\n\n"
            "테스트 항목:\n"
            "- 제목 입력 확인\n"
            "- 본문 입력 확인\n"
            "- 발행 버튼 노출 확인\n\n"
            "테스트 완료 후 삭제 예정입니다."
        ),
    )


# ---------------------------------------------------------------------------
# BlogPost dataclass
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_blogpost_stores_title_and_content():
    """Test that BlogPost correctly stores title and content."""
    post = BlogPost(title="Hello", content="World")
    assert post.title == "Hello"
    assert post.content == "World"


@pytest.mark.unit
def test_blogpost_category_defaults_to_none():
    """Test that category is optional and defaults to None."""
    post = BlogPost(title="T", content="C")
    assert post.category is None


@pytest.mark.unit
def test_blogpost_with_category():
    """Test that BlogPost accepts an optional category."""
    post = BlogPost(title="T", content="C", category="일상")
    assert post.category == "일상"


# ---------------------------------------------------------------------------
# selectors.py — integrity checks
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_placeholder_selector_contains_no_uuid():
    """Critical: PLACEHOLDER must not contain a hardcoded SE-{uuid}."""
    assert "SE-" not in selectors.PLACEHOLDER, (
        f"PLACEHOLDER contains a UUID: {selectors.PLACEHOLDER!r}"
    )


@pytest.mark.unit
def test_placeholder_selector_uses_stable_class():
    """Test that PLACEHOLDER targets the stable se-placeholder class."""
    assert "se-placeholder" in selectors.PLACEHOLDER
    assert "__se_placeholder" in selectors.PLACEHOLDER


@pytest.mark.unit
def test_title_xpath_is_defined():
    """Test that TITLE_XPATH is a valid xpath expression."""
    assert selectors.TITLE_XPATH.startswith("xpath=")


@pytest.mark.unit
def test_body_xpath_is_defined():
    """Test that BODY_XPATH is a valid xpath expression."""
    assert selectors.BODY_XPATH.startswith("xpath=")


@pytest.mark.unit
def test_publish_trigger_xpath_is_defined():
    """Test that PUBLISH_TRIGGER_XPATH is a valid xpath expression."""
    assert selectors.PUBLISH_TRIGGER_XPATH.startswith("xpath=")


@pytest.mark.unit
def test_publish_confirm_testid_is_defined():
    """Test that PUBLISH_CONFIRM_TESTID is a non-empty string."""
    assert isinstance(selectors.PUBLISH_CONFIRM_TESTID, str)
    assert len(selectors.PUBLISH_CONFIRM_TESTID) > 0


@pytest.mark.unit
def test_title_and_body_xpath_are_different():
    """Test that TITLE_XPATH and BODY_XPATH are distinct selectors."""
    assert selectors.TITLE_XPATH != selectors.BODY_XPATH


# ---------------------------------------------------------------------------
# fill_title
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fill_title_targets_main_frame(mock_page: MagicMock):
    """Test that fill_title uses MAIN_FRAME as the iframe selector."""
    fill_title(mock_page, "테스트 제목")
    mock_page.frame_locator.assert_called_once_with(selectors.MAIN_FRAME)


@pytest.mark.unit
def test_fill_title_uses_title_xpath(mock_page: MagicMock):
    """Test that fill_title locates the element via TITLE_XPATH."""
    fill_title(mock_page, "테스트 제목")
    mock_page.frame_locator.return_value.first.locator.assert_called_with(selectors.TITLE_XPATH)


@pytest.mark.unit
def test_fill_title_types_given_text(mock_page: MagicMock):
    """Test that fill_title types the correct text via keyboard."""
    fill_title(mock_page, "입력할 제목")
    mock_page.keyboard.type.assert_called_once_with("입력할 제목")


# ---------------------------------------------------------------------------
# fill_body
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fill_body_targets_main_frame(mock_page: MagicMock):
    """Test that fill_body uses MAIN_FRAME as the iframe selector."""
    fill_body(mock_page, "본문 내용")
    mock_page.frame_locator.assert_called_with(selectors.MAIN_FRAME)


@pytest.mark.unit
def test_fill_body_uses_body_xpath(mock_page: MagicMock):
    """Test that fill_body locates the element via BODY_XPATH."""
    fill_body(mock_page, "본문 내용")
    mock_page.frame_locator.return_value.first.locator.assert_called_with(selectors.BODY_XPATH)


@pytest.mark.unit
def test_fill_body_types_given_text(mock_page: MagicMock):
    """Test that fill_body types the correct text via keyboard."""
    fill_body(mock_page, "자동화 본문")
    mock_page.keyboard.type.assert_called_once_with("자동화 본문")


@pytest.mark.unit
def test_title_and_body_use_different_xpaths(mock_page: MagicMock):
    """Test that fill_title and fill_body target different XPath selectors."""
    fill_title(mock_page, "제목")
    title_arg = mock_page.frame_locator.return_value.first.locator.call_args[0][0]

    mock_page.reset_mock()

    fill_body(mock_page, "본문")
    body_arg = mock_page.frame_locator.return_value.first.locator.call_args[0][0]

    assert title_arg != body_arg


# ---------------------------------------------------------------------------
# click_publish_trigger
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_click_publish_trigger_uses_trigger_xpath(mock_page: MagicMock):
    """Test that click_publish_trigger uses PUBLISH_TRIGGER_XPATH."""
    click_publish_trigger(mock_page)
    mock_page.frame_locator.return_value.first.locator.assert_called_with(
        selectors.PUBLISH_TRIGGER_XPATH
    )


@pytest.mark.unit
def test_click_publish_trigger_calls_click(mock_page: MagicMock):
    """Test that click_publish_trigger clicks the located element."""
    click_publish_trigger(mock_page)
    mock_page.frame_locator.return_value.first.locator.return_value.first.click.assert_called_once()


# ---------------------------------------------------------------------------
# click_publish_confirm
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_click_publish_confirm_uses_testid(mock_page: MagicMock):
    """Test that click_publish_confirm targets the element by data-testid."""
    click_publish_confirm(mock_page)
    call_arg = mock_page.frame_locator.return_value.first.locator.call_args[0][0]
    assert selectors.PUBLISH_CONFIRM_TESTID in call_arg


@pytest.mark.unit
def test_click_publish_confirm_calls_click(mock_page: MagicMock):
    """Test that click_publish_confirm clicks the located element."""
    click_publish_confirm(mock_page)
    mock_page.frame_locator.return_value.first.locator.return_value.first.click.assert_called_once()


# ---------------------------------------------------------------------------
# post_blog
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_post_blog_navigates_to_write_url(mock_page: MagicMock, sample_post: BlogPost):
    """Test that post_blog navigates to settings.write_url."""
    post_blog(mock_page, sample_post)
    mock_page.goto.assert_called_once_with(settings.write_url)


@pytest.mark.unit
def test_post_blog_goto_is_first_call(mock_page: MagicMock, sample_post: BlogPost):
    """Test that goto is the very first action in post_blog."""
    call_order: list[str] = []
    mock_page.goto.side_effect = lambda *_: call_order.append("goto")
    mock_page.keyboard.type.side_effect = lambda *_: call_order.append("type")

    post_blog(mock_page, sample_post)

    assert call_order[0] == "goto"


# ---------------------------------------------------------------------------
# session_exists
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_session_exists_returns_true_when_file_present(tmp_path: Path):
    """Test that session_exists returns True when the session file exists."""
    f = tmp_path / "session_state.json"
    f.write_text("{}")
    assert session_exists(f) is True


@pytest.mark.unit
def test_session_exists_returns_false_when_missing(tmp_path: Path):
    """Test that session_exists returns False when the session file is absent."""
    assert session_exists(tmp_path / "nonexistent.json") is False
