"""키워드 + 풀 탭 - 카테고리별 값 관리."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QInputDialog, QSplitter, QGroupBox,
    QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt

from gui.excel_io import export_kv_single, import_kv_single, template_kv_single


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


class KeywordsTab(QWidget):

    def __init__(self) -> None:
        super().__init__()

        self._kw_table = _KvTable(
            "키워드 (조합 생성)",
            "조합 수 = 카테고리별 값 수의 곱 x 제목 수. 예: region 3개 x subject 2개 = 6 조합",
            excel_label="키워드",
            template_examples=["강남", "서초", "송파"],
        )
        self._pool_table = _KvTable(
            "풀 (랜덤 선택)",
            "매 포스트마다 풀에서 하나를 무작위로 선택합니다.",
            excel_label="풀",
            template_examples=["추천", "리뷰", "비교"],
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
        self._kw_table.from_data(data.get("keywords") or {})
        self._pool_table.from_data(data.get("pools") or {})
