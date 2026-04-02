"""
cli/session_manager.py
-----------------------
세션 생명주기 관리.

책임:
    validate        -세션 유효성 확인 (headless 네이버 접속)
    assisted_login  -브라우저 열고 ID/PW 복사 툴바(확장 프로그램) 표시 → 사용자가 직접 로그인
    ensure          -validate → assisted_login 순차 시도
    recover         -작업 중 세션 만료 시 복구

사용:
    mgr = SessionManager(session_store, playwright, browser_config)
    state = mgr.ensure(account)          # 유효한 세션 반환 (없으면 로그인)
    state = mgr.recover(account)         # 작업 중 만료 시 재시도
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from automator.browser import build_context, merge_browser_config

log = logging.getLogger(__name__)

LOGIN_URL = "https://nid.naver.com/nidlogin.login"

# 세션 만료 판단용 URL 패턴
SESSION_EXPIRED_PATTERNS = ("nidlogin", "sso/cross-domain", "login")

_MANIFEST_JSON = json.dumps({
    "manifest_version": 3,
    "name": "Login Helper",
    "version": "1.0",
    "permissions": ["clipboardWrite"],
    "content_scripts": [{
        "matches": ["*://nid.naver.com/*"],
        "js": ["content.js"],
        "run_at": "document_idle",
    }],
}, ensure_ascii=False)


def is_session_error(url: str = "", error_msg: str = "") -> bool:
    """URL이나 에러 메시지로 세션 만료를 판단한다."""
    text = (url + " " + error_msg).lower()
    return any(p in text for p in SESSION_EXPIRED_PATTERNS)


def _build_login_ext(username: str, password: str) -> str:
    """credentials가 포함된 임시 확장 프로그램 디렉터리를 생성하고 경로를 반환한다."""
    tmp_dir = tempfile.mkdtemp(prefix="login_helper_")

    # manifest.json 인라인 생성
    (Path(tmp_dir) / "manifest.json").write_text(_MANIFEST_JSON, encoding="utf-8")

    # content.js — Ctrl+V 순차 붙여넣기: 1회차=ID, 2회차=PW
    content_js = f"""\
(function() {{
    if (window.__loginHelperLoaded) return;
    window.__loginHelperLoaded = true;

    var creds = [{json.dumps(username)}, {json.dumps(password)}];
    var pasteCount = 0;

    document.addEventListener('paste', function(e) {{
        if (pasteCount >= creds.length) return;
        e.preventDefault();
        e.stopImmediatePropagation();

        var value = creds[pasteCount];
        var el = document.activeElement;

        if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {{
            // input/textarea — 직접 값 설정 + input 이벤트 발생
            var nativeSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            ).set;
            nativeSetter.call(el, value);
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }} else if (el && el.isContentEditable) {{
            document.execCommand('insertText', false, value);
        }}

        pasteCount++;
    }}, true);

    // 클립보드에 빈 텍스트라도 넣어서 Ctrl+V가 paste 이벤트를 발생시키도록 함
    if (navigator.clipboard && navigator.clipboard.writeText) {{
        navigator.clipboard.writeText(' ').catch(function() {{}});
    }}
}})();
"""
    (Path(tmp_dir) / "content.js").write_text(content_js, encoding="utf-8")
    return tmp_dir


class SessionManager:
    """세션 생명주기 관리자."""

    def __init__(
        self,
        session_store,
        playwright,
        global_browser_config: dict[str, Any] | None = None,
    ) -> None:
        self._store = session_store
        self._pw = playwright
        self._global_browser_cfg = global_browser_config or {}
        self._max_manual_wait_ms = 300_000  # 5분

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ensure(self, account: dict[str, Any]) -> dict:
        """유효한 세션을 반환한다. 없으면 로그인 과정을 거친다.

        순서: 기존 세션 로드 → 유효성 확인 → assisted_login
        """
        username = account["username"]
        cfg = self._resolve_config(account)

        # 1. 기존 세션 로드
        blog_id = account.get("blog_id", username)
        state = self._load(account)
        if state and self.validate(state, blog_id, cfg):
            log.info("[%s] 세션 유효 -재사용", username)
            return state

        if state:
            log.info("[%s] 세션 만료 -갱신 필요", username)
        else:
            log.info("[%s] 세션 없음 -로그인 필요", username)

        # 2. 수동 로그인 (브라우저 + 확장 프로그램 ID/PW 복사 툴바)
        state = self.assisted_login(account, cfg)
        if state and self.validate(state, blog_id, cfg):
            self._save(account, state)
            log.info("[%s] 로그인 성공", username)
            return state

        raise RuntimeError(f"[{username}] 로그인 실패 — 세션을 확보할 수 없습니다")

    def recover(self, account: dict[str, Any]) -> dict:
        """작업 중 세션 만료 시 복구. ensure와 동일하지만 로그 메시지가 다르다."""
        username = account["username"]
        log.warning("[%s] 세션 만료 감지 -복구 시도", username)
        return self.ensure(account)

    def validate(
        self,
        state: dict,
        blog_id: str,
        browser_config: dict[str, Any] | None = None,
    ) -> bool:
        """세션이 아직 유효한지 headless로 확인.

        실제 글쓰기 페이지(blog.naver.com/{blog_id}?Redirect=Write&)에 접속하여
        nidlogin으로 리다이렉트되면 만료로 판단한다.
        """
        check_url = f"https://blog.naver.com/{blog_id}?Redirect=Write&"
        try:
            browser = self._pw.chromium.launch(headless=True)
            ctx = build_context(browser, browser_config, storage_state=state)
            page = ctx.new_page()
            page.goto(check_url, wait_until="domcontentloaded", timeout=15_000)

            logged_in = "nidlogin" not in page.url

            page.close()
            ctx.close()
            browser.close()
            return logged_in
        except Exception as exc:
            log.debug("validate 실패: %s", exc)
            return False

    @staticmethod
    def _has_display() -> bool:
        """GUI 브라우저를 띄울 수 있는 환경인지 확인."""
        if sys.platform == "win32" or sys.platform == "darwin":
            return True
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

    def assisted_login(self, account: dict[str, Any], browser_config: dict[str, Any] | None = None) -> dict | None:
        """브라우저를 열고 확장 프로그램으로 ID/PW 복사 툴바를 표시한 뒤, 사용자가 직접 로그인을 완료한다."""
        username = account["username"]

        if not self._has_display():
            log.error(
                "[%s] 디스플레이 없음 — assisted_login 불가.\n"
                "  해결 방법:\n"
                "    1) 로컬에서 세션 준비 후 서버로 복사:\n"
                "       python -m cli campaign.yaml --prepare\n"
                "       python -m cli --export-sessions ./sessions_backup/\n"
                "       scp -r ./sessions_backup/ server:~/automator/\n"
                "       python -m cli --import-sessions ./sessions_backup/\n"
                "    2) X11 포워딩: ssh -X user@server\n"
                "    3) DISPLAY 환경변수 설정 (VNC/xvfb 사용 시)",
                username,
            )
            return None
        blog_id = account.get("blog_id", username)
        write_url = f"https://blog.naver.com/{blog_id}?Redirect=Write&"

        # 임시 확장 프로그램 생성
        ext_dir = _build_login_ext(account["username"], account["password"])

        # persistent context — 확장 프로그램은 이 방식에서만 동작
        user_data_dir = tempfile.mkdtemp(prefix="login_profile_")

        try:
            ctx = self._pw.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,
                args=[
                    f"--disable-extensions-except={ext_dir}",
                    f"--load-extension={ext_dir}",
                ],
            )
            page = ctx.new_page()

            # 1. 로그인 페이지 로딩 (확장 프로그램이 자동으로 툴바 삽입)
            page.goto(LOGIN_URL, wait_until="domcontentloaded")

            log.info("[%s] 브라우저 열림 — 직접 로그인해주세요", username)
            print(f"          >> 브라우저가 열렸습니다. 직접 로그인해주세요. ({username})")

            # 2. 사용자가 로그인할 때까지 대기 (최대 5분)
            page.wait_for_url(
                lambda url: "nidlogin" not in url and "naver.com" in url,
                timeout=self._max_manual_wait_ms,
            )

            # 3. 블로그 글쓰기 URL로 이동하여 세션 확인
            page.goto(write_url, wait_until="domcontentloaded", timeout=15_000)
            page.wait_for_timeout(3_000)

            if "nidlogin" in page.url:
                log.warning("[%s] 로그인 후 블로그 접속 시 세션 무효 (url=%s)", username, page.url)
                page.close()
                ctx.close()
                return None

            state = ctx.storage_state()
            page.close()
            ctx.close()
            return state
        except Exception as exc:
            log.warning("[%s] 로그인 실패: %s", username, exc)
            try:
                ctx.close()
            except Exception:
                pass
            return None
        finally:
            shutil.rmtree(ext_dir, ignore_errors=True)
            shutil.rmtree(user_data_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_config(self, account: dict[str, Any]) -> dict[str, Any]:
        """글로벌 browser config + 계정별 오버라이드 머지."""
        return merge_browser_config(self._global_browser_cfg, account.get("browser"))

    def _load(self, account: dict[str, Any]) -> dict | None:
        username = account["username"]
        explicit_path = account.get("session", "")
        if explicit_path and hasattr(self._store, "load_path"):
            return self._store.load_path(explicit_path)
        return self._store.load(username)

    def _save(self, account: dict[str, Any], state: dict) -> None:
        username = account["username"]
        explicit_path = account.get("session", "")
        if explicit_path and hasattr(self._store, "save_path"):
            self._store.save_path(explicit_path, state)
        else:
            self._store.save(username, state)
