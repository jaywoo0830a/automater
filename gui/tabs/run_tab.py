"""실행 설정 탭 - 간격, 병렬, 알림, 브라우저 설정."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QSpinBox, QCheckBox, QComboBox, QLabel, QLineEdit,
)

from gui.collapsible import CollapsibleSection


class RunTab(QWidget):

    def __init__(self) -> None:
        super().__init__()

        # ── 기본 설정 ──
        self._interval = QSpinBox()
        self._interval.setRange(0, 3600)
        self._interval.setValue(60)
        self._interval.setSuffix(" 초")

        self._headless = QCheckBox("헤드리스 모드 (브라우저 창 숨김)")
        self._headless.setChecked(True)

        self._on_failure = QComboBox()
        self._on_failure.addItems(["계속 진행 (continue)", "즉시 중단 (stop)"])
        self._on_failure.setToolTip(
            "continue: 실패해도 다음 조합 계속 실행\n"
            "stop: 첫 실패 즉시 캠페인 전체 중단"
        )

        self._on_resume = QComboBox()
        self._on_resume.addItems(["처음부터 (restart)", "이어서 (skip)"])

        basic_form = QFormLayout()
        basic_form.addRow("포스트 간 대기:", self._interval)
        basic_form.addRow("", self._headless)
        basic_form.addRow("실패 시:", self._on_failure)
        basic_form.addRow("재실행 시:", self._on_resume)

        basic_group = QGroupBox("기본")
        basic_group.setLayout(basic_form)

        # ── 병렬 실행 (접힘) ──
        self._parallel = QCheckBox("계정별 병렬 실행")
        self._parallel.setChecked(False)

        self._max_workers = QSpinBox()
        self._max_workers.setRange(1, 20)
        self._max_workers.setValue(3)
        self._max_workers.setEnabled(False)
        self._parallel.toggled.connect(self._max_workers.setEnabled)

        advanced_parallel = CollapsibleSection("병렬 실행")
        advanced_parallel.add_row("", self._parallel)
        advanced_parallel.add_row("동시 실행 계정 수:", self._max_workers)

        # ── 알림 (접힘) ──
        self._notify_on = QComboBox()
        self._notify_on.addItems(["사용 안 함", "항상 (always)", "성공 시 (complete)", "실패 시 (fail)"])

        self._tg_token = QLineEdit()
        self._tg_token.setPlaceholderText("BotFather에서 받은 봇 토큰")
        self._tg_chat_id = QLineEdit()
        self._tg_chat_id.setPlaceholderText("채팅 ID")

        advanced_notify = CollapsibleSection("알림 (실패 즉시 + 완료 요약)")
        advanced_notify.add_row("알림 조건:", self._notify_on)
        advanced_notify.add_row("Telegram 토큰:", self._tg_token)
        advanced_notify.add_row("Telegram 채팅 ID:", self._tg_chat_id)
        self._notify_on.setToolTip(
            "always: 완료 요약 항상 + 실패 발생 시 즉시 알림\n"
            "fail: 실패 발생 시 즉시 알림 + 실패 있는 경우만 완료 요약\n"
            "complete: 성공 완료 시에만 알림 (실패 알림 없음)"
        )

        layout = QVBoxLayout()
        layout.addWidget(basic_group)
        layout.addWidget(advanced_parallel)
        layout.addWidget(advanced_notify)
        layout.addStretch()
        self.setLayout(layout)

    _FAIL_MAP = {"계속 진행 (continue)": "continue", "즉시 중단 (stop)": "stop"}
    _FAIL_REV = {v: k for k, v in _FAIL_MAP.items()}
    _RESUME_MAP = {"처음부터 (restart)": "restart", "이어서 (skip)": "skip"}
    _RESUME_REV = {v: k for k, v in _RESUME_MAP.items()}
    _NOTIFY_MAP = {
        "사용 안 함": "",
        "항상 (always)": "always",
        "성공 시 (complete)": "complete",
        "실패 시 (fail)": "fail",
    }
    _NOTIFY_REV = {v: k for k, v in _NOTIFY_MAP.items()}

    def to_dict(self) -> dict:
        run: dict = {}

        run["interval"] = f"{self._interval.value()}s"
        run["on_failure"] = self._FAIL_MAP.get(self._on_failure.currentText(), "continue")
        run["on_resume"] = self._RESUME_MAP.get(self._on_resume.currentText(), "restart")
        run["headless"] = self._headless.isChecked()
        run["parallel"] = self._parallel.isChecked()
        if self._parallel.isChecked():
            run["max_workers"] = self._max_workers.value()

        result: dict = {"run": run}

        # 알림
        notify_on = self._NOTIFY_MAP.get(self._notify_on.currentText(), "")
        token = self._tg_token.text().strip()
        chat_id = self._tg_chat_id.text().strip()
        if notify_on and token and chat_id:
            result["notify"] = {
                "on": notify_on,
                "channels": [
                    {"type": "telegram", "token": token, "chat_id": chat_id},
                ],
            }

        return result

    def from_dict(self, data: dict) -> None:
        run = data.get("run", {})

        interval_raw = str(run.get("interval", "60s"))
        self._interval.setValue(int(interval_raw.rstrip("s")))

        self._headless.setChecked(run.get("headless", True))

        on_failure = run.get("on_failure", "continue")
        display = self._FAIL_REV.get(on_failure, "계속 진행 (continue)")
        idx = self._on_failure.findText(display)
        if idx >= 0:
            self._on_failure.setCurrentIndex(idx)

        on_resume = run.get("on_resume", "restart")
        display = self._RESUME_REV.get(on_resume, "처음부터 (restart)")
        idx = self._on_resume.findText(display)
        if idx >= 0:
            self._on_resume.setCurrentIndex(idx)

        self._parallel.setChecked(run.get("parallel", False))
        self._max_workers.setValue(int(run.get("max_workers", 3)))

        # 알림
        notify = data.get("notify", {})
        notify_on = notify.get("on", "")
        display = self._NOTIFY_REV.get(notify_on, "사용 안 함")
        idx = self._notify_on.findText(display)
        if idx >= 0:
            self._notify_on.setCurrentIndex(idx)

        channels = notify.get("channels", [])
        for ch in channels:
            if isinstance(ch, dict) and ch.get("type") == "telegram":
                self._tg_token.setText(str(ch.get("token", "")))
                self._tg_chat_id.setText(str(ch.get("chat_id", "")))
                break
