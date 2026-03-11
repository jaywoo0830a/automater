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
    LOGIN_URL,
    fill_title,
    fill_body,
    click_publish_trigger,
    click_publish_confirm,
    post_blog,
    wait_for_editor,
    session_exists,
    login,
    upload_image,
    set_representative_image,
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


@pytest.mark.unit
def test_image_upload_trigger_xpath_is_defined():
    """Test that IMAGE_UPLOAD_TRIGGER_XPATH is a valid xpath expression."""
    assert selectors.IMAGE_UPLOAD_TRIGGER_XPATH.startswith("xpath=")


@pytest.mark.unit
def test_uploaded_image_selector_is_defined():
    """Test that UPLOADED_IMAGE is a non-empty CSS selector."""
    assert isinstance(selectors.UPLOADED_IMAGE, str)
    assert len(selectors.UPLOADED_IMAGE) > 0


@pytest.mark.unit
def test_rep_image_button_selector_is_defined():
    """Test that REP_IMAGE_BUTTON is a non-empty CSS selector."""
    assert isinstance(selectors.REP_IMAGE_BUTTON, str)
    assert "se-set-rep-image-button" in selectors.REP_IMAGE_BUTTON


@pytest.mark.unit
def test_rep_image_selected_contains_is_selected_class():
    """Test that REP_IMAGE_BUTTON_SELECTED includes the se-is-selected class."""
    assert "se-is-selected" in selectors.REP_IMAGE_BUTTON_SELECTED


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


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_login_navigates_to_login_url(mock_page: MagicMock):
    """Test that login navigates to LOGIN_URL first."""
    login(mock_page, "test_id", "test_pw")
    mock_page.goto.assert_any_call(LOGIN_URL)


@pytest.mark.unit
def test_login_fills_id_and_pw(mock_page: MagicMock):
    """Test that login fills in the ID and password fields."""
    login(mock_page, "my_id", "my_pw")

    locator_calls = mock_page.locator.call_args_list
    id_called = any(call[0][0] == "#id" for call in locator_calls)
    pw_called = any(call[0][0] == "#pw" for call in locator_calls)
    assert id_called, "Expected locator('#id') to be called"
    assert pw_called, "Expected locator('#pw') to be called"


@pytest.mark.unit
def test_login_clicks_login_button(mock_page: MagicMock):
    """Test that login clicks the login button."""
    login(mock_page, "test_id", "test_pw")
    mock_page.get_by_text.assert_called_once_with("로그인", exact=True)
    mock_page.get_by_text.return_value.click.assert_called_once()


@pytest.mark.unit
def test_login_waits_for_navigation_away_from_login_page(mock_page: MagicMock):
    """Test that login uses wait_for_url to confirm leaving the login page."""
    login(mock_page, "test_id", "test_pw")
    mock_page.wait_for_url.assert_called_once()
    # Verify the predicate rejects nidlogin URLs
    predicate = mock_page.wait_for_url.call_args[0][0]
    assert predicate("https://www.naver.com") is True
    assert predicate("https://nid.naver.com/nidlogin.login") is False


@pytest.mark.unit
def test_login_uses_domcontentloaded_not_networkidle(mock_page: MagicMock):
    """Test that login waits for domcontentloaded, not networkidle."""
    login(mock_page, "test_id", "test_pw")
    load_state_calls = [
        call[0][0] for call in mock_page.wait_for_load_state.call_args_list
    ]
    assert all(s == "domcontentloaded" for s in load_state_calls), (
        f"Expected only 'domcontentloaded', got: {load_state_calls}"
    )


@pytest.mark.unit
def test_login_navigates_to_write_url_after_login(mock_page: MagicMock):
    """Test that login navigates to write_url after successful login."""
    mock_page.url = "https://www.naver.com"
    login(mock_page, "test_id", "test_pw")

    goto_calls = [call[0][0] for call in mock_page.goto.call_args_list]
    assert settings.write_url in goto_calls, (
        f"Expected goto({settings.write_url!r}) after login, "
        f"got calls: {goto_calls}"
    )


# ---------------------------------------------------------------------------
# upload_image
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_upload_image_targets_main_frame(mock_page: MagicMock, tmp_path: Path):
    """Test that upload_image uses MAIN_FRAME as the iframe selector."""
    img = tmp_path / "test.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0")
    upload_image(mock_page, str(img))
    mock_page.frame_locator.assert_called_with(selectors.MAIN_FRAME)


@pytest.mark.unit
def test_upload_image_uses_trigger_xpath(mock_page: MagicMock, tmp_path: Path):
    """Test that upload_image locates the trigger via IMAGE_UPLOAD_TRIGGER_XPATH."""
    img = tmp_path / "test.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0")
    upload_image(mock_page, str(img))
    mock_page.frame_locator.return_value.first.locator.assert_any_call(
        selectors.IMAGE_UPLOAD_TRIGGER_XPATH
    )


@pytest.mark.unit
def test_upload_image_uses_expect_file_chooser(mock_page: MagicMock, tmp_path: Path):
    """Test that upload_image intercepts the file chooser dialog."""
    img = tmp_path / "test.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0")
    upload_image(mock_page, str(img))
    mock_page.expect_file_chooser.assert_called_once()


@pytest.mark.unit
def test_upload_image_raises_for_missing_file(mock_page: MagicMock):
    """Test that upload_image raises FileNotFoundError for a non-existent path."""
    with pytest.raises(FileNotFoundError):
        upload_image(mock_page, "/nonexistent/image.jpg")


# ---------------------------------------------------------------------------
# set_representative_image
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_set_representative_image_targets_main_frame(mock_page: MagicMock):
    """Test that set_representative_image uses MAIN_FRAME."""
    set_representative_image(mock_page, index=0)
    mock_page.frame_locator.assert_called_with(selectors.MAIN_FRAME)


@pytest.mark.unit
def test_set_representative_image_locates_rep_buttons(mock_page: MagicMock):
    """Test that set_representative_image queries REP_IMAGE_BUTTON."""
    set_representative_image(mock_page, index=1)
    mock_page.frame_locator.return_value.first.locator.assert_any_call(
        selectors.REP_IMAGE_BUTTON
    )


@pytest.mark.unit
def test_set_representative_image_clicks_nth_button(mock_page: MagicMock):
    """Test that set_representative_image clicks the button at the given index."""
    set_representative_image(mock_page, index=1)
    nth_calls = [
        call[0][0] for call in
        mock_page.frame_locator.return_value.first.locator.return_value.nth.call_args_list
    ]
    assert 1 in nth_calls, f"Expected nth(1) in calls, got: {nth_calls}"


@pytest.mark.unit
def test_set_representative_image_raises_for_negative_index(mock_page: MagicMock):
    """Test that set_representative_image raises ValueError for negative index."""
    with pytest.raises(ValueError):
        set_representative_image(mock_page, index=-1)
