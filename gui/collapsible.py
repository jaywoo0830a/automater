"""
gui/collapsible.py
------------------
Collapsible advanced settings section widget.

Usage:
    advanced = CollapsibleSection("Advanced")
    advanced.add_row("Label:", widget)
    layout.addWidget(advanced)
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QPushButton, QFrame,
)


class CollapsibleSection(QWidget):
    """Collapsible section. Collapsed by default."""

    def __init__(self, title: str = "Advanced", parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._toggle = QPushButton(f"[+] {title}")
        self._toggle.setCheckable(True)
        self._toggle.setChecked(False)
        self._toggle.setStyleSheet(
            "QPushButton { text-align: left; border: none; padding: 4px; color: #555; font-size: 12px; }"
            "QPushButton:checked { color: #333; }"
        )
        self._toggle.toggled.connect(self._on_toggle)
        self._title = title

        self._content = QFrame()
        self._content.setVisible(False)
        self._form = QFormLayout()
        self._form.setContentsMargins(16, 4, 0, 4)
        self._content.setLayout(self._form)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
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
