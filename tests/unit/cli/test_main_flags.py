"""
tests/unit/cli/test_main_flags.py
-----------------------------------
CLI flag parsing and on_resume override behavior.

Covers:
    --resume       → forces on_resume="skip"
    --restart      → forces on_resume="restart"
    both           → --restart wins
    neither        → YAML value preserved
"""

from __future__ import annotations

import pytest

from cli.__main__ import _parse_args


# ---------------------------------------------------------------------------
# _parse_args smoke
# ---------------------------------------------------------------------------

class TestParseArgs:

    def test_execute_only(self):
        args = _parse_args(["campaign.yaml", "--execute"])
        assert args.execute is True
        assert args.resume is False
        assert args.restart is False

    def test_execute_resume(self):
        args = _parse_args(["campaign.yaml", "--execute", "--resume"])
        assert args.resume is True
        assert args.restart is False

    def test_execute_restart(self):
        args = _parse_args(["campaign.yaml", "--execute", "--restart"])
        assert args.resume is False
        assert args.restart is True

    def test_both_flags(self):
        args = _parse_args(["campaign.yaml", "--execute", "--resume", "--restart"])
        assert args.resume is True
        assert args.restart is True


# ---------------------------------------------------------------------------
# on_resume override logic (in main())
# ---------------------------------------------------------------------------

def _apply_flag_overrides(config: dict, args) -> dict:
    """main()에서 추출한 flag → config override 로직 복제.

    main() 함수의 해당 블록과 동일하게 동작한다.
    실제 main()을 호출하지 않고 로직만 검증한다.
    """
    if args.restart:
        config.setdefault("run", {})["on_resume"] = "restart"
    elif args.resume:
        config.setdefault("run", {})["on_resume"] = "skip"
    return config


class TestOnResumeOverride:

    def test_restart_flag_overrides_yaml_skip(self):
        """YAML에 on_resume: skip이 있어도 --restart는 restart로 덮어쓴다."""
        config = {"run": {"on_resume": "skip"}}
        args = _parse_args(["campaign.yaml", "--execute", "--restart"])
        result = _apply_flag_overrides(config, args)
        assert result["run"]["on_resume"] == "restart"

    def test_resume_flag_overrides_yaml_restart(self):
        """YAML에 on_resume: restart가 있어도 --resume은 skip으로 덮어쓴다."""
        config = {"run": {"on_resume": "restart"}}
        args = _parse_args(["campaign.yaml", "--execute", "--resume"])
        result = _apply_flag_overrides(config, args)
        assert result["run"]["on_resume"] == "skip"

    def test_no_flag_preserves_yaml(self):
        """플래그 없으면 YAML 값 그대로."""
        config = {"run": {"on_resume": "skip"}}
        args = _parse_args(["campaign.yaml", "--execute"])
        result = _apply_flag_overrides(config, args)
        assert result["run"]["on_resume"] == "skip"

    def test_no_flag_preserves_yaml_restart(self):
        config = {"run": {"on_resume": "restart"}}
        args = _parse_args(["campaign.yaml", "--execute"])
        result = _apply_flag_overrides(config, args)
        assert result["run"]["on_resume"] == "restart"

    def test_no_flag_no_yaml_value(self):
        """YAML에 on_resume 자체가 없으면 그대로 없음 (실행 시 기본 restart)."""
        config = {"run": {}}
        args = _parse_args(["campaign.yaml", "--execute"])
        result = _apply_flag_overrides(config, args)
        assert "on_resume" not in result["run"]

    def test_restart_wins_over_resume(self):
        """둘 다 주어지면 --restart가 우선."""
        config = {"run": {"on_resume": "skip"}}
        args = _parse_args(["campaign.yaml", "--execute", "--resume", "--restart"])
        result = _apply_flag_overrides(config, args)
        assert result["run"]["on_resume"] == "restart"

    def test_restart_creates_run_section(self):
        """run 섹션이 없어도 restart 플래그가 생성."""
        config = {}
        args = _parse_args(["campaign.yaml", "--execute", "--restart"])
        result = _apply_flag_overrides(config, args)
        assert result["run"]["on_resume"] == "restart"
