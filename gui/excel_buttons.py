"""
gui/excel_buttons.py
--------------------
각 탭에서 재사용하는 엑셀 가져오기 / 내보내기 / 템플릿 버튼 행.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QFileDialog, QMessageBox,
)


class ExcelButtonRow(QWidget):
    """엑셀 가져오기·내보내기·템플릿 버튼 3개를 제공하는 위젯.

    Parameters
    ----------
    parent : QWidget
    label : str            — 섹션 이름 (예: "계정", "키워드")
    default_filename : str — 저장 다이얼로그 기본 파일명
    import_fn : callable(path) -> data  — 엑셀 읽기 함수
    export_fn : callable(path, data)    — 엑셀 쓰기 ���수
    template_fn : callable(path)        — 빈 템플릿 생성 함수
    get_data : callable() -> data       — 현재 탭 데이터 조회
    set_data : callable(data, append)   — 탭에 데이터 적용
    """

    def __init__(
        self,
        parent: QWidget,
        *,
        label: str,
        default_filename: str,
        import_fn,
        export_fn,
        template_fn,
        get_data,
        set_data,
    ) -> None:
        super().__init__(parent)
        self._label = label
        self._default_filename = default_filename
        self._import_fn = import_fn
        self._export_fn = export_fn
        self._template_fn = template_fn
        self._get_data = get_data
        self._set_data = set_data

        btn_import = QPushButton(f"엑셀 가져오기")
        btn_import.clicked.connect(self._on_import)
        btn_export = QPushButton(f"엑셀 내보내기")
        btn_export.clicked.connect(self._on_export)
        btn_template = QPushButton(f"엑셀 템플릿")
        btn_template.clicked.connect(self._on_template)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(btn_import)
        row.addWidget(btn_export)
        row.addWidget(btn_template)
        row.addStretch()
        self.setLayout(row)

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, f"{self._label} 엑셀 가져오기", "", "Excel 파일 (*.xlsx)",
        )
        if not path:
            return
        try:
            data = self._import_fn(path)
        except Exception as e:
            QMessageBox.critical(self, "엑셀 읽기 오류", str(e))
            return

        reply = QMessageBox.question(
            self,
            "가져오기 방식",
            "기존 데이터에 추가하시겠습니까?\n\n"
            "예 → 기존 데이터 유지 + 추가\n"
            "아니오 → 기존 데이터 삭제 후 교체",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return
        self._set_data(data, append=(reply == QMessageBox.StandardButton.Yes))

    def _on_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, f"{self._label} 엑셀 내보내기", self._default_filename, "Excel 파일 (*.xlsx)",
        )
        if not path:
            return
        try:
            self._export_fn(path, self._get_data())
        except Exception as e:
            QMessageBox.critical(self, "엑셀 내보내기 오류", str(e))

    def _on_template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, f"{self._label} 엑셀 템플릿 저장",
            f"{self._default_filename.replace('.xlsx', '')}_template.xlsx",
            "Excel 파일 (*.xlsx)",
        )
        if not path:
            return
        try:
            self._template_fn(path)
        except Exception as e:
            QMessageBox.critical(self, "템플릿 저장 오류", str(e))
