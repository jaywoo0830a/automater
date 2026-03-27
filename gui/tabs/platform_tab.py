"""플랫폼 + 세션 저장소 탭."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QFormLayout, QComboBox, QLineEdit, QRadioButton,
    QButtonGroup, QHBoxLayout, QGroupBox, QVBoxLayout,
)


class PlatformTab(QWidget):

    def __init__(self) -> None:
        super().__init__()

        # 플랫폼 선택
        self._platform = QComboBox()
        self._platform.addItems(["naver", "wordpress", "tistory"])

        # 세션 저장소
        self._store_file = QRadioButton("파일 (기본)")
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

        store_group = QGroupBox("세션 저장소")
        store_group.setLayout(store_row)

        form = QFormLayout()
        form.addRow("플랫폼:", self._platform)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(store_group)
        layout.addStretch()
        self.setLayout(layout)

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
