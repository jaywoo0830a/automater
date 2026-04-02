"""
api/vnc_session.py
-------------------
VNC 기반 원격 로그인 세션 관리.

Xvfb(가상 디스플레이) + Chromium(headed) + x11vnc + websockify 조합으로
웹 브라우저에서 원격 로그인을 수행한다.

흐름:
    1. Xvfb 시작 (가상 디스플레이)
    2. Playwright Chromium 실행 (headless=False, DISPLAY=:N)
    3. x11vnc → websockify 로 WebSocket 노출
    4. 프론트엔드 noVNC로 원격 브라우저 표시
    5. 사용자가 로그인 완료 → 세션 저장 → 전체 종료
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

LOGIN_URL = "https://nid.naver.com/nidlogin.login"
_MONITOR_TIMEOUT = 300  # 5분
_POLL_INTERVAL = 2


_WS_PORT_RANGE = range(6080, 6090)
_used_ws_ports: set[int] = set()


def _find_free_port(restrict: bool = False) -> int:
    """포트를 할당한다. restrict=True이면 6080-6089 범위 내에서만."""
    if restrict:
        for port in _WS_PORT_RANGE:
            if port in _used_ws_ports:
                continue
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("", port))
                    _used_ws_ports.add(port)
                    return port
                except OSError:
                    continue
        raise RuntimeError("No free websockify port in 6080-6089")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _find_free_display() -> int:
    for n in range(99, 200):
        lock = Path(f"/tmp/.X{n}-lock")
        if not lock.exists():
            return n
    raise RuntimeError("No free X display found")


class VncLoginSession:
    """하나의 VNC 로그인 세션."""

    def __init__(self, account: dict[str, Any], config: dict[str, Any] | None = None) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.account = account
        self.config = config or {}
        self.status = "starting"
        self.websockify_port: int = 0
        self.error: str = ""

        self._display: int = 0
        self._vnc_port: int = 0
        self._xvfb_proc: subprocess.Popen | None = None
        self._vnc_proc: subprocess.Popen | None = None
        self._ws_proc: subprocess.Popen | None = None
        self._pw = None
        self._context = None
        self._page = None
        self._ext_dir: str = ""
        self._user_data_dir: str = ""
        self._lock = threading.Lock()

    def start(self) -> None:
        """VNC 세션을 백그라운드에서 시작한다."""
        thread = threading.Thread(target=self._start_internal, daemon=True)
        thread.start()

    def _start_internal(self) -> None:
        try:
            self._display = _find_free_display()
            self._vnc_port = _find_free_port()
            self.websockify_port = _find_free_port(restrict=True)

            display_str = f":{self._display}"
            env = {**os.environ, "DISPLAY": display_str}

            # 2. Playwright 설정 로드 (Xvfb 해상도에 필요)
            from playwright.sync_api import sync_playwright
            from automator.browser import DEFAULT_BROWSER_CONFIG, merge_browser_config

            browser_cfg = self.config.get("browser", {})
            cfg = merge_browser_config(DEFAULT_BROWSER_CONFIG, browser_cfg)
            viewport_raw = cfg.get("viewport", [1920, 1080])
            if isinstance(viewport_raw, (list, tuple)) and len(viewport_raw) >= 2:
                xvfb_w, xvfb_h = int(viewport_raw[0]), int(viewport_raw[1])
            else:
                xvfb_w, xvfb_h = 1920, 1080

            # 1. Xvfb (DSL viewport 해상도에 맞춤)
            self._xvfb_proc = subprocess.Popen(
                ["Xvfb", display_str, "-screen", "0", f"{xvfb_w}x{xvfb_h}x24", "-ac"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1)

            from cli.session_manager import _build_login_ext
            from automator.stealth import build_stealth_script

            self._ext_dir = _build_login_ext(
                self.account["username"],
                self.account["password"],
            )
            self._user_data_dir = tempfile.mkdtemp(prefix="vnc_profile_")

            locale = str(cfg.get("locale", "ko-KR"))
            timezone = str(cfg.get("timezone", "Asia/Seoul"))
            lang = locale.split("-")[0] if "-" in locale else locale.split("_")[0]

            viewport_raw = cfg.get("viewport", [1920, 1080])
            if isinstance(viewport_raw, (list, tuple)) and len(viewport_raw) >= 2:
                viewport = {"width": int(viewport_raw[0]), "height": int(viewport_raw[1])}
            else:
                viewport = {"width": 1920, "height": 1080}

            ctx_kwargs = {
                "headless": False,
                "locale": locale,
                "timezone_id": timezone,
                "viewport": viewport,
                "color_scheme": cfg.get("color_scheme", "light"),
                "device_scale_factor": int(cfg.get("device_scale_factor", 1)),
                "args": [
                    f"--disable-extensions-except={self._ext_dir}",
                    f"--load-extension={self._ext_dir}",
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                ],
                "env": {**env},
                "extra_http_headers": {
                    "Accept-Language": f"{locale},{lang};q=0.9",
                },
            }

            ua = cfg.get("user_agent")
            if ua:
                ctx_kwargs["user_agent"] = str(ua)

            geo = cfg.get("geolocation")
            if isinstance(geo, (list, tuple)) and len(geo) >= 2:
                ctx_kwargs["geolocation"] = {
                    "latitude": float(geo[0]),
                    "longitude": float(geo[1]),
                }
                ctx_kwargs["permissions"] = ["geolocation"]

            self._pw = sync_playwright().start()
            self._context = self._pw.chromium.launch_persistent_context(
                self._user_data_dir,
                **ctx_kwargs,
            )

            # stealth script (fingerprint 위장)
            fingerprint = cfg.get("fingerprint", {})
            stealth = build_stealth_script(fingerprint, locale)
            if stealth:
                self._context.add_init_script(stealth)

            self._page = self._context.new_page()
            self._page.goto(LOGIN_URL, wait_until="domcontentloaded")

            # 3. x11vnc
            self._vnc_proc = subprocess.Popen(
                [
                    "x11vnc",
                    "-display", display_str,
                    "-nopw", "-shared", "-forever",
                    "-rfbport", str(self._vnc_port),
                    "-noxdamage",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.5)

            # 4. websockify
            self._ws_proc = subprocess.Popen(
                [
                    "websockify",
                    "--web", "/usr/share/novnc",
                    str(self.websockify_port),
                    f"localhost:{self._vnc_port}",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.5)

            self.status = "ready"
            log.info("[vnc:%s] ready (display=%s, ws_port=%d)", self.id, display_str, self.websockify_port)

            # 5. 로그인 감지 모니터
            self._monitor_login()

        except Exception as exc:
            self.status = "failed"
            self.error = str(exc)
            log.error("[vnc:%s] start failed: %s", self.id, exc)
            self.teardown()

    def _monitor_login(self) -> None:
        """로그인 완료를 감지하여 세션을 저장한다."""
        username = self.account["username"]
        blog_id = self.account.get("blog_id", username)
        write_url = f"https://blog.naver.com/{blog_id}?Redirect=Write&"

        deadline = time.time() + _MONITOR_TIMEOUT
        log.info("[vnc:%s] monitoring login for %s (timeout=%ds)", self.id, username, _MONITOR_TIMEOUT)

        while time.time() < deadline:
            if self.status not in ("ready",):
                return

            try:
                # page.url 대신 JS로 직접 URL 확인 (VNC 사용자 상호작용 반영)
                url = self._page.evaluate("window.location.href")
                log.debug("[vnc:%s] current url: %s", self.id, url)

                if "nidlogin" not in url and "naver.com" in url:
                    log.info("[vnc:%s] login detected, verifying session...", self.id)
                    time.sleep(3)  # 쿠키 전파 대기

                    # 새 탭에서 블로그 접속하여 세션 확인
                    check_page = self._context.new_page()
                    try:
                        check_page.goto(write_url, wait_until="domcontentloaded", timeout=15_000)
                        time.sleep(2)
                        check_url = check_page.evaluate("window.location.href")
                        log.info("[vnc:%s] verify url: %s", self.id, check_url)

                        if "nidlogin" in check_url:
                            log.warning("[vnc:%s] session not valid yet, retrying...", self.id)
                            check_page.close()
                            time.sleep(_POLL_INTERVAL)
                            continue

                        # 세션 유효 — 저장
                        state = self._context.storage_state()
                        check_page.close()
                        self._save_session(state)
                        self.status = "logged_in"
                        log.info("[vnc:%s] login success for %s", self.id, username)
                        time.sleep(2)
                        self.teardown()
                        return
                    except Exception as exc:
                        log.warning("[vnc:%s] verify failed: %s", self.id, exc)
                        try:
                            check_page.close()
                        except Exception:
                            pass
            except Exception as exc:
                log.debug("[vnc:%s] monitor error: %s", self.id, exc)

            time.sleep(_POLL_INTERVAL)

        # 타임아웃
        self.status = "failed"
        self.error = "login timeout"
        log.warning("[vnc:%s] login timeout for %s", self.id, username)
        self.teardown()

    def _save_session(self, state: dict) -> None:
        """세션을 FileSessionStore에 저장한다."""
        from cli.session_store import create_session_store

        store_cfg = self.config.get("session_store", "")
        base_dir = self.config.get("_base_dir", ".")
        store = create_session_store(store_cfg, base_dir=base_dir)

        username = self.account["username"]
        explicit = self.account.get("session", "")

        if explicit and hasattr(store, "save_path"):
            store.save_path(explicit, state)
        else:
            store.save(username, state)

    def teardown(self) -> None:
        """모든 프로세스를 정리한다."""
        with self._lock:
            for proc in (self._ws_proc, self._vnc_proc, self._xvfb_proc):
                if proc:
                    try:
                        proc.terminate()
                        proc.wait(timeout=3)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass

            if self._context:
                try:
                    self._context.close()
                except Exception:
                    pass
            if self._pw:
                try:
                    self._pw.stop()
                except Exception:
                    pass

            if self._ext_dir:
                shutil.rmtree(self._ext_dir, ignore_errors=True)
            if self._user_data_dir:
                shutil.rmtree(self._user_data_dir, ignore_errors=True)

            self._xvfb_proc = None
            self._vnc_proc = None
            self._ws_proc = None
            self._context = None
            self._pw = None
            self._page = None

            _used_ws_ports.discard(self.websockify_port)

            if self.status == "ready":
                self.status = "closed"

    def to_dict(self) -> dict:
        return {
            "session_id": self.id,
            "status": self.status,
            "websockify_port": self.websockify_port,
            "username": self.account.get("username", ""),
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Module-level registry
# ---------------------------------------------------------------------------

_sessions: dict[str, VncLoginSession] = {}
_sessions_lock = threading.Lock()


def create_vnc_session(account: dict[str, Any], config: dict[str, Any] | None = None) -> VncLoginSession:
    session = VncLoginSession(account, config)
    with _sessions_lock:
        _sessions[session.id] = session
    session.start()
    return session


def get_vnc_session(session_id: str) -> VncLoginSession | None:
    return _sessions.get(session_id)


def delete_vnc_session(session_id: str) -> bool:
    session = _sessions.get(session_id)
    if not session:
        return False
    session.teardown()
    return True
