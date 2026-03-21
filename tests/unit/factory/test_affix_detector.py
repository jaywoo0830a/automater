"""
tests/unit/factory/test_affix_detector.py
-------------------------------------------
Affix detection unit tests — pure functions, no DB.
"""

import pytest

from factory.affix_detector import detect_suffixes, detect_prefixes, detect_affixes


# ---------------------------------------------------------------------------
# detect_suffixes
# ---------------------------------------------------------------------------

class TestDetectSuffixes:

    def test_korean_district_suffix(self):
        values = ["수리동", "산본동", "봉천동"]
        result = detect_suffixes(values)
        assert ("suffix", "동") in result

    def test_mixed_suffixes(self):
        values = ["강남구", "수원시", "수리동"]
        result = detect_suffixes(values)
        types = {r[1] for r in result}
        assert "구" in types
        assert "시" in types
        assert "동" in types

    def test_no_known_suffix(self):
        values = ["수학", "영어", "과학"]
        result = detect_suffixes(values)
        assert result == []

    def test_single_value(self):
        values = ["수리동"]
        result = detect_suffixes(values)
        assert ("suffix", "동") in result

    def test_empty_list(self):
        assert detect_suffixes([]) == []

    def test_partial_match(self):
        """Only values ending with the suffix are matched."""
        values = ["수리동", "산본동", "수학"]
        result = detect_suffixes(values)
        assert ("suffix", "동") in result


# ---------------------------------------------------------------------------
# detect_prefixes
# ---------------------------------------------------------------------------

class TestDetectPrefixes:

    def test_no_known_prefix(self):
        values = ["수리동", "산본동"]
        result = detect_prefixes(values)
        assert result == []

    def test_empty_list(self):
        assert detect_prefixes([]) == []


# ---------------------------------------------------------------------------
# detect_affixes — combined
# ---------------------------------------------------------------------------

class TestDetectAffixes:

    def test_combined_detection(self):
        values = ["강남구", "수원시", "수리동", "산본동"]
        result = detect_affixes(values)
        types_values = {(t, v) for t, v in result}
        assert ("suffix", "구") in types_values
        assert ("suffix", "시") in types_values
        assert ("suffix", "동") in types_values

    def test_returns_unique_pairs(self):
        values = ["수리동", "산본동", "봉천동"]
        result = detect_affixes(values)
        assert len(result) == len(set(result))

    def test_custom_suffix_dictionary(self):
        result = detect_affixes(
            ["서울점", "강남점", "수원점"],
            suffix_dict=["점"],
        )
        assert ("suffix", "점") in result

    def test_custom_prefix_dictionary(self):
        result = detect_affixes(
            ["신수리", "신산본"],
            prefix_dict=["신"],
        )
        assert ("prefix", "신") in result

    def test_no_matches_returns_empty(self):
        result = detect_affixes(["수학", "영어"])
        assert result == []
