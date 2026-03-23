"""
cli/campaign_executor.py
--------------------------
CampaignExecutor — orchestrates the full CLI pipeline.

    load config → build combos → build specs → assign accounts → execute

Supports:
    - preview()  — returns ExecutionPlan without executing
    - execute()  — runs the pipeline with dry-run or live mode
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, TypeVar

from automator.contracts import PostingSpec
from automator.editor import BlogEditor
from automator.runner import JobRunner
from automator.title_generator import generate_title

from cli.campaign_config import AccountEntry, CampaignConfig
from cli.combo_builder import KeywordCombo, build_keyword_combos
from cli.spec_builder import build_account_option, build_spec

KST = timezone(timedelta(hours=9))

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlanItem:
    """One account's share of the execution plan."""
    account_username: str
    combo_count:      int


@dataclass(frozen=True)
class ExecutionPlan:
    """Preview of what execute() would do."""
    total_combos:  int
    accounts_used: int
    items:         list[PlanItem]
    sample_titles: list[str]       = field(default_factory=list)


@dataclass
class ExecutionResult:
    """Outcome of execute()."""
    total_attempted: int = 0
    total_succeeded: int = 0
    total_failed:    int = 0
    errors:          list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Round-robin assignment (pure function)
# ---------------------------------------------------------------------------

def assign_round_robin(
    items: list[_T],
    buckets: list[Any],
) -> list[tuple[Any, list[_T]]]:
    """
    Distribute items across buckets in round-robin order.

    Returns list of (bucket, [items]) tuples.
    Empty buckets are excluded from the result.
    """
    assignment: dict[int, list[_T]] = {i: [] for i in range(len(buckets))}

    for idx, item in enumerate(items):
        bucket_idx = idx % len(buckets)
        assignment[bucket_idx].append(item)

    return [
        (buckets[i], assigned)
        for i, assigned in assignment.items()
        if assigned
    ]


# ---------------------------------------------------------------------------
# CampaignExecutor
# ---------------------------------------------------------------------------

EditorFactory = Callable[[AccountEntry], BlogEditor]


class CampaignExecutor:
    """
    Orchestrate the full campaign execution pipeline.

    Dependencies (all optional — defaults support dry-run):
        runner:         JobRunner instance for live execution.
        editor_factory: AccountEntry → BlogEditor for live execution.
    """

    def __init__(
        self,
        runner: JobRunner | None = None,
        editor_factory: EditorFactory | None = None,
    ) -> None:
        self._runner = runner
        self._editor_factory = editor_factory

    def preview(
        self,
        config: CampaignConfig,
        limit: int | None = None,
    ) -> ExecutionPlan:
        """
        Build an execution plan without running anything.

        Returns:
            ExecutionPlan with combo counts, account assignments,
            and sample generated titles.
        """
        combos = build_keyword_combos(config)
        if limit is not None:
            combos = combos[:limit]

        assignments = assign_round_robin(
            combos, list(config.accounts),
        )

        sample_titles = _generate_sample_titles(combos[:5], config)

        items = [
            PlanItem(
                account_username=account.username,
                combo_count=len(assigned_combos),
            )
            for account, assigned_combos in assignments
        ]

        return ExecutionPlan(
            total_combos=len(combos),
            accounts_used=len(assignments),
            items=items,
            sample_titles=sample_titles,
        )

    def execute(
        self,
        config: CampaignConfig,
        dry_run: bool = True,
        limit: int | None = None,
    ) -> ExecutionResult:
        """
        Execute the campaign pipeline.

        Args:
            config:  Validated CampaignConfig.
            dry_run: If True, build specs but skip JobRunner.run().
            limit:   Max number of combos to process.

        Returns:
            ExecutionResult with success/failure counts.
        """
        combos = build_keyword_combos(config)
        if limit is not None:
            combos = combos[:limit]

        assignments = assign_round_robin(
            combos, list(config.accounts),
        )

        result = ExecutionResult()
        post_interval = config.run_config.get("post_interval", 60)

        for account_entry, assigned_combos in assignments:
            self._execute_account_batch(
                account_entry=account_entry,
                combos=assigned_combos,
                config=config,
                dry_run=dry_run,
                post_interval=post_interval,
                result=result,
            )

        return result

    def _execute_account_batch(
        self,
        account_entry: AccountEntry,
        combos: list[KeywordCombo],
        config: CampaignConfig,
        dry_run: bool,
        post_interval: int,
        result: ExecutionResult,
    ) -> None:
        """Process all combos assigned to one account."""
        for i, combo in enumerate(combos):
            result.total_attempted += 1

            try:
                spec = build_spec(combo, config, account_entry)

                if dry_run:
                    logger.info(
                        "[DRY-RUN] %s | %s",
                        account_entry.username,
                        generate_title(spec.title),
                    )
                    result.total_succeeded += 1
                    continue

                self._run_spec(spec, account_entry)
                result.total_succeeded += 1
                logger.info(
                    "[OK] %s | %s",
                    account_entry.username,
                    generate_title(spec.title),
                )

            except Exception as exc:
                result.total_failed += 1
                result.errors.append(str(exc))
                logger.error(
                    "[FAIL] %s | %s",
                    account_entry.username,
                    str(exc),
                )

            # Interval between posts (skip after last)
            if not dry_run and i < len(combos) - 1 and post_interval > 0:
                time.sleep(post_interval)

    def _run_spec(
        self,
        spec: PostingSpec,
        account_entry: AccountEntry,
    ) -> None:
        """Execute a single PostingSpec through JobRunner."""
        if self._runner is None:
            raise RuntimeError(
                "JobRunner not provided — cannot execute in live mode. "
                "Use dry_run=True or inject a runner."
            )
        if self._editor_factory is None:
            raise RuntimeError(
                "editor_factory not provided — cannot create BlogEditor."
            )

        editor = self._editor_factory(account_entry)
        self._runner.run(spec, editor)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_sample_titles(
    combos: list[KeywordCombo],
    config: CampaignConfig,
) -> list[str]:
    """Generate sample titles for preview display."""
    titles: list[str] = []
    for combo in combos:
        try:
            spec = build_spec(combo, config, config.accounts[0])
            title = generate_title(spec.title)
            titles.append(title)
        except Exception:
            titles.append("(title generation failed)")
    return titles
