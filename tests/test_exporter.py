"""Tests for CSV export."""

import pandas as pd
import pytest

from processor.exporter import (
    export_translated_csv,
    export_notes_csv,
    get_translated_filename,
    get_notes_filename,
    build_notes_report,
)
from processor.rules import CellTranslation, Provenance
from processor.classifier import CellType


class TestExportTranslatedCsv:
    """Test CSV export functionality."""

    def test_utf8_with_bom(self):
        df = pd.DataFrame({"A": ["Hello"], "B": ["World"]})
        result = export_translated_csv(df, "test.csv", use_bom=True)
        assert result.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM

    def test_utf8_without_bom(self):
        df = pd.DataFrame({"A": ["Hello"], "B": ["World"]})
        result = export_translated_csv(df, "test.csv", use_bom=False)
        assert not result.startswith(b"\xef\xbb\xbf")

    def test_csv_content_valid(self):
        df = pd.DataFrame({"EN": ["Hello"], "FR-CA": ["Bonjour"]})
        result = export_translated_csv(df, "test.csv", use_bom=False)
        text = result.decode("utf-8")
        assert "EN,FR-CA" in text
        assert "Hello,Bonjour" in text

    def test_special_characters_preserved(self):
        df = pd.DataFrame({"EN": ["café"], "FR": ["café"]})
        result = export_translated_csv(df, "test.csv", use_bom=False)
        text = result.decode("utf-8")
        assert "café" in text

    def test_quotes_and_commas(self):
        df = pd.DataFrame({"A": ["Hello, World"], "B": ['"quoted"']})
        result = export_translated_csv(df, "test.csv", use_bom=False)
        text = result.decode("utf-8")
        # pandas should properly quote these
        assert "Hello, World" in text


class TestFilenames:
    """Test filename generation."""

    def test_translated_filename(self):
        name = get_translated_filename("dashboard_translations.csv")
        assert name == "dashboard_translations_translated_ready_for_qualtrics.csv"

    def test_notes_filename(self):
        name = get_notes_filename("dashboard_translations.csv")
        assert name == "dashboard_translations_translation_notes.csv"


class TestBuildNotesReport:
    """Test notes report building."""

    def test_with_flagged_translations(self):
        translations = [
            CellTranslation(
                row_index=0, column_name="FR-CA",
                original="Hello", translated="Bonjour",
                provenance=Provenance.REFERENCE_EXACT,
                cell_type=CellType.TRANSLATABLE,
                notes=["Matched from data_file (exact)"],
            ),
            CellTranslation(
                row_index=1, column_name="FR-CA",
                original="", translated="",
                provenance=Provenance.SKIPPED_EMPTY,
                cell_type=CellType.EMPTY,
                notes=[],
            ),
        ]
        notes_df = build_notes_report(translations)
        assert len(notes_df) > 0
        # Should have at least the flagged translation + summary rows
        assert "SUMMARY" in notes_df["column"].values

    def test_empty_translations(self):
        notes_df = build_notes_report([])
        assert len(notes_df) == 0
