"""
tests/test_selector_unit.py
----------------------------
Unit tests for SelectorLoader.

Verifies JSON loading, locator resolution, and fallback behaviour.
No browser, no Playwright.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from automator.selector_loader import SelectorLoader


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def login_json(tmp_path: Path) -> Path:
    data = {
        "naver_login_id": {
            "primary": "page.locator('#id').first",
            "selectors": [
                {"label": "css",  "pw": "page.locator('#id').first",              "score": 0.81},
                {"label": "aria", "pw": "page.get_by_label('아이디 또는 전화번호')", "score": 0.55},
            ],
        },
        "naver_login_pw": {
            "primary": "page.locator('#pw').first",
            "selectors": [
                {"label": "css",  "pw": "page.locator('#pw').first",  "score": 0.81},
                {"label": "aria", "pw": "page.get_by_label('비밀번호')", "score": 0.55},
            ],
        },
        "naver_login_submit": {
            "primary": "page.locator('#log\\.login').first",
            "selectors": [
                {"label": "css",  "pw": "page.locator('#log\\.login').first",      "score": 0.81},
                {"label": "text", "pw": "page.get_by_text('로그인', exact=True)", "score": 0.42},
            ],
        },
    }
    p = tmp_path / "login.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def editor_json(tmp_path: Path) -> Path:
    data = {
        "editor_title": {
            "primary": "page.get_by_text('제목', exact=True)",
            "selectors": [{"label": "text", "pw": "page.get_by_text('제목', exact=True)", "score": 0.42}],
        },
        "publish_trigger": {
            "primary": "page.get_by_text('발행', exact=True)",
            "selectors": [
                {"label": "text",   "pw": "page.get_by_text('발행', exact=True)",   "score": 0.42},
                {"label": "testid", "pw": "page.get_by_test_id('seOnePublishBtn')", "score": 0.65},
            ],
        },
        "publish_confirm": {
            "primary": "page.get_by_test_id('seOnePublishBtn')",
            "selectors": [{"label": "testid", "pw": "page.get_by_test_id('seOnePublishBtn')", "score": 0.65}],
        },
    }
    p = tmp_path / "editor.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def mock_page() -> MagicMock:
    page = MagicMock()
    page.locator.return_value      = MagicMock()
    page.get_by_label.return_value = MagicMock()
    page.get_by_text.return_value  = MagicMock()
    page.get_by_test_id.return_value = MagicMock()
    return page


@pytest.fixture
def mock_frame() -> MagicMock:
    frame = MagicMock()
    frame.locator.return_value       = MagicMock()
    frame.get_by_text.return_value   = MagicMock()
    frame.get_by_test_id.return_value = MagicMock()
    return frame


# ===========================================================================
# load()
# ===========================================================================

@pytest.mark.unit
def test_load_reads_all_keys(login_json):
    loader = SelectorLoader.load(login_json)
    assert set(loader.keys()) == {"naver_login_id", "naver_login_pw", "naver_login_submit"}


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
# locator() — page context
# ===========================================================================

@pytest.mark.unit
def test_locator_css_id_field(login_json, mock_page):
    SelectorLoader.load(login_json).locator(mock_page, "naver_login_id")
    mock_page.locator.assert_called_once_with("#id")


@pytest.mark.unit
def test_locator_css_pw_field(login_json, mock_page):
    SelectorLoader.load(login_json).locator(mock_page, "naver_login_pw")
    mock_page.locator.assert_called_once_with("#pw")


@pytest.mark.unit
def test_locator_css_submit_button(login_json, mock_page):
    SelectorLoader.load(login_json).locator(mock_page, "naver_login_submit")
    mock_page.locator.assert_called_once_with("#log\\.login")


@pytest.mark.unit
def test_locator_missing_key_raises(login_json, mock_page):
    with pytest.raises(KeyError, match="nonexistent"):
        SelectorLoader.load(login_json).locator(mock_page, "nonexistent")


# ===========================================================================
# locator() — frame context
# ===========================================================================

@pytest.mark.unit
def test_locator_frame_get_by_text(editor_json, mock_frame):
    SelectorLoader.load(editor_json).locator(mock_frame, "editor_title")
    mock_frame.get_by_text.assert_called_once_with("제목", exact=True)


@pytest.mark.unit
def test_locator_frame_get_by_test_id(editor_json, mock_frame):
    SelectorLoader.load(editor_json).locator(mock_frame, "publish_confirm")
    mock_frame.get_by_test_id.assert_called_once_with("seOnePublishBtn")


# ===========================================================================
# best_selector()
# ===========================================================================

@pytest.mark.unit
def test_best_selector_returns_highest_score(login_json):
    best = SelectorLoader.load(login_json).best_selector("naver_login_id")
    assert best["score"] == 0.81
    assert best["label"] == "css"


@pytest.mark.unit
def test_best_selector_prefers_testid_over_text(editor_json):
    best = SelectorLoader.load(editor_json).best_selector("publish_trigger")
    assert best["label"] == "testid"


@pytest.mark.unit
def test_best_selector_missing_key_raises(login_json):
    with pytest.raises(KeyError):
        SelectorLoader.load(login_json).best_selector("nonexistent")


# ===========================================================================
# primary()
# ===========================================================================

@pytest.mark.unit
def test_primary_returns_raw_string(login_json):
    assert SelectorLoader.load(login_json).primary("naver_login_id") == "page.locator('#id').first"


@pytest.mark.unit
def test_primary_missing_key_raises(login_json):
    with pytest.raises(KeyError):
        SelectorLoader.load(login_json).primary("nonexistent")
