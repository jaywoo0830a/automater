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
from typing import Callable


class Status(str, Enum):
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
    status: Status = Status.QUEUED
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


class Worker:
    """캠페인 실행 워커. 스레드 기반."""

    def __init__(self) -> None:
        self._campaigns: dict[str, Campaign] = {}
        self._lock = threading.Lock()

    def submit(self, campaign_id: str, config_path: str, workspace: str) -> Campaign:
        """캠페인을 큐에 등록하고 즉시 실행한다."""
        campaign = Campaign(
            id=campaign_id,
            config_path=config_path,
            workspace=workspace,
        )
        with self._lock:
            self._campaigns[campaign_id] = campaign

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
        import yaml
        config_file = Path(config_path)
        sessions_dir = config_file.parent / "sessions"
        if not sessions_dir.is_dir():
            return

        raw = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}

        # session_store는 문자열 "file"로 설정
        raw["session_store"] = "file"

        # 계정별 session 경로를 sessions/ 내 파일 절대 경로로 교체
        for acc in raw.get("accounts", []):
            username = acc.get("username", "")
            if not username:
                continue
            # sessions/ 안에서 매칭되는 파일 찾기
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

        # 워크스페이스 내 세션 파일 연결
        self._patch_session_store(campaign.config_path)

        # 프로젝트 루트 = api/ 의 부모
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
