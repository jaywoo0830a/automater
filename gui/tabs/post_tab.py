"""포스트 블록 탭 — 블록 추가/편집/삭제/순서 변경."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QComboBox, QListWidget, QListWidgetItem, QInputDialog,
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
    QLabel, QDoubleSpinBox, QSpinBox, QCheckBox,
)


_BLOCK_TYPES = [
    ("소제목 (H1)", "h1"), ("소제목 (H2)", "h2"), ("소제목 (H3)", "h3"),
    ("소제목 (H4)", "h4"), ("소제목 (H5)", "h5"), ("소제목 (H6)", "h6"),
    ("본문 단락", "paragraph"),
    ("본문 이미지", "image"),
    ("대표 이미지", "featured_image"),
    ("인용구", "quote"),
    ("목록", "list"),
    ("구분선", "divider"),
]


class PostTab(QWidget):

    def __init__(self) -> None:
        super().__init__()

        self._list = QListWidget()
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)

        self._type_combo = QComboBox()
        for label, _ in _BLOCK_TYPES:
            self._type_combo.addItem(label)

        btn_add = QPushButton("+ 블록 추가")
        btn_add.clicked.connect(self._add_block)
        btn_edit = QPushButton("수정")
        btn_edit.clicked.connect(self._edit_block)
        btn_remove = QPushButton("- 삭제")
        btn_remove.clicked.connect(self._remove_block)
        btn_up = QPushButton("▲ 위로")
        btn_up.clicked.connect(self._move_up)
        btn_down = QPushButton("▼ 아래로")
        btn_down.clicked.connect(self._move_down)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("블록 타입:"))
        top_row.addWidget(self._type_combo)
        top_row.addWidget(btn_add)

        bottom_row = QHBoxLayout()
        bottom_row.addWidget(btn_edit)
        bottom_row.addWidget(btn_remove)
        bottom_row.addStretch()
        bottom_row.addWidget(btn_up)
        bottom_row.addWidget(btn_down)

        layout = QVBoxLayout()
        layout.addLayout(top_row)
        layout.addWidget(self._list)
        layout.addLayout(bottom_row)
        self.setLayout(layout)

    # ------------------------------------------------------------------

    def _selected_block_type(self) -> str:
        idx = self._type_combo.currentIndex()
        return _BLOCK_TYPES[idx][1]

    def _add_block(self) -> None:
        bt = self._selected_block_type()

        if bt == "divider":
            self._append({"divider": None})
            return

        if bt.startswith("h") and bt[1:].isdigit():
            text, ok = QInputDialog.getText(self, "소제목 추가", "소제목 텍스트:")
            if ok and text.strip():
                self._append({bt: text.strip()})
            return

        if bt == "paragraph":
            text, ok = QInputDialog.getMultiLineText(
                self, "본문 단락 추가", "AI 프롬프트:",
                "{keyword:region} {keyword:subject} 과외를 소개해줘",
            )
            if ok and text.strip():
                self._append({"paragraph": text.strip()})
            return

        if bt == "quote":
            dlg = _QuoteDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._append(dlg.result())
            return

        if bt == "list":
            text, ok = QInputDialog.getMultiLineText(
                self, "목록 추가", "항목 (한 줄에 하나):", "항목 1\n항목 2\n항목 3"
            )
            if ok and text.strip():
                items = [line.strip() for line in text.splitlines() if line.strip()]
                self._append({"list": items})
            return

        if bt in ("image", "featured_image"):
            dlg = _ImageDialog(self, bt)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._append(dlg.result())
            return

    def _edit_block(self) -> None:
        item = self._list.currentItem()
        if not item:
            return
        block = item.data(256)
        if not isinstance(block, dict):
            return

        bt = next(iter(block), "")
        val = block[bt]

        if bt in ("paragraph",) + tuple(f"h{i}" for i in range(1, 7)):
            current = val if isinstance(val, str) else ""
            if bt == "paragraph":
                text, ok = QInputDialog.getMultiLineText(self, "본문 수정", "AI 프롬프트:", current)
            else:
                text, ok = QInputDialog.getText(self, "소제목 수정", "텍스트:", text=current)
            if ok and text.strip():
                new = {bt: text.strip()}
                item.setData(256, new)
                item.setText(self._label(new))

    def _remove_block(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)

    def _move_up(self) -> None:
        row = self._list.currentRow()
        if row > 0:
            item = self._list.takeItem(row)
            self._list.insertItem(row - 1, item)
            self._list.setCurrentRow(row - 1)

    def _move_down(self) -> None:
        row = self._list.currentRow()
        if row < self._list.count() - 1:
            item = self._list.takeItem(row)
            self._list.insertItem(row + 1, item)
            self._list.setCurrentRow(row + 1)

    # ------------------------------------------------------------------

    def _append(self, block: dict) -> None:
        item = QListWidgetItem(self._label(block))
        item.setData(256, block)
        self._list.addItem(item)

    @staticmethod
    def _label(block: dict) -> str:
        if block.get("divider") is None and "divider" in block:
            return "─────── 구분선 ───────"
        bt = next(iter(block))
        val = block[bt]
        if isinstance(val, str):
            short = val[:50] + "…" if len(val) > 50 else val
            return f"[{bt}]  {short}"
        if isinstance(val, list):
            return f"[{bt}]  {', '.join(str(v) for v in val[:3])}…"
        if isinstance(val, dict):
            path = val.get("path", "")
            overlay = val.get("overlay_text", "")
            detail = overlay or path
            return f"[{bt}]  {detail}"
        return str(block)

    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        blocks = []
        for i in range(self._list.count()):
            block = self._list.item(i).data(256)
            if isinstance(block, dict) and block.get("divider") is None and "divider" in block:
                blocks.append("divider")
            else:
                blocks.append(block)
        return {"post": blocks} if blocks else {}

    def from_dict(self, data: dict) -> None:
        self._list.clear()
        for entry in data.get("post", []):
            if entry == "divider" or entry is None:
                self._append({"divider": None})
            elif isinstance(entry, dict):
                self._append(entry)
            elif isinstance(entry, str):
                self._append({"divider": None} if entry == "divider" else {"paragraph": entry})


# ======================================================================
# Dialogs
# ======================================================================

class _QuoteDialog(QDialog):

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("인용구 추가")

        self._text = QLineEdit()
        self._text.setPlaceholderText("인용문 텍스트")
        self._attribution = QLineEdit()
        self._attribution.setPlaceholderText("출처 (선택)")

        form = QFormLayout()
        form.addRow("인용문:", self._text)
        form.addRow("출처:", self._attribution)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def result(self) -> dict:
        text = self._text.text().strip()
        attr = self._attribution.text().strip()
        if attr:
            return {"quote": {"text": text, "attribution": attr}}
        return {"quote": text}


class _ImageDialog(QDialog):

    def __init__(self, parent: QWidget, block_type: str) -> None:
        super().__init__(parent)
        is_featured = block_type == "featured_image"
        self.setWindowTitle("대표 이미지 추가" if is_featured else "본문 이미지 추가")
        self._block_type = block_type

        self._path = QLineEdit()
        self._path.setPlaceholderText("photo.jpg 또는 {map:photo}")
        self._link = QLineEdit()
        self._link.setPlaceholderText("tel:01012345678 또는 https://…")
        self._alt = QLineEdit()
        self._alt.setPlaceholderText("대체 텍스트")

        form = QFormLayout()
        form.addRow("파일 경로:", self._path)
        form.addRow("링크:", self._link)
        if not is_featured:
            form.addRow("대체 텍스트:", self._alt)

        if is_featured:
            self._overlay_text = QLineEdit()
            self._overlay_text.setPlaceholderText("{keyword:region} 과외")

            self._overlay_color = QLineEdit("#FFFFFF")

            self._overlay_bg = QDoubleSpinBox()
            self._overlay_bg.setRange(0.0, 1.0)
            self._overlay_bg.setSingleStep(0.1)
            self._overlay_bg.setValue(0.0)

            self._overlay_pos = QComboBox()
            self._overlay_pos.addItems(["center", "top", "bottom"])

            form.addRow("오버레이 텍스트:", self._overlay_text)
            form.addRow("텍스트 색상:", self._overlay_color)
            form.addRow("배경 불투명도:", self._overlay_bg)
            form.addRow("텍스트 위치:", self._overlay_pos)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def result(self) -> dict:
        cfg: dict = {}
        path = self._path.text().strip()
        if path:
            cfg["path"] = path
        link = self._link.text().strip()
        if link:
            cfg["link"] = link
        alt = self._alt.text().strip()
        if alt and self._block_type == "image":
            cfg["alt"] = alt

        if self._block_type == "featured_image":
            ot = self._overlay_text.text().strip()
            if ot:
                cfg["overlay_text"] = ot
            oc = self._overlay_color.text().strip()
            if oc and oc != "#FFFFFF":
                cfg["overlay_color"] = oc
            ob = self._overlay_bg.value()
            if ob > 0.0:
                cfg["overlay_background"] = ob
            op = self._overlay_pos.currentText()
            if op != "center":
                cfg["overlay_position"] = op
        if len(cfg) == 1 and "path" in cfg:
            return {self._block_type: cfg["path"]}
        return {self._block_type: cfg}
