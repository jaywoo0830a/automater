"""
gui/__main__.py
----------------
Campaign DSL Builder — PySide6 (Qt for Python 6.11).

Builds a campaign YAML file from user input, then runs it via CLI.

    python -m gui
"""

import sys
from gui.app import main

if __name__ == "__main__":
    sys.exit(main())
