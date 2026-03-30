"""
gui/theme.py
------------
디자인 시스템 -- 토큰 + QSS 생성.

사용:
    from gui.theme import build_stylesheet

    app.setStyleSheet(build_stylesheet())
"""

from __future__ import annotations


# ── 기본 단위 ──
BASE = 14  # 1rem = 14px


def rem(n: float) -> int:
    """rem 단위를 px로 변환."""
    return round(BASE * n)


# ── 색상 토큰 ──
GREY = {
    50:  "#fafafa",
    100: "#f5f5f5",
    200: "#e8e8e8",
    300: "#ddd",
    400: "#ccc",
    500: "#bbb",
    600: "#999",
    700: "#666",
    800: "#444",
    900: "#222",
}

WHITE = "#ffffff"
BLACK = "#000000"

BLUE = "#0078d4"
BLUE_DARK = "#005a9e"
BLUE_LIGHT = "#e5f1fb"

RED = "#d32f2f"
RED_LIGHT = "#fce4ec"

# ── 의미 토큰 ──
BG_MAIN = GREY[100]
BG_SURFACE = WHITE
BG_SUBTLE = GREY[50]
BG_HEADER = "#f0f0f0"

BORDER = GREY[400]
BORDER_LIGHT = GREY[200]
BORDER_INPUT = GREY[500]
BORDER_FOCUS = BLUE

TEXT = GREY[900]
TEXT_SECONDARY = GREY[800]
TEXT_HINT = GREY[600]
TEXT_DISABLED = GREY[600]

BTN_BG = "#fdfdfd"
BTN_HOVER = GREY[200]
BTN_PRESSED = GREY[300]

SELECTED_BG = BLUE
SELECTED_TEXT = WHITE

# ── 간격 토큰 ──
SP_XS = rem(0.25)   # 4
SP_SM = rem(0.5)     # 7
SP_MD = rem(0.75)    # 10
SP_LG = rem(1)       # 14
SP_XL = rem(1.5)     # 21

RADIUS_SM = 2
RADIUS_MD = 3

INPUT_HEIGHT = rem(1.5)  # 21
INPUT_PAD_V = rem(0.3)   # 4
INPUT_PAD_H = rem(0.5)   # 7

BTN_PAD_V = rem(0.35)    # 5
BTN_PAD_H = rem(1)       # 14


# ── QSS 생성 ──

def build_stylesheet() -> str:
    return f"""
QWidget {{
    font-family: "Segoe UI", "Malgun Gothic", sans-serif;
    font-size: {BASE}px;
}}

QMainWindow {{
    background: {BG_MAIN};
}}

/* ── 탭 ── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    background: {BG_SURFACE};
    padding: {SP_SM}px;
}}
QTabBar::tab {{
    background: {GREY[200]};
    border: 1px solid {BORDER};
    border-bottom: none;
    padding: {SP_SM}px {SP_LG}px;
    margin-right: {RADIUS_SM}px;
    border-top-left-radius: {RADIUS_MD}px;
    border-top-right-radius: {RADIUS_MD}px;
}}
QTabBar::tab:selected {{
    background: {BG_SURFACE};
    border-bottom: 1px solid {BG_SURFACE};
}}
QTabBar::tab:hover:!selected {{
    background: {GREY[300]};
}}

/* ── 그룹박스 ── */
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: {RADIUS_MD}px;
    margin-top: {SP_LG}px;
    padding: {SP_LG}px {SP_SM}px {SP_SM}px {SP_SM}px;
    background: {BG_SURFACE};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: {SP_MD}px;
    padding: 0 {SP_SM}px;
    color: {TEXT_SECONDARY};
}}

/* ── 입력 컨트롤 ── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    border: 1px solid {BORDER_INPUT};
    border-radius: {RADIUS_SM}px;
    padding: {INPUT_PAD_V}px {INPUT_PAD_H}px;
    background: {BG_SURFACE};
    min-height: {INPUT_HEIGHT}px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {BORDER_FOCUS};
}}
QComboBox::drop-down {{
    border: none;
    padding-right: {INPUT_PAD_V}px;
}}

QTextEdit {{
    border: 1px solid {BORDER_INPUT};
    border-radius: {RADIUS_SM}px;
    padding: {INPUT_PAD_V}px;
    background: {BG_SURFACE};
}}
QTextEdit:focus {{
    border-color: {BORDER_FOCUS};
}}

/* ── 테이블 ── */
QTableWidget {{
    border: 1px solid {BORDER};
    gridline-color: {BORDER_LIGHT};
    background: {BG_SURFACE};
    alternate-background-color: {BG_SUBTLE};
}}
QHeaderView::section {{
    background: {BG_HEADER};
    border: none;
    border-right: 1px solid {GREY[300]};
    border-bottom: 1px solid {BORDER};
    padding: {INPUT_PAD_V}px {SP_SM}px;
    font-weight: bold;
    color: {TEXT_SECONDARY};
}}

/* ── 리스트 ── */
QListWidget {{
    border: 1px solid {BORDER};
    background: {BG_SURFACE};
    alternate-background-color: {BG_SUBTLE};
}}
QListWidget::item {{
    padding: {SP_XS}px {SP_SM}px;
}}
QListWidget::item:selected {{
    background: {SELECTED_BG};
    color: {SELECTED_TEXT};
}}

/* ── 버튼 ── */
QPushButton {{
    border: 1px solid {BORDER_INPUT};
    border-radius: {RADIUS_SM}px;
    padding: {BTN_PAD_V}px {BTN_PAD_H}px;
    background: {BTN_BG};
    min-height: {INPUT_HEIGHT}px;
}}
QPushButton:hover {{
    background: {BTN_HOVER};
    border-color: {GREY[600]};
}}
QPushButton:pressed {{
    background: {BTN_PRESSED};
}}
QPushButton:disabled {{
    color: {TEXT_DISABLED};
    background: {BG_HEADER};
    border-color: {BORDER};
}}

/* ── 체크박스, 라디오 ── */
QCheckBox, QRadioButton {{
    spacing: {SP_SM}px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: {SP_LG}px;
    height: {SP_LG}px;
}}

/* ── 상태바 ── */
QStatusBar {{
    background: {BG_HEADER};
    border-top: 1px solid {GREY[300]};
    padding: {SP_XS}px {SP_SM}px;
    color: {TEXT_HINT};
}}

/* ── 스크롤바 ── */
QScrollBar:vertical {{
    border: none;
    background: {BG_HEADER};
    width: {SP_MD}px;
}}
QScrollBar::handle:vertical {{
    background: {GREY[400]};
    border-radius: {INPUT_PAD_V}px;
    min-height: {rem(1.5)}px;
}}
QScrollBar::handle:vertical:hover {{
    background: {GREY[600]};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
}}
QScrollBar:horizontal {{
    border: none;
    background: {BG_HEADER};
    height: {SP_MD}px;
}}
QScrollBar::handle:horizontal {{
    background: {GREY[400]};
    border-radius: {INPUT_PAD_V}px;
    min-width: {rem(1.5)}px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {GREY[600]};
}}

/* ── 스플리터 ── */
QSplitter::handle {{
    background: {GREY[300]};
    height: {RADIUS_MD}px;
}}

/* ── 메뉴 ── */
QMenu {{
    background: {BG_SURFACE};
    border: 1px solid {BORDER};
    padding: {INPUT_PAD_V}px 0;
}}
QMenu::item {{
    padding: {INPUT_PAD_V}px {rem(1.5)}px;
}}
QMenu::item:selected {{
    background: {SELECTED_BG};
    color: {SELECTED_TEXT};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER_LIGHT};
    margin: {INPUT_PAD_V}px {SP_SM}px;
}}
"""
