"""실행 설정 탭 — 간격, 브라우저 설정."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QSpinBox, QCheckBox, QComboBox, QLabel,
)


class RunTab(QWidget):

    def __init__(self) -> None:
        super().__init__()

        # ── 실행 간격 ──
        self._interval = QSpinBox()
        self._interval.setRange(0, 3600)
        self._interval.setValue(60)
        self._interval.setSuffix(" 초")

        self._upload_delay = QSpinBox()
        self._upload_delay.setRange(0, 30000)
        self._upload_delay.setValue(1500)
        self._upload_delay.setSuffix(" ms")
        self._upload_delay.setSingleStep(500)

        timing_form = QFormLayout()
        timing_form.addRow("포스트 간 대기:", self._interval)
        timing_form.addRow("이미지 업로드 딜레이:", self._upload_delay)

        timing_group = QGroupBox("타이밍")
        timing_group.setLayout(timing_form)

        # ── 브라우저 ──
        self._headless = QCheckBox("헤드리스 모드 (브라우저 창 숨김)")
        self._headless.setChecked(True)

        self._on_failure = QComboBox()
        self._on_failure.addItems(["중단 (stop)", "계정 전환 (switch_account)"])

        browser_form = QFormLayout()
        browser_form.addRow("", self._headless)
        browser_form.addRow("실패 시:", self._on_failure)

        browser_group = QGroupBox("브라우저")
        browser_group.setLayout(browser_form)

        layout = QVBoxLayout()
        layout.addWidget(timing_group)
        layout.addWidget(browser_group)
        layout.addStretch()
        self.setLayout(layout)

    _FAIL_MAP = {"중단 (stop)": "stop", "계정 전환 (switch_account)": "switch_account"}
    _FAIL_REV = {v: k for k, v in _FAIL_MAP.items()}

    def to_dict(self) -> dict:
        run: dict = {}

        interval = self._interval.value()
        if interval != 60:
            run["interval"] = f"{interval}s"
        upload_delay = self._upload_delay.value()
        if upload_delay != 1500:
            run["upload_delay"] = f"{upload_delay}ms"
        if not self._headless.isChecked():
            run["headless"] = False
        on_failure = self._FAIL_MAP.get(self._on_failure.currentText(), "stop")
        if on_failure != "stop":
            run["on_failure"] = on_failure

        return {"run": run} if run else {}

    def from_dict(self, data: dict) -> None:
        run = data.get("run", {})

        interval_raw = str(run.get("interval", "60s"))
        self._interval.setValue(int(interval_raw.rstrip("s")))

        delay_raw = str(run.get("upload_delay", "1500ms"))
        self._upload_delay.setValue(int(delay_raw.rstrip("ms")))

        self._headless.setChecked(run.get("headless", True))

        on_failure = run.get("on_failure", "stop")
        display = self._FAIL_REV.get(on_failure, "중단 (stop)")
        idx = self._on_failure.findText(display)
        if idx >= 0:
            self._on_failure.setCurrentIndex(idx)
