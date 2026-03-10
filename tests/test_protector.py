"""Tests for token protection and restoration."""

import pytest

from processor.protector import (
    ProtectionResult,
    extract_translatable_segments,
    is_fully_protected,
    protect_tokens,
    restore_tokens,
    validate_restoration,
)


class TestProtectTokens:
    """Test token detection and replacement."""

    def test_qualtrics_embedded_data(self):
        text = "Hello ${e://Field/FirstName}, welcome!"
        result = protect_tokens(text)
        assert "${e://Field/FirstName}" not in result.protected_text
        assert "__QTX_PROT_" in result.protected_text
        assert len(result.placeholders) == 1

    def test_qualtrics_question_reference(self):
        text = "Your answer was ${q://QID42/ChoiceTextEntryValue}"
        result = protect_tokens(text)
        assert "${q://QID42/ChoiceTextEntryValue}" not in result.protected_text
        assert len(result.placeholders) >= 1

    def test_qualtrics_loop_merge(self):
        text = "Item: ${lm://Field/ItemName}"
        result = protect_tokens(text)
        assert "${lm://Field/ItemName}" not in result.protected_text

    def test_html_tags_preserved(self):
        text = '<p style="color: red;">Important</p>'
        result = protect_tokens(text)
        assert "<p" not in result.protected_text
        assert "</p>" not in result.protected_text
        assert "Important" in result.protected_text

    def test_html_entities(self):
        text = "Tom &amp; Jerry &gt; others"
        result = protect_tokens(text)
        assert "&amp;" not in result.protected_text
        assert "&gt;" not in result.protected_text

    def test_mixed_tokens_and_text(self):
        text = 'Hello ${e://Field/Name}, <b>welcome</b> to the survey!'
        result = protect_tokens(text)
        # Tokens replaced
        assert "${e://Field/Name}" not in result.protected_text
        assert "<b>" not in result.protected_text
        # Text preserved
        assert "Hello" in result.protected_text
        assert "welcome" in result.protected_text
        assert "survey" in result.protected_text

    def test_empty_string(self):
        result = protect_tokens("")
        assert result.protected_text == ""
        assert len(result.placeholders) == 0

    def test_no_tokens(self):
        text = "Just plain text here"
        result = protect_tokens(text)
        assert result.protected_text == text
        assert len(result.placeholders) == 0

    def test_complex_html_with_qualtrics(self):
        text = (
            '<p dir="ltr" style="text-align: center;">'
            '<span style="font-size: 24px;">Awareness and Value</span></p>'
        )
        result = protect_tokens(text)
        assert "Awareness and Value" in result.protected_text
        assert "<p" not in result.protected_text


class TestRestoreTokens:
    """Test token restoration."""

    def test_basic_restoration(self):
        text = "Hello ${e://Field/FirstName}!"
        protected = protect_tokens(text)
        # Simulate translation of the non-protected parts
        translated = protected.protected_text.replace("Hello", "Bonjour")
        restored = restore_tokens(translated, protected.placeholders)
        assert "${e://Field/FirstName}" in restored
        assert "Bonjour" in restored

    def test_multiple_tokens_restored(self):
        text = "${e://Field/A} and ${e://Field/B}"
        protected = protect_tokens(text)
        restored = restore_tokens(protected.protected_text, protected.placeholders)
        assert restored == text

    def test_html_restoration(self):
        text = "<b>Bold</b> and <i>italic</i>"
        protected = protect_tokens(text)
        restored = restore_tokens(protected.protected_text, protected.placeholders)
        assert "<b>" in restored
        assert "</b>" in restored
        assert "<i>" in restored
        assert "</i>" in restored


class TestValidateRestoration:
    """Test validation of token restoration."""

    def test_valid_restoration(self):
        original = "Hello ${e://Field/Name}!"
        translated = "Bonjour ${e://Field/Name}!"
        # No placeholders remaining means all were restored
        issues = validate_restoration(original, translated, {})
        assert len(issues) == 0

    def test_missing_token(self):
        original = "Hello ${e://Field/Name}!"
        translated = "Bonjour !"
        placeholders = {"__QTX_PROT_0__": "${e://Field/Name}"}
        issues = validate_restoration(original, translated, placeholders)
        assert len(issues) > 0

    def test_unreplaced_placeholder(self):
        original = "Hello ${e://Field/Name}!"
        translated = "Bonjour __QTX_PROT_0__!"
        placeholders = {"__QTX_PROT_0__": "${e://Field/Name}"}
        issues = validate_restoration(original, translated, placeholders)
        assert any("not restored" in i for i in issues)


class TestIsFullyProtected:
    """Test full-protection detection."""

    def test_qualtrics_expression(self):
        assert is_fully_protected("${e://Field/Name}") is True

    def test_plain_text(self):
        assert is_fully_protected("Hello world") is False

    def test_empty(self):
        assert is_fully_protected("") is True
        assert is_fully_protected("   ") is True


class TestExtractTranslatableSegments:
    """Test segment extraction."""

    def test_mixed_content(self):
        text = "Hello <b>world</b>!"
        segments = extract_translatable_segments(text)
        assert len(segments) >= 3
        # Check we have both protected and non-protected
        has_protected = any(is_prot for _, is_prot in segments)
        has_translatable = any(not is_prot for _, is_prot in segments)
        assert has_protected
        assert has_translatable

    def test_pure_text(self):
        segments = extract_translatable_segments("Just text")
        assert len(segments) == 1
        assert segments[0] == ("Just text", False)

    def test_empty(self):
        segments = extract_translatable_segments("")
        assert len(segments) == 0
