"""Filesystem snapshot recorder — stores directory walk results as tensors.

Takes a WranglerEnvelope[FilesystemSnapshot], maps it to a two-strand
TensorRecord (summary + JSON entries), and stores via ApachetaInterface.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import NAMESPACE_DNS, UUID, uuid5

from yanantin.apacheta.interface import ApachetaInterface
from yanantin.apacheta.models import (
    ProvenanceEnvelope,
    SourceIdentifier,
    StrandRecord,
    TensorRecord,
)
from yanantin.collector.storage.local.linux.models import FilesystemSnapshot
from yanantin.recorder.base import RecorderBase
from yanantin.transport.models import WranglerEnvelope
from yanantin.transport.wranglers import DirectWrangler


class FilesystemRecorder(RecorderBase[FilesystemSnapshot]):
    """Normalizes a filesystem snapshot into a tensor and stores it.

    Creates a two-strand tensor: snapshot summary (root, counts, timing)
    and machine-readable entries (JSON array of FileEntryData).
    """

    def __init__(self, interface: ApachetaInterface) -> None:
        super().__init__(interface)
        self._recorder_id = uuid5(
            NAMESPACE_DNS,
            "yanantin.recorder.filesystem",
        )

    def record(self, envelope: WranglerEnvelope[FilesystemSnapshot]) -> UUID:
        """Create a tensor from the filesystem snapshot and store it."""
        data = envelope.data

        summary_strand = StrandRecord(
            strand_index=0,
            title="Filesystem Snapshot Summary",
            content=(
                f"root_path: {data.root_path}\n"
                f"total_files: {data.total_files}\n"
                f"total_dirs: {data.total_dirs}\n"
                f"error_count: {data.error_count}\n"
                f"collected_at: {data.collected_at.isoformat()}"
            ),
            topics=("filesystem", "snapshot", "summary"),
        )

        entries_json = json.dumps(
            [e.model_dump(mode="json") for e in data.entries],
            separators=(",", ":"),
        )
        data_strand = StrandRecord(
            strand_index=1,
            title="Filesystem Entries",
            content=entries_json,
            topics=("filesystem", "entries", "data"),
        )

        content_tag = f"content:{self._content_hash(data)}"
        tensor = TensorRecord(
            provenance=ProvenanceEnvelope(
                source=SourceIdentifier(
                    identifier=envelope.provider_id,
                    description="Filesystem metadata collector",
                ),
                author_model_family="collector",
            ),
            preamble=f"Filesystem snapshot of {data.root_path} ({data.total_files} files, {data.total_dirs} dirs)",
            strands=(summary_strand, data_strand),
            lineage_tags=("filesystem", "snapshot", content_tag),
        )

        self.interface.store_tensor(tensor)
        return tensor.id

    def get_recorder_id(self) -> UUID:
        return self._recorder_id

    def get_description(self) -> str:
        return "Filesystem recorder — stores directory snapshots as tensors"


def collect_and_record_filesystem(
    interface: ApachetaInterface,
    root_path: Path,
    since=None,
) -> UUID:
    """Full pipeline: collect → wrangle → record a filesystem snapshot."""
    from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector

    collector = LinuxFilesystemCollector(root_path)
    wrangler: DirectWrangler[FilesystemSnapshot] = DirectWrangler()
    recorder = FilesystemRecorder(interface)

    data = collector.collect(since=since)
    envelope: WranglerEnvelope[FilesystemSnapshot] = WranglerEnvelope(
        data=data,
        provider_id=collector.get_provider_id(),
    )

    wrangler.deliver(envelope)
    received = wrangler.receive()
    if received is None:
        msg = "DirectWrangler returned None — this should not happen"
        raise RuntimeError(msg)

    return recorder.record(received)
