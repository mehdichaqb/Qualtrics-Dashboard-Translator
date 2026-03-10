"""Tests for structural validation."""

import pandas as pd
import pytest

from processor.validator import validate_output, validate_cell_integrity, validate_csv_safety


class TestValidateOutput:
    """Test DataFrame structural validation."""

    def test_identical_structure_passes(self):
        df1 = pd.DataFrame({"A": ["1", "2"], "B": ["3", "4"]})
        df2 = pd.DataFrame({"A": ["x", "y"], "B": ["z", "w"]})
        result = validate_output(df1, df2)
        assert result.passed is True

    def test_row_count_mismatch(self):
        df1 = pd.DataFrame({"A": ["1", "2"]})
        df2 = pd.DataFrame({"A": ["1"]})
        result = validate_output(df1, df2)
        assert result.passed is False
        assert any("Row count" in i for i in result.issues)

    def test_column_count_mismatch(self):
        df1 = pd.DataFrame({"A": ["1"], "B": ["2"]})
        df2 = pd.DataFrame({"A": ["1"]})
        result = validate_output(df1, df2)
        assert result.passed is False
        assert any("Column count" in i for i in result.issues)

    def test_column_name_mismatch(self):
        df1 = pd.DataFrame({"A": ["1"], "B": ["2"]})
        df2 = pd.DataFrame({"A": ["1"], "C": ["2"]})
        result = validate_output(df1, df2)
        assert result.passed is False
        assert any("Column names" in i for i in result.issues)

    def test_empty_dataframes_pass(self):
        df1 = pd.DataFrame(columns=["A", "B"])
        df2 = pd.DataFrame(columns=["A", "B"])
        result = validate_output(df1, df2)
        assert result.passed is True


class TestValidateCellIntegrity:
    """Test individual cell validation."""

    def test_normal_cell(self):
        issues = validate_cell_integrity("Hello", "Bonjour", "EN", 0)
        assert len(issues) == 0

    def test_none_value(self):
        issues = validate_cell_integrity("Hello", None, "EN", 0)
        assert len(issues) > 0

    def test_nan_string(self):
        issues = validate_cell_integrity("Hello", "nan", "EN", 0)
        assert len(issues) > 0


class TestValidateCsvSafety:
    """Test CSV serialization safety checks."""

    def test_clean_text(self):
        issues = validate_csv_safety("Hello world")
        assert len(issues) == 0

    def test_unbalanced_quotes(self):
        issues = validate_csv_safety('Hello "world')
        assert any("quote" in i.lower() for i in issues)

    def test_newlines(self):
        issues = validate_csv_safety("Hello\nworld")
        assert any("newline" in i.lower() for i in issues)
