"""
automator/stealth.py
--------------------
브라우저 핑거프린트 위장 스크립트 생성.

DSL fingerprint 설정에 따라 개별 init script를 조합한다.

지원 항목:
    webdriver       — navigator.webdriver → false
    plugins         — navigator.plugins 위장 (Chrome 기본 플러그인)
    chrome_runtime  — window.chrome.runtime 존재 위장
    languages       — navigator.languages를 locale에 맞게 설정
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Individual script fragments
# ---------------------------------------------------------------------------

_WEBDRIVER_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {
    get: () => false,
});
"""

_PLUGINS_SCRIPT = """
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            { name: 'Chrome PDF Plugin', description: 'Portable Document Format', filename: 'internal-pdf-viewer', length: 1 },
            { name: 'Chrome PDF Viewer', description: '', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', length: 1 },
            { name: 'Native Client', description: '', filename: 'internal-nacl-plugin', length: 2 },
        ];
        plugins.length = 3;
        return plugins;
    },
});
"""

_CHROME_RUNTIME_SCRIPT = """
if (!window.chrome) {
    window.chrome = {};
}
if (!window.chrome.runtime) {
    window.chrome.runtime = {
        connect: function() {},
        sendMessage: function() {},
    };
}
"""

_LANGUAGES_TEMPLATE = """
Object.defineProperty(navigator, 'languages', {{
    get: () => {languages},
}});
"""


# ---------------------------------------------------------------------------
# Default fingerprint config
# ---------------------------------------------------------------------------

DEFAULT_FINGERPRINT = {
    "webdriver": False,
    "plugins": True,
    "chrome_runtime": True,
    "languages": True,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_stealth_script(
    fingerprint: dict | None = None,
    locale: str = "ko-KR",
) -> str:
    """fingerprint 설정에 따라 init script 문자열을 조합한다.

    Args:
        fingerprint: DSL fingerprint dict. None이면 DEFAULT_FINGERPRINT 사용.
        locale:      navigator.languages에 사용할 locale.

    Returns:
        Playwright add_init_script()에 전달할 JavaScript 문자열.
        빈 문자열이면 주입할 것 없음.
    """
    cfg = {**DEFAULT_FINGERPRINT, **(fingerprint or {})}
    parts: list[str] = []

    if not cfg.get("webdriver", True):
        # webdriver: false → navigator.webdriver를 false로 위장
        parts.append(_WEBDRIVER_SCRIPT)

    if cfg.get("plugins", False):
        parts.append(_PLUGINS_SCRIPT)

    if cfg.get("chrome_runtime", False):
        parts.append(_CHROME_RUNTIME_SCRIPT)

    if cfg.get("languages", False):
        lang = locale.split("-")[0] if "-" in locale else locale.split("_")[0]
        languages = f'["{locale}", "{lang}"]'
        parts.append(_LANGUAGES_TEMPLATE.format(languages=languages))

    return "\n".join(parts)
