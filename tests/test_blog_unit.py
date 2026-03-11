"""
tests/test_blog_unit.py
-----------------------
Unit tests for automator.blog using mocks.
These tests run without a browser — fast and safe for CI.
"""

import pytest
from unittest.mock import MagicMock, call, patch
from pathlib import Path

from automator.blog import (
    BlogPost,
    fill_title,
    fill_body,
    click_publish,
    post_blog,
    wait_for_editor,
    session_exists,
    PLACEHOLDER_SELECTOR,
    EDITOR_IFRAME,
    WRITE_URL,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_page() -> MagicMock:
    """Return a MagicMock that mimics a Playwright Page."""
    page = MagicMock()

    # frame_locator().locator().nth().locator("..") chain
    frame = MagicMock()
    page.frame_locator.return_value = frame

    locator_chain = MagicMock()
    frame.locator.return_value = locator_chain
    locator_chain.nth.return_value = locator_chain
    locator_chain.locator.return_value = locator_chain

    return page


@pytest.fixture()
def sample_post() -> BlogPost:
    return BlogPost(title="[테스트] 자동화 제목", content="자동화 테스트 본문입니다.")


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
# Selector safety: no UUID hardcoding
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_placeholder_selector_contains_no_uuid():
    """
    Critical: PLACEHOLDER_SELECTOR must not contain a hardcoded SE-{uuid}.
    If this test fails, a UUID has been accidentally embedded in the selector.
    """
    assert "SE-" not in PLACEHOLDER_SELECTOR, (
        f"PLACEHOLDER_SELECTOR contains a UUID: {PLACEHOLDER_SELECTOR!r}"
    )


@pytest.mark.unit
def test_placeholder_selector_uses_stable_class():
    """Test that the selector targets the stable se-placeholder class."""
    assert "se-placeholder" in PLACEHOLDER_SELECTOR
    assert "__se_placeholder" in PLACEHOLDER_SELECTOR


# ---------------------------------------------------------------------------
# fill_title
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fill_title_targets_frame(mock_page: MagicMock):
    """Test that fill_title uses the correct iframe selector."""
    fill_title(mock_page, "테스트 제목")
    mock_page.frame_locator.assert_called_once_with(EDITOR_IFRAME)


@pytest.mark.unit
def test_fill_title_uses_nth_zero(mock_page: MagicMock):
    """Test that fill_title targets nth(0) — the title placeholder."""
    fill_title(mock_page, "테스트 제목")
    frame = mock_page.frame_locator.return_value
    frame.locator.return_value.nth.assert_called_with(0)


@pytest.mark.unit
def test_fill_title_navigates_to_parent(mock_page: MagicMock):
    """Test that fill_title navigates to the parent editable element."""
    fill_title(mock_page, "테스트 제목")
    frame = mock_page.frame_locator.return_value
    # After nth(0), we expect locator("..") to get the parent
    frame.locator.return_value.nth.return_value.locator.assert_called_with("..")


@pytest.mark.unit
def test_fill_title_types_given_text(mock_page: MagicMock):
    """Test that fill_title types the correct title text."""
    fill_title(mock_page, "입력할 제목")
    mock_page.keyboard.type.assert_called_once_with("입력할 제목")


# ---------------------------------------------------------------------------
# fill_body
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fill_body_targets_frame(mock_page: MagicMock):
    """Test that fill_body uses the correct iframe selector."""
    fill_body(mock_page, "본문 내용")
    mock_page.frame_locator.assert_called_with(EDITOR_IFRAME)


@pytest.mark.unit
def test_fill_body_uses_nth_one(mock_page: MagicMock):
    """Test that fill_body targets nth(1) — the body placeholder."""
    fill_body(mock_page, "본문 내용")
    frame = mock_page.frame_locator.return_value
    frame.locator.return_value.nth.assert_called_with(1)


@pytest.mark.unit
def test_fill_body_types_given_text(mock_page: MagicMock):
    """Test that fill_body types the correct content text."""
    fill_body(mock_page, "자동화 본문")
    mock_page.keyboard.type.assert_called_once_with("자동화 본문")


@pytest.mark.unit
def test_title_and_body_use_different_nth(mock_page: MagicMock):
    """
    Test that title uses nth(0) and body uses nth(1).
    If both used the same index, they would target the same element.
    """
    # Capture nth call args for title
    fill_title(mock_page, "제목")
    frame = mock_page.frame_locator.return_value
    title_nth_call = frame.locator.return_value.nth.call_args[0][0]

    # Reset mock
    mock_page.reset_mock()
    frame.locator.return_value.nth.reset_mock()

    # Capture nth call args for body
    fill_body(mock_page, "본문")
    body_nth_call = frame.locator.return_value.nth.call_args[0][0]

    assert title_nth_call != body_nth_call, (
        "Title and body must target different nth indices"
    )
    assert title_nth_call == 0
    assert body_nth_call == 1


# ---------------------------------------------------------------------------
# click_publish
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_click_publish_uses_exact_text(mock_page: MagicMock):
    """Test that publish button is located by exact text '발행'."""
    click_publish(mock_page)
    mock_page.get_by_text.assert_called_once_with("발행", exact=True)


@pytest.mark.unit
def test_click_publish_calls_click(mock_page: MagicMock):
    """Test that the publish button is actually clicked."""
    click_publish(mock_page)
    mock_page.get_by_text.return_value.click.assert_called_once()


# ---------------------------------------------------------------------------
# post_blog (integration of all steps)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_post_blog_navigates_to_write_url(mock_page: MagicMock, sample_post: BlogPost):
    """Test that post_blog navigates to the blog write URL."""
    post_blog(mock_page, sample_post)
    mock_page.goto.assert_called_once_with(WRITE_URL)


@pytest.mark.unit
def test_post_blog_calls_steps_in_order(mock_page: MagicMock, sample_post: BlogPost):
    """Test that post_blog executes goto → editor wait → title → body → publish."""
    call_order: list[str] = []

    mock_page.goto.side_effect = lambda *_: call_order.append("goto")
    mock_page.frame_locator.return_value.locator.return_value.wait_for.side_effect = (
        lambda **_: call_order.append("wait_for_editor")
    )
    mock_page.keyboard.type.side_effect = lambda text: call_order.append(
        "type_title" if text == sample_post.title else "type_body"
    )
    mock_page.get_by_text.return_value.click.side_effect = (
        lambda: call_order.append("publish")
    )

    post_blog(mock_page, sample_post)

    assert call_order[0] == "goto", "goto must be called first"
    assert "publish" in call_order, "publish must be called"


# ---------------------------------------------------------------------------
# session_exists
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_session_exists_returns_true_when_file_present(tmp_path: Path):
    """Test that session_exists returns True when the session file exists."""
    session_file = tmp_path / "session_state.json"
    session_file.write_text("{}")
    assert session_exists(session_file) is True


@pytest.mark.unit
def test_session_exists_returns_false_when_missing(tmp_path: Path):
    """Test that session_exists returns False when the session file is absent."""
    assert session_exists(tmp_path / "nonexistent.json") is False
