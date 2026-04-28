"""변형(variations) 탭 — AI 본문 구성 변형 프로파일 관리.

DSL 형식::

    variations:
      blog_review:
        axes:
          intro:   ["장면 묘사로 시작", "독자 질문으로 시작"]
          body:    ["3가지 비교", "단계별 절차"]
          closing: ["체크리스트로 마무리"]
        template: |        # 선택. 생략 시 자동 포맷.

          [작성 지침]
          - 도입: {intro}
          - 본론: {body}
          - 마무리: {closing}

GUI 모델::

    {profile_name: {"axes": {axis: [values]}, "template": str|None}}
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QInputDialog, QSplitter, QPlainTextEdit,
    QFileDialog, QMessageBox,
)

from gui.excel_io import (
    export_variation_axes, import_variation_axes, template_variation_axes,
)


class VariationsTab(QWidget):

    def __init__(self) -> None:
        super().__init__()
        # {name: {"axes": {axis: [values]}, "template": str}}
        self._profiles: dict[str, dict] = {}
        self._updating = False

        # ── 좌측: 프로파일 목록 ──
        self._slug_list = QListWidget()
        self._slug_list.currentRowChanged.connect(self._on_slug_changed)

        btn_add = QPushButton("+ 프로파일 추가")
        btn_add.clicked.connect(self._add_slug)
        btn_remove = QPushButton("- 프로파일 삭제")
        btn_remove.clicked.connect(self._remove_slug)

        slug_btn_row = QHBoxLayout()
        slug_btn_row.addWidget(btn_add)
        slug_btn_row.addWidget(btn_remove)
        slug_btn_row.addStretch()

        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("변형 프로파일"))
        left_layout.addWidget(self._slug_list)
        left_layout.addLayout(slug_btn_row)
        left_widget = QWidget()
        left_widget.setLayout(left_layout)

        # ── 우측: axes 표 + template 에디터 ──
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["축 (axis)", "값 (값1, 값2, ...)"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.cellChanged.connect(self._on_cell_changed)

        btn_add_row = QPushButton("+ 축 추가")
        btn_add_row.clicked.connect(self._add_axis_row)
        btn_remove_row = QPushButton("- 축 삭제")
        btn_remove_row.clicked.connect(self._remove_axis_row)

        row_btn_row = QHBoxLayout()
        row_btn_row.addWidget(btn_add_row)
        row_btn_row.addWidget(btn_remove_row)
        row_btn_row.addStretch()

        # 엑셀 (axis, value 두 컬럼 long-format)
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

        axes_hint = QLabel(
            "각 축은 매 콤보마다 하나가 무작위로 선택됩니다. "
            "값은 콤마(,)로 구분 — 더 큰 풀은 엑셀로 가져오세요."
        )
        axes_hint.setStyleSheet("color: gray; font-size: 11px;")
        axes_hint.setWordWrap(True)

        self._template_edit = QPlainTextEdit()
        self._template_edit.setPlaceholderText(
            "(선택) 템플릿. 자리표시자 {축이름} 사용. 예:\n"
            "[작성 지침]\n- 도입: {intro}\n- 본론: {body}\n- 마무리: {closing}\n\n"
            "비워두면 자동 포맷 ('- 축이름: 값' 줄들)"
        )
        self._template_edit.setMinimumHeight(120)
        self._template_edit.textChanged.connect(self._on_template_changed)

        template_hint = QLabel(
            "템플릿 안 자리표시자 {축이름}은 axes에 정의된 축 이름이어야 합니다 "
            "(다른 DSL 토큰 {keyword:...} 등은 템플릿 내부에서는 해석되지 않음)."
        )
        template_hint.setStyleSheet("color: gray; font-size: 11px;")
        template_hint.setWordWrap(True)

        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("축 (axes)"))
        right_layout.addWidget(self._table)
        right_layout.addWidget(axes_hint)
        right_layout.addLayout(row_btn_row)
        right_layout.addLayout(excel_row)
        right_layout.addWidget(QLabel("템플릿 (template, 선택)"))
        right_layout.addWidget(self._template_edit)
        right_layout.addWidget(template_hint)
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

    # -- profile management --

    def _current_slug(self) -> str | None:
        item = self._slug_list.currentItem()
        return item.text() if item else None

    def _add_slug(self) -> None:
        slug, ok = QInputDialog.getText(self, "프로파일 추가", "프로파일 이름:")
        if not ok or not slug.strip():
            return
        slug = slug.strip()
        if slug in self._profiles:
            QMessageBox.warning(self, "중복", f"'{slug}' 프로파일이 이미 존재합니다.")
            return
        self._profiles[slug] = {"axes": {}, "template": ""}
        self._slug_list.addItem(slug)
        self._slug_list.setCurrentRow(self._slug_list.count() - 1)

    def _remove_slug(self) -> None:
        row = self._slug_list.currentRow()
        if row < 0:
            return
        slug = self._slug_list.item(row).text()
        self._profiles.pop(slug, None)
        self._slug_list.takeItem(row)

    def _on_slug_changed(self, _row: int) -> None:
        self._updating = True
        slug = self._current_slug()
        if slug and slug in self._profiles:
            entry = self._profiles[slug]
            self._load_axes(entry.get("axes", {}))
            self._template_edit.setPlainText(str(entry.get("template", "") or ""))
        else:
            self._table.setRowCount(0)
            self._template_edit.clear()
        self._updating = False

    # -- axes table --

    def _load_axes(self, axes: dict) -> None:
        self._table.setRowCount(0)
        for axis, vals in axes.items():
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(str(axis)))
            vals_str = ", ".join(str(v) for v in vals) if isinstance(vals, list) else str(vals)
            self._table.setItem(row, 1, QTableWidgetItem(vals_str))

    def _add_axis_row(self) -> None:
        if not self._current_slug():
            QMessageBox.information(self, "프로파일 선택", "먼저 좌측에서 프로파일을 선택하세요.")
            return
        axis, ok = QInputDialog.getText(self, "축 추가", "축 이름 (영숫자/_):")
        if ok and axis.strip():
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(axis.strip()))
            self._table.setItem(row, 1, QTableWidgetItem(""))

    def _remove_axis_row(self) -> None:
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)
            self._sync_axes_to_state()

    def _on_cell_changed(self, _row: int, _col: int) -> None:
        if self._updating:
            return
        self._sync_axes_to_state()

    def _on_template_changed(self) -> None:
        if self._updating:
            return
        slug = self._current_slug()
        if slug and slug in self._profiles:
            self._profiles[slug]["template"] = self._template_edit.toPlainText()

    def _sync_axes_to_state(self) -> None:
        slug = self._current_slug()
        if not slug or slug not in self._profiles:
            return
        axes: dict[str, list[str]] = {}
        for row in range(self._table.rowCount()):
            a_item = self._table.item(row, 0)
            v_item = self._table.item(row, 1)
            axis = a_item.text().strip() if a_item else ""
            vals_str = v_item.text().strip() if v_item else ""
            if not axis:
                continue
            vals = [v.strip() for v in vals_str.split(",") if v.strip()]
            if vals:
                axes[axis] = vals
        self._profiles[slug]["axes"] = axes

    # -- excel --

    def _on_import(self) -> None:
        slug = self._current_slug()
        if not slug:
            QMessageBox.information(self, "프로파일 선택", "먼저 좌측에서 프로파일을 선택하세요.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "변형 axes 엑셀 가져오기", "", "Excel (*.xlsx)",
        )
        if not path:
            return
        try:
            axes = import_variation_axes(path)
        except Exception as e:
            QMessageBox.critical(self, "엑셀 읽기 오류", str(e))
            return

        reply = QMessageBox.question(
            self, "가져오기 방식",
            "기존 axes 데이터에 추가하시겠습니까?\n\n예 = 추가 / 아니오 = 교체",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return

        if reply == QMessageBox.StandardButton.Yes:
            existing = self._profiles[slug].get("axes", {})
            for k, vs in axes.items():
                cur = existing.get(k, [])
                merged = list(cur)
                for v in vs:
                    if v not in merged:
                        merged.append(v)
                existing[k] = merged
            axes = existing

        self._profiles[slug]["axes"] = axes
        self._updating = True
        self._load_axes(axes)
        self._updating = False

    def _on_export(self) -> None:
        slug = self._current_slug()
        if not slug:
            return
        self._sync_axes_to_state()
        axes = self._profiles[slug].get("axes", {})
        if not axes:
            QMessageBox.information(self, "데이터 없음", f"'{slug}' 프로파일에 axes가 없습니다.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "변형 axes 엑셀 내보내기", f"{slug}.xlsx", "Excel (*.xlsx)",
        )
        if not path:
            return
        try:
            export_variation_axes(path, axes)
        except Exception as e:
            QMessageBox.critical(self, "엑셀 내보내기 오류", str(e))

    def _on_template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "변형 axes 엑셀 템플릿", "variations_template.xlsx", "Excel (*.xlsx)",
        )
        if not path:
            return
        try:
            template_variation_axes(path)
        except Exception as e:
            QMessageBox.critical(self, "템플릿 저장 오류", str(e))

    # -- (de)serialize --

    def to_dict(self) -> dict:
        self._sync_axes_to_state()
        out: dict = {}
        for slug, entry in self._profiles.items():
            axes = entry.get("axes") or {}
            template = (entry.get("template") or "").rstrip("\n")
            if not axes:
                continue
            profile: dict = {"axes": dict(axes)}
            if template:
                profile["template"] = template + "\n"  # YAML block style 호환성
            out[slug] = profile
        if not out:
            return {}
        return {"variations": out}

    def from_dict(self, data: dict) -> None:
        self._profiles.clear()
        self._slug_list.clear()
        variations = data.get("variations") or {}
        for slug, entry in variations.items():
            if not isinstance(entry, dict):
                continue
            axes_raw = entry.get("axes") or {}
            axes: dict[str, list[str]] = {}
            if isinstance(axes_raw, dict):
                for k, vs in axes_raw.items():
                    if isinstance(vs, list):
                        axes[str(k)] = [str(v) for v in vs]
            template = entry.get("template")
            self._profiles[str(slug)] = {
                "axes": axes,
                "template": str(template) if isinstance(template, str) else "",
            }
            self._slug_list.addItem(str(slug))
        if self._slug_list.count() > 0:
            self._slug_list.setCurrentRow(0)

    # -- token helpers (for token_insert in other tabs) --

    def variation_tokens(self) -> list[str]:
        """현재 정의된 프로파일·축으로부터 {variation:*} 토큰 목록 생성."""
        self._sync_axes_to_state()
        tokens: list[str] = []
        for slug, entry in self._profiles.items():
            tokens.append(f"{{variation:{slug}}}")
            for axis in (entry.get("axes") or {}).keys():
                tokens.append(f"{{variation:{slug}.{axis}}}")
        return tokens
