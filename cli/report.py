"""
cli/report.py
--------------
캠페인 완료 후 발행 기록을 YAML 파일로 내보낸다.

랭크 추적 콜렉터가 소비할 수 있도록 각 발행 건의 핵심 정보만 기록한다:
    blog_id | keyword | title | published_at

출력 포맷은 YAML 로 고정. 사용자가 .xlsx 등 다른 확장자를 넘겨도
.yaml 로 저장한다.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

log = logging.getLogger(__name__)


# 랭크 콜렉터가 필요로 하는 필드만.
_FIELDS: tuple[str, ...] = ("blog_id", "keyword", "title", "published_at")
_YAML_EXTS: frozenset[str] = frozenset({".yaml", ".yml"})


def _iter_rows(result: Any, include_failed: bool) -> Iterable[dict[str, Any]]:
    """ExecutionResult 에서 리포트 row 를 만든다."""
    records = list(result.succeeded_combos)
    if include_failed:
        records.extend(result.failed_combos)

    for rec in records:
        published = getattr(rec, "published_at", None)
        yield {
            "blog_id":      getattr(rec, "blog_id", "") or "",
            "keyword":      getattr(rec, "keyword", "") or "",
            "title":        getattr(rec, "title", "") or "",
            "published_at": published.isoformat() if isinstance(published, datetime) else "",
        }


def _coerce_yaml_path(path: str | Path) -> Path:
    """경로 확장자를 .yaml 로 강제한다 (.yml 은 그대로 둠)."""
    out = Path(path).expanduser().resolve()
    if out.suffix.lower() not in _YAML_EXTS:
        out = out.with_suffix(".yaml")
    return out


def write_rows(rows: list[dict[str, Any]], path: str | Path) -> Path:
    """평탄화된 row dict 리스트를 YAML 파일로 저장한다.

    GUI 등 ExecutionResult 없이 기존 리포트 파일을 다른 포맷으로
    재저장하려는 경우에 사용한다. 출력은 항상 YAML.
    """
    out = _coerce_yaml_path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    _write_yaml(out, rows)
    log.info("[report] %d건 저장 완료 → %s", len(rows), out)
    return out


def write_report(
    result: Any,
    path: str | Path,
    *,
    include_failed: bool = False,
) -> Path:
    """ExecutionResult 로부터 row 를 뽑아 YAML 로 저장한다.

    Args:
        result:         ExecutionResult (succeeded_combos / failed_combos 를 가진 객체).
        path:           저장 경로. 확장자가 .yaml/.yml 이 아니면 .yaml 로 강제.
        include_failed: True 이면 실패한 조합도 포함.

    Returns:
        저장된 파일의 절대 경로.
    """
    rows = list(_iter_rows(result, include_failed=include_failed))
    return write_rows(rows, path)


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

def _write_yaml(out: Path, rows: list[dict[str, Any]]) -> None:
    import yaml

    with open(out, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            rows,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
