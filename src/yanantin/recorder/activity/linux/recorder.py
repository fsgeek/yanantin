"""Filesystem event recorder — stores change batches as tensors."""

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
from yanantin.collector.activity.linux.models import FsEventBatch
from yanantin.recorder.base import RecorderBase
from yanantin.transport.models import WranglerEnvelope
from yanantin.transport.wranglers import DirectWrangler


class FsEventRecorder(RecorderBase[FsEventBatch]):
    """Normalizes a filesystem event batch into a tensor and stores it."""

    def __init__(self, interface: ApachetaInterface) -> None:
        super().__init__(interface)
        self._recorder_id = uuid5(
            NAMESPACE_DNS,
            "yanantin.recorder.fs_events",
        )

    def record(self, envelope: WranglerEnvelope[FsEventBatch]) -> UUID:
        """Create a tensor from the event batch and store it."""
        data = envelope.data

        summary_strand = StrandRecord(
            strand_index=0,
            title="Event Batch Metadata",
            content=(
                f"volumes: {', '.join(data.volumes)}\n"
                f"event_count: {len(data.events)}\n"
                f"last_run: {data.last_run.isoformat() if data.last_run else 'first run'}\n"
                f"current_run: {data.current_run.isoformat()}"
            ),
            topics=("fs-events", "batch-metadata"),
        )

        events_json = json.dumps(
            [e.model_dump(mode="json") for e in data.events],
            separators=(",", ":"),
        )
        data_strand = StrandRecord(
            strand_index=1,
            title="Filesystem Change Events",
            content=events_json,
            topics=("fs-events", "events", "data"),
        )

        content_tag = f"content:{self._content_hash(data)}"
        tensor = TensorRecord(
            provenance=ProvenanceEnvelope(
                source=SourceIdentifier(
                    identifier=envelope.provider_id,
                    description="Incremental filesystem event collector",
                ),
                author_model_family="collector",
            ),
            preamble=f"Filesystem events: {len(data.events)} changes across {len(data.volumes)} volume(s)",
            strands=(summary_strand, data_strand),
            lineage_tags=("fs-events", "incremental", content_tag),
        )

        self.interface.store_tensor(tensor)
        return tensor.id

    def get_recorder_id(self) -> UUID:
        return self._recorder_id

    def get_description(self) -> str:
        return "Filesystem event recorder — stores change batches as tensors"


def collect_and_record_fs_events(
    interface: ApachetaInterface,
    volumes: list[str],
    state_file: Path,
    since=None,
) -> UUID:
    """Full pipeline: collect → wrangle → record filesystem events."""
    from yanantin.collector.activity.linux.collector import FsIncrementalCollector

    collector = FsIncrementalCollector(volumes, state_file)
    wrangler: DirectWrangler[FsEventBatch] = DirectWrangler()
    recorder = FsEventRecorder(interface)

    data = collector.collect(since=since)
    envelope: WranglerEnvelope[FsEventBatch] = WranglerEnvelope(
        data=data,
        provider_id=collector.get_provider_id(),
    )

    wrangler.deliver(envelope)
    received = wrangler.receive()
    if received is None:
        msg = "DirectWrangler returned None — this should not happen"
        raise RuntimeError(msg)

    return recorder.record(received)
