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

def _build_message(campaign: str, result: Any) -> str:
    """ExecutionResult에서 알림 메시지를 생성한다."""
    lines = [
        f"[{campaign}] 캠페인 완료",
        f"성공: {result.total_succeeded} / 실패: {result.total_failed}",
    ]
    if result.errors:
        lines.append("오류:")
        for err in result.errors[:5]:
            lines.append(f"  - {err[:100]}")
        if len(result.errors) > 5:
            lines.append(f"  ... 외 {len(result.errors) - 5}건")
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
    """캠페인 결과에 따라 등록된 채널로 알림을 전송한다."""

    def __init__(
        self,
        channels: list[NotifyChannel],
        on: str = "always",
    ) -> None:
        self._channels = channels
        self._on = on  # "complete" | "fail" | "always"

    def send(self, result: Any, campaign: str = "campaign") -> None:
        """result(ExecutionResult)를 기반으로 알림 전송 여부를 결정하고 전송한다."""
        if not self._channels:
            return

        has_failure = result.total_failed > 0

        if self._on == "complete" and has_failure:
            return
        if self._on == "fail" and not has_failure:
            return

        message = _build_message(campaign, result)
        for channel in self._channels:
            try:
                channel.send(message)
            except Exception as exc:
                log.error("알림 전송 실패: %s", exc)


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
