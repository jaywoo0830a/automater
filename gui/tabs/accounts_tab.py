"""계정 탭 — 계정 추가/삭제, 분배 설정."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
)

from gui.excel_buttons import ExcelButtonRow
from gui.excel_io import import_accounts, export_accounts, template_accounts


_COLUMNS = [
    ("아이디", "username"),
    ("비밀번호", "password"),
    ("블로그 ID", "blog_id"),
    ("세션 경로", "session"),
    ("가중치", "weight"),
    ("최소", "min_posts"),
    ("최대", "max_posts"),
    ("프록시", "proxy"),
]
_DEFAULTS = ["", "", "", "", "1", "0", "0", ""]
_HEADERS = [c[0] for c in _COLUMNS]
_KEYS = [c[1] for c in _COLUMNS]


class AccountsTab(QWidget):

    def __init__(self) -> None:
        super().__init__()

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_HEADERS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        btn_add = QPushButton("+ 계정 추가")
        btn_add.clicked.connect(self._add_row)
        btn_remove = QPushButton("- 선택 삭제")
        btn_remove.clicked.connect(self._remove_row)

        hint = QLabel(
            "가중치: 분배 비율 (1:3 → 25%:75%)  |  "
            "최소: 보장 수량  |  "
            "최대: 상한 (0=무제한)"
        )
        hint.setStyleSheet("color: gray; font-size: 11px;")

        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_remove)
        btn_row.addStretch()

        excel_row = ExcelButtonRow(
            self,
            label="계정",
            default_filename="accounts.xlsx",
            import_fn=import_accounts,
            export_fn=lambda path, data: export_accounts(path, data),
            template_fn=template_accounts,
            get_data=self._get_accounts,
            set_data=self._set_accounts,
        )

        layout = QVBoxLayout()
        layout.addWidget(self._table)
        layout.addWidget(hint)
        layout.addLayout(btn_row)
        layout.addWidget(excel_row)
        self.setLayout(layout)

        self._add_row()

    def _add_row(self) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        for col, default in enumerate(_DEFAULTS):
            self._table.setItem(row, col, QTableWidgetItem(default))

    def _remove_row(self) -> None:
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)

    # -- excel helpers ---------------------------------------------------

    def _get_accounts(self) -> list[dict]:
        return self.to_dict().get("accounts", [])

    def _set_accounts(self, data: list[dict], append: bool = False) -> None:
        if append:
            existing = self._get_accounts()
            existing.extend(data)
            data = existing
        self.from_dict({"accounts": data})

    # -- serialisation ----------------------------------------------------

    def to_dict(self) -> dict:
        accounts = []
        for row in range(self._table.rowCount()):
            acc: dict = {}
            for col, key in enumerate(_KEYS):
                item = self._table.item(row, col)
                val = item.text().strip() if item else ""
                if not val:
                    continue
                if key in ("weight", "min_posts", "max_posts"):
                    ival = int(val)
                    if key == "weight" and ival == 1:
                        continue
                    if key in ("min_posts", "max_posts") and ival == 0:
                        continue
                    acc[key] = ival
                else:
                    acc[key] = val
            if acc.get("username"):
                accounts.append(acc)
        return {"accounts": accounts} if accounts else {}

    def from_dict(self, data: dict) -> None:
        accounts = data.get("accounts", [])
        self._table.setRowCount(0)
        for acc in accounts:
            row = self._table.rowCount()
            self._table.insertRow(row)
            for col, key in enumerate(_KEYS):
                val = str(acc.get(key, _DEFAULTS[col]))
                self._table.setItem(row, col, QTableWidgetItem(val))
