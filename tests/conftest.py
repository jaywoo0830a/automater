"""
tests/conftest.py
------------------
Shared pytest fixtures.

Hierarchy
----------
Unit fixtures      : stub_text_gen, noop_img_proc, runner (no mock.patch)
Browser fixtures   : (none — tests use MagicMock)
E2E fixtures       : account -> browser_instance -> auth_context -> page -> editor

E2E fixture requirements
-------------------------
.env needs one of:
  - SESSION_PATH with valid session_state.json
  - NAVER_ID + NAVER_PW + NAVER_BLOG_ID (auto login)
Both absent -> e2e tests skip.
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

from automator.contracts import PostingSpec
from automator.ports import TextGenerator, ImageProcessor
from automator.stubs import StubTextGenerator, NoopImageProcessor
from automator.spec_validator import SpecValidator
from automator.content_builder import ContentBuilder
from automator.runner import JobRunner
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
# Unit / Integration — injected test doubles (no mock.patch)
# ---------------------------------------------------------------------------

@pytest.fixture
def stub_text_gen() -> StubTextGenerator:
    return StubTextGenerator()


@pytest.fixture
def noop_img_proc() -> NoopImageProcessor:
    return NoopImageProcessor()


@pytest.fixture
def validator() -> SpecValidator:
    return SpecValidator()


@pytest.fixture
def builder(stub_text_gen, noop_img_proc) -> ContentBuilder:
    return ContentBuilder(stub_text_gen, noop_img_proc)


@pytest.fixture
def runner(validator, builder) -> JobRunner:
    return JobRunner(validator, builder)


# ---------------------------------------------------------------------------
# E2E — account / browser / context / page / editor
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def account() -> AccountOption:
    if not NAVER_BLOG_ID:
        if not os.path.exists(SESSION_PATH):
            pytest.skip(
                "E2E unavailable — set NAVER_ID / NAVER_PW / NAVER_BLOG_ID in .env "
                "or provide session_state.json."
            )
    return AccountOption(
        username=NAVER_ID,
        password=NAVER_PW,
        meta={"blog_id": NAVER_BLOG_ID},
        session_path=SESSION_PATH,
    )


@pytest.fixture(scope="session")
def browser_instance():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        yield browser
        browser.close()


@pytest.fixture(scope="session")
def auth_context(browser_instance: Browser, account: AccountOption):
    if os.path.exists(account.resolved_session_path):
        ctx = browser_instance.new_context(
            storage_state=account.resolved_session_path,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )
    else:
        ctx = browser_instance.new_context(locale="ko-KR", timezone_id="Asia/Seoul")
        page = ctx.new_page()
        page.goto("https://nid.naver.com/nidlogin.login")
        _LOGIN_SEL.locator(page, "naver_login_id").fill(account.username)
        _LOGIN_SEL.locator(page, "naver_login_pw").fill(account.password)
        _LOGIN_SEL.locator(page, "naver_login_submit").click()
        page.wait_for_url(lambda url: "nidlogin" not in url, timeout=15_000)
        ctx.storage_state(path=account.resolved_session_path)
        page.close()
    yield ctx
    ctx.close()


@pytest.fixture
def page(auth_context: BrowserContext) -> Page:
    p = auth_context.new_page()
    yield p
    p.close()


@pytest.fixture
def editor(page: Page, account: AccountOption) -> SmartEditorOne:
    return SmartEditorOne(
        page,
        f"https://blog.naver.com/{account.meta['blog_id']}?Redirect=Write&",
        dry_run=True,
    )


# ---------------------------------------------------------------------------
# --real-run custom option
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    parser.addoption(
        "--real-run",
        action="store_true",
        default=False,
        help="Enable real publishing (dry_run=False).",
    )


@pytest.fixture
def real_run(request) -> bool:
    return request.config.getoption("--real-run")
