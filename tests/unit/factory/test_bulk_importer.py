"""
tests/unit/factory/test_bulk_importer.py
-----------------------------------------
BulkImporter input validation — DB-free.
"""

import pytest

from factory.bulk_importer import validate_import_data


class TestValidateImportData:

    def test_valid_data(self):
        validate_import_data({"region": ["강남", "수원"]})

    def test_multiple_categories(self):
        validate_import_data({
            "region": ["강남", "수원"],
            "subject": ["수학", "영어"],
        })

    def test_empty_dict_raises(self):
        with pytest.raises(ValueError, match="empty"):
            validate_import_data({})

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="empty"):
            validate_import_data({"region": []})

    def test_non_string_key_raises(self):
        with pytest.raises(ValueError, match="string"):
            validate_import_data({123: ["강남"]})

    def test_non_string_value_raises(self):
        with pytest.raises(ValueError, match="string"):
            validate_import_data({"region": [123, "강남"]})

    def test_duplicate_values_deduplicated(self):
        """Duplicates within a category are silently accepted (deduped at import)."""
        validate_import_data({"region": ["강남", "강남"]})

    def test_whitespace_only_slug_raises(self):
        with pytest.raises(ValueError, match="empty"):
            validate_import_data({"": ["강남"]})

    def test_whitespace_only_value_raises(self):
        with pytest.raises(ValueError, match="empty"):
            validate_import_data({"region": ["", "강남"]})
