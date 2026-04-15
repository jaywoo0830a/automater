"""패키징 다이얼로그 - zip 생성 전 경로 필드 검토."""

from __future__ import annotations

import copy
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QAbstractItemView,
)
from PySide6.QtCore import Qt

from automator.path_fields import PathField, iter_path_fields, relocate_to


class PackDialog(QDialog):
    """잡 딕셔너리의 모든 경로 필드를 보여주고, 절대경로는 사용자가 직접
    Workspace/Assets 디렉토리로 복사(또는 상대화)할 수 있게 한다.

    메모리상 복사본(``job_copy``)만 수정하며 원본 ``job``은 건드리지 않는다.
    ``exec()`` 이 Accepted 로 반환되면 ``job_copy`` 가 최종 상태.
    """

    def __init__(self, job: dict, base_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("패키징")
        self.resize(900, 560)

        self.job_copy: dict = copy.deepcopy(job)
        self._base_dir = Path(base_dir).resolve()

        layout = QVBoxLayout(self)

        # --- 디렉토리 입력 ---
        self._assets_edit = QLineEdit(str(self._resolve_assets_default()))
        layout.addLayout(self._make_dir_row("Assets 디렉토리:", self._assets_edit))

        # --- 안내 라벨 ---
        hint = QLabel(
            "절대경로는 <b>assets로 복사</b> 버튼으로 Assets 디렉토리 안으로 옮기면 상대경로화됩니다.\n"
            "절대경로가 남아있으면 패키징 버튼이 비활성화됩니다."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # --- 경로 필드 테이블 ---
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["위치", "값", "상태", "작업"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._table, 1)

        # --- 버튼 ---
        self._pack_btn = QPushButton("패키징")
        self._pack_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._pack_btn)
        layout.addLayout(btn_row)

        self._refresh()

    # ------------------------------------------------------------------
    # 내부 도우미
    # ------------------------------------------------------------------

    def _resolve_assets_default(self) -> Path:
        assets_value = self.job_copy.get("assets") or "./assets"
        p = Path(str(assets_value))
        if not p.is_absolute():
            p = self._base_dir / p
        return p.resolve()

    def _make_dir_row(self, label: str, edit: QLineEdit) -> QHBoxLayout:
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setFixedWidth(130)
        row.addWidget(lbl)
        row.addWidget(edit, 1)
        btn = QPushButton("...")
        btn.setFixedWidth(30)
        btn.clicked.connect(lambda: self._browse(edit))
        row.addWidget(btn)
        return row

    def _browse(self, edit: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "디렉토리 선택", edit.text())
        if path:
            edit.setText(path)

    def _target_dir(self) -> Path:
        return Path(self._assets_edit.text()).expanduser()

    # ------------------------------------------------------------------
    # 테이블 갱신
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        fields = list(iter_path_fields(self.job_copy))
        self._table.setRowCount(len(fields))
        absolute_count = 0

        for row, field in enumerate(fields):
            self._table.setItem(row, 0, _ro_item(field.location))
            self._table.setItem(row, 1, _ro_item(field.value or "(비어있음)"))
            self._table.setItem(row, 2, _ro_item(_status_text(field)))

            if field.is_absolute:
                absolute_count += 1
                btn = QPushButton("assets로 복사")
                btn.clicked.connect(lambda _=False, f=field: self._copy_action(f))
                self._table.setCellWidget(row, 3, btn)
            else:
                self._table.removeCellWidget(row, 3)
                self._table.setItem(row, 3, _ro_item(""))

        self._pack_btn.setEnabled(absolute_count == 0)
        if absolute_count > 0:
            self._pack_btn.setToolTip(f"절대경로 {absolute_count}개를 먼저 처리하세요")
        else:
            self._pack_btn.setToolTip("")

    def _copy_action(self, field: PathField) -> None:
        target_dir = self._target_dir()
        if not target_dir.parent.exists() and not target_dir.exists():
            QMessageBox.warning(
                self,
                "디렉토리 없음",
                f"대상 디렉토리의 상위가 존재하지 않습니다:\n{target_dir}",
            )
            return
        try:
            new_value, _copied = relocate_to(field, target_dir)
        except FileNotFoundError as exc:
            QMessageBox.warning(self, "파일 없음", f"원본 파일이 없습니다:\n{exc}")
            return
        except ValueError as exc:
            QMessageBox.warning(self, "처리 불가", str(exc))
            return

        field.setter(new_value)
        self._refresh()


# ---------------------------------------------------------------------------
# 모듈 수준 도우미
# ---------------------------------------------------------------------------


def _ro_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


def _status_text(field: PathField) -> str:
    if not field.value:
        return "비어있음"
    if field.is_template:
        return "토큰"
    if field.is_absolute:
        return "절대경로"
    return "상대경로"
