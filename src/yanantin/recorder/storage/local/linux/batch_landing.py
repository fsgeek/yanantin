# src/yanantin/recorder/storage/local/linux/batch_landing.py
"""Batch landing — the millions-scale write path (goal 2026-07-03).

collector→file→recorder→bulk, the Indaleko fan-out: the collector streams
entries to JSONL (the file IS the retained raw, and restartability), then the
landing pass reads it back in chunks and lands objects + edges through the
Registrar batch APIs. Measured basis: singular contribute() = 457 docs/s;
chunked insert_many = 56k docs/s on the same live server.

The throughput gate is asserted from MEASURED run fields, and the reported
rate must be consistent with count/elapsed — a lied-about rate raises. The
gate refuses aspiration: 10k docs/s is 5x below the measured probe.
"""

from __future__ import annotations

import gzip
import time
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import IO
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict

from yanantin.collector.storage.local.linux.models import FileEntryData
from yanantin.core.registration import Registrar
from yanantin.recorder.storage.local.linux.normalize import (
    NAMESPACE,
    normalize_file_entry,
)
from yanantin.recorder.storage.local.linux.registration import (
    CONTAINS_RELATION,
    RECORDER_ID,
)

MIN_LANDING_RATE_DOCS_PER_SECOND = 10_000.0
MIN_GATED_DOC_COUNT = 100_000
# Reported rate may drift from landed/elapsed by rounding, never by more:
_RATE_CONSISTENCY_TOLERANCE = 0.01


class BatchLandingRunReport(BaseModel):
    """Measured facts of one landing run. extra="allow": run metadata nobody
    anticipated (run_id, jsonl path, host) is kept, not rejected."""

    model_config = ConfigDict(extra="allow")

    real_doc_count: int
    landed_doc_count: int
    landing_elapsed_seconds: float
    landing_docs_per_second: float


def assert_landing_throughput(
    report: BatchLandingRunReport,
    *,
    min_rate: float = MIN_LANDING_RATE_DOCS_PER_SECOND,
    min_docs: int = MIN_GATED_DOC_COUNT,
) -> None:
    """The gate, from measured fields only. Raises AssertionError when the
    run is too small to gate, too slow, or reports a rate inconsistent with
    its own count/elapsed (the anti-gaming check)."""
    if report.landed_doc_count < min_docs:
        raise AssertionError(
            f"landing gated on >= {min_docs} docs; "
            f"landed {report.landed_doc_count} — too small to gate"
        )
    if report.landing_elapsed_seconds <= 0:
        raise AssertionError(
            f"non-positive elapsed time {report.landing_elapsed_seconds!r}"
        )
    computed = report.landed_doc_count / report.landing_elapsed_seconds
    if abs(report.landing_docs_per_second - computed) > max(
        _RATE_CONSISTENCY_TOLERANCE * computed, 1.0
    ):
        raise AssertionError(
            f"reported rate {report.landing_docs_per_second:,.0f} docs/s is "
            f"inconsistent with landed/elapsed = {computed:,.0f} docs/s"
        )
    if computed < min_rate:
        raise AssertionError(
            f"landing ran at {computed:,.0f} docs/s; gate is {min_rate:,.0f}"
        )


def _open_maybe_gzip(path: Path, mode: str) -> IO:
    if path.suffix == ".gz":
        return gzip.open(path, mode + "t", encoding="utf-8")
    return open(path, mode, encoding="utf-8")


def write_entries_jsonl(entries: Iterable[FileEntryData], path: Path) -> int:
    """Stream entries to JSONL (gzipped when the path ends .gz) without ever
    holding the tree in memory. Returns the entry count written."""
    count = 0
    with _open_maybe_gzip(path, "w") as sink:
        for entry in entries:
            sink.write(entry.model_dump_json() + "\n")
            count += 1
    return count


def _read_entries_jsonl(path: Path) -> Iterator[FileEntryData]:
    with _open_maybe_gzip(path, "r") as source:
        for line in source:
            line = line.strip()
            if line:
                yield FileEntryData.model_validate_json(line)


def land_jsonl(
    registrar: Registrar,
    jsonl_path: Path,
    provider_id: UUID,
    *,
    recorder_id: UUID = RECORDER_ID,
    chunk_size: int = 10_000,
) -> BatchLandingRunReport:
    """Land a collected JSONL corpus: objects + records-edges + containment
    edges, through the Registrar batch APIs, chunk by chunk.

    Semantics match contribute_snapshot() (the singular path) exactly — same
    normalization, same keys, same edge endpoints — so relanding is idempotent
    for the same structural reason: identity is uuid5(source:uri), not insert
    order. Containment uses a running set of SEEN DIRECTORY uris instead of the
    singular path's whole-snapshot uri set: os.walk is top-down, so a parent
    directory always precedes its children in the stream, and only directories
    can be parents — same edges, ~1% of the memory.
    """
    if not registrar.owns_owned_collection:
        raise ValueError(
            "well_known Objects target has no owning collection on the "
            "handed registrar; construct it with owned_collection=Objects "
            "(well_known never mints — that is the dynamic path)"
        )
    if not registrar.owns_edge_collection:
        raise ValueError(
            "well_known Relationships target has no owning edge collection; "
            "construct the registrar with owned_edge_collection=Relationships"
        )
    objects_name = registrar.owned_collection_name

    seen_dir_uris: set[str] = set()
    real = 0
    landed = 0
    started = time.monotonic()

    object_docs: list[dict] = []
    edge_docs: list[dict] = []

    def _flush() -> None:
        nonlocal landed
        if object_docs:
            landed += registrar.contribute_many(
                provider_id, object_docs, chunk_size=chunk_size
            )
            object_docs.clear()
        if edge_docs:
            landed += registrar.contribute_edge_many(
                recorder_id, edge_docs, chunk_size=chunk_size
            )
            edge_docs.clear()

    for entry in _read_entries_jsonl(jsonl_path):
        obj = normalize_file_entry(entry, source=provider_id)
        obj_key = str(obj.object_identifier)
        object_docs.append({"_key": obj_key, **obj.to_contribution_fields()})
        edge_docs.append(
            {
                "from_ref": f"entities/{recorder_id}",
                "to_ref": f"{objects_name}/{obj_key}",
                "relation_type": "records",
            }
        )
        real += 1
        parent_uri = entry.uri.rsplit("/", 1)[0]
        if parent_uri != entry.uri and parent_uri in seen_dir_uris:
            parent_key = str(uuid5(NAMESPACE, f"{provider_id}:{parent_uri}"))
            edge_docs.append(
                {
                    "from_ref": f"{objects_name}/{parent_key}",
                    "to_ref": f"{objects_name}/{obj_key}",
                    "relation_type": CONTAINS_RELATION,
                }
            )
            real += 1
        real += 1  # the records edge
        if entry.is_directory:
            seen_dir_uris.add(entry.uri)
        if len(object_docs) >= chunk_size:
            _flush()
    _flush()

    elapsed = time.monotonic() - started
    return BatchLandingRunReport(
        real_doc_count=real,
        landed_doc_count=landed,
        landing_elapsed_seconds=elapsed,
        landing_docs_per_second=(landed / elapsed) if elapsed > 0 else 0.0,
        jsonl_path=str(jsonl_path),
        provider_id=str(provider_id),
        recorder_id=str(recorder_id),
    )
