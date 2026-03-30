"""
gui/main_window.py
-------------------
Main window - campaign sidebar + builder + multi-campaign execution.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

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
    QListWidget,
    QListWidgetItem,
    QInputDialog,
    QLabel,
    QGroupBox,
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
# Signal bridge
# ---------------------------------------------------------------------------

class _CliSignals(QObject):
    output = Signal(str, str)     # (campaign_name, line)
    finished = Signal(str, str)   # (campaign_name, label)


class _CampaignState:
    """하나의 캠페인 상태."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.file_path: str = ""
        self.config: dict = {}
        self.proc: subprocess.Popen | None = None
        self.log_lines: list[str] = []
        self.status: str = ""  # "", "실행 중", "[완료]", "[중단]"


class MainWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("캠페인 빌더")
        self.setMinimumSize(1100, 750)

        # ── Campaign state ──
        self._campaigns: dict[str, _CampaignState] = {}
        self._current_name: str = ""

        self._cli_signals = _CliSignals()
        self._cli_signals.output.connect(self._on_cli_output)
        self._cli_signals.finished.connect(self._on_cli_finished)

        # ── Left sidebar ──
        self._sidebar = QListWidget()
        self._sidebar.currentItemChanged.connect(self._on_campaign_switched)

        btn_new = QPushButton("+ 새 캠페인")
        btn_new.clicked.connect(self._new_campaign)
        btn_load_file = QPushButton("파일 열기")
        btn_load_file.clicked.connect(self._load_campaign_file)
        btn_remove = QPushButton("- 삭제")
        btn_remove.clicked.connect(self._remove_campaign)

        sidebar_btns = QHBoxLayout()
        sidebar_btns.addWidget(btn_new)
        sidebar_btns.addWidget(btn_load_file)
        sidebar_btns.addWidget(btn_remove)

        sidebar_layout = QVBoxLayout()
        sidebar_layout.addWidget(QLabel("캠페인 목록"))
        sidebar_layout.addWidget(self._sidebar)
        sidebar_layout.addLayout(sidebar_btns)

        sidebar_widget = QWidget()
        sidebar_widget.setLayout(sidebar_layout)
        sidebar_widget.setMaximumWidth(200)

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

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setPlaceholderText("YAML 미리보기...")

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setPlaceholderText("실행 로그...")

        self._bottom_tabs.addTab(self._preview, "YAML 미리보기")
        self._bottom_tabs.addTab(self._log, "실행 로그")

        # ── Buttons ──
        btn_save = QPushButton("저장")
        btn_save.clicked.connect(self._save_yaml)
        btn_refresh = QPushButton("YAML 갱신")
        btn_refresh.clicked.connect(self._refresh_preview)

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
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_refresh)
        btn_row.addSpacing(SP_LG)
        btn_row.addWidget(self._btn_validate)
        btn_row.addWidget(self._btn_prepare)
        btn_row.addWidget(self._btn_preview_plan)
        btn_row.addWidget(self._btn_dryrun)
        btn_row.addWidget(self._btn_execute)
        btn_row.addWidget(self._btn_stop)

        # ── Right panel (builder + bottom + buttons) ──
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.addWidget(self._tabs)
        right_splitter.addWidget(self._bottom_tabs)
        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 2)

        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(SP_SM)
        right_layout.addWidget(right_splitter)
        right_layout.addLayout(btn_row)

        right_widget = QWidget()
        right_widget.setLayout(right_layout)

        # ── Main splitter (sidebar | right) ──
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(sidebar_widget)
        main_splitter.addWidget(right_widget)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(SP_SM, SP_SM, SP_SM, SP_SM)
        main_layout.setSpacing(SP_SM)
        main_layout.addWidget(main_splitter)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self._status = QStatusBar()
        self.setStatusBar(self._status)

        # 기본 캠페인 하나 생성
        self._new_campaign_internal("새 캠페인")

    # ------------------------------------------------------------------
    # Campaign management
    # ------------------------------------------------------------------

    def _new_campaign_internal(self, name: str) -> _CampaignState:
        """캠페인 생성 (내부)."""
        # 이름 중복 방지
        base = name
        counter = 1
        while name in self._campaigns:
            name = f"{base} ({counter})"
            counter += 1

        state = _CampaignState(name)
        self._campaigns[name] = state

        item = QListWidgetItem(name)
        self._sidebar.addItem(item)
        self._sidebar.setCurrentItem(item)
        return state

    def _new_campaign(self) -> None:
        name, ok = QInputDialog.getText(self, "새 캠페인", "캠페인 이름:")
        if ok and name.strip():
            self._new_campaign_internal(name.strip())

    def _load_campaign_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "캠페인 파일 열기",
            self._platform_tab.workspace,
            "YAML (*.yaml *.yml)",
        )
        if not path:
            return
        name = Path(path).stem
        state = self._new_campaign_internal(name)
        state.file_path = path
        self._load_from_file(path)

    def _remove_campaign(self) -> None:
        item = self._sidebar.currentItem()
        if not item:
            return
        name = item.text()
        state = self._campaigns.get(name)
        if state and state.proc is not None:
            reply = QMessageBox.question(
                self, "실행 중",
                f"'{name}' 캠페인이 실행 중입니다. 중단하고 삭제하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._kill_job(state)

        self._campaigns.pop(name, None)
        row = self._sidebar.row(item)
        self._sidebar.takeItem(row)

        if self._sidebar.count() == 0:
            self._new_campaign_internal("새 캠페인")

    def _on_campaign_switched(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        # 이전 캠페인 데이터 저장
        if previous:
            prev_name = previous.text()
            prev_state = self._campaigns.get(prev_name)
            if prev_state:
                prev_state.config = self._build_config()

        # 새 캠페인 데이터 로드
        if current:
            name = current.text()
            self._current_name = name
            state = self._campaigns.get(name)
            if state and state.config:
                self._apply_config(state.config)
            elif state and state.file_path:
                self._load_from_file(state.file_path)

            # 로그 복원
            self._log.clear()
            if state:
                self._log.setPlainText("".join(state.log_lines))
                self._update_sidebar_label(state)

    def _update_sidebar_label(self, state: _CampaignState) -> None:
        """사이드바 아이템 텍스트를 상태에 맞게 갱신."""
        for i in range(self._sidebar.count()):
            item = self._sidebar.item(i)
            if item and item.text().rstrip(" *").rstrip("[완료] ").rstrip("[중단] ") == state.name:
                if state.proc is not None:
                    item.setText(f"{state.name} *")
                elif state.status:
                    item.setText(f"{state.status} {state.name}")
                else:
                    item.setText(state.name)
                break

    def _current_state(self) -> _CampaignState | None:
        return self._campaigns.get(self._current_name)

    # ------------------------------------------------------------------
    # Config apply/build
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

    def _apply_config(self, config: dict) -> None:
        self._platform_tab.from_dict(config)
        self._accounts_tab.from_dict(config)
        self._browser_tab.from_dict(config)
        self._titles_tab.from_dict(config)
        self._keywords_tab.from_dict(config)
        self._maps_tab.from_dict(config)
        self._post_tab.from_dict(config)
        self._publish_tab.from_dict(config)
        self._run_tab.from_dict(config)

    def _to_yaml(self) -> str:
        config = self._build_config()
        config.pop("_maps_data", None)
        return yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False)

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
        running = [s for s in self._campaigns.values() if s.proc is not None]
        if running:
            names = ", ".join(s.name for s in running)
            reply = QMessageBox.question(
                self, "작업 실행 중",
                f"실행 중인 캠페인: {names}\n\n종료하면 모든 작업이 중단됩니다.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            for s in running:
                self._kill_job(s)
        event.accept()

    def _kill_job(self, state: _CampaignState) -> None:
        proc = state.proc
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
        state.proc = None

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
        state = self._current_state()
        if not state:
            return
        default = state.file_path or str(Path(self._platform_tab.workspace) / f"{state.name}.yaml")
        path, _ = QFileDialog.getSaveFileName(self, "YAML 저장", default, "YAML (*.yaml *.yml)")
        if not path:
            return
        try:
            config = self._build_config()
            self._save_map_files(config, Path(path).parent)
            text = yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False)
            Path(path).write_text(text, encoding="utf-8")
            state.file_path = path
            state.config = config
            self._status.showMessage(f"저장 완료: {path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "저장 오류", str(e))

    def _load_from_file(self, path: str) -> None:
        try:
            raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
            self._load_map_files(raw, Path(path).parent)
            self._apply_config(raw)
            state = self._current_state()
            if state:
                state.config = raw
                state.file_path = path
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
    # CLI execution
    # ------------------------------------------------------------------

    def _ensure_saved(self) -> bool:
        state = self._current_state()
        if not state:
            return False
        if not state.file_path:
            QMessageBox.information(self, "저장 필요", "먼저 YAML 파일을 저장하세요.")
            self._save_yaml()
        return bool(state and state.file_path)

    def _run_cli(self, *args: str, label: str = "") -> None:
        state = self._current_state()
        if not state:
            return
        if state.proc is not None:
            QMessageBox.information(self, "실행 중", f"'{state.name}' 캠페인이 이미 실행 중입니다.")
            return
        if not self._ensure_saved():
            return

        state.status = "실행 중"
        state.log_lines = [f"# {label} - {state.name}\n"]
        self._log.setPlainText(state.log_lines[0])
        self._bottom_tabs.setCurrentIndex(1)
        self._update_sidebar_label(state)
        self._status.showMessage(f"{state.name}: {label} ...", 0)

        cmd = [sys.executable, "-m", "cli", state.file_path, *args]
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        campaign_name = state.name

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
                state.proc = proc
                for line in proc.stdout:
                    self._cli_signals.output.emit(campaign_name, line)
                proc.wait()
            except Exception as exc:
                self._cli_signals.output.emit(campaign_name, f"\n[ERROR] {exc}\n")
            finally:
                state.proc = None
                self._cli_signals.finished.emit(campaign_name, label)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def _on_cli_output(self, campaign_name: str, line: str) -> None:
        state = self._campaigns.get(campaign_name)
        if not state:
            return
        state.log_lines.append(line)
        # 현재 보고 있는 캠페인이면 로그 표시
        if campaign_name == self._current_name:
            self._log.moveCursor(QTextCursor.MoveOperation.End)
            self._log.insertPlainText(line)

    def _on_cli_finished(self, campaign_name: str, label: str) -> None:
        state = self._campaigns.get(campaign_name)
        if state:
            state.status = "[완료]"
            state.log_lines.append("\n-- 완료 --\n")
            self._update_sidebar_label(state)
            if campaign_name == self._current_name:
                self._log.moveCursor(QTextCursor.MoveOperation.End)
                self._log.insertPlainText("\n-- 완료 --\n")
        self._status.showMessage(f"{campaign_name}: {label} 완료", 5000)

    def _stop_current(self) -> None:
        state = self._current_state()
        if not state or state.proc is None:
            return
        self._kill_job(state)
        state.status = "[중단]"
        state.log_lines.append("\n-- 사용자에 의해 중단됨 --\n")
        self._update_sidebar_label(state)
        self._log.moveCursor(QTextCursor.MoveOperation.End)
        self._log.insertPlainText("\n-- 사용자에 의해 중단됨 --\n")
        self._status.showMessage(f"{state.name}: 중단됨", 5000)

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

        state = self._current_state()
        if not state:
            return

        has_progress = self._check_progress(state)

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
                f"캠페인을 실제로 실행합니까?\n\n{state.file_path}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._run_cli("--execute", label="실행")

    @staticmethod
    def _check_progress(state: _CampaignState) -> bool:
        if not state.file_path:
            return False
        try:
            from cli.progress import ProgressTracker
            base_dir = str(Path(state.file_path).parent)
            pt = ProgressTracker(state.file_path, base_dir)
            return pt.completed_count > 0
        except Exception:
            return False
