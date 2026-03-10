"""
translator.py — Translation engine abstraction with provider pattern.

Supports:
  - MockTranslator (for tests)
  - AnthropicTranslator (via Anthropic API)

Easy to add new providers by subclassing TranslationProvider.
"""

from __future__ import annotations

import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Anthropic SDK import — optional at module level
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


@dataclass
class TranslationRequest:
    """A single translation request."""
    source_text: str
    source_lang: str
    target_lang: str
    context: Optional[str] = None  # e.g. "survey question", "choice label"


@dataclass
class TranslationResult:
    """A single translation result."""
    source_text: str
    translated_text: str
    provider: str
    success: bool = True
    error: Optional[str] = None


class TranslationProvider(ABC):
    """Abstract base for translation providers."""

    @abstractmethod
    def translate_batch(
        self, requests: List[TranslationRequest]
    ) -> List[TranslationResult]:
        """Translate a batch of requests."""
        ...

    @abstractmethod
    def translate_single(self, request: TranslationRequest) -> TranslationResult:
        """Translate a single request."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class MockTranslator(TranslationProvider):
    """Mock translator for testing — prefixes with [TRANSLATED]."""

    def translate_batch(
        self, requests: List[TranslationRequest]
    ) -> List[TranslationResult]:
        return [self.translate_single(r) for r in requests]

    def translate_single(self, request: TranslationRequest) -> TranslationResult:
        return TranslationResult(
            source_text=request.source_text,
            translated_text=f"[FR-CA] {request.source_text}",
            provider=self.name,
        )

    @property
    def name(self) -> str:
        return "mock"


class AnthropicTranslator(TranslationProvider):
    """Translation via Anthropic Claude API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_batch_size: int = 25,
        max_retries: int = 3,
    ) -> None:
        if not HAS_ANTHROPIC:
            raise ImportError(
                "anthropic package is required. Install with: pip install anthropic"
            )
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY must be set in environment or passed directly"
            )
        self._client = anthropic.Anthropic(api_key=self._api_key)
        self._model = model
        self._max_batch_size = max_batch_size
        self._max_retries = max_retries

    def translate_batch(
        self, requests: List[TranslationRequest]
    ) -> List[TranslationResult]:
        """
        Translate a batch by grouping into sub-batches.

        Uses a numbered-list prompt format for batched translation
        to maintain source-to-target mapping.
        """
        if not requests:
            return []

        if len(requests) == 1:
            return [self.translate_single(requests[0])]

        results: List[TranslationResult] = []
        for i in range(0, len(requests), self._max_batch_size):
            chunk = requests[i:i + self._max_batch_size]
            chunk_results = self._translate_chunk(chunk)
            results.extend(chunk_results)

        return results

    def translate_single(self, request: TranslationRequest) -> TranslationResult:
        target_name = _lang_display_name(request.target_lang)
        source_name = _lang_display_name(request.source_lang)

        prompt = (
            f"Translate the following text from {source_name} to {target_name}.\n"
            f"Rules:\n"
            f"- Translate ONLY the visible human-readable text\n"
            f"- Preserve any placeholders like __QTX_PROT_N__ exactly as-is\n"
            f"- Preserve HTML tags exactly\n"
            f"- Preserve tone and meaning\n"
            f"- Use Canadian French if target is French\n"
            f"- Do not add explanations — return only the translated text\n"
            f"- Do not embellish or reformat\n\n"
            f"Text to translate:\n{request.source_text}"
        )

        for attempt in range(self._max_retries):
            try:
                message = self._client.messages.create(
                    model=self._model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                )
                translated = message.content[0].text.strip()
                return TranslationResult(
                    source_text=request.source_text,
                    translated_text=translated,
                    provider=self.name,
                )
            except Exception as e:
                if attempt == self._max_retries - 1:
                    return TranslationResult(
                        source_text=request.source_text,
                        translated_text=request.source_text,
                        provider=self.name,
                        success=False,
                        error=str(e),
                    )
                time.sleep(2 ** attempt)

        # Should not reach here, but safety fallback
        return TranslationResult(
            source_text=request.source_text,
            translated_text=request.source_text,
            provider=self.name,
            success=False,
            error="Max retries exceeded",
        )

    def _translate_chunk(
        self, chunk: List[TranslationRequest]
    ) -> List[TranslationResult]:
        """Translate a chunk using numbered-list format."""
        if not chunk:
            return []

        target_name = _lang_display_name(chunk[0].target_lang)
        source_name = _lang_display_name(chunk[0].source_lang)

        lines = []
        for i, req in enumerate(chunk, 1):
            lines.append(f"{i}. {req.source_text}")

        prompt = (
            f"Translate each numbered line from {source_name} to {target_name}.\n"
            f"Rules:\n"
            f"- Translate ONLY the visible human-readable text\n"
            f"- Preserve any placeholders like __QTX_PROT_N__ exactly as-is\n"
            f"- Preserve HTML tags exactly\n"
            f"- Preserve tone and meaning\n"
            f"- Use Canadian French if target is French\n"
            f"- Do not add explanations\n"
            f"- Do not embellish or reformat\n"
            f"- Return ONLY numbered translations in the same order\n"
            f"- Each line must start with the number followed by a period\n\n"
            + "\n".join(lines)
        )

        for attempt in range(self._max_retries):
            try:
                message = self._client.messages.create(
                    model=self._model,
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}],
                )
                response_text = message.content[0].text.strip()
                parsed = self._parse_numbered_response(response_text, chunk)
                if parsed:
                    return parsed
                # If parsing fails, fall back to individual translation
                break
            except Exception as e:
                if attempt == self._max_retries - 1:
                    # Fall back to individual translations
                    break
                time.sleep(2 ** attempt)

        # Fallback: translate individually
        return [self.translate_single(req) for req in chunk]

    def _parse_numbered_response(
        self, response: str, original_requests: List[TranslationRequest]
    ) -> Optional[List[TranslationResult]]:
        """Parse a numbered-list response back into individual results."""
        lines = response.strip().split("\n")
        results: Dict[int, str] = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = re.match(r"^(\d+)\.\s*(.*)", line)
            if match:
                num = int(match.group(1))
                text = match.group(2).strip()
                results[num] = text

        if len(results) != len(original_requests):
            return None

        output: List[TranslationResult] = []
        for i, req in enumerate(original_requests, 1):
            if i not in results:
                return None
            output.append(TranslationResult(
                source_text=req.source_text,
                translated_text=results[i],
                provider=self.name,
            ))

        return output

    @property
    def name(self) -> str:
        return "anthropic"


def get_translator(provider: str = "auto", api_key: Optional[str] = None) -> TranslationProvider:
    """
    Factory function to get a translation provider.

    *provider* can be: "auto", "anthropic", "mock".
    "auto" tries Anthropic first, falls back to mock.
    """
    if provider == "mock":
        return MockTranslator()

    if provider == "anthropic":
        return AnthropicTranslator(api_key=api_key)

    # Auto: try anthropic, fall back to mock
    if provider == "auto":
        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if key and HAS_ANTHROPIC:
            try:
                return AnthropicTranslator(api_key=key)
            except Exception:
                pass
        return MockTranslator()

    raise ValueError(f"Unknown translation provider: {provider}")


def _lang_display_name(code: str) -> str:
    """Map a locale code to a human-readable language name."""
    mapping = {
        "EN": "English",
        "FR": "French",
        "FR-CA": "Canadian French (French spoken in Canada)",
        "ES": "Spanish",
        "DE": "German",
        "IT": "Italian",
        "PT": "Portuguese",
        "PT-BR": "Brazilian Portuguese",
        "EN-GB": "British English",
    }
    return mapping.get(code.upper(), code)
