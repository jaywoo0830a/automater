"""
gui/main_window.py
-------------------
Main window with tabs for each DSL section.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QFileDialog,
    QMessageBox,
    QStatusBar,
)

from gui.tabs.platform_tab import PlatformTab
from gui.tabs.accounts_tab import AccountsTab
from gui.tabs.titles_tab import TitlesTab
from gui.tabs.keywords_tab import KeywordsTab
from gui.tabs.post_tab import PostTab
from gui.tabs.publish_tab import PublishTab
from gui.tabs.run_tab import RunTab


class MainWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("캠페인 빌더")
        self.setMinimumSize(900, 700)

        self._tabs = QTabWidget()
        self._platform_tab = PlatformTab()
        self._accounts_tab = AccountsTab()
        self._titles_tab = TitlesTab()
        self._keywords_tab = KeywordsTab()
        self._post_tab = PostTab()
        self._publish_tab = PublishTab()
        self._run_tab = RunTab()

        self._tabs.addTab(self._platform_tab, "플랫폼")
        self._tabs.addTab(self._accounts_tab, "계정")
        self._tabs.addTab(self._titles_tab, "제목")
        self._tabs.addTab(self._keywords_tab, "키워드 / 풀")
        self._tabs.addTab(self._post_tab, "포스트 블록")
        self._tabs.addTab(self._publish_tab, "발행")
        self._tabs.addTab(self._run_tab, "실행 설정")

        # Preview pane
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setPlaceholderText("YAML 미리보기가 여기에 표시됩니다...")

        # Buttons
        btn_preview = QPushButton("미리보기")
        btn_preview.clicked.connect(self._refresh_preview)

        btn_save = QPushButton("YAML 저장")
        btn_save.clicked.connect(self._save_yaml)

        btn_run = QPushButton("▶ 캠페인 실행")
        btn_run.clicked.connect(self._run_campaign)

        btn_load = QPushButton("YAML 불러오기")
        btn_load.clicked.connect(self._load_yaml)

        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_load)
        btn_row.addWidget(btn_preview)
        btn_row.addWidget(btn_save)
        btn_row.addStretch()
        btn_row.addWidget(btn_run)

        layout = QVBoxLayout()
        layout.addWidget(self._tabs, stretch=3)
        layout.addWidget(self._preview, stretch=2)
        layout.addLayout(btn_row)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self._status = QStatusBar()
        self.setStatusBar(self._status)

        self._last_saved_path: str = ""

    # ------------------------------------------------------------------
    # Build config dict from all tabs
    # ------------------------------------------------------------------

    def _build_config(self) -> dict:
        config: dict = {}
        config.update(self._platform_tab.to_dict())
        config.update(self._accounts_tab.to_dict())
        config.update(self._titles_tab.to_dict())
        config.update(self._keywords_tab.to_dict())
        config.update(self._post_tab.to_dict())
        config.update(self._publish_tab.to_dict())
        config.update(self._run_tab.to_dict())
        return config

    def _to_yaml(self) -> str:
        config = self._build_config()
        return yaml.dump(
            config,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _refresh_preview(self) -> None:
        try:
            text = self._to_yaml()
            self._preview.setPlainText(text)
            self._status.showMessage("미리보기 갱신됨", 3000)
        except Exception as e:
            QMessageBox.warning(self, "미리보기 오류", str(e))

    def _save_yaml(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "캠페인 YAML 저장", self._last_saved_path or "campaign.yaml",
            "YAML 파일 (*.yaml *.yml)",
        )
        if not path:
            return
        try:
            text = self._to_yaml()
            Path(path).write_text(text, encoding="utf-8")
            self._last_saved_path = path
            self._status.showMessage(f"저장 완료: {path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "저장 오류", str(e))

    def _load_yaml(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "캠페인 YAML 불러오기", "",
            "YAML 파일 (*.yaml *.yml)",
        )
        if not path:
            return
        try:
            raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
            self._platform_tab.from_dict(raw)
            self._accounts_tab.from_dict(raw)
            self._titles_tab.from_dict(raw)
            self._keywords_tab.from_dict(raw)
            self._post_tab.from_dict(raw)
            self._publish_tab.from_dict(raw)
            self._run_tab.from_dict(raw)
            self._last_saved_path = path
            self._status.showMessage(f"불러옴: {path}", 5000)
            self._refresh_preview()
        except Exception as e:
            QMessageBox.critical(self, "불러오기 오류", str(e))

    def _run_campaign(self) -> None:
        if not self._last_saved_path:
            QMessageBox.information(self, "저장 필요", "YAML 파일을 먼저 저장하세요.")
            self._save_yaml()
            if not self._last_saved_path:
                return

        reply = QMessageBox.question(
            self, "캠페인 실행",
            f"캠페인을 실행합니까? (dry-run)\n\n{self._last_saved_path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            python = sys.executable
            result = subprocess.run(
                [python, "-m", "cli", self._last_saved_path, "--dry-run"],
                capture_output=True, text=True, timeout=300,
            )
            output = result.stdout + result.stderr
            self._preview.setPlainText(f"# 실행 결과\n\n{output}")
            self._status.showMessage("캠페인 실행 완료", 5000)
        except subprocess.TimeoutExpired:
            QMessageBox.warning(self, "시간 초과", "캠페인 실행 시간 초과 (5분)")
        except Exception as e:
            QMessageBox.critical(self, "실행 오류", str(e))
