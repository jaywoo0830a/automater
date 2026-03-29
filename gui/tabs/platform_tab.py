"""플랫폼 + 세션 저장소 + ���업 디렉토리 + 이미지 설정 탭."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QFormLayout, QComboBox, QLineEdit, QRadioButton,
    QButtonGroup, QHBoxLayout, QGroupBox, QVBoxLayout,
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
        self._images_dir = QLineEdit()
        self._images_dir.setPlaceholderText("./images (상대 경로 또는 절대 경로)")
        btn_browse_img = QPushButton("...")
        btn_browse_img.setFixedWidth(30)
        btn_browse_img.clicked.connect(self._browse_images)

        img_row = QHBoxLayout()
        img_row.addWidget(self._images_dir)
        img_row.addWidget(btn_browse_img)
        img_widget = QWidget()
        img_widget.setLayout(img_row)

        form = QFormLayout()
        form.addRow("플��폼:", self._platform)
        form.addRow("작업 디렉토리:", ws_widget)
        form.addRow("이미지 디렉토리:", img_widget)

        # Session store
        self._store_file = QRadioButton("파일 (기��)")
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

        store_group = QGroupBox("��션 저장소")
        store_group.setLayout(store_row)

        # 고급: EXIF
        self._exif = QCheckBox("EXIF 자동 삽입 (카메라 메타데이터)")
        self._exif.setChecked(True)

        advanced = CollapsibleSection("이미지 고급 설정")
        advanced.add_row("", self._exif)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(store_group)
        layout.addWidget(advanced)
        layout.addStretch()
        self.setLayout(layout)

    def _browse_workspace(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "작업 디렉토리 선���", self._workspace.text(),
        )
        if path:
            self._workspace.setText(path)

    def _browse_images(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "이미지 ���렉토리 선택", self._images_dir.text() or self._workspace.text(),
        )
        if path:
            self._images_dir.setText(path)

    @property
    def workspace(self) -> str:
        return self._workspace.text().strip() or _default_workspace()

    def to_dict(self) -> dict:
        d: dict = {"platform": self._platform.currentText()}
        if self._store_redis.isChecked():
            url = self._redis_url.text().strip() or "redis://localhost:6379"
            d["session_store"] = url
        images = self._images_dir.text().strip()
        if images:
            d["images"] = images
        if not self._exif.isChecked():
            d["exif_optimization"] = False
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

        self._images_dir.setText(data.get("images", ""))
        self._exif.setChecked(data.get("exif_optimization", True))
