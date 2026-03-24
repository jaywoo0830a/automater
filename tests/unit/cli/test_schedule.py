"""
tests/unit/cli/test_schedule.py
---------------------------------
publish.schedule string parsing.

    immediate      → mode="immediate"
    fixed HH:MM    → mode="fixed", at=today HH:MM KST
    random ±Nmin   → mode="random_window", jitter_minutes=N
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cli.spec_builder import parse_schedule

KST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# immediate
# ---------------------------------------------------------------------------

class TestImmediate:

    def test_immediate_string(self):
        result = parse_schedule("immediate")
        assert result["mode"] == "immediate"
        assert result["at"] is None

    def test_empty_string(self):
        result = parse_schedule("")
        assert result["mode"] == "immediate"

    def test_none(self):
        result = parse_schedule(None)
        assert result["mode"] == "immediate"


# ---------------------------------------------------------------------------
# fixed HH:MM
# ---------------------------------------------------------------------------

class TestFixed:

    def test_fixed_parses_time(self):
        result = parse_schedule("fixed 09:00")
        assert result["mode"] == "fixed"
        assert result["at"].hour == 9
        assert result["at"].minute == 0

    def test_fixed_afternoon(self):
        result = parse_schedule("fixed 14:30")
        assert result["at"].hour == 14
        assert result["at"].minute == 30

    def test_fixed_has_kst(self):
        result = parse_schedule("fixed 09:00")
        assert result["at"].tzinfo is not None

    def test_fixed_no_jitter(self):
        result = parse_schedule("fixed 09:00")
        assert result.get("jitter_minutes", 0) == 0


# ---------------------------------------------------------------------------
# random ±Nmin
# ---------------------------------------------------------------------------

class TestRandom:

    def test_random_30min(self):
        result = parse_schedule("random ±30min")
        assert result["mode"] == "random_window"
        assert result["jitter_minutes"] == 30

    def test_random_60min(self):
        result = parse_schedule("random ±60min")
        assert result["jitter_minutes"] == 60

    def test_random_has_at(self):
        result = parse_schedule("random ±30min")
        assert result["at"] is not None

    def test_random_at_is_kst(self):
        result = parse_schedule("random ±30min")
        assert result["at"].tzinfo is not None


# ---------------------------------------------------------------------------
# Account override
# ---------------------------------------------------------------------------

class TestAccountOverride:

    def test_account_headless_overrides_global(self):
        from cli.spec_builder import merge_account_run
        global_run = {"interval": "60s", "headless": True}
        account = {"username": "u", "password": "p", "headless": False}
        merged = merge_account_run(global_run, account)
        assert merged["headless"] is False
        assert merged["interval"] == "60s"

    def test_account_interval_overrides_global(self):
        from cli.spec_builder import merge_account_run
        global_run = {"interval": "60s", "headless": True}
        account = {"username": "u", "password": "p", "interval": "120s"}
        merged = merge_account_run(global_run, account)
        assert merged["interval"] == "120s"

    def test_account_keys_not_leaked(self):
        """username, password, blog_id etc. don't leak into run config."""
        from cli.spec_builder import merge_account_run
        global_run = {"interval": "60s"}
        account = {"username": "u", "password": "p", "blog_id": "b", "headless": False}
        merged = merge_account_run(global_run, account)
        assert "username" not in merged
        assert "password" not in merged
        assert "blog_id" not in merged
        assert merged["headless"] is False

    def test_no_overrides_returns_global(self):
        from cli.spec_builder import merge_account_run
        global_run = {"interval": "60s", "headless": True}
        account = {"username": "u", "password": "p"}
        merged = merge_account_run(global_run, account)
        assert merged == global_run
