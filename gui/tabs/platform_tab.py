"""플랫폼 + 작업 디렉토리 + 이미지 설정 탭."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QFormLayout, QComboBox, QLineEdit,
    QHBoxLayout, QVBoxLayout,
    QPushButton, QFileDialog, QCheckBox,
)

from gui.collapsible import CollapsibleSection


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
        btn_browse_ws = QPushButton("...")
        btn_browse_ws.setFixedWidth(30)
        btn_browse_ws.clicked.connect(self._browse_workspace)

        ws_row = QHBoxLayout()
        ws_row.addWidget(self._workspace)
        ws_row.addWidget(btn_browse_ws)
        ws_widget = QWidget()
        ws_widget.setLayout(ws_row)

        # Images directory
        self._assets_dir = QLineEdit()
        self._assets_dir.setPlaceholderText("./assets (이미지, 텍스트 파일 등)")
        btn_browse_assets = QPushButton("...")
        btn_browse_assets.setFixedWidth(30)
        btn_browse_assets.clicked.connect(self._browse_assets)

        assets_row = QHBoxLayout()
        assets_row.addWidget(self._assets_dir)
        assets_row.addWidget(btn_browse_assets)
        assets_widget = QWidget()
        assets_widget.setLayout(assets_row)

        form = QFormLayout()
        form.addRow("플랫폼:", self._platform)
        form.addRow("작업 디렉토리:", ws_widget)
        form.addRow("Assets 디렉토리:", assets_widget)

        # 고급: EXIF
        self._exif = QCheckBox("EXIF 자동 삽입 (카메라 메타데이터)")
        self._exif.setChecked(True)

        advanced = CollapsibleSection("이미지 고급 설정")
        advanced.add_row("", self._exif)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(advanced)
        layout.addStretch()
        self.setLayout(layout)

    def _browse_workspace(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "작업 디렉토리 선택", self._workspace.text(),
        )
        if path:
            self._workspace.setText(path)

    def _browse_assets(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Assets 디렉토리 선택", self._assets_dir.text() or self._workspace.text(),
        )
        if path:
            self._assets_dir.setText(path)

    @property
    def workspace(self) -> str:
        return self._workspace.text().strip() or _default_workspace()

    def to_dict(self) -> dict:
        return {
            "platform":          self._platform.currentText(),
            "assets":            self._assets_dir.text().strip() or "./assets",
            "exif_optimization": self._exif.isChecked(),
        }

    def from_dict(self, data: dict) -> None:
        platform = data.get("platform", "naver")
        idx = self._platform.findText(platform)
        if idx >= 0:
            self._platform.setCurrentIndex(idx)

        self._assets_dir.setText(data.get("assets", ""))
        self._exif.setChecked(data.get("exif_optimization", True))
