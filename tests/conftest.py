"""
tests/conftest.py
------------------
모든 테스트가 공유하는 pytest fixtures.

계층 구조
----------
Unit fixtures  : mock_paragraph_generator (autouse)
E2E fixtures   : account → browser_instance → auth_context → page → editor
                 post_images (이미지 경로) — AssetLoader 로 대체됨

E2E fixture 사용 조건
----------------------
.env 에 다음 중 하나가 필요:
  - SESSION_PATH 에 유효한 session_state.json
  - NAVER_ID + NAVER_PW + NAVER_BLOG_ID (자동 로그인)
둘 다 없으면 e2e 테스트는 자동으로 skip 된다.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

from automator.paragraph_generator import _stub_generate
from automator.selector_loader import SelectorLoader
from automator.smart_editor import SmartEditorOne
from automator.options import AccountOption

load_dotenv()

NAVER_ID      = os.getenv("NAVER_ID",      "")
NAVER_PW      = os.getenv("NAVER_PW",      "")
NAVER_BLOG_ID = os.getenv("NAVER_BLOG_ID", "")
SESSION_PATH  = os.getenv("SESSION_PATH",  "session_state.json")


_LOGIN_SEL = SelectorLoader.load("selectors/naver/login.json")


# ---------------------------------------------------------------------------
# Unit — ParagraphGenerator mock (autouse)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_paragraph_generator(request):
    """
    Unit 테스트에서 ParagraphGenerator 를 stub 으로 교체.
    E2e 테스트는 실제 클래스를 사용 (ENV=dev|test 면 자동으로 stub 반환).
    """
    if "e2e" in request.keywords:
        yield
        return

    mock = MagicMock()
    mock.return_value.generate.side_effect = _stub_generate
    with patch("automator.job.ParagraphGenerator", mock):
        yield mock


# ---------------------------------------------------------------------------
# E2E — 계정 / 브라우저 / 컨텍스트 / 페이지 / 에디터
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def account() -> AccountOption:
    """
    .env 의 Naver 계정 정보로 AccountOption 생성.
    계정 정보와 session_state.json 모두 없으면 skip.
    """
    if not NAVER_BLOG_ID:
        if not os.path.exists(SESSION_PATH):
            pytest.skip(
                "E2E 테스트 실행 불가 — .env 에 NAVER_ID / NAVER_PW / NAVER_BLOG_ID 설정 또는 "
                "session_state.json 필요. bash ./run/dev.sh --session 으로 세션을 저장하세요."
            )
    return AccountOption(
        naver_id     = NAVER_ID,
        naver_pw     = NAVER_PW,
        blog_id      = NAVER_BLOG_ID,
        session_path = SESSION_PATH,
    )


@pytest.fixture(scope="session")
def browser_instance():
    """세션 전체에서 하나의 Chromium 인스턴스를 공유."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        yield browser
        browser.close()


@pytest.fixture(scope="session")
def auth_context(browser_instance: Browser, account: AccountOption):
    """
    session_state.json 이 있으면 로드, 없으면 자동 로그인 후 저장.
    세션 전체에서 하나의 BrowserContext 를 공유.
    """
    if os.path.exists(account.resolved_session_path):
        ctx = browser_instance.new_context(
            storage_state = account.resolved_session_path,
            locale        = "ko-KR",
            timezone_id   = "Asia/Seoul",
        )
    else:
        ctx  = browser_instance.new_context(locale="ko-KR", timezone_id="Asia/Seoul")
        page = ctx.new_page()
        page.goto("https://nid.naver.com/nidlogin.login")
        _LOGIN_SEL.locator(page, "naver_login_id").fill(account.naver_id)
        _LOGIN_SEL.locator(page, "naver_login_pw").fill(account.naver_pw)
        _LOGIN_SEL.locator(page, "naver_login_submit").click()
        page.wait_for_url(lambda url: "nidlogin" not in url, timeout=15_000)
        ctx.storage_state(path=account.resolved_session_path)
        page.close()

    yield ctx
    ctx.close()


@pytest.fixture
def page(auth_context: BrowserContext) -> Page:
    """테스트마다 새 탭을 열고 종료 시 닫는다."""
    p = auth_context.new_page()
    yield p
    p.close()


@pytest.fixture
def editor(page: Page, account: AccountOption) -> SmartEditorOne:
    """dry_run=True — 발행 팝오버는 열리지만 실제 발행하기 버튼은 누르지 않는다."""
    return SmartEditorOne(page, account.write_url, dry_run=True)


