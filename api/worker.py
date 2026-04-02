"""
api/worker.py
--------------
캠페인 실행 워커.

각 캠페인을 subprocess로 실행하고 상태를 추적한다.
로그는 메모리 버퍼에 저장되며 WebSocket으로 스트리밍된다.
"""

from __future__ import annotations

import os
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
    _proc: subprocess.Popen | None = field(default=None, repr=False)
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
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_campaign_accounts(config_path: str) -> list[dict[str, Any]]:
    """캠페인 YAML에서 accounts 목록을 추출한다."""
    raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    return raw.get("accounts", [])


def check_sessions(config_path: str, workspace: str) -> dict[str, Any]:
    """캠페인의 각 계정에 대해 세션 파일 존재 여부를 확인한다."""
    accounts = parse_campaign_accounts(config_path)
    sessions_dir = Path(workspace) / "sessions"
    results = []

    for acc in accounts:
        username = acc.get("username", "")
        blog_id = acc.get("blog_id", username)
        has_session = False

        if sessions_dir.is_dir():
            for f in sessions_dir.iterdir():
                if f.is_file() and username in f.stem:
                    has_session = True
                    break

        results.append({
            "username": username,
            "blog_id": blog_id,
            "has_session": has_session,
        })

    return {
        "accounts": results,
        "all_ready": all(r["has_session"] for r in results),
    }


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
    def _patch_session_store(config_path: str) -> None:
        """워크스페이스 내 sessions/ 폴더가 있으면 YAML의 session_store를 패치."""
        config_file = Path(config_path)
        sessions_dir = config_file.parent / "sessions"
        if not sessions_dir.is_dir():
            return

        raw = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
        raw["session_store"] = "file"

        for acc in raw.get("accounts", []):
            username = acc.get("username", "")
            if not username:
                continue
            for candidate in sessions_dir.iterdir():
                if candidate.is_file() and username in candidate.stem:
                    acc["session"] = str(candidate.resolve())
                    break

        config_file.write_text(
            yaml.dump(raw, allow_unicode=True, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    def _run(self, campaign: Campaign) -> None:
        """워커 스레드: subprocess로 CLI를 실행한다."""
        campaign.status = Status.RUNNING
        campaign._emit(f"[실행 시작] {campaign.config_path}\n")

        self._patch_session_store(campaign.config_path)

        project_root = str(Path(__file__).resolve().parent.parent)

        cmd = [
            sys.executable, "-m", "cli",
            campaign.config_path,
            "--execute",
        ]
        env = {
            **os.environ,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONPATH": project_root,
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
