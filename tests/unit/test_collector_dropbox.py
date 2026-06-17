"""Tests for Dropbox collectors (synthetic only — real requires SDK + auth)."""

from __future__ import annotations

from yanantin.collector.storage.cloud.dropbox.models import DropboxEntryData, DropboxListing
from yanantin.collector.storage.cloud.dropbox.synthetic import SyntheticDropboxCollector


class TestDropboxModels:
    def test_entry_frozen(self) -> None:
        from datetime import datetime, timezone

        entry = DropboxEntryData(
            name="test.txt",
            path_display="/test.txt",
            path_lower="/test.txt",
            entry_type="file",
        )
        import pytest

        with pytest.raises(Exception):
            entry.name = "other"  # type: ignore[misc]

    def test_listing_roundtrips_json(self) -> None:
        from datetime import datetime, timezone

        listing = DropboxListing(
            account_email="test@example.com",
            entries=(
                DropboxEntryData(
                    name="doc.pdf",
                    path_display="/doc.pdf",
                    path_lower="/doc.pdf",
                    entry_type="file",
                    size=1024,
                ),
            ),
            total_files=1,
            total_folders=0,
        )
        json_str = listing.model_dump_json()
        restored = DropboxListing.model_validate_json(json_str)
        assert restored.account_email == listing.account_email
        assert len(restored.entries) == 1


class TestSyntheticDropboxCollector:
    def test_generate_returns_listing(self) -> None:
        collector = SyntheticDropboxCollector(seed=42)
        listing = collector.generate()
        assert isinstance(listing, DropboxListing)
        assert listing.account_email == "synthetic@example.com"
        assert len(listing.entries) > 0

    def test_deterministic_with_seed(self) -> None:
        c1 = SyntheticDropboxCollector(seed=42)
        c2 = SyntheticDropboxCollector(seed=42)
        assert c1.collect() == c2.collect()

    def test_different_seeds_differ(self) -> None:
        c1 = SyntheticDropboxCollector(seed=42)
        c2 = SyntheticDropboxCollector(seed=99)
        assert c1.collect() != c2.collect()

    def test_entry_types(self) -> None:
        collector = SyntheticDropboxCollector(seed=42, total_entries=50)
        listing = collector.collect()
        types = {e.entry_type for e in listing.entries}
        assert "file" in types
        assert "folder" in types

    def test_files_have_content_hash(self) -> None:
        collector = SyntheticDropboxCollector(seed=42, total_entries=50)
        listing = collector.collect()
        file_entries = [e for e in listing.entries if e.entry_type == "file"]
        assert all(e.content_hash for e in file_entries)
        # Content hashes should be 64 hex chars (SHA-256)
        assert all(len(e.content_hash) == 64 for e in file_entries)

    def test_files_have_revisions(self) -> None:
        collector = SyntheticDropboxCollector(seed=42, total_entries=50)
        listing = collector.collect()
        file_entries = [e for e in listing.entries if e.entry_type == "file"]
        assert all(e.rev for e in file_entries)

    def test_configurable_entry_count(self) -> None:
        collector = SyntheticDropboxCollector(seed=42, total_entries=20)
        listing = collector.collect()
        assert listing.total_files + listing.total_folders == len(listing.entries)

    def test_has_cursor(self) -> None:
        collector = SyntheticDropboxCollector(seed=42)
        listing = collector.collect()
        assert listing.cursor
        assert listing.cursor.startswith("synthetic_cursor_")

    def test_shared_files_present(self) -> None:
        collector = SyntheticDropboxCollector(
            seed=42, total_entries=100, shared_fraction=0.5,
        )
        listing = collector.collect()
        shared = [e for e in listing.entries if e.shared]
        assert len(shared) > 0

    def test_custom_email(self) -> None:
        collector = SyntheticDropboxCollector(
            seed=42, account_email="tony@example.com",
        )
        listing = collector.collect()
        assert listing.account_email == "tony@example.com"

    def test_collect_batch(self) -> None:
        collector = SyntheticDropboxCollector(seed=42)
        batch = collector.collect_batch(3)
        assert len(batch) == 3
        for item in batch:
            assert isinstance(item, DropboxListing)

    def test_listing_roundtrips_json(self) -> None:
        collector = SyntheticDropboxCollector(seed=42)
        listing = collector.collect()
        json_str = listing.model_dump_json()
        restored = DropboxListing.model_validate_json(json_str)
        assert restored == listing


class TestDropboxTokenPermissions:
    """The OAuth token file is a credential — it must land owner-only (0o600)."""

    def test_save_tokens_writes_owner_only_mode(self, tmp_path) -> None:
        import stat
        from yanantin.collector.storage.cloud.dropbox.collector import (
            DropboxCollector,
            _TOKEN_FILENAME,
        )

        collector = DropboxCollector(tmp_path)
        collector._save_tokens({"access_token": "secret", "refresh_token": "also-secret"})

        token_path = tmp_path / _TOKEN_FILENAME
        assert token_path.exists()
        mode = stat.S_IMODE(token_path.stat().st_mode)
        assert mode == 0o600, f"token file mode {oct(mode)} exposes credentials"

    def test_save_tokens_roundtrips(self, tmp_path) -> None:
        from yanantin.collector.storage.cloud.dropbox.collector import DropboxCollector

        collector = DropboxCollector(tmp_path)
        tokens = {"access_token": "a", "refresh_token": "r", "app_key": "k"}
        collector._save_tokens(tokens)
        assert collector._load_tokens() == tokens
