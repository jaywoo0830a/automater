"""키워드 + 풀 + 트리 키워드 탭."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QInputDialog, QSplitter, QGroupBox,
    QFileDialog, QMessageBox, QListWidget, QComboBox,
    QFormLayout,
)
from PySide6.QtCore import Qt

from gui.excel_io import (
    export_kv_single, import_kv_single, template_kv_single,
    export_tree, import_tree, template_tree,
)


class _KvTable(QWidget):
    """카테고리(slug) -> 값 목록 편집 테이블. 카테고리별 엑셀 import/export."""

    def __init__(self, title: str, hint: str, excel_label: str = "데이터",
                 template_examples: list[str] | None = None) -> None:
        super().__init__()
        self._excel_label = excel_label
        self._template_examples = template_examples

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["카테고리", "값 (콤마 구분)"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        btn_add = QPushButton("+ 추가")
        btn_add.clicked.connect(self._add)
        btn_remove = QPushButton("- 삭제")
        btn_remove.clicked.connect(self._remove)

        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_remove)
        btn_row.addStretch()

        hint_label = QLabel(hint)
        hint_label.setStyleSheet("color: gray; font-size: 11px;")

        # 엑셀 - 카테고리별 파일
        btn_import = QPushButton("엑셀 가져오기")
        btn_import.clicked.connect(self._on_import)
        btn_export = QPushButton("엑셀 내보내기")
        btn_export.clicked.connect(self._on_export)
        btn_template = QPushButton("엑셀 템플릿")
        btn_template.clicked.connect(self._on_template)

        excel_row = QHBoxLayout()
        excel_row.addWidget(btn_import)
        excel_row.addWidget(btn_export)
        excel_row.addWidget(btn_template)
        excel_row.addStretch()

        excel_hint = QLabel(
            "엑셀 파일: 1열에 값 나열. 파일명이 카테고리명이 됩니다."
        )
        excel_hint.setStyleSheet("color: gray; font-size: 11px;")

        layout = QVBoxLayout()
        layout.addWidget(QLabel(title))
        layout.addWidget(self._table)
        layout.addWidget(hint_label)
        layout.addLayout(btn_row)
        layout.addWidget(excel_hint)
        layout.addLayout(excel_row)
        self.setLayout(layout)

    def _add(self) -> None:
        slug, ok = QInputDialog.getText(self, "카테고리 추가", "카테고리 이름 (slug):")
        if ok and slug.strip():
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(slug.strip()))
            self._table.setItem(row, 1, QTableWidgetItem(""))

    def _remove(self) -> None:
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)

    # -- 엑셀: 카테고리별 파일 --

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, f"{self._excel_label} 엑셀 가져오기", "", "Excel (*.xlsx)",
        )
        if not path:
            return
        try:
            values = import_kv_single(path)
        except Exception as e:
            QMessageBox.critical(self, "엑셀 읽기 오류", str(e))
            return

        # 파일명에서 카테고리명 추출
        slug = Path(path).stem

        reply = QMessageBox.question(
            self,
            "가져오기 방식",
            f"카테고리: {slug}\n값: {len(values)}개\n\n"
            "기존 데이터에 추가하시겠습니까?\n\n"
            "예 = 기존 데이터 유지 + 추가\n"
            "아니오 = 해당 카테고리 교체",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return

        existing = self.to_data()
        if reply == QMessageBox.StandardButton.Yes and slug in existing:
            merged = list(dict.fromkeys(existing[slug] + values))
            existing[slug] = merged
        else:
            existing[slug] = values
        self.from_data(existing)

    def _on_export(self) -> None:
        # 선택된 카테고리 또는 전체
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.information(self, "선택 필요", "내보낼 카테고리를 선택하세요.")
            return
        slug_item = self._table.item(row, 0)
        slug = slug_item.text().strip() if slug_item else ""
        if not slug:
            return

        data = self.to_data()
        values = data.get(slug, [])
        if not values:
            QMessageBox.information(self, "데이터 없음", f"'{slug}' 카테고리에 값이 없습니다.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, f"{self._excel_label} 엑셀 내보내기", f"{slug}.xlsx", "Excel (*.xlsx)",
        )
        if not path:
            return
        try:
            export_kv_single(path, slug, values)
        except Exception as e:
            QMessageBox.critical(self, "엑셀 내보내기 오류", str(e))

    def _on_template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, f"{self._excel_label} 엑셀 템플릿",
            f"{self._excel_label}_template.xlsx",
            "Excel (*.xlsx)",
        )
        if not path:
            return
        try:
            slug = Path(path).stem.replace("_template", "")
            template_kv_single(path, slug, self._template_examples)
        except Exception as e:
            QMessageBox.critical(self, "템플릿 저장 오류", str(e))

    # -- 데이터 --

    def to_data(self) -> dict:
        result: dict = {}
        for row in range(self._table.rowCount()):
            slug_item = self._table.item(row, 0)
            vals_item = self._table.item(row, 1)
            slug = slug_item.text().strip() if slug_item else ""
            vals = vals_item.text().strip() if vals_item else ""
            if slug and vals:
                result[slug] = [v.strip() for v in vals.split(",") if v.strip()]
        return result

    def from_data(self, data: dict) -> None:
        self._table.setRowCount(0)
        for slug, vals in data.items():
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(slug))
            vals_str = ", ".join(vals) if isinstance(vals, list) else str(vals)
            self._table.setItem(row, 1, QTableWidgetItem(vals_str))


# ---------------------------------------------------------------------------
# Tree keywords editor
# ---------------------------------------------------------------------------

class _TreeEditor(QWidget):
    """트리 키워드(부모 → 자식) 편집기.

    좌측: 트리 슬러그 목록.
    우측: 부모 슬러그 콤보박스 + 부모 값별 자식 리스트(엑셀 long-format 호환).

    부모는 평면 keyword 이름을 입력 (다른 트리도 가능). 자식 목록은
    long-format 표 (부모값 | 자식값)로 편집하며, 한 부모의 자식이 여러
    개면 빈 부모 셀로 행을 이어 넣는다 — maps 탭과 동일한 컨벤션.
    """

    def __init__(self) -> None:
        super().__init__()
        self._trees: dict[str, dict] = {}     # {slug: {"parent": str, "by": dict}}
        self._updating = False
        self._keyword_source: Callable[[], list[str]] = lambda: []

        # ── 좌측 ──
        self._slug_list = QListWidget()
        self._slug_list.currentRowChanged.connect(self._on_slug_changed)

        btn_add_slug = QPushButton("+ 트리 추가")
        btn_add_slug.clicked.connect(self._add_slug)
        btn_remove_slug = QPushButton("- 트리 삭제")
        btn_remove_slug.clicked.connect(self._remove_slug)

        slug_btn_row = QHBoxLayout()
        slug_btn_row.addWidget(btn_add_slug)
        slug_btn_row.addWidget(btn_remove_slug)
        slug_btn_row.addStretch()

        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("트리 키워드 목록"))
        left_layout.addWidget(self._slug_list)
        left_layout.addLayout(slug_btn_row)
        left_widget = QWidget()
        left_widget.setLayout(left_layout)

        # ── 우측: 편집 패널 ──
        self._parent_combo = QComboBox()
        self._parent_combo.setEditable(True)
        self._parent_combo.lineEdit().textChanged.connect(self._on_parent_changed)
        self._parent_combo.activated.connect(lambda _i: None)  # noop placeholder

        parent_form = QFormLayout()
        parent_form.addRow("부모 슬러그:", self._parent_combo)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["부모 값", "자식 값"])
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

        # 엑셀 버튼 (트리 long-format)
        btn_import = QPushButton("엑셀 가져오기")
        btn_import.clicked.connect(self._on_import)
        btn_export = QPushButton("엑셀 내보내기")
        btn_export.clicked.connect(self._on_export)
        btn_template = QPushButton("엑셀 템플릿")
        btn_template.clicked.connect(self._on_template)

        excel_row = QHBoxLayout()
        excel_row.addWidget(btn_import)
        excel_row.addWidget(btn_export)
        excel_row.addWidget(btn_template)
        excel_row.addStretch()

        hint = QLabel(
            "각 행: 부모 값 | 자식 값. 한 부모에 자식이 여러 개면 부모 칸을 비우고 자식만 이어서 입력. "
            "_default = 부모 값에 entry가 없을 때 폴백."
        )
        hint.setStyleSheet("color: gray; font-size: 11px;")
        hint.setWordWrap(True)

        right_layout = QVBoxLayout()
        right_layout.addLayout(parent_form)
        right_layout.addWidget(QLabel("자식 목록 (long-format)"))
        right_layout.addWidget(self._table)
        right_layout.addWidget(hint)
        right_layout.addLayout(row_btn_row)
        right_layout.addLayout(excel_row)
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

    # -- keyword source (parent dropdown options) --

    def set_keyword_source(self, fn: Callable[[], list[str]]) -> None:
        """부모 슬러그 후보를 주는 콜백. flat keyword 이름들."""
        self._keyword_source = fn

    def _refresh_parent_combo(self) -> None:
        current_text = self._parent_combo.lineEdit().text()
        candidates = list(self._keyword_source())
        # 현재 선택된 트리 자기 자신은 제외
        cur = self._current_slug()
        if cur and cur in candidates:
            candidates.remove(cur)
        # 다른 트리들은 부모로 가능하므로 같이 표시
        for s in self._trees.keys():
            if s != cur and s not in candidates:
                candidates.append(s)
        self._updating = True
        self._parent_combo.clear()
        self._parent_combo.addItems(candidates)
        self._parent_combo.lineEdit().setText(current_text)
        self._updating = False

    # -- slug management --

    def _add_slug(self) -> None:
        slug, ok = QInputDialog.getText(self, "트리 추가", "트리 이름 (slug):")
        if not ok or not slug.strip():
            return
        slug = slug.strip()
        if slug in self._trees:
            QMessageBox.warning(self, "중복", f"'{slug}' 트리가 이미 존재합니다.")
            return
        self._trees[slug] = {"parent": "", "by": {}}
        self._slug_list.addItem(slug)
        self._slug_list.setCurrentRow(self._slug_list.count() - 1)

    def _remove_slug(self) -> None:
        row = self._slug_list.currentRow()
        if row < 0:
            return
        slug = self._slug_list.item(row).text()
        self._trees.pop(slug, None)
        self._slug_list.takeItem(row)

    def _current_slug(self) -> str | None:
        item = self._slug_list.currentItem()
        return item.text() if item else None

    def _on_slug_changed(self, _row: int) -> None:
        self._updating = True
        slug = self._current_slug()
        if slug and slug in self._trees:
            entry = self._trees[slug]
            self._refresh_parent_combo()
            self._parent_combo.lineEdit().setText(entry.get("parent", ""))
            self._load_table(entry.get("by", {}))
        else:
            self._parent_combo.lineEdit().clear()
            self._table.setRowCount(0)
        self._updating = False

    def _on_parent_changed(self, text: str) -> None:
        if self._updating:
            return
        slug = self._current_slug()
        if slug and slug in self._trees:
            self._trees[slug]["parent"] = text.strip()

    # -- table --

    def _load_table(self, by: dict) -> None:
        self._table.setRowCount(0)
        for parent, children in by.items():
            if isinstance(children, list):
                for i, c in enumerate(children):
                    row = self._table.rowCount()
                    self._table.insertRow(row)
                    self._table.setItem(row, 0, QTableWidgetItem(parent if i == 0 else ""))
                    self._table.setItem(row, 1, QTableWidgetItem(str(c)))
            else:
                row = self._table.rowCount()
                self._table.insertRow(row)
                self._table.setItem(row, 0, QTableWidgetItem(str(parent)))
                self._table.setItem(row, 1, QTableWidgetItem(str(children)))

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

    def _on_cell_changed(self, _row: int, _col: int) -> None:
        if self._updating:
            return
        self._sync_table_to_state()

    def _sync_table_to_state(self) -> None:
        slug = self._current_slug()
        if not slug or slug not in self._trees:
            return
        by: dict[str, list[str]] = {}
        last_parent = ""
        for row in range(self._table.rowCount()):
            p_item = self._table.item(row, 0)
            c_item = self._table.item(row, 1)
            parent = p_item.text().strip() if p_item else ""
            child = c_item.text().strip() if c_item else ""
            if not child:
                continue
            if parent:
                last_parent = parent
            if not last_parent:
                continue
            if last_parent not in by:
                by[last_parent] = []
            if child not in by[last_parent]:
                by[last_parent].append(child)
        self._trees[slug]["by"] = by

    # -- excel --

    def _on_import(self) -> None:
        slug = self._current_slug()
        if not slug:
            QMessageBox.information(self, "트리 선택", "먼저 좌측에서 트리를 선택하세요.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "트리 엑셀 가져오기", "", "Excel (*.xlsx)",
        )
        if not path:
            return
        try:
            by = import_tree(path)
        except Exception as e:
            QMessageBox.critical(self, "엑셀 읽기 오류", str(e))
            return

        reply = QMessageBox.question(
            self, "가져오기 방식",
            "기존 자식 데이터에 추가하시겠습니까?\n\n"
            "예 = 기존 + 새로 추가\n"
            "아니오 = 교체",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return

        if reply == QMessageBox.StandardButton.Yes:
            existing = self._trees[slug].get("by", {})
            for k, vs in by.items():
                cur = existing.get(k, [])
                merged = list(cur)
                for v in vs:
                    if v not in merged:
                        merged.append(v)
                existing[k] = merged
            by = existing

        self._trees[slug]["by"] = by
        self._updating = True
        self._load_table(by)
        self._updating = False

    def _on_export(self) -> None:
        slug = self._current_slug()
        if not slug:
            return
        self._sync_table_to_state()
        by = self._trees[slug].get("by", {})
        if not by:
            QMessageBox.information(self, "데이터 없음", f"'{slug}' 트리에 자식이 없습니다.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "트리 엑셀 내보내기", f"{slug}.xlsx", "Excel (*.xlsx)",
        )
        if not path:
            return
        try:
            export_tree(path, by)
        except Exception as e:
            QMessageBox.critical(self, "엑셀 내보내기 오류", str(e))

    def _on_template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "트리 엑셀 템플릿", "tree_template.xlsx", "Excel (*.xlsx)",
        )
        if not path:
            return
        try:
            template_tree(path)
        except Exception as e:
            QMessageBox.critical(self, "템플릿 저장 오류", str(e))

    # -- (de)serialize for campaign YAML --

    def to_data(self) -> dict:
        """Return {slug: {"parent": str, "by": {...}}} only for non-empty trees."""
        self._sync_table_to_state()
        out: dict = {}
        for slug, entry in self._trees.items():
            parent = (entry.get("parent") or "").strip()
            by = entry.get("by") or {}
            if not parent and not by:
                continue
            out[slug] = {"parent": parent, "by": dict(by)}
        return out

    def from_data(self, data: dict) -> None:
        self._trees.clear()
        self._slug_list.clear()
        for slug, entry in (data or {}).items():
            if not isinstance(entry, dict):
                continue
            parent = str(entry.get("parent", "") or "").strip()
            by = entry.get("by") or {}
            # 정규화: 자식이 list 가 아니면 단일값 → 리스트로
            norm: dict[str, list[str]] = {}
            if isinstance(by, dict):
                for k, vs in by.items():
                    if isinstance(vs, list):
                        norm[str(k)] = [str(v) for v in vs]
                    else:
                        norm[str(k)] = [str(vs)]
            self._trees[str(slug)] = {"parent": parent, "by": norm}
            self._slug_list.addItem(str(slug))
        if self._slug_list.count() > 0:
            self._slug_list.setCurrentRow(0)


# ---------------------------------------------------------------------------
# Top-level tab
# ---------------------------------------------------------------------------

class KeywordsTab(QWidget):

    def __init__(self) -> None:
        super().__init__()

        self._kw_table = _KvTable(
            "키워드 (조합 생성)",
            "조합 수 = 카테고리별 값 수의 곱 x 제목 수. 트리는 부모 값별로 펼쳐집니다.",
            excel_label="키워드",
            template_examples=["강남", "서초", "송파"],
        )
        self._tree_editor = _TreeEditor()
        self._tree_editor.set_keyword_source(lambda: list(self._kw_table.to_data().keys()))

        self._pool_table = _KvTable(
            "풀 (랜덤 선택)",
            "매 포스트마다 풀에서 하나를 무작위로 선택합니다.",
            excel_label="풀",
            template_examples=["추천", "리뷰", "비교"],
        )

        # 트리는 별도 그룹박스로
        tree_group = QGroupBox("트리 키워드 (부모 → 자식)")
        tree_group_layout = QVBoxLayout()
        tree_group_layout.setContentsMargins(8, 8, 8, 8)
        tree_group_layout.addWidget(self._tree_editor)
        tree_group.setLayout(tree_group_layout)

        # 상단: 평면 keywords + pools 좌우 분할
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.addWidget(self._kw_table)
        top_splitter.addWidget(self._pool_table)

        # 전체: 상단/하단 수직 분할
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(tree_group)
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 3)

        layout = QVBoxLayout()
        layout.addWidget(main_splitter)
        self.setLayout(layout)

    def to_dict(self) -> dict:
        d: dict = {}
        kw = self._kw_table.to_data()
        trees = self._tree_editor.to_data()

        # keywords 와 trees 를 하나의 dict 로 합친다 (DSL 스펙대로)
        merged: dict = {}
        for slug, vals in kw.items():
            merged[slug] = vals
        for slug, entry in trees.items():
            # tree 정의는 file: 모드는 GUI에서 안 쓰고 인라인만 (file은 main_window가 export 시 외부화)
            merged[slug] = {
                "parent": entry["parent"],
                "by": entry["by"],
            }

        if merged:
            d["keywords"] = merged

        pools = self._pool_table.to_data()
        if pools:
            d["pools"] = pools
        return d

    def from_dict(self, data: dict) -> None:
        kw_raw = data.get("keywords") or {}
        flat: dict = {}
        trees: dict = {}
        for slug, entry in kw_raw.items():
            if isinstance(entry, dict):
                trees[slug] = entry
            else:
                flat[slug] = entry

        self._kw_table.from_data(flat)
        self._tree_editor.from_data(trees)
        self._pool_table.from_data(data.get("pools") or {})
