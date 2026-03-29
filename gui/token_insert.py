"""
gui/token_insert.py
-------------------
토큰 삽입 위젯.

텍스트 입력 필드 옆에 붙여서 사용.
클릭하면 현재 등록된 keyword/pool/map/i 토큰 목록을 보여주고,
선택하면 커서 위치에 {keyword:slug} 형태로 삽입한다.

Usage:
    from gui.token_insert import TokenInsertButton

    self._title = QLineEdit()
    token_btn = TokenInsertButton(self._title, token_source=self._get_tokens)

    # token_source: () -> list[str]  현재 사용 가능한 토큰 목록 반환
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QWidget, QPushButton, QMenu, QLineEdit, QTextEdit,
)
from PySide6.QtGui import QAction


class TokenInsertButton(QPushButton):
    """토큰 삽입 버튼. 클릭 시 토큰 목록 메뉴를 보여준다."""

    def __init__(
        self,
        target: QLineEdit | QTextEdit,
        token_source: Callable[[], list[str]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        from gui.theme import BASE, SP_XS, rem
        super().__init__("{..}", parent)
        self.setFixedWidth(rem(2.5))
        self.setToolTip("토큰 삽입")
        self.setStyleSheet(
            f"QPushButton {{ font-size: {BASE - 2}px; padding: {SP_XS}px; }}"
        )
        self._target = target
        self._token_source = token_source or (lambda: [])
        self.clicked.connect(self._show_menu)

    def _show_menu(self) -> None:
        tokens = self._token_source()
        if not tokens:
            return

        menu = QMenu(self)

        # 그룹별 분류
        kw_tokens = [t for t in tokens if t.startswith("{keyword:")]
        pool_tokens = [t for t in tokens if t.startswith("{pool:")]
        map_tokens = [t for t in tokens if t.startswith("{map:")]
        other_tokens = [t for t in tokens if t not in kw_tokens + pool_tokens + map_tokens]

        if kw_tokens:
            menu.addSection("keyword")
            for t in kw_tokens:
                action = menu.addAction(t)
                action.triggered.connect(lambda checked, tok=t: self._insert(tok))

        if pool_tokens:
            menu.addSection("pool")
            for t in pool_tokens:
                action = menu.addAction(t)
                action.triggered.connect(lambda checked, tok=t: self._insert(tok))

        if map_tokens:
            menu.addSection("map")
            for t in map_tokens:
                action = menu.addAction(t)
                action.triggered.connect(lambda checked, tok=t: self._insert(tok))

        if other_tokens:
            menu.addSection("기타")
            for t in other_tokens:
                action = menu.addAction(t)
                action.triggered.connect(lambda checked, tok=t: self._insert(tok))

        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def _insert(self, token: str) -> None:
        if isinstance(self._target, QLineEdit):
            pos = self._target.cursorPosition()
            text = self._target.text()
            self._target.setText(text[:pos] + token + text[pos:])
            self._target.setCursorPosition(pos + len(token))
            self._target.setFocus()
        elif isinstance(self._target, QTextEdit):
            cursor = self._target.textCursor()
            cursor.insertText(token)
            self._target.setFocus()
