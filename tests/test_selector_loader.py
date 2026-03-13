"""
tests/test_selector_loader.py
-----------------------------
Unit tests for automator.selector_loader.

SelectorLoader wraps a superselect-format JSON file and resolves
Playwright locators from it. Two contexts are supported:
  - page context  : for selectors outside any iframe (e.g. login)
  - frame context : for selectors inside an iframe (e.g. editor)

JSON format (superselect output):
  {
    "<key>": {
      "primary": "<playwright locator string>",
      "selectors": [{"label": "...", "pw": "...", "score": 0.9}, ...],
      ...
    }
  }
"""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from automator.selector_loader import SelectorLoader


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def login_json(tmp_path: Path) -> Path:
    data = {
        "naver_login_id": {
            "tag": "input",
            "primary": "page.locator('#id').first",
            "selectors": [
                {"label": "css",  "pw": "page.locator('#id').first",              "score": 0.81},
                {"label": "aria", "pw": "page.get_by_label('아이디 또는 전화번호')", "score": 0.55},
            ],
            "stability_score": 0.81,
            "_meta": {"css": "#id", "alias": "naver_login_id"},
        },
        "naver_login_pw": {
            "tag": "input",
            "primary": "page.locator('#pw').first",
            "selectors": [
                {"label": "css",  "pw": "page.locator('#pw').first",  "score": 0.81},
                {"label": "aria", "pw": "page.get_by_label('비밀번호')", "score": 0.55},
            ],
            "stability_score": 0.81,
            "_meta": {"css": "#pw", "alias": "naver_login_pw"},
        },
        "naver_login_submit": {
            "tag": "button",
            "primary": "page.locator('#log\\.login').first",
            "selectors": [
                {"label": "css",  "pw": "page.locator('#log\\.login').first",      "score": 0.81},
                {"label": "text", "pw": "page.get_by_text('로그인', exact=True)", "score": 0.42},
            ],
            "stability_score": 0.81,
            "_meta": {"alias": "naver_login_submit"},
        },
    }
    f = tmp_path / "login.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    return f


@pytest.fixture
def editor_json(tmp_path: Path) -> Path:
    data = {
        "editor_title": {
            "tag": "span",
            "primary": "page.get_by_text('제목', exact=True)",
            "selectors": [
                {"label": "text", "pw": "page.get_by_text('제목', exact=True)", "score": 0.42},
            ],
            "stability_score": 0.42,
            "_meta": {"alias": "editor_title"},
        },
        "editor_body": {
            "tag": "span",
            "primary": "page.get_by_text('글감과 함께 나의 일상을 기록해보세요!', exact=True)",
            "selectors": [
                {"label": "text", "pw": "page.get_by_text('글감과 함께 나의 일상을 기록해보세요!', exact=True)", "score": 0.42},
            ],
            "stability_score": 0.42,
            "_meta": {"alias": "editor_body"},
        },
        "publish_trigger": {
            "tag": "button",
            "primary": "page.get_by_text('발행', exact=True)",
            "selectors": [
                {"label": "text",   "pw": "page.get_by_text('발행', exact=True)",             "score": 0.42},
                {"label": "testid", "pw": "page.get_by_test_id('seOnePublishBtn')",           "score": 0.65},
            ],
            "stability_score": 0.65,
            "_meta": {"alias": "publish_trigger"},
        },
        "publish_confirm": {
            "tag": "button",
            "primary": "page.get_by_test_id('seOnePublishBtn')",
            "selectors": [
                {"label": "testid", "pw": "page.get_by_test_id('seOnePublishBtn')", "score": 0.65},
            ],
            "stability_score": 0.65,
            "_meta": {"alias": "publish_confirm"},
        },
    }
    f = tmp_path / "editor.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    return f


@pytest.fixture
def mock_page() -> MagicMock:
    page = MagicMock()
    page.locator.return_value = MagicMock()
    page.get_by_label.return_value = MagicMock()
    page.get_by_text.return_value = MagicMock()
    page.get_by_test_id.return_value = MagicMock()
    return page


@pytest.fixture
def mock_frame() -> MagicMock:
    frame = MagicMock()
    frame.locator.return_value = MagicMock()
    frame.get_by_text.return_value = MagicMock()
    frame.get_by_test_id.return_value = MagicMock()
    return frame


# ---------------------------------------------------------------------------
# 1. SelectorLoader.load
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_load_reads_json_keys(login_json: Path) -> None:
    """load() reads all top-level keys from the JSON file."""
    loader = SelectorLoader.load(login_json)
    assert set(loader.keys()) == {"naver_login_id", "naver_login_pw", "naver_login_submit"}


@pytest.mark.unit
def test_load_missing_file_raises() -> None:
    """load() raises FileNotFoundError for a non-existent file."""
    with pytest.raises(FileNotFoundError):
        SelectorLoader.load(Path("/nonexistent/selectors.json"))


@pytest.mark.unit
def test_load_invalid_json_raises(tmp_path: Path) -> None:
    """load() raises ValueError for invalid JSON."""
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError):
        SelectorLoader.load(bad)


# ---------------------------------------------------------------------------
# 2. locator() — page context (login selectors, outside iframe)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_locator_page_css_id(login_json: Path, mock_page: MagicMock) -> None:
    """locator() with a page context calls page.locator for CSS #id selectors."""
    loader = SelectorLoader.load(login_json)
    loader.locator(mock_page, "naver_login_id")
    mock_page.locator.assert_called_once_with("#id")


@pytest.mark.unit
def test_locator_page_pw_field(login_json: Path, mock_page: MagicMock) -> None:
    """locator() resolves the password field from login JSON."""
    loader = SelectorLoader.load(login_json)
    loader.locator(mock_page, "naver_login_pw")
    mock_page.locator.assert_called_once_with("#pw")


@pytest.mark.unit
def test_locator_page_submit_button(login_json: Path, mock_page: MagicMock) -> None:
    """locator() resolves the submit button (CSS with escaped dot)."""
    loader = SelectorLoader.load(login_json)
    loader.locator(mock_page, "naver_login_submit")
    mock_page.locator.assert_called_once_with("#log\\.login")


@pytest.mark.unit
def test_locator_missing_key_raises(login_json: Path, mock_page: MagicMock) -> None:
    """locator() raises KeyError for an unknown selector key."""
    loader = SelectorLoader.load(login_json)
    with pytest.raises(KeyError, match="nonexistent"):
        loader.locator(mock_page, "nonexistent")


# ---------------------------------------------------------------------------
# 3. locator() — frame context (editor selectors, inside iframe)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_locator_frame_get_by_text(editor_json: Path, mock_frame: MagicMock) -> None:
    """locator() with a frame context calls frame.get_by_text for text selectors."""
    loader = SelectorLoader.load(editor_json)
    loader.locator(mock_frame, "editor_title")
    mock_frame.get_by_text.assert_called_once_with("제목", exact=True)


@pytest.mark.unit
def test_locator_frame_get_by_test_id(editor_json: Path, mock_frame: MagicMock) -> None:
    """locator() with a frame context calls frame.get_by_test_id for testid selectors."""
    loader = SelectorLoader.load(editor_json)
    loader.locator(mock_frame, "publish_confirm")
    mock_frame.get_by_test_id.assert_called_once_with("seOnePublishBtn")


# ---------------------------------------------------------------------------
# 4. primary() — raw primary pw string
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_primary_returns_string(login_json: Path) -> None:
    """primary() returns the raw Playwright locator string from the JSON."""
    loader = SelectorLoader.load(login_json)
    assert loader.primary("naver_login_id") == "page.locator('#id').first"


@pytest.mark.unit
def test_primary_missing_key_raises(login_json: Path) -> None:
    """primary() raises KeyError for an unknown key."""
    loader = SelectorLoader.load(login_json)
    with pytest.raises(KeyError):
        loader.primary("nonexistent")


# ---------------------------------------------------------------------------
# 5. best_selector() — highest-score selector entry
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_best_selector_returns_highest_score(login_json: Path) -> None:
    """best_selector() returns the entry with the highest score."""
    loader = SelectorLoader.load(login_json)
    best = loader.best_selector("naver_login_id")
    assert best["score"] == 0.81
    assert best["label"] == "css"


@pytest.mark.unit
def test_best_selector_testid_over_text(editor_json: Path) -> None:
    """best_selector() prefers testid (0.65) over text (0.42)."""
    loader = SelectorLoader.load(editor_json)
    best = loader.best_selector("publish_trigger")
    assert best["label"] == "testid"
