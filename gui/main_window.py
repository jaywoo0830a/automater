"""
gui/main_window.py
-------------------
Main window — DSL builder + campaign workflow.
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
    QSplitter,
)

from gui.tabs.platform_tab import PlatformTab
from gui.tabs.accounts_tab import AccountsTab
from gui.tabs.browser_tab import BrowserTab
from gui.tabs.titles_tab import TitlesTab
from gui.tabs.keywords_tab import KeywordsTab
from gui.tabs.maps_tab import MapsTab
from gui.tabs.post_tab import PostTab
from gui.tabs.publish_tab import PublishTab
from gui.tabs.run_tab import RunTab


class MainWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("캠페인 빌더")
        self.setMinimumSize(1000, 750)

        # ── Builder tabs ──
        self._tabs = QTabWidget()
        self._platform_tab = PlatformTab()
        self._accounts_tab = AccountsTab()
        self._browser_tab = BrowserTab()
        self._titles_tab = TitlesTab()
        self._keywords_tab = KeywordsTab()
        self._maps_tab = MapsTab()
        self._post_tab = PostTab()
        self._publish_tab = PublishTab()
        self._run_tab = RunTab()

        self._tabs.addTab(self._platform_tab, "플랫폼")
        self._tabs.addTab(self._accounts_tab, "계정")
        self._tabs.addTab(self._browser_tab, "브라우저")
        self._tabs.addTab(self._titles_tab, "제목")
        self._tabs.addTab(self._keywords_tab, "키워드 / 풀")
        self._tabs.addTab(self._maps_tab, "맵")
        self._tabs.addTab(self._post_tab, "포스트 블록")
        self._tabs.addTab(self._publish_tab, "발행")
        self._tabs.addTab(self._run_tab, "실행 설정")

        # ── Bottom panel — YAML preview / execution log ──
        self._bottom_tabs = QTabWidget()

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setPlaceholderText("YAML 미리보기가 여기에 표시됩니다...")

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setPlaceholderText("실행 결과가 여기에 표시됩니다...")

        self._bottom_tabs.addTab(self._preview, "YAML 미리보기")
        self._bottom_tabs.addTab(self._log, "실행 로그")

        # ── File buttons (left) ──
        btn_load = QPushButton("불러오기")
        btn_load.clicked.connect(self._load_yaml)
        btn_save = QPushButton("저장")
        btn_save.clicked.connect(self._save_yaml)

        # ── Workflow buttons (center) ──
        btn_validate = QPushButton("검증")
        btn_validate.clicked.connect(self._run_validate)
        btn_prepare = QPushButton("세션 준비")
        btn_prepare.clicked.connect(self._run_prepare)
        btn_preview_plan = QPushButton("미리보기")
        btn_preview_plan.clicked.connect(self._run_preview)
        btn_dryrun = QPushButton("Dry-run")
        btn_dryrun.clicked.connect(self._run_dryrun)

        # ── Execute button (right) ──
        btn_execute = QPushButton("▶ 실행")
        btn_execute.setStyleSheet("QPushButton { font-weight: bold; }")
        btn_execute.clicked.connect(self._run_execute)

        # ── YAML preview refresh ──
        btn_refresh = QPushButton("YAML 갱신")
        btn_refresh.clicked.connect(self._refresh_preview)

        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_load)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_refresh)
        btn_row.addSpacing(20)
        btn_row.addWidget(btn_validate)
        btn_row.addWidget(btn_prepare)
        btn_row.addWidget(btn_preview_plan)
        btn_row.addWidget(btn_dryrun)
        btn_row.addStretch()
        btn_row.addWidget(btn_execute)

        # ── Layout ──
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._tabs)
        splitter.addWidget(self._bottom_tabs)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout = QVBoxLayout()
        layout.addWidget(splitter)
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
        config.update(self._browser_tab.to_dict())
        config.update(self._titles_tab.to_dict())
        config.update(self._keywords_tab.to_dict())
        config.update(self._maps_tab.to_dict())
        config.update(self._post_tab.to_dict())
        config.update(self._publish_tab.to_dict())
        config.update(self._run_tab.to_dict())
        return config

    def _to_yaml(self) -> str:
        config = self._build_config()
        config.pop("_maps_data", None)
        return yaml.dump(
            config,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )

    # ------------------------------------------------------------------
    # File actions
    # ------------------------------------------------------------------

    def _refresh_preview(self) -> None:
        try:
            self._preview.setPlainText(self._to_yaml())
            self._bottom_tabs.setCurrentIndex(0)
            self._status.showMessage("YAML 갱신됨", 3000)
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
            config = self._build_config()
            self._save_map_files(config, Path(path).parent)
            text = yaml.dump(
                config,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )
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
            self._load_map_files(raw, Path(path).parent)
            self._platform_tab.from_dict(raw)
            self._accounts_tab.from_dict(raw)
            self._browser_tab.from_dict(raw)
            self._titles_tab.from_dict(raw)
            self._keywords_tab.from_dict(raw)
            self._maps_tab.from_dict(raw)
            self._post_tab.from_dict(raw)
            self._publish_tab.from_dict(raw)
            self._run_tab.from_dict(raw)
            self._last_saved_path = path
            self._status.showMessage(f"불러옴: {path}", 5000)
            self._refresh_preview()
        except Exception as e:
            QMessageBox.critical(self, "불러오기 오류", str(e))

    @staticmethod
    def _save_map_files(config: dict, base_dir: Path) -> None:
        maps_data = config.pop("_maps_data", None)
        if not maps_data or "maps" not in config:
            return
        maps_dir = base_dir / "maps"
        maps_dir.mkdir(exist_ok=True)
        for slug, data in maps_data.items():
            if slug not in config["maps"]:
                continue
            filename = f"{slug}.yaml"
            file_path = maps_dir / filename
            file_path.write_text(
                yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
            config["maps"][slug]["file"] = f"maps/{filename}"

    @staticmethod
    def _load_map_files(raw: dict, base_dir: Path) -> None:
        maps_config = raw.get("maps")
        if not maps_config:
            return
        maps_data: dict = {}
        for slug, entry in maps_config.items():
            if not isinstance(entry, dict):
                continue
            file_path = entry.get("file", "")
            if not file_path:
                continue
            p = Path(file_path)
            if not p.is_absolute():
                p = base_dir / p
            if p.exists():
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                maps_data[slug] = data
        raw["_maps_data"] = maps_data

    # ------------------------------------------------------------------
    # Workflow actions — CLI 파이프라인 순서
    # ------------------------------------------------------------------

    def _ensure_saved(self) -> bool:
        """YAML 저장 확인. 저장 안 됐으면 저장 유도. 실패 시 False."""
        if not self._last_saved_path:
            QMessageBox.information(self, "저장 필요", "먼저 YAML 파일을 저장하세요.")
            self._save_yaml()
        return bool(self._last_saved_path)

    def _run_cli(self, *args: str, label: str = "") -> None:
        """CLI 명령 실행 후 결과를 실행 로그 탭에 표시."""
        if not self._ensure_saved():
            return
        try:
            python = sys.executable
            cmd = [python, "-m", "cli", self._last_saved_path, *args]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600,
            )
            output = result.stdout + result.stderr
            self._log.setPlainText(f"# {label or ' '.join(args)}\n\n{output}")
            self._bottom_tabs.setCurrentIndex(1)  # 실행 로그 탭으로 전환
            self._status.showMessage(f"{label} 완료", 5000)
        except subprocess.TimeoutExpired:
            QMessageBox.warning(self, "시간 초과", f"{label} 시간 초과 (10분)")
        except Exception as e:
            QMessageBox.critical(self, "실행 오류", str(e))

    def _run_validate(self) -> None:
        self._run_cli("--validate", label="검증")

    def _run_prepare(self) -> None:
        self._run_cli("--prepare", label="세션 준비")

    def _run_preview(self) -> None:
        self._run_cli("--preview", label="미리보기")

    def _run_dryrun(self) -> None:
        self._run_cli(label="Dry-run")

    def _run_execute(self) -> None:
        reply = QMessageBox.question(
            self, "캠페인 실행",
            f"캠페인을 실제로 실행합니까?\n\n{self._last_saved_path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._run_cli("--execute", label="실행")
