"""Checksum collector — semantic content metadata via cryptographic hashes.

Computes multiple hash algorithms in a single read pass using mmap for
large files. Follows the Indaleko pattern: one pass through the file data,
all requested digests computed simultaneously.
"""

from __future__ import annotations

import hashlib
import mmap
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_DNS, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Self

from yanantin.apacheta.interface import ApachetaInterface
from yanantin.apacheta.models import (
    ProvenanceEnvelope,
    SourceIdentifier,
    StrandRecord,
    TensorRecord,
)
from yanantin.activity.models import FactRecord
from yanantin.activity.store import ActivityStreamStore
from yanantin.collector.base import CollectorBase, FactRecorderBase, RecorderBase
from yanantin.collector.models import WranglerEnvelope
from yanantin.collector.synthetic import SyntheticCollectorBase
from yanantin.collector.wranglers import DirectWrangler

# Threshold for using mmap vs direct read. Files under 1 MiB use
# read() since mmap overhead isn't worth it for small files.
_MMAP_THRESHOLD = 1024 * 1024

# Default chunk size for reading files without mmap.
_READ_CHUNK = 64 * 1024

_DEFAULT_ALGORITHMS = ("sha256", "sha1", "md5")


class ChecksumData(BaseModel):
    """Cryptographic checksums for a single file.

    Validators enforce: file_size is non-negative, checksums keys match
    the declared algorithms, algorithms is non-empty, and all digests
    are valid hex strings.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: str
    file_size: int
    checksums: dict[str, str]
    algorithms: tuple[str, ...]
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        if not self.file_path:
            raise ValueError("file_path must be non-empty")
        if self.file_size < 0:
            raise ValueError(f"file_size must be >= 0, got {self.file_size}")
        if len(self.algorithms) == 0:
            raise ValueError("algorithms must be non-empty")
        if set(self.checksums.keys()) != set(self.algorithms):
            raise ValueError(
                f"checksums keys {set(self.checksums.keys())} "
                f"!= algorithms {set(self.algorithms)}"
            )
        for alg, digest in self.checksums.items():
            try:
                int(digest, 16)
            except ValueError:
                raise ValueError(
                    f"checksum for {alg} is not valid hex: {digest!r}"
                )
        return self


class ChecksumCollector(CollectorBase[ChecksumData]):
    """Computes cryptographic checksums for a file.

    Uses mmap for files over 1 MiB to avoid loading the entire file
    into memory. All requested algorithms are computed in a single
    read pass — the file data flows through all hashers simultaneously.
    """

    def __init__(
        self,
        file_path: Path,
        algorithms: tuple[str, ...] = _DEFAULT_ALGORITHMS,
    ) -> None:
        self._file_path = file_path.resolve()
        self._algorithms = algorithms
        self._provider_id = uuid5(
            NAMESPACE_DNS, "yanantin.collector.checksum",
        )

    def collect(self, since: datetime | None = None) -> ChecksumData:
        """Compute all requested checksums in a single pass.

        The ``since`` parameter is accepted but ignored — the caller
        decides whether to invoke the collector at all.
        """
        file_size = self._file_path.stat().st_size
        hashers = {alg: hashlib.new(alg) for alg in self._algorithms}

        if file_size == 0:
            # Empty file — all hashers already have the right digest
            pass
        elif file_size >= _MMAP_THRESHOLD:
            self._hash_with_mmap(hashers)
        else:
            self._hash_with_read(hashers)

        return ChecksumData(
            file_path=str(self._file_path),
            file_size=file_size,
            checksums={alg: h.hexdigest() for alg, h in hashers.items()},
            algorithms=self._algorithms,
        )

    def _hash_with_mmap(self, hashers: dict[str, hashlib._Hash]) -> None:
        """Hash a large file using mmap."""
        with open(self._file_path, "rb") as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                # Process in chunks to keep memory usage bounded
                offset = 0
                size = mm.size()
                while offset < size:
                    chunk = mm[offset:offset + _READ_CHUNK]
                    for h in hashers.values():
                        h.update(chunk)
                    offset += _READ_CHUNK

    def _hash_with_read(self, hashers: dict[str, hashlib._Hash]) -> None:
        """Hash a small file using buffered read."""
        with open(self._file_path, "rb") as f:
            while True:
                chunk = f.read(_READ_CHUNK)
                if not chunk:
                    break
                for h in hashers.values():
                    h.update(chunk)

    def get_provider_id(self) -> UUID:
        return self._provider_id

    def get_description(self) -> str:
        return (
            f"Checksum collector — computes {', '.join(self._algorithms)} "
            f"for {self._file_path}"
        )


class SyntheticChecksumCollector(SyntheticCollectorBase[ChecksumData]):
    """Generates deterministic checksum data from seeded RNG.

    Produces ChecksumData instances with plausible file paths, sizes,
    and hashes. The hashes are computed from deterministic byte strings
    derived from the seed, so they are real hashes of synthetic content.
    """

    def __init__(
        self,
        seed: int | None = None,
        algorithms: tuple[str, ...] = _DEFAULT_ALGORITHMS,
    ) -> None:
        super().__init__(seed)
        self._algorithms = algorithms

    def generate(self) -> ChecksumData:
        """Generate a single synthetic checksum record."""
        # Build a plausible path
        dirs = ["home", "user", "documents", "projects", "data"]
        exts = [".txt", ".py", ".json", ".csv", ".pdf", ".log"]
        depth = self._rng.randint(2, 4)
        path_parts = [self._rng.choice(dirs) for _ in range(depth)]
        filename = f"file_{self._rng.randint(0, 9999)}{self._rng.choice(exts)}"
        file_path = "/" + "/".join(path_parts) + "/" + filename

        # Generate a deterministic content blob and hash it for real
        content_seed = self._rng.randint(0, 2**32 - 1)
        content = f"synthetic-content-{content_seed}".encode()

        checksums = {}
        for alg in self._algorithms:
            h = hashlib.new(alg)
            h.update(content)
            checksums[alg] = h.hexdigest()

        # Power-law file size
        file_size = int(self._rng.paretovariate(1.5) * 100)

        # Deterministic timestamp from RNG
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        offset_secs = self._rng.random() * 365 * 86400
        collected_at = base + timedelta(seconds=offset_secs)

        return ChecksumData(
            file_path=file_path,
            file_size=file_size,
            checksums=checksums,
            algorithms=self._algorithms,
            collected_at=collected_at,
        )

    def get_description(self) -> str:
        return "Synthetic checksum collector — generates fake checksum data"


# ── Recorder ──────────────────────────────────────────────────────


class ChecksumRecorder(RecorderBase[ChecksumData]):
    """Normalizes checksum data into a tensor and stores it.

    Creates a two-strand tensor: file identity (path, size, timing)
    and cryptographic checksums (algorithm: digest pairs).
    """

    def __init__(self, interface: ApachetaInterface) -> None:
        super().__init__(interface)
        self._recorder_id = uuid5(
            NAMESPACE_DNS,
            "yanantin.recorder.checksum",
        )

    def record(self, envelope: WranglerEnvelope[ChecksumData]) -> UUID:
        """Create a tensor from the checksum data and store it."""
        data = envelope.data

        identity_strand = StrandRecord(
            strand_index=0,
            title="File Identity",
            content=(
                f"file_path: {data.file_path}\n"
                f"file_size: {data.file_size}\n"
                f"collected_at: {data.collected_at.isoformat()}"
            ),
            topics=("checksum", "file-identity"),
        )

        digest_lines = "\n".join(
            f"{alg}: {digest}" for alg, digest in data.checksums.items()
        )
        checksum_strand = StrandRecord(
            strand_index=1,
            title="Cryptographic Checksums",
            content=digest_lines,
            topics=("checksum", "digests"),
        )

        content_tag = f"content:{self._content_hash(data)}"
        tensor = TensorRecord(
            provenance=ProvenanceEnvelope(
                source=SourceIdentifier(
                    identifier=envelope.provider_id,
                    description="Checksum collector",
                ),
                author_model_family="collector",
            ),
            preamble=f"Checksums for {data.file_path} ({data.file_size:,} bytes)",
            strands=(identity_strand, checksum_strand),
            lineage_tags=("checksum", content_tag),
        )

        self.interface.store_tensor(tensor)
        return tensor.id

    def get_recorder_id(self) -> UUID:
        return self._recorder_id

    def get_description(self) -> str:
        return "Checksum recorder — stores file checksums as tensors"


# ── Fact Recorder ─────────────────────────────────────────────────


class ChecksumFactRecorder(FactRecorderBase[ChecksumData]):
    """Stores checksum data as a single fact in the activity stream.

    Unlike the batch-decomposition pattern of other fact recorders,
    a checksum collection produces exactly one fact (one file, one
    set of digests).
    """

    def __init__(self, store: ActivityStreamStore) -> None:
        super().__init__(store)
        self._recorder_id = uuid5(
            NAMESPACE_DNS,
            "yanantin.fact_recorder.checksum",
        )

    def record_facts(self, envelope: WranglerEnvelope[ChecksumData]) -> int:
        """Store one fact for the checksum data. Return 1."""
        data = envelope.data
        data_dict = data.model_dump(mode="json")

        fact = FactRecord(
            provider_id=envelope.provider_id,
            timestamp=data.collected_at,
            data=data_dict,
            content_hash=self._content_hash(data),
        )
        self.store.store_fact(fact)
        return 1

    def get_recorder_id(self) -> UUID:
        return self._recorder_id

    def get_description(self) -> str:
        return "Checksum fact recorder — stores file checksums as facts"


# ── Convenience Functions ─────────────────────────────────────────


def collect_and_record_checksum(
    interface: ApachetaInterface,
    file_path: Path,
    algorithms: tuple[str, ...] = _DEFAULT_ALGORITHMS,
) -> UUID:
    """Full pipeline: collect → wrangle → record file checksums."""
    collector = ChecksumCollector(file_path, algorithms=algorithms)
    wrangler: DirectWrangler[ChecksumData] = DirectWrangler()
    recorder = ChecksumRecorder(interface)

    data = collector.collect()
    envelope: WranglerEnvelope[ChecksumData] = WranglerEnvelope(
        data=data,
        provider_id=collector.get_provider_id(),
    )

    wrangler.deliver(envelope)
    received = wrangler.receive()
    if received is None:
        msg = "DirectWrangler returned None — this should not happen"
        raise RuntimeError(msg)

    return recorder.record(received)
