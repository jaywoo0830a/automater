"""제목 탭 — 제목 템플릿 목록."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QPushButton, QInputDialog,
)

from gui.excel_buttons import ExcelButtonRow
from gui.excel_io import import_titles, export_titles, template_titles


class TitlesTab(QWidget):

    def __init__(self) -> None:
        super().__init__()

        self._list = QListWidget()

        btn_add = QPushButton("+ 템플릿 추가")
        btn_add.clicked.connect(self._add)
        btn_edit = QPushButton("수정")
        btn_edit.clicked.connect(self._edit)
        btn_remove = QPushButton("- 삭제")
        btn_remove.clicked.connect(self._remove)

        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_edit)
        btn_row.addWidget(btn_remove)
        btn_row.addStretch()

        hint = QLabel(
            "사용 가능한 토큰: {keyword:slug}  {pool:slug}  {map:slug}  {i}"
        )
        hint.setStyleSheet("color: gray; font-size: 11px;")

        excel_row = ExcelButtonRow(
            self,
            label="제목",
            default_filename="titles.xlsx",
            import_fn=import_titles,
            export_fn=lambda path, data: export_titles(path, data),
            template_fn=template_titles,
            get_data=self._get_titles,
            set_data=self._set_titles,
        )

        layout = QVBoxLayout()
        layout.addWidget(QLabel("제목 템플릿 (하나씩 추가):"))
        layout.addWidget(self._list)
        layout.addWidget(hint)
        layout.addLayout(btn_row)
        layout.addWidget(excel_row)
        self.setLayout(layout)

    def _add(self) -> None:
        text, ok = QInputDialog.getText(
            self, "제목 템플릿 추가",
            "템플릿:",
            text="{keyword:region} {keyword:subject} 과외 추천",
        )
        if ok and text.strip():
            self._list.addItem(text.strip())

    def _edit(self) -> None:
        item = self._list.currentItem()
        if not item:
            return
        text, ok = QInputDialog.getText(
            self, "제목 템플릿 수정", "템플릿:", text=item.text()
        )
        if ok and text.strip():
            item.setText(text.strip())

    def _remove(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)

    # -- excel helpers ---------------------------------------------------

    def _get_titles(self) -> list[str]:
        return self.to_dict().get("titles", [])

    def _set_titles(self, data: list[str], append: bool = False) -> None:
        if append:
            existing = self._get_titles()
            for t in data:
                if t not in existing:
                    existing.append(t)
            data = existing
        self.from_dict({"titles": data})

    # -- serialisation ----------------------------------------------------

    def to_dict(self) -> dict:
        titles = [self._list.item(i).text() for i in range(self._list.count())]
        return {"titles": titles} if titles else {}

    def from_dict(self, data: dict) -> None:
        self._list.clear()
        for title in data.get("titles", []):
            self._list.addItem(str(title))
