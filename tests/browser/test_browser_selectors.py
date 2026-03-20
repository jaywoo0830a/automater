"""
tests/test_selector_unit.py
----------------------------
Unit tests for SelectorLoader.

Verifies JSON loading, locator resolution, and fallback behaviour
against automator's own selector format (no superselect dependency).
No browser, no Playwright.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, call

from automator.selector_loader import SelectorLoader


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def login_json(tmp_path: Path) -> Path:
    """Minimal login selector file in automator format."""
    data = {
        "_comment": "test fixture",
        "naver_login_id": {
            "description": "아이디 입력란",
            "locators": [
                {"type": "label", "value": "아이디 또는 전화번호"},
                {"type": "css",   "value": "#id"},
            ],
        },
        "naver_login_pw": {
            "description": "비밀번호 입력란",
            "locators": [
                {"type": "label", "value": "비밀번호"},
                {"type": "css",   "value": "#pw"},
            ],
        },
        "naver_login_submit": {
            "description": "로그인 버튼",
            "locators": [
                {"type": "role", "value": "button", "name": "로그인"},
                {"type": "css",  "value": "#log\\.login"},
            ],
        },
    }
    p = tmp_path / "login.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def editor_json(tmp_path: Path) -> Path:
    """Minimal editor selector file in automator format."""
    data = {
        "editor_title": {
            "description": "제목 입력란",
            "locators": [
                {"type": "text", "value": "제목"},
                {"type": "css",  "value": "span.se-placeholder"},
            ],
        },
        "publish_trigger": {
            "description": "발행 버튼",
            "locators": [
                {"type": "role", "value": "button", "name": "발행"},
                {"type": "text", "value": "발행"},
            ],
        },
        "publish_confirm": {
            "description": "발행 확인 버튼",
            "locators": [
                {"type": "testid", "value": "seOnePublishBtn"},
                {"type": "role",   "value": "button", "name": "발행하기"},
            ],
        },
    }
    p = tmp_path / "editor.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def mock_page() -> MagicMock:
    page = MagicMock()
    page.locator.return_value         = MagicMock()
    page.get_by_label.return_value    = MagicMock()
    page.get_by_text.return_value     = MagicMock()
    page.get_by_test_id.return_value  = MagicMock()
    page.get_by_role.return_value     = MagicMock()
    return page


@pytest.fixture
def mock_frame() -> MagicMock:
    frame = MagicMock()
    frame.locator.return_value        = MagicMock()
    frame.get_by_text.return_value    = MagicMock()
    frame.get_by_test_id.return_value = MagicMock()
    frame.get_by_role.return_value    = MagicMock()
    return frame


# ===========================================================================
# 1. load()
# ===========================================================================

@pytest.mark.unit
def test_load_reads_all_keys(login_json):
    loader = SelectorLoader.load(login_json)
    assert set(loader.keys()) == {
        "naver_login_id", "naver_login_pw", "naver_login_submit"
    }


@pytest.mark.unit
def test_load_strips_comment_keys(login_json):
    """Keys starting with _ are metadata and must be excluded."""
    loader = SelectorLoader.load(login_json)
    assert not any(k.startswith("_") for k in loader.keys())


@pytest.mark.unit
def test_load_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        SelectorLoader.load(Path("/nonexistent/selectors.json"))


@pytest.mark.unit
def test_load_invalid_json_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError):
        SelectorLoader.load(bad)


# ===========================================================================
# 2. locator() — type: label (login page)
# ===========================================================================

@pytest.mark.unit
def test_locator_label_id_field(login_json, mock_page):
    """아이디 입력란 — first locator is label."""
    SelectorLoader.load(login_json).locator(mock_page, "naver_login_id")
    mock_page.get_by_label.assert_called_once_with("아이디 또는 전화번호")


@pytest.mark.unit
def test_locator_label_pw_field(login_json, mock_page):
    """비밀번호 입력란 — first locator is label."""
    SelectorLoader.load(login_json).locator(mock_page, "naver_login_pw")
    mock_page.get_by_label.assert_called_once_with("비밀번호")


# ===========================================================================
# 3. locator() — type: role
# ===========================================================================

@pytest.mark.unit
def test_locator_role_submit_button(login_json, mock_page):
    """로그인 버튼 — first locator is role+name."""
    SelectorLoader.load(login_json).locator(mock_page, "naver_login_submit")
    mock_page.get_by_role.assert_called_once_with("button", name="로그인")


@pytest.mark.unit
def test_locator_role_publish_trigger(editor_json, mock_frame):
    """발행 버튼 — first locator is role+name."""
    SelectorLoader.load(editor_json).locator(mock_frame, "publish_trigger")
    mock_frame.get_by_role.assert_called_once_with("button", name="발행")


# ===========================================================================
# 4. locator() — type: testid
# ===========================================================================

@pytest.mark.unit
def test_locator_testid_publish_confirm(editor_json, mock_frame):
    """발행 확인 버튼 — first locator is testid."""
    SelectorLoader.load(editor_json).locator(mock_frame, "publish_confirm")
    mock_frame.get_by_test_id.assert_called_once_with("seOnePublishBtn")


# ===========================================================================
# 5. locator() — type: text
# ===========================================================================

@pytest.mark.unit
def test_locator_text_editor_title(editor_json, mock_frame):
    """제목 — first locator is text."""
    SelectorLoader.load(editor_json).locator(mock_frame, "editor_title")
    mock_frame.get_by_text.assert_called_once_with("제목", exact=True)


# ===========================================================================
# 6. locator() — type: css (fallback)
# ===========================================================================

@pytest.mark.unit
def test_locator_css_fallback(tmp_path, mock_page):
    """When only css is defined, locator() uses ctx.locator(css)."""
    data = {"my_el": {"locators": [{"type": "css", "value": ".my-class"}]}}
    p = tmp_path / "s.json"
    p.write_text(json.dumps(data))
    SelectorLoader.load(p).locator(mock_page, "my_el")
    mock_page.locator.assert_called_once_with(".my-class")


# ===========================================================================
# 7. locator() — type: xpath
# ===========================================================================

@pytest.mark.unit
def test_locator_xpath(tmp_path, mock_page):
    """xpath type is prefixed with 'xpath=' before passing to locator()."""
    data = {"el": {"locators": [{"type": "xpath", "value": "//div[@id='x']"}]}}
    p = tmp_path / "s.json"
    p.write_text(json.dumps(data))
    SelectorLoader.load(p).locator(mock_page, "el")
    mock_page.locator.assert_called_once_with("xpath=//div[@id='x']")


# ===========================================================================
# 8. Fallback: first locator fails, second succeeds
# ===========================================================================

@pytest.mark.unit
def test_locator_falls_back_to_second_on_unknown_type(tmp_path, mock_page):
    """
    If the first locator has an unknown type (ValueError), the loader falls
    back to the second locator.
    """
    data = {
        "el": {
            "locators": [
                {"type": "unknown_type", "value": "x"},  # will raise ValueError
                {"type": "css", "value": ".fallback"},
            ]
        }
    }
    p = tmp_path / "s.json"
    p.write_text(json.dumps(data))
    SelectorLoader.load(p).locator(mock_page, "el")
    mock_page.locator.assert_called_once_with(".fallback")


# ===========================================================================
# 9. Error cases
# ===========================================================================

@pytest.mark.unit
def test_locator_missing_key_raises(login_json, mock_page):
    with pytest.raises(KeyError, match="nonexistent"):
        SelectorLoader.load(login_json).locator(mock_page, "nonexistent")


@pytest.mark.unit
def test_locator_empty_locators_raises(tmp_path, mock_page):
    """An entry with an empty locators list raises ValueError."""
    data = {"el": {"locators": []}}
    p = tmp_path / "s.json"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="no locators"):
        SelectorLoader.load(p).locator(mock_page, "el")


@pytest.mark.unit
def test_locator_all_unknown_types_raises(tmp_path, mock_page):
    """All locators failing raises ValueError."""
    data = {"el": {"locators": [{"type": "???", "value": "x"}]}}
    p = tmp_path / "s.json"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        SelectorLoader.load(p).locator(mock_page, "el")


# ===========================================================================
# 10. description()
# ===========================================================================

@pytest.mark.unit
def test_description_returns_value(login_json):
    assert SelectorLoader.load(login_json).description("naver_login_id") == "아이디 입력란"


@pytest.mark.unit
def test_description_missing_returns_empty(tmp_path):
    data = {"el": {"locators": [{"type": "css", "value": ".x"}]}}
    p = tmp_path / "s.json"
    p.write_text(json.dumps(data))
    assert SelectorLoader.load(p).description("el") == ""


@pytest.mark.unit
def test_description_missing_key_raises(login_json):
    with pytest.raises(KeyError):
        SelectorLoader.load(login_json).description("nonexistent")


# ===========================================================================
# 11. Real selector files
# ===========================================================================

@pytest.mark.unit
def test_real_login_json_loads(mock_page):
    """The actual selectors/naver/login.json parses without error."""
    loader = SelectorLoader.load("selectors/naver/login.json")
    assert "naver_login_id"     in loader.keys()
    assert "naver_login_pw"     in loader.keys()
    assert "naver_login_submit" in loader.keys()


@pytest.mark.unit
def test_real_editor_json_loads(mock_frame):
    """The actual selectors/naver/editor.json parses without error."""
    loader = SelectorLoader.load("selectors/naver/editor.json")
    required_keys = [
        # overlay
        "overlay_draft_cancel", "overlay_draft_confirm", "overlay_help_close",
        # toolbar
        "toolbar_image", "toolbar_publish",
        # editor
        "editor_title", "editor_body", "editor_paragraph",
        "editor_image", "editor_image_block",
        "editor_image_rep", "editor_image_rep_selected",
        # library
        "library_close",
        # publish
        "publish_confirm", "publish_now", "publish_scheduled",
        "publish_scheduled_hour", "publish_scheduled_min",
    ]
    for key in required_keys:
        assert key in loader.keys(), f"Missing key: {key}"


@pytest.mark.unit
def test_real_editor_json_naming_convention(mock_frame):
    """All keys in editor.json follow the {context}_{element}_{variant?} rule."""
    valid_contexts = {"overlay", "toolbar", "editor", "library", "publish"}
    loader = SelectorLoader.load("selectors/naver/editor.json")
    for key in loader.keys():
        context = key.split("_")[0]
        assert context in valid_contexts, (
            f"Key {key!r} has unknown context {context!r}. "
            f"Valid: {valid_contexts}"
        )


@pytest.mark.unit
def test_real_login_json_locator_id(mock_page):
    """naver_login_id resolves to get_by_label in the real JSON."""
    SelectorLoader.load("selectors/naver/login.json").locator(mock_page, "naver_login_id")
    mock_page.get_by_label.assert_called_once_with("아이디 또는 전화번호")


@pytest.mark.unit
def test_real_editor_json_locator_publish_confirm(mock_frame):
    """publish_confirm resolves to get_by_test_id in the real JSON."""
    SelectorLoader.load("selectors/naver/editor.json").locator(mock_frame, "publish_confirm")
    mock_frame.get_by_test_id.assert_called_once_with("seOnePublishBtn")


# ===========================================================================
# 12. css() helper
# ===========================================================================

@pytest.mark.unit
def test_css_returns_first_css_value(tmp_path):
    """css() returns the first css-type locator value."""
    data = {"el": {"locators": [
        {"type": "role", "value": "button", "name": "클릭"},
        {"type": "css",  "value": ".my-btn"},
    ]}}
    p = tmp_path / "s.json"
    p.write_text(json.dumps(data))
    assert SelectorLoader.load(p).css("el") == ".my-btn"


@pytest.mark.unit
def test_css_returns_none_when_no_css(tmp_path):
    """css() returns None when no css-type locator exists."""
    data = {"el": {"locators": [{"type": "role", "value": "button"}]}}
    p = tmp_path / "s.json"
    p.write_text(json.dumps(data))
    assert SelectorLoader.load(p).css("el") is None


@pytest.mark.unit
def test_css_missing_key_raises(login_json):
    with pytest.raises(KeyError):
        SelectorLoader.load(login_json).css("nonexistent")



