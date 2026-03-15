"""
automator/browser_actions.py
------------------------------
Layer 2: Browser Actions

Pure functions for Playwright DOM interactions.

Rules
-----
- No `self`, no class state, no global mutable state.
- Accept Playwright locators / frames / pages as arguments.
- Return plain Python values (bool, str, int, list, None).
- Never raise — return a sentinel value on failure instead.
- Each function does exactly one thing.

These rules make every function independently testable with MagicMock
without launching a browser.

Catalogue
---------
Waiting       wait_until_visible, wait_until_hidden, wait_until_attached,
              wait_until_count, wait_for_url_contains

Clicking      click_if_visible, click_polling, click_nth

Typing        fill, fill_and_submit, type_text, clear_and_fill, press_key,
              type_and_press

Selection     select_option_by_value, select_option_by_label

Hovering      hover_if_visible

State checks  is_visible, is_checked, is_disabled, is_editable,
              has_class, get_count

Reading       get_text, get_attribute, get_all_texts

Scrolling     scroll_into_view, scroll_to_bottom

File upload   upload_file

Composed      dismiss, dismiss_polling, dismiss_parallel

Parallel      wait_any_visible, wait_all_visible,
              any_visible, all_visible,
              click_parallel, fill_parallel,
              get_texts_parallel, get_attributes_parallel

JavaScript    js_dispatch_click, js_evaluate, js_scroll_into_view

Frame         find_editor_frame, find_js_frame
"""

from __future__ import annotations

import time
from typing import Any


# ---------------------------------------------------------------------------
# Waiting
# ---------------------------------------------------------------------------

def wait_until_visible(locator, timeout_ms: int = 5_000) -> bool:
    """
    Wait for locator to become visible.
    Returns True if visible within timeout, False otherwise. Never raises.
    """
    try:
        locator.wait_for(state="visible", timeout=timeout_ms)
        return True
    except Exception:
        return False


def wait_until_hidden(locator, timeout_ms: int = 3_000) -> bool:
    """
    Wait for locator to become hidden / detached.
    Returns True if hidden within timeout, False otherwise. Never raises.
    """
    try:
        locator.wait_for(state="hidden", timeout=timeout_ms)
        return True
    except Exception:
        return False


def wait_until_attached(locator, timeout_ms: int = 5_000) -> bool:
    """
    Wait for locator to be attached to DOM (not necessarily visible).
    Returns True if attached within timeout, False otherwise. Never raises.
    """
    try:
        locator.wait_for(state="attached", timeout=timeout_ms)
        return True
    except Exception:
        return False


def wait_until_count(locator, expected: int, timeout_ms: int = 5_000) -> bool:
    """
    Wait until the locator matches exactly ``expected`` elements.

    Polls every 100 ms. Useful for waiting on dynamic content to fully load
    (e.g. "wait until 3 images are in the DOM").

    Returns True when count matches within timeout, False otherwise.
    """
    deadline = time.monotonic() + timeout_ms / 1_000
    while time.monotonic() < deadline:
        try:
            if locator.count() == expected:
                return True
        except Exception:
            pass
        time.sleep(0.1)
    return False


def wait_for_url_contains(page: Any, fragment: str, timeout_ms: int = 10_000) -> bool:
    """
    Wait until the page URL contains ``fragment``.

    Useful for navigation confirmation (e.g. after login redirect).
    Returns True when URL matches within timeout, False otherwise.
    """
    deadline = time.monotonic() + timeout_ms / 1_000
    while time.monotonic() < deadline:
        try:
            if fragment in page.url:
                return True
        except Exception:
            pass
        time.sleep(0.1)
    return False


# ---------------------------------------------------------------------------
# Clicking
# ---------------------------------------------------------------------------

def click_if_visible(locator, timeout_ms: int = 3_000) -> bool:
    """
    Click locator if it becomes visible within timeout_ms.
    Returns True when clicked, False when not found / not visible. Never raises.
    """
    if wait_until_visible(locator, timeout_ms):
        try:
            locator.click()
            return True
        except Exception:
            return False
    return False


def click_polling(locator, timeout_ms: int = 6_000, probe_ms: int = 200) -> bool:
    """
    Poll locator repeatedly until visible, then click.

    Useful for race-condition elements that appear unpredictably after page load.
    Returns True when clicked, False when deadline expired. Never raises.
    """
    deadline = time.monotonic() + timeout_ms / 1_000
    while time.monotonic() < deadline:
        if click_if_visible(locator, probe_ms):
            return True
    return False


def click_nth(locator, index: int, timeout_ms: int = 3_000) -> bool:
    """
    Click the nth element matched by locator.

    Returns True when clicked, False when not found / index out of range.
    Never raises.
    """
    return click_if_visible(locator.nth(index), timeout_ms)


# ---------------------------------------------------------------------------
# Typing
# ---------------------------------------------------------------------------

def fill(locator, text: str, timeout_ms: int = 5_000) -> bool:
    """
    Wait for locator to be visible, then fill it with ``text`` (replaces content).

    Uses Playwright's fill() — works for input/textarea. Clears existing value.
    Returns True on success, False otherwise. Never raises.
    """
    if wait_until_visible(locator, timeout_ms):
        try:
            locator.fill(text)
            return True
        except Exception:
            return False
    return False


def fill_and_submit(locator, text: str, timeout_ms: int = 5_000) -> bool:
    """
    Fill locator with text, then press Enter to submit.

    Composition of fill + press_key("Enter").
    Returns True on success, False otherwise. Never raises.
    """
    if fill(locator, text, timeout_ms):
        return press_key(locator, "Enter")
    return False


def type_text(page: Any, text: str) -> bool:
    """
    Type ``text`` into the currently focused element via keyboard.

    Uses page.keyboard.type() — simulates real keystrokes. Use this for
    contenteditable areas that don't support fill().
    Returns True on success, False otherwise. Never raises.
    """
    try:
        page.keyboard.type(text)
        return True
    except Exception:
        return False


def clear_and_fill(locator, text: str, timeout_ms: int = 5_000) -> bool:
    """
    Select all existing content then type new text.

    Useful for contenteditable elements where fill() doesn't work.
    Sequence: click → Ctrl+A → type.
    Returns True on success, False otherwise. Never raises.
    """
    try:
        locator.wait_for(state="visible", timeout=timeout_ms)
        locator.click()
        locator.page.keyboard.press("Control+a")
        locator.page.keyboard.type(text)
        return True
    except Exception:
        return False


def press_key(locator, key: str, timeout_ms: int = 3_000) -> bool:
    """
    Wait for locator to be visible, then press ``key``.

    ``key`` follows Playwright key notation (e.g. "Enter", "Tab", "Escape",
    "Control+a").
    Returns True on success, False otherwise. Never raises.
    """
    if wait_until_visible(locator, timeout_ms):
        try:
            locator.press(key)
            return True
        except Exception:
            return False
    return False


def type_and_press(page: Any, text: str, key: str) -> bool:
    """
    Type text into the focused element, then press a key.

    Composition of type_text + keyboard.press.
    Common use: type_and_press(page, "검색어", "Enter").
    Returns True on success, False otherwise. Never raises.
    """
    try:
        page.keyboard.type(text)
        page.keyboard.press(key)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Selection (dropdowns)
# ---------------------------------------------------------------------------

def select_option_by_value(locator, value: str, timeout_ms: int = 5_000) -> bool:
    """
    Select a <select> option by its value attribute.

    Returns True on success, False otherwise. Never raises.
    """
    if wait_until_visible(locator, timeout_ms):
        try:
            locator.select_option(value=value)
            return True
        except Exception:
            return False
    return False


def select_option_by_label(locator, label: str, timeout_ms: int = 5_000) -> bool:
    """
    Select a <select> option by its visible label text.

    Returns True on success, False otherwise. Never raises.
    """
    if wait_until_visible(locator, timeout_ms):
        try:
            locator.select_option(label=label)
            return True
        except Exception:
            return False
    return False


# ---------------------------------------------------------------------------
# Hovering
# ---------------------------------------------------------------------------

def hover_if_visible(locator, timeout_ms: int = 3_000) -> bool:
    """
    Move the mouse over locator if it is visible.

    Useful for revealing hover-only elements (e.g. image control buttons).
    Returns True on success, False otherwise. Never raises.
    """
    if wait_until_visible(locator, timeout_ms):
        try:
            locator.hover()
            return True
        except Exception:
            return False
    return False


# ---------------------------------------------------------------------------
# State checks  (return bool / primitive — never raise)
# ---------------------------------------------------------------------------

def is_visible(locator) -> bool:
    """Return True if locator is currently visible in the DOM. Never raises."""
    try:
        return locator.is_visible()
    except Exception:
        return False


def is_checked(locator) -> bool:
    """Return True if checkbox / radio locator is checked. Never raises."""
    try:
        return locator.is_checked()
    except Exception:
        return False


def is_disabled(locator) -> bool:
    """Return True if locator is disabled. Never raises."""
    try:
        return locator.is_disabled()
    except Exception:
        return True   # assume disabled on error (safe default)


def is_editable(locator) -> bool:
    """Return True if locator is editable (not readonly / disabled). Never raises."""
    try:
        return locator.is_editable()
    except Exception:
        return False


def has_class(locator, class_name: str) -> bool:
    """
    Return True if locator's class attribute contains ``class_name``.
    Never raises.
    """
    try:
        cls = locator.get_attribute("class") or ""
        return class_name in cls.split()
    except Exception:
        return False


def get_count(locator) -> int:
    """Return number of elements matching locator, or 0 on error. Never raises."""
    try:
        return locator.count()
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def get_text(locator, default: str = "") -> str:
    """
    Return the visible inner text of locator.
    Returns ``default`` on any error. Never raises.
    """
    try:
        return (locator.inner_text() or "").strip()
    except Exception:
        return default


def get_attribute(locator, name: str, default: str = "") -> str:
    """
    Return value of attribute ``name`` on locator.
    Returns ``default`` when attribute is absent or on error. Never raises.
    """
    try:
        return locator.get_attribute(name) or default
    except Exception:
        return default


def get_all_texts(locator) -> list[str]:
    """
    Return inner text of every element matching locator as a list.
    Returns empty list on error. Never raises.
    """
    try:
        return [t.strip() for t in locator.all_inner_texts()]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Scrolling
# ---------------------------------------------------------------------------

def scroll_into_view(locator) -> bool:
    """
    Scroll locator into the viewport.
    Returns True on success, False otherwise. Never raises.
    """
    try:
        locator.scroll_into_view_if_needed()
        return True
    except Exception:
        return False


def scroll_to_bottom(page: Any) -> bool:
    """
    Scroll the page to the very bottom.
    Useful for triggering infinite-scroll content loads.
    Returns True on success, False otherwise. Never raises.
    """
    try:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------

def upload_file(page: Any, trigger_locator, file_path: str, timeout_ms: int = 10_000) -> bool:
    """
    Click trigger_locator to open a file chooser and upload ``file_path``.

    Handles the expect_file_chooser context manager automatically.
    Returns True on success, False otherwise. Never raises.
    """
    try:
        with page.expect_file_chooser(timeout=timeout_ms) as fc_info:
            trigger_locator.click()
        fc_info.value.set_files(file_path)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Composed actions
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Parallel variants
#
# Naming rule: {action}_parallel or {check}_any / {check}_all
#
#   _parallel  : applies the same action to N locators in one shared window
#   _any       : succeeds as soon as ONE of N locators satisfies the condition
#   _all       : succeeds only when ALL N locators satisfy the condition
#
# All share a single timeout window — total wait is timeout_ms, not N × timeout_ms.
# ---------------------------------------------------------------------------

def wait_any_visible(locators: list, timeout_ms: int = 5_000) -> int:
    """
    Wait until ANY locator in the list becomes visible.

    Returns the index of the first visible locator, or -1 if none appeared
    within timeout_ms. Never raises.

    Useful for racing conditions:
        idx = wait_any_visible([success_banner, error_banner])
        if idx == 0: ...  # success
        if idx == 1: ...  # error
    """
    deadline = time.monotonic() + timeout_ms / 1_000
    while time.monotonic() < deadline:
        for i, loc in enumerate(locators):
            try:
                if loc.is_visible():
                    return i
            except Exception:
                pass
        time.sleep(0.1)
    return -1


def wait_all_visible(locators: list, timeout_ms: int = 5_000) -> bool:
    """
    Wait until ALL locators in the list are visible.

    Returns True when every locator is visible within timeout_ms.
    Returns False as soon as the deadline expires. Never raises.

    Useful for confirming a page is fully loaded before interacting:
        wait_all_visible([title, body, publish_btn])
    """
    deadline = time.monotonic() + timeout_ms / 1_000
    while time.monotonic() < deadline:
        try:
            if all(loc.is_visible() for loc in locators):
                return True
        except Exception:
            pass
        time.sleep(0.1)
    return False


def any_visible(locators: list) -> bool:
    """
    Return True immediately if ANY locator is currently visible.

    Synchronous snapshot — no waiting. Never raises.
    """
    for loc in locators:
        try:
            if loc.is_visible():
                return True
        except Exception:
            pass
    return False


def all_visible(locators: list) -> bool:
    """
    Return True immediately if ALL locators are currently visible.

    Synchronous snapshot — no waiting. Never raises.
    """
    for loc in locators:
        try:
            if not loc.is_visible():
                return False
        except Exception:
            return False
    return len(locators) > 0


def click_parallel(locators: list, timeout_ms: int = 3_000) -> list[bool]:
    """
    Click every locator that is visible within timeout_ms.

    All locators are attempted in a shared polling window — each is clicked
    the moment it becomes visible. Already-clicked locators are removed from
    the probe loop.

    Returns a list of bools — True for each locator that was clicked.
    Never raises.

    Useful for selecting multiple checkboxes or toggling multiple options:
        click_parallel([checkbox_a, checkbox_b, checkbox_c])
    """
    remaining = list(range(len(locators)))
    results   = [False] * len(locators)
    deadline  = time.monotonic() + timeout_ms / 1_000

    while remaining and time.monotonic() < deadline:
        still_pending = []
        for i in remaining:
            try:
                locators[i].wait_for(state="visible", timeout=200)
                locators[i].click()
                results[i] = True
            except Exception:
                still_pending.append(i)
        remaining = still_pending

    return results


def fill_parallel(pairs: list[tuple], timeout_ms: int = 5_000) -> list[bool]:
    """
    Fill multiple form fields simultaneously.

    ``pairs`` is a list of (locator, text) tuples. Each field is filled in a
    shared polling window — filled fields are removed from subsequent probes.

    Returns a list of bools — True for each field that was successfully filled.
    Never raises.

    Useful for login forms or multi-field forms:
        fill_parallel([(id_field, "user"), (pw_field, "pass")])
    """
    remaining = list(range(len(pairs)))
    results   = [False] * len(pairs)
    deadline  = time.monotonic() + timeout_ms / 1_000

    while remaining and time.monotonic() < deadline:
        still_pending = []
        for i in remaining:
            locator, text = pairs[i]
            try:
                locator.wait_for(state="visible", timeout=200)
                locator.fill(text)
                results[i] = True
            except Exception:
                still_pending.append(i)
        remaining = still_pending

    return results


def get_texts_parallel(locators: list, default: str = "") -> list[str]:
    """
    Read inner text from multiple locators at once.

    Returns a list of strings in the same order as ``locators``.
    Falls back to ``default`` for any locator that errors. Never raises.

    Useful for reading a row of table cells or a list of labels:
        texts = get_texts_parallel([cell_1, cell_2, cell_3])
    """
    results = []
    for loc in locators:
        try:
            results.append((loc.inner_text() or "").strip())
        except Exception:
            results.append(default)
    return results


def get_attributes_parallel(locators: list, name: str, default: str = "") -> list[str]:
    """
    Read the same attribute from multiple locators at once.

    Returns a list of attribute values in the same order as ``locators``.
    Falls back to ``default`` when attribute is absent or on error. Never raises.

    Useful for reading href from multiple links, or class from multiple buttons:
        hrefs   = get_attributes_parallel([link_1, link_2], "href")
        classes = get_attributes_parallel([btn_1, btn_2], "class")
    """
    results = []
    for loc in locators:
        try:
            results.append(loc.get_attribute(name) or default)
        except Exception:
            results.append(default)
    return results


def dismiss(locator, panel_locator=None, timeout_ms: int = 6_000) -> bool:
    """
    Click locator (single attempt), then optionally wait for panel to hide.

    Composition of click_if_visible + wait_until_hidden.
    Returns True if the element was clicked, False otherwise.
    """
    clicked = click_if_visible(locator, timeout_ms)
    if clicked and panel_locator is not None:
        wait_until_hidden(panel_locator)
    return clicked



def dismiss_parallel(locators: list, timeout_ms: int = 8_000) -> list[bool]:
    """
    Poll all locators simultaneously until each is clicked or deadline expires.

    All overlays are treated as unpredictably timed — one timeout window is
    shared across all of them. Each is probed on every cycle and clicked the
    moment it becomes visible.

    Returns a list of bools — True for each locator that was clicked.
    Never raises.

    Example:
        dismiss_parallel([draft_cancel, help_close], timeout_ms=8_000)
    """
    remaining = list(range(len(locators)))   # indices not yet clicked
    results   = [False] * len(locators)
    deadline  = time.monotonic() + timeout_ms / 1_000

    while remaining and time.monotonic() < deadline:
        still_pending = []
        for i in remaining:
            try:
                locators[i].wait_for(state="visible", timeout=200)
                locators[i].click()
                results[i] = True
            except Exception:
                still_pending.append(i)
        remaining = still_pending

    return results

def dismiss_polling(locator, panel_locator=None, timeout_ms: int = 6_000) -> bool:
    """
    Poll-click locator, then optionally wait for panel to hide.

    Use this for race-condition overlays that appear at unpredictable times.
    """
    clicked = click_polling(locator, timeout_ms)
    if clicked and panel_locator is not None:
        wait_until_hidden(panel_locator)
    return clicked


# ---------------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------------

def js_dispatch_click(js_frame, css: str, index: int) -> str:
    """
    Fire a MouseEvent on the nth element matching css via JS dispatchEvent.

    Uses document.querySelectorAll — does NOT pierce shadow DOM.
    Use locator_dispatch_click instead when elements live inside shadow DOM.

    Returns:
        'selected'     — element gained 'se-is-selected' class after click
        'not-selected' — event fired but class not set
        'index N out of range (M elements)' — index too large
    """
    return js_frame.evaluate(
        """([css, idx]) => {
            const els = document.querySelectorAll(css);
            if (idx >= els.length)
                return `index ${idx} out of range (${els.length} elements)`;
            els[idx].dispatchEvent(
                new MouseEvent('click', {bubbles: true, cancelable: true})
            );
            return els[idx].classList.contains('se-is-selected')
                ? 'selected' : 'not-selected';
        }""",
        [css, index],
    )


def locator_dispatch_click(locator, index: int = 0) -> str:
    """
    Fire a MouseEvent via Playwright locator.evaluate — pierces shadow DOM.

    Use this instead of js_dispatch_click when elements live inside shadow DOM
    (querySelectorAll cannot find them, but Playwright locator can).

    The locator should already be scoped to the right frame/context.

    Returns:
        'selected'     — element gained 'se-is-selected' class after click
        'not-selected' — event fired but class not set
        'error: ...'   — exception message
    Never raises.
    """
    try:
        return locator.nth(index).evaluate("""el => {
            el.dispatchEvent(
                new MouseEvent('click', {bubbles: true, cancelable: true})
            );
            return el.classList.contains('se-is-selected')
                ? 'selected' : 'not-selected';
        }""")
    except Exception as e:
        return f"error: {e}"


def js_evaluate(js_frame, expression: str, arg: Any = None) -> Any:
    """
    Evaluate a JavaScript expression and return the result.

    ``arg`` is passed as the first argument to the JS function.
    Returns None on any error. Never raises.

    Example:
        count = js_evaluate(frame, "() => document.querySelectorAll('img').length")
        text  = js_evaluate(frame, "(sel) => document.querySelector(sel)?.innerText", "h1")
    """
    try:
        if arg is None:
            return js_frame.evaluate(expression)
        return js_frame.evaluate(expression, arg)
    except Exception:
        return None


def js_scroll_into_view(js_frame, css: str, index: int = 0) -> bool:
    """
    Scroll the nth element matching css into view via JS scrollIntoView.

    Useful when Playwright's scroll_into_view_if_needed doesn't work
    inside a custom scroll container.
    Returns True on success, False otherwise.
    """
    result = js_evaluate(
        js_frame,
        """([css, idx]) => {
            const els = document.querySelectorAll(css);
            if (idx >= els.length) return false;
            els[idx].scrollIntoView({behavior: 'smooth', block: 'center'});
            return true;
        }""",
        [css, index],
    )
    return result is True


# ---------------------------------------------------------------------------
# Frame resolution
# ---------------------------------------------------------------------------

def find_editor_frame(page: Any, main_frame_selector: str, editor_body_selector: str):
    """
    Detect whether the Smart Editor lives inside an iframe or directly on page.

    Probes for main_frame_selector within 1 s. Returns the FrameLocator
    when found, the page itself as fallback (no iframe case).
    """
    try:
        page.frame_locator(main_frame_selector) \
            .locator(editor_body_selector) \
            .wait_for(state="visible", timeout=1_000)
        return page.frame_locator(main_frame_selector).first
    except Exception:
        return page


def find_js_frame(page: Any, url_fragment: str = ""):
    """
    Return the Frame object needed for JavaScript evaluate() calls.

    FrameLocator does not expose evaluate(). When url_fragment is given,
    finds the frame whose URL contains that fragment (stable across
    dynamically added frames). Falls back to the first non-main frame,
    then main_frame.

    Args:
        page:         Playwright Page object.
        url_fragment: Optional URL substring to pin the target frame
                      (e.g. "PostWriteForm" for the Naver editor iframe).
                      Prevents stale frame references when the browser
                      adds/removes frames during file uploads.
    """
    if url_fragment:
        match = next(
            (f for f in page.frames if url_fragment in f.url),
            None,
        )
        if match:
            return match
    return next(
        (f for f in page.frames if f != page.main_frame),
        page.main_frame,
    )
