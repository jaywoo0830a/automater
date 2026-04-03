"""
cli/progress.py
----------------
캠페인 진행 기록 — 완료된 조합 추적.

저장 위치: {base_dir}/progress/{campaign_name}.json
"""

from __future__ import annotations

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any


class ProgressTracker:
    """캠페인 진행 상태를 파일에 기록한다."""

    def __init__(self, config_path: str, base_dir: str = ".") -> None:
        self._campaign_id = self._make_id(config_path)
        self._dir = Path(base_dir) / "progress"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / f"{self._campaign_id}.json"
        self._completed: set[int] = set()
        self._total: int = 0
        self._last_schedule_at: str = ""
        self._load()

    @staticmethod
    def _make_id(config_path: str) -> str:
        """캠페인 파일명 기반 ID (확장자 제거)."""
        name = Path(config_path).stem
        return name

    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._completed = set(data.get("completed", []))
                self._total = data.get("total", 0)
                self._last_schedule_at = data.get("last_schedule_at", "")
            except (json.JSONDecodeError, KeyError):
                self._completed = set()

    def _save(self) -> None:
        data = {
            "campaign": self._campaign_id,
            "completed": sorted(self._completed),
            "total": self._total,
            "last_updated": datetime.now().isoformat(),
            "last_schedule_at": self._last_schedule_at,
        }
        self._path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def set_total(self, total: int) -> None:
        self._total = total
        self._save()

    def mark_done(self, index: int) -> None:
        """조합 인덱스를 완료로 기록."""
        self._completed.add(index)
        self._save()

    def is_done(self, index: int) -> bool:
        return index in self._completed

    @property
    def completed_count(self) -> int:
        return len(self._completed)

    @property
    def completed_indices(self) -> set[int]:
        return set(self._completed)

    @property
    def last_schedule_at(self) -> str:
        """마지막으로 예약된 시간 (ISO format)."""
        return self._last_schedule_at

    @last_schedule_at.setter
    def last_schedule_at(self, value: str) -> None:
        self._last_schedule_at = value
        self._save()

    def reset(self) -> None:
        """진행 기록 초기화."""
        self._completed.clear()
        self._total = 0
        self._last_schedule_at = ""
        if self._path.exists():
            self._path.unlink()
