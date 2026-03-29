"""
cli/campaign_executor.py
--------------------------
CampaignExecutor — orchestrates the full CLI pipeline.

    load config → build combos → build specs → assign accounts → execute
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, TypeVar

from automator.contracts import PostingSpec
from automator.editor import BlogEditor
from automator.runner import JobRunner
from automator.title_generator import generate_title

from cli.combo_builder import Combo, build_combos
from cli.spec_builder import build_spec, merge_account_run

logger = logging.getLogger(__name__)

_T = TypeVar("_T")
_KST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlanItem:
    """One account's share of the plan."""
    account_username: str
    combo_count:      int


@dataclass(frozen=True)
class ExecutionPlan:
    """Preview of what execute() would do."""
    total_combos:  int
    accounts_used: int
    items:         list[PlanItem]
    sample_titles: list[str] = field(default_factory=list)


@dataclass
class ExecutionResult:
    """Outcome of execute()."""
    total_attempted:    int = 0
    total_succeeded:    int = 0
    total_failed:       int = 0
    session_recoveries: int = 0
    errors:             list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Round-robin (pure function)
# ---------------------------------------------------------------------------

def assign_weighted(
    items: list[_T],
    buckets: list[Any],
) -> list[tuple[Any, list[_T]]]:
    """
    Distribute items across buckets by weight, respecting min/max caps.

    Each bucket (account dict) may have:
        "weight"    — distribution ratio (default 1)
        "min_posts" — guaranteed minimum, 0 = none (default 0)
        "max_posts" — hard cap, 0 = unlimited (default 0)

    Algorithm:
        1. Allocate min_posts guarantees first.
        2. Distribute remainder by weight ratio.
        3. Apply max_posts caps — overflow is redistributed.

    Empty buckets excluded from result.
    """
    n = len(items)
    if not buckets or n == 0:
        return []

    def _get(b, key, default):
        return b.get(key, default) if isinstance(b, dict) else default

    weights = [int(_get(b, "weight", 1)) for b in buckets]
    floors = [int(_get(b, "min_posts", 0)) for b in buckets]
    caps = [int(_get(b, "max_posts", 0)) for b in buckets]

    # 1. Allocate min_posts guarantees
    counts = [min(f, n) for f in floors]
    remaining = max(0, n - sum(counts))

    # 2. Distribute remainder by weight
    if remaining > 0:
        extra = _distribute_by_weight(remaining, weights)
        counts = [c + e for c, e in zip(counts, extra)]

    # 3. Apply max_posts caps
    counts = _apply_caps(counts, caps, weights)

    # Slice items by counts
    result: list[tuple[Any, list[_T]]] = []
    offset = 0
    for i, bucket in enumerate(buckets):
        assigned = items[offset:offset + counts[i]]
        offset += counts[i]
        if assigned:
            result.append((bucket, assigned))

    return result


def _distribute_by_weight(n: int, weights: list[int]) -> list[int]:
    """Split n items proportionally by weights."""
    total_weight = sum(weights)
    counts = [n * w // total_weight for w in weights]
    remainder = n - sum(counts)

    fractions = [(n * w / total_weight) - (n * w // total_weight) for w in weights]
    for idx in sorted(range(len(weights)), key=lambda i: fractions[i], reverse=True):
        if remainder <= 0:
            break
        counts[idx] += 1
        remainder -= 1

    return counts


def _apply_caps(
    counts: list[int],
    caps: list[int],
    weights: list[int],
) -> list[int]:
    """
    Enforce max_posts caps. Overflow is redistributed to uncapped buckets
    proportionally by weight. Repeats until stable.
    """
    result = list(counts)

    for _ in range(len(counts)):  # max iterations = number of buckets
        overflow = 0
        uncapped_weight = 0

        for i, cap in enumerate(caps):
            if cap > 0 and result[i] > cap:
                overflow += result[i] - cap
                result[i] = cap
            elif cap == 0 or result[i] < cap:
                uncapped_weight += weights[i]

        if overflow == 0:
            break

        # Redistribute overflow to uncapped buckets by weight
        if uncapped_weight == 0:
            break  # all buckets capped, drop remainder

        distributed = 0
        for i, cap in enumerate(caps):
            if (cap == 0 or result[i] < cap) and uncapped_weight > 0:
                share = overflow * weights[i] // uncapped_weight
                room = (cap - result[i]) if cap > 0 else overflow
                added = min(share, room)
                result[i] += added
                distributed += added

        # Remainder from integer division — give one each to largest uncapped
        leftover = overflow - distributed
        for i in sorted(
            range(len(counts)),
            key=lambda i: weights[i],
            reverse=True,
        ):
            if leftover <= 0:
                break
            if caps[i] == 0 or result[i] < caps[i]:
                result[i] += 1
                leftover -= 1

    return result


# ---------------------------------------------------------------------------
# CampaignExecutor
# ---------------------------------------------------------------------------

EditorFactory = Callable[[dict[str, Any]], BlogEditor]
SessionRecovery = Callable[[dict[str, Any]], BlogEditor]

_MAX_SESSION_RETRIES = 2


class CampaignExecutor:
    """
    Orchestrate the full campaign pipeline.

    Dependencies (optional — defaults support dry-run):
        runner:           JobRunner for live execution.
        editor_factory:   account_dict → BlogEditor for live execution.
        session_recovery: account_dict → BlogEditor (세션 복구 후 에디터 재생성).
    """

    def __init__(
        self,
        runner: JobRunner | None = None,
        editor_factory: EditorFactory | None = None,
        session_recovery: SessionRecovery | None = None,
    ) -> None:
        self._runner = runner
        self._editor_factory = editor_factory
        self._session_recovery = session_recovery
        self._seq_next_at: datetime | None = None

    def preview(
        self,
        config: dict[str, Any],
        limit: int | None = None,
    ) -> ExecutionPlan:
        """Build an execution plan without running anything."""
        combos = self._build_combos(config, limit)
        assignments = assign_weighted(combos, config["accounts"])

        sample_titles = []
        for combo in combos[:5]:
            try:
                spec = build_spec(combo, config)
                sample_titles.append(generate_title(spec.title))
            except Exception:
                sample_titles.append("(generation failed)")

        return ExecutionPlan(
            total_combos=len(combos),
            accounts_used=len(assignments),
            items=[
                PlanItem(
                    account_username=acc["username"],
                    combo_count=len(assigned),
                )
                for acc, assigned in assignments
            ],
            sample_titles=sample_titles,
        )

    def execute(
        self,
        config: dict[str, Any],
        dry_run: bool = True,
        limit: int | None = None,
    ) -> ExecutionResult:
        """
        Execute the campaign.

        Args:
            config:  Validated config dict.
            dry_run: If True, build specs but skip runner.run().
            limit:   Max combos to process.
        """
        combos = self._build_combos(config, limit)
        assignments = assign_weighted(combos, config["accounts"])
        result = ExecutionResult()

        global_run = config.get("run", {})

        for account, assigned_combos in assignments:
            account_idx = config["accounts"].index(account)
            merged_run = merge_account_run(global_run, account)
            interval = self._parse_interval(merged_run)
            self._execute_batch(
                combos=assigned_combos,
                config=config,
                account_idx=account_idx,
                dry_run=dry_run,
                interval=interval,
                result=result,
            )

        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _build_combos(
        config: dict[str, Any],
        limit: int | None,
    ) -> list[Combo]:
        combos = build_combos(config["keywords"], config["titles"])
        if limit is not None:
            combos = combos[:limit]
        return combos

    def _execute_batch(
        self,
        combos: list[Combo],
        config: dict[str, Any],
        account_idx: int,
        dry_run: bool,
        interval: int,
        result: ExecutionResult,
    ) -> None:
        from cli.session_manager import is_session_error

        account = config["accounts"][account_idx]
        username = account["username"]

        # Create editor once per account batch (not per spec)
        editor = None
        if not dry_run and self._editor_factory is not None:
            try:
                editor = self._editor_factory(account)
            except Exception as exc:
                logger.error("[FAIL] %s | editor init: %s", username, exc)
                for _ in combos:
                    result.total_attempted += 1
                    result.total_failed += 1
                    result.errors.append(str(exc))
                return

        for i, combo in enumerate(combos):
            result.total_attempted += 1

            try:
                spec = build_spec(combo, config, account_idx)

                # Sequential mode: compute schedule_at for each post progressively
                spec = self._resolve_sequential(spec, i, config)

                if dry_run:
                    title = generate_title(spec.title)
                    at_label = spec.schedule_at.strftime("%H:%M") if spec.schedule_at else "-"
                    logger.info("[DRY-RUN] %s | %s (at=%s)", username, title, at_label)
                    result.total_succeeded += 1
                    continue

                # 실행 + 세션 만료 시 복구 재시도
                self._run_with_recovery(
                    spec, editor, account, result,
                )

            except Exception as exc:
                result.total_failed += 1
                result.errors.append(str(exc))
                logger.error("[FAIL] %s | %s", username, str(exc))

            if not dry_run and i < len(combos) - 1 and interval > 0:
                time.sleep(interval)

    def _run_with_recovery(
        self,
        spec: PostingSpec,
        editor: BlogEditor | None,
        account: dict[str, Any],
        result: ExecutionResult,
    ) -> None:
        """spec 실행. 세션 만료 감지 시 복구 후 재시��."""
        from cli.session_manager import is_session_error

        username = account["username"]
        last_exc: Exception | None = None

        for attempt in range(_MAX_SESSION_RETRIES + 1):
            try:
                self._run_spec(spec, editor)
                result.total_succeeded += 1
                return
            except Exception as exc:
                last_exc = exc
                error_msg = str(exc)

                # 세션 문제가 아니면 바로 실패
                if not is_session_error(error_msg=error_msg):
                    break

                # 마지막 시도였으면 탈출
                if attempt >= _MAX_SESSION_RETRIES:
                    break

                # 세션 복구 시도
                if self._session_recovery is None:
                    logger.warning("[%s] 세션 만료 감지, 복구 불가 (session_recovery 없음)", username)
                    break

                logger.warning(
                    "[%s] 세션 만료 감지 (시도 %d/%d) — 복구 중...",
                    username, attempt + 1, _MAX_SESSION_RETRIES,
                )
                try:
                    editor = self._session_recovery(account)
                    result.session_recoveries += 1
                    logger.info("[%s] 세션 복구 완료 — 재시도", username)
                except Exception as recovery_exc:
                    logger.error("[%s] 세션 복구 실패: %s", username, recovery_exc)
                    break

        # 모든 시도 실패
        result.total_failed += 1
        result.errors.append(str(last_exc))
        logger.error("[FAIL] %s | %s", username, str(last_exc))

    def _run_spec(self, spec: PostingSpec, editor: BlogEditor) -> None:
        if self._runner is None:
            raise RuntimeError("JobRunner not provided")
        if editor is None:
            raise RuntimeError("editor not initialized")
        self._runner.run(spec, editor)

    def _resolve_sequential(self, spec: PostingSpec, index: int, config: dict[str, Any]) -> PostingSpec:
        """
        For sequential schedule, compute schedule_at progressively.

        Reads interval_lo/interval_hi from config publish.schedule.
        Returns the spec unchanged if schedule is not sequential.
        """
        publish_config = config.get("publish", {})
        schedule_raw = publish_config.get("schedule", "")
        if not isinstance(schedule_raw, str) or "++" not in schedule_raw:
            return spec

        from cli.spec_builder import parse_schedule
        parsed = parse_schedule(schedule_raw)
        lo = parsed.get("interval_lo", 0)
        hi = parsed.get("interval_hi", 0) or lo
        interval = random.randint(min(lo, hi), max(lo, hi))

        if index == 0:
            self._seq_next_at = datetime.now(tz=_KST) + timedelta(seconds=interval)
        else:
            self._seq_next_at = self._seq_next_at + timedelta(seconds=interval)

        return replace(spec, schedule_at=self._seq_next_at)

    @staticmethod
    def _parse_interval(run_config: dict[str, Any]) -> int:
        raw = run_config.get("interval", "60s")
        if isinstance(raw, (int, float)):
            return int(raw)
        s = str(raw).strip().lower()
        if s.endswith("ms"):
            return 0  # sub-second, treat as 0 for sleep
        if s.endswith("min"):
            return int(s[:-3]) * 60
        if s.endswith("s"):
            return int(s[:-1])
        try:
            return int(s)
        except ValueError:
            return 60
