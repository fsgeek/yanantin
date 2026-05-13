"""Activity-stream capture for the memory-tool harness.

Schema-open, append-only, no-truncation. Every tool call (and later,
every model call) produces one CaptureRecord written as a JSONL line.
Schema-open via `extra="allow"`: collectors attach fields without
coordinating with consumers. No truncation: full request, full response,
full error payload — storage is not the constraint, signal is.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class CaptureRecord(BaseModel):
    """One captured call. Built complete; never mutated.

    `response_parsed` / `response_raw_body` are None on error.
    `error_*` are None on success. `status` discriminates.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    record_id: str
    timestamp: datetime
    experiment_id: str
    panel_id: str
    tool_variant_id: str
    model_id: str
    prompt_template_id: str
    prompt_full: str
    request_full: dict[str, Any]
    response_parsed: dict[str, Any] | None
    response_raw_body: str | None
    usage: dict[str, Any]
    elapsed_seconds: float
    status: Literal["ok", "error"]
    error_type: str | None = None
    error_message: str | None = None
    error_payload: str | None = None


class CaptureWriter:
    """Append-only JSONL writer for CaptureRecords.

    One file per run. Flushes on every write so a crashed run still
    leaves a complete record of everything captured before the crash.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8")

    def write(self, record: CaptureRecord) -> None:
        self._fh.write(json.dumps(record.model_dump(mode="json")) + "\n")
        self._fh.flush()

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    def __enter__(self) -> "CaptureWriter":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def load_run(path: Path) -> list[CaptureRecord]:
    """Load all CaptureRecords from a run's JSONL file, in file order.

    Blank lines are skipped. A malformed line raises ValueError naming
    the 1-based line number.
    """
    records: list[CaptureRecord] = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(CaptureRecord.model_validate(json.loads(stripped)))
            except Exception as exc:  # noqa: BLE001 — re-raised with context
                raise ValueError(f"capture file {path} line {lineno}: {exc}") from exc
    return records
