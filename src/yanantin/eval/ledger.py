# Copied unchanged from levadura_salvaje (src/levadura_salvaje/ledger.py @ d4ae388).
"""Append-only observation ledger.

Measurements live here; interpretations elsewhere cite them by id. Two
times are kept apart on purpose: ``observed_at`` is when the quantity held
the value, ``recorded_at`` is when it was computed. Without the first, a
system that changes is indistinguishable from a memory that drifts.

Each line carries the sha256 of the line before it, so an edited or deleted
entry is detectable from the file alone -- except the newest line, which
nothing follows yet; it is protected only by the OTS-stamped commit.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

LEDGER = Path("ledger/observations.jsonl")
REQUIRED = ("observed_at", "instrument", "population", "quantity", "value")
ASSIGNED = ("id", "recorded_at", "prev")


class LedgerError(Exception):
    pass


def _digest(line: str) -> str:
    return hashlib.sha256(line.encode()).hexdigest()


def _lines(path: Path) -> list[str]:
    return path.read_text().splitlines() if path.exists() else []


def append(entry: dict, path: Path = LEDGER) -> dict:
    missing = [k for k in REQUIRED if k not in entry]
    if missing:
        raise LedgerError(f"missing required fields: {missing}")
    supplied = [k for k in ASSIGNED if k in entry]
    if supplied:
        raise LedgerError(f"fields assigned by the ledger, not the caller: {supplied}")

    path = Path(path)
    lines = _lines(path)
    record = {
        **entry,
        "id": f"obs-{len(lines) + 1:04d}",
        "recorded_at": datetime.now(UTC).isoformat(),
        "prev": _digest(lines[-1]) if lines else None,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
    return record


def verify(path: Path = LEDGER) -> int:
    """Check ids are sequential and the hash chain is intact; return the count."""
    prev = None
    lines = _lines(Path(path))
    for n, line in enumerate(lines, 1):
        record = json.loads(line)
        if record.get("id") != f"obs-{n:04d}":
            raise LedgerError(f"line {n}: expected obs-{n:04d}, found {record.get('id')}")
        if record.get("prev") != prev:
            raise LedgerError(f"line {n}: chain broken (prev does not match line {n - 1})")
        prev = _digest(line)
    return len(lines)
