"""맵 탭 — 키워드 값별 매핑 데이터 관리 + 엑셀 대량 입력."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QInputDialog, QSplitter,
    QLineEdit, QFormLayout, QGroupBox, QMessageBox,
    QCompleter,
)

from gui.excel_buttons import ExcelButtonRow
from gui.excel_io import import_map, export_map, template_map
from gui.token_insert import TokenInsertButton


class MapsTab(QWidget):

    def __init__(self) -> None:
        super().__init__()

        # ── 왼쪽: 맵 슬러그 목록 ──
        self._slug_list = QListWidget()
        self._slug_list.currentRowChanged.connect(self._on_slug_changed)

        btn_add_slug = QPushButton("+ 맵 추가")
        btn_add_slug.clicked.connect(self._add_slug)
        btn_remove_slug = QPushButton("- 맵 삭제")
        btn_remove_slug.clicked.connect(self._remove_slug)

        slug_btn_row = QHBoxLayout()
        slug_btn_row.addWidget(btn_add_slug)
        slug_btn_row.addWidget(btn_remove_slug)
        slug_btn_row.addStretch()

        self._by_input = QLineEdit()
        self._by_input.setPlaceholderText("{keyword:region}")
        self._by_input.textChanged.connect(self._on_by_changed)

        self._token_source: Callable[[], list[str]] = lambda: []
        self._by_completer = QCompleter([], self)
        self._by_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._by_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._by_input.setCompleter(self._by_completer)
        self._by_input.focusInEvent = self._by_focus_wrapper(self._by_input.focusInEvent)

        self._by_token_btn = TokenInsertButton(self._by_input)

        by_row = QHBoxLayout()
        by_row.addWidget(self._by_input, 1)
        by_row.addWidget(self._by_token_btn)

        by_form = QFormLayout()
        by_form.addRow("매핑 기준 (by):", by_row)

        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("맵 목록"))
        left_layout.addWidget(self._slug_list)
        left_layout.addLayout(slug_btn_row)
        left_layout.addLayout(by_form)

        left_widget = QWidget()
        left_widget.setLayout(left_layout)

        # ── 오른쪽: 키:값 테이블 ──
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["키", "값"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.cellChanged.connect(self._on_cell_changed)

        btn_add_row = QPushButton("+ 행 추가")
        btn_add_row.clicked.connect(self._add_row)
        btn_remove_row = QPushButton("- 행 삭제")
        btn_remove_row.clicked.connect(self._remove_row)

        row_btn_row = QHBoxLayout()
        row_btn_row.addWidget(btn_add_row)
        row_btn_row.addWidget(btn_remove_row)
        row_btn_row.addStretch()

        self._excel_row = ExcelButtonRow(
            self,
            label="맵",
            default_filename="map.xlsx",
            import_fn=import_map,
            export_fn=lambda path, data: export_map(path, data),
            template_fn=template_map,
            get_data=self._get_current_map_data,
            set_data=self._set_current_map_data,
        )

        hint = QLabel(
            "키: 키워드 값 (예: 강남)  |  값: 매핑 결과 (예: gangnam.jpg)  |  "
            "_default: 기본값"
        )
        hint.setStyleSheet("color: gray; font-size: 11px;")
        hint.setWordWrap(True)

        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("매핑 데이터"))
        right_layout.addWidget(self._table)
        right_layout.addWidget(hint)
        right_layout.addLayout(row_btn_row)
        right_layout.addWidget(self._excel_row)

        right_widget = QWidget()
        right_widget.setLayout(right_layout)

        # ── splitter ──
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout = QVBoxLayout()
        layout.addWidget(splitter)
        self.setLayout(layout)

        # ── internal state ──
        # {slug: {"by": str, "data": {key: value}}}
        self._maps: dict[str, dict] = {}
        self._updating = False

    # ── token source (keyword autocomplete for "by" field) ────────────

    def set_token_source(self, fn: Callable[[], list[str]]) -> None:
        """MainWindow에서 호출. keyword 토큰만 필터링하여 자동완성에 사용."""
        self._token_source = fn
        self._by_token_btn._token_source = self._get_keyword_tokens

    def _get_keyword_tokens(self) -> list[str]:
        """by 필드에 유효한 {keyword:...} 토큰만 반환."""
        return [t for t in self._token_source() if t.startswith("{keyword:")]

    def _refresh_completer(self) -> None:
        tokens = self._get_keyword_tokens()
        from PySide6.QtCore import QStringListModel
        model = QStringListModel(tokens, self._by_completer)
        self._by_completer.setModel(model)

    def _by_focus_wrapper(self, original):
        """by 입력 필드에 포커스가 들어올 때 completer 목록을 갱신."""
        def wrapped(event):
            self._refresh_completer()
            original(event)
        return wrapped

    # ── slug management ──────────────────────────────────────────────

    def _add_slug(self) -> None:
        slug, ok = QInputDialog.getText(self, "맵 추가", "맵 이름 (slug):")
        if not ok or not slug.strip():
            return
        slug = slug.strip()
        if slug in self._maps:
            QMessageBox.warning(self, "중복", f"'{slug}' 맵이 이미 존재합니다.")
            return
        self._maps[slug] = {"by": "", "data": {}}
        self._slug_list.addItem(slug)
        self._slug_list.setCurrentRow(self._slug_list.count() - 1)

    def _remove_slug(self) -> None:
        row = self._slug_list.currentRow()
        if row < 0:
            return
        slug = self._slug_list.item(row).text()
        self._maps.pop(slug, None)
        self._slug_list.takeItem(row)

    def _current_slug(self) -> str | None:
        item = self._slug_list.currentItem()
        return item.text() if item else None

    # ── slug selection changed ───────────────────────────────────────

    def _on_slug_changed(self, row: int) -> None:
        self._updating = True
        slug = self._current_slug()
        if slug and slug in self._maps:
            entry = self._maps[slug]
            self._by_input.setText(entry.get("by", ""))
            self._load_table(entry.get("data", {}))
        else:
            self._by_input.clear()
            self._table.setRowCount(0)
        self._updating = False

    def _on_by_changed(self, text: str) -> None:
        if self._updating:
            return
        slug = self._current_slug()
        if slug and slug in self._maps:
            self._maps[slug]["by"] = text.strip()

    # ── table management ─────────────────────────────────────────────

    def _load_table(self, data: dict) -> None:
        self._table.setRowCount(0)
        for key, val in data.items():
            if isinstance(val, list):
                for i, item in enumerate(val):
                    row = self._table.rowCount()
                    self._table.insertRow(row)
                    self._table.setItem(row, 0, QTableWidgetItem(key if i == 0 else ""))
                    self._table.setItem(row, 1, QTableWidgetItem(str(item)))
            else:
                row = self._table.rowCount()
                self._table.insertRow(row)
                self._table.setItem(row, 0, QTableWidgetItem(str(key)))
                self._table.setItem(row, 1, QTableWidgetItem(str(val)))

    def _add_row(self) -> None:
        if not self._current_slug():
            return
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(""))
        self._table.setItem(row, 1, QTableWidgetItem(""))

    def _remove_row(self) -> None:
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)
            self._sync_table_to_state()

    def _on_cell_changed(self, row: int, col: int) -> None:
        if self._updating:
            return
        self._sync_table_to_state()

    def _sync_table_to_state(self) -> None:
        slug = self._current_slug()
        if not slug or slug not in self._maps:
            return
        data: dict[str, str | list[str]] = {}
        last_key = ""
        for row in range(self._table.rowCount()):
            k_item = self._table.item(row, 0)
            v_item = self._table.item(row, 1)
            key = k_item.text().strip() if k_item else ""
            val = v_item.text().strip() if v_item else ""
            if not val:
                continue
            if key:
                last_key = key
            if not last_key:
                continue
            if last_key in data:
                existing = data[last_key]
                if isinstance(existing, list):
                    existing.append(val)
                else:
                    data[last_key] = [existing, val]
            else:
                data[last_key] = val
        self._maps[slug]["data"] = data

    # ── excel helpers ────────────────────────────────────────────────

    def _get_current_map_data(self) -> dict[str, str | list[str]]:
        self._sync_table_to_state()
        slug = self._current_slug()
        if not slug or slug not in self._maps:
            return {}
        return self._maps[slug].get("data", {})

    def _set_current_map_data(self, data: dict[str, str | list[str]], append: bool = False) -> None:
        slug = self._current_slug()
        if not slug:
            QMessageBox.warning(self, "맵 선택", "먼저 왼쪽에서 맵을 선택하세요.")
            return
        if slug not in self._maps:
            self._maps[slug] = {"by": "", "data": {}}

        if append:
            existing = self._maps[slug].get("data", {})
            existing.update(data)
            data = existing

        self._maps[slug]["data"] = data
        self._updating = True
        self._load_table(data)
        self._updating = False

    # ── serialisation (campaign YAML) ────────────────────────────────

    def to_dict(self) -> dict:
        self._sync_table_to_state()
        if not self._maps:
            return {}
        maps_config: dict = {}
        maps_data: dict = {}
        for slug, entry in self._maps.items():
            by = entry.get("by", "")
            data = entry.get("data", {})
            # file 경로는 저장 시 _save_map_files에서 채워짐
            maps_config[slug] = {"by": by, "file": f"maps/{slug}.yaml"}
            maps_data[slug] = data
        if not maps_config:
            return {}
        return {"maps": maps_config, "_maps_data": maps_data}

    def from_dict(self, data: dict) -> None:
        self._maps.clear()
        self._slug_list.clear()

        maps_config = data.get("maps", {})
        maps_data = data.get("_maps_data", {})

        for slug, entry in maps_config.items():
            by = entry.get("by", "") if isinstance(entry, dict) else ""
            map_data = maps_data.get(slug, {})
            self._maps[slug] = {"by": by, "data": map_data}
            self._slug_list.addItem(slug)

        if self._slug_list.count() > 0:
            self._slug_list.setCurrentRow(0)
