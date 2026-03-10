"""Tests for translation rules / decision engine."""

import pandas as pd
import pytest

from processor.classifier import CellType
from processor.detector import FileType
from processor.reference_memory import TranslationMemory
from processor.rules import CellTranslation, Provenance, translate_cell
from processor.translator import MockTranslator


class TestTranslateCell:
    """Test the cell-level translation decision engine."""

    def _make_memory(self) -> TranslationMemory:
        """Create a memory with common entries."""
        memory = TranslationMemory()
        df = pd.DataFrame({
            "EN": ["Agree", "Disagree", "Count", "Other"],
            "FR-CA": ["D'accord", "Pas d'accord", "Compte", "Autre"],
        })
        memory.load_reference(df, FileType.DATA_FILE, "EN", "FR-CA")
        return memory

    def test_empty_cell_skipped(self):
        memory = TranslationMemory()
        translator = MockTranslator()
        result = translate_cell(
            "", 0, "FR-CA", "EN", "FR-CA", FileType.DATA_FILE, memory, translator
        )
        assert result.provenance == Provenance.SKIPPED_EMPTY
        assert result.translated == ""

    def test_numeric_cell_skipped(self):
        memory = TranslationMemory()
        translator = MockTranslator()
        result = translate_cell(
            "42", 0, "FR-CA", "EN", "FR-CA", FileType.DATA_FILE, memory, translator
        )
        assert result.provenance == Provenance.SKIPPED_NUMERIC

    def test_internal_code_skipped(self):
        memory = TranslationMemory()
        translator = MockTranslator()
        result = translate_cell(
            "QID42", 0, "FR-CA", "EN", "FR-CA", FileType.DATA_FILE, memory, translator
        )
        assert result.provenance == Provenance.SKIPPED_INTERNAL

    def test_exact_reference_match(self):
        memory = self._make_memory()
        translator = MockTranslator()
        result = translate_cell(
            "Agree", 0, "FR-CA", "EN", "FR-CA", FileType.DATA_FILE, memory, translator
        )
        assert result.provenance == Provenance.REFERENCE_EXACT
        assert result.translated == "D'accord"

    def test_normalized_reference_match(self):
        memory = self._make_memory()
        translator = MockTranslator()
        result = translate_cell(
            "  Agree  ", 0, "FR-CA", "EN", "FR-CA", FileType.DATA_FILE, memory, translator
        )
        # Extra whitespace should still match
        assert result.provenance in (Provenance.REFERENCE_EXACT, Provenance.REFERENCE_NORMALIZED)
        assert result.translated == "D'accord"

    def test_fresh_translation_fallback(self):
        memory = TranslationMemory()
        translator = MockTranslator()
        result = translate_cell(
            "Something new and exciting",
            0, "FR-CA", "EN", "FR-CA",
            FileType.DATA_FILE, memory, translator,
        )
        assert result.provenance == Provenance.FRESH_TRANSLATION
        assert "[FR-CA]" in result.translated  # Mock prefix

    def test_session_cache(self):
        memory = TranslationMemory()
        translator = MockTranslator()

        # First translation
        result1 = translate_cell(
            "Brand new text", 0, "FR-CA", "EN", "FR-CA",
            FileType.DATA_FILE, memory, translator,
        )
        assert result1.provenance == Provenance.FRESH_TRANSLATION

        # Second time — should come from session cache
        result2 = translate_cell(
            "Brand new text", 1, "FR-CA", "EN", "FR-CA",
            FileType.DATA_FILE, memory, translator,
        )
        assert result2.provenance == Provenance.SESSION_CACHE

    def test_protected_token_skipped(self):
        memory = TranslationMemory()
        translator = MockTranslator()
        result = translate_cell(
            "${e://Field/Name}", 0, "FR-CA", "EN", "FR-CA",
            FileType.DATA_FILE, memory, translator,
        )
        assert result.provenance == Provenance.SKIPPED_PROTECTED

    def test_mixed_content_translated(self):
        memory = TranslationMemory()
        translator = MockTranslator()
        result = translate_cell(
            "Hello ${e://Field/Name}!",
            0, "FR-CA", "EN", "FR-CA",
            FileType.DATA_FILE, memory, translator,
        )
        # Should translate the text part
        assert result.provenance == Provenance.FRESH_TRANSLATION
        # Protected token should be preserved
        assert "${e://Field/Name}" in result.translated
