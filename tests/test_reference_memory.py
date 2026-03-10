"""Tests for reference file translation memory."""

import pandas as pd
import pytest

from processor.detector import FileType
from processor.reference_memory import TranslationMemory, build_memory_from_reference


class TestTranslationMemory:
    """Test translation memory operations."""

    def _make_memory_with_entries(self) -> TranslationMemory:
        """Helper: create a memory with some standard entries."""
        memory = TranslationMemory()
        df = pd.DataFrame({
            "EN": ["Agree", "Disagree", "Other", "Count"],
            "FR-CA": ["D'accord", "Pas d'accord", "Autre", "Compte"],
        })
        memory.load_reference(df, FileType.DATA_FILE, "EN", "FR-CA")
        return memory

    def test_exact_match(self):
        memory = self._make_memory_with_entries()
        match = memory.lookup("Agree")
        assert match is not None
        assert match.translation == "D'accord"
        assert match.match_type == "exact"

    def test_normalized_match(self):
        memory = self._make_memory_with_entries()
        match = memory.lookup("  Agree  ")  # extra whitespace
        assert match is not None
        assert match.translation == "D'accord"
        # Could be exact if trimmed, or normalized
        assert match.match_type in ("exact", "normalized")

    def test_no_match(self):
        memory = self._make_memory_with_entries()
        match = memory.lookup("Something completely different")
        assert match is None

    def test_session_cache(self):
        memory = self._make_memory_with_entries()
        memory.add_to_session_cache("New text", "Nouveau texte")
        match = memory.lookup("New text")
        assert match is not None
        assert match.translation == "Nouveau texte"
        assert match.match_type == "session_cache"

    def test_prefer_origin(self):
        memory = TranslationMemory()
        # Load same text from both origins
        df_data = pd.DataFrame({
            "EN": ["Count"],
            "FR-CA": ["Compte (data)"],
        })
        df_label = pd.DataFrame({
            "EN": ["Count"],
            "FR-CA": ["Compte (label)"],
        })
        memory.load_reference(df_data, FileType.DATA_FILE, "EN", "FR-CA")
        memory.load_reference(df_label, FileType.LABEL_FILE, "EN", "FR-CA")

        match_data = memory.lookup("Count", prefer_origin="data_file")
        assert match_data is not None
        assert match_data.translation == "Compte (data)"

        match_label = memory.lookup("Count", prefer_origin="label_file")
        assert match_label is not None
        assert match_label.translation == "Compte (label)"

    def test_conflict_detection(self):
        memory = TranslationMemory()
        df = pd.DataFrame({
            "EN": ["Hello", "Hello"],
            "FR-CA": ["Bonjour", "Salut"],
        })
        memory.load_reference(df, FileType.LABEL_FILE, "EN", "FR-CA")
        assert len(memory.conflicts) == 1
        assert memory.conflicts[0].source == "Hello"

    def test_empty_values_skipped(self):
        memory = TranslationMemory()
        df = pd.DataFrame({
            "EN": ["Agree", "", "Other"],
            "FR-CA": ["D'accord", "Something", ""],
        })
        memory.load_reference(df, FileType.DATA_FILE, "EN", "FR-CA")
        # Empty source → skipped; empty target → skipped
        assert memory.lookup("") is None
        # "Other" had empty target so should not be loaded
        assert memory.lookup("Other") is None

    def test_session_cache_size(self):
        memory = TranslationMemory()
        assert memory.get_session_cache_size() == 0
        memory.add_to_session_cache("a", "b")
        memory.add_to_session_cache("c", "d")
        assert memory.get_session_cache_size() == 2


class TestBuildMemoryFromReference:
    """Test the high-level reference loading function."""

    def test_auto_detect_columns(self):
        memory = TranslationMemory()
        df = pd.DataFrame({
            "unique identifier": ["DM_abc"],
            "type": ["labels"],
            "recode": ["123"],
            "default value": ["Yes"],
            "EN": ["Yes"],
            "FR-CA": ["Oui"],
        })
        notes = build_memory_from_reference(df, memory, "EN", "FR-CA")
        assert notes.get("warning") is None
        match = memory.lookup("Yes")
        assert match is not None
        assert match.translation == "Oui"

    def test_missing_source_column(self):
        memory = TranslationMemory()
        df = pd.DataFrame({
            "DE": ["Ja"],
            "FR": ["Oui"],
        })
        notes = build_memory_from_reference(df, memory, "EN", "FR-CA")
        assert "warning" in notes
        assert "EN" in notes["warning"]

    def test_label_file_reference(self):
        memory = TranslationMemory()
        df = pd.DataFrame({
            "pageId - Part of the Dashboard URL [DO NOT EDIT]": ["Page_abc"],
            "widgetPosition [DO NOT EDIT]": ["1/10"],
            "widgetType [DO NOT EDIT]": ["reporting.rsdkrichtext"],
            "defaultWidgetTitle [DO NOT EDIT]": ["N/A"],
            "entityId [DO NOT EDIT]": ["esdc_abc"],
            "entityKey [DO NOT EDIT]": ["title:text"],
            "EN": ["Welcome"],
            "FR-CA": ["Bienvenue"],
        })
        notes = build_memory_from_reference(df, memory, "EN", "FR-CA")
        match = memory.lookup("Welcome")
        assert match is not None
        assert match.translation == "Bienvenue"
        assert notes["detected_type"] == "label_file"
