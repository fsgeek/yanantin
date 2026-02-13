"""OpenTimestamps integration for git commit provenance.

Provides blockchain-anchored proof that specific commits existed at
specific times. Each commit's hash is SHA-256'd and submitted to
OpenTimestamps calendar servers. The pending proof is stored in
docs/ots/{short_hash}.ots and later upgraded to a Bitcoin-anchored
proof when the calendar aggregates it into a block.

The calendar submission protocol:
  1. SHA-256 the ASCII hex commit hash (40 bytes)
  2. POST the 32-byte digest to calendar_url/digest
  3. Calendar returns a binary OTS timestamp with PendingAttestation
  4. Wrap in DetachedTimestampFile and serialize to disk

The upgrade protocol:
  1. Deserialize the .ots file
  2. Walk attestations looking for PendingAttestation
  3. GET calendar_url/timestamp/{commitment_hex}
  4. If upgraded (has BitcoinBlockHeaderAttestation), merge and re-save
"""

from __future__ import annotations

import hashlib
import io
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

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

logger = logging.getLogger(__name__)

# Calendar servers for redundancy. We try each in order until one succeeds.
CALENDAR_URLS = [
    "https://a.pool.opentimestamps.org",
    "https://b.pool.opentimestamps.org",
    "https://alice.btc.calendar.opentimestamps.org",
]

# Timeout for individual calendar requests (seconds).
CALENDAR_TIMEOUT = 10

# Minimum age (seconds) before attempting proof upgrade.
# Bitcoin blocks arrive every ~10 minutes but calendar aggregation
# into a block can take hours.
MIN_UPGRADE_AGE = 7200  # 2 hours

# OTS request headers per the protocol.
OTS_HEADERS = {
    "Accept": "application/vnd.opentimestamps.v1",
    "User-Agent": "yanantin-provenance/0.1",
    "Content-Type": "application/x-www-form-urlencoded",
}


def _commit_hash_to_digest(commit_hash: str) -> bytes:
    """Convert a git commit hash string to a SHA-256 digest.

    Following the ots-git-gpg-wrapper convention: SHA-256 hash the
    ASCII hex representation of the commit hash. This produces a
    32-byte digest suitable for calendar submission.
    """
    return hashlib.sha256(commit_hash.encode("ascii")).digest()


def _submit_to_calendar(
    digest: bytes,
    calendar_url: str,
    timeout: float = CALENDAR_TIMEOUT,
) -> Timestamp | None:
    """Submit a digest to a single calendar server.

    POSTs the raw 32-byte digest to {calendar_url}/digest.
    Returns a Timestamp on success, None on failure.
    """
    url = f"{calendar_url}/digest"
    try:
        resp = httpx.post(
            url,
            content=digest,
            headers=OTS_HEADERS,
            timeout=timeout,
        )
        if resp.status_code != 200:
            logger.warning(
                "Calendar %s returned status %d: %s",
                calendar_url,
                resp.status_code,
                resp.text[:200],
            )
            return None

        ctx = BytesDeserializationContext(resp.content)
        return Timestamp.deserialize(ctx, digest)

    except (httpx.HTTPError, OSError, Exception) as exc:
        logger.warning("Calendar %s submission failed: %s", calendar_url, exc)
        return None


def _serialize_detached(detached: DetachedTimestampFile) -> bytes:
    """Serialize a DetachedTimestampFile to bytes."""
    ctx = BytesSerializationContext()
    detached.serialize(ctx)
    return ctx.getbytes()


def _deserialize_detached(data: bytes) -> DetachedTimestampFile:
    """Deserialize bytes to a DetachedTimestampFile."""
    ctx = BytesDeserializationContext(data)
    return DetachedTimestampFile.deserialize(ctx)


def _collect_attestations(
    timestamp: Timestamp,
) -> list[tuple[bytes, PendingAttestation | BitcoinBlockHeaderAttestation]]:
    """Walk a timestamp tree and collect all attestations with their messages."""
    return list(timestamp.all_attestations())


def _has_bitcoin_attestation(timestamp: Timestamp) -> bool:
    """Check if a timestamp tree contains any BitcoinBlockHeaderAttestation."""
    for _msg, attestation in timestamp.all_attestations():
        if isinstance(attestation, BitcoinBlockHeaderAttestation):
            return True
    return False


def _get_pending_attestations(
    timestamp: Timestamp,
) -> list[tuple[bytes, PendingAttestation]]:
    """Extract all PendingAttestations from a timestamp tree."""
    results = []
    for msg, attestation in timestamp.all_attestations():
        if isinstance(attestation, PendingAttestation):
            results.append((msg, attestation))
    return results


def stamp_commit(commit_hash: str, ots_dir: Path) -> Path | None:
    """Create an OpenTimestamps proof for a git commit hash.

    Submits the SHA-256 of the commit hash to calendar servers and
    stores the resulting proof as a DetachedTimestampFile.

    Args:
        commit_hash: The full hex SHA-1 commit hash (40 characters).
        ots_dir: Directory to store the .ots proof file.

    Returns:
        Path to the .ots file on success, None on failure.
    """
    if not commit_hash or len(commit_hash) < 7:
        logger.error("Invalid commit hash: %r", commit_hash)
        return None

    ots_dir.mkdir(parents=True, exist_ok=True)
    short_hash = commit_hash[:10]
    ots_path = ots_dir / f"{short_hash}.ots"

    if ots_path.exists():
        logger.info("Proof already exists: %s", ots_path)
        return ots_path

    digest = _commit_hash_to_digest(commit_hash)
    logger.info(
        "Stamping commit %s (digest: %s)",
        short_hash,
        digest.hex()[:16] + "...",
    )

    # Try each calendar server until one succeeds.
    # Merge results from multiple servers for redundancy.
    merged_timestamp = None
    successful_calendars = []

    for calendar_url in CALENDAR_URLS:
        result = _submit_to_calendar(digest, calendar_url)
        if result is not None:
            if merged_timestamp is None:
                merged_timestamp = result
            else:
                try:
                    merged_timestamp.merge(result)
                except ValueError:
                    # Different messages — shouldn't happen but be safe.
                    logger.warning(
                        "Calendar %s returned incompatible timestamp",
                        calendar_url,
                    )
                    continue
            successful_calendars.append(calendar_url)
            logger.info("Submitted to %s", calendar_url)

    if merged_timestamp is None:
        logger.error("All calendar servers failed for commit %s", short_hash)
        return None

    # Wrap in DetachedTimestampFile with OpSHA256 as the file hash operation.
    detached = DetachedTimestampFile(OpSHA256(), merged_timestamp)

    try:
        data = _serialize_detached(detached)
        ots_path.write_bytes(data)
        logger.info(
            "Proof saved: %s (%d bytes, %d calendars)",
            ots_path,
            len(data),
            len(successful_calendars),
        )
        return ots_path
    except (OSError, ValueError) as exc:
        logger.error("Failed to save proof %s: %s", ots_path, exc)
        return None


def verify_proof(ots_file: Path) -> dict:
    """Verify an OTS proof file and return its status.

    Returns a dict with:
        - path: str — the file path
        - commit_short: str — short hash from filename
        - status: "confirmed" | "pending" | "error"
        - attestations: list of dicts describing each attestation
        - file_digest_hex: str — the SHA-256 digest in the proof
        - error: str | None — error message if status is "error"
    """
    result = {
        "path": str(ots_file),
        "commit_short": ots_file.stem,
        "status": "error",
        "attestations": [],
        "file_digest_hex": "",
        "error": None,
    }

    if not ots_file.exists():
        result["error"] = "File not found"
        return result

    try:
        data = ots_file.read_bytes()
        detached = _deserialize_detached(data)
    except Exception as exc:
        result["error"] = f"Deserialization failed: {exc}"
        return result

    result["file_digest_hex"] = detached.file_digest.hex()

    has_bitcoin = False
    has_pending = False

    for msg, attestation in detached.timestamp.all_attestations():
        att_info = {
            "type": type(attestation).__name__,
            "message_hex": msg.hex()[:32] + "...",
        }

        if isinstance(attestation, BitcoinBlockHeaderAttestation):
            att_info["bitcoin_height"] = attestation.height
            has_bitcoin = True
        elif isinstance(attestation, PendingAttestation):
            att_info["calendar_uri"] = attestation.uri
            has_pending = True

        result["attestations"].append(att_info)

    if has_bitcoin:
        result["status"] = "confirmed"
    elif has_pending:
        result["status"] = "pending"
    else:
        result["status"] = "error"
        result["error"] = "No recognized attestations found"

    return result


def list_proofs(ots_dir: Path) -> list[dict]:
    """List all OTS proofs in a directory with their status.

    Returns a list of dicts from verify_proof(), sorted by filename.
    """
    if not ots_dir.is_dir():
        return []

    results = []
    for ots_file in sorted(ots_dir.glob("*.ots")):
        results.append(verify_proof(ots_file))

    return results


def _upgrade_single_proof(ots_file: Path) -> bool:
    """Attempt to upgrade a single pending proof.

    Reads the .ots file, checks for PendingAttestations, queries
    each calendar for an upgraded timestamp, and if any return a
    Bitcoin attestation, merges and re-saves.

    Returns True if the proof was upgraded.
    """
    try:
        data = ots_file.read_bytes()
        detached = _deserialize_detached(data)
    except Exception as exc:
        logger.warning("Cannot read proof %s: %s", ots_file, exc)
        return False

    if _has_bitcoin_attestation(detached.timestamp):
        logger.debug("Proof %s already confirmed", ots_file)
        return False

    pending = _get_pending_attestations(detached.timestamp)
    if not pending:
        logger.debug("Proof %s has no pending attestations", ots_file)
        return False

    upgraded = False

    for commitment, attestation in pending:
        calendar_uri = attestation.uri
        commitment_hex = commitment.hex()
        timestamp_url = f"{calendar_uri}/timestamp/{commitment_hex}"

        try:
            resp = httpx.get(
                timestamp_url,
                headers={
                    "Accept": "application/vnd.opentimestamps.v1",
                    "User-Agent": "yanantin-provenance/0.1",
                },
                timeout=CALENDAR_TIMEOUT,
            )

            if resp.status_code == 200:
                ctx = BytesDeserializationContext(resp.content)
                upgraded_timestamp = Timestamp.deserialize(ctx, commitment)

                if _has_bitcoin_attestation(upgraded_timestamp):
                    # Merge the upgraded timestamp into our existing one.
                    # We need to find the right node in the tree to merge into.
                    # The upgraded_timestamp is rooted at 'commitment', which
                    # is the same message as some node in our tree.
                    # Walk the tree to find it and merge.
                    _merge_at_commitment(
                        detached.timestamp, commitment, upgraded_timestamp
                    )
                    upgraded = True
                    logger.info(
                        "Upgraded proof %s via %s",
                        ots_file.name,
                        calendar_uri,
                    )
                else:
                    logger.debug(
                        "Calendar %s responded but still pending",
                        calendar_uri,
                    )

            elif resp.status_code == 404:
                logger.debug(
                    "Calendar %s: commitment not found (yet)",
                    calendar_uri,
                )
            else:
                logger.warning(
                    "Calendar %s returned status %d",
                    calendar_uri,
                    resp.status_code,
                )

        except (httpx.HTTPError, OSError, Exception) as exc:
            logger.warning(
                "Upgrade request to %s failed: %s",
                calendar_uri,
                exc,
            )

    if upgraded:
        try:
            new_data = _serialize_detached(detached)
            ots_file.write_bytes(new_data)
            logger.info("Saved upgraded proof: %s", ots_file)
        except (OSError, ValueError) as exc:
            logger.error(
                "Failed to save upgraded proof %s: %s", ots_file, exc
            )
            return False

    return upgraded


def _merge_at_commitment(
    root_timestamp: Timestamp,
    commitment: bytes,
    new_timestamp: Timestamp,
) -> bool:
    """Recursively find the timestamp node with the given message and merge.

    Walks the timestamp tree to find a node whose msg matches commitment,
    then merges new_timestamp into it.

    Returns True if a merge happened.
    """
    if root_timestamp.msg == commitment:
        root_timestamp.merge(new_timestamp)
        return True

    for op_stamp in root_timestamp.ops.values():
        if _merge_at_commitment(op_stamp, commitment, new_timestamp):
            return True

    return False


def upgrade_pending_proofs(ots_dir: Path) -> list[str]:
    """Scan for pending proofs and attempt to upgrade them.

    Only attempts upgrade on proofs whose .ots file is older than
    MIN_UPGRADE_AGE seconds, to avoid hammering calendars before
    they've had a chance to aggregate.

    Args:
        ots_dir: Directory containing .ots proof files.

    Returns:
        List of filenames that were successfully upgraded.
    """
    if not ots_dir.is_dir():
        logger.debug("OTS directory does not exist: %s", ots_dir)
        return []

    now = time.time()
    upgraded = []

    for ots_file in sorted(ots_dir.glob("*.ots")):
        # Only try upgrading proofs older than the minimum age.
        try:
            file_age = now - ots_file.stat().st_mtime
        except OSError:
            continue

        if file_age < MIN_UPGRADE_AGE:
            logger.debug(
                "Proof %s too recent (%.0fs < %ds), skipping",
                ots_file.name,
                file_age,
                MIN_UPGRADE_AGE,
            )
            continue

        if _upgrade_single_proof(ots_file):
            upgraded.append(ots_file.name)

    return upgraded
