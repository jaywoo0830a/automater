"""
gui/main_window.py
-------------------
Main window - DSL builder + campaign workflow.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

import yaml
from PySide6.QtCore import Qt, Signal, QObject
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


# ---------------------------------------------------------------------------
# Signal bridge - thread -> GUI
# ---------------------------------------------------------------------------

class _CliSignals(QObject):
    """Signals emitted from background CLI thread."""
    output = Signal(str)    # stdout + stderr line
    finished = Signal(str)  # label when done


class MainWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Campaign Builder")
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

        self._tabs.addTab(self._platform_tab, "Platform")
        self._tabs.addTab(self._accounts_tab, "Accounts")
        self._tabs.addTab(self._browser_tab, "Browser")
        self._tabs.addTab(self._titles_tab, "Titles")
        self._tabs.addTab(self._keywords_tab, "Keywords")
        self._tabs.addTab(self._maps_tab, "Maps")
        self._tabs.addTab(self._post_tab, "Post")
        self._tabs.addTab(self._publish_tab, "Publish")
        self._tabs.addTab(self._run_tab, "Run")

        # ── Bottom panel ──
        self._bottom_tabs = QTabWidget()

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setPlaceholderText("YAML preview...")

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setPlaceholderText("Execution log...")

        self._bottom_tabs.addTab(self._preview, "YAML")
        self._bottom_tabs.addTab(self._log, "Log")

        # ── File buttons ──
        btn_load = QPushButton("Load")
        btn_load.clicked.connect(self._load_yaml)
        btn_save = QPushButton("Save")
        btn_save.clicked.connect(self._save_yaml)
        btn_refresh = QPushButton("Refresh YAML")
        btn_refresh.clicked.connect(self._refresh_preview)

        # ── Workflow buttons ──
        self._btn_validate = QPushButton("Validate")
        self._btn_validate.clicked.connect(self._run_validate)
        self._btn_prepare = QPushButton("Prepare")
        self._btn_prepare.clicked.connect(self._run_prepare)
        self._btn_preview_plan = QPushButton("Preview")
        self._btn_preview_plan.clicked.connect(self._run_preview)
        self._btn_dryrun = QPushButton("Dry-run")
        self._btn_dryrun.clicked.connect(self._run_dryrun)
        self._btn_execute = QPushButton("Execute")
        self._btn_execute.setStyleSheet("QPushButton { font-weight: bold; }")
        self._btn_execute.clicked.connect(self._run_execute)

        self._workflow_buttons = [
            self._btn_validate, self._btn_prepare, self._btn_preview_plan,
            self._btn_dryrun, self._btn_execute,
        ]

        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_load)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_refresh)
        btn_row.addSpacing(20)
        for btn in self._workflow_buttons:
            btn_row.addWidget(btn)

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
        self._running = False

        # ── CLI signal bridge ──
        self._cli_signals = _CliSignals()
        self._cli_signals.output.connect(self._on_cli_output)
        self._cli_signals.finished.connect(self._on_cli_finished)

    # ------------------------------------------------------------------
    # Build config
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
            self._status.showMessage("YAML refreshed", 3000)
        except Exception as e:
            QMessageBox.warning(self, "Preview error", str(e))

    def _save_yaml(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save YAML", self._last_saved_path or "campaign.yaml",
            "YAML (*.yaml *.yml)",
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
            self._status.showMessage(f"Saved: {path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Save error", str(e))

    def _load_yaml(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load YAML", "",
            "YAML (*.yaml *.yml)",
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
            self._status.showMessage(f"Loaded: {path}", 5000)
            self._refresh_preview()
        except Exception as e:
            QMessageBox.critical(self, "Load error", str(e))

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
    # CLI execution (background thread)
    # ------------------------------------------------------------------

    def _ensure_saved(self) -> bool:
        if not self._last_saved_path:
            QMessageBox.information(self, "Save required", "Save YAML first.")
            self._save_yaml()
        return bool(self._last_saved_path)

    def _set_running(self, running: bool) -> None:
        self._running = running
        for btn in self._workflow_buttons:
            btn.setEnabled(not running)

    def _run_cli(self, *args: str, label: str = "") -> None:
        """Run CLI command in background thread."""
        if self._running:
            return
        if not self._ensure_saved():
            return

        self._set_running(True)
        self._log.clear()
        self._log.setPlainText(f"# {label} ...\n")
        self._bottom_tabs.setCurrentIndex(1)
        self._status.showMessage(f"{label} running...", 0)

        cmd = [sys.executable, "-m", "cli", self._last_saved_path, *args]

        def _worker():
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                for line in proc.stdout:
                    self._cli_signals.output.emit(line)
                proc.wait()
            except Exception as exc:
                self._cli_signals.output.emit(f"\n[ERROR] {exc}\n")
            finally:
                self._cli_signals.finished.emit(label)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def _on_cli_output(self, line: str) -> None:
        self._log.moveCursor(self._log.textCursor().End)
        self._log.insertPlainText(line)

    def _on_cli_finished(self, label: str) -> None:
        self._set_running(False)
        self._status.showMessage(f"{label} done", 5000)

    # ------------------------------------------------------------------
    # Workflow buttons
    # ------------------------------------------------------------------

    def _run_validate(self) -> None:
        self._run_cli("--validate", label="Validate")

    def _run_prepare(self) -> None:
        self._run_cli("--prepare", label="Prepare")

    def _run_preview(self) -> None:
        self._run_cli("--preview", label="Preview")

    def _run_dryrun(self) -> None:
        self._run_cli(label="Dry-run")

    def _run_execute(self) -> None:
        reply = QMessageBox.question(
            self, "Execute",
            f"Execute campaign?\n\n{self._last_saved_path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._run_cli("--execute", label="Execute")
