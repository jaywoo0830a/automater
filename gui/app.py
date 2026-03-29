"""
gui/app.py
-----------
Main application window — Campaign DSL Builder.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("캠페인 빌더")
    window = MainWindow()
    window.show()
    return app.exec()
