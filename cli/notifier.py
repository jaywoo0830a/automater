"""
cli/notifier.py
----------------
캠페인 완료 알림.

채널 추상화:
    NotifyChannel (ABC) -> TelegramChannel, (향후 WebhookChannel, ...)

사용:
    notifier = build_notifier(config.get("notify"))
    notifier.send(result, campaign_name)
"""

from __future__ import annotations

import logging
import urllib.request
import urllib.parse
import json
from abc import ABC, abstractmethod
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result summary
# ---------------------------------------------------------------------------

def _format_combo(values: dict[str, str]) -> str:
    return ", ".join(f"{k}={v}" for k, v in values.items())


def _build_summary_message(campaign: str, result: Any) -> str:
    """캠페인 완료 시 전송하는 요약 메시지. 모든 combo를 전부 나열한다."""
    stopped = getattr(result, "stop_requested", False)
    header = (
        f"<b>[{campaign}] 캠페인 중단됨 (on_failure=stop)</b>"
        if stopped else
        f"<b>[{campaign}] 캠페인 완료</b>"
    )
    lines = [
        header,
        f"성공: {result.total_succeeded} / 실패: {result.total_failed}",
    ]

    if result.succeeded_combos:
        lines.append(f"\n<b>✓ 성공 ({len(result.succeeded_combos)}건)</b>")
        for rec in result.succeeded_combos:
            entry = f"  [{_format_combo(rec.combo_values)}]"
            title = getattr(rec, "title", "")
            if title:
                entry += f"\n    → {title}"
            lines.append(entry)

    if result.failed_combos:
        lines.append(f"\n<b>✗ 실패 ({len(result.failed_combos)}건)</b>")
        for rec in result.failed_combos:
            entry = f"  [{_format_combo(rec.combo_values)}]"
            title = getattr(rec, "title", "")
            if title:
                entry += f"\n    제목: {title}"
            if rec.error:
                entry += f"\n    에러: {rec.error}"
            lines.append(entry)

    return "\n".join(lines)


def _build_failure_alert_message(
    campaign: str,
    username: str,
    progress: str,
    combo_values: dict[str, str],
    title: str,
    error: str,
) -> str:
    """개별 combo 실패 시 즉시 전송하는 실시간 알림 메시지."""
    lines = [
        f"<b>🚨 [{campaign}] 실패 발생</b>",
        f"계정: <code>{username}</code>",
        f"진행: {progress}",
        f"조합: [{_format_combo(combo_values)}]",
    ]
    if title:
        lines.append(f"제목: {title}")
    lines.append(f"\n<b>에러:</b>\n<pre>{error}</pre>")
    return "\n".join(lines)


def _build_manual_login_required_message(
    campaign: str,
    username: str,
    error: str,
) -> str:
    """세션 자동 복구 실패 시 전송하는 수동 로그인 요청 메시지."""
    lines = [
        f"<b>🔐 [{campaign}] 수동 로그인 필요</b>",
        f"계정: <code>{username}</code>",
        "자동 로그인 복구에 실패했습니다. 수동으로 로그인한 뒤 캠페인을 다시 실행해주세요.",
        f"\n<b>에러:</b>\n<pre>{error}</pre>",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Channel ABC
# ---------------------------------------------------------------------------

class NotifyChannel(ABC):
    """알림 채널 추상 클래스."""

    @abstractmethod
    def send(self, message: str) -> bool:
        """메시지를 전송한다. 성공 시 True."""


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

class TelegramChannel(NotifyChannel):
    """Telegram Bot API로 메시지를 전송한다. 외부 의존성 없음 (urllib만 사용)."""

    def __init__(self, token: str, chat_id: str) -> None:
        self._token = token
        self._chat_id = chat_id

    def send(self, message: str) -> bool:
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": self._chat_id,
            "text": message,
            "parse_mode": "HTML",
        }).encode("utf-8")

        try:
            req = urllib.request.Request(url, data=data, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as exc:
            log.error("Telegram 알림 전송 실패: %s", exc)
            return False


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_CHANNEL_REGISTRY: dict[str, type] = {
    "telegram": TelegramChannel,
}


def _build_channel(cfg: dict[str, Any]) -> NotifyChannel | None:
    """채널 설정 dict에서 NotifyChannel 인스턴스를 생성한다."""
    channel_type = cfg.get("type", "")
    if channel_type not in _CHANNEL_REGISTRY:
        log.warning("알 수 없는 알림 채널: %s", channel_type)
        return None

    if channel_type == "telegram":
        token = cfg.get("token", "")
        chat_id = str(cfg.get("chat_id", ""))
        if not token or not chat_id:
            log.warning("Telegram 설정 불완전: token/chat_id 필요")
            return None
        return TelegramChannel(token, chat_id)

    return None


class Notifier:
    """캠페인 결과에 따라 등록된 채널로 알림을 전송한다.

    두 가지 종류의 알림:
        send_failure_alert — 실패가 발생한 즉시 호출. on=complete면 스킵.
        send_summary       — 캠페인 종료 시 1회 호출. on에 따라 전송 여부 결정.
    """

    def __init__(
        self,
        channels: list[NotifyChannel],
        on: str = "always",
    ) -> None:
        self._channels = channels
        self._on = on  # "complete" | "fail" | "always"

    def _broadcast(self, message: str) -> None:
        for channel in self._channels:
            try:
                channel.send(message)
            except Exception as exc:
                log.error("알림 전송 실패: %s", exc)

    def send_summary(self, result: Any, campaign: str = "campaign") -> None:
        """캠페인 완료 시 전송하는 요약 알림."""
        if not self._channels:
            return

        has_failure = result.total_failed > 0

        if self._on == "complete" and has_failure:
            return
        if self._on == "fail" and not has_failure:
            return

        message = _build_summary_message(campaign, result)
        self._broadcast(message)

    def send_failure_alert(
        self,
        campaign: str,
        username: str,
        progress: str,
        combo_values: dict[str, str],
        title: str,
        error: str,
    ) -> None:
        """개별 combo 실패 시 즉시 전송하는 실시간 알림.

        on=complete (성공 시에만 알림)인 경우에는 실패 알림도 보내지 않는다.
        on=always / on=fail인 경우 모두 실패 시 알림 전송.
        """
        if not self._channels:
            return
        if self._on == "complete":
            return

        message = _build_failure_alert_message(
            campaign=campaign,
            username=username,
            progress=progress,
            combo_values=combo_values,
            title=title,
            error=error,
        )
        self._broadcast(message)

    def send_manual_login_required_alert(
        self,
        campaign: str,
        username: str,
        error: str,
    ) -> None:
        """세션 자동 복구 실패 시 수동 로그인 요청 알림.

        on=complete인 경우에도 세션 문제는 사용자 개입이 반드시 필요하므로 전송한다.
        """
        if not self._channels:
            return

        message = _build_manual_login_required_message(
            campaign=campaign,
            username=username,
            error=error,
        )
        self._broadcast(message)

    # 하위 호환을 위해 기존 send() 유지 — send_summary로 위임
    def send(self, result: Any, campaign: str = "campaign") -> None:
        """deprecated alias for send_summary()."""
        self.send_summary(result, campaign)


def build_notifier(notify_config: dict[str, Any] | None) -> Notifier | None:
    """DSL notify 설정에서 Notifier를 생성한다. 설정 없으면 None."""
    if not notify_config:
        return None

    on = str(notify_config.get("on", "always"))
    channels_cfg = notify_config.get("channels", [])
    if not isinstance(channels_cfg, list):
        return None

    channels: list[NotifyChannel] = []
    for cfg in channels_cfg:
        if isinstance(cfg, dict):
            ch = _build_channel(cfg)
            if ch:
                channels.append(ch)

    if not channels:
        return None

    return Notifier(channels, on=on)
