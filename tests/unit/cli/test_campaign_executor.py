"""
tests/unit/cli/test_campaign_executor.py
------------------------------------------
campaign_executor — orchestrates load → combos → specs → execute.

Tests cover:
    - Account round-robin assignment
    - Dry-run vs execute mode
    - Preview mode (returns summary, no execution)
    - Limit flag
    - Error propagation
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, call

import pytest

from automator.contracts import PostingSpec
from automator.editor import BlogEditor

from cli.campaign_config import (
    AccountEntry,
    CampaignConfig,
    TitleConfig,
    TokenEntry,
)
from cli.campaign_executor import (
    CampaignExecutor,
    ExecutionPlan,
    PlanItem,
    assign_round_robin,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_config(
    n_accounts: int = 2,
    n_keywords: int = 3,
) -> CampaignConfig:
    """Build a config with N accounts and N keywords in one category."""
    accounts = tuple(
        AccountEntry(username=f"user{i}", password=f"pw{i}")
        for i in range(n_accounts)
    )
    return CampaignConfig(
        accounts=accounts,
        title=TitleConfig(
            tokens=(TokenEntry(slug="region", type="keyword"),),
            spacing_rules=({"region": 1},),
        ),
        keywords={"region": [f"kw{i}" for i in range(n_keywords)]},
        run_config={"post_interval": 0},
    )


# ---------------------------------------------------------------------------
# Round-robin assignment
# ---------------------------------------------------------------------------

class TestAssignRoundRobin:

    def test_even_distribution(self):
        items = ["a", "b", "c", "d"]
        buckets = ["X", "Y"]
        result = assign_round_robin(items, buckets)
        # result: [(X, [a, c]), (Y, [b, d])]
        assert len(result) == 2
        assert result[0][0] == "X"
        assert result[0][1] == ["a", "c"]
        assert result[1][0] == "Y"
        assert result[1][1] == ["b", "d"]

    def test_uneven_distribution(self):
        items = ["a", "b", "c"]
        buckets = ["X", "Y"]
        result = assign_round_robin(items, buckets)
        assert result[0][1] == ["a", "c"]
        assert result[1][1] == ["b"]

    def test_more_buckets_than_items(self):
        items = ["a"]
        buckets = ["X", "Y", "Z"]
        result = assign_round_robin(items, buckets)
        # Only first bucket gets an item; others are empty and excluded
        assert len(result) == 1
        assert result[0] == ("X", ["a"])

    def test_single_bucket(self):
        items = ["a", "b", "c"]
        buckets = ["X"]
        result = assign_round_robin(items, buckets)
        assert result == [("X", ["a", "b", "c"])]


# ---------------------------------------------------------------------------
# ExecutionPlan / Preview
# ---------------------------------------------------------------------------

class TestPreview:

    def test_preview_returns_plan(self):
        config = _make_config(n_accounts=2, n_keywords=4)
        executor = CampaignExecutor()
        plan = executor.preview(config)
        assert isinstance(plan, ExecutionPlan)

    def test_plan_total_combos(self):
        config = _make_config(n_accounts=2, n_keywords=4)
        executor = CampaignExecutor()
        plan = executor.preview(config)
        # 4 keywords × 1 spacing rule = 4 combos
        assert plan.total_combos == 4

    def test_plan_accounts_used(self):
        config = _make_config(n_accounts=2, n_keywords=4)
        executor = CampaignExecutor()
        plan = executor.preview(config)
        assert plan.accounts_used == 2

    def test_plan_items_have_account_and_count(self):
        config = _make_config(n_accounts=2, n_keywords=4)
        executor = CampaignExecutor()
        plan = executor.preview(config)
        assert len(plan.items) == 2
        assert plan.items[0].account_username == "user0"
        assert plan.items[0].combo_count == 2
        assert plan.items[1].account_username == "user1"
        assert plan.items[1].combo_count == 2

    def test_plan_sample_titles(self):
        config = _make_config(n_accounts=1, n_keywords=2)
        executor = CampaignExecutor()
        plan = executor.preview(config)
        # Should have at least some sample titles
        assert len(plan.sample_titles) >= 1

    def test_limit_reduces_combos(self):
        config = _make_config(n_accounts=1, n_keywords=10)
        executor = CampaignExecutor()
        plan = executor.preview(config, limit=3)
        assert plan.total_combos == 3


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

class TestExecute:

    def test_dry_run_does_not_call_runner(self):
        """Dry-run builds specs but does not call JobRunner.run."""
        config = _make_config(n_accounts=1, n_keywords=2)
        mock_runner = MagicMock()
        mock_editor_factory = MagicMock()

        executor = CampaignExecutor(
            runner=mock_runner,
            editor_factory=mock_editor_factory,
        )
        results = executor.execute(config, dry_run=True)
        mock_runner.run.assert_not_called()
        assert results.total_attempted == 2
        assert results.total_succeeded == 2  # dry-run = success

    def test_execute_calls_runner_for_each_spec(self):
        config = _make_config(n_accounts=1, n_keywords=2)
        mock_runner = MagicMock()
        mock_editor = MagicMock(spec=BlogEditor)
        mock_editor_factory = MagicMock(return_value=mock_editor)

        executor = CampaignExecutor(
            runner=mock_runner,
            editor_factory=mock_editor_factory,
        )
        results = executor.execute(config, dry_run=False)
        assert mock_runner.run.call_count == 2

    def test_execute_with_limit(self):
        config = _make_config(n_accounts=1, n_keywords=10)
        mock_runner = MagicMock()
        mock_editor = MagicMock(spec=BlogEditor)
        mock_editor_factory = MagicMock(return_value=mock_editor)

        executor = CampaignExecutor(
            runner=mock_runner,
            editor_factory=mock_editor_factory,
        )
        results = executor.execute(config, dry_run=False, limit=3)
        assert mock_runner.run.call_count == 3

    def test_execute_continues_on_failure_by_default(self):
        """When run_config.on_failure='stop' is NOT set, failures continue."""
        config = _make_config(n_accounts=1, n_keywords=3)
        mock_runner = MagicMock()
        mock_runner.run.side_effect = [None, RuntimeError("fail"), None]
        mock_editor = MagicMock(spec=BlogEditor)
        mock_editor_factory = MagicMock(return_value=mock_editor)

        executor = CampaignExecutor(
            runner=mock_runner,
            editor_factory=mock_editor_factory,
        )
        results = executor.execute(config, dry_run=False)
        assert results.total_attempted == 3
        assert results.total_succeeded == 2
        assert results.total_failed == 1
