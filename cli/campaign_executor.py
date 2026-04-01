"""
cli/campaign_executor.py
--------------------------
CampaignExecutor — orchestrates the full CLI pipeline.

    load config → build combos → build specs → assign accounts → execute
"""

from __future__ import annotations

import logging
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from pathlib import Path
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
    """Outcome of execute(). Thread-safe via lock."""
    total_attempted:    int = 0
    total_succeeded:    int = 0
    total_failed:       int = 0
    errors:             list[str] = field(default_factory=list)
    _lock:              threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_success(self) -> None:
        with self._lock:
            self.total_attempted += 1
            self.total_succeeded += 1

    def record_failure(self, error: str) -> None:
        with self._lock:
            self.total_attempted += 1
            self.total_failed += 1
            self.errors.append(error)

    def record_attempt(self) -> None:
        with self._lock:
            self.total_attempted += 1


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


class CampaignExecutor:
    """
    Orchestrate the full campaign pipeline.

    Dependencies (optional — defaults support dry-run):
        runner:           JobRunner for live execution.
        editor_factory:   account_dict → BlogEditor for live execution.

    Philosophy:
        어떤 프로세스든 실패하면 즉시 에러를 던지고 다음 조합으로 넘어간다.
        암묵적·명시적 재시도는 없다.
    """

    def __init__(
        self,
        runner: JobRunner | None = None,
        editor_factory: EditorFactory | None = None,
    ) -> None:
        self._runner = runner
        self._editor_factory = editor_factory
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
        from cli.progress import ProgressTracker

        combos = self._build_combos(config, limit)
        assignments = assign_weighted(combos, config["accounts"])
        result = ExecutionResult()

        mode_label = "DRY-RUN" if dry_run else "LIVE"
        account_names = [acc["username"] for acc, _ in assignments]
        logger.info("=" * 60)
        logger.info("  캠페인 실행 시작 (%s)", mode_label)
        logger.info("  총 조합: %d | 계정: %s", len(combos), ", ".join(account_names))
        logger.info("=" * 60)

        global_run = config.get("run", {})
        on_resume = global_run.get("on_resume", "restart")
        parallel = bool(global_run.get("parallel", False))
        max_workers = int(global_run.get("max_workers", len(assignments)))

        # Progress tracking
        config_path = config.get("_config_path", "campaign")
        base_dir = config.get("_base_dir", ".")
        progress = ProgressTracker(config_path, base_dir)

        if on_resume == "restart" and not dry_run:
            progress.reset()
        progress.set_total(len(combos))

        if parallel and not dry_run and len(assignments) > 1:
            self._execute_parallel(assignments, config, global_run, max_workers, result, progress, on_resume)
        else:
            self._execute_serial(assignments, config, global_run, dry_run, result, progress, on_resume)

        logger.info("=" * 60)
        logger.info("  캠페인 실행 완료 (%s)", mode_label)
        logger.info("  성공: %d | 실패: %d",
                     result.total_succeeded, result.total_failed)
        if result.errors:
            logger.info("  오류 목록:")
            for err in result.errors[:10]:
                logger.info("    - %s", err)
        logger.info("=" * 60)

        # 알림 전송
        from cli.notifier import build_notifier
        notifier = build_notifier(config.get("notify"))
        if notifier and not dry_run:
            campaign_name = Path(config.get("_config_path", "campaign")).stem
            notifier.send(result, campaign_name)

        return result

    def _execute_serial(
        self,
        assignments: list[tuple[Any, list[Combo]]],
        config: dict[str, Any],
        global_run: dict[str, Any],
        dry_run: bool,
        result: ExecutionResult,
        progress=None,
        on_resume: str = "restart",
    ) -> None:
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
                progress=progress,
                on_resume=on_resume,
            )

    def _execute_parallel(
        self,
        assignments: list[tuple[Any, list[Combo]]],
        config: dict[str, Any],
        global_run: dict[str, Any],
        max_workers: int,
        result: ExecutionResult,
        progress=None,
        on_resume: str = "restart",
    ) -> None:
        logger.info(
            "병렬 실행: %d 계정, max_workers=%d",
            len(assignments), max_workers,
        )

        def _run_account(account, assigned_combos):
            account_idx = config["accounts"].index(account)
            merged_run = merge_account_run(global_run, account)
            interval = self._parse_interval(merged_run)
            self._execute_batch(
                combos=assigned_combos,
                config=config,
                account_idx=account_idx,
                dry_run=False,
                interval=interval,
                result=result,
                progress=progress,
                on_resume=on_resume,
            )

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_run_account, account, combos): account["username"]
                for account, combos in assignments
            }
            for future in as_completed(futures):
                username = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    logger.error("[PARALLEL] %s 스레드 에러: %s", username, exc)

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
        progress=None,
        on_resume: str = "restart",
    ) -> None:
        account = config["accounts"][account_idx]
        username = account["username"]
        total = len(combos)

        logger.info("=" * 50)
        logger.info("[%s] 배치 시작 (%d개 조합)", username, total)
        logger.info("=" * 50)

        # Create editor once per account batch (not per spec)
        editor = None
        if not dry_run and self._editor_factory is not None:
            try:
                logger.info("[%s] 에디터 초기화 중...", username)
                editor = self._editor_factory(account)
                logger.info("[%s] 에디터 준비 완료", username)
            except Exception as exc:
                logger.error("[FAIL] %s | 에디터 초기화 실패: %s", username, exc)
                for _ in combos:
                    result.record_failure(str(exc))
                return

        succeeded_in_batch = 0

        for i, combo in enumerate(combos):
            combo_index = combo.index - 1  # 0-based global index
            progress_label = f"[{i + 1}/{total}]"

            # skip 모드: 이미 완료된 조합 건너뛰기
            if on_resume == "skip" and progress and progress.is_done(combo_index):
                logger.info("%s [SKIP] %s | #%d (이전 실행에서 완료)", progress_label, username, combo.index)
                continue

            try:
                spec = build_spec(combo, config, account_idx)
                title = generate_title(spec.title)

                # Sequential mode: compute schedule_at for each post progressively
                spec = self._resolve_sequential(spec, i, config)
                at_label = spec.schedule_at.strftime("%H:%M") if spec.schedule_at else "즉시"

                logger.info("%s [START] %s | %s (예약: %s)", progress_label, username, title, at_label)

                if dry_run:
                    result.record_attempt()
                    logger.info("%s [DRY-RUN] %s | %s -- OK", progress_label, username, title)
                    with result._lock:
                        result.total_succeeded += 1
                    succeeded_in_batch += 1
                    continue

                # 실행 — 실패 시 즉시 예외, 재시도 없음
                self._run_spec(spec, editor)
                result.record_success()
                succeeded_in_batch += 1
                logger.info("%s [DONE] %s | %s -- 성공", progress_label, username, title)
                if progress:
                    progress.mark_done(combo_index)

            except Exception as exc:
                result.record_failure(str(exc))
                logger.error("%s [FAIL] %s | %s -- 다음 조합으로 건너뜀", progress_label, username, str(exc))
                continue

            if not dry_run and i < len(combos) - 1 and interval > 0:
                logger.info("[%s] %d초 대기 중...", username, interval)
                time.sleep(interval)

        logger.info("-" * 50)
        logger.info("[%s] 배치 완료 (%d/%d 성공)", username, succeeded_in_batch, total)
        logger.info("-" * 50)

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

        if self._seq_next_at is None:
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
