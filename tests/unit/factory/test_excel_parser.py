"""
tests/unit/factory/test_excel_parser.py
-----------------------------------------
Excel parser unit tests — no DB, no file I/O for parse_rows.
"""

import pytest

from factory.excel_parser import parse_rows, resolve_headers


# ---------------------------------------------------------------------------
# parse_rows — pure function
# ---------------------------------------------------------------------------

class TestParseRows:

    def test_basic_columnar_data(self):
        headers = ["지역", "과목"]
        rows = [
            ["수리동", "수학"],
            ["산본동", "영어"],
        ]
        result = parse_rows(headers, rows)
        assert result == {
            "지역": ["수리동", "산본동"],
            "과목": ["수학", "영어"],
        }

    def test_strips_whitespace(self):
        headers = [" 지역 ", "과목"]
        rows = [["  수리동  ", " 수학"]]
        result = parse_rows(headers, rows)
        assert result == {"지역": ["수리동"], "과목": ["수학"]}

    def test_skips_empty_cells(self):
        headers = ["지역", "과목"]
        rows = [
            ["수리동", "수학"],
            ["산본동", ""],
            ["", "영어"],
        ]
        result = parse_rows(headers, rows)
        assert result == {
            "지역": ["수리동", "산본동"],
            "과목": ["수학", "영어"],
        }

    def test_skips_none_cells(self):
        headers = ["지역", "과목"]
        rows = [
            ["수리동", None],
            [None, "수학"],
        ]
        result = parse_rows(headers, rows)
        assert result == {"지역": ["수리동"], "과목": ["수학"]}

    def test_deduplicates_values(self):
        headers = ["지역"]
        rows = [["수리동"], ["수리동"], ["산본동"]]
        result = parse_rows(headers, rows)
        assert result == {"지역": ["수리동", "산본동"]}

    def test_empty_rows_skipped(self):
        headers = ["지역"]
        rows = [["수리동"], [], ["산본동"]]
        result = parse_rows(headers, rows)
        assert result == {"지역": ["수리동", "산본동"]}

    def test_ragged_rows_padded(self):
        """Rows shorter than headers are treated as None for missing cells."""
        headers = ["지역", "과목", "학습형태"]
        rows = [
            ["수리동", "수학"],
            ["산본동"],
        ]
        result = parse_rows(headers, rows)
        assert result == {
            "지역": ["수리동", "산본동"],
            "과목": ["수학"],
        }

    def test_empty_headers_raises(self):
        with pytest.raises(ValueError, match="header"):
            parse_rows([], [["수리동"]])

    def test_blank_header_raises(self):
        with pytest.raises(ValueError, match="header"):
            parse_rows(["지역", ""], [["수리동", "수학"]])

    def test_no_rows_returns_empty_dict(self):
        result = parse_rows(["지역", "과목"], [])
        assert result == {}

    def test_numeric_values_converted_to_string(self):
        """Excel might return integers for zip codes, grades, etc."""
        headers = ["학년"]
        rows = [[1], [2], [3]]
        result = parse_rows(headers, rows)
        assert result == {"학년": ["1", "2", "3"]}

    def test_float_values_converted(self):
        headers = ["학년"]
        rows = [[1.0], [2.0]]
        result = parse_rows(headers, rows)
        assert result == {"학년": ["1", "2"]}

    def test_columns_with_no_data_excluded(self):
        """Columns where all cells are empty are excluded from result."""
        headers = ["지역", "비고"]
        rows = [
            ["수리동", ""],
            ["산본동", None],
        ]
        result = parse_rows(headers, rows)
        assert "비고" not in result
        assert result == {"지역": ["수리동", "산본동"]}


# ---------------------------------------------------------------------------
# resolve_headers — maps display names to slugs
# ---------------------------------------------------------------------------

class TestResolveHeaders:

    def test_explicit_map(self):
        data = {"지역": ["수리동"], "과목": ["수학"]}
        header_map = {"지역": "region", "과목": "subject"}
        result = resolve_headers(data, header_map)
        assert result == {"region": ["수리동"], "subject": ["수학"]}

    def test_partial_map_with_categories(self):
        """Unmapped headers fall through to category lookup."""
        data = {"지역": ["수리동"], "subject": ["수학"]}
        header_map = {"지역": "region"}
        categories = {"과목": "subject"}
        result = resolve_headers(data, header_map, categories)
        assert result == {"region": ["수리동"], "subject": ["수학"]}

    def test_category_lookup(self):
        data = {"지역": ["수리동"], "과목": ["수학"]}
        categories = {"지역": "region", "과목": "subject"}
        result = resolve_headers(data, category_names=categories)
        assert result == {"region": ["수리동"], "subject": ["수학"]}

    def test_slug_passthrough(self):
        """Headers that are already valid slugs pass through unchanged."""
        data = {"region": ["수리동"], "subject": ["수학"]}
        result = resolve_headers(data)
        assert result == {"region": ["수리동"], "subject": ["수학"]}

    def test_unresolved_header_raises(self):
        data = {"지역": ["수리동"], "알수없음": ["뭔가"]}
        header_map = {"지역": "region"}
        with pytest.raises(ValueError, match="알수없음"):
            resolve_headers(data, header_map)

    def test_map_takes_precedence_over_category(self):
        data = {"지역": ["수리동"]}
        header_map = {"지역": "area"}
        categories = {"지역": "region"}
        result = resolve_headers(data, header_map, categories)
        assert result == {"area": ["수리동"]}

    def test_empty_data_raises(self):
        with pytest.raises(ValueError, match="empty"):
            resolve_headers({})
