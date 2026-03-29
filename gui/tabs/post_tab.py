"""포스트 블록 탭 - 블록 추가/편집/삭제/순서 변경."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QComboBox, QListWidget, QListWidgetItem, QInputDialog,
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
    QLabel, QDoubleSpinBox, QSpinBox, QCheckBox, QTextEdit,
    QGroupBox,
)

from typing import Callable

from gui.collapsible import CollapsibleSection
from gui.token_insert import TokenInsertButton


_BLOCK_TYPES = [
    ("소제목 (H1)", "h1"), ("소제목 (H2)", "h2"), ("소제목 (H3)", "h3"),
    ("소제목 (H4)", "h4"), ("소제목 (H5)", "h5"), ("소제목 (H6)", "h6"),
    ("AI 단락", "paragraph"),
    ("수동 텍스트", "text"),
    ("본문 이미지", "image"),
    ("대표 이미지", "featured_image"),
    ("인용구", "quote"),
    ("목록", "list"),
    ("구분선", "divider"),
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
            self._append({"divider": None})
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
            text, ok = QInputDialog.getMultiLineText(
                self, "목록 추가", "항목 (한 줄에 하나):", "항목 1\n항목 2\n항목 3"
            )
            if ok and text.strip():
                items = [line.strip() for line in text.splitlines() if line.strip()]
                self._append({"list": items})
            return

        if bt in ("image", "featured_image"):
            dlg = _ImageDialog(self, bt, token_source=self._token_source)
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
            return "------- 구분선 -------"
        bt = next(iter(block))
        val = block[bt]
        if isinstance(val, str):
            short = val[:50] + "..." if len(val) > 50 else val
            return f"[{bt}]  {short}"
        if isinstance(val, list):
            return f"[{bt}]  {', '.join(str(v) for v in val[:3])}..."
        if isinstance(val, dict):
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

class _SimpleTextDialog(QDialog):
    """소제목, paragraph 등 단일 텍스트 + when/wait 고급 설정."""

    def __init__(self, parent: QWidget, title: str, label: str, block_type: str,
                 multiline: bool = False, default: str = "",
                 token_source: Callable | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(500)
        self._block_type = block_type
        self._multiline = multiline

        if multiline:
            self._text = QTextEdit()
            self._text.setPlainText(default)
            self._text.setMaximumHeight(100)
        else:
            self._text = QLineEdit(default)

        token_btn = TokenInsertButton(self._text, token_source or (lambda: []))

        input_row = QHBoxLayout()
        input_row.addWidget(self._text)
        input_row.addWidget(token_btn)

        form = QFormLayout()
        form.addRow(label, input_row)

        # 고급
        self._when = QLineEdit()
        self._when.setPlaceholderText('{keyword:region} == 강남')
        self._wait = QLineEdit()
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
        if self._multiline:
            text = self._text.toPlainText().strip()
        else:
            text = self._text.text().strip()

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

    def __init__(self, parent: QWidget, token_source: Callable | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("수동 텍스트 추가")
        self.setMinimumWidth(500)

        self._inline = QTextEdit()
        self._inline.setPlaceholderText("{keyword:region} 중등 수학학원은 대표 전문 학원입니다.")
        self._inline.setMaximumHeight(100)

        token_btn_inline = TokenInsertButton(self._inline, token_source or (lambda: []))

        self._file = QLineEdit()
        self._file.setPlaceholderText("{i}.txt 또는 {keyword:region}/{i}.txt")
        token_btn_file = TokenInsertButton(self._file, token_source or (lambda: []))
        self._format = QComboBox()
        self._format.addItems(["plain", "html"])

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
        self._when = QLineEdit()
        self._when.setPlaceholderText('{keyword:region} == 강남')
        self._wait = QLineEdit()
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

    def __init__(self, parent: QWidget, token_source: Callable | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("인용구 추가")
        self.setMinimumWidth(500)

        self._text = QLineEdit()
        self._text.setPlaceholderText("인용문 텍스트")
        token_btn = TokenInsertButton(self._text, token_source or (lambda: []))
        self._attribution = QLineEdit()
        self._attribution.setPlaceholderText("출처 (선택)")

        text_row = QHBoxLayout()
        text_row.addWidget(self._text)
        text_row.addWidget(token_btn)

        form = QFormLayout()
        form.addRow("인용문:", text_row)
        form.addRow("출처:", self._attribution)

        # 고급
        self._when = QLineEdit()
        self._when.setPlaceholderText('{keyword:region} == 강남')
        self._wait = QLineEdit()
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
        if attr:
            entry: dict = {"quote": {"text": text, "attribution": attr}}
        else:
            entry = {"quote": text}

        when = self._when.text().strip()
        if when:
            entry["when"] = when
        wait = self._wait.text().strip()
        if wait:
            entry["wait"] = wait
        return entry


class _ImageDialog(QDialog):

    def __init__(self, parent: QWidget, block_type: str,
                 token_source: Callable | None = None) -> None:
        super().__init__(parent)
        is_featured = block_type == "featured_image"
        self.setWindowTitle("대표 이미지 추가" if is_featured else "본문 이미지 추가")
        self.setMinimumWidth(500)
        self._block_type = block_type
        ts = token_source or (lambda: [])

        # 기본 필드
        self._path = QLineEdit()
        self._path.setPlaceholderText("photo.jpg 또는 {map:photo}")
        token_btn_path = TokenInsertButton(self._path, ts)

        self._link = QLineEdit()
        self._link.setPlaceholderText("tel:01012345678 또는 https://...")
        token_btn_link = TokenInsertButton(self._link, ts)

        path_row = QHBoxLayout()
        path_row.addWidget(self._path)
        path_row.addWidget(token_btn_path)

        link_row = QHBoxLayout()
        link_row.addWidget(self._link)
        link_row.addWidget(token_btn_link)

        form = QFormLayout()
        form.addRow("파일 경로:", path_row)
        form.addRow("링크:", link_row)

        if not is_featured:
            self._alt = QLineEdit()
            self._alt.setPlaceholderText("대체 텍스트")
            form.addRow("대체 텍스트:", self._alt)
        else:
            self._alt = None

        # 오버레이 (featured_image 전용)
        if is_featured:
            self._overlay_text = QLineEdit()
            self._overlay_text.setPlaceholderText("{keyword:region} 과외")
            token_btn_overlay = TokenInsertButton(self._overlay_text, ts)

            overlay_row = QHBoxLayout()
            overlay_row.addWidget(self._overlay_text)
            overlay_row.addWidget(token_btn_overlay)

            self._overlay_color = QLineEdit("#FFFFFF")
            self._overlay_bg = QDoubleSpinBox()
            self._overlay_bg.setRange(0.0, 1.0)
            self._overlay_bg.setSingleStep(0.1)
            self._overlay_bg.setValue(0.0)
            self._overlay_pos = QComboBox()
            self._overlay_pos.addItems(["center", "top", "bottom"])

            form.addRow("오버레이 텍스트:", overlay_row)
            form.addRow("텍스트 색상:", self._overlay_color)
            form.addRow("배경 불투명도:", self._overlay_bg)
            form.addRow("텍스트 위치:", self._overlay_pos)

        # 고급 1: when / wait / effects
        self._when = QLineEdit()
        self._when.setPlaceholderText('{keyword:region} in [강남, 서초]')
        self._wait = QLineEdit()
        self._wait.setPlaceholderText("2s 또는 1s ~ 3s")
        self._effects = QTextEdit()
        self._effects.setPlaceholderText(
            "한 줄에 하나씩 (region | effect):\n"
            "border:10 ~ 30 | brightness:0.3 ~ 0.7\n"
            "all | hue:0.0 ~ 0.03"
        )
        self._effects.setMaximumHeight(80)

        advanced1 = CollapsibleSection("조건 / 대기 / 효과")
        advanced1.add_row("조건 (when):", self._when)
        advanced1.add_row("대기 (wait):", self._wait)
        advanced1.add_row("효과 (effects):", self._effects)

        # 고급 2: GPS / EXIF / 파일명
        self._gps_lat = QLineEdit()
        self._gps_lat.setPlaceholderText("37.497")
        self._gps_lng = QLineEdit()
        self._gps_lng.setPlaceholderText("127.027")
        self._filename_kw = QLineEdit()
        self._filename_kw.setPlaceholderText("gangnam-tutor")
        self._exif_desc = QLineEdit()
        self._exif_desc.setPlaceholderText("ASCII 설명 (선택)")

        advanced2 = CollapsibleSection("GPS / EXIF / 파일명")
        advanced2.add_row("위도:", self._gps_lat)
        advanced2.add_row("경도:", self._gps_lng)
        advanced2.add_row("파일명 키워드:", self._filename_kw)
        advanced2.add_row("EXIF 설명:", self._exif_desc)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(advanced1)
        layout.addWidget(advanced2)
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
