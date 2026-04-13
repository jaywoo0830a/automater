"""
tests/unit/cli/test_campaign_executor.py
------------------------------------------
Campaign executor — orchestration, round-robin, preview, execute.
"""

from __future__ import annotations

from pathlib import Path
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
        # 명시적 on_failure=continue (interval 보존)
        config = _config(n_accounts=1, n_keywords=3)
        config["run"]["on_failure"] = "continue"
        result = executor.execute(config, dry_run=False)
        assert result.total_attempted == 3
        assert result.total_succeeded == 2
        assert result.total_failed == 1
        assert result.stop_requested is False

    def test_stops_on_first_failure(self):
        """on_failure=stop: 첫 실패 즉시 캠페인 중단."""
        mock_runner = MagicMock()
        mock_runner.run.side_effect = [None, RuntimeError("fail"), None, None, None]
        mock_editor = MagicMock()

        executor = CampaignExecutor(
            runner=mock_runner,
            editor_factory=lambda acc: mock_editor,
        )
        config = _config(n_accounts=1, n_keywords=5)
        config["run"]["on_failure"] = "stop"
        result = executor.execute(config, dry_run=False)

        # 첫 성공 → 두 번째 실패 → 나머지 3개 건너뜀
        assert result.total_attempted == 2
        assert result.total_succeeded == 1
        assert result.total_failed == 1
        assert result.stop_requested is True
        # runner.run은 2번만 호출됨
        assert mock_runner.run.call_count == 2

    def test_stop_across_multiple_accounts(self):
        """여러 계정 중 하나에서 실패 발생 → 다음 계정도 건너뜀."""
        mock_runner = MagicMock()
        mock_runner.run.side_effect = [RuntimeError("fail"), None, None, None]
        mock_editor = MagicMock()

        executor = CampaignExecutor(
            runner=mock_runner,
            editor_factory=lambda acc: mock_editor,
        )
        config = _config(n_accounts=2, n_keywords=2)  # 4 combos total
        config["run"]["on_failure"] = "stop"
        result = executor.execute(config, dry_run=False)

        assert result.stop_requested is True
        # 첫 번째 호출이 실패 → 즉시 중단
        assert result.total_failed == 1
        assert mock_runner.run.call_count == 1

    def test_immediate_failure_alert_sent(self):
        """실패 발생 시 notifier.send_failure_alert 즉시 호출."""
        from unittest.mock import patch

        mock_runner = MagicMock()
        mock_runner.run.side_effect = [None, RuntimeError("ugly error"), None]
        mock_editor = MagicMock()
        mock_notifier = MagicMock()

        executor = CampaignExecutor(
            runner=mock_runner,
            editor_factory=lambda acc: mock_editor,
        )
        config = _config(n_accounts=1, n_keywords=3)
        config["notify"] = {
            "on": "always",
            "channels": [
                {"type": "telegram", "token": "t", "chat_id": "c"},
            ],
        }

        with patch("cli.campaign_executor.build_notifier", return_value=mock_notifier):
            executor.execute(config, dry_run=False)

        # 실패 1번 → 즉시 알림 1번
        assert mock_notifier.send_failure_alert.call_count == 1
        call_kwargs = mock_notifier.send_failure_alert.call_args.kwargs
        assert "ugly error" in call_kwargs["error"]
        # 캠페인 완료 요약 알림
        mock_notifier.send_summary.assert_called_once()

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

    def test_midnight_crossing_increments_date(self):
        """23시 시작 + 30분 간격 → 자정을 넘으면 날짜가 자동으로 +1일."""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import patch

        _KST = timezone(timedelta(hours=9))

        captured_specs = []
        mock_runner = MagicMock()
        mock_runner.run.side_effect = lambda spec, editor: captured_specs.append(spec)
        mock_editor = MagicMock()

        executor = CampaignExecutor(
            runner=mock_runner,
            editor_factory=lambda acc: mock_editor,
        )

        # 23:30에 시작하도록 고정
        fake_now = datetime(2026, 4, 13, 23, 30, 0, tzinfo=_KST)
        with patch("cli.campaign_executor.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            executor.execute(
                _seq_config(n_keywords=4, schedule="++ 30m"),
                dry_run=False,
            )

        assert len(captured_specs) == 4
        times = [s.schedule_at for s in captured_specs]

        # 순차 증가
        for i in range(1, len(times)):
            assert times[i] > times[i - 1], f"post {i} not after post {i-1}"

        # 자정 넘김 확인: 23:30 + 30m = 00:00 → 4/14일
        assert times[0].day == 14, f"첫 포스트 날짜: {times[0]}"
        # 마지막(4번째) 포스트: 23:30 + 30m*4 = 01:30 → 4/14일
        assert times[-1].day == 14, f"마지막 포스트 날짜: {times[-1]}"
        assert times[-1].hour >= 1, f"마지막 포스트 시간: {times[-1]}"

    def test_midnight_crossing_month_boundary(self):
        """월말 23시 시작 → 자정 넘기면 다음 달로 넘어가는지 확인."""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import patch

        _KST = timezone(timedelta(hours=9))

        captured_specs = []
        mock_runner = MagicMock()
        mock_runner.run.side_effect = lambda spec, editor: captured_specs.append(spec)
        mock_editor = MagicMock()

        executor = CampaignExecutor(
            runner=mock_runner,
            editor_factory=lambda acc: mock_editor,
        )

        # 4/30 23:40에 시작
        fake_now = datetime(2026, 4, 30, 23, 40, 0, tzinfo=_KST)
        with patch("cli.campaign_executor.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            executor.execute(
                _seq_config(n_keywords=3, schedule="++ 15m"),
                dry_run=False,
            )

        times = [s.schedule_at for s in captured_specs]

        # 순차 증가
        for i in range(1, len(times)):
            assert times[i] > times[i - 1]

        # 첫 포스트: 23:40 + 15m = 23:55 → 4/30
        assert times[0].month == 4, f"첫 포스트: {times[0]}"
        # 마지막(3번째): 23:40 + 15m*3 = 00:25 → 5/1
        assert times[-1].month == 5, f"마지막 포스트: {times[-1]}"
        assert times[-1].day == 1, f"마지막 포스트 날짜: {times[-1]}"

    def test_from_starts_at_future_base(self):
        """++ 15m from +1d → 첫 포스트가 ~24시간 뒤부터 시작."""
        from datetime import datetime, timedelta, timezone

        _KST = timezone(timedelta(hours=9))

        captured_specs = []
        mock_runner = MagicMock()
        mock_runner.run.side_effect = lambda spec, editor: captured_specs.append(spec)
        mock_editor = MagicMock()

        executor = CampaignExecutor(
            runner=mock_runner,
            editor_factory=lambda acc: mock_editor,
        )
        executor.execute(
            _seq_config(n_keywords=3, schedule="++ 15m from +1d"),
            dry_run=False,
        )

        now = datetime.now(tz=_KST)
        times = [s.schedule_at for s in captured_specs]

        # 모든 예약이 ~24시간 뒤
        for t in times:
            diff = (t - now).total_seconds()
            assert diff > 86_000, f"너무 이름: {t} (diff={diff}s)"

        # 순차 증가
        for i in range(1, len(times)):
            assert times[i] > times[i - 1]

        # 간격이 15분 (900초)
        for i in range(1, len(times)):
            gap = (times[i] - times[i - 1]).total_seconds()
            assert gap == 900, f"간격 불일치: {gap}s"

    def test_from_with_time_starts_at_specified_hour(self):
        """++ 15m from +1d 09:00 → 내일 9시부터 15분 간격."""
        from datetime import datetime, timedelta, timezone

        _KST = timezone(timedelta(hours=9))

        captured_specs = []
        mock_runner = MagicMock()
        mock_runner.run.side_effect = lambda spec, editor: captured_specs.append(spec)
        mock_editor = MagicMock()

        executor = CampaignExecutor(
            runner=mock_runner,
            editor_factory=lambda acc: mock_editor,
        )
        executor.execute(
            _seq_config(n_keywords=3, schedule="++ 15m from +1d 09:00"),
            dry_run=False,
        )

        times = [s.schedule_at for s in captured_specs]

        # 첫 포스트: 내일 09:15
        assert times[0].hour == 9
        assert times[0].minute == 15
        # 두 번째: 09:30
        assert times[1].minute == 30
        # 세 번째: 09:45
        assert times[2].minute == 45

    def test_resume_with_past_schedule_falls_back_to_now(self, tmp_path):
        """복원된 last_schedule_at이 과거이면 현재 시각 기준으로 재계산."""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import MagicMock
        from cli.progress import ProgressTracker

        _KST = timezone(timedelta(hours=9))

        # 과거 시각을 progress 파일에 심어둔다
        config_path = str(tmp_path / "test_campaign.yaml")
        Path(config_path).write_text("{}", encoding="utf-8")
        pt = ProgressTracker(config_path, str(tmp_path))
        past = datetime.now(tz=_KST) - timedelta(hours=8)
        pt.last_schedule_at = past.isoformat()
        pt.mark_done(0)  # 첫 combo는 이미 완료로 간주
        pt.mark_done(1)

        captured_specs = []
        mock_runner = MagicMock()
        mock_runner.run.side_effect = lambda spec, editor: captured_specs.append(spec)
        mock_editor = MagicMock()

        executor = CampaignExecutor(
            runner=mock_runner,
            editor_factory=lambda acc: mock_editor,
        )

        config = _seq_config(n_keywords=5, schedule="++ 15m")
        config["_config_path"] = config_path
        config["_base_dir"] = str(tmp_path)
        config["run"]["on_resume"] = "skip"

        result = executor.execute(config, dry_run=False)

        # 완료된 2개는 skip → 3개만 실행됨
        assert len(captured_specs) == 3
        # 모든 예약 시간이 현재 이후
        now_kst = datetime.now(tz=_KST)
        for spec in captured_specs:
            assert spec.schedule_at > now_kst, (
                f"과거 시간으로 예약됨: {spec.schedule_at}"
            )
        # 순차 증가 보장
        times = [s.schedule_at for s in captured_specs]
        for i in range(1, len(times)):
            assert times[i] > times[i - 1]
