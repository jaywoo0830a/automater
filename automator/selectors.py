"""
automator/selectors.py
----------------------
Central repository for all Playwright selectors used in Naver Blog automation.

Naver Smart Editor uses dynamically generated class names and UUIDs, so selectors
are expected to change periodically. Update this file when selectors break —
no other file needs to change.

Selector strategy priority (most to least stable):
  1. data-testid attributes   — rarely change, intentionally stable
  2. XPath structural paths   — changes only when DOM structure changes
  3. CSS class names          — may change on any deployment (use as fallback)
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# iframe
# ---------------------------------------------------------------------------

# The main iframe wrapping the Smart Editor
MAIN_FRAME = "#mainFrame"


# ---------------------------------------------------------------------------
# Editor content area
# ---------------------------------------------------------------------------

# Stable class on the editor root — used to confirm the editor has loaded
EDITOR_CONTENT = ".se-content"

# Placeholder spans appear in DOM order: nth(0) = title, nth(1) = body
# Targets the stable class pattern, avoiding all UUIDs entirely
PLACEHOLDER = "span.se-placeholder.__se_placeholder"


# ---------------------------------------------------------------------------
# Title input
# ---------------------------------------------------------------------------

# XPath to the title placeholder span (inside the iframe)
# Update when the editor DOM structure changes
TITLE_XPATH = (
    "xpath=//html[1]/body[1]/div[1]/div[1]/div[3]/div[1]"
    "/div[1]/div[1]/div[1]/div[1]/div[2]/section[1]/article[1]"
    "/div[1]/div[1]/div[1]/div[1]/p[1]/span[2]"
)


# ---------------------------------------------------------------------------
# Body input
# ---------------------------------------------------------------------------

# XPath to the body placeholder span (inside the iframe)
# Update when the editor DOM structure changes
BODY_XPATH = (
    "xpath=//html[1]/body[1]/div[1]/div[1]/div[3]/div[1]"
    "/div[1]/div[1]/div[1]/div[1]/div[2]/section[1]/article[1]"
    "/div[2]/div[1]/div[1]/div[1]/div[1]/p[1]/span[2]"
)


# ---------------------------------------------------------------------------
# Publish flow
# ---------------------------------------------------------------------------

# Button that opens the publish popover (inside the iframe)
# XPath is more stable than the dynamic CSS class names here
PUBLISH_TRIGGER_XPATH = (
    "xpath=//html[1]/body[1]/div[1]/div[1]/div[1]/div[1]"
    "/div[3]/div[2]/button[1]"
)

# The actual publish confirm button inside the popover
# data-testid is the most stable selector available — prefer it
PUBLISH_CONFIRM_TESTID = "seOnePublishBtn"

# Fallback XPath for the confirm button if data-testid changes
PUBLISH_CONFIRM_XPATH = (
    "xpath=//html[1]/body[1]/div[1]/div[1]/div[1]/div[1]"
    "/div[3]/div[2]/div[1]/div[1]/div[1]/div[8]/div[1]/button[1]"
)


# ---------------------------------------------------------------------------
# Image upload
# ---------------------------------------------------------------------------

# Button that opens the OS file chooser dialog for image upload (inside the iframe)
IMAGE_UPLOAD_TRIGGER_XPATH = (
    "xpath=//html[1]/body[1]/div[1]/div[1]/div[3]/div[1]"
    "/div[1]/div[1]/div[1]/header[1]/div[1]/ul[1]/li[1]/button[1]"
)

# CSS selector for an uploaded image inside the editor content area
# Used to verify that the image was successfully inserted
UPLOADED_IMAGE = ".se-image-resource"


# ---------------------------------------------------------------------------
# Representative (thumbnail) image
# ---------------------------------------------------------------------------

# All "대표" toggle buttons — one per uploaded image (inside the iframe)
REP_IMAGE_BUTTON = "button.se-set-rep-image-button"

# The currently active representative image button (green badge)
# Presence of .se-is-selected distinguishes active vs inactive
REP_IMAGE_BUTTON_SELECTED = "button.se-set-rep-image-button.se-is-selected"
