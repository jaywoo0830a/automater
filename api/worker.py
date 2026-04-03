"""
api/worker.py
--------------
캠페인 실행 워커.

각 캠페인을 subprocess로 실행하고 상태를 추적한다.
로그는 메모리 버퍼에 저장되며 WebSocket으로 스트리밍된다.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import yaml


class Status(str, Enum):
    PENDING_SESSIONS = "pending_sessions"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


_VNC_PORT_RANGE = range(6090, 6100)
_WS_PORT_RANGE = range(6080, 6090)
_used_ports: set[int] = set()


def _alloc_port(port_range: range) -> int:
    for port in port_range:
        if port in _used_ports:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                _used_ports.add(port)
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port in {port_range.start}-{port_range.stop}")


def _free_port(port: int) -> None:
    _used_ports.discard(port)


@dataclass
class Campaign:
    """실행 중인 캠페인 상태."""
    id: str
    config_path: str
    workspace: str
    status: Status = Status.PENDING_SESSIONS
    log_lines: list[str] = field(default_factory=list)
    exit_code: int | None = None
    created_at: float = field(default_factory=time.time)
    vnc_port: int = 0
    _proc: subprocess.Popen | None = field(default=None, repr=False)
    _vnc_procs: list = field(default_factory=list, repr=False)
    _listeners: list[Callable[[str], None]] = field(default_factory=list, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add_listener(self, fn: Callable[[str], None]) -> None:
        with self._lock:
            self._listeners.append(fn)

    def remove_listener(self, fn: Callable[[str], None]) -> None:
        with self._lock:
            self._listeners = [f for f in self._listeners if f is not fn]

    def _emit(self, line: str) -> None:
        with self._lock:
            self.log_lines.append(line)
            for fn in self._listeners:
                try:
                    fn(line)
                except Exception:
                    pass

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status.value,
            "config_path": self.config_path,
            "exit_code": self.exit_code,
            "log_length": len(self.log_lines),
            "created_at": self.created_at,
            "vnc_port": self.vnc_port,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_windows_abs(path: str) -> bool:
    """윈도우 절대 경로인지 확인."""
    return len(path) >= 3 and path[1] == ":" and path[2] in ("/", "\\")


def parse_campaign_accounts(config_path: str) -> list[dict[str, Any]]:
    """캠페인 YAML에서 accounts 목록을 추출한다."""
    raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    return raw.get("accounts", [])


def check_sessions(config_path: str, workspace: str, validate: bool = True) -> dict[str, Any]:
    """캠페인의 각 계정에 대해 세션 유효성을 확인한다.

    validate=True이면 headless 브라우저로 실제 로그인 상태를 검증한다.
    validate=False이면 파일 존재 여부만 확인한다.
    """
    accounts = parse_campaign_accounts(config_path)
    sessions_dir = Path(workspace) / "sessions"
    results = []

    for acc in accounts:
        username = acc.get("username", "")
        blog_id = acc.get("blog_id", username)
        has_session = False
        session_file = _find_session_file(sessions_dir, username)

        if session_file and validate:
            has_session = _validate_session(session_file, blog_id)
            # 무효한 세션 파일 삭제
            if not has_session:
                session_file.unlink(missing_ok=True)
        elif session_file:
            has_session = True

        results.append({
            "username": username,
            "blog_id": blog_id,
            "has_session": has_session,
        })

    return {
        "accounts": results,
        "all_ready": all(r["has_session"] for r in results),
    }


def _find_session_file(sessions_dir: Path, username: str) -> Path | None:
    """sessions/ 디렉터리에서 해당 username의 세션 파일을 찾는다."""
    if not sessions_dir.is_dir():
        return None
    for f in sessions_dir.iterdir():
        if f.is_file() and username in f.stem:
            return f
    return None


def _validate_session(session_file: Path, blog_id: str) -> bool:
    """headless 브라우저로 세션의 실제 유효성을 검증한다."""
    import json as _json
    try:
        state = _json.loads(session_file.read_text(encoding="utf-8"))
    except Exception:
        return False

    check_url = f"https://blog.naver.com/{blog_id}?Redirect=Write&"
    try:
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(storage_state=state)
        page = ctx.new_page()
        page.goto(check_url, wait_until="domcontentloaded", timeout=15_000)
        valid = "nidlogin" not in page.url
        page.close()
        ctx.close()
        browser.close()
        pw.stop()
        return valid
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class Worker:
    """캠페인 실행 워커. 스레드 기반."""

    def __init__(self) -> None:
        self._campaigns: dict[str, Campaign] = {}
        self._lock = threading.Lock()

    def register(self, campaign_id: str, config_path: str, workspace: str) -> Campaign:
        """캠페인을 등록한다. 세션 확인 후 execute로 실행."""
        # sessions/ 디렉터리 보장
        (Path(workspace) / "sessions").mkdir(exist_ok=True)

        campaign = Campaign(
            id=campaign_id,
            config_path=config_path,
            workspace=workspace,
            status=Status.PENDING_SESSIONS,
        )
        with self._lock:
            self._campaigns[campaign_id] = campaign
        return campaign

    def execute(self, campaign_id: str) -> Campaign | None:
        """세션 준비 완료된 캠페인을 실행한다."""
        campaign = self._campaigns.get(campaign_id)
        if not campaign:
            return None

        campaign.status = Status.QUEUED
        thread = threading.Thread(
            target=self._run,
            args=(campaign,),
            daemon=True,
        )
        thread.start()
        return campaign

    def get(self, campaign_id: str) -> Campaign | None:
        return self._campaigns.get(campaign_id)

    def list_all(self) -> list[Campaign]:
        return list(self._campaigns.values())

    def cancel(self, campaign_id: str) -> bool:
        """실행 중인 캠페인을 중단한다."""
        campaign = self._campaigns.get(campaign_id)
        if not campaign or campaign._proc is None:
            return False

        try:
            campaign._proc.terminate()
            campaign._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            campaign._proc.kill()
            campaign._proc.wait(timeout=3)
        except Exception:
            pass

        campaign.status = Status.CANCELLED
        campaign._emit("[중단됨]\n")
        return True

    @staticmethod
    def _patch_config(config_path: str) -> None:
        """워크스페이스 환경에 맞게 YAML 설정을 패치한다.

        1. 세션 경로를 워크스페이스 sessions/ 내 파일로 교체
        2. assets 경로를 워크스페이스 기준 상대 경로로 교체
        3. YAML 내 윈도우 절대 경로를 워크스페이스 내 파일로 교체
        """
        import re

        config_file = Path(config_path)
        workspace = config_file.parent

        raw = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
        changed = False

        # 1. 세션 패치
        sessions_dir = workspace / "sessions"
        if sessions_dir.is_dir():
            raw["session_store"] = "file"
            for acc in raw.get("accounts", []):
                username = acc.get("username", "")
                if not username:
                    continue
                for candidate in sessions_dir.iterdir():
                    if candidate.is_file() and username in candidate.stem:
                        acc["session"] = str(candidate.resolve())
                        changed = True
                        break

        # 2. assets 경로 패치 — 윈도우 절대 경로 or 존재하지 않는 경로면 워크스페이스 내로 교체
        assets_raw = raw.get("assets", "")
        if assets_raw and (_is_windows_abs(assets_raw) or not (workspace / assets_raw).exists()):
            # 워크스페이스 내 assets/ 가 있으면 사용
            if (workspace / "assets").is_dir():
                raw["assets"] = "./assets"
                changed = True
            elif workspace.is_dir():
                raw["assets"] = "."
                changed = True

        # 3. 전체 YAML 문자열에서 윈도우 절대 경로를 상대 경로로 치환
        raw_text = yaml.dump(raw, allow_unicode=True, default_flow_style=False, sort_keys=False)
        # C:/Users/.../assets/something → ./something (워크스페이스에 있으면)
        def _fix_win_path(match):
            full = match.group(0)
            # 경로에서 마지막 의미 있는 부분 추출
            # e.g., C:/Users/x/Documents/automator/assets/images/photo.jpg → images/photo.jpg
            for marker in ("assets/", "assets\\", "maps/", "maps\\", "sessions/", "sessions\\"):
                idx = full.replace("\\", "/").find(marker)
                if idx >= 0:
                    relative = full.replace("\\", "/")[idx:]
                    if (workspace / relative).exists():
                        return relative
                    # assets/ 이후 부분만
                    after_assets = full.replace("\\", "/")[idx + len(marker):]
                    candidate = workspace / "assets" / after_assets
                    if candidate.exists():
                        return f"assets/{after_assets}"
            return full

        patched_text = re.sub(r'[A-Z]:[/\\][\w/\\.~: -]+', _fix_win_path, raw_text)

        if patched_text != raw_text or changed:
            config_file.write_text(patched_text, encoding="utf-8")

    @staticmethod
    def _find_free_display() -> int:
        for n in range(99, 200):
            if not Path(f"/tmp/.X{n}-lock").exists():
                return n
        raise RuntimeError("No free X display")

    def _start_vnc(self, campaign: Campaign) -> tuple[str, int]:
        """Xvfb + x11vnc + websockify를 시작하고 (display, ws_port)를 반환."""
        display_num = self._find_free_display()
        display_str = f":{display_num}"
        vnc_port = _alloc_port(_VNC_PORT_RANGE)
        ws_port = _alloc_port(_WS_PORT_RANGE)

        xvfb = subprocess.Popen(
            ["Xvfb", display_str, "-screen", "0", "1920x1080x24", "-ac"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(1)

        vnc = subprocess.Popen(
            ["x11vnc", "-display", display_str, "-nopw", "-shared", "-forever",
             "-rfbport", str(vnc_port), "-noxdamage"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(0.5)

        wsproxy = subprocess.Popen(
            ["websockify", "--web", "/usr/share/novnc", str(ws_port),
             f"localhost:{vnc_port}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(0.5)

        campaign._vnc_procs = [xvfb, vnc, wsproxy]
        campaign.vnc_port = ws_port
        return display_str, ws_port

    def _stop_vnc(self, campaign: Campaign) -> None:
        """VNC 관련 프로세스를 종료한다."""
        for proc in reversed(campaign._vnc_procs):
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        if campaign.vnc_port:
            _free_port(campaign.vnc_port)
        campaign._vnc_procs = []
        campaign.vnc_port = 0

    def _run(self, campaign: Campaign) -> None:
        """워커 스레드: Xvfb + VNC로 실시간 브라우저 화면을 제공하며 CLI를 실행한다."""
        campaign.status = Status.RUNNING
        campaign._emit(f"[실행 시작] {campaign.config_path}\n")

        self._patch_config(campaign.config_path)

        project_root = str(Path(__file__).resolve().parent.parent)

        # Xvfb + VNC 시작
        display_str, ws_port = self._start_vnc(campaign)
        campaign._emit(f"[VNC] ws://localhost:{ws_port}\n")

        cmd = [
            sys.executable, "-m", "cli",
            campaign.config_path,
            "--execute",
            "--no-headless",
        ]
        env = {
            **os.environ,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONPATH": project_root,
            "DISPLAY": display_str,
        }

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                cwd=str(Path(campaign.config_path).parent),
            )
            campaign._proc = proc

            for line in proc.stdout:
                campaign._emit(line)

            proc.wait()
            campaign.exit_code = proc.returncode
            campaign.status = (
                Status.COMPLETED if proc.returncode == 0 else Status.FAILED
            )
            campaign._emit(f"[완료] exit_code={proc.returncode}\n")

        except Exception as exc:
            campaign.status = Status.FAILED
            campaign._emit(f"[오류] {exc}\n")
        finally:
            campaign._proc = None
            self._stop_vnc(campaign)
