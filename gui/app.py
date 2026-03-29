"""
gui/app.py
-----------
Main application entry.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow
from gui.theme import build_stylesheet


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("캠페인 빌더")
    app.setStyleSheet(build_stylesheet())
    window = MainWindow()
    window.show()
    return app.exec()
