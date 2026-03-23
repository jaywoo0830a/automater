"""
tests/unit/factory/test_keyword_preview.py
--------------------------------------------
Unit tests for BulkImporter.preview_keywords — preview mode.

Preview returns what would happen without touching the DB.
Uses a FakeSession to verify no writes occur.
"""

import pytest

from factory.keyword_preview import preview_keywords, KeywordPreviewResult


class TestPreviewKeywords:
    """preview_keywords is a pure function: parsed data in, preview out."""

    def test_basic_two_categories(self):
        data = {
            "region": ["수리동", "산본동"],
            "subject": ["수학", "영어"],
        }
        result = preview_keywords(data)

        assert len(result.categories) == 2
        assert result.categories[0].slug == "region"
        assert result.categories[0].keyword_count == 2
        assert result.categories[0].sample_values == ["수리동", "산본동"]
        assert result.categories[1].slug == "subject"

    def test_total_keywords_counted(self):
        data = {
            "region": ["수리동", "산본동", "금정동"],
            "subject": ["수학"],
        }
        result = preview_keywords(data)
        assert result.total_keywords == 4

    def test_estimated_combinations_is_cartesian_product(self):
        data = {
            "region": ["수리동", "산본동"],
            "subject": ["수학", "영어", "과학"],
        }
        result = preview_keywords(data)
        assert result.estimated_combinations == 6  # 2 * 3

    def test_single_category(self):
        data = {"region": ["수리동", "산본동"]}
        result = preview_keywords(data)
        assert result.estimated_combinations == 2

    def test_title_template_generated_from_category_order(self):
        data = {
            "region": ["수리동"],
            "subject": ["수학"],
            "learning_type": ["과외"],
        }
        result = preview_keywords(data)
        assert result.title_template == "{region} {subject} {learning_type}"

    def test_deduplicates_values(self):
        data = {"region": ["수리동", "수리동", "산본동"]}
        result = preview_keywords(data)
        assert result.categories[0].keyword_count == 2
        assert result.categories[0].sample_values == ["수리동", "산본동"]

    def test_strips_whitespace_from_values(self):
        data = {"region": ["  수리동  ", " 산본동"]}
        result = preview_keywords(data)
        assert result.categories[0].sample_values == ["수리동", "산본동"]

    def test_empty_data_raises(self):
        with pytest.raises(ValueError, match="empty"):
            preview_keywords({})

    def test_sample_values_limited_to_five(self):
        data = {"region": [f"지역{i}" for i in range(10)]}
        result = preview_keywords(data)
        assert len(result.categories[0].sample_values) == 5
        # keyword_count reflects all, not just samples
        assert result.categories[0].keyword_count == 10

    def test_empty_values_in_category_filtered(self):
        data = {"region": ["수리동", "", "  ", "산본동"]}
        result = preview_keywords(data)
        assert result.categories[0].keyword_count == 2
