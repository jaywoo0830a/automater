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
    assign_weighted,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _config(n_accounts=2, n_keywords=3):
    return {
        "accounts": [
            {"username": f"user{i}", "password": f"pw{i}"}
            for i in range(n_accounts)
        ],
        "titles": ["{keyword:region} 과외"],
        "keywords": {"region": [f"kw{i}" for i in range(n_keywords)]},
        "pools": {},
        "post": [{"paragraph": "{keyword:region}"}],
        "assets": ".",
        "publish": {},
        "run": {"interval": "0s"},
    }


# ---------------------------------------------------------------------------
# Weighted assignment
# ---------------------------------------------------------------------------

class TestAssignWeighted:

    def test_equal_weight_splits_evenly(self):
        a = {"username": "A", "weight": 1}
        b = {"username": "B", "weight": 1}
        result = assign_weighted(["a", "b", "c", "d"], [a, b])
        assert result[0] == (a, ["a", "b"])
        assert result[1] == (b, ["c", "d"])

    def test_unequal_weight(self):
        a = {"username": "A", "weight": 1}
        b = {"username": "B", "weight": 3}
        result = assign_weighted(list(range(80)), [a, b])
        a_items = result[0][1]
        b_items = result[1][1]
        assert len(a_items) == 20
        assert len(b_items) == 60

    def test_default_weight_is_one(self):
        a = {"username": "A"}
        b = {"username": "B"}
        result = assign_weighted(["a", "b", "c", "d"], [a, b])
        assert len(result[0][1]) == 2
        assert len(result[1][1]) == 2

    def test_single_bucket_gets_all(self):
        a = {"username": "A", "weight": 1}
        result = assign_weighted(["a", "b", "c"], [a])
        assert result == [(a, ["a", "b", "c"])]

    def test_remainder_distributed(self):
        a = {"username": "A", "weight": 1}
        b = {"username": "B", "weight": 1}
        result = assign_weighted(["a", "b", "c"], [a, b])
        counts = [len(r[1]) for r in result]
        assert sorted(counts) == [1, 2]
        assert sum(counts) == 3

    def test_empty_buckets_excluded(self):
        a = {"username": "A", "weight": 1}
        b = {"username": "B", "weight": 99}
        result = assign_weighted(["x"], [a, b])
        # Only one item, most weight goes to B
        assert len(result) == 1
        assert result[0][0] == b

    def test_max_posts_caps_account(self):
        a = {"username": "A", "weight": 1, "max_posts": 20}
        b = {"username": "B", "weight": 1}
        result = assign_weighted(list(range(80)), [a, b])
        a_count = len(result[0][1])
        b_count = len(result[1][1])
        assert a_count == 20
        assert b_count == 60  # overflow redistributed

    def test_max_posts_zero_means_unlimited(self):
        a = {"username": "A", "weight": 1, "max_posts": 0}
        b = {"username": "B", "weight": 1, "max_posts": 0}
        result = assign_weighted(list(range(10)), [a, b])
        assert len(result[0][1]) == 5
        assert len(result[1][1]) == 5

    def test_max_posts_with_weight(self):
        """weight 1:3 but A capped at 10 out of 80 → A=10, B=70."""
        a = {"username": "A", "weight": 1, "max_posts": 10}
        b = {"username": "B", "weight": 3}
        result = assign_weighted(list(range(80)), [a, b])
        assert len(result[0][1]) == 10
        assert len(result[1][1]) == 70

    def test_all_capped_drops_excess(self):
        """Both capped below total → excess items dropped."""
        a = {"username": "A", "max_posts": 5}
        b = {"username": "B", "max_posts": 5}
        result = assign_weighted(list(range(20)), [a, b])
        total = sum(len(r[1]) for r in result)
        assert total == 10

    def test_min_posts_guaranteed(self):
        """min_posts ensures minimum allocation even with low weight."""
        a = {"username": "A", "weight": 1, "min_posts": 30}
        b = {"username": "B", "weight": 9}
        result = assign_weighted(list(range(80)), [a, b])
        a_count = len(result[0][1])
        assert a_count >= 30

    def test_min_posts_with_small_total(self):
        """min_posts can't exceed total items."""
        a = {"username": "A", "min_posts": 50}
        b = {"username": "B", "min_posts": 50}
        result = assign_weighted(list(range(10)), [a, b])
        total = sum(len(r[1]) for r in result)
        assert total == 10

    def test_min_and_max_together(self):
        """min_posts=10, max_posts=20 → gets between 10 and 20."""
        a = {"username": "A", "min_posts": 10, "max_posts": 20}
        b = {"username": "B", "weight": 1}
        result = assign_weighted(list(range(80)), [a, b])
        a_count = len(result[0][1])
        assert 10 <= a_count <= 20


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


# ---------------------------------------------------------------------------
# Sequential scheduling — ++ mode
# ---------------------------------------------------------------------------

def _seq_config(n_keywords=5, schedule="++ 15m"):
    c = _config(n_accounts=1, n_keywords=n_keywords)
    c["publish"] = {"schedule": schedule}
    return c


class TestSequentialSchedule:

    def test_dry_run_all_succeed(self):
        executor = CampaignExecutor()
        result = executor.execute(_seq_config(), dry_run=True)
        assert result.total_succeeded == 5
        assert result.total_failed == 0

    def test_specs_get_progressive_times(self):
        """Each spec's publish.at is later than the previous."""
        captured_specs = []
        mock_runner = MagicMock()
        mock_runner.run.side_effect = lambda spec, editor: captured_specs.append(spec)
        mock_editor = MagicMock()

        executor = CampaignExecutor(
            runner=mock_runner,
            editor_factory=lambda acc: mock_editor,
        )
        executor.execute(_seq_config(n_keywords=4, schedule="++ 10m"), dry_run=False)

        assert len(captured_specs) == 4
        times = [s.schedule_at for s in captured_specs]
        for i in range(1, len(times)):
            assert times[i] > times[i - 1], f"post {i} not after post {i-1}"

    def test_range_produces_varying_intervals(self):
        """Range schedule produces different intervals between posts."""
        captured_specs = []
        mock_runner = MagicMock()
        mock_runner.run.side_effect = lambda spec, editor: captured_specs.append(spec)
        mock_editor = MagicMock()

        executor = CampaignExecutor(
            runner=mock_runner,
            editor_factory=lambda acc: mock_editor,
        )
        executor.execute(
            _seq_config(n_keywords=10, schedule="++ 1m ~ 30m"),
            dry_run=False,
        )

        times = [s.schedule_at for s in captured_specs]
        gaps = [(times[i] - times[i - 1]).total_seconds() for i in range(1, len(times))]
        # With 1m~30m range over 9 gaps, not all should be identical
        assert len(set(gaps)) > 1, f"All gaps identical: {gaps}"

    def test_mode_becomes_scheduled(self):
        """Sequential specs are converted to scheduled mode with at."""
        captured_specs = []
        mock_runner = MagicMock()
        mock_runner.run.side_effect = lambda spec, editor: captured_specs.append(spec)
        mock_editor = MagicMock()

        executor = CampaignExecutor(
            runner=mock_runner,
            editor_factory=lambda acc: mock_editor,
        )
        executor.execute(_seq_config(n_keywords=2), dry_run=False)

        for spec in captured_specs:
            assert spec.schedule_at is not None
