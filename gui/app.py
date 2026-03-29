"""
gui/app.py
-----------
Main application window.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow

_STYLESHEET = """
QGroupBox {
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
QTableWidget {
    border: 1px solid #d0d0d0;
    gridline-color: #e8e8e8;
}
QListWidget {
    border: 1px solid #d0d0d0;
}
QTextEdit {
    border: 1px solid #d0d0d0;
}
QLineEdit {
    border: 1px solid #d0d0d0;
    border-radius: 2px;
    padding: 2px 4px;
}
QSpinBox, QDoubleSpinBox, QComboBox {
    border: 1px solid #d0d0d0;
    border-radius: 2px;
    padding: 2px 4px;
}
QPushButton {
    border: 1px solid #c0c0c0;
    border-radius: 3px;
    padding: 4px 12px;
    background: #f8f8f8;
}
QPushButton:hover {
    background: #e8e8e8;
}
QPushButton:pressed {
    background: #d8d8d8;
}
QPushButton:disabled {
    color: #a0a0a0;
    background: #f0f0f0;
}
QTabWidget::pane {
    border: 1px solid #d0d0d0;
}
"""


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("캠페인 빌더")
    app.setStyleSheet(_STYLESHEET)
    window = MainWindow()
    window.show()
    return app.exec()
