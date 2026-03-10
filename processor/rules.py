"""
rules.py — Translation decision engine.

Implements the matching/decision hierarchy:
  Priority 1: exact reference match
  Priority 2: normalized reference match
  Priority 3: session cache
  Priority 4: fresh translation
  Priority 5: keep original + flag if unsafe
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from .classifier import CellType, classify_cell
from .detector import FileType
from .protector import ProtectionResult, protect_tokens, restore_tokens, validate_restoration
from .reference_memory import MemoryMatch, TranslationMemory
from .translator import TranslationProvider, TranslationRequest, TranslationResult


class Provenance(Enum):
    """How a translation was obtained."""
    REFERENCE_EXACT = "reference_exact_match"
    REFERENCE_NORMALIZED = "reference_normalized_match"
    SESSION_CACHE = "session_cache"
    FRESH_TRANSLATION = "fresh_translation"
    SKIPPED_PROTECTED = "skipped_protected"
    SKIPPED_EMPTY = "skipped_empty"
    SKIPPED_NUMERIC = "skipped_numeric"
    SKIPPED_INTERNAL = "skipped_internal"
    KEPT_ORIGINAL_FLAGGED = "kept_original_flagged"
    TRANSLATION_ERROR = "translation_error"


@dataclass
class CellTranslation:
    """Result of translating a single cell."""
    row_index: int
    column_name: str
    original: str
    translated: str
    provenance: Provenance
    cell_type: CellType
    notes: List[str]
    protection_result: Optional[ProtectionResult] = None


def translate_cell(
    value: str,
    row_index: int,
    column_name: str,
    source_lang: str,
    target_lang: str,
    file_type: FileType,
    memory: TranslationMemory,
    translator: TranslationProvider,
) -> CellTranslation:
    """
    Apply the full decision hierarchy to translate a single cell.
    """
    notes: List[str] = []

    # Classify the cell
    cell_type = classify_cell(value, column_name)

    # Skip non-translatable types
    if cell_type == CellType.EMPTY:
        return CellTranslation(
            row_index=row_index, column_name=column_name,
            original=value, translated=value,
            provenance=Provenance.SKIPPED_EMPTY, cell_type=cell_type, notes=notes,
        )

    if cell_type == CellType.NUMERIC:
        return CellTranslation(
            row_index=row_index, column_name=column_name,
            original=value, translated=value,
            provenance=Provenance.SKIPPED_NUMERIC, cell_type=cell_type, notes=notes,
        )

    if cell_type in (CellType.INTERNAL_CODE, CellType.VARIABLE_NAME):
        return CellTranslation(
            row_index=row_index, column_name=column_name,
            original=value, translated=value,
            provenance=Provenance.SKIPPED_INTERNAL, cell_type=cell_type, notes=notes,
        )

    if cell_type == CellType.PROTECTED_TOKEN:
        return CellTranslation(
            row_index=row_index, column_name=column_name,
            original=value, translated=value,
            provenance=Provenance.SKIPPED_PROTECTED, cell_type=cell_type, notes=notes,
        )

    # Determine preferred reference origin
    prefer_origin = "label_file" if file_type == FileType.LABEL_FILE else "data_file"

    # Priority 1 & 2: reference lookup (exact and normalized)
    mem_match = memory.lookup(value.strip(), prefer_origin=prefer_origin)
    if mem_match:
        prov = (
            Provenance.REFERENCE_EXACT
            if mem_match.match_type == "exact"
            else Provenance.REFERENCE_NORMALIZED
            if mem_match.match_type == "normalized"
            else Provenance.SESSION_CACHE
        )
        notes.append(f"Matched from {mem_match.reference_origin} ({mem_match.match_type})")
        return CellTranslation(
            row_index=row_index, column_name=column_name,
            original=value, translated=mem_match.translation,
            provenance=prov, cell_type=cell_type, notes=notes,
        )

    # Priority 4: fresh translation
    # First, protect tokens
    protection = protect_tokens(value)
    text_to_translate = protection.protected_text

    # Only translate if there's something left after protection
    if text_to_translate.strip() and text_to_translate.strip() != value.strip():
        notes.append(f"Protected {len(protection.placeholders)} token(s)")

    request = TranslationRequest(
        source_text=text_to_translate,
        source_lang=source_lang,
        target_lang=target_lang,
        context=f"{file_type.value} / {column_name}",
    )

    result = translator.translate_single(request)

    if not result.success:
        notes.append(f"Translation error: {result.error}")
        return CellTranslation(
            row_index=row_index, column_name=column_name,
            original=value, translated=value,
            provenance=Provenance.TRANSLATION_ERROR, cell_type=cell_type,
            notes=notes, protection_result=protection,
        )

    # Restore protected tokens
    translated = restore_tokens(result.translated_text, protection.placeholders)

    # Validate restoration
    restoration_issues = validate_restoration(value, translated, protection.placeholders)
    if restoration_issues:
        notes.extend(restoration_issues)

    # Cache this translation
    memory.add_to_session_cache(value.strip(), translated)

    return CellTranslation(
        row_index=row_index, column_name=column_name,
        original=value, translated=translated,
        provenance=Provenance.FRESH_TRANSLATION, cell_type=cell_type,
        notes=notes, protection_result=protection,
    )


def translate_batch_cells(
    values: List[str],
    source_lang: str,
    target_lang: str,
    file_type: FileType,
    memory: TranslationMemory,
    translator: TranslationProvider,
) -> List[TranslationResult]:
    """
    Translate a batch of cell values that are known to need fresh translation.

    Protects tokens, batches to the provider, restores tokens.
    """
    if not values:
        return []

    # Protect tokens in each value
    protections = [protect_tokens(v) for v in values]

    # Build requests for the batch
    requests = [
        TranslationRequest(
            source_text=p.protected_text,
            source_lang=source_lang,
            target_lang=target_lang,
        )
        for p in protections
    ]

    # Translate batch
    results = translator.translate_batch(requests)

    # Restore tokens
    final_results = []
    for result, protection in zip(results, protections):
        restored = restore_tokens(result.translated_text, protection.placeholders)
        final_results.append(TranslationResult(
            source_text=result.source_text,
            translated_text=restored,
            provider=result.provider,
            success=result.success,
            error=result.error,
        ))
        # Cache
        if result.success:
            orig = restore_tokens(result.source_text, protection.placeholders)
            memory.add_to_session_cache(orig.strip(), restored)

    return final_results
