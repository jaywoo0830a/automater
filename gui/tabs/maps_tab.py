"""맵 탭 — 키워드 값별 매핑 데이터 관리 + 엑셀 대량 입력."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QInputDialog, QSplitter,
    QLineEdit, QFormLayout, QGroupBox, QMessageBox,
)

from gui.excel_buttons import ExcelButtonRow
from gui.excel_io import import_map, export_map, template_map


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

        by_form = QFormLayout()
        by_form.addRow("매핑 기준 (by):", self._by_input)

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

    def _load_table(self, data: dict[str, str]) -> None:
        self._table.setRowCount(0)
        for key, val in data.items():
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
        data: dict[str, str] = {}
        for row in range(self._table.rowCount()):
            k_item = self._table.item(row, 0)
            v_item = self._table.item(row, 1)
            key = k_item.text().strip() if k_item else ""
            val = v_item.text().strip() if v_item else ""
            if key:
                data[key] = val
        self._maps[slug]["data"] = data

    # ── excel helpers ────────────────────────────────────────────────

    def _get_current_map_data(self) -> dict[str, str]:
        self._sync_table_to_state()
        slug = self._current_slug()
        if not slug or slug not in self._maps:
            return {}
        return self._maps[slug].get("data", {})

    def _set_current_map_data(self, data: dict[str, str], append: bool = False) -> None:
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
            if not data:
                continue
            maps_config[slug] = {"by": by}
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
