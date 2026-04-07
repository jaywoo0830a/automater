"""포스트 블록 탭 - 블록 추가/편집/삭제/순서 변경."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QComboBox, QListWidget, QListWidgetItem, QInputDialog,
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
    QLabel, QDoubleSpinBox, QSpinBox, QCheckBox, QTextEdit,
    QGroupBox, QFileDialog, QMessageBox,
)

from typing import Callable

from gui.collapsible import CollapsibleSection
from gui.token_insert import TokenInsertButton


_BLOCK_TYPES = [
    ("소제목 (H1)", "h1"), ("소제목 (H2)", "h2"), ("소제목 (H3)", "h3"),
    ("소제목 (H4)", "h4"), ("소제목 (H5)", "h5"), ("소제목 (H6)", "h6"),
    ("AI 단락", "paragraph"),
    ("AI 섹션 (구조화)", "ai_section"),
    ("수동 텍스트", "text"),
    ("본문 이미지", "image"),
    ("대표 이미지", "featured_image"),
    ("인용구", "quote"),
    ("목록", "list"),
    ("구분선", "divider"),
    ("줄바꿈", "newline"),
]


class PostTab(QWidget):

    def __init__(self) -> None:
        super().__init__()
        self._token_source: Callable[[], list[str]] = lambda: []

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
        btn_up = QPushButton("Up")
        btn_up.clicked.connect(self._move_up)
        btn_down = QPushButton("Down")
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

    def set_token_source(self, fn: Callable[[], list[str]]) -> None:
        self._token_source = fn

    # ------------------------------------------------------------------

    def _selected_block_type(self) -> str:
        idx = self._type_combo.currentIndex()
        return _BLOCK_TYPES[idx][1]

    def _add_block(self) -> None:
        bt = self._selected_block_type()

        if bt == "divider":
            dlg = _DividerDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._append(dlg.result())
            return

        if bt == "newline":
            dlg = _NewLineDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._append(dlg.result())
            return

        if bt.startswith("h") and bt[1:].isdigit():
            dlg = _SimpleTextDialog(self, "소제목 추가", "텍스트:", bt,
                                    token_source=self._token_source)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._append(dlg.result())
            return

        if bt == "paragraph":
            dlg = _SimpleTextDialog(self, "AI 단락 추가", "프롬프트:", "paragraph",
                                    multiline=True,
                                    default="{keyword:region} {keyword:subject} 과외를 소개해줘",
                                    token_source=self._token_source)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._append(dlg.result())
            return

        if bt == "text":
            dlg = _TextBlockDialog(self, token_source=self._token_source)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._append(dlg.result())
            return

        if bt == "quote":
            dlg = _QuoteDialog(self, token_source=self._token_source)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._append(dlg.result())
            return

        if bt == "list":
            dlg = _ListDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._append(dlg.result())
            return

        if bt in ("image", "featured_image"):
            dlg = _ImageDialog(self, bt, token_source=self._token_source)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._append(dlg.result())
            return

        if bt == "ai_section":
            dlg = _AiSectionDialog(self, token_source=self._token_source)
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
        when = block.get("when", "")
        wait = block.get("wait", "")

        dlg = None

        # 소제목
        if bt.startswith("h") and bt[1:].isdigit():
            current = val if isinstance(val, str) else ""
            dlg = _SimpleTextDialog(
                self, "소제목 수정", "텍스트:", bt,
                default=current, when_default=when, wait_default=wait,
                token_source=self._token_source,
            )

        # AI 단락
        elif bt == "paragraph":
            current = val if isinstance(val, str) else ""
            dlg = _SimpleTextDialog(
                self, "AI 단락 수정", "프롬프트:", "paragraph",
                multiline=True, default=current,
                when_default=when, wait_default=wait,
                token_source=self._token_source,
            )

        # 수동 텍스트
        elif bt == "text":
            dlg = _TextBlockDialog(
                self, token_source=self._token_source,
                existing=block,
            )

        # 인용구
        elif bt == "quote":
            dlg = _QuoteDialog(
                self, token_source=self._token_source,
                existing=block,
            )

        # 목록
        elif bt == "list":
            dlg = _ListDialog(self, existing=block)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                new = dlg.result()
                item.setData(256, new)
                item.setText(self._label(new))
            return

        # 이미지
        elif bt in ("image", "featured_image"):
            dlg = _ImageDialog(
                self, bt, token_source=self._token_source,
                existing=block,
            )

        # divider - when/wait 편집
        elif bt == "divider":
            dlg = _DividerDialog(self, existing=block)

        # 줄바꿈
        elif bt == "newline":
            dlg = _NewLineDialog(self, existing=block)

        # AI 섹션
        elif bt == "ai_section":
            dlg = _AiSectionDialog(
                self, token_source=self._token_source,
                existing=block,
            )

        if dlg is None:
            return

        if dlg.exec() == QDialog.DialogCode.Accepted:
            new = dlg.result()
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
        # divider 특수 처리 — type 표시
        if "divider" in block:
            val = block["divider"]
            if val is None:
                return "------- 구분선 (type 2) -------"
            if isinstance(val, int):
                return f"------- 구분선 (type {val}) -------"
            if isinstance(val, dict):
                t = val.get("type", 2)
                return f"------- 구분선 (type {t}) -------"

        bt = next(iter(block))
        val = block[bt]

        # ai_section 특수 처리 — structure 요약 표시
        if bt == "ai_section" and isinstance(val, dict):
            prompt = str(val.get("prompt", ""))
            structure = val.get("structure", []) or []
            short = prompt[:40] + "..." if len(prompt) > 40 else prompt
            struct_str = "→".join(str(s) for s in structure[:5])
            return f"[ai_section:{struct_str}]  {short}"

        # quote 특수 처리 — type 표시
        if bt == "quote" and isinstance(val, dict):
            text = str(val.get("text", ""))
            t = val.get("type", 1)
            short = text[:50] + "..." if len(text) > 50 else text
            return f"[{bt}:type{t}]  {short}"

        if isinstance(val, int):
            return f"[{bt}]  {val}"
        if isinstance(val, str):
            short = val[:50] + "..." if len(val) > 50 else val
            return f"[{bt}]  {short}"
        if isinstance(val, list):
            return f"[{bt}]  {', '.join(str(v) for v in val[:3])}..."
        if isinstance(val, dict):
            # list dict form
            if bt == "list":
                items = val.get("items", [])
                ordered = "번호" if val.get("ordered") else "기호"
                return f"[{bt}:{ordered}]  {', '.join(str(v) for v in items[:3])}..."
            path = val.get("path", "")
            overlay = val.get("overlay_text", "")
            file_ = val.get("file", "")
            detail = overlay or path or file_
            return f"[{bt}]  {detail}"
        return str(block)

    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        blocks = []
        for i in range(self._list.count()):
            block = self._list.item(i).data(256)
            # divider 단축 형식 처리:
            #   {divider: None}              → "divider"  (기본 type=2)
            #   {divider: 5}                 → {divider: 5}  (단축 숫자)
            #   {divider: 5, when/wait}      → {divider: 5, ...}
            #   {divider: {type: 5}}         → {divider: {type: 5}}
            if isinstance(block, dict) and "divider" in block:
                val = block.get("divider")
                extra_keys = {k for k in block if k != "divider"}
                if val is None and not extra_keys:
                    blocks.append("divider")
                else:
                    blocks.append(block)
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

class _SimpleTextDialog(QDialog):
    """소제목, paragraph 등 단일 텍스트 + when/wait 고급 설정."""

    def __init__(self, parent: QWidget, title: str, label: str, block_type: str,
                 multiline: bool = False, default: str = "",
                 when_default: str = "", wait_default: str = "",
                 token_source: Callable | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(500)
        self._block_type = block_type
        self._multiline = multiline
        self._text_edit: QTextEdit | None = None
        self._text_line: QLineEdit | None = None

        text_widget: QWidget
        if multiline:
            self._text_edit = QTextEdit()
            self._text_edit.setPlainText(default)
            self._text_edit.setMaximumHeight(100)
            text_widget = self._text_edit
        else:
            self._text_line = QLineEdit(default)
            text_widget = self._text_line

        token_btn = TokenInsertButton(text_widget, token_source or (lambda: []))

        input_row = QHBoxLayout()
        input_row.addWidget(text_widget)
        input_row.addWidget(token_btn)

        form = QFormLayout()
        form.addRow(label, input_row)

        # 고급
        self._when = QLineEdit(when_default)
        self._when.setPlaceholderText('{keyword:region} == 강남')
        self._wait = QLineEdit(wait_default)
        self._wait.setPlaceholderText("2s 또는 1s ~ 3s")

        advanced = CollapsibleSection("고급 설정")
        advanced.add_row("조건 (when):", self._when)
        advanced.add_row("대기 (wait):", self._wait)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(advanced)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def result(self) -> dict:
        if self._text_edit is not None:
            text = self._text_edit.toPlainText().strip()
        elif self._text_line is not None:
            text = self._text_line.text().strip()
        else:
            text = ""

        entry: dict = {self._block_type: text}

        when = self._when.text().strip()
        if when:
            entry["when"] = when
        wait = self._wait.text().strip()
        if wait:
            entry["wait"] = wait

        return entry


class _TextBlockDialog(QDialog):
    """수동 텍스트 블록 - 인라인 또는 파일 모드."""

    def __init__(self, parent: QWidget, token_source: Callable | None = None,
                 existing: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("수동 텍스트 수정" if existing else "수동 텍스트 추가")
        self.setMinimumWidth(500)

        # 기존 값 파싱
        _raw_val = (existing or {}).get("text", "")
        _when: str = str((existing or {}).get("when", ""))
        _wait_entry: str = str((existing or {}).get("wait", ""))
        if isinstance(_raw_val, dict):
            _inline_default = ""
            _file_default = str(_raw_val.get("file", ""))
            _format_default = str(_raw_val.get("format", "plain"))
            _wait_inner = str(_raw_val.get("wait", ""))
        else:
            _inline_default = str(_raw_val) if _raw_val else ""
            _file_default = ""
            _format_default = "plain"
            _wait_inner = ""
        _wait_default = str(_wait_entry or _wait_inner)

        self._inline = QTextEdit()
        self._inline.setPlaceholderText("{keyword:region} 중등 수학학원은 대표 전문 학원입니다.")
        self._inline.setMaximumHeight(100)
        if _inline_default:
            self._inline.setPlainText(_inline_default)

        token_btn_inline = TokenInsertButton(self._inline, token_source or (lambda: []))

        self._file = QLineEdit(_file_default)
        self._file.setPlaceholderText("{i}.txt 또는 {keyword:region}/{i}.txt")
        token_btn_file = TokenInsertButton(self._file, token_source or (lambda: []))
        self._format = QComboBox()
        self._format.addItems(["plain", "html"])
        idx = self._format.findText(_format_default)
        if idx >= 0:
            self._format.setCurrentIndex(idx)

        inline_row = QHBoxLayout()
        inline_row.addWidget(self._inline)
        inline_row.addWidget(token_btn_inline)
        inline_widget = QWidget()
        inline_widget.setLayout(inline_row)

        file_row = QHBoxLayout()
        file_row.addWidget(self._file)
        file_row.addWidget(token_btn_file)
        file_widget = QWidget()
        file_widget.setLayout(file_row)

        form = QFormLayout()
        form.addRow("인라인 텍스트:", inline_widget)

        file_form = QFormLayout()
        file_form.addRow("파일 경로:", file_widget)
        file_form.addRow("포맷:", self._format)
        file_group = QGroupBox("또는 파일에서 읽기")
        file_group.setLayout(file_form)

        hint = QLabel("인라인 텍스트가 있으면 우선 사용. 비어있으면 파일에서 읽기.")
        hint.setStyleSheet("color: gray; font-size: 11px;")

        # 고급
        self._when = QLineEdit(_when)
        self._when.setPlaceholderText('{keyword:region} == 강남')
        self._wait = QLineEdit(_wait_default)
        self._wait.setPlaceholderText("2s 또는 1s ~ 3s")

        advanced = CollapsibleSection("고급 설정")
        advanced.add_row("조건 (when):", self._when)
        advanced.add_row("대기 (wait):", self._wait)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        # QTextEdit에서 Enter 키가 개행 대신 OK 버튼을 트리거하지 않도록 설정
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setAutoDefault(False)
            ok_btn.setDefault(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(file_group)
        layout.addWidget(hint)
        layout.addWidget(advanced)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def result(self) -> dict:
        inline = self._inline.toPlainText().strip()
        file_ = self._file.text().strip()

        if inline:
            entry: dict = {"text": inline}
        elif file_:
            cfg: dict = {"file": file_}
            fmt = self._format.currentText()
            if fmt != "plain":
                cfg["format"] = fmt
            wait = self._wait.text().strip()
            if wait:
                cfg["wait"] = wait
            entry = {"text": cfg}
        else:
            entry = {"text": ""}

        when = self._when.text().strip()
        if when:
            entry["when"] = when
        # wait for inline mode (entry-level)
        if inline:
            wait = self._wait.text().strip()
            if wait:
                entry["wait"] = wait

        return entry


class _QuoteDialog(QDialog):

    def __init__(self, parent: QWidget, token_source: Callable | None = None,
                 existing: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("인용구 수정" if existing else "인용구 추가")
        self.setMinimumWidth(500)

        _raw_val = (existing or {}).get("quote", "")
        if isinstance(_raw_val, dict):
            _text_default = str(_raw_val.get("text", ""))
            _attr_default = str(_raw_val.get("attribution", ""))
            _type_default = int(_raw_val.get("type", 1)) if _raw_val.get("type") else 1
        else:
            _text_default = str(_raw_val) if _raw_val else ""
            _attr_default = ""
            _type_default = 1
        _when: str = str((existing or {}).get("when", ""))
        _wait: str = str((existing or {}).get("wait", ""))

        self._text = QLineEdit(_text_default)
        self._text.setPlaceholderText("인용문 텍스트")
        token_btn = TokenInsertButton(self._text, token_source or (lambda: []))
        self._attribution = QLineEdit(_attr_default)
        self._attribution.setPlaceholderText("출처 (선택)")

        # 인용구 스타일 (1~6, 기본 1)
        self._type = QSpinBox()
        self._type.setRange(1, 6)
        self._type.setValue(_type_default)
        self._type.setToolTip("네이버 SE 인용구 스타일 1~6 (기본 1)")

        text_row = QHBoxLayout()
        text_row.addWidget(self._text)
        text_row.addWidget(token_btn)

        form = QFormLayout()
        form.addRow("인용문:", text_row)
        form.addRow("출처:", self._attribution)
        form.addRow("스타일:", self._type)

        # 고급
        self._when = QLineEdit(str(_when))
        self._when.setPlaceholderText('{keyword:region} == 강남')
        self._wait = QLineEdit(str(_wait) if _wait else "")
        self._wait.setPlaceholderText("2s 또는 1s ~ 3s")

        advanced = CollapsibleSection("고급 설정")
        advanced.add_row("조건 (when):", self._when)
        advanced.add_row("대기 (wait):", self._wait)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(advanced)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def result(self) -> dict:
        text = self._text.text().strip()
        attr = self._attribution.text().strip()
        qtype = int(self._type.value())

        # type이 기본값(1)이 아니거나 attribution이 있으면 dict 형식
        if attr or qtype != 1:
            quote_dict: dict = {"text": text}
            if attr:
                quote_dict["attribution"] = attr
            if qtype != 1:
                quote_dict["type"] = qtype
            entry: dict = {"quote": quote_dict}
        else:
            entry = {"quote": text}

        when = self._when.text().strip()
        if when:
            entry["when"] = when
        wait = self._wait.text().strip()
        if wait:
            entry["wait"] = wait
        return entry


class _ListDialog(QDialog):
    """목록 블록 — 항목 + ordered 옵션 + when/wait."""

    def __init__(self, parent: QWidget, existing: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("목록 수정" if existing else "목록 추가")
        self.setMinimumWidth(500)

        _raw_val = (existing or {}).get("list", [])
        if isinstance(_raw_val, dict):
            _items = _raw_val.get("items", [])
            _ordered = bool(_raw_val.get("ordered", False))
        elif isinstance(_raw_val, list):
            _items = _raw_val
            _ordered = False
        else:
            _items = []
            _ordered = False
        _when: str = str((existing or {}).get("when", ""))
        _wait: str = str((existing or {}).get("wait", ""))

        self._items = QTextEdit()
        self._items.setPlaceholderText("항목 1\n항목 2\n항목 3")
        self._items.setMaximumHeight(120)
        if _items:
            self._items.setPlainText("\n".join(str(i) for i in _items))

        self._ordered = QCheckBox("번호 매기기 (ordered)")
        self._ordered.setChecked(_ordered)

        form = QFormLayout()
        form.addRow("항목 (한 줄에 하나):", self._items)
        form.addRow("", self._ordered)

        # 고급
        self._when = QLineEdit(_when)
        self._when.setPlaceholderText('{keyword:region} == 강남')
        self._wait = QLineEdit(_wait)
        self._wait.setPlaceholderText("2s 또는 1s ~ 3s")

        advanced = CollapsibleSection("고급 설정")
        advanced.add_row("조건 (when):", self._when)
        advanced.add_row("대기 (wait):", self._wait)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setAutoDefault(False)
            ok_btn.setDefault(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(advanced)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def result(self) -> dict:
        raw = self._items.toPlainText().strip()
        items = [line.strip() for line in raw.splitlines() if line.strip()]
        ordered = self._ordered.isChecked()

        if ordered:
            entry: dict = {"list": {"items": items, "ordered": True}}
        else:
            entry = {"list": items}

        when = self._when.text().strip()
        if when:
            entry["when"] = when
        wait = self._wait.text().strip()
        if wait:
            entry["wait"] = wait
        return entry


class _NewLineDialog(QDialog):
    """줄바꿈 설정 -- count + when/wait."""

    def __init__(self, parent: QWidget, existing: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("줄바꿈 설정")
        self.setMinimumWidth(400)

        _count = int((existing or {}).get("newline", 1) or 1)
        _when: str = str((existing or {}).get("when", ""))
        _wait: str = str((existing or {}).get("wait", ""))

        self._count = QSpinBox()
        self._count.setRange(1, 50)
        self._count.setValue(_count)

        self._when = QLineEdit(_when)
        self._when.setPlaceholderText('{keyword:region} == 강남')
        self._wait = QLineEdit(_wait)
        self._wait.setPlaceholderText("2s 또는 1s ~ 3s")

        form = QFormLayout()
        form.addRow("줄바꿈 횟수:", self._count)

        advanced = CollapsibleSection("고급 설정")
        advanced.add_row("조건 (when):", self._when)
        advanced.add_row("대기 (wait):", self._wait)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(advanced)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def result(self) -> dict:
        entry: dict = {"newline": self._count.value()}
        when = self._when.text().strip()
        if when:
            entry["when"] = when
        wait = self._wait.text().strip()
        if wait:
            entry["wait"] = wait
        return entry


class _ImageDialog(QDialog):

    def __init__(self, parent: QWidget, block_type: str,
                 token_source: Callable | None = None,
                 existing: dict | None = None) -> None:
        super().__init__(parent)
        is_featured = block_type == "featured_image"
        self.setWindowTitle("이미지 수정" if existing else ("대표 이미지 추가" if is_featured else "본문 이미지 추가"))
        self.setMinimumWidth(500)
        self._block_type = block_type
        ts = token_source or (lambda: [])

        # 기존 값 파싱
        _raw = (existing or {}).get(block_type, {})
        _val: dict = {"path": _raw} if isinstance(_raw, str) else (_raw if isinstance(_raw, dict) else {})
        _e_when: str = str((existing or {}).get("when", ""))

        # 기본 필드
        self._path = QLineEdit(str(_val.get("path", "")))
        self._path.setPlaceholderText("photo.jpg 또는 {map:photo}")
        token_btn_path = TokenInsertButton(self._path, ts)
        btn_browse = QPushButton("...")
        btn_browse.setFixedWidth(30)
        btn_browse.clicked.connect(self._browse_file)

        self._link = QLineEdit(str(_val.get("link", "")))
        self._link.setPlaceholderText("tel:01012345678 또는 https://...")
        token_btn_link = TokenInsertButton(self._link, ts)

        path_row = QHBoxLayout()
        path_row.addWidget(self._path)
        path_row.addWidget(token_btn_path)
        path_row.addWidget(btn_browse)

        link_row = QHBoxLayout()
        link_row.addWidget(self._link)
        link_row.addWidget(token_btn_link)

        form = QFormLayout()
        form.addRow("파일 경로:", path_row)
        form.addRow("링크:", link_row)

        if not is_featured:
            self._alt = QLineEdit(str(_val.get("alt", "")))
            self._alt.setPlaceholderText("대체 텍스트")
            form.addRow("대체 텍스트:", self._alt)
        else:
            self._alt = None

        # 오버레이 (featured_image 전용)
        if is_featured:
            self._overlay_text = QLineEdit(str(_val.get("overlay_text", "")))
            self._overlay_text.setPlaceholderText("{keyword:region} 과외")
            token_btn_overlay = TokenInsertButton(self._overlay_text, ts)

            overlay_row = QHBoxLayout()
            overlay_row.addWidget(self._overlay_text)
            overlay_row.addWidget(token_btn_overlay)

            self._overlay_color = QLineEdit(str(_val.get("overlay_color", "#FFFFFF")))
            self._overlay_bg = QDoubleSpinBox()
            self._overlay_bg.setRange(0.0, 1.0)
            self._overlay_bg.setSingleStep(0.1)
            self._overlay_bg.setValue(float(_val.get("overlay_background", 0.0)))
            self._overlay_pos = QComboBox()
            self._overlay_pos.addItems(["center", "top", "bottom"])
            _pos = str(_val.get("overlay_position", "center"))
            _pos_idx = self._overlay_pos.findText(_pos)
            if _pos_idx >= 0:
                self._overlay_pos.setCurrentIndex(_pos_idx)

            form.addRow("오버레이 텍스트:", overlay_row)
            form.addRow("텍스트 색상:", self._overlay_color)
            form.addRow("배경 불투명도:", self._overlay_bg)
            form.addRow("텍스트 위치:", self._overlay_pos)

        # 고급 1: when / wait / effects
        self._when = QLineEdit(str(_e_when))
        self._when.setPlaceholderText('{keyword:region} in [강남, 서초]')
        self._wait = QLineEdit(str(_val.get("wait", "")))
        self._wait.setPlaceholderText("2s 또는 1s ~ 3s")
        self._effects = QTextEdit()
        self._effects.setPlaceholderText(
            "한 줄에 하나씩 (region | effect):\n"
            "border:10 ~ 30 | brightness:0.3 ~ 0.7\n"
            "all | hue:0.0 ~ 0.03"
        )
        self._effects.setMaximumHeight(80)
        # 기존 effects 로드
        _existing_effects = _val.get("effects") or []
        if _existing_effects:
            lines = []
            for fx in _existing_effects:
                region = fx.get("region", "all")
                effect = fx.get("effect", "")
                if region and region != "all":
                    lines.append(f"{region} | {effect}")
                else:
                    lines.append(effect)
            self._effects.setPlainText("\n".join(lines))

        advanced1 = CollapsibleSection("조건 / 대기 / 효과")
        advanced1.add_row("조건 (when):", self._when)
        advanced1.add_row("대기 (wait):", self._wait)
        advanced1.add_row("효과 (effects):", self._effects)

        # 고급 2: GPS / EXIF / 파일명
        _gps = _val.get("gps", [])
        self._gps_lat = QLineEdit(str(_gps[0]) if isinstance(_gps, (list, tuple)) and len(_gps) >= 2 else "")
        self._gps_lat.setPlaceholderText("37.497")
        self._gps_lng = QLineEdit(str(_gps[1]) if isinstance(_gps, (list, tuple)) and len(_gps) >= 2 else "")
        self._gps_lng.setPlaceholderText("127.027")
        self._filename_kw = QLineEdit(str(_val.get("filename_keyword", "")))
        self._filename_kw.setPlaceholderText("gangnam-tutor")
        self._exif_desc = QLineEdit(str(_val.get("exif_description", "")))
        self._exif_desc.setPlaceholderText("ASCII 설명 (선택)")

        advanced2 = CollapsibleSection("GPS / EXIF / 파일명")
        advanced2.add_row("위도:", self._gps_lat)
        advanced2.add_row("경도:", self._gps_lng)
        advanced2.add_row("파일명 키워드:", self._filename_kw)
        advanced2.add_row("EXIF 설명:", self._exif_desc)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(advanced1)
        layout.addWidget(advanced2)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _on_accept(self) -> None:
        """OK 버튼 핸들러 — path 유효성 검증 후에만 accept."""
        path = self._path.text().strip()
        label = "대표 이미지" if self._block_type == "featured_image" else "본문 이미지"

        if not path or path == ".":
            QMessageBox.warning(
                self,
                "경로 필수",
                f"{label} 블록은 'path' 필드가 필수입니다.\n\n"
                f"파일 경로를 입력하거나 '...' 버튼으로 파일을 선택하세요.\n"
                f"DSL 토큰({{map:X}}, {{keyword:X}} 등)도 사용 가능합니다.",
            )
            self._path.setFocus()
            return

        self.accept()

    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "이미지 파일 선택", "",
            "이미지 (*.jpg *.jpeg *.png *.gif *.webp);;모든 파일 (*)",
        )
        if path:
            self._path.setText(path)

    def result(self) -> dict:
        cfg: dict = {}
        path = self._path.text().strip()
        if path:
            cfg["path"] = path
        link = self._link.text().strip()
        if link:
            cfg["link"] = link
        if self._alt is not None:
            alt = self._alt.text().strip()
            if alt:
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

        # 고급: wait
        wait = self._wait.text().strip()
        if wait:
            cfg["wait"] = wait

        # 고급: effects
        effects = self._parse_effects_text()
        if effects:
            cfg["effects"] = effects

        # 고급: GPS
        lat = self._gps_lat.text().strip()
        lng = self._gps_lng.text().strip()
        if lat and lng:
            try:
                cfg["gps"] = [float(lat), float(lng)]
            except ValueError:
                pass

        # 고급: filename_keyword
        fkw = self._filename_kw.text().strip()
        if fkw:
            cfg["filename_keyword"] = fkw

        # 고급: exif_description
        exif_desc = self._exif_desc.text().strip()
        if exif_desc:
            cfg["exif_description"] = exif_desc

        # entry-level when
        entry: dict
        if len(cfg) == 1 and "path" in cfg:
            entry = {self._block_type: cfg["path"]}
        else:
            entry = {self._block_type: cfg}

        when = self._when.text().strip()
        if when:
            entry["when"] = when

        return entry

    def _parse_effects_text(self) -> list[dict]:
        raw = self._effects.toPlainText().strip()
        if not raw:
            return []
        effects = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) == 2:
                effects.append({"region": parts[0], "effect": parts[1]})
            elif len(parts) == 1:
                effects.append({"effect": parts[0]})
        return effects


class _DividerDialog(QDialog):
    """구분선 편집 -- type + when/wait."""

    def __init__(self, parent: QWidget, existing: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("구분선 설정")
        self.setMinimumWidth(400)

        # 기존 값 추출 — divider는 dict({type: N}) 또는 int(N) 또는 None
        _raw_val = (existing or {}).get("divider")
        if isinstance(_raw_val, dict):
            _type_default = int(_raw_val.get("type", 2)) if _raw_val.get("type") else 2
        elif isinstance(_raw_val, int):
            _type_default = _raw_val
        else:
            _type_default = 2

        _when: str = str((existing or {}).get("when", ""))
        _wait: str = str((existing or {}).get("wait", ""))

        # 구분선 스타일 (1~8, 기본 2)
        self._type = QSpinBox()
        self._type.setRange(1, 8)
        self._type.setValue(_type_default)
        self._type.setToolTip("네이버 SE 구분선 스타일 1~8 (기본 2)")

        self._when = QLineEdit(_when)
        self._when.setPlaceholderText('{keyword:region} == 강남')
        self._wait = QLineEdit(_wait)
        self._wait.setPlaceholderText("2s 또는 1s ~ 3s")

        form = QFormLayout()
        form.addRow("스타일:", self._type)
        form.addRow("조건 (when):", self._when)
        form.addRow("대기 (wait):", self._wait)

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
        dtype = int(self._type.value())
        # type이 기본값(2)이 아니면 단축형(숫자)으로, 기본값이면 None으로 저장
        if dtype != 2:
            entry: dict = {"divider": dtype}
        else:
            entry = {"divider": None}
        when = self._when.text().strip()
        if when:
            entry["when"] = when
        wait = self._wait.text().strip()
        if wait:
            entry["wait"] = wait
        return entry


# ─────────────────────────────────────────────────────────────────────────────
# AI 섹션 다이얼로그
# ─────────────────────────────────────────────────────────────────────────────

_AI_SECTION_STRUCTURE_OPTIONS = [
    "heading", "h1", "h2", "h3", "h4", "h5", "h6",
    "list", "ordered_list", "quote", "divider", "paragraph",
]


class _AiSectionDialog(QDialog):
    """AI 섹션 블록 — prompt + structure + on_mismatch + when/wait."""

    def __init__(
        self,
        parent: QWidget,
        token_source: Callable | None = None,
        existing: dict | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI 섹션 수정" if existing else "AI 섹션 추가")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        ts = token_source or (lambda: [])

        _raw = (existing or {}).get("ai_section", {})
        if not isinstance(_raw, dict):
            _raw = {}
        _prompt_default = str(_raw.get("prompt", ""))
        _structure_default = _raw.get("structure", []) or []
        _on_mismatch_default = str(_raw.get("on_mismatch", "lenient"))
        _auto_prompt_default = bool(_raw.get("auto_prompt", True))
        _when: str = str((existing or {}).get("when", ""))
        _wait: str = str((existing or {}).get("wait", ""))

        # 프롬프트 (멀티라인)
        self._prompt = QTextEdit()
        self._prompt.setPlainText(_prompt_default)
        self._prompt.setPlaceholderText(
            "{keyword:region} 수학학원의 장점을 정리해줘"
        )
        self._prompt.setMaximumHeight(120)
        token_btn = TokenInsertButton(self._prompt, ts)

        prompt_row = QHBoxLayout()
        prompt_row.addWidget(self._prompt)
        prompt_row.addWidget(token_btn)

        # 구조 리스트 (블록 시퀀스)
        self._structure_list = QListWidget()
        self._structure_list.setMaximumHeight(140)
        for s in _structure_default:
            self._structure_list.addItem(str(s))

        # 구조 추가 콤보 + 버튼
        self._structure_combo = QComboBox()
        self._structure_combo.addItems(_AI_SECTION_STRUCTURE_OPTIONS)

        btn_add_struct = QPushButton("+ 추가")
        btn_add_struct.clicked.connect(self._add_structure_item)
        btn_remove_struct = QPushButton("- 삭제")
        btn_remove_struct.clicked.connect(self._remove_structure_item)
        btn_up = QPushButton("↑")
        btn_up.clicked.connect(lambda: self._move_structure(-1))
        btn_down = QPushButton("↓")
        btn_down.clicked.connect(lambda: self._move_structure(+1))

        struct_btn_row = QHBoxLayout()
        struct_btn_row.addWidget(self._structure_combo)
        struct_btn_row.addWidget(btn_add_struct)
        struct_btn_row.addWidget(btn_remove_struct)
        struct_btn_row.addWidget(btn_up)
        struct_btn_row.addWidget(btn_down)
        struct_btn_row.addStretch()

        # 옵션
        self._on_mismatch = QComboBox()
        self._on_mismatch.addItems(["lenient", "strict"])
        idx = self._on_mismatch.findText(_on_mismatch_default)
        if idx >= 0:
            self._on_mismatch.setCurrentIndex(idx)
        self._on_mismatch.setToolTip(
            "lenient: AI 응답을 그대로 사용 (기본)\n"
            "strict: structure와 시퀀스가 정확히 일치해야 통과"
        )

        self._auto_prompt = QCheckBox("structure를 프롬프트에 자동 추가")
        self._auto_prompt.setChecked(_auto_prompt_default)
        self._auto_prompt.setToolTip(
            "체크 시: structure 항목을 마크다운 가이드로 변환해 프롬프트 끝에 추가\n"
            "체크 해제: prompt를 그대로 AI에게 전달"
        )

        # 고급
        self._when = QLineEdit(_when)
        self._when.setPlaceholderText('{keyword:region} == 강남')
        self._wait = QLineEdit(_wait)
        self._wait.setPlaceholderText("2s 또는 1s ~ 3s")

        advanced = CollapsibleSection("고급 설정")
        advanced.add_row("조건 (when):", self._when)
        advanced.add_row("대기 (wait):", self._wait)

        # 폼 조립
        form = QFormLayout()
        form.addRow("프롬프트:", prompt_row)
        form.addRow("구조 (블록 시퀀스):", self._structure_list)
        form.addRow("", struct_btn_row)
        form.addRow("불일치 모드:", self._on_mismatch)
        form.addRow("", self._auto_prompt)

        # 안내 텍스트
        hint = QLabel(
            "AI가 1회 호출되어 마크다운으로 응답하고, 그 결과가 자동으로 "
            "여러 블록으로 변환됩니다. structure는 AI에게 주는 가이드입니다."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(advanced)
        layout.addWidget(hint)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _add_structure_item(self) -> None:
        text = self._structure_combo.currentText()
        if text:
            self._structure_list.addItem(text)

    def _remove_structure_item(self) -> None:
        row = self._structure_list.currentRow()
        if row >= 0:
            self._structure_list.takeItem(row)

    def _move_structure(self, delta: int) -> None:
        row = self._structure_list.currentRow()
        if row < 0:
            return
        new_row = row + delta
        if not (0 <= new_row < self._structure_list.count()):
            return
        item = self._structure_list.takeItem(row)
        self._structure_list.insertItem(new_row, item)
        self._structure_list.setCurrentRow(new_row)

    def _on_accept(self) -> None:
        prompt = self._prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(
                self, "프롬프트 필수",
                "AI 섹션은 프롬프트가 필수입니다.\n"
                "AI에게 어떤 글을 써달라고 할지 입력하세요.",
            )
            self._prompt.setFocus()
            return

        if self._structure_list.count() == 0:
            QMessageBox.warning(
                self, "구조 필수",
                "AI 섹션은 최소 하나의 구조 항목이 필요합니다.\n"
                "예: heading, list, paragraph",
            )
            return

        self.accept()

    def result(self) -> dict:
        prompt = self._prompt.toPlainText().strip()
        structure = [
            self._structure_list.item(i).text()
            for i in range(self._structure_list.count())
        ]

        cfg: dict = {
            "prompt": prompt,
            "structure": structure,
        }

        on_mismatch = self._on_mismatch.currentText()
        if on_mismatch != "lenient":
            cfg["on_mismatch"] = on_mismatch

        if not self._auto_prompt.isChecked():
            cfg["auto_prompt"] = False

        entry: dict = {"ai_section": cfg}
        when = self._when.text().strip()
        if when:
            entry["when"] = when
        wait = self._wait.text().strip()
        if wait:
            entry["wait"] = wait
        return entry
