"""키워드 + 풀 탭 — 카테고리별 값 관리."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QInputDialog, QSplitter, QGroupBox,
)
from PySide6.QtCore import Qt

from gui.excel_buttons import ExcelButtonRow
from gui.excel_io import import_kv, export_kv, template_kv


class _KvTable(QWidget):
    """카테고리(slug) → 값 목록 편집 테이블."""

    def __init__(self, title: str, hint: str, excel_label: str = "데이터",
                 excel_filename: str = "data.xlsx",
                 template_examples: list[list[str]] | None = None) -> None:
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

        excel_row = ExcelButtonRow(
            self,
            label=excel_label,
            default_filename=excel_filename,
            import_fn=import_kv,
            export_fn=lambda path, data: export_kv(path, data, sheet_name=excel_label),
            template_fn=lambda path: template_kv(path, sheet_name=excel_label, examples=self._template_examples),
            get_data=self.to_data,
            set_data=self._set_data,
        )

        layout = QVBoxLayout()
        layout.addWidget(QLabel(title))
        layout.addWidget(self._table)
        layout.addWidget(hint_label)
        layout.addLayout(btn_row)
        layout.addWidget(excel_row)
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

    def _set_data(self, data: dict, append: bool = False) -> None:
        if append:
            existing = self.to_data()
            for slug, vals in data.items():
                if slug in existing:
                    merged = list(dict.fromkeys(existing[slug] + vals))
                    existing[slug] = merged
                else:
                    existing[slug] = vals
            data = existing
        self.from_data(data)

    def from_data(self, data: dict) -> None:
        self._table.setRowCount(0)
        for slug, vals in data.items():
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(slug))
            vals_str = ", ".join(vals) if isinstance(vals, list) else str(vals)
            self._table.setItem(row, 1, QTableWidgetItem(vals_str))


class KeywordsTab(QWidget):

    def __init__(self) -> None:
        super().__init__()

        self._kw_table = _KvTable(
            "키워드 (조합 생성)",
            "조합 수 = 카테고리별 값 수의 곱 × 제목 수. 예: region 3개 × subject 2개 = 6 조합",
            excel_label="키워드",
            excel_filename="keywords.xlsx",
            template_examples=[["region", "강남, 서초, 송파"], ["subject", "수학, 영어"]],
        )
        self._pool_table = _KvTable(
            "풀 (랜덤 선택)",
            "매 포스트마다 풀에서 하나를 무작위로 선택합니다.",
            excel_label="풀",
            excel_filename="pools.xlsx",
            template_examples=[["suffix", "추천, 리뷰, 비교"]],
        )

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._kw_table)
        splitter.addWidget(self._pool_table)

        layout = QVBoxLayout()
        layout.addWidget(splitter)
        self.setLayout(layout)

    def to_dict(self) -> dict:
        d: dict = {}
        kw = self._kw_table.to_data()
        if kw:
            d["keywords"] = kw
        pools = self._pool_table.to_data()
        if pools:
            d["pools"] = pools
        return d

    def from_dict(self, data: dict) -> None:
        self._kw_table.from_data(data.get("keywords", {}))
        self._pool_table.from_data(data.get("pools", {}))
