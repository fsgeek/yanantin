"""Incremental filesystem change collector.

Detects file changes by comparing mtime against the previous collection
run. Ported from Indaleko's FsIncrementalCollector (90 lines, pure stdlib)
with additions: typed Pydantic models, deletion detection, atomic state
file writes.

State file format is JSON: maps file_path → {mtime, size}.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_DNS, UUID, uuid5

from yanantin.collector._collector_base import CollectorBase
from yanantin.collector.activity.linux.models import FsChangeEvent, FsEventBatch
from yanantin.machine.base import _get_machine_id

logger = logging.getLogger(__name__)


class FsIncrementalCollector(CollectorBase[FsEventBatch]):
    """Detects filesystem changes via mtime comparison between runs.

    Walks the configured volumes and compares each file's mtime against
    the stored state from the previous run. Files with newer mtimes are
    reported as modifications, new files as creations, and missing files
    as deletions.

    State is persisted atomically (write-to-temp + rename) to prevent
    corruption on crash.
    """

    def __init__(
        self,
        volumes: list[str],
        state_file: Path,
    ) -> None:
        self._volumes = [str(Path(v).resolve()) for v in volumes]
        self._state_file = state_file.resolve()
        self._provider_id = uuid5(
            NAMESPACE_DNS,
            f"yanantin.collector.fs_events.{_get_machine_id()}",
        )

    def _load_state(self) -> tuple[dict[str, dict], datetime | None]:
        """Load previous scan state from the state file."""
        if not self._state_file.exists():
            return {}, None

        try:
            raw = json.loads(self._state_file.read_text())
            files = raw.get("files", {})
            last_run_str = raw.get("last_run")
            last_run = (
                datetime.fromisoformat(last_run_str)
                if last_run_str
                else None
            )
            return files, last_run
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.warning("Corrupt state file %s: %s", self._state_file, exc)
            return {}, None

    def _save_state(
        self, files: dict[str, dict], run_time: datetime,
    ) -> None:
        """Atomically save scan state to the state file."""
        state = {
            "last_run": run_time.isoformat(),
            "files": files,
        }
        self._state_file.parent.mkdir(parents=True, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._state_file.parent),
            prefix=".fs_events_state_",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state, f)
            os.rename(tmp_path, str(self._state_file))
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _scan_volumes(self) -> dict[str, dict]:
        """Walk all volumes and build a map of file_path → {mtime, size}."""
        current: dict[str, dict] = {}
        for volume in self._volumes:
            for dirpath, _dirnames, filenames in os.walk(volume):
                for filename in filenames:
                    full_path = os.path.join(dirpath, filename)
                    try:
                        st = os.lstat(full_path)
                        current[full_path] = {
                            "mtime": st.st_mtime,
                            "size": st.st_size,
                        }
                    except OSError:
                        continue
        return current

    def collect(self, since: datetime | None = None) -> FsEventBatch:
        """Scan volumes and detect changes since the last run."""
        previous_files, last_run = self._load_state()
        if since is not None:
            last_run = max(since, last_run) if last_run else since
        current_run = datetime.now(timezone.utc)
        current_files = self._scan_volumes()

        events: list[FsChangeEvent] = []
        now = datetime.now(timezone.utc)

        for path, info in current_files.items():
            mtime_dt = datetime.fromtimestamp(info["mtime"], tz=timezone.utc)
            if path not in previous_files:
                events.append(FsChangeEvent(
                    file_path=path,
                    event_type="created",
                    modified_time=mtime_dt,
                    size_bytes=info["size"],
                    detected_at=now,
                ))
            elif info["mtime"] != previous_files[path]["mtime"]:
                events.append(FsChangeEvent(
                    file_path=path,
                    event_type="modified",
                    modified_time=mtime_dt,
                    size_bytes=info["size"],
                    detected_at=now,
                ))

        for path in previous_files:
            if path not in current_files:
                prev_mtime = datetime.fromtimestamp(
                    previous_files[path]["mtime"], tz=timezone.utc,
                )
                events.append(FsChangeEvent(
                    file_path=path,
                    event_type="deleted",
                    modified_time=prev_mtime,
                    size_bytes=previous_files[path]["size"],
                    detected_at=now,
                ))

        self._save_state(current_files, current_run)

        return FsEventBatch(
            volumes=tuple(self._volumes),
            events=tuple(events),
            last_run=last_run,
            current_run=current_run,
        )

    def get_provider_id(self) -> UUID:
        return self._provider_id

    def get_description(self) -> str:
        return (
            f"Incremental filesystem event collector "
            f"— monitors {len(self._volumes)} volume(s) for changes"
        )
