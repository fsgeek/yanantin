"""Tests for checksum collectors (real and synthetic)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from yanantin.collector.storage.local.checksum import (
    ChecksumCollector,
    ChecksumData,
    SyntheticChecksumCollector,
)


class TestChecksumCollector:
    def test_collect_returns_checksum_data(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        collector = ChecksumCollector(test_file)
        data = collector.collect()

        assert isinstance(data, ChecksumData)
        assert data.file_path == str(test_file)
        assert data.file_size == 11
        assert "sha256" in data.checksums
        assert "sha1" in data.checksums
        assert "md5" in data.checksums

    def test_known_hash_verification(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.txt"
        content = b"hello world"
        test_file.write_bytes(content)

        collector = ChecksumCollector(test_file)
        data = collector.collect()

        expected_sha256 = hashlib.sha256(content).hexdigest()
        expected_sha1 = hashlib.sha1(content).hexdigest()
        expected_md5 = hashlib.md5(content).hexdigest()

        assert data.checksums["sha256"] == expected_sha256
        assert data.checksums["sha1"] == expected_sha1
        assert data.checksums["md5"] == expected_md5

    def test_single_pass_multi_hash(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"\x00" * 1000)

        collector = ChecksumCollector(test_file, algorithms=("sha256", "sha512", "md5"))
        data = collector.collect()

        assert len(data.checksums) == 3
        assert data.algorithms == ("sha256", "sha512", "md5")

    def test_empty_file(self, tmp_path: Path) -> None:
        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")

        collector = ChecksumCollector(test_file)
        data = collector.collect()

        assert data.file_size == 0
        # Empty file has known hash
        expected = hashlib.sha256(b"").hexdigest()
        assert data.checksums["sha256"] == expected

    def test_large_file_uses_mmap(self, tmp_path: Path) -> None:
        test_file = tmp_path / "large.bin"
        # Write 2 MiB — over the mmap threshold
        chunk = b"A" * (1024 * 1024)
        test_file.write_bytes(chunk * 2)

        collector = ChecksumCollector(test_file)
        data = collector.collect()

        assert data.file_size == 2 * 1024 * 1024
        expected = hashlib.sha256(chunk * 2).hexdigest()
        assert data.checksums["sha256"] == expected

    def test_custom_algorithms(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        collector = ChecksumCollector(test_file, algorithms=("sha512",))
        data = collector.collect()

        assert data.algorithms == ("sha512",)
        assert "sha512" in data.checksums
        assert "sha256" not in data.checksums

    def test_provider_id_is_stable(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("a")
        f2.write_text("b")

        c1 = ChecksumCollector(f1)
        c2 = ChecksumCollector(f2)
        assert c1.get_provider_id() == c2.get_provider_id()

    def test_data_roundtrips_json(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        collector = ChecksumCollector(test_file)
        data = collector.collect()

        json_str = data.model_dump_json()
        restored = ChecksumData.model_validate_json(json_str)
        assert restored.checksums == data.checksums
        assert restored.file_size == data.file_size

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        collector = ChecksumCollector(tmp_path / "nonexistent.txt")
        with pytest.raises(FileNotFoundError):
            collector.collect()


class TestSyntheticChecksumCollector:
    def test_generate_returns_checksum_data(self) -> None:
        collector = SyntheticChecksumCollector(seed=42)
        data = collector.generate()
        assert isinstance(data, ChecksumData)
        assert data.file_path
        assert data.file_size >= 0
        assert len(data.checksums) == 3

    def test_deterministic_with_seed(self) -> None:
        c1 = SyntheticChecksumCollector(seed=42)
        c2 = SyntheticChecksumCollector(seed=42)
        assert c1.collect() == c2.collect()

    def test_different_seeds_differ(self) -> None:
        c1 = SyntheticChecksumCollector(seed=42)
        c2 = SyntheticChecksumCollector(seed=99)
        assert c1.collect() != c2.collect()

    def test_hashes_are_real(self) -> None:
        collector = SyntheticChecksumCollector(seed=42)
        data = collector.collect()
        # SHA-256 is 64 hex chars
        assert len(data.checksums["sha256"]) == 64
        # SHA-1 is 40 hex chars
        assert len(data.checksums["sha1"]) == 40
        # MD5 is 32 hex chars
        assert len(data.checksums["md5"]) == 32

    def test_collect_batch(self) -> None:
        collector = SyntheticChecksumCollector(seed=42)
        batch = collector.collect_batch(5)
        assert len(batch) == 5
        # Each should be different (different RNG draws)
        paths = {item.file_path for item in batch}
        assert len(paths) > 1

    def test_custom_algorithms(self) -> None:
        collector = SyntheticChecksumCollector(seed=42, algorithms=("sha512",))
        data = collector.collect()
        assert data.algorithms == ("sha512",)
        assert "sha512" in data.checksums
