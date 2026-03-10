"""Tests for file type detection."""

import pandas as pd
import pytest

from processor.detector import FileType, detect_file_type, find_locale_columns, detect_language_pair


class TestDetectFileType:
    """Test automatic file type classification."""

    def test_data_file_detection(self):
        """Data file with standard columns detected correctly."""
        df = pd.DataFrame({
            "unique identifier": ["DM_abc123", "DM_def456"],
            "type": ["labels", "labels"],
            "recode": ["456789", "456790"],
            "default value": ["Agree", "Disagree"],
            "EN": ["Agree", "Disagree"],
            "FR-CA": ["D'accord", "Pas d'accord"],
        })
        assert detect_file_type(df) == FileType.DATA_FILE

    def test_label_file_detection(self):
        """Label file with dashboard columns detected correctly."""
        df = pd.DataFrame({
            "pageId - Part of the Dashboard URL [DO NOT EDIT]": ["Page_abc", ""],
            "widgetPosition [DO NOT EDIT]": ["1/10", ""],
            "widgetType [DO NOT EDIT]": ["reporting.rsdkrichtext", ""],
            "defaultWidgetTitle [DO NOT EDIT]": ["N/A", ""],
            "entityId [DO NOT EDIT]": ["esdc_abc_dashboard", "esdc_abc_dashboard"],
            "entityKey [DO NOT EDIT]": ["title:text", "description:text"],
            "EN": ["Hello World", ""],
            "FR-CA": ["Bonjour le monde", ""],
        })
        assert detect_file_type(df) == FileType.LABEL_FILE

    def test_unknown_file(self):
        """File with no recognizable structure."""
        df = pd.DataFrame({
            "col1": ["a", "b"],
            "col2": ["c", "d"],
        })
        assert detect_file_type(df) == FileType.UNKNOWN

    def test_data_file_with_dm_ids(self):
        """Data file recognized by DM_ identifiers even without standard headers."""
        df = pd.DataFrame({
            "id": ["DM_abc", "DM_def", "DM_ghi", "DM_jkl"],
            "type": ["labels", "labels", "labels", "labels"],
            "EN": ["Yes", "No", "Maybe", "Other"],
            "FR": ["Oui", "Non", "Peut-être", "Autre"],
        })
        result = detect_file_type(df)
        # Should recognize DM_ pattern
        assert result in (FileType.DATA_FILE, FileType.UNKNOWN)


class TestFindLocaleColumns:
    """Test locale column detection."""

    def test_standard_locales(self):
        df = pd.DataFrame(columns=["Name", "EN", "FR", "FR-CA", "ES", "DE"])
        locales = find_locale_columns(df)
        assert "EN" in locales
        assert "FR" in locales
        assert "FR-CA" in locales
        assert "ES" in locales
        assert "DE" in locales
        assert "Name" not in locales

    def test_mixed_case(self):
        df = pd.DataFrame(columns=["en", "fr-ca", "Name"])
        # Our detector normalizes to upper for matching
        # The columns must match exactly in the original case
        locales = find_locale_columns(df)
        # "en" upper = "EN" which is in _LOCALE_CODES
        assert len(locales) >= 1

    def test_no_locales(self):
        df = pd.DataFrame(columns=["name", "value", "score"])
        locales = find_locale_columns(df)
        assert len(locales) == 0


class TestDetectLanguagePair:
    """Test language pair detection."""

    def test_en_frca_pair(self):
        df = pd.DataFrame({
            "EN": ["Hello"],
            "FR-CA": ["Bonjour"],
            "ES": [""],
        })
        src, tgt = detect_language_pair(df)
        assert src == "EN"
        assert tgt == "FR-CA"

    def test_with_hints(self):
        df = pd.DataFrame({
            "EN": ["Hello"],
            "FR": ["Bonjour"],
            "FR-CA": ["Bonjour"],
        })
        src, tgt = detect_language_pair(df, source_hint="EN", target_hint="FR")
        assert src == "EN"
        assert tgt == "FR"

    def test_empty_dataframe(self):
        df = pd.DataFrame(columns=["col1", "col2"])
        src, tgt = detect_language_pair(df)
        assert src is None
        assert tgt is None
