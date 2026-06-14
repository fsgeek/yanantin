"""Concrete wrangler implementations for the collector pipeline.

Three strategies, ordered by coupling:

- **DirectWrangler** — In-memory handoff. Collector and recorder run
  in the same process, same moment. Simplest path.
- **BatchWrangler** — File-based. Collector writes JSON to a directory,
  recorder reads from it. Decoupled in time.
- **QueuedWrangler** — In-process queue (collections.deque). Decoupled
  in time but same process. Useful for producer/consumer patterns
  within a single run.

All three track provenance: when data was delivered and via what strategy.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import TypeAdapter

from yanantin.transport.base import WranglerBase
from yanantin.transport.models import WranglerEnvelope

DataT = TypeVar("DataT")


class DirectWrangler(WranglerBase[DataT], Generic[DataT]):
    """In-memory wrangler. The recorder wraps the collector.

    The simplest path: deliver() stores the envelope in memory,
    receive() returns it. No serialization, no files, no queues.
    One envelope at a time — deliver replaces any unread envelope.
    """

    def __init__(self) -> None:
        self._pending: WranglerEnvelope[DataT] | None = None

    @property
    def strategy_name(self) -> str:
        return "direct"

    def deliver(self, envelope: WranglerEnvelope[DataT]) -> None:
        self._pending = self.stamp_delivery(envelope)

    def receive(self) -> WranglerEnvelope[DataT] | None:
        result = self._pending
        self._pending = None
        return result


class BatchWrangler(WranglerBase[DataT], Generic[DataT]):
    """File-based wrangler. Collector and recorder are decoupled in time.

    Collector calls deliver(), which writes the envelope as a JSON file
    to a staging directory. Recorder calls receive(), which reads the
    oldest file and removes it. Files are named with timestamps for
    ordering.

    The staging directory must exist before use. Files use atomic
    write (write to temp, rename) to prevent partial reads.
    """

    def __init__(self, staging_dir: Path, data_type: type[DataT]) -> None:
        self._staging_dir = staging_dir
        self._data_type = data_type
        self._envelope_adapter: TypeAdapter[WranglerEnvelope[DataT]] = TypeAdapter(
            WranglerEnvelope[data_type],  # type: ignore[valid-type]
        )

    @property
    def strategy_name(self) -> str:
        return "batch"

    @property
    def staging_dir(self) -> Path:
        return self._staging_dir

    def deliver(self, envelope: WranglerEnvelope[DataT]) -> None:
        self._staging_dir.mkdir(parents=True, exist_ok=True)
        stamped = self.stamp_delivery(envelope)

        # Filename encodes delivery time for ordering
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%f")
        target = self._staging_dir / f"envelope_{ts}.json"
        tmp = self._staging_dir / f".tmp_envelope_{ts}.json"

        # Atomic write: write to temp file, then rename
        payload = self._envelope_adapter.dump_json(stamped)
        tmp.write_bytes(payload)
        tmp.rename(target)

    def receive(self) -> WranglerEnvelope[DataT] | None:
        if not self._staging_dir.exists():
            return None

        # Find the oldest envelope file
        files = sorted(self._staging_dir.glob("envelope_*.json"))
        if not files:
            return None

        oldest = files[0]
        raw = oldest.read_bytes()
        envelope = self._envelope_adapter.validate_json(raw)
        oldest.unlink()
        return envelope


class QueuedWrangler(WranglerBase[DataT], Generic[DataT]):
    """In-process queue wrangler using collections.deque.

    Collector and recorder are decoupled in time but run in the
    same process. The deque is unbounded by default — set maxlen
    if backpressure is needed.

    Thread-safe for single-producer/single-consumer via deque's
    atomic append/popleft. For multi-producer or multi-consumer,
    use external synchronization.
    """

    def __init__(self, maxlen: int | None = None) -> None:
        self._queue: deque[WranglerEnvelope[DataT]] = deque(maxlen=maxlen)

    @property
    def strategy_name(self) -> str:
        return "queued"

    def deliver(self, envelope: WranglerEnvelope[DataT]) -> None:
        stamped = self.stamp_delivery(envelope)
        self._queue.append(stamped)

    def receive(self) -> WranglerEnvelope[DataT] | None:
        try:
            return self._queue.popleft()
        except IndexError:
            return None

    @property
    def pending_count(self) -> int:
        """Number of envelopes waiting to be received."""
        return len(self._queue)
