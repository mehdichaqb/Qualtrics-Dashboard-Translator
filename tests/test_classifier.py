"""Tests for cell content classification."""

import pytest

from processor.classifier import CellType, classify_cell, get_translatable_columns, is_structural_column
from processor.detector import FileType


class TestClassifyCell:
    """Test cell classification heuristics."""

    def test_empty(self):
        assert classify_cell("") == CellType.EMPTY
        assert classify_cell("   ") == CellType.EMPTY

    def test_numeric(self):
        assert classify_cell("42") == CellType.NUMERIC
        assert classify_cell("3.14") == CellType.NUMERIC
        assert classify_cell("-100") == CellType.NUMERIC
        assert classify_cell("50%") == CellType.NUMERIC
        assert classify_cell("456789") == CellType.NUMERIC

    def test_qualtrics_expression(self):
        assert classify_cell("${e://Field/FirstName}") == CellType.PROTECTED_TOKEN

    def test_qualtrics_id(self):
        assert classify_cell("QID42") == CellType.INTERNAL_CODE
        assert classify_cell("DM_abc123") == CellType.INTERNAL_CODE

    def test_translatable_text(self):
        assert classify_cell("How do you like the survey?") == CellType.TRANSLATABLE
        assert classify_cell("Agree") == CellType.TRANSLATABLE
        assert classify_cell("Other") == CellType.TRANSLATABLE

    def test_mixed_content(self):
        result = classify_cell("Hello ${e://Field/Name}!")
        assert result == CellType.MIXED

    def test_html_with_text(self):
        result = classify_cell("<b>Important</b> notice")
        assert result == CellType.MIXED

    def test_pure_html(self):
        result = classify_cell("<br/><hr/>")
        assert result == CellType.PROTECTED_TOKEN

    def test_short_label_words(self):
        # Common survey labels should be translatable
        assert classify_cell("Count") == CellType.TRANSLATABLE
        assert classify_cell("Other") == CellType.TRANSLATABLE
        assert classify_cell("Support") == CellType.TRANSLATABLE


class TestIsStructuralColumn:
    """Test structural column detection."""

    def test_data_file_structural(self):
        assert is_structural_column("unique identifier", FileType.DATA_FILE) is True
        assert is_structural_column("type", FileType.DATA_FILE) is True
        assert is_structural_column("recode", FileType.DATA_FILE) is True
        assert is_structural_column("default value", FileType.DATA_FILE) is True

    def test_data_file_non_structural(self):
        assert is_structural_column("EN", FileType.DATA_FILE) is False
        assert is_structural_column("FR-CA", FileType.DATA_FILE) is False

    def test_label_file_structural(self):
        assert is_structural_column(
            "pageId - Part of the Dashboard URL [DO NOT EDIT]",
            FileType.LABEL_FILE,
        ) is True
        assert is_structural_column(
            "entityKey [DO NOT EDIT]",
            FileType.LABEL_FILE,
        ) is True

    def test_label_file_non_structural(self):
        assert is_structural_column("EN", FileType.LABEL_FILE) is False


class TestGetTranslatableColumns:
    """Test translatable column identification."""

    def test_data_file(self):
        columns = ["unique identifier", "type", "recode", "default value", "EN", "FR-CA", "ES"]
        locale_cols = ["EN", "FR-CA", "ES"]
        result = get_translatable_columns(columns, FileType.DATA_FILE, locale_cols)
        assert "EN" in result
        assert "FR-CA" in result
        assert "unique identifier" not in result

    def test_label_file(self):
        columns = [
            "pageId - Part of the Dashboard URL [DO NOT EDIT]",
            "entityKey [DO NOT EDIT]",
            "EN", "FR-CA",
        ]
        locale_cols = ["EN", "FR-CA"]
        result = get_translatable_columns(columns, FileType.LABEL_FILE, locale_cols)
        assert "EN" in result
        assert "FR-CA" in result
        assert len(result) == 2
