"""
exporter.py — Export translated DataFrame to UTF-8 CSV.

Handles BOM option, quoting, and filename generation.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import List, Optional

import pandas as pd

from .rules import CellTranslation, Provenance


def export_translated_csv(
    df: pd.DataFrame,
    original_filename: str,
    use_bom: bool = True,
) -> bytes:
    """
    Export DataFrame to UTF-8 CSV bytes.

    *use_bom*: if True, prepend UTF-8 BOM (recommended for Excel compatibility).
    """
    buf = io.StringIO()
    df.to_csv(buf, index=False, encoding="utf-8")
    csv_text = buf.getvalue()

    if use_bom:
        return ("\ufeff" + csv_text).encode("utf-8")
    return csv_text.encode("utf-8")


def get_translated_filename(original_filename: str) -> str:
    """Generate output filename for the translated file."""
    stem = Path(original_filename).stem
    return f"{stem}_translated_ready_for_qualtrics.csv"


def get_notes_filename(original_filename: str) -> str:
    """Generate output filename for the notes report."""
    stem = Path(original_filename).stem
    return f"{stem}_translation_notes.csv"


def build_notes_report(
    translations: List[CellTranslation],
    diagnostics: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Build a notes/flags DataFrame from translation results.
    """
    rows = []

    for t in translations:
        if t.notes or t.provenance in (
            Provenance.KEPT_ORIGINAL_FLAGGED,
            Provenance.TRANSLATION_ERROR,
        ):
            rows.append({
                "row": t.row_index,
                "column": t.column_name,
                "provenance": t.provenance.value,
                "cell_type": t.cell_type.value,
                "original": _truncate(t.original, 100),
                "translated": _truncate(t.translated, 100),
                "notes": " | ".join(t.notes) if t.notes else "",
            })

    # Also include provenance summary rows
    prov_counts: dict[str, int] = {}
    for t in translations:
        key = t.provenance.value
        prov_counts[key] = prov_counts.get(key, 0) + 1

    for prov, count in sorted(prov_counts.items()):
        rows.append({
            "row": "",
            "column": "SUMMARY",
            "provenance": prov,
            "cell_type": "",
            "original": "",
            "translated": "",
            "notes": f"Total cells: {count}",
        })

    if diagnostics:
        for key, value in diagnostics.items():
            rows.append({
                "row": "",
                "column": "DIAGNOSTIC",
                "provenance": "",
                "cell_type": "",
                "original": key,
                "translated": str(value),
                "notes": "",
            })

    return pd.DataFrame(rows)


def export_notes_csv(notes_df: pd.DataFrame, use_bom: bool = True) -> bytes:
    """Export notes DataFrame to UTF-8 CSV bytes."""
    buf = io.StringIO()
    notes_df.to_csv(buf, index=False, encoding="utf-8")
    csv_text = buf.getvalue()

    if use_bom:
        return ("\ufeff" + csv_text).encode("utf-8")
    return csv_text.encode("utf-8")


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."
