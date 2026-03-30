"""
gui/main_window.py
-------------------
Main window - DSL builder + multi-campaign workflow.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
from dataclasses import dataclass, field

import yaml
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QTextCursor, QCloseEvent
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
    output = Signal(str, str)     # (job_id, line)
    finished = Signal(str, str)   # (job_id, label)


@dataclass
class _RunningJob:
    job_id: str
    label: str
    proc: subprocess.Popen | None = None
    log_widget: QTextEdit | None = None
    tab_index: int = -1


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

        self._accounts_tab.set_platform_tab(self._platform_tab)
        self._titles_tab.set_token_source(self._get_tokens)
        self._post_tab.set_token_source(self._get_tokens)

        self._tabs.addTab(self._platform_tab, "플랫폼")
        self._tabs.addTab(self._accounts_tab, "계정")
        self._tabs.addTab(self._browser_tab, "브라우저")
        self._tabs.addTab(self._keywords_tab, "키워드 / 풀")
        self._tabs.addTab(self._titles_tab, "제목")
        self._tabs.addTab(self._maps_tab, "맵")
        self._tabs.addTab(self._post_tab, "포스트 블록")
        self._tabs.addTab(self._publish_tab, "발행")
        self._tabs.addTab(self._run_tab, "실행 설정")

        # ── Bottom panel ──
        self._bottom_tabs = QTabWidget()
        self._bottom_tabs.setTabsClosable(True)
        self._bottom_tabs.tabCloseRequested.connect(self._on_tab_close_requested)

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setPlaceholderText("YAML 미리보기...")
        self._bottom_tabs.addTab(self._preview, "YAML 미리보기")

        # ── File buttons ──
        btn_load = QPushButton("불러오기")
        btn_load.clicked.connect(self._load_yaml)
        btn_save = QPushButton("저장")
        btn_save.clicked.connect(self._save_yaml)
        btn_refresh = QPushButton("YAML 갱신")
        btn_refresh.clicked.connect(self._refresh_preview)

        # ── Workflow buttons ──
        self._btn_validate = QPushButton("검증")
        self._btn_validate.clicked.connect(self._run_validate)
        self._btn_prepare = QPushButton("세션 준비")
        self._btn_prepare.clicked.connect(self._run_prepare)
        self._btn_preview_plan = QPushButton("미리보기")
        self._btn_preview_plan.clicked.connect(self._run_preview)
        self._btn_dryrun = QPushButton("Dry-run")
        self._btn_dryrun.clicked.connect(self._run_dryrun)
        self._btn_execute = QPushButton("실행")
        self._btn_execute.setStyleSheet("QPushButton { font-weight: bold; }")
        self._btn_execute.clicked.connect(self._run_execute)

        self._btn_stop = QPushButton("중단")
        self._btn_stop.setStyleSheet("QPushButton { color: red; font-weight: bold; }")
        self._btn_stop.clicked.connect(self._stop_current)

        from gui.theme import SP_SM, SP_LG

        btn_row = QHBoxLayout()
        btn_row.setSpacing(SP_SM)
        btn_row.addWidget(btn_load)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_refresh)
        btn_row.addSpacing(SP_LG)
        btn_row.addWidget(self._btn_validate)
        btn_row.addWidget(self._btn_prepare)
        btn_row.addWidget(self._btn_preview_plan)
        btn_row.addWidget(self._btn_dryrun)
        btn_row.addWidget(self._btn_execute)
        btn_row.addWidget(self._btn_stop)

        # ── Layout ──
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._tabs)
        splitter.addWidget(self._bottom_tabs)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout = QVBoxLayout()
        layout.setContentsMargins(SP_SM, SP_SM, SP_SM, SP_SM)
        layout.setSpacing(SP_SM)
        layout.addWidget(splitter)
        layout.addLayout(btn_row)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self._status = QStatusBar()
        self.setStatusBar(self._status)

        self._last_saved_path: str = ""

        # ── Multi-job state ──
        self._jobs: dict[str, _RunningJob] = {}
        self._job_counter = 0

        self._cli_signals = _CliSignals()
        self._cli_signals.output.connect(self._on_cli_output)
        self._cli_signals.finished.connect(self._on_cli_finished)

    # ------------------------------------------------------------------
    # Token source
    # ------------------------------------------------------------------

    def _get_tokens(self) -> list[str]:
        tokens: list[str] = []
        kw_data = self._keywords_tab.to_dict()
        for slug in (kw_data.get("keywords") or {}):
            tokens.append(f"{{keyword:{slug}}}")
        for slug in (kw_data.get("pools") or {}):
            tokens.append(f"{{pool:{slug}}}")
        maps_data = self._maps_tab.to_dict()
        for slug in (maps_data.get("maps") or {}):
            tokens.append(f"{{map:{slug}}}")
        tokens.append("{i}")
        return tokens

    # ------------------------------------------------------------------
    # Close event
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        running = [j for j in self._jobs.values() if j.proc is not None]
        if running:
            names = ", ".join(j.label for j in running)
            reply = QMessageBox.question(
                self,
                "작업 실행 중",
                f"실행 중인 작업이 {len(running)}개 있습니다:\n{names}\n\n"
                "종료하면 모든 작업이 중단됩니다.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            for job in running:
                self._kill_job(job)
        event.accept()

    def _kill_job(self, job: _RunningJob) -> None:
        proc = job.proc
        if proc is None:
            return
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        except Exception:
            pass
        job.proc = None

    # ------------------------------------------------------------------
    # Build config
    # ------------------------------------------------------------------

    def _build_config(self) -> dict:
        config: dict = {}
        platform_data = self._platform_tab.to_dict()
        config["platform"] = platform_data.get("platform", "naver")
        config.update(self._browser_tab.to_dict())
        config.update(self._accounts_tab.to_dict())
        config.update(self._titles_tab.to_dict())
        config.update(self._keywords_tab.to_dict())
        config.update(self._maps_tab.to_dict())
        config.update(self._post_tab.to_dict())
        config["assets"] = platform_data.get("assets", "./assets")
        config["exif_optimization"] = platform_data.get("exif_optimization", True)
        if "session_store" in platform_data:
            config["session_store"] = platform_data["session_store"]
        config.update(self._publish_tab.to_dict())
        config.update(self._run_tab.to_dict())
        return config

    def _to_yaml(self) -> str:
        config = self._build_config()
        config.pop("_maps_data", None)
        return yaml.dump(
            config, allow_unicode=True, default_flow_style=False, sort_keys=False,
        )

    # ------------------------------------------------------------------
    # File actions
    # ------------------------------------------------------------------

    def _refresh_preview(self) -> None:
        try:
            self._preview.setPlainText(self._to_yaml())
            self._bottom_tabs.setCurrentWidget(self._preview)
            self._status.showMessage("YAML 갱신됨", 3000)
        except Exception as e:
            QMessageBox.warning(self, "미리보기 오류", str(e))

    def _save_yaml(self) -> None:
        default = self._last_saved_path or str(Path(self._platform_tab.workspace) / "campaign.yaml")
        path, _ = QFileDialog.getSaveFileName(self, "YAML 저장", default, "YAML (*.yaml *.yml)")
        if not path:
            return
        try:
            config = self._build_config()
            self._save_map_files(config, Path(path).parent)
            text = yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False)
            Path(path).write_text(text, encoding="utf-8")
            self._last_saved_path = path
            self._status.showMessage(f"저장 완료: {path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "저장 오류", str(e))

    def _load_yaml(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "YAML 불러오기", self._last_saved_path or self._platform_tab.workspace,
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
            self._status.showMessage(f"불러옴: {path}", 5000)
            self._refresh_preview()
        except Exception as e:
            QMessageBox.critical(self, "불러오기 오류", str(e))

    @staticmethod
    def _save_map_files(config: dict, base_dir: Path) -> None:
        maps_data: dict = config.pop("_maps_data", None) or {}
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
        maps_config: dict = raw.get("maps") or {}
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
    # CLI execution (multi-job)
    # ------------------------------------------------------------------

    def _ensure_saved(self) -> bool:
        if not self._last_saved_path:
            QMessageBox.information(self, "저장 필요", "먼저 YAML 파일을 저장하세요.")
            self._save_yaml()
        return bool(self._last_saved_path)

    def _new_job_id(self) -> str:
        self._job_counter += 1
        return f"job_{self._job_counter}"

    def _run_cli(self, *args: str, label: str = "", config_path: str = "") -> None:
        """Run CLI command in background thread. Multiple jobs can run simultaneously."""
        path = config_path or self._last_saved_path
        if not path:
            if not self._ensure_saved():
                return
            path = self._last_saved_path

        job_id = self._new_job_id()
        campaign_name = Path(path).stem

        # 로그 탭 생성
        log_widget = QTextEdit()
        log_widget.setReadOnly(True)
        log_widget.setPlainText(f"# {label} - {campaign_name}\n")
        tab_title = f"{label}: {campaign_name}"
        tab_index = self._bottom_tabs.addTab(log_widget, tab_title)
        self._bottom_tabs.setCurrentIndex(tab_index)

        job = _RunningJob(
            job_id=job_id,
            label=tab_title,
            log_widget=log_widget,
            tab_index=tab_index,
        )
        self._jobs[job_id] = job

        self._status.showMessage(f"{tab_title} ...", 0)

        cmd = [sys.executable, "-m", "cli", path, *args]
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

        def _worker():
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                )
                job.proc = proc
                for line in proc.stdout:
                    self._cli_signals.output.emit(job_id, line)
                proc.wait()
            except Exception as exc:
                self._cli_signals.output.emit(job_id, f"\n[ERROR] {exc}\n")
            finally:
                job.proc = None
                self._cli_signals.finished.emit(job_id, tab_title)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def _on_cli_output(self, job_id: str, line: str) -> None:
        job = self._jobs.get(job_id)
        if job and job.log_widget:
            job.log_widget.moveCursor(QTextCursor.MoveOperation.End)
            job.log_widget.insertPlainText(line)

    def _on_cli_finished(self, job_id: str, label: str) -> None:
        job = self._jobs.get(job_id)
        if job and job.log_widget:
            job.log_widget.moveCursor(QTextCursor.MoveOperation.End)
            job.log_widget.insertPlainText(f"\n-- 완료 --\n")
            # 탭 제목에 완료 표시
            idx = self._bottom_tabs.indexOf(job.log_widget)
            if idx >= 0:
                self._bottom_tabs.setTabText(idx, f"[완료] {label}")
        self._status.showMessage(f"{label} 완료", 5000)

    def _stop_current(self) -> None:
        """현재 보고 있는 로그 탭의 작업을 중단한다."""
        widget = self._bottom_tabs.currentWidget()
        if widget is self._preview:
            return
        for job in self._jobs.values():
            if job.log_widget is widget and job.proc is not None:
                self._kill_job(job)
                job.log_widget.moveCursor(QTextCursor.MoveOperation.End)
                job.log_widget.insertPlainText("\n\n-- 사용자에 의해 중단됨 --\n")
                idx = self._bottom_tabs.indexOf(job.log_widget)
                if idx >= 0:
                    self._bottom_tabs.setTabText(idx, f"[중단] {job.label}")
                self._status.showMessage("중단됨", 5000)
                return

    def _on_tab_close_requested(self, index: int) -> None:
        """로그 탭 닫기. YAML 미리보기는 닫을 수 없음. 실행 중이면 중단 확인."""
        widget = self._bottom_tabs.widget(index)
        if widget is self._preview:
            return  # YAML 미리보기는 닫지 않음

        # 실행 중인 job인지 확인
        for job_id, job in self._jobs.items():
            if job.log_widget is widget:
                if job.proc is not None:
                    reply = QMessageBox.question(
                        self, "작업 실행 중",
                        f"'{job.label}'이 실행 중입니다. 중단하고 닫으시겠습니까?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return
                    self._kill_job(job)
                del self._jobs[job_id]
                break

        self._bottom_tabs.removeTab(index)

    # ------------------------------------------------------------------
    # Workflow buttons
    # ------------------------------------------------------------------

    def _run_validate(self) -> None:
        self._run_cli("--validate", label="검증")

    def _run_prepare(self) -> None:
        self._run_cli("--prepare", label="세션 준비")

    def _run_preview(self) -> None:
        self._run_cli("--preview", label="미리보기")

    def _run_dryrun(self) -> None:
        self._run_cli(label="Dry-run")

    def _run_execute(self) -> None:
        if not self._ensure_saved():
            return

        has_progress = self._check_progress()

        if has_progress:
            msg = QMessageBox(self)
            msg.setWindowTitle("캠페인 실행")
            msg.setText("이전 실행에서 진행 기록이 있습니다.")
            msg.setInformativeText("어떻게 실행하시겠습니까?")
            btn_restart = msg.addButton("처음부터", QMessageBox.ButtonRole.AcceptRole)
            btn_skip = msg.addButton("이어서", QMessageBox.ButtonRole.AcceptRole)
            btn_cancel = msg.addButton("취소", QMessageBox.ButtonRole.RejectRole)
            msg.exec()

            clicked = msg.clickedButton()
            if clicked == btn_cancel:
                return
            elif clicked == btn_skip:
                self._run_cli("--execute", "--resume", label="실행(이어서)")
            else:
                self._run_cli("--execute", label="실행")
        else:
            reply = QMessageBox.question(
                self, "캠페인 실행",
                f"캠페인을 실제로 실행합니까?\n\n{self._last_saved_path}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._run_cli("--execute", label="실행")

    def _check_progress(self) -> bool:
        if not self._last_saved_path:
            return False
        try:
            from cli.progress import ProgressTracker
            base_dir = str(Path(self._last_saved_path).parent)
            pt = ProgressTracker(self._last_saved_path, base_dir)
            return pt.completed_count > 0
        except Exception:
            return False
