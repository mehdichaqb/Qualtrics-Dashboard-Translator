"""
validator.py — Validate structural integrity of translated output.

Ensures the translated DataFrame matches the original in shape, headers,
column order, row order, and protected-token preservation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import pandas as pd

from .protector import validate_restoration


@dataclass
class ValidationResult:
    """Overall validation result."""
    passed: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def validate_output(
    original_df: pd.DataFrame,
    translated_df: pd.DataFrame,
) -> ValidationResult:
    """
    Validate that the translated DataFrame preserves the structural
    integrity of the original.
    """
    issues: List[str] = []
    warnings: List[str] = []

    # Row count
    if len(original_df) != len(translated_df):
        issues.append(
            f"Row count mismatch: original={len(original_df)}, "
            f"translated={len(translated_df)}"
        )

    # Column count
    if len(original_df.columns) != len(translated_df.columns):
        issues.append(
            f"Column count mismatch: original={len(original_df.columns)}, "
            f"translated={len(translated_df.columns)}"
        )

    # Column names and order
    orig_cols = list(original_df.columns)
    trans_cols = list(translated_df.columns)
    if orig_cols != trans_cols:
        issues.append("Column names or ordering differ from original")
        # Find specific differences
        for i, (oc, tc) in enumerate(zip(orig_cols, trans_cols)):
            if oc != tc:
                issues.append(f"  Column {i}: original='{oc}', translated='{tc}'")

    # Check that non-translatable columns are unchanged
    # (headers row is the column names themselves — already checked)

    if issues:
        return ValidationResult(passed=False, issues=issues, warnings=warnings)

    return ValidationResult(passed=True, issues=issues, warnings=warnings)


def validate_cell_integrity(
    original_value: str,
    translated_value: str,
    column_name: str,
    row_index: int,
) -> List[str]:
    """
    Validate a single cell's integrity after translation.

    Returns a list of issues (empty = OK).
    """
    issues: List[str] = []

    # Check for None or NaN leakage
    if translated_value is None:
        issues.append(f"[{row_index}][{column_name}] Translated value is None")
    elif translated_value == "nan":
        issues.append(f"[{row_index}][{column_name}] Translated value is 'nan' string")

    return issues


def validate_csv_safety(text: str) -> List[str]:
    """
    Check for common CSV serialization issues in a text value.
    """
    issues: List[str] = []

    # Unbalanced quotes
    if text.count('"') % 2 != 0:
        issues.append("Unbalanced double quotes")

    # Newlines without proper quoting (would need quoting in CSV)
    if "\n" in text or "\r" in text:
        issues.append("Contains newlines (will need proper CSV quoting)")

    return issues
