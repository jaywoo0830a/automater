"""
factory/account_parser.py
----------------------------
Account Excel parsing — row-oriented (one row = one account).

Two layers:
    parse_account_rows(headers, rows)  — pure function, no I/O
    parse_account_excel(path)          — thin openpyxl wrapper

Validation:
    validate_account_rows(rows) — returns per-row errors

Unlike keyword Excel (column-oriented, each column = category),
account Excel is row-oriented (each row = one complete account).

Required columns : username, password, platform
Optional columns : blog_id, cooldown_days
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AccountRow:
    """One parsed account row. row_number is 1-based (Excel convention)."""
    row_number:    int
    username:      str
    password:      str
    platform:      str
    blog_id:       str  = ""
    cooldown_days: int  = 14


@dataclass(frozen=True)
class AccountRowError:
    """Validation error for a single row."""
    row_number: int
    column:     str
    message:    str


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS = {"username", "password", "platform"}

_OPTIONAL_DEFAULTS: dict[str, str | int] = {
    "blog_id":       "",
    "cooldown_days":  14,
}

_ALL_KNOWN_COLUMNS = REQUIRED_COLUMNS | set(_OPTIONAL_DEFAULTS.keys())


# ---------------------------------------------------------------------------
# parse_account_rows — pure function, no I/O
# ---------------------------------------------------------------------------

def parse_account_rows(
    headers: list[str],
    rows: list[list],
) -> list[AccountRow]:
    """
    Parse row-oriented account data into AccountRow list.

    Args:
        headers: Column header strings (case-insensitive).
        rows:    List of rows, each a list of cell values.

    Returns:
        List of AccountRow. Completely empty rows are skipped.

    Raises:
        ValueError: If headers list is empty or required columns missing.
    """
    if not headers:
        raise ValueError("headers must not be empty")

    col_map = _build_column_map(headers)
    _check_required_columns(col_map)

    result: list[AccountRow] = []
    for row_idx, row in enumerate(rows):
        parsed = _parse_one_row(row, col_map, row_number=row_idx + 1)
        if parsed is not None:
            result.append(parsed)

    return result


# ---------------------------------------------------------------------------
# parse_account_excel — openpyxl wrapper
# ---------------------------------------------------------------------------

def parse_account_excel(
    path: str,
    sheet_name: str | None = None,
) -> list[AccountRow]:
    """
    Parse an .xlsx file into a list of AccountRow.

    Args:
        path:       Path to .xlsx file.
        sheet_name: Sheet to read. None = active sheet.

    Returns:
        Parsed account rows via parse_account_rows.
    """
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet_name] if sheet_name else wb.active

    row_iter = ws.iter_rows(values_only=True)
    header_row = next(row_iter, None)
    if not header_row:
        raise ValueError("Excel file has no header row")

    headers = [str(h).strip() if h else "" for h in header_row]
    rows = [list(r) for r in row_iter]

    wb.close()
    return parse_account_rows(headers, rows)


# ---------------------------------------------------------------------------
# validate_account_rows — per-row validation
# ---------------------------------------------------------------------------

def validate_account_rows(rows: list[AccountRow]) -> list[AccountRowError]:
    """
    Validate parsed account rows. Returns a list of errors (empty = all valid).

    Checks:
        - Required fields not empty (username, password, platform)
        - cooldown_days >= 0
        - No duplicate (username, platform) pairs
    """
    errors: list[AccountRowError] = []
    seen_pairs: dict[tuple[str, str], int] = {}

    for row in rows:
        if not row.username:
            errors.append(AccountRowError(
                row.row_number, "username",
                "Missing required field: username",
            ))
        if not row.password:
            errors.append(AccountRowError(
                row.row_number, "password",
                "Missing required field: password",
            ))
        if not row.platform:
            errors.append(AccountRowError(
                row.row_number, "platform",
                "Missing required field: platform",
            ))
        if row.cooldown_days < 0:
            errors.append(AccountRowError(
                row.row_number, "cooldown_days",
                "cooldown_days must be >= 0",
            ))

        # Duplicate check — only when both fields are present
        if row.username and row.platform:
            pair = (row.username.lower(), row.platform.lower())
            if pair in seen_pairs:
                errors.append(AccountRowError(
                    row.row_number, "username",
                    f"Duplicate (username, platform) pair — "
                    f"same as row {seen_pairs[pair]}",
                ))
            else:
                seen_pairs[pair] = row.row_number

    return errors


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_column_map(headers: list[str]) -> dict[str, int]:
    """
    Map normalized column names to their indices.

    Only known columns are included. Unknown columns are ignored.
    Headers are lowered and stripped for case-insensitive matching.
    """
    col_map: dict[str, int] = {}
    for idx, raw_header in enumerate(headers):
        normalized = raw_header.strip().lower()
        if normalized in _ALL_KNOWN_COLUMNS:
            col_map[normalized] = idx
    return col_map


def _check_required_columns(col_map: dict[str, int]) -> None:
    """Raise ValueError if any required column is missing."""
    missing = REQUIRED_COLUMNS - set(col_map.keys())
    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}. "
            f"Required: {sorted(REQUIRED_COLUMNS)}"
        )


def _parse_one_row(
    row: list,
    col_map: dict[str, int],
    row_number: int,
) -> AccountRow | None:
    """
    Parse a single row into an AccountRow.

    Returns None if the row is completely empty.
    """
    def cell(name: str) -> str:
        idx = col_map.get(name)
        if idx is None or idx >= len(row):
            return ""
        value = row[idx]
        if value is None:
            return ""
        if isinstance(value, float):
            value = int(value) if value == int(value) else value
        return str(value).strip()

    username = cell("username")
    password = cell("password")
    platform = cell("platform")
    blog_id  = cell("blog_id")

    # Skip completely empty rows
    if not any([username, password, platform, blog_id]):
        return None

    # Parse cooldown_days with default fallback
    cooldown_raw = cell("cooldown_days")
    cooldown_days = _OPTIONAL_DEFAULTS["cooldown_days"]
    if cooldown_raw:
        try:
            cooldown_days = int(float(cooldown_raw))
        except (ValueError, TypeError):
            cooldown_days = _OPTIONAL_DEFAULTS["cooldown_days"]

    return AccountRow(
        row_number=row_number,
        username=username,
        password=password,
        platform=platform,
        blog_id=blog_id,
        cooldown_days=cooldown_days,
    )
