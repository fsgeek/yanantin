"""Unit tests for the provenance/timestamp module.

Tests OpenTimestamps integration: digest computation, calendar submission,
proof serialization/deserialization, verification, listing, and upgrade logic.

This module was not written by the code author.
"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from opentimestamps.core.notary import (
    BitcoinBlockHeaderAttestation,
    PendingAttestation,
)
from opentimestamps.core.op import OpSHA256
from opentimestamps.core.serialize import (
    BytesDeserializationContext,
    BytesSerializationContext,
)
from opentimestamps.core.timestamp import DetachedTimestampFile, Timestamp

from yanantin.provenance import (
    list_proofs,
    stamp_commit,
    upgrade_pending_proofs,
    verify_proof,
)
from yanantin.provenance.timestamp import (
    CALENDAR_URLS,
    MIN_UPGRADE_AGE,
    _commit_hash_to_digest,
    _deserialize_detached,
    _get_pending_attestations,
    _has_bitcoin_attestation,
    _merge_at_commitment,
    _serialize_detached,
    _submit_to_calendar,
)


# ---------------------------------------------------------------------------
# Helpers for building mock OTS objects
# ---------------------------------------------------------------------------

FAKE_COMMIT_HASH = "abc123def456789012345678901234567890abcd"
FAKE_SHORT_HASH = FAKE_COMMIT_HASH[:10]


def _make_digest(commit_hash: str = FAKE_COMMIT_HASH) -> bytes:
    """Compute the SHA-256 digest of a commit hash the same way the module does."""
    return hashlib.sha256(commit_hash.encode("ascii")).digest()


def _make_pending_timestamp(
    digest: bytes,
    calendar_uri: str = "https://a.pool.opentimestamps.org",
) -> Timestamp:
    """Create a Timestamp with a single PendingAttestation."""
    ts = Timestamp(digest)
    ts.attestations.add(PendingAttestation(calendar_uri))
    return ts


def _make_bitcoin_timestamp(
    digest: bytes,
    height: int = 800000,
) -> Timestamp:
    """Create a Timestamp with a BitcoinBlockHeaderAttestation."""
    ts = Timestamp(digest)
    ts.attestations.add(BitcoinBlockHeaderAttestation(height))
    return ts


def _serialize_timestamp(ts: Timestamp) -> bytes:
    """Serialize a bare Timestamp (as a calendar server would return)."""
    ctx = BytesSerializationContext()
    ts.serialize(ctx)
    return ctx.getbytes()


def _make_pending_ots_bytes(
    digest: bytes,
    calendar_uri: str = "https://a.pool.opentimestamps.org",
) -> bytes:
    """Create serialized DetachedTimestampFile bytes with a PendingAttestation."""
    ts = _make_pending_timestamp(digest, calendar_uri)
    dtf = DetachedTimestampFile(OpSHA256(), ts)
    return _serialize_detached(dtf)


def _make_bitcoin_ots_bytes(
    digest: bytes,
    height: int = 800000,
) -> bytes:
    """Create serialized DetachedTimestampFile bytes with a BitcoinBlockHeaderAttestation."""
    ts = _make_bitcoin_timestamp(digest, height)
    dtf = DetachedTimestampFile(OpSHA256(), ts)
    return _serialize_detached(dtf)


# ---------------------------------------------------------------------------
# Digest computation
# ---------------------------------------------------------------------------


class TestCommitHashToDigest:
    """Tests for _commit_hash_to_digest."""

    def test_produces_32_bytes(self):
        """Digest must be exactly 32 bytes (SHA-256 output)."""
        digest = _commit_hash_to_digest(FAKE_COMMIT_HASH)
        assert len(digest) == 32

    def test_is_sha256_of_ascii_hex(self):
        """Digest must be SHA-256 of the ASCII hex string."""
        expected = hashlib.sha256(FAKE_COMMIT_HASH.encode("ascii")).digest()
        assert _commit_hash_to_digest(FAKE_COMMIT_HASH) == expected

    def test_deterministic(self):
        """Same commit hash always produces the same digest."""
        d1 = _commit_hash_to_digest(FAKE_COMMIT_HASH)
        d2 = _commit_hash_to_digest(FAKE_COMMIT_HASH)
        assert d1 == d2

    def test_different_hashes_produce_different_digests(self):
        """Different commit hashes produce different digests."""
        d1 = _commit_hash_to_digest("a" * 40)
        d2 = _commit_hash_to_digest("b" * 40)
        assert d1 != d2

    def test_short_hash_still_produces_digest(self):
        """Even a short hash (7 chars) produces a valid 32-byte digest."""
        digest = _commit_hash_to_digest("abc1234")
        assert len(digest) == 32


# ---------------------------------------------------------------------------
# stamp_commit validation
# ---------------------------------------------------------------------------


class TestStampCommitValidation:
    """Tests for stamp_commit input validation."""

    def test_rejects_empty_hash(self, tmp_path: Path):
        """Empty commit hash returns None."""
        result = stamp_commit("", tmp_path / "ots")
        assert result is None

    def test_rejects_short_hash(self, tmp_path: Path):
        """Commit hash shorter than 7 chars returns None."""
        result = stamp_commit("abc12", tmp_path / "ots")
        assert result is None

    def test_rejects_six_char_hash(self, tmp_path: Path):
        """Commit hash of exactly 6 chars returns None."""
        result = stamp_commit("abcdef", tmp_path / "ots")
        assert result is None

    def test_accepts_seven_char_hash(self, tmp_path: Path):
        """Commit hash of exactly 7 chars is accepted (reaches calendar submission)."""
        with patch("yanantin.provenance.timestamp.httpx.post") as mock_post:
            mock_post.side_effect = httpx.ConnectError("no network")
            result = stamp_commit("abcdef0", tmp_path / "ots")
            # All calendars fail but validation passed
            assert result is None
            assert mock_post.called

    def test_rejects_none_hash(self, tmp_path: Path):
        """None commit hash (falsy) returns None."""
        result = stamp_commit("", tmp_path / "ots")
        assert result is None


# ---------------------------------------------------------------------------
# stamp_commit idempotency
# ---------------------------------------------------------------------------


class TestStampCommitIdempotency:
    """Tests for stamp_commit returning existing proofs."""

    def test_returns_existing_path(self, tmp_path: Path):
        """If proof file already exists, returns its path without network calls."""
        ots_dir = tmp_path / "ots"
        ots_dir.mkdir()
        existing = ots_dir / f"{FAKE_SHORT_HASH}.ots"
        existing.write_bytes(b"existing proof data")

        with patch("yanantin.provenance.timestamp.httpx.post") as mock_post:
            result = stamp_commit(FAKE_COMMIT_HASH, ots_dir)
            assert result == existing
            mock_post.assert_not_called()

    def test_creates_directory_if_missing(self, tmp_path: Path):
        """stamp_commit creates ots_dir if it does not exist."""
        ots_dir = tmp_path / "nested" / "ots"
        assert not ots_dir.exists()

        with patch("yanantin.provenance.timestamp.httpx.post") as mock_post:
            mock_post.side_effect = httpx.ConnectError("no network")
            stamp_commit(FAKE_COMMIT_HASH, ots_dir)
            assert ots_dir.is_dir()


# ---------------------------------------------------------------------------
# stamp_commit with mocked calendars
# ---------------------------------------------------------------------------


class TestStampCommitCalendars:
    """Tests for stamp_commit with mocked calendar responses."""

    def _mock_calendar_response(self, digest: bytes, calendar_uri: str) -> MagicMock:
        """Create a mock httpx.Response that returns a valid calendar timestamp."""
        ts = _make_pending_timestamp(digest, calendar_uri)
        body = _serialize_timestamp(ts)
        resp = MagicMock()
        resp.status_code = 200
        resp.content = body
        return resp

    def test_single_calendar_success(self, tmp_path: Path):
        """stamp_commit succeeds when one calendar returns valid data."""
        digest = _make_digest()

        with patch("yanantin.provenance.timestamp.httpx.post") as mock_post:
            mock_post.return_value = self._mock_calendar_response(
                digest, CALENDAR_URLS[0]
            )
            result = stamp_commit(FAKE_COMMIT_HASH, tmp_path / "ots")

        assert result is not None
        assert result.exists()
        assert result.suffix == ".ots"
        assert result.stem == FAKE_SHORT_HASH

    def test_proof_file_is_valid_ots(self, tmp_path: Path):
        """The saved proof file can be deserialized as a DetachedTimestampFile."""
        digest = _make_digest()

        with patch("yanantin.provenance.timestamp.httpx.post") as mock_post:
            mock_post.return_value = self._mock_calendar_response(
                digest, CALENDAR_URLS[0]
            )
            result = stamp_commit(FAKE_COMMIT_HASH, tmp_path / "ots")

        data = result.read_bytes()
        dtf = _deserialize_detached(data)
        assert dtf.file_digest == digest

    def test_all_calendars_fail_returns_none(self, tmp_path: Path):
        """When all calendar servers fail, stamp_commit returns None."""
        with patch("yanantin.provenance.timestamp.httpx.post") as mock_post:
            mock_post.side_effect = httpx.ConnectError("no network")
            result = stamp_commit(FAKE_COMMIT_HASH, tmp_path / "ots")

        assert result is None
        # No .ots file should exist
        ots_dir = tmp_path / "ots"
        assert list(ots_dir.glob("*.ots")) == []

    def test_all_calendars_return_non_200(self, tmp_path: Path):
        """When all calendars return HTTP errors, stamp_commit returns None."""
        resp = MagicMock()
        resp.status_code = 503
        resp.text = "Service Unavailable"

        with patch("yanantin.provenance.timestamp.httpx.post") as mock_post:
            mock_post.return_value = resp
            result = stamp_commit(FAKE_COMMIT_HASH, tmp_path / "ots")

        assert result is None

    def test_partial_success_first_fails(self, tmp_path: Path):
        """First calendar fails, second succeeds — proof is still created."""
        digest = _make_digest()

        fail_resp = MagicMock()
        fail_resp.status_code = 503
        fail_resp.text = "Service Unavailable"

        ok_resp = self._mock_calendar_response(digest, CALENDAR_URLS[1])

        with patch("yanantin.provenance.timestamp.httpx.post") as mock_post:
            mock_post.side_effect = [fail_resp, ok_resp, fail_resp]
            result = stamp_commit(FAKE_COMMIT_HASH, tmp_path / "ots")

        assert result is not None
        assert result.exists()

    def test_partial_success_first_raises(self, tmp_path: Path):
        """First calendar raises exception, second succeeds."""
        digest = _make_digest()
        ok_resp = self._mock_calendar_response(digest, CALENDAR_URLS[1])

        with patch("yanantin.provenance.timestamp.httpx.post") as mock_post:
            mock_post.side_effect = [
                httpx.TimeoutException("timeout"),
                ok_resp,
                httpx.ConnectError("refused"),
            ]
            result = stamp_commit(FAKE_COMMIT_HASH, tmp_path / "ots")

        assert result is not None
        assert result.exists()

    def test_multiple_calendars_merge(self, tmp_path: Path):
        """Multiple successful calendar responses are merged into one proof."""
        digest = _make_digest()

        resp_a = self._mock_calendar_response(digest, CALENDAR_URLS[0])
        resp_b = self._mock_calendar_response(digest, CALENDAR_URLS[1])
        resp_c = self._mock_calendar_response(digest, CALENDAR_URLS[2])

        with patch("yanantin.provenance.timestamp.httpx.post") as mock_post:
            mock_post.side_effect = [resp_a, resp_b, resp_c]
            result = stamp_commit(FAKE_COMMIT_HASH, tmp_path / "ots")

        assert result is not None
        data = result.read_bytes()
        dtf = _deserialize_detached(data)
        attestations = list(dtf.timestamp.all_attestations())
        # Should have attestations from all three calendars
        assert len(attestations) == 3

    def test_calendar_url_format(self, tmp_path: Path):
        """Calendar POST URL is {base}/digest."""
        digest = _make_digest()

        with patch("yanantin.provenance.timestamp.httpx.post") as mock_post:
            mock_post.side_effect = httpx.ConnectError("no network")
            stamp_commit(FAKE_COMMIT_HASH, tmp_path / "ots")

        # Check all called URLs end with /digest
        for call in mock_post.call_args_list:
            url = call.args[0] if call.args else call.kwargs.get("url", "")
            assert url.endswith("/digest"), f"Expected /digest URL, got: {url}"


# ---------------------------------------------------------------------------
# verify_proof
# ---------------------------------------------------------------------------


class TestVerifyProof:
    """Tests for verify_proof."""

    def test_missing_file_returns_error(self, tmp_path: Path):
        """verify_proof on a nonexistent file returns error status."""
        result = verify_proof(tmp_path / "nonexistent.ots")
        assert result["status"] == "error"
        assert result["error"] == "File not found"
        assert result["commit_short"] == "nonexistent"

    def test_corrupted_file_returns_error(self, tmp_path: Path):
        """verify_proof on a corrupted file returns deserialization error."""
        bad_file = tmp_path / "corrupt.ots"
        bad_file.write_bytes(b"this is not a valid OTS file")
        result = verify_proof(bad_file)
        assert result["status"] == "error"
        assert "Deserialization failed" in result["error"]

    def test_empty_file_returns_error(self, tmp_path: Path):
        """verify_proof on an empty file returns deserialization error."""
        empty_file = tmp_path / "empty.ots"
        empty_file.write_bytes(b"")
        result = verify_proof(empty_file)
        assert result["status"] == "error"
        assert result["error"] is not None

    def test_pending_proof(self, tmp_path: Path):
        """verify_proof on a pending proof returns status=pending."""
        digest = _make_digest()
        data = _make_pending_ots_bytes(digest)
        ots_file = tmp_path / f"{FAKE_SHORT_HASH}.ots"
        ots_file.write_bytes(data)

        result = verify_proof(ots_file)
        assert result["status"] == "pending"
        assert result["error"] is None
        assert result["commit_short"] == FAKE_SHORT_HASH
        assert len(result["attestations"]) == 1
        assert result["attestations"][0]["type"] == "PendingAttestation"
        assert "calendar_uri" in result["attestations"][0]

    def test_confirmed_proof(self, tmp_path: Path):
        """verify_proof on a bitcoin-confirmed proof returns status=confirmed."""
        digest = _make_digest()
        data = _make_bitcoin_ots_bytes(digest, height=800123)
        ots_file = tmp_path / f"{FAKE_SHORT_HASH}.ots"
        ots_file.write_bytes(data)

        result = verify_proof(ots_file)
        assert result["status"] == "confirmed"
        assert result["error"] is None
        assert len(result["attestations"]) == 1
        assert result["attestations"][0]["type"] == "BitcoinBlockHeaderAttestation"
        assert result["attestations"][0]["bitcoin_height"] == 800123

    def test_mixed_attestations_is_confirmed(self, tmp_path: Path):
        """A proof with both pending and bitcoin attestations is confirmed."""
        digest = _make_digest()
        ts = Timestamp(digest)
        ts.attestations.add(PendingAttestation("https://a.pool.opentimestamps.org"))
        ts.attestations.add(BitcoinBlockHeaderAttestation(800000))
        dtf = DetachedTimestampFile(OpSHA256(), ts)
        data = _serialize_detached(dtf)

        ots_file = tmp_path / "mixed.ots"
        ots_file.write_bytes(data)

        result = verify_proof(ots_file)
        assert result["status"] == "confirmed"
        assert len(result["attestations"]) == 2

    def test_no_recognized_attestations(self, tmp_path: Path):
        """A proof with no attestations triggers 'no recognized' error."""
        digest = _make_digest()
        # OTS library refuses to serialize an empty timestamp, so we
        # mock _deserialize_detached to return one with no attestations.
        ts = Timestamp(digest)
        dtf = DetachedTimestampFile(OpSHA256(), ts)

        ots_file = tmp_path / "bare.ots"
        ots_file.write_bytes(b"placeholder")

        with patch(
            "yanantin.provenance.timestamp._deserialize_detached",
            return_value=dtf,
        ):
            result = verify_proof(ots_file)

        assert result["status"] == "error"
        assert "No recognized attestations" in result["error"]

    def test_path_field(self, tmp_path: Path):
        """verify_proof result includes the file path as a string."""
        digest = _make_digest()
        data = _make_pending_ots_bytes(digest)
        ots_file = tmp_path / "test.ots"
        ots_file.write_bytes(data)

        result = verify_proof(ots_file)
        assert result["path"] == str(ots_file)

    def test_file_digest_hex(self, tmp_path: Path):
        """verify_proof result includes the file digest as hex."""
        digest = _make_digest()
        data = _make_pending_ots_bytes(digest)
        ots_file = tmp_path / "test.ots"
        ots_file.write_bytes(data)

        result = verify_proof(ots_file)
        assert result["file_digest_hex"] == digest.hex()

    def test_real_ots_file_if_present(self):
        """If real OTS proof files exist, verify they parse correctly."""
        ots_dir = Path(__file__).resolve().parents[2] / "docs" / "ots"
        if not ots_dir.is_dir():
            pytest.skip("No docs/ots directory present")

        ots_files = list(ots_dir.glob("*.ots"))
        if not ots_files:
            pytest.skip("No .ots files in docs/ots")

        for ots_file in ots_files:
            result = verify_proof(ots_file)
            assert result["status"] in ("pending", "confirmed"), (
                f"{ots_file.name}: expected pending or confirmed, got {result}"
            )
            assert result["error"] is None
            assert len(result["file_digest_hex"]) == 64  # SHA-256 hex


# ---------------------------------------------------------------------------
# list_proofs
# ---------------------------------------------------------------------------


class TestListProofs:
    """Tests for list_proofs."""

    def test_empty_directory(self, tmp_path: Path):
        """Empty directory returns empty list."""
        result = list_proofs(tmp_path)
        assert result == []

    def test_nonexistent_directory(self, tmp_path: Path):
        """Nonexistent directory returns empty list."""
        result = list_proofs(tmp_path / "does_not_exist")
        assert result == []

    def test_directory_with_no_ots_files(self, tmp_path: Path):
        """Directory with non-.ots files returns empty list."""
        (tmp_path / "readme.txt").write_text("not a proof")
        (tmp_path / "data.json").write_text("{}")
        result = list_proofs(tmp_path)
        assert result == []

    def test_directory_with_proofs(self, tmp_path: Path):
        """Directory with .ots files returns one result per file."""
        digest1 = _make_digest("a" * 40)
        digest2 = _make_digest("b" * 40)

        (tmp_path / "aaaaaaaaaa.ots").write_bytes(_make_pending_ots_bytes(digest1))
        (tmp_path / "bbbbbbbbbb.ots").write_bytes(_make_bitcoin_ots_bytes(digest2))

        results = list_proofs(tmp_path)
        assert len(results) == 2
        statuses = {r["commit_short"]: r["status"] for r in results}
        assert statuses["aaaaaaaaaa"] == "pending"
        assert statuses["bbbbbbbbbb"] == "confirmed"

    def test_results_sorted_by_filename(self, tmp_path: Path):
        """Results are sorted by filename."""
        digest = _make_digest()
        (tmp_path / "zzz.ots").write_bytes(_make_pending_ots_bytes(digest))
        (tmp_path / "aaa.ots").write_bytes(_make_pending_ots_bytes(digest))
        (tmp_path / "mmm.ots").write_bytes(_make_pending_ots_bytes(digest))

        results = list_proofs(tmp_path)
        names = [r["commit_short"] for r in results]
        assert names == ["aaa", "mmm", "zzz"]


# ---------------------------------------------------------------------------
# Serialization roundtrip
# ---------------------------------------------------------------------------


class TestSerializationRoundtrip:
    """Tests for _serialize_detached and _deserialize_detached."""

    def test_roundtrip_pending(self):
        """Serialize then deserialize a pending proof preserves data."""
        digest = _make_digest()
        ts = _make_pending_timestamp(digest, "https://a.pool.opentimestamps.org")
        dtf = DetachedTimestampFile(OpSHA256(), ts)

        data = _serialize_detached(dtf)
        assert isinstance(data, bytes)
        assert len(data) > 0

        dtf2 = _deserialize_detached(data)
        assert dtf2.file_digest == digest

        attestations = list(dtf2.timestamp.all_attestations())
        assert len(attestations) == 1
        _, att = attestations[0]
        assert isinstance(att, PendingAttestation)

    def test_roundtrip_bitcoin(self):
        """Serialize then deserialize a confirmed proof preserves data."""
        digest = _make_digest()
        ts = _make_bitcoin_timestamp(digest, height=750000)
        dtf = DetachedTimestampFile(OpSHA256(), ts)

        data = _serialize_detached(dtf)
        dtf2 = _deserialize_detached(data)

        assert dtf2.file_digest == digest
        attestations = list(dtf2.timestamp.all_attestations())
        assert len(attestations) == 1
        _, att = attestations[0]
        assert isinstance(att, BitcoinBlockHeaderAttestation)
        assert att.height == 750000

    def test_roundtrip_multiple_attestations(self):
        """Serialize then deserialize a proof with multiple attestations."""
        digest = _make_digest()
        ts = Timestamp(digest)
        ts.attestations.add(PendingAttestation("https://cal1.example.com"))
        ts.attestations.add(PendingAttestation("https://cal2.example.com"))
        dtf = DetachedTimestampFile(OpSHA256(), ts)

        data = _serialize_detached(dtf)
        dtf2 = _deserialize_detached(data)

        attestations = list(dtf2.timestamp.all_attestations())
        assert len(attestations) == 2

    def test_roundtrip_preserves_digest(self):
        """The file_digest is preserved through serialization."""
        for commit in ["0" * 40, "f" * 40, "1234567890abcdef" * 2 + "12345678"]:
            digest = _make_digest(commit)
            ts = _make_pending_timestamp(digest)
            dtf = DetachedTimestampFile(OpSHA256(), ts)
            data = _serialize_detached(dtf)
            dtf2 = _deserialize_detached(data)
            assert dtf2.file_digest == digest


# ---------------------------------------------------------------------------
# _has_bitcoin_attestation
# ---------------------------------------------------------------------------


class TestHasBitcoinAttestation:
    """Tests for _has_bitcoin_attestation."""

    def test_pending_only(self):
        """Timestamp with only PendingAttestation returns False."""
        digest = _make_digest()
        ts = _make_pending_timestamp(digest)
        assert _has_bitcoin_attestation(ts) is False

    def test_bitcoin_only(self):
        """Timestamp with only BitcoinBlockHeaderAttestation returns True."""
        digest = _make_digest()
        ts = _make_bitcoin_timestamp(digest)
        assert _has_bitcoin_attestation(ts) is True

    def test_mixed(self):
        """Timestamp with both types returns True."""
        digest = _make_digest()
        ts = Timestamp(digest)
        ts.attestations.add(PendingAttestation("https://example.com"))
        ts.attestations.add(BitcoinBlockHeaderAttestation(800000))
        assert _has_bitcoin_attestation(ts) is True

    def test_empty(self):
        """Timestamp with no attestations returns False."""
        digest = _make_digest()
        ts = Timestamp(digest)
        assert _has_bitcoin_attestation(ts) is False

    def test_bitcoin_in_child_op(self):
        """Bitcoin attestation in a child op node is found."""
        digest = _make_digest()
        ts = Timestamp(digest)
        child = ts.ops.add(OpSHA256())
        child.attestations.add(BitcoinBlockHeaderAttestation(800000))
        assert _has_bitcoin_attestation(ts) is True


# ---------------------------------------------------------------------------
# _get_pending_attestations
# ---------------------------------------------------------------------------


class TestGetPendingAttestations:
    """Tests for _get_pending_attestations."""

    def test_extracts_pending(self):
        """Extracts PendingAttestations from a timestamp."""
        digest = _make_digest()
        ts = Timestamp(digest)
        ts.attestations.add(PendingAttestation("https://cal1.example.com"))
        ts.attestations.add(PendingAttestation("https://cal2.example.com"))

        pending = _get_pending_attestations(ts)
        assert len(pending) == 2
        uris = {att.uri for _, att in pending}
        assert "https://cal1.example.com" in uris
        assert "https://cal2.example.com" in uris

    def test_ignores_bitcoin(self):
        """Does not include BitcoinBlockHeaderAttestations."""
        digest = _make_digest()
        ts = Timestamp(digest)
        ts.attestations.add(PendingAttestation("https://example.com"))
        ts.attestations.add(BitcoinBlockHeaderAttestation(800000))

        pending = _get_pending_attestations(ts)
        assert len(pending) == 1
        assert isinstance(pending[0][1], PendingAttestation)

    def test_empty_timestamp(self):
        """Empty timestamp returns empty list."""
        digest = _make_digest()
        ts = Timestamp(digest)
        assert _get_pending_attestations(ts) == []

    def test_pending_in_ops_chain(self):
        """PendingAttestation nested in ops chain is extracted."""
        digest = _make_digest()
        ts = Timestamp(digest)
        child = ts.ops.add(OpSHA256())
        child.attestations.add(PendingAttestation("https://nested.example.com"))

        pending = _get_pending_attestations(ts)
        assert len(pending) == 1
        assert pending[0][1].uri == "https://nested.example.com"

    def test_returns_commitment_bytes(self):
        """Each pending attestation is paired with its commitment message."""
        digest = _make_digest()
        ts = _make_pending_timestamp(digest, "https://example.com")

        pending = _get_pending_attestations(ts)
        assert len(pending) == 1
        commitment, att = pending[0]
        assert isinstance(commitment, bytes)
        assert len(commitment) == 32  # SHA-256


# ---------------------------------------------------------------------------
# _merge_at_commitment
# ---------------------------------------------------------------------------


class TestMergeAtCommitment:
    """Tests for _merge_at_commitment."""

    def test_merge_at_root(self):
        """Merge succeeds when commitment matches root timestamp."""
        digest = _make_digest()
        root = _make_pending_timestamp(digest)
        new_ts = _make_bitcoin_timestamp(digest)

        result = _merge_at_commitment(root, digest, new_ts)
        assert result is True
        assert _has_bitcoin_attestation(root)

    def test_merge_at_child(self):
        """Merge succeeds when commitment matches a child op node."""
        digest = _make_digest()
        root = Timestamp(digest)
        child = root.ops.add(OpSHA256())
        child.attestations.add(PendingAttestation("https://example.com"))
        commitment = child.msg

        new_ts = _make_bitcoin_timestamp(commitment)
        result = _merge_at_commitment(root, commitment, new_ts)
        assert result is True
        assert _has_bitcoin_attestation(root)

    def test_no_match_returns_false(self):
        """Returns False when commitment does not match any node."""
        digest = _make_digest()
        root = _make_pending_timestamp(digest)
        unrelated_commitment = _make_digest("z" * 40)
        new_ts = _make_bitcoin_timestamp(unrelated_commitment)

        result = _merge_at_commitment(root, unrelated_commitment, new_ts)
        assert result is False
        assert not _has_bitcoin_attestation(root)


# ---------------------------------------------------------------------------
# _submit_to_calendar
# ---------------------------------------------------------------------------


class TestSubmitToCalendar:
    """Tests for _submit_to_calendar."""

    def test_success(self):
        """Successful calendar response returns a Timestamp."""
        digest = _make_digest()
        ts = _make_pending_timestamp(digest, "https://a.pool.opentimestamps.org")
        body = _serialize_timestamp(ts)

        resp = MagicMock()
        resp.status_code = 200
        resp.content = body

        with patch("yanantin.provenance.timestamp.httpx.post", return_value=resp):
            result = _submit_to_calendar(digest, "https://a.pool.opentimestamps.org")

        assert result is not None
        assert isinstance(result, Timestamp)
        assert result.msg == digest

    def test_non_200_returns_none(self):
        """Non-200 response returns None."""
        digest = _make_digest()
        resp = MagicMock()
        resp.status_code = 503
        resp.text = "Service Unavailable"

        with patch("yanantin.provenance.timestamp.httpx.post", return_value=resp):
            result = _submit_to_calendar(digest, "https://a.pool.opentimestamps.org")

        assert result is None

    def test_connection_error_returns_none(self):
        """Connection error returns None."""
        digest = _make_digest()

        with patch("yanantin.provenance.timestamp.httpx.post") as mock_post:
            mock_post.side_effect = httpx.ConnectError("refused")
            result = _submit_to_calendar(digest, "https://a.pool.opentimestamps.org")

        assert result is None

    def test_timeout_returns_none(self):
        """Timeout returns None."""
        digest = _make_digest()

        with patch("yanantin.provenance.timestamp.httpx.post") as mock_post:
            mock_post.side_effect = httpx.TimeoutException("timed out")
            result = _submit_to_calendar(digest, "https://a.pool.opentimestamps.org")

        assert result is None

    def test_posts_to_correct_url(self):
        """POST goes to {calendar_url}/digest."""
        digest = _make_digest()

        with patch("yanantin.provenance.timestamp.httpx.post") as mock_post:
            mock_post.side_effect = httpx.ConnectError("no network")
            _submit_to_calendar(digest, "https://test.calendar.org")

        mock_post.assert_called_once()
        call_url = mock_post.call_args.args[0] if mock_post.call_args.args else mock_post.call_args.kwargs.get("url", "")
        assert call_url == "https://test.calendar.org/digest"

    def test_sends_raw_digest_as_content(self):
        """POST body is the raw 32-byte digest."""
        digest = _make_digest()

        with patch("yanantin.provenance.timestamp.httpx.post") as mock_post:
            mock_post.side_effect = httpx.ConnectError("no network")
            _submit_to_calendar(digest, "https://test.calendar.org")

        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs.get("content") == digest


# ---------------------------------------------------------------------------
# upgrade_pending_proofs
# ---------------------------------------------------------------------------


class TestUpgradePendingProofs:
    """Tests for upgrade_pending_proofs."""

    def test_nonexistent_directory(self, tmp_path: Path):
        """Nonexistent directory returns empty list."""
        result = upgrade_pending_proofs(tmp_path / "no_such_dir")
        assert result == []

    def test_empty_directory(self, tmp_path: Path):
        """Empty directory returns empty list."""
        result = upgrade_pending_proofs(tmp_path)
        assert result == []

    def test_age_filter_skips_recent(self, tmp_path: Path):
        """Proofs newer than MIN_UPGRADE_AGE are not upgraded."""
        digest = _make_digest()
        ots_file = tmp_path / "recent.ots"
        ots_file.write_bytes(_make_pending_ots_bytes(digest))
        # File was just created, so it's recent

        with patch("yanantin.provenance.timestamp.httpx.get") as mock_get:
            result = upgrade_pending_proofs(tmp_path)

        assert result == []
        mock_get.assert_not_called()

    def test_old_proof_is_attempted(self, tmp_path: Path):
        """Proofs older than MIN_UPGRADE_AGE are attempted for upgrade."""
        digest = _make_digest()
        ots_file = tmp_path / "old.ots"
        ots_file.write_bytes(_make_pending_ots_bytes(digest))

        # Make the file appear old by backdating its mtime
        old_time = time.time() - MIN_UPGRADE_AGE - 100
        os.utime(ots_file, (old_time, old_time))

        with patch("yanantin.provenance.timestamp.httpx.get") as mock_get:
            resp = MagicMock()
            resp.status_code = 404
            mock_get.return_value = resp
            result = upgrade_pending_proofs(tmp_path)

        assert result == []
        # But httpx.get was called (upgrade was attempted)
        assert mock_get.called

    def test_successful_upgrade(self, tmp_path: Path):
        """When a calendar returns a bitcoin attestation, the proof is upgraded."""
        digest = _make_digest()
        calendar_uri = "https://a.pool.opentimestamps.org"

        # Create a pending proof with known structure
        ts = _make_pending_timestamp(digest, calendar_uri)
        dtf = DetachedTimestampFile(OpSHA256(), ts)
        data = _serialize_detached(dtf)

        ots_file = tmp_path / "upgradeable.ots"
        ots_file.write_bytes(data)

        # Backdate the file
        old_time = time.time() - MIN_UPGRADE_AGE - 100
        os.utime(ots_file, (old_time, old_time))

        # The pending attestation's commitment is the digest itself
        # Create an upgraded response with bitcoin attestation
        upgraded_ts = _make_bitcoin_timestamp(digest, height=800500)
        upgraded_body = _serialize_timestamp(upgraded_ts)

        resp = MagicMock()
        resp.status_code = 200
        resp.content = upgraded_body

        with patch("yanantin.provenance.timestamp.httpx.get", return_value=resp):
            result = upgrade_pending_proofs(tmp_path)

        assert "upgradeable.ots" in result

        # Verify the file on disk is now confirmed
        status = verify_proof(ots_file)
        assert status["status"] == "confirmed"

    def test_upgrade_still_pending(self, tmp_path: Path):
        """When calendar returns a timestamp still pending, proof is not upgraded."""
        digest = _make_digest()
        calendar_uri = "https://a.pool.opentimestamps.org"

        ts = _make_pending_timestamp(digest, calendar_uri)
        dtf = DetachedTimestampFile(OpSHA256(), ts)
        data = _serialize_detached(dtf)

        ots_file = tmp_path / "stillpending.ots"
        ots_file.write_bytes(data)

        old_time = time.time() - MIN_UPGRADE_AGE - 100
        os.utime(ots_file, (old_time, old_time))

        # Calendar returns a still-pending timestamp
        still_pending_ts = _make_pending_timestamp(digest, calendar_uri)
        still_pending_body = _serialize_timestamp(still_pending_ts)

        resp = MagicMock()
        resp.status_code = 200
        resp.content = still_pending_body

        with patch("yanantin.provenance.timestamp.httpx.get", return_value=resp):
            result = upgrade_pending_proofs(tmp_path)

        assert result == []

    def test_upgrade_network_failure(self, tmp_path: Path):
        """Network failure during upgrade does not crash."""
        digest = _make_digest()
        ots_file = tmp_path / "netfail.ots"
        ots_file.write_bytes(_make_pending_ots_bytes(digest))

        old_time = time.time() - MIN_UPGRADE_AGE - 100
        os.utime(ots_file, (old_time, old_time))

        with patch("yanantin.provenance.timestamp.httpx.get") as mock_get:
            mock_get.side_effect = httpx.ConnectError("no network")
            result = upgrade_pending_proofs(tmp_path)

        assert result == []

    def test_already_confirmed_not_upgraded(self, tmp_path: Path):
        """Already-confirmed proofs are not attempted for upgrade."""
        digest = _make_digest()
        ots_file = tmp_path / "confirmed.ots"
        ots_file.write_bytes(_make_bitcoin_ots_bytes(digest))

        old_time = time.time() - MIN_UPGRADE_AGE - 100
        os.utime(ots_file, (old_time, old_time))

        with patch("yanantin.provenance.timestamp.httpx.get") as mock_get:
            result = upgrade_pending_proofs(tmp_path)

        assert result == []
        mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# Red-bar constraints
# ---------------------------------------------------------------------------


class TestRedBarConstraints:
    """Structural invariants: no real network calls, no writes outside tmp_path."""

    def test_no_hardcoded_home_paths(self):
        """Source file does not contain hardcoded references to user home dirs."""
        import inspect

        from yanantin.provenance import timestamp as mod

        source = inspect.getsource(mod)
        # Check that the source module doesn't bake in any absolute home paths
        assert "home/tony" not in source.lower()

    def test_calendar_urls_are_https(self):
        """All calendar URLs use HTTPS."""
        for url in CALENDAR_URLS:
            assert url.startswith("https://"), f"Non-HTTPS URL: {url}"

    def test_stamp_commit_writes_only_in_ots_dir(self, tmp_path: Path):
        """stamp_commit only creates files inside the specified ots_dir."""
        ots_dir = tmp_path / "ots_only"
        digest = _make_digest()

        with patch("yanantin.provenance.timestamp.httpx.post") as mock_post:
            ts = _make_pending_timestamp(digest, CALENDAR_URLS[0])
            body = _serialize_timestamp(ts)
            resp = MagicMock()
            resp.status_code = 200
            resp.content = body
            mock_post.return_value = resp
            stamp_commit(FAKE_COMMIT_HASH, ots_dir)

        # Only files should be in ots_dir
        all_files = list(tmp_path.rglob("*"))
        for f in all_files:
            if f.is_file():
                assert str(f).startswith(str(ots_dir)), (
                    f"File created outside ots_dir: {f}"
                )


# ---------------------------------------------------------------------------
# Public API re-exports
# ---------------------------------------------------------------------------


class TestPublicAPIExports:
    """Verify the public API is correctly exported from yanantin.provenance."""

    def test_stamp_commit_importable(self):
        """stamp_commit is importable from yanantin.provenance."""
        from yanantin.provenance import stamp_commit as sc

        assert callable(sc)

    def test_verify_proof_importable(self):
        """verify_proof is importable from yanantin.provenance."""
        from yanantin.provenance import verify_proof as vp

        assert callable(vp)

    def test_list_proofs_importable(self):
        """list_proofs is importable from yanantin.provenance."""
        from yanantin.provenance import list_proofs as lp

        assert callable(lp)

    def test_upgrade_pending_proofs_importable(self):
        """upgrade_pending_proofs is importable from yanantin.provenance."""
        from yanantin.provenance import upgrade_pending_proofs as upp

        assert callable(upp)
