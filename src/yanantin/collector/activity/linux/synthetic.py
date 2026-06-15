"""Synthetic filesystem event generator.

Produces FsEventBatch instances with realistic event sequences: creates
precede modifications (not the reverse), temporal ordering within batches,
plausible file paths with common extensions.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from yanantin.collector._synthetic_base import SyntheticCollectorBase
from yanantin.collector.activity.linux.models import FsChangeEvent, FsEventBatch

_EVENT_TYPES = ("created", "modified", "deleted")
_DEFAULT_WEIGHTS = (0.4, 0.45, 0.15)  # more creates/modifies than deletes

_EXTENSIONS = (
    ".py", ".txt", ".json", ".md", ".log", ".csv", ".pdf",
    ".html", ".js", ".yaml", ".toml",
)

_DIR_PARTS = (
    "home", "user", "projects", "data", "documents",
    "src", "tests", "config", "tmp", "output",
)


class SyntheticFsEventCollector(SyntheticCollectorBase[FsEventBatch]):
    """Generates realistic filesystem event batches.

    Events within a batch are temporally ordered. Creates are guaranteed
    to precede modifications for the same path — a file can't be modified
    before it exists.
    """

    def __init__(
        self,
        seed: int | None = None,
        events_per_batch: int = 20,
        event_type_weights: tuple[float, ...] = _DEFAULT_WEIGHTS,
    ) -> None:
        super().__init__(seed)
        self._events_per_batch = events_per_batch
        self._weights = event_type_weights
        self._base_time = datetime(2025, 6, 1, tzinfo=timezone.utc)

    def _random_path(self) -> str:
        """Generate a plausible file path."""
        depth = self._rng.randint(2, 4)
        parts = [self._rng.choice(_DIR_PARTS) for _ in range(depth)]
        name = f"file_{self._rng.randint(0, 999)}{self._rng.choice(_EXTENSIONS)}"
        return "/" + "/".join(parts) + "/" + name

    def generate(self) -> FsEventBatch:
        """Generate a batch of synthetic filesystem events."""
        last_run = self._base_time + timedelta(
            hours=self._rng.randint(0, 720),
        )
        current_run = last_run + timedelta(
            minutes=self._rng.randint(5, 120),
        )

        created_paths: set[str] = set()
        events: list[FsChangeEvent] = []
        event_time = last_run

        for _ in range(self._events_per_batch):
            event_time = event_time + timedelta(
                seconds=self._rng.uniform(0.1, 60.0),
            )
            if event_time > current_run:
                event_time = current_run

            event_type = self._rng.choices(
                _EVENT_TYPES, weights=self._weights, k=1,
            )[0]
            path = self._random_path()

            if event_type in ("modified", "deleted") and path not in created_paths:
                event_type = "created"

            if event_type == "created":
                created_paths.add(path)
            elif event_type == "deleted":
                created_paths.discard(path)

            events.append(FsChangeEvent(
                file_path=path,
                event_type=event_type,
                modified_time=event_time,
                size_bytes=self._rng.randint(0, 10_000_000),
                detected_at=event_time,
            ))

        volumes = tuple(sorted({
            "/" + e.file_path.split("/")[1]
            for e in events
            if e.file_path.startswith("/")
        }))

        return FsEventBatch(
            volumes=volumes,
            events=tuple(events),
            last_run=last_run,
            current_run=current_run,
            collected_at=current_run,
        )

    def get_description(self) -> str:
        return (
            f"Synthetic filesystem event collector "
            f"— generates {self._events_per_batch} events per batch"
        )
