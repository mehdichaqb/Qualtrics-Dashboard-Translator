"""
protector.py — Detect and protect technical tokens before translation.

Replaces protected spans with stable placeholders, then restores them
exactly after translation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# ── Protected-token patterns (order matters: more specific first) ────────

_TOKEN_PATTERNS: List[re.Pattern] = [
    # Qualtrics piped text / embedded data / loops & merges
    re.compile(r"\$\{[^}]+\}"),
    # HTML tags (including self-closing and attributes)
    re.compile(r"</?[a-zA-Z][^>]*>"),
    # HTML entities
    re.compile(r"&(?:#\d+|#x[\da-fA-F]+|[a-zA-Z]+);"),
    # Qualtrics QID / MQ / DB style identifiers (standalone or in technical context)
    re.compile(r"\b(?:QID\d+\w*|MQ\d+\w*|DB_\w+)\b"),
    # Variable-like identifiers that look like internal codes
    # e.g. DM_abc123, esdc_xxx_dashboard, Widget_xxx
    re.compile(r"\b(?:DM_[a-zA-Z0-9]+|Widget_[a-zA-Z0-9\-]+)\b"),
    # UUID-style strings (8-4-4-4-12)
    re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
]


@dataclass
class ProtectionResult:
    """Result of protecting tokens in a string."""
    protected_text: str
    placeholders: Dict[str, str] = field(default_factory=dict)
    # Maps placeholder → original token


def protect_tokens(text: str) -> ProtectionResult:
    """
    Replace protected spans with numbered placeholders.

    Returns a ProtectionResult with the modified text and
    a mapping from placeholder IDs back to original tokens.
    """
    if not text or not text.strip():
        return ProtectionResult(protected_text=text)

    placeholders: Dict[str, str] = {}
    counter = 0
    result = text

    # Collect all matches with their spans to avoid overlapping replacements
    all_matches: List[Tuple[int, int, str]] = []

    for pattern in _TOKEN_PATTERNS:
        for m in pattern.finditer(result):
            # Check for overlap with existing matches
            start, end = m.start(), m.end()
            overlaps = False
            for ex_start, ex_end, _ in all_matches:
                if start < ex_end and end > ex_start:
                    overlaps = True
                    break
            if not overlaps:
                all_matches.append((start, end, m.group()))

    # Sort by position (right to left) so replacements don't shift indices
    all_matches.sort(key=lambda x: x[0], reverse=True)

    for start, end, token in all_matches:
        placeholder = f"__QTX_PROT_{counter}__"
        placeholders[placeholder] = token
        result = result[:start] + placeholder + result[end:]
        counter += 1

    return ProtectionResult(protected_text=result, placeholders=placeholders)


def restore_tokens(text: str, placeholders: Dict[str, str]) -> str:
    """
    Restore protected tokens from placeholders.

    The restored tokens are byte-for-byte identical to the originals.
    """
    result = text
    for placeholder, original in placeholders.items():
        result = result.replace(placeholder, original)
    return result


def validate_restoration(original: str, translated: str, placeholders: Dict[str, str]) -> List[str]:
    """
    Validate that all protected tokens were restored correctly.

    Returns a list of issues (empty if all tokens are intact).
    """
    issues: List[str] = []

    for placeholder, original_token in placeholders.items():
        if placeholder in translated:
            issues.append(
                f"Placeholder {placeholder} was not restored "
                f"(original token: {original_token!r})"
            )

        if original_token in original and original_token not in translated:
            issues.append(
                f"Protected token {original_token!r} is missing from translated text"
            )

    return issues


def is_fully_protected(text: str) -> bool:
    """
    Check if the entire text is a single protected token (no translatable content).
    """
    stripped = text.strip()
    if not stripped:
        return True

    for pattern in _TOKEN_PATTERNS:
        if pattern.fullmatch(stripped):
            return True

    return False


def extract_translatable_segments(text: str) -> List[Tuple[str, bool]]:
    """
    Split text into segments: (segment_text, is_protected).

    Useful for understanding the structure of mixed content.
    """
    if not text:
        return []

    # Find all protected spans
    protected_spans: List[Tuple[int, int]] = []
    for pattern in _TOKEN_PATTERNS:
        for m in pattern.finditer(text):
            start, end = m.start(), m.end()
            # Skip overlaps
            overlaps = False
            for ps, pe in protected_spans:
                if start < pe and end > ps:
                    overlaps = True
                    break
            if not overlaps:
                protected_spans.append((start, end))

    if not protected_spans:
        return [(text, False)]

    protected_spans.sort()
    segments: List[Tuple[str, bool]] = []
    pos = 0

    for start, end in protected_spans:
        if pos < start:
            segments.append((text[pos:start], False))
        segments.append((text[start:end], True))
        pos = end

    if pos < len(text):
        segments.append((text[pos:], False))

    return segments
