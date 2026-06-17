"""End-to-end pipeline: collect -> wrangle -> record facts -> anchor.

Wires the collector/wrangler/fact-recorder pipeline to the activity
stream and memory anchor service. The CLI and programmatic callers
use this to avoid repeating the same wiring pattern.

Backend selection via string name + environment variables:
- "memory" — InMemoryActivityStreamStore (data dies with process)
- "duckdb" — DuckDBActivityStreamStore (local file, env: YANANTIN_DUCKDB_PATH)
- "arango" — ArangoDBActivityStreamStore (production, env: YANANTIN_ARANGO_*)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from yanantin.activity.anchor import MemoryAnchorService
from yanantin.activity.store import ActivityStreamStore
from yanantin.recorder.base import FactRecorderBase
from yanantin.transport.models import WranglerEnvelope
from yanantin.transport.wranglers import DirectWrangler


@dataclass(frozen=True)
class PipelineResult:
    """What happened when facts were recorded."""

    fact_count: int
    provider_id: UUID
    anchor_handle: UUID | None
    anchor_flushed: bool
    backend: str


def open_store(backend: str) -> ActivityStreamStore:
    """Create an ActivityStreamStore from a backend name.

    Environment variables for each backend:
    - duckdb: YANANTIN_DUCKDB_PATH (default: ~/.local/share/yanantin/activity.duckdb)
    - arango: YANANTIN_ARANGO_HOST (default: http://localhost:8529)
              YANANTIN_ARANGO_DB   (default: apacheta)
              YANANTIN_ARANGO_USER (default: "")
              YANANTIN_ARANGO_PASSWORD (default: "")

    DuckDB uses semantic names (local trusted storage).
    ArangoDB uses the transparent default — obfuscation is Pukara's job.
    When Pukara gets activity endpoints, the collector will go through
    the gateway client instead of connecting directly.
    """
    if backend == "memory":
        from yanantin.activity.backends.memory import InMemoryActivityStreamStore
        return InMemoryActivityStreamStore()

    if backend == "duckdb":
        from yanantin.activity.backends.duckdb import DuckDBActivityStreamStore
        default_path = Path.home() / ".local" / "share" / "yanantin" / "activity.duckdb"
        db_path = os.environ.get("YANANTIN_DUCKDB_PATH", str(default_path))
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return DuckDBActivityStreamStore(db_path)

    if backend == "arango":
        from yanantin.activity.backends.arango import ArangoDBActivityStreamStore
        return ArangoDBActivityStreamStore(
            host=os.environ.get("YANANTIN_ARANGO_HOST", "http://localhost:8529"),
            db_name=os.environ.get("YANANTIN_ARANGO_DB", "apacheta"),
            username=os.environ.get("YANANTIN_ARANGO_USER", ""),
            password=os.environ.get("YANANTIN_ARANGO_PASSWORD", ""),
        )

    raise ValueError(f"Unknown backend: {backend!r}. Choose memory, duckdb, or arango.")


def record_and_anchor(
    store: ActivityStreamStore,
    recorder: FactRecorderBase,
    envelope: WranglerEnvelope,
    backend_name: str = "unknown",
) -> PipelineResult:
    """Record facts from an envelope and update the memory anchor.

    This is the complete pipeline tail: record facts, update cursor,
    get handle, flush anchor. The anchor service is created fresh
    each invocation — it reconstructs cursor state from the store.
    """
    # Record facts
    wrangler = DirectWrangler()
    wrangler.deliver(envelope)
    received = wrangler.receive()
    fact_count = recorder.record_facts(received)

    # Wire the anchor service
    service = MemoryAnchorService(store)

    # Update cursor: provider has new data, reference is the recorder's ID
    service.update_cursor(
        provider=envelope.provider_id,
        reference=recorder.get_recorder_id(),
        data=recorder.get_description(),
    )

    # Get handle (sets referenced=True) and flush (write gate: updated AND referenced)
    handle = service.get_handle()
    flushed = service.flush()

    return PipelineResult(
        fact_count=fact_count,
        provider_id=envelope.provider_id,
        anchor_handle=handle if flushed else None,
        anchor_flushed=flushed,
        backend=backend_name,
    )
