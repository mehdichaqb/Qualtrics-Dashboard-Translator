"""
reference_memory.py — Build and query translation memory from reference files.

Loads reference data files and label files, extracts bilingual pairs,
and provides lookup methods with exact / normalized matching.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .detector import FileType, detect_file_type, find_locale_columns


@dataclass
class MemoryMatch:
    """A match from translation memory."""
    source: str
    translation: str
    match_type: str  # "exact" | "normalized" | "fuzzy"
    reference_origin: str  # "data_file" | "label_file"
    confidence: float = 1.0


@dataclass
class ConflictReport:
    """Report of conflicting translations for the same source."""
    source: str
    translations: List[Tuple[str, str]]  # (translation, origin)


class TranslationMemory:
    """
    In-memory translation dictionary built from reference files.

    Supports exact match, normalized match, and session-cache.
    """

    def __init__(self) -> None:
        # source_text → list of (translation, origin)
        self._exact: Dict[str, List[Tuple[str, str]]] = {}
        # normalized_key → list of (source_text, translation, origin)
        self._normalized: Dict[str, List[Tuple[str, str, str]]] = {}
        # Session cache: source → translation
        self._session_cache: Dict[str, str] = {}
        # Conflict tracking
        self.conflicts: List[ConflictReport] = []
        # Stats
        self.data_file_entries: int = 0
        self.label_file_entries: int = 0

    def load_reference(
        self,
        df: pd.DataFrame,
        file_type: FileType,
        source_col: str,
        target_col: str,
    ) -> Dict[str, str]:
        """
        Load bilingual pairs from a reference DataFrame.

        Returns a dict of diagnostics/notes.
        """
        origin = "data_file" if file_type == FileType.DATA_FILE else "label_file"
        notes: Dict[str, str] = {}
        loaded = 0

        for _, row in df.iterrows():
            src = str(row.get(source_col, "")).strip()
            tgt = str(row.get(target_col, "")).strip()

            if not src or not tgt:
                continue
            if src == tgt and _looks_like_code(src):
                continue

            # Exact entry
            if src not in self._exact:
                self._exact[src] = []
            self._exact[src].append((tgt, origin))

            # Normalized entry
            norm_key = _normalize(src)
            if norm_key not in self._normalized:
                self._normalized[norm_key] = []
            self._normalized[norm_key].append((src, tgt, origin))

            loaded += 1

        if file_type == FileType.DATA_FILE:
            self.data_file_entries += loaded
        else:
            self.label_file_entries += loaded

        notes["loaded_pairs"] = str(loaded)
        notes["source_col"] = source_col
        notes["target_col"] = target_col

        # Detect conflicts
        self._detect_conflicts()

        return notes

    def lookup(
        self,
        source_text: str,
        prefer_origin: Optional[str] = None,
    ) -> Optional[MemoryMatch]:
        """
        Look up a translation for *source_text*.

        Priority: exact → normalized → session cache.
        *prefer_origin* can be "data_file" or "label_file".
        """
        # 1. Exact match
        match = self._exact_lookup(source_text, prefer_origin)
        if match:
            return match

        # 2. Normalized match
        match = self._normalized_lookup(source_text, prefer_origin)
        if match:
            return match

        # 3. Session cache
        if source_text in self._session_cache:
            return MemoryMatch(
                source=source_text,
                translation=self._session_cache[source_text],
                match_type="session_cache",
                reference_origin="session",
                confidence=0.95,
            )

        return None

    def add_to_session_cache(self, source: str, translation: str) -> None:
        """Add a fresh translation to the session cache."""
        self._session_cache[source] = translation

    def get_session_cache_size(self) -> int:
        return len(self._session_cache)

    def _exact_lookup(
        self, source_text: str, prefer_origin: Optional[str]
    ) -> Optional[MemoryMatch]:
        entries = self._exact.get(source_text)
        if not entries:
            return None

        # If preferred origin matches, use it
        if prefer_origin:
            for tgt, origin in entries:
                if origin == prefer_origin:
                    return MemoryMatch(
                        source=source_text,
                        translation=tgt,
                        match_type="exact",
                        reference_origin=origin,
                    )

        # Use first entry
        tgt, origin = entries[0]
        return MemoryMatch(
            source=source_text,
            translation=tgt,
            match_type="exact",
            reference_origin=origin,
        )

    def _normalized_lookup(
        self, source_text: str, prefer_origin: Optional[str]
    ) -> Optional[MemoryMatch]:
        norm_key = _normalize(source_text)
        entries = self._normalized.get(norm_key)
        if not entries:
            return None

        if prefer_origin:
            for src, tgt, origin in entries:
                if origin == prefer_origin:
                    return MemoryMatch(
                        source=source_text,
                        translation=tgt,
                        match_type="normalized",
                        reference_origin=origin,
                        confidence=0.98,
                    )

        src, tgt, origin = entries[0]
        return MemoryMatch(
            source=source_text,
            translation=tgt,
            match_type="normalized",
            reference_origin=origin,
            confidence=0.98,
        )

    def _detect_conflicts(self) -> None:
        """Identify source texts with conflicting translations."""
        self.conflicts.clear()
        for src, entries in self._exact.items():
            unique_translations = set()
            for tgt, _ in entries:
                unique_translations.add(tgt)
            if len(unique_translations) > 1:
                self.conflicts.append(ConflictReport(
                    source=src,
                    translations=entries,
                ))


def build_memory_from_reference(
    df: pd.DataFrame,
    memory: TranslationMemory,
    source_lang: str = "EN",
    target_lang: str = "FR-CA",
) -> Dict[str, str]:
    """
    Auto-detect file type and language columns, then load into memory.

    Returns diagnostics dict.
    """
    file_type = detect_file_type(df)
    locale_cols = find_locale_columns(df)

    # Try to find source and target columns
    upper_map = {c.strip().upper(): c for c in locale_cols}

    source_col = upper_map.get(source_lang.upper())
    target_col = upper_map.get(target_lang.upper())

    notes: Dict[str, str] = {
        "detected_type": file_type.value,
        "locale_columns_found": str(len(locale_cols)),
    }

    if not source_col:
        notes["warning"] = f"Source language column '{source_lang}' not found"
        return notes
    if not target_col:
        notes["warning"] = f"Target language column '{target_lang}' not found"
        return notes

    load_notes = memory.load_reference(df, file_type, source_col, target_col)
    notes.update(load_notes)
    return notes


def _normalize(text: str) -> str:
    """Normalize text for fuzzy-ish matching (whitespace, case)."""
    result = text.strip()
    result = re.sub(r"\s+", " ", result)
    result = result.lower()
    return result


def _looks_like_code(text: str) -> bool:
    """Heuristic: does this text look like an internal code?"""
    if re.match(r"^[A-Z_][A-Z0-9_]*$", text):
        return True
    if re.match(r"^[a-f0-9\-]{36}$", text):
        return True
    if re.match(r"^(?:QID|DM_|SV_|MQ)\w+$", text):
        return True
    return False
