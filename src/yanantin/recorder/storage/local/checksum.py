"""Checksum recorders — normalize file checksums into tensors and facts.

Co-located with the linux local recorders. Consumes ``ChecksumData`` from
``collector.storage.local.checksum`` and records it either as a two-strand
tensor (identity + digests) or as a single activity-stream fact.
"""

from __future__ import annotations

from pathlib import Path
from uuid import NAMESPACE_DNS, UUID, uuid5

from yanantin.apacheta.interface import ApachetaInterface
from yanantin.apacheta.models import (
    ProvenanceEnvelope,
    SourceIdentifier,
    StrandRecord,
    TensorRecord,
)
from yanantin.activity.models import FactRecord
from yanantin.activity.store import ActivityStreamStore
from yanantin.collector.storage.local.checksum import (
    ChecksumCollector,
    ChecksumData,
)
from yanantin.recorder.base import FactRecorderBase, RecorderBase
from yanantin.transport.models import WranglerEnvelope
from yanantin.transport.wranglers import DirectWrangler

_DEFAULT_ALGORITHMS = ("sha256", "sha1", "md5")


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
