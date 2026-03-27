"""
automator/spec_validator.py
-----------------------------
SpecValidator — validates a PostingSpec before execution.

Extracted from PostingJob.validate(). Single responsibility: detect
configuration errors early so the runner never starts invalid work.
"""

from __future__ import annotations

from datetime import datetime

from automator.contracts import PostingSpec
from automator.layout import validate_sections
from automator.title_generator import validate_template
from automator.options import KST


class SpecValidator:
    """Stateless validator — call validate(spec) before running."""

    def validate(self, spec: PostingSpec) -> None:
        """
        Raise ValueError if spec is misconfigured.

        Checks: account, title template, section layout, publish schedule,
        run settings.
        """
        self._validate_account(spec)
        self._validate_title(spec)
        validate_sections(list(spec.body))
        self._validate_publish(spec)
        self._validate_setting(spec)

    @staticmethod
    def _validate_account(spec: PostingSpec) -> None:
        if not spec.account.username.strip():
            raise ValueError("AccountOption.username must not be empty")
        if not spec.account.password.strip():
            raise ValueError("AccountOption.password must not be empty")

    @staticmethod
    def _validate_title(spec: PostingSpec) -> None:
        if spec.title and not spec.title.fixed_title:
            if spec.title.template:
                validate_template(spec.title.template)

    @staticmethod
    def _validate_publish(spec: PostingSpec) -> None:
        pub = spec.publish
        if pub.min_tags > pub.max_tags:
            raise ValueError("PublishOption.min_tags must be <= max_tags")
        if not (0 <= pub.backlink_ratio <= 100):
            raise ValueError("PublishOption.backlink_ratio must be 0-100")
        if not (0 <= pub.internal_link_ratio <= 100):
            raise ValueError("PublishOption.internal_link_ratio must be 0-100")

        mode = pub.mode
        if mode == "immediate":
            return
        if mode == "sequential":
            return  # at is computed at runtime by CampaignExecutor

        # All non-immediate modes require a future, timezone-aware `at`
        if pub.at is None:
            raise ValueError(
                f"PublishOption.at 은 mode='{mode}'일 때 필수입니다."
            )
        if pub.at.tzinfo is None:
            raise ValueError(
                "PublishOption.at 은 timezone-aware datetime 이어야 합니다. "
                "예: datetime(2025, 6, 1, 9, 0, tzinfo=KST)"
            )
        now = datetime.now(tz=KST)
        if pub.at <= now:
            raise ValueError(
                "PublishOption.at 은 현재 시각보다 미래여야 합니다. "
                f"(at={pub.at.isoformat()}, now={now.isoformat()})"
            )

    @staticmethod
    def _validate_setting(spec: PostingSpec) -> None:
        setting = spec.setting
        if setting.post_interval < 0:
            raise ValueError("RunSetting.post_interval must be >= 0")
        if setting.max_daily_posts < 1:
            raise ValueError("RunSetting.max_daily_posts must be >= 1")
