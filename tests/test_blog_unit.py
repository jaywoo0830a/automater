"""
tests/test_blog_unit.py
-----------------------
Unit tests for automator.blog — JSON 기반 셀렉터 아키텍처.

selectors.py 상수 대신 SelectorLoader로 JSON을 읽어
Playwright locator를 생성하는 구조를 검증합니다.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from automator.config import settings
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
    EDITOR_CONTENT,
    MAIN_FRAME,
    UPLOADED_IMAGE,
    IMAGE_COMPONENT,
    REP_IMAGE_BUTTON,
    REP_IMAGE_BUTTON_SELECTED,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_page() -> MagicMock:
    page = MagicMock()
    frame = MagicMock()
    frame.first = frame
    page.frame_locator.return_value = frame
    locator = MagicMock()
    locator.first = locator
    frame.locator.return_value = locator
    frame.get_by_text.return_value = locator
    frame.get_by_test_id.return_value = locator
    page.locator.return_value = locator
    page.get_by_text.return_value = locator
    return page


@pytest.fixture
def login_json(tmp_path: Path) -> Path:
    data = {
        "naver_login_id":     {"primary": "page.locator('#id').first",          "selectors": [{"label": "css",  "pw": "page.locator('#id').first",          "score": 0.81}]},
        "naver_login_pw":     {"primary": "page.locator('#pw').first",          "selectors": [{"label": "css",  "pw": "page.locator('#pw').first",          "score": 0.81}]},
        "naver_login_submit": {"primary": "page.get_by_text('로그인', exact=True)", "selectors": [{"label": "text", "pw": "page.get_by_text('로그인', exact=True)", "score": 0.42}]},
    }
    f = tmp_path / "login.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    return f


@pytest.fixture
def editor_json(tmp_path: Path) -> Path:
    data = {
        "editor_title":    {"primary": "page.get_by_text('제목', exact=True)",        "selectors": [{"label": "text",   "pw": "page.get_by_text('제목', exact=True)",        "score": 0.42}]},
        "editor_body":     {"primary": "page.get_by_text('본문', exact=True)",        "selectors": [{"label": "text",   "pw": "page.get_by_text('본문', exact=True)",        "score": 0.42}]},
        "image_trigger":   {"primary": "page.get_by_text('사진사진 추가', exact=True)", "selectors": [{"label": "text",   "pw": "page.get_by_text('사진사진 추가', exact=True)", "score": 0.42}]},
        "publish_trigger": {"primary": "page.get_by_text('발행', exact=True)",        "selectors": [{"label": "text",   "pw": "page.get_by_text('발행', exact=True)",        "score": 0.42}]},
        "publish_confirm": {"primary": "page.get_by_test_id('seOnePublishBtn')",      "selectors": [{"label": "testid", "pw": "page.get_by_test_id('seOnePublishBtn')",      "score": 0.65}]},
        "selected":        {"primary": "page.get_by_text('대표', exact=True)",        "selectors": [{"label": "text",   "pw": "page.get_by_text('대표', exact=True)",        "score": 0.42}]},
        "non_selected":    {"primary": "page.get_by_text('대표', exact=True)",        "selectors": [{"label": "text",   "pw": "page.get_by_text('대표', exact=True)",        "score": 0.42}]},
        "recovery_no":     {"primary": "page.get_by_text('취소', exact=True)",        "selectors": [{"label": "text",   "pw": "page.get_by_text('취소', exact=True)",        "score": 0.42}]},
        "library_close":   {"primary": "page.get_by_text('팝업 닫기', exact=True)",   "selectors": [{"label": "text",   "pw": "page.get_by_text('팝업 닫기', exact=True)",   "score": 0.42}]},
    }
    f = tmp_path / "editor.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    return f


@pytest.fixture
def sample_post() -> BlogPost:
    return BlogPost(title="테스트 제목", content="테스트 본문")


# ---------------------------------------------------------------------------
# BlogPost dataclass
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# selectors.py 제거 확인 — 상수가 blog.py 안에 남아있어서는 안 됨
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_selectors_module_does_not_exist():
    """automator/selectors.py가 완전히 제거되었는지 확인."""
    import importlib, importlib.util
    spec = importlib.util.find_spec("automator.selectors")
    assert spec is None, "automator.selectors 모듈이 아직 존재합니다 — 삭제해야 합니다"


# ---------------------------------------------------------------------------
# blog.py 내 DOM 상수 (selectors.py가 아닌 blog.py에서 직접 관리)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_main_frame_constant_defined():
    assert isinstance(MAIN_FRAME, str) and len(MAIN_FRAME) > 0


@pytest.mark.unit
def test_editor_content_constant_defined():
    assert isinstance(EDITOR_CONTENT, str) and len(EDITOR_CONTENT) > 0


@pytest.mark.unit
def test_uploaded_image_constant_defined():
    assert isinstance(UPLOADED_IMAGE, str) and len(UPLOADED_IMAGE) > 0


@pytest.mark.unit
def test_rep_image_button_constants_defined():
    """REP_IMAGE_BUTTON 상수는 e2e 테스트의 DOM 구조 검증에 사용된다."""
    assert "se-set-rep-image-button" in REP_IMAGE_BUTTON
    assert "se-is-selected"          in REP_IMAGE_BUTTON_SELECTED


# ---------------------------------------------------------------------------
# wait_for_editor — 복구 팝업 처리
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_wait_for_editor_dismisses_recovery_popup(mock_page):
    """복구 팝업이 나타나면 se-popup-button-cancel 버튼을 클릭해 닫는다."""
    from automator.blog import wait_for_editor

    # _editor_frame() probes: 1st call uses .locator(EDITOR_CONTENT).wait_for → success
    # then frame_locator is called again for the popup poll loop
    # We return the same frame mock for all calls to simplify.
    frame    = MagicMock()
    frame.first = frame

    editor_loc = MagicMock()
    editor_loc.wait_for.return_value = None

    popup_btn = MagicMock()
    popup_btn.first = popup_btn
    popup_btn.wait_for.return_value = None   # popup visible on first probe

    # locator() returns editor_loc for EDITOR_CONTENT, popup_btn for cancel button
    def locator_side_effect(selector):
        if selector == "button.se-popup-button-cancel":
            return popup_btn
        return editor_loc

    frame.locator.side_effect = locator_side_effect
    mock_page.frame_locator.return_value = frame

    wait_for_editor(mock_page)

    frame.locator.assert_any_call("button.se-popup-button-cancel")
    popup_btn.click.assert_called()


@pytest.mark.unit
def test_wait_for_editor_continues_when_no_popup(mock_page):
    """복구 팝업이 없으면 예외 없이 정상 진행된다."""
    from automator.blog import wait_for_editor
    import automator.blog as blog_module

    frame    = MagicMock()
    frame.first = frame

    editor_loc = MagicMock()
    editor_loc.wait_for.return_value = None

    popup_btn = MagicMock()
    popup_btn.first = popup_btn
    popup_btn.wait_for.side_effect = Exception("timeout")   # never appears

    def locator_side_effect(selector):
        if selector == "button.se-popup-button-cancel":
            return popup_btn
        return editor_loc

    frame.locator.side_effect = locator_side_effect
    mock_page.frame_locator.return_value = frame

    # Patch the poll window to near-zero so the test doesn't actually wait 5s
    original = blog_module.__dict__.copy()
    with patch("time.monotonic", side_effect=[0.0, 0.0, 999.0]):
        wait_for_editor(mock_page)   # must not raise


# ---------------------------------------------------------------------------
# fill_title / fill_body — frame + get_by_text 기반
# ---------------------------------------------------------------------------

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
def test_title_and_body_call_different_selectors(mock_page, editor_json):
    fill_title(mock_page, "제목", editor_json)
    title_call = mock_page.frame_locator.return_value.first.get_by_text.call_args

    mock_page.reset_mock()

    fill_body(mock_page, "본문", editor_json)
    body_call = mock_page.frame_locator.return_value.first.get_by_text.call_args

    assert title_call != body_call


# ---------------------------------------------------------------------------
# click_publish_trigger / click_publish_confirm
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_click_publish_trigger_uses_frame(mock_page, editor_json):
    click_publish_trigger(mock_page, editor_json)
    mock_page.frame_locator.assert_called_with(MAIN_FRAME)


@pytest.mark.unit
def test_click_publish_trigger_calls_click(mock_page, editor_json):
    click_publish_trigger(mock_page, editor_json)
    mock_page.frame_locator.return_value.first.get_by_text.return_value.click.assert_called_once()


@pytest.mark.unit
def test_click_publish_confirm_uses_testid(mock_page, editor_json):
    click_publish_confirm(mock_page, editor_json)
    mock_page.frame_locator.return_value.first.get_by_test_id.assert_called_once_with("seOnePublishBtn")


@pytest.mark.unit
def test_click_publish_confirm_calls_click(mock_page, editor_json):
    click_publish_confirm(mock_page, editor_json)
    mock_page.frame_locator.return_value.first.get_by_test_id.return_value.click.assert_called_once()


# ---------------------------------------------------------------------------
# post_blog
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# session_exists
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_session_exists_true(tmp_path):
    f = tmp_path / "s.json"
    f.write_text("{}")
    assert session_exists(f) is True


@pytest.mark.unit
def test_session_exists_false(tmp_path):
    assert session_exists(tmp_path / "nope.json") is False


# ---------------------------------------------------------------------------
# login — JSON 기반
# ---------------------------------------------------------------------------

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
def test_login_waits_for_url_away_from_login(mock_page, login_json):
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


# ---------------------------------------------------------------------------
# upload_image
# ---------------------------------------------------------------------------

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
    lib_btn.wait_for.return_value = None   # library popup appears

    def get_by_text_dispatch(text, **kwargs):
        if text == "팝업 닫기":
            return lib_btn
        return MagicMock()

    frame.get_by_text.side_effect = get_by_text_dispatch

    upload_image(mock_page, str(img), editor_json)
    lib_btn.click.assert_called()


@pytest.mark.unit
def test_upload_image_proceeds_when_no_library_popup(mock_page, editor_json, tmp_path):
    """라이브러리 팝업이 없어도 정상 진행된다."""
    img = tmp_path / "t.jpg"; img.write_bytes(b"\xff\xd8")
    # Default mock: wait_for raises → treated as absent, should not raise
    upload_image(mock_page, str(img), editor_json)


@pytest.mark.unit
def test_upload_image_raises_for_missing_file(mock_page, editor_json):
    with pytest.raises(FileNotFoundError):
        upload_image(mock_page, "/no/such/file.jpg", editor_json)


# ---------------------------------------------------------------------------
# set_representative_image — JS dispatchEvent 기반
# ---------------------------------------------------------------------------

def _make_page_with_editor_frame(evaluate_return="selected"):
    """set_representative_image() 테스트용 mock_page 헬퍼."""
    page = MagicMock()
    frame = MagicMock(); frame.first = frame
    page.frame_locator.return_value = frame

    editor_frame = MagicMock()
    editor_frame.evaluate.return_value = evaluate_return
    page.main_frame = MagicMock()
    page.frames = [page.main_frame, editor_frame]
    return page, editor_frame


@pytest.mark.unit
def test_set_rep_image_targets_main_frame():
    """set_representative_image()가 MAIN_FRAME iframe을 사용하는지 확인."""
    page, _ = _make_page_with_editor_frame()
    set_representative_image(page, index=0)
    page.frame_locator.assert_called_with(MAIN_FRAME)


@pytest.mark.unit
def test_set_rep_image_uses_js_dispatch():
    """set_representative_image()가 JavaScript dispatchEvent로 버튼을 클릭한다."""
    page, editor_frame = _make_page_with_editor_frame()

    set_representative_image(page, index=1)

    editor_frame.evaluate.assert_called_once()
    # JS 코드는 첫 번째 인자, 셀렉터+인덱스 배열은 두 번째 인자로 전달됨
    js_code, js_args = editor_frame.evaluate.call_args[0]
    assert "dispatchEvent" in js_code
    assert js_args == [REP_IMAGE_BUTTON, 1]


@pytest.mark.unit
def test_set_rep_image_raises_on_js_not_selected():
    """JS click이 se-is-selected를 반환하지 않으면 RuntimeError를 발생시킨다."""
    page, _ = _make_page_with_editor_frame(evaluate_return="not-selected")
    with pytest.raises(RuntimeError):
        set_representative_image(page, index=0)


@pytest.mark.unit
def test_set_rep_image_raises_for_negative_index(mock_page):
    """음수 index는 ValueError를 발생시켜야 한다."""
    with pytest.raises(ValueError):
        set_representative_image(mock_page, index=-1)
