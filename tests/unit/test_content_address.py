"""Unit tests for content addressing module.

Tests content_hash normalization, ContentIndex building and querying,
and the deduplicate_report output format.

This module was not written by the test author.
"""

from pathlib import Path

import pytest

from yanantin.apacheta.content_address import (
    HASH_PREFIX_LENGTH,
    ContentIndex,
    content_hash,
    deduplicate_report,
)


class TestContentHash:
    """Tests for the content_hash() function."""

    def test_same_content_produces_same_hash(self):
        """Identical strings must produce identical hashes."""
        text = "The cairn accumulates stones."
        assert content_hash(text) == content_hash(text)

    def test_different_content_produces_different_hash(self):
        """Distinct content must produce distinct hashes."""
        assert content_hash("alpha") != content_hash("beta")

    def test_trailing_spaces_normalized(self):
        """Trailing spaces on lines should not affect the hash."""
        clean = "line one\nline two"
        trailing = "line one   \nline two  "
        assert content_hash(clean) == content_hash(trailing)

    def test_crlf_vs_lf_normalized(self):
        """Windows (\\r\\n) and Unix (\\n) line endings produce the same hash."""
        unix = "first\nsecond\nthird"
        windows = "first\r\nsecond\r\nthird"
        assert content_hash(unix) == content_hash(windows)

    def test_bare_cr_normalized(self):
        """Old Mac (\\r) line endings produce the same hash as \\n."""
        unix = "first\nsecond"
        mac = "first\rsecond"
        assert content_hash(unix) == content_hash(mac)

    def test_runs_of_blank_lines_collapsed(self):
        """Multiple consecutive blank lines collapse to a single blank line."""
        single_blank = "para one\n\npara two"
        triple_blank = "para one\n\n\n\npara two"
        assert content_hash(single_blank) == content_hash(triple_blank)

    def test_leading_trailing_blank_lines_stripped(self):
        """Leading and trailing blank lines are removed before hashing."""
        clean = "content"
        padded = "\n\n\ncontent\n\n\n"
        assert content_hash(clean) == content_hash(padded)

    def test_combined_normalization(self):
        """All normalization steps applied together produce a stable hash."""
        canonical = "line one\n\nline two"
        messy = "\r\n  \r\nline one   \r\n\r\n\r\n\r\nline two  \r\n\r\n"
        assert content_hash(canonical) == content_hash(messy)

    def test_empty_string_has_stable_hash(self):
        """Empty string produces a deterministic, repeatable hash."""
        h1 = content_hash("")
        h2 = content_hash("")
        assert h1 == h2
        # Also verify it is a valid hash (not empty or None)
        assert len(h1) == HASH_PREFIX_LENGTH

    def test_whitespace_only_equals_empty(self):
        """A string of only whitespace normalizes to the same hash as empty."""
        assert content_hash("") == content_hash("   \n\n  \r\n  ")

    def test_hash_is_16_hex_characters(self):
        """Hash output must be exactly 16 lowercase hexadecimal characters."""
        h = content_hash("test document content")
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_length_matches_constant(self):
        """Hash length matches HASH_PREFIX_LENGTH."""
        h = content_hash("anything")
        assert len(h) == HASH_PREFIX_LENGTH


class TestContentIndex:
    """Tests for the ContentIndex class."""

    def test_build_from_directory_counts_correct(self, tmp_path: Path):
        """Index built from a directory has one entry per unique-content file."""
        (tmp_path / "a.md").write_text("document alpha", encoding="utf-8")
        (tmp_path / "b.md").write_text("document beta", encoding="utf-8")
        (tmp_path / "c.md").write_text("document gamma", encoding="utf-8")

        index = ContentIndex.from_directory(tmp_path)
        assert len(index) == 3

    def test_build_from_directory_skips_non_md(self, tmp_path: Path):
        """Only .md files are indexed; other extensions are ignored."""
        (tmp_path / "doc.md").write_text("markdown", encoding="utf-8")
        (tmp_path / "data.txt").write_text("plain text", encoding="utf-8")
        (tmp_path / "script.py").write_text("print('hello')", encoding="utf-8")

        index = ContentIndex.from_directory(tmp_path)
        assert len(index) == 1

    def test_build_from_directory_skips_hidden_files(self, tmp_path: Path):
        """Files starting with a dot are skipped."""
        (tmp_path / "visible.md").write_text("visible", encoding="utf-8")
        (tmp_path / ".hidden.md").write_text("hidden", encoding="utf-8")

        index = ContentIndex.from_directory(tmp_path)
        assert len(index) == 1

    def test_build_from_nonexistent_directory(self, tmp_path: Path):
        """Non-existent directory returns empty index without error."""
        index = ContentIndex.from_directory(tmp_path / "does_not_exist")
        assert len(index) == 0

    def test_build_from_directory_recursive(self, tmp_path: Path):
        """Index recurses into subdirectories."""
        sub = tmp_path / "subdir"
        sub.mkdir()
        (tmp_path / "top.md").write_text("top-level", encoding="utf-8")
        (sub / "nested.md").write_text("nested content", encoding="utf-8")

        index = ContentIndex.from_directory(tmp_path)
        assert len(index) == 2

    def test_has_content_true_for_existing(self, tmp_path: Path):
        """has_content() returns True when the content exists in the index."""
        (tmp_path / "doc.md").write_text("unique content here", encoding="utf-8")
        index = ContentIndex.from_directory(tmp_path)
        assert index.has_content("unique content here") is True

    def test_has_content_false_for_new(self, tmp_path: Path):
        """has_content() returns False for content not in the index."""
        (tmp_path / "doc.md").write_text("existing content", encoding="utf-8")
        index = ContentIndex.from_directory(tmp_path)
        assert index.has_content("completely different content") is False

    def test_has_content_respects_normalization(self, tmp_path: Path):
        """has_content() finds content even with different whitespace."""
        (tmp_path / "doc.md").write_text("line one\nline two", encoding="utf-8")
        index = ContentIndex.from_directory(tmp_path)
        assert index.has_content("line one  \r\nline two  \r\n") is True

    def test_register_adds_file_and_returns_hash(self, tmp_path: Path):
        """register() adds a file to the index and returns its content hash."""
        filepath = tmp_path / "new.md"
        filepath.write_text("brand new content", encoding="utf-8")

        index = ContentIndex()
        h = index.register(filepath)

        assert len(h) == HASH_PREFIX_LENGTH
        assert len(index) == 1
        assert index.has_content("brand new content") is True

    def test_register_unreadable_file_returns_empty(self, tmp_path: Path):
        """register() returns empty string for a file that does not exist."""
        index = ContentIndex()
        h = index.register(tmp_path / "nonexistent.md")
        assert h == ""
        assert len(index) == 0

    def test_register_same_file_twice_no_duplicate_paths(self, tmp_path: Path):
        """Registering the same file twice does not create duplicate path entries."""
        filepath = tmp_path / "doc.md"
        filepath.write_text("content", encoding="utf-8")

        index = ContentIndex()
        index.register(filepath)
        index.register(filepath)

        # Only one unique hash
        assert len(index) == 1
        # Only one path for that hash
        paths = index.lookup("content")
        assert len(paths) == 1

    def test_duplicates_empty_when_no_dupes(self, tmp_path: Path):
        """duplicates() returns empty dict when all content is unique."""
        (tmp_path / "a.md").write_text("content alpha", encoding="utf-8")
        (tmp_path / "b.md").write_text("content beta", encoding="utf-8")

        index = ContentIndex.from_directory(tmp_path)
        assert index.duplicates() == {}

    def test_duplicates_returns_groups_when_dupes_exist(self, tmp_path: Path):
        """duplicates() returns groups of paths sharing the same content."""
        (tmp_path / "original.md").write_text("shared content", encoding="utf-8")
        (tmp_path / "copy.md").write_text("shared content", encoding="utf-8")
        (tmp_path / "unique.md").write_text("different content", encoding="utf-8")

        index = ContentIndex.from_directory(tmp_path)
        dupes = index.duplicates()

        assert len(dupes) == 1
        # The single duplicate group has exactly 2 paths
        group = list(dupes.values())[0]
        assert len(group) == 2

    def test_duplicates_multiple_groups(self, tmp_path: Path):
        """Multiple groups of duplicates are all reported."""
        (tmp_path / "a1.md").write_text("content A", encoding="utf-8")
        (tmp_path / "a2.md").write_text("content A", encoding="utf-8")
        (tmp_path / "b1.md").write_text("content B", encoding="utf-8")
        (tmp_path / "b2.md").write_text("content B", encoding="utf-8")

        index = ContentIndex.from_directory(tmp_path)
        dupes = index.duplicates()
        assert len(dupes) == 2

    def test_lookup_finds_paths_by_content(self, tmp_path: Path):
        """lookup() returns all paths containing the given content."""
        (tmp_path / "one.md").write_text("findable content", encoding="utf-8")
        (tmp_path / "two.md").write_text("findable content", encoding="utf-8")
        (tmp_path / "other.md").write_text("other content", encoding="utf-8")

        index = ContentIndex.from_directory(tmp_path)
        results = index.lookup("findable content")
        assert len(results) == 2
        names = {p.name for p in results}
        assert names == {"one.md", "two.md"}

    def test_lookup_returns_empty_for_missing_content(self, tmp_path: Path):
        """lookup() returns empty list for content not in the index."""
        (tmp_path / "doc.md").write_text("existing", encoding="utf-8")
        index = ContentIndex.from_directory(tmp_path)
        assert index.lookup("absent content") == []

    def test_hash_for_path(self, tmp_path: Path):
        """hash_for_path() returns the hash for a registered path."""
        filepath = tmp_path / "doc.md"
        filepath.write_text("hashable content", encoding="utf-8")

        index = ContentIndex()
        expected_hash = index.register(filepath)
        assert index.hash_for_path(filepath) == expected_hash

    def test_hash_for_path_unregistered(self, tmp_path: Path):
        """hash_for_path() returns None for an unregistered path."""
        index = ContentIndex()
        assert index.hash_for_path(tmp_path / "nope.md") is None

    def test_len_counts_unique_hashes(self, tmp_path: Path):
        """len(index) counts unique content hashes, not file count."""
        (tmp_path / "a.md").write_text("same", encoding="utf-8")
        (tmp_path / "b.md").write_text("same", encoding="utf-8")
        (tmp_path / "c.md").write_text("different", encoding="utf-8")

        index = ContentIndex.from_directory(tmp_path)
        # Two unique contents, even though three files
        assert len(index) == 2


class TestDeduplicateReport:
    """Tests for the deduplicate_report() function."""

    def test_clean_directory_no_duplicates(self, tmp_path: Path):
        """Clean directory produces a 'No duplicates' message."""
        (tmp_path / "a.md").write_text("unique alpha", encoding="utf-8")
        (tmp_path / "b.md").write_text("unique beta", encoding="utf-8")

        report = deduplicate_report(tmp_path)
        assert "No duplicates" in report
        assert "2 documents" in report

    def test_empty_directory(self, tmp_path: Path):
        """Empty directory reports no duplicates among 0 documents."""
        report = deduplicate_report(tmp_path)
        assert "No duplicates" in report
        assert "0 documents" in report

    def test_directory_with_dupes_produces_report(self, tmp_path: Path):
        """Directory with duplicates produces a report listing them."""
        (tmp_path / "original.md").write_text("shared content", encoding="utf-8")
        (tmp_path / "copy.md").write_text("shared content", encoding="utf-8")
        (tmp_path / "unique.md").write_text("unique content", encoding="utf-8")

        report = deduplicate_report(tmp_path)

        # Report should contain structural elements
        assert "Duplicate report" in report
        assert "Duplicate groups: 1" in report
        assert "Redundant copies: 1" in report
        assert "(original)" in report
        assert "(duplicate)" in report

    def test_report_contains_hash(self, tmp_path: Path):
        """Report includes the content hash for each duplicate group."""
        content = "duplicated content"
        (tmp_path / "a.md").write_text(content, encoding="utf-8")
        (tmp_path / "b.md").write_text(content, encoding="utf-8")

        report = deduplicate_report(tmp_path)
        expected_hash = content_hash(content)
        assert expected_hash in report

    def test_report_shows_relative_paths(self, tmp_path: Path):
        """Report shows paths relative to the scanned directory."""
        (tmp_path / "file_one.md").write_text("dup content", encoding="utf-8")
        (tmp_path / "file_two.md").write_text("dup content", encoding="utf-8")

        report = deduplicate_report(tmp_path)
        assert "file_one.md" in report
        assert "file_two.md" in report

    def test_report_multiple_groups(self, tmp_path: Path):
        """Multiple duplicate groups are all included in the report."""
        (tmp_path / "a1.md").write_text("group A", encoding="utf-8")
        (tmp_path / "a2.md").write_text("group A", encoding="utf-8")
        (tmp_path / "b1.md").write_text("group B", encoding="utf-8")
        (tmp_path / "b2.md").write_text("group B", encoding="utf-8")

        report = deduplicate_report(tmp_path)
        assert "Duplicate groups: 2" in report
        assert "Redundant copies: 2" in report

    def test_report_total_unique_hashes(self, tmp_path: Path):
        """Report states the total number of unique content hashes."""
        (tmp_path / "a.md").write_text("dup", encoding="utf-8")
        (tmp_path / "b.md").write_text("dup", encoding="utf-8")
        (tmp_path / "c.md").write_text("unique", encoding="utf-8")

        report = deduplicate_report(tmp_path)
        # 2 unique hashes: one for "dup", one for "unique"
        assert "Total unique hashes: 2" in report
