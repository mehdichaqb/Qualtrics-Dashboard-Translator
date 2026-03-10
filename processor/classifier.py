"""
classifier.py — Classify cell content to determine translatability.

Each cell is classified as one of:
  - TRANSLATABLE: user-facing text that should be translated
  - PROTECTED_TOKEN: entirely technical (QID, UUID, code)
  - INTERNAL_CODE: internal Qualtrics identifier or code
  - VARIABLE_NAME: column/variable name or key
  - NUMERIC: purely numeric or categorical response code
  - EMPTY: blank or whitespace-only
  - MIXED: contains both translatable text and protected tokens
"""

from __future__ import annotations

import re
from enum import Enum
from typing import List, Optional

from .detector import FileType


class CellType(Enum):
    TRANSLATABLE = "translatable"
    PROTECTED_TOKEN = "protected_token"
    INTERNAL_CODE = "internal_code"
    VARIABLE_NAME = "variable_name"
    NUMERIC = "numeric"
    EMPTY = "empty"
    MIXED = "mixed"


# ── Patterns for non-translatable content ────────────────────────────────

_NUMERIC_RE = re.compile(r"^[\s\-+]?\d+[\d.,]*%?\s*$")
_QUALTRICS_ID_RE = re.compile(
    r"^(?:QID\d+|MQ\d+|DB_\w+|DM_\w+|SV_\w+|"
    r"esdc_\w+|Widget_[\w\-]+|Page_[\w\-]+|"
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r")$"
)
_VARIABLE_NAME_RE = re.compile(r"^[a-zA-Z_]\w*$")
_RECODE_RE = re.compile(r"^\d{3,}$")  # 3+ digit recode numbers
_ENTITY_KEY_TECHNICAL_RE = re.compile(
    r"^(?:title:text|description:text|contentHtml:contentHtml|"
    r"description:description|"
    r"[a-f0-9\-]{36}:label|"
    r"content-\w+:label|ticker-\w+:label|"
    r"label:[\w\-:]+|topics:[\w\s\-&]+)$",
    re.IGNORECASE,
)
_QUALTRICS_EXPR_RE = re.compile(r"^\$\{[^}]+\}$")
_HTML_ONLY_RE = re.compile(r"^(?:<[^>]+>|\s|&\w+;)+$")


# ── Columns that are NEVER translatable ──────────────────────────────────

# Data-file structural columns
DATA_FILE_STRUCTURAL_COLS = {
    "unique identifier", "type", "recode", "default value",
}

# Label-file structural columns (may have "[DO NOT EDIT]" suffix)
LABEL_FILE_STRUCTURAL_KEYWORDS = {
    "pageid", "widgetposition", "widgettype",
    "defaultwidgettitle", "entityid", "entitykey",
}


def is_structural_column(column_name: str, file_type: FileType) -> bool:
    """Check if a column is structural (never translatable)."""
    col_lower = column_name.lower().strip()

    if file_type == FileType.DATA_FILE:
        if col_lower in DATA_FILE_STRUCTURAL_COLS:
            return True

    if file_type == FileType.LABEL_FILE:
        for kw in LABEL_FILE_STRUCTURAL_KEYWORDS:
            if kw in col_lower:
                return True

    return False


def classify_cell(value: str, column_name: Optional[str] = None) -> CellType:
    """
    Classify a single cell value.

    *column_name* is optional context for better classification.
    """
    if not value or not value.strip():
        return CellType.EMPTY

    stripped = value.strip()

    # Pure numeric
    if _NUMERIC_RE.match(stripped):
        return CellType.NUMERIC

    # Qualtrics expression
    if _QUALTRICS_EXPR_RE.match(stripped):
        return CellType.PROTECTED_TOKEN

    # Qualtrics internal ID
    if _QUALTRICS_ID_RE.match(stripped):
        return CellType.INTERNAL_CODE

    # Recode number (3+ digits)
    if _RECODE_RE.match(stripped):
        return CellType.NUMERIC

    # Pure HTML structure with no text
    if _HTML_ONLY_RE.match(stripped):
        return CellType.PROTECTED_TOKEN

    # Check if it looks like a variable name (single word, no spaces, code-like)
    if _VARIABLE_NAME_RE.match(stripped) and len(stripped) > 20:
        # Long single-word tokens are likely codes
        return CellType.INTERNAL_CODE

    # Check for mixed content (has both tokens and text)
    has_token = bool(re.search(r"\$\{[^}]+\}|<[^>]+>", stripped))
    has_text = bool(re.search(r"[a-zA-ZÀ-ÿ]{2,}", re.sub(r"\$\{[^}]+\}|<[^>]+>|&\w+;", "", stripped)))

    if has_token and has_text:
        return CellType.MIXED

    if has_token and not has_text:
        return CellType.PROTECTED_TOKEN

    # If we get here, it's likely human-readable text
    if has_text:
        return CellType.TRANSLATABLE

    # Short single-word entries might be labels or codes
    if len(stripped.split()) == 1 and not any(c in stripped for c in " .,;:!?"):
        # Single word — could be a label like "Count", "Other", etc.
        # We'll treat short single words as translatable if they look like words
        if stripped[0].isupper() and stripped[1:].islower() and len(stripped) <= 15:
            return CellType.TRANSLATABLE
        return CellType.INTERNAL_CODE

    return CellType.TRANSLATABLE


def get_translatable_columns(
    columns: List[str],
    file_type: FileType,
    locale_columns: List[str],
) -> List[str]:
    """
    Determine which columns contain translatable content.

    For both file types, only locale columns are translatable.
    Structural columns are always excluded.
    """
    locale_set = set(locale_columns)
    result = []

    for col in columns:
        if col in locale_set and not is_structural_column(col, file_type):
            result.append(col)

    return result
