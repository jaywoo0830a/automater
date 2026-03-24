"""
tests/unit/cli/test_campaign_executor.py
------------------------------------------
Campaign executor — orchestration, round-robin, preview, execute.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cli.campaign_executor import (
    CampaignExecutor,
    ExecutionPlan,
    assign_round_robin,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _config(n_accounts=2, n_keywords=3):
    return {
        "accounts": [
            {"username": f"user{i}", "password": f"pw{i}", "blog_id": f"blog{i}"}
            for i in range(n_accounts)
        ],
        "titles": ["{keyword:region} 과외"],
        "keywords": {"region": [f"kw{i}" for i in range(n_keywords)]},
        "pools": {},
        "post": [{"paragraph": "{keyword:region}"}],
        "images": ".",
        "publish": {},
        "run": {"interval": "0s"},
    }


# ---------------------------------------------------------------------------
# Round-robin
# ---------------------------------------------------------------------------

class TestRoundRobin:

    def test_even(self):
        result = assign_round_robin(["a", "b", "c", "d"], ["X", "Y"])
        assert result == [("X", ["a", "c"]), ("Y", ["b", "d"])]

    def test_uneven(self):
        result = assign_round_robin(["a", "b", "c"], ["X", "Y"])
        assert result[0] == ("X", ["a", "c"])
        assert result[1] == ("Y", ["b"])

    def test_more_buckets_than_items(self):
        result = assign_round_robin(["a"], ["X", "Y", "Z"])
        assert len(result) == 1
        assert result[0] == ("X", ["a"])

    def test_single_bucket(self):
        result = assign_round_robin(["a", "b"], ["X"])
        assert result == [("X", ["a", "b"])]


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

class TestPreview:

    def test_returns_plan(self):
        executor = CampaignExecutor()
        plan = executor.preview(_config())
        assert isinstance(plan, ExecutionPlan)

    def test_total_combos(self):
        plan = CampaignExecutor().preview(_config(n_keywords=4))
        assert plan.total_combos == 4

    def test_accounts_used(self):
        plan = CampaignExecutor().preview(_config(n_accounts=2, n_keywords=4))
        assert plan.accounts_used == 2

    def test_items_have_counts(self):
        plan = CampaignExecutor().preview(_config(n_accounts=2, n_keywords=4))
        assert plan.items[0].combo_count == 2
        assert plan.items[1].combo_count == 2

    def test_sample_titles(self):
        plan = CampaignExecutor().preview(_config(n_keywords=3))
        assert len(plan.sample_titles) >= 1

    def test_limit(self):
        plan = CampaignExecutor().preview(_config(n_keywords=10), limit=3)
        assert plan.total_combos == 3


# ---------------------------------------------------------------------------
# Execute — dry-run
# ---------------------------------------------------------------------------

class TestDryRun:

    def test_dry_run_succeeds(self):
        result = CampaignExecutor().execute(_config(), dry_run=True)
        assert result.total_attempted == 3
        assert result.total_succeeded == 3
        assert result.total_failed == 0

    def test_dry_run_with_limit(self):
        result = CampaignExecutor().execute(_config(n_keywords=10), dry_run=True, limit=5)
        assert result.total_attempted == 5


# ---------------------------------------------------------------------------
# Execute — live
# ---------------------------------------------------------------------------

class TestLiveExecute:

    def test_calls_runner_for_each(self):
        mock_runner = MagicMock()
        mock_editor = MagicMock()

        executor = CampaignExecutor(
            runner=mock_runner,
            editor_factory=lambda acc: mock_editor,
        )
        result = executor.execute(_config(n_accounts=1, n_keywords=2), dry_run=False)
        assert mock_runner.run.call_count == 2
        assert result.total_succeeded == 2

    def test_continues_on_failure(self):
        mock_runner = MagicMock()
        mock_runner.run.side_effect = [None, RuntimeError("fail"), None]
        mock_editor = MagicMock()

        executor = CampaignExecutor(
            runner=mock_runner,
            editor_factory=lambda acc: mock_editor,
        )
        result = executor.execute(_config(n_accounts=1, n_keywords=3), dry_run=False)
        assert result.total_attempted == 3
        assert result.total_succeeded == 2
        assert result.total_failed == 1

    def test_limit_respected(self):
        mock_runner = MagicMock()
        mock_editor = MagicMock()

        executor = CampaignExecutor(
            runner=mock_runner,
            editor_factory=lambda acc: mock_editor,
        )
        result = executor.execute(_config(n_keywords=10), dry_run=False, limit=3)
        assert mock_runner.run.call_count == 3
