"""
factory/affix_detector.py
---------------------------
Dictionary-based affix detection for Korean keyword values.

Detects known suffixes (동, 읍, 면, 리, 구, 시, 군, 도) and prefixes
by matching against keyword values.

Usage:
    detect_affixes(["수리동", "산본동", "강남구"])
    → [("suffix", "동"), ("suffix", "구")]
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Default dictionaries — Korean administrative suffixes
# ---------------------------------------------------------------------------

DEFAULT_SUFFIXES: list[str] = [
    "동", "읍", "면", "리",
    "구", "시", "군", "도",
]

DEFAULT_PREFIXES: list[str] = []


# ---------------------------------------------------------------------------
# Detection functions
# ---------------------------------------------------------------------------

def detect_suffixes(
    values: list[str],
    suffix_dict: list[str] | None = None,
) -> list[tuple[str, str]]:
    """
    Detect known suffixes present in the given values.

    Args:
        values:      Keyword values to scan.
        suffix_dict: Known suffixes. Defaults to Korean admin divisions.

    Returns:
        List of ("suffix", value) tuples for each detected suffix.
    """
    if not values:
        return []

    dictionary = suffix_dict if suffix_dict is not None else DEFAULT_SUFFIXES
    found: list[tuple[str, str]] = []

    for suffix in dictionary:
        if any(v.endswith(suffix) and len(v) > len(suffix) for v in values):
            found.append(("suffix", suffix))

    return found


def detect_prefixes(
    values: list[str],
    prefix_dict: list[str] | None = None,
) -> list[tuple[str, str]]:
    """
    Detect known prefixes present in the given values.

    Args:
        values:      Keyword values to scan.
        prefix_dict: Known prefixes. Defaults to empty.

    Returns:
        List of ("prefix", value) tuples for each detected prefix.
    """
    if not values:
        return []

    dictionary = prefix_dict if prefix_dict is not None else DEFAULT_PREFIXES
    found: list[tuple[str, str]] = []

    for prefix in dictionary:
        if any(v.startswith(prefix) and len(v) > len(prefix) for v in values):
            found.append(("prefix", prefix))

    return found


def detect_affixes(
    values: list[str],
    suffix_dict: list[str] | None = None,
    prefix_dict: list[str] | None = None,
) -> list[tuple[str, str]]:
    """
    Detect both suffixes and prefixes in the given values.

    Args:
        values:      Keyword values to scan.
        suffix_dict: Known suffixes. None = default Korean admin divisions.
        prefix_dict: Known prefixes. None = default (empty).

    Returns:
        List of (type, value) tuples. Unique, order preserved.
    """
    results = detect_suffixes(values, suffix_dict) + detect_prefixes(values, prefix_dict)
    seen: set[tuple[str, str]] = set()
    unique: list[tuple[str, str]] = []
    for pair in results:
        if pair not in seen:
            unique.append(pair)
            seen.add(pair)
    return unique
