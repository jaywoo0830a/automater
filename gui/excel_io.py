"""
gui/excel_io.py
---------------
섹션별 Excel 가져오기 / 내보내기.

각 탭(계정·키워드·풀·제목)에서 독립적으로 호출한다.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ── column definitions ─────────────────────────────────────────────

ACCOUNT_COLUMNS = [
    ("username", "Username"),
    ("password", "Password"),
    ("blog_id", "Blog ID"),
    ("weight", "Weight"),
    ("min_posts", "Min"),
    ("max_posts", "Max"),
    ("proxy", "Proxy"),
]
ACCOUNT_DEFAULTS = ["", "", "", "1", "0", "0", ""]

KV_COLUMNS = [
    ("category", "카테고리"),
    ("values", "값 (콤마 구분)"),
]

TITLE_COLUMNS = [
    ("title", "제목 템플릿"),
]

# ── styling ────────────────────────────────────────────────────────

_HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
_HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
_HEADER_ALIGN = Alignment(horizontal="center", vertical="center")
_THIN_BORDER = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin"),
)


def _style_header(ws, columns: list[tuple[str, str]]) -> None:
    for col_idx, (_, label) in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=col_idx, value=label)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _HEADER_ALIGN
        cell.border = _THIN_BORDER
    for col_idx in range(1, len(columns) + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 22


def _read_rows(ws, skip_header: bool = True) -> list[list[str]]:
    rows: list[list[str]] = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if skip_header and i == 0:
            continue
        vals = [str(c).strip() if c is not None else "" for c in row]
        if any(vals):
            rows.append(vals)
    return rows


def _single_sheet_wb(title: str, columns: list[tuple[str, str]]) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = title
    _style_header(ws, columns)
    return wb


# ── accounts ───────────────────────────────────────────────────────

def export_accounts(path: str | Path, accounts: list[dict]) -> None:
    wb = _single_sheet_wb("accounts", ACCOUNT_COLUMNS)
    ws = wb.active
    for acc in accounts:
        ws.append([acc.get(k, d) for (k, _), d in zip(ACCOUNT_COLUMNS, ACCOUNT_DEFAULTS)])
    wb.save(str(path))


def import_accounts(path: str | Path) -> list[dict]:
    wb = load_workbook(str(path), read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    keys = [k for k, _ in ACCOUNT_COLUMNS]
    result: list[dict] = []
    for row in _read_rows(ws):
        acc: dict = {}
        for i, key in enumerate(keys):
            val = row[i] if i < len(row) else ACCOUNT_DEFAULTS[i]
            if not val:
                val = ACCOUNT_DEFAULTS[i]
            if key in ("weight", "min_posts", "max_posts"):
                try:
                    ival = int(float(val))
                except (ValueError, TypeError):
                    ival = int(ACCOUNT_DEFAULTS[i])
                if key == "weight" and ival == 1:
                    continue
                if key in ("min_posts", "max_posts") and ival == 0:
                    continue
                acc[key] = ival
            else:
                if val:
                    acc[key] = val
        if acc.get("username"):
            result.append(acc)
    wb.close()
    return result


def template_accounts(path: str | Path) -> None:
    wb = _single_sheet_wb("accounts", ACCOUNT_COLUMNS)
    wb.active.append(["example_id", "password123", "myblog", 1, 0, 0, ""])
    wb.save(str(path))


# ── key-value (keywords / pools) ──────────────────────────────────

def export_kv(path: str | Path, data: dict[str, list[str]], sheet_name: str = "data") -> None:
    wb = _single_sheet_wb(sheet_name, KV_COLUMNS)
    ws = wb.active
    for slug, vals in data.items():
        ws.append([slug, ", ".join(vals)])
    wb.save(str(path))


def import_kv(path: str | Path) -> dict[str, list[str]]:
    wb = load_workbook(str(path), read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    result: dict[str, list[str]] = {}
    for row in _read_rows(ws):
        slug = row[0] if len(row) > 0 else ""
        vals = row[1] if len(row) > 1 else ""
        if slug and vals:
            result[slug] = [v.strip() for v in vals.split(",") if v.strip()]
    wb.close()
    return result


def template_kv(path: str | Path, sheet_name: str = "data", examples: list[list[str]] | None = None) -> None:
    wb = _single_sheet_wb(sheet_name, KV_COLUMNS)
    ws = wb.active
    for row in (examples or [["region", "강남, 서초, 송파"]]):
        ws.append(row)
    wb.save(str(path))


# ── titles ─────────────────────────────────────────────────────────

def export_titles(path: str | Path, titles: list[str]) -> None:
    wb = _single_sheet_wb("titles", TITLE_COLUMNS)
    ws = wb.active
    for t in titles:
        ws.append([t])
    wb.save(str(path))


def import_titles(path: str | Path) -> list[str]:
    wb = load_workbook(str(path), read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    result: list[str] = []
    for row in _read_rows(ws):
        val = row[0] if row else ""
        if val:
            result.append(val)
    wb.close()
    return result


def template_titles(path: str | Path) -> None:
    wb = _single_sheet_wb("titles", TITLE_COLUMNS)
    wb.active.append(["{keyword:region} {keyword:subject} 과외 추천"])
    wb.save(str(path))


# ── maps (key → value) ────────────────────────────────────────────

MAP_COLUMNS = [
    ("key", "키"),
    ("value", "값"),
]


def export_map(path: str | Path, data: dict[str, str]) -> None:
    wb = _single_sheet_wb("map", MAP_COLUMNS)
    ws = wb.active
    for k, v in data.items():
        ws.append([k, v])
    wb.save(str(path))


def import_map(path: str | Path) -> dict[str, str]:
    wb = load_workbook(str(path), read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    result: dict[str, str] = {}
    for row in _read_rows(ws):
        key = row[0] if len(row) > 0 else ""
        val = row[1] if len(row) > 1 else ""
        if key:
            result[key] = val
    wb.close()
    return result


def template_map(path: str | Path) -> None:
    wb = _single_sheet_wb("map", MAP_COLUMNS)
    ws = wb.active
    ws.append(["강남", "gangnam.jpg"])
    ws.append(["서초", "seocho.jpg"])
    ws.append(["_default", "default.jpg"])
    wb.save(str(path))
