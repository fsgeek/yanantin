"""Dropbox listing recorder — stores cloud file metadata as tensors.

Takes a WranglerEnvelope[DropboxListing], maps it to a two-strand
TensorRecord (account metadata + JSON entries), and stores via ApachetaInterface.
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
from yanantin.collector.storage.cloud.dropbox.models import DropboxListing
from yanantin.recorder.base import RecorderBase
from yanantin.transport.models import WranglerEnvelope
from yanantin.transport.wranglers import DirectWrangler


class DropboxRecorder(RecorderBase[DropboxListing]):
    """Normalizes a Dropbox listing into a tensor and stores it."""

    def __init__(self, interface: ApachetaInterface) -> None:
        super().__init__(interface)
        self._recorder_id = uuid5(
            NAMESPACE_DNS,
            "yanantin.recorder.dropbox",
        )

    def record(self, envelope: WranglerEnvelope[DropboxListing]) -> UUID:
        """Create a tensor from the Dropbox listing and store it."""
        data = envelope.data

        cursor_display = data.cursor[:32] + "..." if len(data.cursor) > 32 else data.cursor

        summary_strand = StrandRecord(
            strand_index=0,
            title="Dropbox Account Metadata",
            content=(
                f"account_email: {data.account_email}\n"
                f"total_files: {data.total_files}\n"
                f"total_folders: {data.total_folders}\n"
                f"cursor: {cursor_display}\n"
                f"collected_at: {data.collected_at.isoformat()}"
            ),
            topics=("dropbox", "account-metadata"),
        )

        entries_json = json.dumps(
            [e.model_dump(mode="json") for e in data.entries],
            separators=(",", ":"),
        )
        data_strand = StrandRecord(
            strand_index=1,
            title="Dropbox File Entries",
            content=entries_json,
            topics=("dropbox", "entries", "data"),
        )

        content_tag = f"content:{self._content_hash(data)}"
        tensor = TensorRecord(
            provenance=ProvenanceEnvelope(
                source=SourceIdentifier(
                    identifier=envelope.provider_id,
                    description="Dropbox cloud storage collector",
                ),
                author_model_family="collector",
            ),
            preamble=f"Dropbox listing for {data.account_email} ({data.total_files} files, {data.total_folders} folders)",
            strands=(summary_strand, data_strand),
            lineage_tags=("dropbox", "listing", content_tag),
        )

        self.interface.store_tensor(tensor)
        return tensor.id

    def get_recorder_id(self) -> UUID:
        return self._recorder_id

    def get_description(self) -> str:
        return "Dropbox recorder — stores cloud file listings as tensors"


def collect_and_record_dropbox(
    interface: ApachetaInterface,
    config_dir: Path,
) -> UUID:
    """Full pipeline: collect → wrangle → record a Dropbox listing."""
    from yanantin.collector.storage.cloud.dropbox.collector import DropboxCollector

    collector = DropboxCollector(config_dir)
    wrangler: DirectWrangler[DropboxListing] = DirectWrangler()
    recorder = DropboxRecorder(interface)

    data = collector.collect()
    envelope: WranglerEnvelope[DropboxListing] = WranglerEnvelope(
        data=data,
        provider_id=collector.get_provider_id(),
    )

    wrangler.deliver(envelope)
    received = wrangler.receive()
    if received is None:
        msg = "DirectWrangler returned None — this should not happen"
        raise RuntimeError(msg)

    return recorder.record(received)
