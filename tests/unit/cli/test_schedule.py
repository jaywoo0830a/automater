"""
tests/unit/cli/test_schedule.py
---------------------------------
Schedule DSL parsing.

    now                → immediate
    now + 15s          → scheduled, at = now + 15 seconds
    now + 15m          → scheduled, at = now + 15 minutes
    now + 1h           → scheduled, at = now + 1 hour
    now + 1d           → scheduled, at = now + 1 day
    now + 30~60m       → scheduled, at = now + random(30,60) minutes
    now + 30m ~ 60m    → same, with explicit units
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cli.spec_builder import parse_schedule

KST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# now → immediate
# ---------------------------------------------------------------------------

class TestImmediate:

    def test_now(self):
        result = parse_schedule("now")
        assert result["mode"] == "immediate"
        assert result["at"] is None

    def test_empty(self):
        result = parse_schedule("")
        assert result["mode"] == "immediate"

    def test_none(self):
        result = parse_schedule(None)
        assert result["mode"] == "immediate"

    def test_immediate_string(self):
        """Backward compat."""
        result = parse_schedule("immediate")
        assert result["mode"] == "immediate"


# ---------------------------------------------------------------------------
# now + fixed offset
# ---------------------------------------------------------------------------

class TestFixedOffset:

    def test_seconds(self):
        before = datetime.now(tz=KST)
        result = parse_schedule("now + 15s")
        assert result["mode"] == "scheduled"
        assert result["at"] >= before + timedelta(seconds=14)

    def test_minutes(self):
        before = datetime.now(tz=KST)
        result = parse_schedule("now + 15m")
        assert result["at"] >= before + timedelta(minutes=14)

    def test_hours(self):
        before = datetime.now(tz=KST)
        result = parse_schedule("now + 1h")
        assert result["at"] >= before + timedelta(hours=0, minutes=59)

    def test_days(self):
        before = datetime.now(tz=KST)
        result = parse_schedule("now + 1d")
        assert result["at"] >= before + timedelta(hours=23)

    def test_at_is_kst(self):
        result = parse_schedule("now + 15m")
        assert result["at"].tzinfo is not None

    def test_mode_is_scheduled(self):
        result = parse_schedule("now + 30m")
        assert result["mode"] == "scheduled"

    def test_no_spaces(self):
        result = parse_schedule("now+15m")
        assert result["mode"] == "scheduled"
        assert result["at"] is not None

    def test_large_offset(self):
        before = datetime.now(tz=KST)
        result = parse_schedule("now + 120m")
        assert result["at"] >= before + timedelta(minutes=119)


# ---------------------------------------------------------------------------
# now + N~M range (random)
# ---------------------------------------------------------------------------

class TestRandomRange:

    def test_random_minutes(self):
        before = datetime.now(tz=KST)
        result = parse_schedule("now + 30m ~ 60m")
        assert result["mode"] == "scheduled"
        assert result["at"] >= before + timedelta(minutes=29)
        assert result["at"] <= before + timedelta(minutes=61)

    def test_random_seconds(self):
        before = datetime.now(tz=KST)
        result = parse_schedule("now + 10s ~ 30s")
        assert result["at"] >= before + timedelta(seconds=9)
        assert result["at"] <= before + timedelta(seconds=31)

    def test_random_hours(self):
        before = datetime.now(tz=KST)
        result = parse_schedule("now + 1h ~ 3h")
        assert result["at"] >= before + timedelta(minutes=59)
        assert result["at"] <= before + timedelta(hours=3, minutes=1)

    def test_mixed_units(self):
        """Different units on each side: 30s ~ 2m = 30sec ~ 120sec."""
        before = datetime.now(tz=KST)
        result = parse_schedule("now + 30s ~ 2m")
        assert result["mode"] == "scheduled"
        assert result["at"] >= before + timedelta(seconds=29)
        assert result["at"] <= before + timedelta(minutes=2, seconds=1)

    def test_random_at_is_kst(self):
        result = parse_schedule("now + 30m ~ 60m")
        assert result["at"].tzinfo is not None

    def test_no_spaces_range(self):
        result = parse_schedule("now+30m~60m")
        assert result["mode"] == "scheduled"


# ---------------------------------------------------------------------------
# Validator compat — at is always future
# ---------------------------------------------------------------------------

class TestValidatorCompat:

    def test_scheduled_at_is_future(self):
        now = datetime.now(tz=KST)
        result = parse_schedule("now + 15m")
        assert result["at"] > now

    def test_random_at_is_future(self):
        now = datetime.now(tz=KST)
        result = parse_schedule("now + 30m ~ 60m")
        assert result["at"] > now

    def test_immediate_passes_validator(self):
        """Immediate mode has no schedule_at — validator should not check."""
        from automator.contracts import PostingSpec
        from automator.options import AccountOption
        from automator.spec_validator import SpecValidator

        spec = PostingSpec(
            account=AccountOption(username="u", password="p"),
            title="t",
        )
        SpecValidator().validate(spec)  # should not raise

    def test_scheduled_passes_validator(self):
        """Scheduled mode with future at — validator passes."""
        from automator.contracts import PostingSpec
        from automator.options import AccountOption
        from automator.spec_validator import SpecValidator

        result = parse_schedule("now + 15m")
        spec = PostingSpec(
            account=AccountOption(username="u", password="p"),
            title="t",
            schedule_at=result["at"],
        )
        SpecValidator().validate(spec)  # should not raise


# ---------------------------------------------------------------------------
# Account override (kept from previous)
# ---------------------------------------------------------------------------

class TestAccountOverride:

    def test_account_headless_overrides_global(self):
        from cli.spec_builder import merge_account_run
        global_run = {"interval": "60s", "headless": True}
        account = {"username": "u", "password": "p", "headless": False}
        merged = merge_account_run(global_run, account)
        assert merged["headless"] is False

    def test_account_interval_overrides_global(self):
        from cli.spec_builder import merge_account_run
        global_run = {"interval": "60s", "headless": True}
        account = {"username": "u", "password": "p", "interval": "120s"}
        merged = merge_account_run(global_run, account)
        assert merged["interval"] == "120s"

    def test_account_keys_not_leaked(self):
        from cli.spec_builder import merge_account_run
        global_run = {"interval": "60s"}
        account = {"username": "u", "password": "p", "blog_id": "b", "headless": False}
        merged = merge_account_run(global_run, account)
        assert "username" not in merged
        assert merged["headless"] is False

    def test_no_overrides_returns_global(self):
        from cli.spec_builder import merge_account_run
        global_run = {"interval": "60s", "headless": True}
        account = {"username": "u", "password": "p"}
        merged = merge_account_run(global_run, account)
        assert merged == global_run


# ---------------------------------------------------------------------------
# ++ sequential scheduling
# ---------------------------------------------------------------------------

class TestSequential:

    def test_bare_plus_plus(self):
        result = parse_schedule("++")
        assert result["mode"] == "sequential"
        assert result["interval_lo"] == 900  # default 15m

    def test_plus_plus_fixed(self):
        result = parse_schedule("++ 15m")
        assert result["mode"] == "sequential"
        assert result["interval_lo"] == 900
        assert result["interval_hi"] == 900

    def test_plus_plus_seconds(self):
        result = parse_schedule("++ 30s")
        assert result["interval_lo"] == 30

    def test_plus_plus_hours(self):
        result = parse_schedule("++ 2h")
        assert result["interval_lo"] == 7200

    def test_plus_plus_range(self):
        result = parse_schedule("++ 15m ~ 30m")
        assert result["mode"] == "sequential"
        assert result["interval_lo"] == 900
        assert result["interval_hi"] == 1800

    def test_plus_plus_range_mixed_units(self):
        result = parse_schedule("++ 30s ~ 2m")
        assert result["interval_lo"] == 30
        assert result["interval_hi"] == 120

    def test_plus_plus_at_is_none(self):
        """Sequential mode has no pre-computed at."""
        result = parse_schedule("++")
        assert result["at"] is None

    def test_plus_plus_no_spaces(self):
        result = parse_schedule("++15m")
        assert result["mode"] == "sequential"
        assert result["interval_lo"] == 900
