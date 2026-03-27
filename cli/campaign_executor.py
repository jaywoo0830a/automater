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
    total_attempted: int = 0
    total_succeeded: int = 0
    total_failed:    int = 0
    errors:          list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Round-robin (pure function)
# ---------------------------------------------------------------------------

def assign_round_robin(
    items: list[_T],
    buckets: list[Any],
) -> list[tuple[Any, list[_T]]]:
    """
    Distribute items across buckets in round-robin order.

    Empty buckets excluded from result.
    """
    assignment: dict[int, list[_T]] = {i: [] for i in range(len(buckets))}
    for idx, item in enumerate(items):
        assignment[idx % len(buckets)].append(item)
    return [
        (buckets[i], assigned)
        for i, assigned in assignment.items()
        if assigned
    ]


# ---------------------------------------------------------------------------
# CampaignExecutor
# ---------------------------------------------------------------------------

EditorFactory = Callable[[dict[str, Any]], BlogEditor]


class CampaignExecutor:
    """
    Orchestrate the full campaign pipeline.

    Dependencies (optional — defaults support dry-run):
        runner:         JobRunner for live execution.
        editor_factory: account_dict → BlogEditor for live execution.
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
        assignments = assign_round_robin(combos, config["accounts"])

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
        assignments = assign_round_robin(combos, config["accounts"])
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

                self._run_spec(spec, editor)
                result.total_succeeded += 1

            except Exception as exc:
                result.total_failed += 1
                result.errors.append(str(exc))
                logger.error("[FAIL] %s | %s", username, str(exc))

            if not dry_run and i < len(combos) - 1 and interval > 0:
                time.sleep(interval)

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
