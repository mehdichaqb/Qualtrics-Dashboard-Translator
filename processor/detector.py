"""
detector.py — Detect whether a Qualtrics file is a Data File or a Label File.

Heuristic-based classification using column signatures and content patterns.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

import pandas as pd


class FileType(Enum):
    DATA_FILE = "data_file"
    LABEL_FILE = "label_file"
    UNKNOWN = "unknown"


# ── Column-name fingerprints ────────────────────────────────────────────

# Data files typically begin with these columns
_DATA_HEADER_SIGNATURES: List[str] = [
    "unique identifier",
    "type",
    "recode",
    "default value",
]

# Label/dashboard files typically begin with these columns
_LABEL_HEADER_KEYWORDS: List[str] = [
    "pageid",
    "widgetposition",
    "widgettype",
    "defaultwidgettitle",
    "entityid",
    "entitykey",
]

# Shared locale columns (present in both types)
_LOCALE_CODES = {
    "EN", "FR", "FR-CA", "ES", "DE", "IT", "PT", "PT-BR", "ZH-S", "ZH-T",
    "JA", "KO", "AR", "RU", "RU-RU", "EN-GB", "NL", "SV", "DA", "NO",
    "FI", "PL", "CS", "HU", "EL", "SK", "RO", "SL", "BG", "HR", "TH",
    "TR", "UK", "MS", "HI", "ID", "BS", "LT", "SR", "VI", "CY", "HY",
    "MK", "LV", "ET", "ES-ES", "EE", "BN", "CA", "MY", "PB", "MAL",
    "MAR", "SQI", "SIN", "SW", "TA", "TGL", "UR",
}


def detect_file_type(df: pd.DataFrame) -> FileType:
    """
    Classify a DataFrame as a Qualtrics Data File or Label File.

    Returns FileType.DATA_FILE, FileType.LABEL_FILE, or FileType.UNKNOWN.
    """
    cols_lower = [c.lower().strip() for c in df.columns]

    data_score = _score_data_file(cols_lower, df)
    label_score = _score_label_file(cols_lower, df)

    if data_score > label_score and data_score >= 2:
        return FileType.DATA_FILE
    if label_score > data_score and label_score >= 2:
        return FileType.LABEL_FILE
    if data_score >= 2:
        return FileType.DATA_FILE
    if label_score >= 2:
        return FileType.LABEL_FILE
    return FileType.UNKNOWN


def _score_data_file(cols_lower: List[str], df: pd.DataFrame) -> int:
    score = 0
    # Check for known data-file header columns
    for sig in _DATA_HEADER_SIGNATURES:
        if sig in cols_lower:
            score += 2

    # Content hints: first column often has DM_* or QID* identifiers
    if len(df) > 0 and len(cols_lower) > 0:
        first_col = df.columns[0]
        sample = df[first_col].head(20).str.strip()
        dm_hits = sample.str.match(r"^DM_", na=False).sum()
        qid_hits = sample.str.match(r"^QID", na=False).sum()
        if dm_hits > 2 or qid_hits > 2:
            score += 3

    # "type" column with value "labels" is a strong data-file signal
    if "type" in cols_lower:
        idx = cols_lower.index("type")
        col_name = df.columns[idx]
        if df[col_name].str.lower().str.strip().eq("labels").any():
            score += 2

    return score


def _score_label_file(cols_lower: List[str], df: pd.DataFrame) -> int:
    score = 0

    # Check for label-file header keywords
    for kw in _LABEL_HEADER_KEYWORDS:
        # Allow partial match (e.g. column may end with "[DO NOT EDIT]")
        if any(kw in c for c in cols_lower):
            score += 2

    # entityKey column with patterns like "title:text", "description:text",
    # "contentHtml:contentHtml", "label:*", "topics:*"
    entity_key_col = _find_column_containing(df.columns, "entitykey")
    if entity_key_col is not None:
        sample = df[entity_key_col].head(30).str.strip()
        pattern_hits = sample.str.contains(r":", na=False).sum()
        if pattern_hits > 3:
            score += 3

    # widgetType column with known widget type strings
    widget_col = _find_column_containing(df.columns, "widgettype")
    if widget_col is not None:
        sample = df[widget_col].head(20).str.strip()
        reporting_hits = sample.str.contains(r"reporting\.|textanalytics\.|employeeinsights\.", na=False).sum()
        if reporting_hits > 1:
            score += 2

    return score


def _find_column_containing(columns: pd.Index, keyword: str) -> Optional[str]:
    """Return the first column whose lowered name contains *keyword*."""
    for c in columns:
        if keyword in c.lower():
            return c
    return None


def find_locale_columns(df: pd.DataFrame) -> List[str]:
    """Return column names that look like locale codes."""
    result = []
    for c in df.columns:
        normalized = c.strip().upper()
        if normalized in _LOCALE_CODES:
            result.append(c)
    return result


def detect_language_pair(
    df: pd.DataFrame,
    source_hint: Optional[str] = None,
    target_hint: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """
    Detect likely source and target language columns.

    Returns (source_col, target_col) or (None, None).
    """
    locale_cols = find_locale_columns(df)
    if not locale_cols:
        return None, None

    upper_map = {c.strip().upper(): c for c in locale_cols}

    if source_hint and target_hint:
        src = upper_map.get(source_hint.upper())
        tgt = upper_map.get(target_hint.upper())
        if src and tgt:
            return src, tgt

    # Heuristic: pick the locale pair with the most populated rows
    # Prefer EN and FR-CA as they are the most common for this project
    preferred_pairs = [
        ("EN", "FR-CA"),
        ("EN", "FR"),
        ("FR-CA", "EN"),
        ("FR", "EN"),
    ]
    for src_code, tgt_code in preferred_pairs:
        src = upper_map.get(src_code)
        tgt = upper_map.get(tgt_code)
        if src and tgt:
            # Check that at least one of them has content
            src_count = (df[src].str.strip() != "").sum()
            tgt_count = (df[tgt].str.strip() != "").sum()
            if src_count > 0 or tgt_count > 0:
                return src, tgt

    return None, None
