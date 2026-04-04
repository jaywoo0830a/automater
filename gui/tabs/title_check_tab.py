"""제목 중복 검사 탭 — title_check DSL 설정.

네이버 통합검색에서 동일 제목이 이미 노출되고 있으면
pool을 재추첨하여 중복을 회피한다.

검색 전략:
    쿼리  = 키워드 부분만 (pool 제외)
    매칭  = 풀 타이틀 (키워드 + 후킹 문구)

DSL 대응:
    title_check: true
    title_check:
      max_attempts: 10
      match: exact           # exact | contains
      delay: 1s ~ 2s
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QCheckBox, QSpinBox, QComboBox, QLineEdit, QLabel,
)


class TitleCheckTab(QWidget):

    def __init__(self) -> None:
        super().__init__()

        # ── 활성화 ──
        self._enabled = QCheckBox("제목 중복 검사 활성화")
        self._enabled.setToolTip(
            "네이버 통합검색에서 동일 제목 존재 시 pool을 재추첨합니다.\n"
            "titles에 {pool:*} 토큰이 최소 1개 필요합니다."
        )
        self._enabled.toggled.connect(self._on_toggled)

        # ── 설정 그룹 ──
        self._max_attempts = QSpinBox()
        self._max_attempts.setRange(1, 50)
        self._max_attempts.setValue(10)
        self._max_attempts.setToolTip("pool 재추첨 최대 횟수 (기본 10)")

        self._match = QComboBox()
        self._match.addItems(["exact", "contains"])
        self._match.setToolTip(
            "exact — 공백 정규화 후 완전 일치\n"
            "contains — 생성 제목이 검색 결과 제목에 포함되면 중복"
        )

        self._delay = QLineEdit("1s ~ 2s")
        self._delay.setPlaceholderText("1s ~ 2s")
        self._delay.setToolTip(
            "검색 요청 간 대기 시간\n"
            "예: 1s, 2s, 500ms ~ 2s"
        )

        settings_form = QFormLayout()
        settings_form.addRow("최대 시도:", self._max_attempts)
        settings_form.addRow("매칭 모드:", self._match)
        settings_form.addRow("요청 간격:", self._delay)

        self._settings_group = QGroupBox("검사 설정")
        self._settings_group.setLayout(settings_form)
        self._settings_group.setEnabled(False)

        # ── 동작 설명 ──
        desc = QLabel(
            "동작 순서:\n"
            "  1. 제목 템플릿에서 keyword만 추출 → 검색 쿼리\n"
            "     예: \"{keyword:region} 중등 {keyword:subject}학원 {pool:hook}\"\n"
            "     → 쿼리: \"대치동 중등 수학학원\"  (pool 제외)\n"
            "  2. 네이버 통합검색 실행\n"
            "     https://search.naver.com/search.naver?query=대치동+중등+수학학원\n"
            "  3. 결과에 풀 타이틀이 있으면 → pool 재추첨\n"
            "  4. max_attempts 소진 시 마지막 제목 사용 + 경고"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: gray; font-size: 11px;")
        desc.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        # ── 레이아웃 ──
        layout = QVBoxLayout()
        layout.addWidget(self._enabled)
        layout.addWidget(self._settings_group)
        layout.addSpacing(12)
        layout.addWidget(desc)
        layout.addStretch()
        self.setLayout(layout)

    def _on_toggled(self, checked: bool) -> None:
        self._settings_group.setEnabled(checked)

    # -- serialisation ----------------------------------------------------

    def to_dict(self) -> dict:
        if not self._enabled.isChecked():
            return {"title_check": False}

        return {
            "title_check": {
                "max_attempts": self._max_attempts.value(),
                "match": self._match.currentText(),
                "delay": self._delay.text().strip() or "1s ~ 2s",
            }
        }

    def from_dict(self, data: dict) -> None:
        tc = data.get("title_check")

        if tc is True:
            self._enabled.setChecked(True)
            self._max_attempts.setValue(10)
            self._match.setCurrentText("exact")
            self._delay.setText("1s ~ 2s")
        elif isinstance(tc, dict):
            enabled = tc.get("enabled", True)
            self._enabled.setChecked(enabled)
            self._max_attempts.setValue(int(tc.get("max_attempts", 10)))
            match_mode = str(tc.get("match", "exact"))
            idx = self._match.findText(match_mode)
            if idx >= 0:
                self._match.setCurrentIndex(idx)
            self._delay.setText(str(tc.get("delay", "1s ~ 2s")))
        else:
            self._enabled.setChecked(False)
            self._max_attempts.setValue(10)
            self._match.setCurrentText("exact")
            self._delay.setText("1s ~ 2s")
