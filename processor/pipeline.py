"""
pipeline.py — Orchestrates the full translation processing flow.

Steps:
  1. Load main file
  2. Detect file type
  3. Load optional reference files
  4. Build translation memory
  5. Identify translatable cells
  6. Translate (with protection + hierarchy)
  7. Validate structural integrity
  8. Export
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd

from .classifier import CellType, classify_cell, get_translatable_columns, is_structural_column
from .detector import FileType, detect_file_type, detect_language_pair, find_locale_columns
from .exporter import (
    build_notes_report,
    export_notes_csv,
    export_translated_csv,
    get_notes_filename,
    get_translated_filename,
)
from .file_loader import load_file
from .protector import protect_tokens, restore_tokens, validate_restoration
from .reference_memory import TranslationMemory, build_memory_from_reference
from .rules import CellTranslation, Provenance, translate_cell
from .translator import TranslationProvider, TranslationRequest, get_translator
from .validator import ValidationResult, validate_output


# ── Direction enum ───────────────────────────────────────────────────────

class TranslationDirection:
    EN_TO_FR_CA = ("EN", "FR-CA")
    FR_TO_EN = ("FR-CA", "EN")


@dataclass
class PipelineConfig:
    """Configuration for a translation pipeline run."""
    file_type_override: Optional[FileType] = None  # None = auto-detect
    source_lang: str = "EN"
    target_lang: str = "FR-CA"
    use_bom: bool = True
    preserve_html: bool = True
    protect_tokens: bool = True
    provider: str = "auto"
    api_key: Optional[str] = None


@dataclass
class PipelineResult:
    """Result of a full pipeline run."""
    translated_df: pd.DataFrame
    original_df: pd.DataFrame
    translations: List[CellTranslation]
    notes_df: pd.DataFrame
    validation: ValidationResult
    diagnostics: Dict[str, str]
    file_type: FileType
    translated_csv_bytes: bytes
    notes_csv_bytes: bytes
    translated_filename: str
    notes_filename: str


def run_pipeline(
    main_file: Union[str, Path, io.BytesIO],
    main_filename: str,
    config: PipelineConfig,
    ref_data_file: Optional[Tuple[Union[str, Path, io.BytesIO], str]] = None,
    ref_label_file: Optional[Tuple[Union[str, Path, io.BytesIO], str]] = None,
    progress_callback=None,
) -> PipelineResult:
    """
    Execute the full translation pipeline.

    *progress_callback*: optional callable(step: str, progress: float)
    for UI progress bars.
    """
    diagnostics: Dict[str, str] = {}

    def _progress(step: str, pct: float) -> None:
        if progress_callback:
            progress_callback(step, pct)

    # ── Step 1: Load main file ───────────────────────────────────────
    _progress("Loading main file...", 0.05)
    original_df = load_file(main_file, file_name=main_filename)
    diagnostics["main_file_rows"] = str(len(original_df))
    diagnostics["main_file_cols"] = str(len(original_df.columns))

    # ── Step 2: Detect file type ─────────────────────────────────────
    _progress("Detecting file type...", 0.10)
    if config.file_type_override:
        file_type = config.file_type_override
        diagnostics["file_type_source"] = "user_override"
    else:
        file_type = detect_file_type(original_df)
        diagnostics["file_type_source"] = "auto_detected"
    diagnostics["file_type"] = file_type.value

    # ── Step 3: Detect locale columns ────────────────────────────────
    locale_cols = find_locale_columns(original_df)
    diagnostics["locale_columns"] = str(len(locale_cols))

    # Find source and target columns in main file
    source_col, target_col = _resolve_columns(
        original_df, config.source_lang, config.target_lang, locale_cols
    )
    diagnostics["source_column"] = source_col or "NOT_FOUND"
    diagnostics["target_column"] = target_col or "NOT_FOUND"

    if not source_col or not target_col:
        raise ValueError(
            f"Could not find source ({config.source_lang}) or target "
            f"({config.target_lang}) language columns in the main file. "
            f"Found locale columns: {locale_cols}"
        )

    # ── Step 4: Load reference files & build memory ──────────────────
    _progress("Building translation memory...", 0.15)
    memory = TranslationMemory()

    if ref_data_file:
        source, name = ref_data_file
        try:
            ref_df = load_file(source, file_name=name)
            notes = build_memory_from_reference(
                ref_df, memory, config.source_lang, config.target_lang
            )
            for k, v in notes.items():
                diagnostics[f"ref_data_{k}"] = v
        except Exception as e:
            diagnostics["ref_data_error"] = str(e)

    if ref_label_file:
        source, name = ref_label_file
        try:
            ref_df = load_file(source, file_name=name)
            notes = build_memory_from_reference(
                ref_df, memory, config.source_lang, config.target_lang
            )
            for k, v in notes.items():
                diagnostics[f"ref_label_{k}"] = v
        except Exception as e:
            diagnostics["ref_label_error"] = str(e)

    diagnostics["memory_data_entries"] = str(memory.data_file_entries)
    diagnostics["memory_label_entries"] = str(memory.label_file_entries)
    diagnostics["memory_conflicts"] = str(len(memory.conflicts))

    # ── Step 5: Get translator ───────────────────────────────────────
    _progress("Initializing translator...", 0.20)
    translator = get_translator(config.provider, config.api_key)
    diagnostics["translator_provider"] = translator.name

    # ── Step 6: Translate ────────────────────────────────────────────
    _progress("Translating...", 0.25)
    translated_df = original_df.copy()
    all_translations: List[CellTranslation] = []

    # Determine which columns to process
    # We translate the TARGET column using the SOURCE column's content
    total_rows = len(original_df)

    # Batch collection for fresh translations
    batch_indices: List[Tuple[int, str]] = []  # (row_idx, column_name)
    batch_originals: List[str] = []

    for row_idx in range(total_rows):
        if total_rows > 0:
            _progress(
                f"Processing row {row_idx + 1}/{total_rows}...",
                0.25 + 0.60 * (row_idx / total_rows),
            )

        source_value = str(original_df.iloc[row_idx][source_col]).strip()
        target_value = str(original_df.iloc[row_idx][target_col]).strip()

        # If target already has content and source is empty, skip
        if not source_value and target_value:
            all_translations.append(CellTranslation(
                row_index=row_idx,
                column_name=target_col,
                original=target_value,
                translated=target_value,
                provenance=Provenance.SKIPPED_EMPTY,
                cell_type=CellType.EMPTY,
                notes=["Source column empty, keeping existing target"],
            ))
            continue

        # If source is empty and target is empty, skip
        if not source_value and not target_value:
            all_translations.append(CellTranslation(
                row_index=row_idx,
                column_name=target_col,
                original="",
                translated="",
                provenance=Provenance.SKIPPED_EMPTY,
                cell_type=CellType.EMPTY,
                notes=[],
            ))
            continue

        # Translate this cell
        ct = translate_cell(
            value=source_value,
            row_index=row_idx,
            column_name=target_col,
            source_lang=config.source_lang,
            target_lang=config.target_lang,
            file_type=file_type,
            memory=memory,
            translator=translator,
        )

        all_translations.append(ct)

        # Write translation to the target column
        translated_df.at[row_idx, target_col] = ct.translated

    # ── Step 7: Validate ─────────────────────────────────────────────
    _progress("Validating...", 0.90)
    validation = validate_output(original_df, translated_df)
    diagnostics["validation_passed"] = str(validation.passed)
    if validation.issues:
        diagnostics["validation_issues"] = "; ".join(validation.issues)

    # ── Step 8: Build notes report ───────────────────────────────────
    _progress("Building notes report...", 0.93)
    notes_df = build_notes_report(all_translations, diagnostics)

    # ── Step 9: Export ───────────────────────────────────────────────
    _progress("Exporting...", 0.95)
    translated_csv = export_translated_csv(translated_df, main_filename, config.use_bom)
    notes_csv = export_notes_csv(notes_df, config.use_bom)

    _progress("Done!", 1.0)

    return PipelineResult(
        translated_df=translated_df,
        original_df=original_df,
        translations=all_translations,
        notes_df=notes_df,
        validation=validation,
        diagnostics=diagnostics,
        file_type=file_type,
        translated_csv_bytes=translated_csv,
        notes_csv_bytes=notes_csv,
        translated_filename=get_translated_filename(main_filename),
        notes_filename=get_notes_filename(main_filename),
    )


def _resolve_columns(
    df: pd.DataFrame,
    source_lang: str,
    target_lang: str,
    locale_cols: List[str],
) -> Tuple[Optional[str], Optional[str]]:
    """
    Find source and target columns, handling case variations.
    """
    upper_map = {c.strip().upper(): c for c in locale_cols}
    source_col = upper_map.get(source_lang.upper())
    target_col = upper_map.get(target_lang.upper())
    return source_col, target_col
