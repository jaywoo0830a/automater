"""
tests/test_blog_unit.py
-----------------------
Unit tests for automator.blog.

Tests are grouped by function and verify observable behaviour:
- correct Playwright calls are made
- correct arguments are passed
- edge cases raise the right exceptions

Implementation details (internal call order within helpers) are NOT tested.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from automator.config import settings
from automator.blog import (
    BlogPost,
    LOGIN_URL,
    EDITOR_CONTENT,
    MAIN_FRAME,
    UPLOADED_IMAGE,
    IMAGE_COMPONENT,
    REP_IMAGE_BUTTON,
    REP_IMAGE_BUTTON_SELECTED,
    click_publish_confirm,
    click_publish_trigger,
    fill_body,
    fill_title,
    login,
    post_blog,
    session_exists,
    set_representative_image,
    upload_image,
    wait_for_editor,
)


# ===========================================================================
# Fixtures
# ===========================================================================

def _make_frame():
    """Return a frame mock whose locators never raise by default."""
    frame = MagicMock()
    frame.first = frame
    locator = MagicMock()
    locator.first = locator
    frame.locator.return_value     = locator
    frame.get_by_text.return_value = locator
    frame.get_by_test_id.return_value = locator
    return frame, locator


@pytest.fixture
def mock_page() -> MagicMock:
    """
    Page mock where frame_locator('#mainFrame') succeeds so _editor_frame()
    always returns frame_locator.first (iframe path).
    """
    page = MagicMock()
    frame, locator = _make_frame()
    page.frame_locator.return_value = frame
    page.locator.return_value       = locator
    page.get_by_text.return_value   = locator
    page.get_by_test_id.return_value = locator
    return page


@pytest.fixture
def login_json(tmp_path: Path) -> Path:
    data = {
        "naver_login_id": {
            "primary": "page.locator('#id').first",
            "selectors": [{"label": "css", "pw": "page.locator('#id').first", "score": 0.81}],
        },
        "naver_login_pw": {
            "primary": "page.locator('#pw').first",
            "selectors": [{"label": "css", "pw": "page.locator('#pw').first", "score": 0.81}],
        },
        "naver_login_submit": {
            "primary": "page.get_by_text('로그인', exact=True)",
            "selectors": [{"label": "text", "pw": "page.get_by_text('로그인', exact=True)", "score": 0.42}],
        },
    }
    p = tmp_path / "login.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def editor_json(tmp_path: Path) -> Path:
    data = {
        "editor_title":    {"primary": "page.get_by_text('제목', exact=True)",         "selectors": [{"label": "text",   "pw": "page.get_by_text('제목', exact=True)",         "score": 0.42}]},
        "editor_body":     {"primary": "page.get_by_text('본문', exact=True)",         "selectors": [{"label": "text",   "pw": "page.get_by_text('본문', exact=True)",         "score": 0.42}]},
        "image_trigger":   {"primary": "page.get_by_text('사진사진 추가', exact=True)", "selectors": [{"label": "text",   "pw": "page.get_by_text('사진사진 추가', exact=True)", "score": 0.42}]},
        "publish_trigger": {"primary": "page.get_by_text('발행', exact=True)",         "selectors": [{"label": "text",   "pw": "page.get_by_text('발행', exact=True)",         "score": 0.42}]},
        "publish_confirm": {"primary": "page.get_by_test_id('seOnePublishBtn')",       "selectors": [{"label": "testid", "pw": "page.get_by_test_id('seOnePublishBtn')",       "score": 0.65}]},
        "selected":        {"primary": "page.get_by_text('대표', exact=True)",         "selectors": [{"label": "text",   "pw": "page.get_by_text('대표', exact=True)",         "score": 0.42}]},
        "non_selected":    {"primary": "page.get_by_text('대표', exact=True)",         "selectors": [{"label": "text",   "pw": "page.get_by_text('대표', exact=True)",         "score": 0.42}]},
        "recovery_no":     {"primary": "page.get_by_text('취소', exact=True)",         "selectors": [{"label": "text",   "pw": "page.get_by_text('취소', exact=True)",         "score": 0.42}]},
        "library_close":   {"primary": "page.get_by_text('팝업 닫기', exact=True)",    "selectors": [{"label": "text",   "pw": "page.get_by_text('팝업 닫기', exact=True)",    "score": 0.42}]},
    }
    p = tmp_path / "editor.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def sample_post() -> BlogPost:
    return BlogPost(title="테스트 제목", content="테스트 본문")


def _page_for_wait_for_editor(popup_visible=False, help_visible=False):
    """
    Build a mock_page configured for wait_for_editor() tests.

    popup_visible : recovery popup cancel button appears
    help_visible  : help panel close button appears
    """
    page = MagicMock()
    frame = MagicMock(); frame.first = frame

    editor_loc = MagicMock(); editor_loc.wait_for.return_value = None

    popup_btn = MagicMock(); popup_btn.first = popup_btn
    if popup_visible:
        popup_btn.wait_for.return_value = None
    else:
        popup_btn.wait_for.side_effect = Exception("no popup")

    help_btn = MagicMock(); help_btn.first = help_btn
    if help_visible:
        help_btn.wait_for.return_value = None
    else:
        help_btn.wait_for.side_effect = Exception("no help panel")

    def route(selector):
        if selector == "button.se-popup-button-cancel":    return popup_btn
        if selector == "button.se-help-panel-close-button": return help_btn
        return editor_loc

    frame.locator.side_effect = route
    page.frame_locator.return_value = frame
    return page, frame, popup_btn, help_btn


def _make_page_with_editor_frame(evaluate_return="selected"):
    """Build a mock_page for set_representative_image() tests."""
    page = MagicMock()
    frame = MagicMock(); frame.first = frame
    page.frame_locator.return_value = frame

    editor_frame = MagicMock()
    editor_frame.evaluate.return_value = evaluate_return
    page.main_frame = MagicMock()
    page.frames = [page.main_frame, editor_frame]
    return page, editor_frame


# ===========================================================================
# BlogPost dataclass
# ===========================================================================

@pytest.mark.unit
def test_blogpost_stores_title_and_content():
    post = BlogPost(title="Hello", content="World")
    assert post.title == "Hello"
    assert post.content == "World"


@pytest.mark.unit
def test_blogpost_category_defaults_to_none():
    assert BlogPost(title="T", content="C").category is None


@pytest.mark.unit
def test_blogpost_with_category():
    assert BlogPost(title="T", content="C", category="일상").category == "일상"


# ===========================================================================
# Architecture: selectors.py must not exist
# ===========================================================================

@pytest.mark.unit
def test_selectors_module_does_not_exist():
    """automator/selectors.py가 완전히 제거되었는지 확인."""
    import importlib.util
    assert importlib.util.find_spec("automator.selectors") is None, \
        "automator.selectors 모듈이 아직 존재합니다 — 삭제해야 합니다"


# ===========================================================================
# Constants defined in blog.py
# ===========================================================================

@pytest.mark.unit
def test_main_frame_constant_defined():
    assert isinstance(MAIN_FRAME, str) and MAIN_FRAME

@pytest.mark.unit
def test_editor_content_constant_defined():
    assert isinstance(EDITOR_CONTENT, str) and EDITOR_CONTENT

@pytest.mark.unit
def test_uploaded_image_constant_defined():
    assert isinstance(UPLOADED_IMAGE, str) and UPLOADED_IMAGE

@pytest.mark.unit
def test_rep_image_button_constants_defined():
    assert "se-set-rep-image-button" in REP_IMAGE_BUTTON
    assert "se-is-selected"          in REP_IMAGE_BUTTON_SELECTED


# ===========================================================================
# wait_for_editor
# ===========================================================================

@pytest.mark.unit
def test_wait_for_editor_dismisses_recovery_popup():
    """복구 팝업이 나타나면 cancel 버튼을 클릭해 닫는다."""
    page, frame, popup_btn, _ = _page_for_wait_for_editor(popup_visible=True)
    with patch("time.monotonic", side_effect=[0.0, 0.0, 999.0]):
        wait_for_editor(page)
    frame.locator.assert_any_call("button.se-popup-button-cancel")
    popup_btn.click.assert_called()


@pytest.mark.unit
def test_wait_for_editor_continues_when_no_popup():
    """복구 팝업이 없으면 예외 없이 정상 진행된다."""
    page, _, _, _ = _page_for_wait_for_editor(popup_visible=False)
    with patch("time.monotonic", side_effect=[0.0, 0.0, 999.0]):
        wait_for_editor(page)   # must not raise


@pytest.mark.unit
def test_wait_for_editor_dismisses_help_panel():
    """도움말 패널이 열려있으면 close 버튼을 클릭해 닫는다."""
    page, frame, _, help_btn = _page_for_wait_for_editor(help_visible=True)
    with patch("time.monotonic", side_effect=[0.0, 0.0, 999.0]):
        wait_for_editor(page)
    frame.locator.assert_any_call("button.se-help-panel-close-button")
    help_btn.click.assert_called_once()


@pytest.mark.unit
def test_wait_for_editor_continues_when_no_help_panel():
    """도움말 패널이 없으면 예외 없이 정상 진행된다."""
    page, _, _, _ = _page_for_wait_for_editor(help_visible=False)
    with patch("time.monotonic", side_effect=[0.0, 0.0, 999.0]):
        wait_for_editor(page)   # must not raise


# ===========================================================================
# fill_title / fill_body
# ===========================================================================

@pytest.mark.unit
def test_fill_title_uses_frame_locator(mock_page, editor_json):
    fill_title(mock_page, "제목", editor_json)
    mock_page.frame_locator.assert_called_with(MAIN_FRAME)


@pytest.mark.unit
def test_fill_title_types_text(mock_page, editor_json):
    fill_title(mock_page, "입력할 제목", editor_json)
    mock_page.keyboard.type.assert_called_once_with("입력할 제목")


@pytest.mark.unit
def test_fill_body_uses_frame_locator(mock_page, editor_json):
    fill_body(mock_page, "본문", editor_json)
    mock_page.frame_locator.assert_called_with(MAIN_FRAME)


@pytest.mark.unit
def test_fill_body_types_text(mock_page, editor_json):
    fill_body(mock_page, "자동화 본문", editor_json)
    mock_page.keyboard.type.assert_called_once_with("자동화 본문")


@pytest.mark.unit
def test_title_and_body_use_different_selectors(mock_page, editor_json):
    """fill_title과 fill_body는 서로 다른 get_by_text 셀렉터를 사용한다."""
    fill_title(mock_page, "제목", editor_json)
    title_call = mock_page.frame_locator.return_value.first.get_by_text.call_args

    mock_page.reset_mock()

    fill_body(mock_page, "본문", editor_json)
    body_call = mock_page.frame_locator.return_value.first.get_by_text.call_args

    assert title_call != body_call


# ===========================================================================
# click_publish_trigger / click_publish_confirm
#
# 발행 버튼과 확인 버튼은 iframe 바깥 page 레벨 toolbar에 있다.
# 구현은 page를 먼저 시도하고 실패하면 iframe fallback을 사용한다.
# ===========================================================================

@pytest.mark.unit
def test_click_publish_trigger_tries_page_level_first(mock_page, editor_json):
    """publish_trigger를 page 레벨에서 먼저 찾는다."""
    click_publish_trigger(mock_page, editor_json)
    mock_page.get_by_text.assert_called_with("발행", exact=True)


@pytest.mark.unit
def test_click_publish_trigger_clicks_when_found(mock_page, editor_json):
    """page 레벨에서 발견되면 click()을 호출한다."""
    click_publish_trigger(mock_page, editor_json)
    mock_page.get_by_text.return_value.click.assert_called_once()


@pytest.mark.unit
def test_click_publish_trigger_falls_back_to_iframe(editor_json):
    """page 레벨 locator가 실패하면 iframe fallback을 사용한다.

    mock_page fixture를 사용하지 않는다 — fixture의 locator mock이 공유되면
    _editor_frame() 내부의 frame.locator().wait_for()도 함께 실패해
    iframe fallback 자체가 동작하지 않기 때문이다.
    """
    page = MagicMock()

    # frame: _editor_frame() 탐색과 iframe fallback 모두 성공해야 함
    frame = MagicMock(); frame.first = frame
    frame_loc = MagicMock(); frame_loc.first = frame_loc
    frame.locator.return_value = frame_loc          # _editor_frame() probe → success
    frame.get_by_text.return_value = frame_loc      # iframe fallback locator

    page.frame_locator.return_value = frame

    # page-level locator: wait_for raises → page level 실패
    page_loc = MagicMock(); page_loc.first = page_loc
    page_loc.wait_for.side_effect = Exception("not found on page")
    page.get_by_text.return_value = page_loc

    click_publish_trigger(page, editor_json)

    page.frame_locator.assert_called_with(MAIN_FRAME)
    frame.get_by_text.return_value.click.assert_called()


@pytest.mark.unit
def test_click_publish_confirm_tries_page_level_first(mock_page, editor_json):
    """publish_confirm을 page 레벨에서 먼저 찾는다."""
    click_publish_confirm(mock_page, editor_json)
    mock_page.get_by_test_id.assert_called_with("seOnePublishBtn")


@pytest.mark.unit
def test_click_publish_confirm_clicks_when_found(mock_page, editor_json):
    """page 레벨에서 발견되면 click()을 호출한다."""
    click_publish_confirm(mock_page, editor_json)
    mock_page.get_by_test_id.return_value.click.assert_called_once()


@pytest.mark.unit
def test_click_publish_confirm_falls_back_to_iframe(editor_json):
    """page 레벨 locator가 실패하면 iframe fallback을 사용한다."""
    page = MagicMock()

    frame = MagicMock(); frame.first = frame
    frame_loc = MagicMock(); frame_loc.first = frame_loc
    frame.locator.return_value = frame_loc
    frame.get_by_test_id.return_value = frame_loc

    page.frame_locator.return_value = frame

    page_loc = MagicMock(); page_loc.first = page_loc
    page_loc.wait_for.side_effect = Exception("not found on page")
    page.get_by_test_id.return_value = page_loc

    click_publish_confirm(page, editor_json)

    page.frame_locator.assert_called_with(MAIN_FRAME)
    frame.get_by_test_id.return_value.click.assert_called()


# ===========================================================================
# post_blog
# ===========================================================================

@pytest.mark.unit
def test_post_blog_navigates_to_write_url(mock_page, editor_json, sample_post):
    post_blog(mock_page, sample_post, editor_json)
    mock_page.goto.assert_called_once_with(settings.write_url)


@pytest.mark.unit
def test_post_blog_goto_is_first_call(mock_page, editor_json, sample_post):
    order = []
    mock_page.goto.side_effect          = lambda *_: order.append("goto")
    mock_page.keyboard.type.side_effect = lambda *_: order.append("type")
    post_blog(mock_page, sample_post, editor_json)
    assert order[0] == "goto"


# ===========================================================================
# session_exists
# ===========================================================================

@pytest.mark.unit
def test_session_exists_true(tmp_path):
    f = tmp_path / "s.json"; f.write_text("{}")
    assert session_exists(f) is True


@pytest.mark.unit
def test_session_exists_false(tmp_path):
    assert session_exists(tmp_path / "nope.json") is False


# ===========================================================================
# login
# ===========================================================================

@pytest.mark.unit
def test_login_navigates_to_login_url(mock_page, login_json):
    login(mock_page, "id", "pw", login_json)
    mock_page.goto.assert_any_call(LOGIN_URL)


@pytest.mark.unit
def test_login_fills_id_field(mock_page, login_json):
    login(mock_page, "my_id", "my_pw", login_json)
    mock_page.locator.assert_any_call("#id")


@pytest.mark.unit
def test_login_fills_pw_field(mock_page, login_json):
    login(mock_page, "my_id", "my_pw", login_json)
    mock_page.locator.assert_any_call("#pw")


@pytest.mark.unit
def test_login_clicks_submit(mock_page, login_json):
    login(mock_page, "my_id", "my_pw", login_json)
    mock_page.get_by_text.assert_called_with("로그인", exact=True)
    mock_page.get_by_text.return_value.click.assert_called()


@pytest.mark.unit
def test_login_waits_for_redirect_away_from_login(mock_page, login_json):
    login(mock_page, "id", "pw", login_json)
    mock_page.wait_for_url.assert_called_once()
    pred = mock_page.wait_for_url.call_args[0][0]
    assert pred("https://www.naver.com") is True
    assert pred("https://nid.naver.com/nidlogin.login") is False


@pytest.mark.unit
def test_login_uses_domcontentloaded(mock_page, login_json):
    login(mock_page, "id", "pw", login_json)
    states = [c[0][0] for c in mock_page.wait_for_load_state.call_args_list]
    assert all(s == "domcontentloaded" for s in states)


@pytest.mark.unit
def test_login_navigates_to_write_url_after(mock_page, login_json):
    login(mock_page, "id", "pw", login_json)
    urls = [c[0][0] for c in mock_page.goto.call_args_list]
    assert settings.write_url in urls


# ===========================================================================
# upload_image
# ===========================================================================

@pytest.mark.unit
def test_upload_image_targets_main_frame(mock_page, editor_json, tmp_path):
    img = tmp_path / "t.jpg"; img.write_bytes(b"\xff\xd8")
    upload_image(mock_page, str(img), editor_json)
    mock_page.frame_locator.assert_called_with(MAIN_FRAME)


@pytest.mark.unit
def test_upload_image_closes_library_popup_if_open(mock_page, editor_json, tmp_path):
    """파일 선택 후 라이브러리 팝업이 열리면 자동으로 닫는다."""
    img = tmp_path / "t.jpg"; img.write_bytes(b"\xff\xd8")

    frame   = mock_page.frame_locator.return_value.first
    lib_btn = MagicMock(); lib_btn.first = lib_btn
    lib_btn.wait_for.return_value = None

    def get_by_text_dispatch(text, **kwargs):
        return lib_btn if text == "팝업 닫기" else MagicMock()

    frame.get_by_text.side_effect = get_by_text_dispatch
    upload_image(mock_page, str(img), editor_json)
    lib_btn.click.assert_called()


@pytest.mark.unit
def test_upload_image_proceeds_when_no_library_popup(mock_page, editor_json, tmp_path):
    """라이브러리 팝업이 없어도 정상 진행된다."""
    img = tmp_path / "t.jpg"; img.write_bytes(b"\xff\xd8")
    upload_image(mock_page, str(img), editor_json)   # must not raise


@pytest.mark.unit
def test_upload_image_raises_for_missing_file(mock_page, editor_json):
    with pytest.raises(FileNotFoundError):
        upload_image(mock_page, "/no/such/file.jpg", editor_json)


# ===========================================================================
# set_representative_image
# ===========================================================================

@pytest.mark.unit
def test_set_rep_image_targets_main_frame():
    """_editor_frame()이 MAIN_FRAME iframe을 조회한다."""
    page, _ = _make_page_with_editor_frame()
    set_representative_image(page, index=0)
    page.frame_locator.assert_called_with(MAIN_FRAME)


@pytest.mark.unit
def test_set_rep_image_uses_js_dispatch():
    """JavaScript dispatchEvent로 nth 버튼을 클릭한다."""
    page, editor_frame = _make_page_with_editor_frame()
    set_representative_image(page, index=1)

    editor_frame.evaluate.assert_called_once()
    js_code, js_args = editor_frame.evaluate.call_args[0]
    assert "dispatchEvent" in js_code
    assert js_args == [REP_IMAGE_BUTTON, 1]


@pytest.mark.unit
def test_set_rep_image_raises_when_js_returns_not_selected():
    """JS가 'not-selected'를 반환하면 RuntimeError를 발생시킨다."""
    page, _ = _make_page_with_editor_frame(evaluate_return="not-selected")
    with pytest.raises(RuntimeError):
        set_representative_image(page, index=0)


@pytest.mark.unit
def test_set_rep_image_raises_for_negative_index(mock_page):
    """음수 index는 ValueError를 발생시킨다."""
    with pytest.raises(ValueError):
        set_representative_image(mock_page, index=-1)
