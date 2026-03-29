"""실행 설정 탭 - 간격, 병렬, 재개, 브라우저 설정."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QSpinBox, QCheckBox, QComboBox, QLabel,
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
        self._on_failure.addItems(["중단 (stop)", "계정 전환 (switch_account)"])

        self._on_resume = QComboBox()
        self._on_resume.addItems(["처음부터 (restart)", "이어서 (skip)"])

        basic_form = QFormLayout()
        basic_form.addRow("포스트 간 대기:", self._interval)
        basic_form.addRow("", self._headless)
        basic_form.addRow("실패 시:", self._on_failure)
        basic_form.addRow("재실행 시:", self._on_resume)

        basic_group = QGroupBox("기본")
        basic_group.setLayout(basic_form)

        # ── 고급 설정 (접힘) ──
        self._parallel = QCheckBox("계정별 병렬 실행")
        self._parallel.setChecked(False)

        self._max_workers = QSpinBox()
        self._max_workers.setRange(1, 20)
        self._max_workers.setValue(3)
        self._max_workers.setEnabled(False)
        self._parallel.toggled.connect(self._max_workers.setEnabled)

        advanced = CollapsibleSection("병렬 실행")
        advanced.add_row("", self._parallel)
        advanced.add_row("동시 실행 계정 수:", self._max_workers)

        layout = QVBoxLayout()
        layout.addWidget(basic_group)
        layout.addWidget(advanced)
        layout.addStretch()
        self.setLayout(layout)

    _FAIL_MAP = {"중단 (stop)": "stop", "계정 전환 (switch_account)": "switch_account"}
    _FAIL_REV = {v: k for k, v in _FAIL_MAP.items()}
    _RESUME_MAP = {"처음부터 (restart)": "restart", "이어서 (skip)": "skip"}
    _RESUME_REV = {v: k for k, v in _RESUME_MAP.items()}

    def to_dict(self) -> dict:
        run: dict = {}

        interval = self._interval.value()
        if interval != 60:
            run["interval"] = f"{interval}s"
        if not self._headless.isChecked():
            run["headless"] = False
        on_failure = self._FAIL_MAP.get(self._on_failure.currentText(), "stop")
        if on_failure != "stop":
            run["on_failure"] = on_failure
        on_resume = self._RESUME_MAP.get(self._on_resume.currentText(), "restart")
        if on_resume != "restart":
            run["on_resume"] = on_resume
        if self._parallel.isChecked():
            run["parallel"] = True
            run["max_workers"] = self._max_workers.value()

        return {"run": run} if run else {}

    def from_dict(self, data: dict) -> None:
        run = data.get("run", {})

        interval_raw = str(run.get("interval", "60s"))
        self._interval.setValue(int(interval_raw.rstrip("s")))

        self._headless.setChecked(run.get("headless", True))

        on_failure = run.get("on_failure", "stop")
        display = self._FAIL_REV.get(on_failure, "중단 (stop)")
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
