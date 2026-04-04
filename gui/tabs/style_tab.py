"""스타일 탭 — 글 전체 정렬, 폰트 등."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout,
    QComboBox, QGroupBox,
)


class StyleTab(QWidget):

    def __init__(self) -> None:
        super().__init__()

        # ── 정렬 ──
        self._align = QComboBox()
        self._align.addItems(["기본 (left)", "가운데 (center)", "오른쪽 (right)"])

        align_form = QFormLayout()
        align_form.addRow("글 정렬:", self._align)

        align_group = QGroupBox("정렬")
        align_group.setLayout(align_form)

        layout = QVBoxLayout()
        layout.addWidget(align_group)
        layout.addStretch()
        self.setLayout(layout)

    _ALIGN_MAP = {"기본 (left)": "left", "가운데 (center)": "center", "오른쪽 (right)": "right"}
    _ALIGN_REV = {v: k for k, v in _ALIGN_MAP.items()}

    def to_dict(self) -> dict:
        align = self._ALIGN_MAP.get(self._align.currentText(), "left")
        if align == "left":
            return {}
        return {"style": {"align": align}}

    def from_dict(self, data: dict) -> None:
        style = data.get("style", {})
        align = style.get("align", "left") if isinstance(style, dict) else "left"
        display = self._ALIGN_REV.get(align, "기본 (left)")
        idx = self._align.findText(display)
        if idx >= 0:
            self._align.setCurrentIndex(idx)
