"""Platform + session store + workspace directory tab."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QFormLayout, QComboBox, QLineEdit, QRadioButton,
    QButtonGroup, QHBoxLayout, QGroupBox, QVBoxLayout,
    QPushButton, QFileDialog,
)


def _default_workspace() -> str:
    """Return default workspace: ~/Documents/automator."""
    docs = Path.home() / "Documents" / "automator"
    docs.mkdir(parents=True, exist_ok=True)
    return str(docs)


class PlatformTab(QWidget):

    def __init__(self) -> None:
        super().__init__()

        # Platform
        self._platform = QComboBox()
        self._platform.addItems(["naver", "wordpress", "tistory"])

        # Workspace directory
        self._workspace = QLineEdit(_default_workspace())
        btn_browse = QPushButton("...")
        btn_browse.setFixedWidth(30)
        btn_browse.clicked.connect(self._browse_workspace)

        ws_row = QHBoxLayout()
        ws_row.addWidget(self._workspace)
        ws_row.addWidget(btn_browse)

        ws_widget = QWidget()
        ws_widget.setLayout(ws_row)

        # Session store
        self._store_file = QRadioButton("File (default)")
        self._store_redis = QRadioButton("Redis")
        self._store_file.setChecked(True)

        self._store_group = QButtonGroup()
        self._store_group.addButton(self._store_file, 0)
        self._store_group.addButton(self._store_redis, 1)

        self._redis_url = QLineEdit()
        self._redis_url.setPlaceholderText("redis://localhost:6379")
        self._redis_url.setEnabled(False)

        self._store_redis.toggled.connect(self._redis_url.setEnabled)

        store_row = QHBoxLayout()
        store_row.addWidget(self._store_file)
        store_row.addWidget(self._store_redis)
        store_row.addWidget(self._redis_url)

        store_group = QGroupBox("Session Store")
        store_group.setLayout(store_row)

        form = QFormLayout()
        form.addRow("Platform:", self._platform)
        form.addRow("Workspace:", ws_widget)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(store_group)
        layout.addStretch()
        self.setLayout(layout)

    def _browse_workspace(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select workspace directory", self._workspace.text(),
        )
        if path:
            self._workspace.setText(path)

    @property
    def workspace(self) -> str:
        """Current workspace directory path."""
        return self._workspace.text().strip() or _default_workspace()

    def to_dict(self) -> dict:
        d: dict = {"platform": self._platform.currentText()}
        if self._store_redis.isChecked():
            url = self._redis_url.text().strip() or "redis://localhost:6379"
            d["session_store"] = url
        return d

    def from_dict(self, data: dict) -> None:
        platform = data.get("platform", "naver")
        idx = self._platform.findText(platform)
        if idx >= 0:
            self._platform.setCurrentIndex(idx)

        store = data.get("session_store", "")
        if store and store.startswith("redis"):
            self._store_redis.setChecked(True)
            self._redis_url.setText(store)
        else:
            self._store_file.setChecked(True)
            self._redis_url.clear()
