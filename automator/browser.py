"""
automator/browser.py
--------------------
Browser utilities: context creation, frame detection, and stable locators.

Everything in this module is Playwright-specific infrastructure with no
business logic. blog.py imports from here; nothing outside automator/
should need to.

Contents:
  Constants     — DOM selectors that are structurally stable
  build_context — creates a localized BrowserContext for a NaverAccount
  editor_frame  — detects iframe vs page-level Smart Editor
  Locators      — dataclass of pre-built stable Playwright locators
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Page, Browser, BrowserContext, Locator


# ---------------------------------------------------------------------------
# URL constants
# ---------------------------------------------------------------------------

LOGIN_URL = "https://nid.naver.com/nidlogin.login"


# ---------------------------------------------------------------------------
# DOM constants
# Stable CSS selectors that represent Smart Editor structure.
# These change only when Naver redesigns the editor itself (rare).
# ---------------------------------------------------------------------------

# Editor iframe
MAIN_FRAME = "#mainFrame"

# Presence of this class confirms the Smart Editor is fully loaded
EDITOR_CONTENT = ".se-content"

# An uploaded image resource inside the editor
UPLOADED_IMAGE = ".se-image-resource"

# Wrapper div for each image block — hover-target that reveals the rep button
IMAGE_COMPONENT = "div.se-component.se-image"

# Representative (thumbnail) image toggle button
REP_IMAGE_BUTTON          = "button.se-set-rep-image-button"
REP_IMAGE_BUTTON_SELECTED = "button.se-set-rep-image-button.se-is-selected"

# Overlays that can block pointer events
POPUP_CANCEL_BUTTON = "button.se-popup-button-cancel"
HELP_CLOSE_BUTTON   = "button.se-help-panel-close-button"


# ---------------------------------------------------------------------------
# build_context
# ---------------------------------------------------------------------------

def build_context(
    browser: Browser,
    account,   # NaverAccount — imported at call site to avoid circular import
    runtime,   # RuntimeOption
) -> BrowserContext:
    """
    Create a localized BrowserContext for the given account and runtime.

    Applies locale, timezone, and Accept-Language from runtime settings.
    Loads storage state from account.session_path when the file exists so
    the browser starts pre-authenticated.
    """
    context_kwargs: dict = {
        "locale":      runtime.locale,
        "timezone_id": runtime.timezone,
        "extra_http_headers": {
            "Accept-Language": f"{runtime.language},{runtime.locale[:2]};q=0.9"
        },
    }

    if account.session_exists():
        context_kwargs["storage_state"] = str(account.session_path)

    return browser.new_context(**context_kwargs)


# ---------------------------------------------------------------------------
# editor_frame
# ---------------------------------------------------------------------------

def editor_frame(page: Page):
    """
    Return the context (FrameLocator or Page) that contains the Smart Editor.

    Naver Blog has gone through structural changes:
      - Legacy: editor lives inside #mainFrame iframe
      - Current: editor may live directly on the page

    Probes for #mainFrame within 1 second. Returns page.frame_locator(MAIN_FRAME).first
    when found; returns the page itself otherwise. All downstream locator calls work
    identically regardless of which path is taken.
    """
    try:
        page.frame_locator(MAIN_FRAME) \
            .locator(EDITOR_CONTENT) \
            .wait_for(state="visible", timeout=1_000)
        return page.frame_locator(MAIN_FRAME).first
    except Exception:
        return page


# ---------------------------------------------------------------------------
# editor_js_frame
# ---------------------------------------------------------------------------

def editor_js_frame(page: Page):
    """
    Return the actual Frame object for JavaScript evaluate() calls.

    FrameLocator.first does not expose evaluate() — this walks page.frames
    to find the editor iframe's Frame object. Falls back to page.main_frame
    when no iframe is present (page-level editor).
    """
    return next(
        (f for f in page.frames if f != page.main_frame),
        page.main_frame,
    )


# ---------------------------------------------------------------------------
# Stable locator helpers
#
# get_by_role and get_by_test_id are the most stable Playwright locators:
#   - get_by_role   : matches ARIA semantics — independent of class/text changes
#   - get_by_test_id: matches data-testid attributes — explicit contract with devs
#   - get_by_label  : matches <label> associations — stable for form inputs
#
# These are preferred over get_by_text and CSS selectors from superselect JSON
# for elements whose ARIA role or test-id is known and stable.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NaverLoginLocators:
    """
    Stable locators for the Naver login page.

    All three are matched by semantic role+name or label — they do not depend
    on element ID, class, or exact text strings.
    """

    @staticmethod
    def id_field(ctx) -> Locator:
        """Login ID input — matched by label text."""
        return ctx.get_by_label("아이디 또는 전화번호")

    @staticmethod
    def pw_field(ctx) -> Locator:
        """Password input — matched by label text."""
        return ctx.get_by_label("비밀번호")

    @staticmethod
    def submit_button(ctx) -> Locator:
        """Login submit button — matched by role+name."""
        return ctx.get_by_role("button", name="로그인")


@dataclass(frozen=True)
class NaverEditorLocators:
    """
    Stable locators for the Naver Smart Editor.

    All locators use get_by_role or get_by_label where possible.
    Text-based locators are used only when no role/label alternative exists,
    and are listed with a comment explaining why.
    """

    @staticmethod
    def title_area(ctx) -> Locator:
        """
        Title input area — matched by placeholder text via get_by_text.
        The title area is a contenteditable div with placeholder '제목'.
        No stable role or label is available for this element.
        """
        return ctx.get_by_text("제목", exact=True)

    @staticmethod
    def body_area(ctx) -> Locator:
        """
        Body input area — matched by placeholder text via get_by_text.
        The placeholder text changes between Naver deployments; update here
        when the editor prompt text changes.
        """
        return ctx.get_by_text("글감과 함께 나의 일상을 기록해보세요!", exact=True)

    @staticmethod
    def image_trigger(ctx) -> Locator:
        """
        Image upload toolbar button — matched by role+name.
        The button label '사진' is stable across Naver Smart Editor versions.
        """
        return ctx.get_by_role("button", name="사진")

    @staticmethod
    def publish_trigger(ctx) -> Locator:
        """
        Publish trigger button — matched by role+name.
        Lives in the page-level toolbar (outside the iframe).
        """
        return ctx.get_by_role("button", name="발행")

    @staticmethod
    def publish_confirm(ctx) -> Locator:
        """
        Publish confirm button inside the publish popover.
        Matched by data-testid — most stable available locator.
        """
        return ctx.get_by_test_id("seOnePublishBtn")

    @staticmethod
    def library_close(ctx) -> Locator:
        """
        Media library close button — matched by role+name.
        Appears when Naver opens the media library after image selection.
        """
        return ctx.get_by_role("button", name="팝업 닫기")
