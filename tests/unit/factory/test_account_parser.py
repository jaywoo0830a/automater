"""
tests/unit/factory/test_account_parser.py
-------------------------------------------
Account Excel parser unit tests — no DB, no file I/O.

Account Excel is row-oriented (one row = one account),
unlike keyword Excel which is column-oriented.

Required columns : username, password, platform
Optional columns : blog_id, cooldown_days
"""

import pytest

from factory.account_parser import (
    parse_account_rows,
    validate_account_rows,
    AccountRow,
    AccountRowError,
    REQUIRED_COLUMNS,
)


# ---------------------------------------------------------------------------
# parse_account_rows — pure function
# ---------------------------------------------------------------------------

class TestParseAccountRows:

    def test_basic_two_accounts(self):
        headers = ["username", "password", "platform"]
        rows = [
            ["user1", "pass1", "naver"],
            ["user2", "pass2", "naver"],
        ]
        result = parse_account_rows(headers, rows)
        assert len(result) == 2
        assert result[0] == AccountRow(
            row_number=1,
            username="user1",
            password="pass1",
            platform="naver",
            blog_id="",
            cooldown_days=14,
        )
        assert result[1].username == "user2"
        assert result[1].row_number == 2

    def test_with_optional_columns(self):
        headers = ["username", "password", "platform", "blog_id", "cooldown_days"]
        rows = [["user1", "pass1", "naver", "myblog", 7]]
        result = parse_account_rows(headers, rows)
        assert result[0].blog_id == "myblog"
        assert result[0].cooldown_days == 7

    def test_missing_optional_columns_get_defaults(self):
        headers = ["username", "password", "platform"]
        rows = [["user1", "pass1", "naver"]]
        result = parse_account_rows(headers, rows)
        assert result[0].blog_id == ""
        assert result[0].cooldown_days == 14

    def test_strips_whitespace(self):
        headers = [" username ", " password", "platform "]
        rows = [["  user1  ", " pass1 ", " naver "]]
        result = parse_account_rows(headers, rows)
        assert result[0].username == "user1"
        assert result[0].password == "pass1"
        assert result[0].platform == "naver"

    def test_header_case_insensitive(self):
        headers = ["Username", "PASSWORD", "Platform"]
        rows = [["user1", "pass1", "naver"]]
        result = parse_account_rows(headers, rows)
        assert result[0].username == "user1"

    def test_cooldown_days_float_converted_to_int(self):
        headers = ["username", "password", "platform", "cooldown_days"]
        rows = [["user1", "pass1", "naver", 14.0]]
        result = parse_account_rows(headers, rows)
        assert result[0].cooldown_days == 14

    def test_skips_completely_empty_rows(self):
        headers = ["username", "password", "platform"]
        rows = [
            ["user1", "pass1", "naver"],
            [None, None, None],
            ["", "", ""],
            ["user2", "pass2", "naver"],
        ]
        result = parse_account_rows(headers, rows)
        assert len(result) == 2
        assert result[0].row_number == 1
        assert result[1].row_number == 4

    def test_ragged_row_padded_with_empty(self):
        headers = ["username", "password", "platform", "blog_id"]
        rows = [["user1", "pass1"]]
        result = parse_account_rows(headers, rows)
        assert result[0].platform == ""
        assert result[0].blog_id == ""

    def test_missing_required_headers_raises(self):
        headers = ["username", "platform"]
        rows = [["user1", "naver"]]
        with pytest.raises(ValueError, match="password"):
            parse_account_rows(headers, rows)

    def test_empty_headers_raises(self):
        with pytest.raises(ValueError, match="header"):
            parse_account_rows([], [["user1"]])

    def test_no_rows_returns_empty_list(self):
        headers = ["username", "password", "platform"]
        result = parse_account_rows(headers, [])
        assert result == []

    def test_extra_columns_ignored(self):
        headers = ["username", "password", "platform", "memo", "region"]
        rows = [["user1", "pass1", "naver", "note", "seoul"]]
        result = parse_account_rows(headers, rows)
        assert result[0].username == "user1"

    def test_duplicate_usernames_preserved(self):
        """Unlike keywords, duplicate accounts are kept for validation later."""
        headers = ["username", "password", "platform"]
        rows = [
            ["user1", "pass1", "naver"],
            ["user1", "pass2", "naver"],
        ]
        result = parse_account_rows(headers, rows)
        assert len(result) == 2

    def test_numeric_username_converted_to_string(self):
        headers = ["username", "password", "platform"]
        rows = [[12345, "pass1", "naver"]]
        result = parse_account_rows(headers, rows)
        assert result[0].username == "12345"


# ---------------------------------------------------------------------------
# validate_account_rows — row-level validation
# ---------------------------------------------------------------------------

class TestValidateAccountRows:

    def test_valid_rows_return_no_errors(self):
        rows = [
            AccountRow(1, "user1", "pass1", "naver", "blog1", 14),
            AccountRow(2, "user2", "pass2", "naver", "", 14),
        ]
        errors = validate_account_rows(rows)
        assert errors == []

    def test_missing_username(self):
        rows = [AccountRow(1, "", "pass1", "naver", "", 14)]
        errors = validate_account_rows(rows)
        assert len(errors) == 1
        assert errors[0].row_number == 1
        assert "username" in errors[0].message

    def test_missing_password(self):
        rows = [AccountRow(1, "user1", "", "naver", "", 14)]
        errors = validate_account_rows(rows)
        assert len(errors) == 1
        assert "password" in errors[0].message

    def test_missing_platform(self):
        rows = [AccountRow(1, "user1", "pass1", "", "", 14)]
        errors = validate_account_rows(rows)
        assert len(errors) == 1
        assert "platform" in errors[0].message

    def test_multiple_errors_in_one_row(self):
        rows = [AccountRow(1, "", "", "", "", 14)]
        errors = validate_account_rows(rows)
        assert len(errors) == 3

    def test_invalid_cooldown_days(self):
        rows = [AccountRow(1, "user1", "pass1", "naver", "", -1)]
        errors = validate_account_rows(rows)
        assert len(errors) == 1
        assert "cooldown" in errors[0].message

    def test_duplicate_username_platform_pair(self):
        rows = [
            AccountRow(1, "user1", "pass1", "naver", "", 14),
            AccountRow(2, "user1", "pass2", "naver", "", 14),
        ]
        errors = validate_account_rows(rows)
        assert len(errors) == 1
        assert errors[0].row_number == 2
        assert "duplicate" in errors[0].message.lower()

    def test_duplicate_across_different_platforms_ok(self):
        rows = [
            AccountRow(1, "user1", "pass1", "naver", "", 14),
            AccountRow(2, "user1", "pass2", "wordpress", "", 14),
        ]
        errors = validate_account_rows(rows)
        assert errors == []

    def test_errors_across_multiple_rows(self):
        rows = [
            AccountRow(1, "", "pass1", "naver", "", 14),
            AccountRow(2, "user2", "pass2", "naver", "", 14),
            AccountRow(3, "user3", "", "naver", "", 14),
        ]
        errors = validate_account_rows(rows)
        assert len(errors) == 2
        row_nums = {e.row_number for e in errors}
        assert row_nums == {1, 3}
