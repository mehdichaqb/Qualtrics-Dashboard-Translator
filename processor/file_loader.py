"""
file_loader.py — Load CSV and XLSX files into pandas DataFrames.

Handles encoding detection, BOM stripping, and malformed-file resilience.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional, Union

import chardet
import pandas as pd


def detect_encoding(raw_bytes: bytes) -> str:
    """Return best-guess encoding for *raw_bytes*."""
    result = chardet.detect(raw_bytes)
    encoding = (result.get("encoding") or "utf-8").lower()
    # chardet sometimes returns 'ascii' for UTF-8 without high bytes
    if encoding == "ascii":
        encoding = "utf-8"
    return encoding


def load_file(
    file_source: Union[str, Path, io.BytesIO],
    file_name: Optional[str] = None,
) -> pd.DataFrame:
    """
    Load a CSV or XLSX into a DataFrame.

    *file_source* can be a file path (str/Path) or a BytesIO stream
    (e.g. from Streamlit's file uploader).  When a stream is given,
    *file_name* is required so we can choose the correct parser.

    Returns a DataFrame with **all columns as strings** and NaN replaced
    by empty strings (to avoid accidental float 'nan' pollution).
    """
    if isinstance(file_source, (str, Path)):
        path = Path(file_source)
        file_name = file_name or path.name
        raw_bytes = path.read_bytes()
    else:
        raw_bytes = file_source.read()
        file_source.seek(0)  # rewind for pandas
        if not file_name:
            raise ValueError("file_name is required when file_source is a stream")

    ext = Path(file_name).suffix.lower()

    if ext in (".xlsx", ".xls"):
        df = _load_xlsx(raw_bytes)
    elif ext == ".csv":
        df = _load_csv(raw_bytes)
    else:
        raise ValueError(f"Unsupported file extension: {ext}")

    # Coerce every cell to str; replace NaN → ""
    df = df.fillna("").astype(str)
    return df


def _load_csv(raw_bytes: bytes) -> pd.DataFrame:
    """Parse CSV bytes with encoding detection."""
    encoding = detect_encoding(raw_bytes)
    text = raw_bytes.decode(encoding, errors="replace")

    # Strip UTF-8 BOM if present
    if text.startswith("\ufeff"):
        text = text[1:]

    return pd.read_csv(
        io.StringIO(text),
        dtype=str,
        keep_default_na=False,
        na_filter=False,
    )


def _load_xlsx(raw_bytes: bytes) -> pd.DataFrame:
    """Parse XLSX bytes."""
    return pd.read_excel(
        io.BytesIO(raw_bytes),
        dtype=str,
        keep_default_na=False,
        na_filter=False,
        engine="openpyxl",
    )
