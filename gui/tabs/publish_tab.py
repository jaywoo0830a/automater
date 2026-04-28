"""발행 탭 — 스케줄, 태그, 공개 범위."""

from __future__ import annotations

import re

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QRadioButton,
    QButtonGroup, QGroupBox, QSpinBox, QDateEdit,
)


_AT_RE = re.compile(r"^at\s+(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2})\s*$", re.IGNORECASE)


class PublishTab(QWidget):

    def __init__(self) -> None:
        super().__init__()

        # ── 스케줄 라디오 버튼 ──
        self._sched_now = QRadioButton("즉시 발행")
        self._sched_delay = QRadioButton("지연 발행")
        self._sched_at = QRadioButton("고정 시각 (at)")
        self._sched_seq = QRadioButton("순차 예약 (++)")
        self._sched_now.setChecked(True)

        self._sched_group = QButtonGroup()
        self._sched_group.addButton(self._sched_now, 0)
        self._sched_group.addButton(self._sched_delay, 1)
        self._sched_group.addButton(self._sched_at, 2)
        self._sched_group.addButton(self._sched_seq, 3)

        # 지연 발행
        self._delay_value = QLineEdit()
        self._delay_value.setPlaceholderText("15m 또는 15m ~ 30m")
        self._delay_value.setEnabled(False)

        # 고정 시각: YYYY-MM-DD HH (모든 콤보 동일 시각)
        self._at_date = QDateEdit()
        self._at_date.setCalendarPopup(True)
        self._at_date.setDisplayFormat("yyyy-MM-dd")
        self._at_date.setDate(QDate.currentDate().addDays(30))
        self._at_date.setEnabled(False)

        self._at_hour = QSpinBox()
        self._at_hour.setRange(0, 23)
        self._at_hour.setSuffix(" 시")
        self._at_hour.setValue(9)
        self._at_hour.setEnabled(False)

        at_row = QHBoxLayout()
        at_row.addWidget(self._at_date)
        at_row.addWidget(self._at_hour)
        at_row.addStretch()
        at_widget = QWidget()
        at_widget.setLayout(at_row)

        # 순차 예약
        self._seq_value = QLineEdit()
        self._seq_value.setPlaceholderText("15m 또는 15m ~ 30m")
        self._seq_value.setEnabled(False)

        self._seq_from = QLineEdit()
        self._seq_from.setPlaceholderText("+1d 09:00 또는 2026-04-14 09:00 (비우면 지금부터)")
        self._seq_from.setEnabled(False)

        # 활성/비활성 토글
        self._sched_delay.toggled.connect(self._delay_value.setEnabled)
        self._sched_at.toggled.connect(self._at_date.setEnabled)
        self._sched_at.toggled.connect(self._at_hour.setEnabled)
        self._sched_seq.toggled.connect(self._seq_value.setEnabled)
        self._sched_seq.toggled.connect(self._seq_from.setEnabled)

        # ── 폼 구성 ──
        sched_form = QFormLayout()
        sched_form.addRow(self._sched_now, QLabel(""))
        sched_form.addRow(self._sched_delay, self._delay_value)
        sched_form.addRow(self._sched_at, at_widget)
        sched_form.addRow(self._sched_seq, self._seq_value)
        sched_form.addRow("순차 시작 시점:", self._seq_from)

        at_hint = QLabel(
            "고정 시각: 모든 콤보가 정확히 같은 날짜·시(KST)에 예약발행됩니다 — "
            "한 달 뒤 09시 같은 일괄 예약에 사용."
        )
        at_hint.setStyleSheet("color: gray; font-size: 11px;")
        at_hint.setWordWrap(True)

        sched_layout = QVBoxLayout()
        sched_layout.addLayout(sched_form)
        sched_layout.addWidget(at_hint)

        sched_group = QGroupBox("발행 시점")
        sched_group.setLayout(sched_layout)

        # ── 태그 ──
        self._tags = QLineEdit()
        self._tags.setPlaceholderText("교육, 과외, 학원 (콤마 구분)")

        # ── 공개 범위 ──
        self._visibility = QComboBox()
        self._visibility.addItems(["공개 (public)", "비공개 (private)"])

        meta_form = QFormLayout()
        meta_form.addRow("태그:", self._tags)
        meta_form.addRow("공개 범위:", self._visibility)

        layout = QVBoxLayout()
        layout.addWidget(sched_group)
        layout.addLayout(meta_form)
        layout.addStretch()
        self.setLayout(layout)

    _VIS_MAP = {"공개 (public)": "public", "비공개 (private)": "private"}
    _VIS_REV = {v: k for k, v in _VIS_MAP.items()}

    def to_dict(self) -> dict:
        pub: dict = {}

        # schedule
        if self._sched_delay.isChecked():
            val = self._delay_value.text().strip()
            pub["schedule"] = f"now + {val}" if val else "now"
        elif self._sched_at.isChecked():
            d: QDate = self._at_date.date()
            pub["schedule"] = (
                f"at {d.year():04d}-{d.month():02d}-{d.day():02d} "
                f"{self._at_hour.value():02d}"
            )
        elif self._sched_seq.isChecked():
            val = self._seq_value.text().strip()
            from_val = self._seq_from.text().strip()
            base = f"++ {val}" if val else "++"
            if from_val:
                base += f" from {from_val}"
            pub["schedule"] = base
        else:
            pub["schedule"] = "now"

        # tags
        tags = [t.strip() for t in self._tags.text().split(",") if t.strip()]
        pub["tags"] = tags

        # visibility
        vis = self._VIS_MAP.get(self._visibility.currentText(), "public")
        pub["visibility"] = vis

        return {"publish": pub}

    def from_dict(self, data: dict) -> None:
        pub = data.get("publish", {})
        schedule = str(pub.get("schedule", "now"))

        m_at = _AT_RE.match(schedule)
        if schedule.startswith("++"):
            self._sched_seq.setChecked(True)
            rest = schedule.replace("++", "").strip()
            if " from " in rest:
                interval_part, from_part = rest.split(" from ", 1)
                self._seq_value.setText(interval_part.strip())
                self._seq_from.setText(from_part.strip())
            else:
                self._seq_value.setText(rest)
                self._seq_from.setText("")
        elif m_at:
            self._sched_at.setChecked(True)
            y, mo, d, h = (int(g) for g in m_at.groups())
            self._at_date.setDate(QDate(y, mo, d))
            self._at_hour.setValue(h)
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
