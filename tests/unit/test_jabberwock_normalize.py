"""Unit tests for Jabberwock namespace normalization.

Verifies the per-wabe normalizer registry: default (lowercase/strip/NFKC),
case-sensitive wabes, custom normalizer registration, and unknown wabe
fallthrough to default.

Test author: separate from builder (CI enforces separation).
"""

from __future__ import annotations

from yanantin.jabberwock.normalize import (
    normalize_gimble,
    register_normalizer,
)


# -- Default normalization -------------------------------------------------


class TestDefaultNormalization:
    def test_lowercase(self):
        assert normalize_gimble("github", "FsGeek") == "fsgeek"

    def test_strip_whitespace(self):
        assert normalize_gimble("github", "  fsgeek  ") == "fsgeek"

    def test_nfkc_normalization(self):
        """NFKC normalizes compatibility characters (e.g., fi ligature)."""
        # The fi ligature (U+FB01) should decompose to "fi" under NFKC
        assert normalize_gimble("github", "\ufb01le") == "file"

    def test_combined_operations(self):
        """Lowercase + strip + NFKC all applied together."""
        assert normalize_gimble("canvas", "  FsGeek  ") == "fsgeek"

    def test_empty_string(self):
        assert normalize_gimble("github", "") == ""

    def test_already_canonical(self):
        """Already lowercase, stripped, NFKC -- should pass through."""
        assert normalize_gimble("github", "fsgeek") == "fsgeek"

    def test_unicode_accents_preserved(self):
        """Accented characters are preserved (NFKC doesn't strip accents)."""
        result = normalize_gimble("github", "Cafe\u0301")
        # NFKC composes the accent: e + combining acute -> e-acute
        assert result == "caf\u00e9"


# -- Case-sensitive wabes --------------------------------------------------


class TestCaseSensitiveWabes:
    def test_filesystem_linux_preserves_case(self):
        assert normalize_gimble("filesystem-linux", "MyFile.txt") == "MyFile.txt"

    def test_filesystem_linux_strips_whitespace(self):
        assert normalize_gimble("filesystem-linux", "  MyFile.txt  ") == "MyFile.txt"

    def test_sha256_preserves_case(self):
        """SHA-256 hashes are hex and mixed case must be preserved."""
        hash_val = "AbCdEf0123456789"
        assert normalize_gimble("sha256", hash_val) == hash_val

    def test_content_hash_preserves_case(self):
        assert normalize_gimble("content-hash", "DeadBeef") == "DeadBeef"

    def test_base64_preserves_case(self):
        """Base64 is case-sensitive by definition."""
        b64 = "SGVsbG8gV29ybGQ="
        assert normalize_gimble("base64", b64) == b64


# -- Custom normalizer registration ---------------------------------------


class TestCustomNormalizer:
    def test_register_custom_normalizer(self):
        """register_normalizer adds a wabe-specific normalizer."""

        def upper_normalizer(gimble: str) -> str:
            return gimble.upper()

        register_normalizer("test-upper-wabe", upper_normalizer)
        assert normalize_gimble("test-upper-wabe", "hello") == "HELLO"

    def test_custom_normalizer_overrides_default(self):
        """Custom normalizer replaces the default for that wabe."""

        def reverse_normalizer(gimble: str) -> str:
            return gimble[::-1]

        register_normalizer("test-reverse-wabe", reverse_normalizer)
        assert normalize_gimble("test-reverse-wabe", "abc") == "cba"


# -- Unknown wabes ---------------------------------------------------------


class TestUnknownWabes:
    def test_unknown_wabe_uses_default(self):
        """Wabes not in the registry fall through to default normalization."""
        assert normalize_gimble("nonexistent-wabe-xyz", "FsGeek") == "fsgeek"

    def test_unknown_wabe_strips(self):
        assert normalize_gimble("nonexistent-wabe-xyz", "  spaced  ") == "spaced"

    def test_unknown_wabe_lowercases(self):
        assert normalize_gimble("totally-new-wabe", "UPPER") == "upper"
