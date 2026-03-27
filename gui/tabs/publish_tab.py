"""발행 탭 — 스케줄, 태그, 공개 범위."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QRadioButton,
    QButtonGroup, QGroupBox, QSpinBox, QCheckBox,
)


class PublishTab(QWidget):

    def __init__(self) -> None:
        super().__init__()

        # ── 스케줄 ──
        self._sched_now = QRadioButton("즉시 발행")
        self._sched_delay = QRadioButton("지연 발행")
        self._sched_seq = QRadioButton("순차 예약 (++)")
        self._sched_now.setChecked(True)

        self._sched_group = QButtonGroup()
        self._sched_group.addButton(self._sched_now, 0)
        self._sched_group.addButton(self._sched_delay, 1)
        self._sched_group.addButton(self._sched_seq, 2)

        self._delay_value = QLineEdit()
        self._delay_value.setPlaceholderText("15m 또는 15m ~ 30m")
        self._delay_value.setEnabled(False)

        self._seq_value = QLineEdit()
        self._seq_value.setPlaceholderText("15m 또는 15m ~ 30m")
        self._seq_value.setEnabled(False)

        self._sched_delay.toggled.connect(self._delay_value.setEnabled)
        self._sched_seq.toggled.connect(self._seq_value.setEnabled)

        sched_form = QFormLayout()
        sched_form.addRow(self._sched_now, QLabel(""))
        sched_form.addRow(self._sched_delay, self._delay_value)
        sched_form.addRow(self._sched_seq, self._seq_value)

        sched_group = QGroupBox("발행 시점")
        sched_group.setLayout(sched_form)

        # ── 태그 ──
        self._tags = QLineEdit()
        self._tags.setPlaceholderText("교육, 과외, 학원 (콤마 구분)")

        # ── 공개 범위 ──
        self._visibility = QComboBox()
        self._visibility.addItems(["공개 (public)", "비공개 (private)", "임시저장 (draft)"])

        meta_form = QFormLayout()
        meta_form.addRow("태그:", self._tags)
        meta_form.addRow("공개 범위:", self._visibility)

        layout = QVBoxLayout()
        layout.addWidget(sched_group)
        layout.addLayout(meta_form)
        layout.addStretch()
        self.setLayout(layout)

    _VIS_MAP = {"공개 (public)": "public", "비공개 (private)": "private", "임시저장 (draft)": "draft"}
    _VIS_REV = {v: k for k, v in _VIS_MAP.items()}

    def to_dict(self) -> dict:
        pub: dict = {}

        # schedule
        if self._sched_delay.isChecked():
            val = self._delay_value.text().strip()
            pub["schedule"] = f"now + {val}" if val else "now"
        elif self._sched_seq.isChecked():
            val = self._seq_value.text().strip()
            pub["schedule"] = f"++ {val}" if val else "++"
        else:
            pub["schedule"] = "now"

        # tags
        tags = [t.strip() for t in self._tags.text().split(",") if t.strip()]
        if tags:
            pub["tags"] = tags

        # visibility
        vis = self._VIS_MAP.get(self._visibility.currentText(), "public")
        if vis != "public":
            pub["visibility"] = vis

        return {"publish": pub} if pub else {}

    def from_dict(self, data: dict) -> None:
        pub = data.get("publish", {})
        schedule = str(pub.get("schedule", "now"))

        if schedule.startswith("++"):
            self._sched_seq.setChecked(True)
            self._seq_value.setText(schedule.replace("++", "").strip())
        elif schedule.startswith("now +"):
            self._sched_delay.setChecked(True)
            self._delay_value.setText(schedule.replace("now +", "").strip())
        else:
            self._sched_now.setChecked(True)

        tags = pub.get("tags", [])
        self._tags.setText(", ".join(tags) if tags else "")

        vis = pub.get("visibility", "public")
        display = self._VIS_REV.get(vis, "공개 (public)")
        idx = self._visibility.findText(display)
        if idx >= 0:
            self._visibility.setCurrentIndex(idx)
