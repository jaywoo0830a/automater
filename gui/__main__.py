"""
gui/__main__.py
----------------
Campaign DSL Builder — PyQt6-style GUI using PySide6.

Builds a campaign YAML file from user input, then runs it via CLI.

    python -m gui
"""

import sys
from gui.app import main

if __name__ == "__main__":
    sys.exit(main())
