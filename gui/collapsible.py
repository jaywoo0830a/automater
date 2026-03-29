"""
gui/collapsible.py
------------------
접을 수 있는 고급 설정 섹션 위젯.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QPushButton, QFrame,
)

from gui.theme import (
    BLUE, BLUE_DARK, BG_SUBTLE, BORDER_LIGHT,
    BASE, SP_XS, SP_SM, SP_MD, RADIUS_SM,
)


class CollapsibleSection(QWidget):
    """접을 수 있는 섹션. 기본 접힌 상태."""

    def __init__(self, title: str = "고급 설정", parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._toggle = QPushButton(f"[+] {title}")
        self._toggle.setCheckable(True)
        self._toggle.setChecked(False)
        self._toggle.setStyleSheet(
            f"QPushButton {{"
            f"  text-align: left; border: none; padding: {SP_SM}px {SP_XS}px;"
            f"  color: {BLUE}; font-size: {BASE}px; background: transparent;"
            f"}}"
            f"QPushButton:hover {{ color: {BLUE_DARK}; }}"
        )
        self._toggle.toggled.connect(self._on_toggle)
        self._title = title

        self._content = QFrame()
        self._content.setVisible(False)
        self._content.setStyleSheet(
            f"QFrame {{ background: {BG_SUBTLE}; border: 1px solid {BORDER_LIGHT};"
            f" border-radius: {RADIUS_SM}px; }}"
        )
        self._form = QFormLayout()
        self._form.setContentsMargins(SP_MD, SP_SM, SP_MD, SP_SM)
        self._form.setSpacing(SP_SM)
        self._content.setLayout(self._form)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, SP_XS, 0, SP_XS)
        layout.setSpacing(RADIUS_SM)
        layout.addWidget(self._toggle)
        layout.addWidget(self._content)
        self.setLayout(layout)

    def add_row(self, label: str, widget: QWidget) -> None:
        self._form.addRow(label, widget)

    def add_widget(self, widget: QWidget) -> None:
        self._form.addRow(widget)

    def _on_toggle(self, checked: bool) -> None:
        self._content.setVisible(checked)
        prefix = "[-]" if checked else "[+]"
        self._toggle.setText(f"{prefix} {self._title}")
