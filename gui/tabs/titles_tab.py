"""제목 탭 - 제목 템플릿 목록 + 토큰 삽입."""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QPushButton, QDialog, QDialogButtonBox,
    QFormLayout,
)

from gui.excel_buttons import ExcelButtonRow
from gui.excel_io import import_titles, export_titles, template_titles
from gui.token_insert import TokenInsertButton


class TitlesTab(QWidget):

    def __init__(self) -> None:
        super().__init__()
        self._token_source: Callable[[], list[str]] = lambda: []

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
            "토큰: {keyword:slug}  {pool:slug}  {map:slug}  {i}  |  "
            "{...} 버튼으로 삽입 가능"
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
        layout.addWidget(QLabel("제목 템플릿:"))
        layout.addWidget(self._list)
        layout.addWidget(hint)
        layout.addLayout(btn_row)
        layout.addWidget(excel_row)
        self.setLayout(layout)

    def set_token_source(self, fn: Callable[[], list[str]]) -> None:
        self._token_source = fn

    def _add(self) -> None:
        dlg = _TitleDialog(self, self._token_source)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            text = dlg.value()
            if text:
                self._list.addItem(text)

    def _edit(self) -> None:
        item = self._list.currentItem()
        if not item:
            return
        dlg = _TitleDialog(self, self._token_source, item.text())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            text = dlg.value()
            if text:
                item.setText(text)

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


class _TitleDialog(QDialog):

    def __init__(self, parent: QWidget, token_source: Callable, default: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("제목 템플릿")
        self.setMinimumWidth(500)

        self._input = QLineEdit(default)
        self._input.setPlaceholderText("{keyword:region} {keyword:subject} 과외 추천")

        token_btn = TokenInsertButton(self._input, token_source)

        input_row = QHBoxLayout()
        input_row.addWidget(self._input)
        input_row.addWidget(token_btn)

        form = QFormLayout()
        form.addRow("템플릿:", input_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def value(self) -> str:
        return self._input.text().strip()
