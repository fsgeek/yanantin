"""DuckDB backend for the activity stream store.

SQL-based persistent storage with query pushdown for temporal queries.
Unlike Apacheta's DuckDB backend (which loads all records then filters
in Python), this backend pushes temporal queries down to SQL. At 28.5M
facts, load-all-then-filter is not viable.

Design:
- Two tables: facts and anchors
- Timestamps stored as VARCHAR (ISO 8601) — sorts correctly, no pytz dependency
- Composite index on (provider_id, timestamp) for O(log n) temporal queries
- Thread safety via RLock
- File-backed by default, :memory: for tests
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import duckdb

from yanantin.activity.models import FactRecord, MemoryAnchor
from yanantin.activity.store import ActivityStreamStore
from yanantin.apacheta.interface.errors import ImmutabilityError, NotFoundError


class DuckDBActivityStreamStore(ActivityStreamStore):
    """DuckDB implementation of ActivityStreamStore.

    Thread-safe via RLock. Enforces immutability. Pushes temporal
    queries to SQL for O(log n) performance via indexed queries.
    Timestamps are stored as ISO 8601 VARCHAR for portability.

    DuckDB is local storage on a trusted device. No obfuscation
    needed — the trust boundary is at Pukara, not the local disk.
    """

    def __init__(
        self,
        db_path: str | Path = ":memory:",
    ) -> None:
        self._lock = threading.RLock()
        self._db_path = str(db_path)
        self._conn = duckdb.connect(self._db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables and indexes with semantic names."""
        ddl = (
            "CREATE TABLE IF NOT EXISTS facts ("
            "  id VARCHAR PRIMARY KEY,"
            "  provider_id VARCHAR NOT NULL,"
            "  timestamp VARCHAR NOT NULL,"
            "  data JSON NOT NULL,"
            "  content_hash VARCHAR NOT NULL DEFAULT ''"
            ");"
            "CREATE INDEX IF NOT EXISTS idx_facts_provider_id_timestamp "
            "  ON facts (provider_id, timestamp);"
            "CREATE TABLE IF NOT EXISTS anchors ("
            "  handle VARCHAR PRIMARY KEY,"
            "  timestamp VARCHAR NOT NULL,"
            "  data JSON NOT NULL"
            ");"
            "CREATE INDEX IF NOT EXISTS idx_anchors_timestamp "
            "  ON anchors (timestamp);"
        )
        self._conn.execute(ddl)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # -- Fact operations -----------------------------------------------

    def store_fact(self, fact: FactRecord) -> None:
        with self._lock:
            if self._exists("facts", "id", fact.id):
                raise ImmutabilityError(
                    f"Fact {fact.id} already exists. "
                    "Facts are immutable — append, don't overwrite."
                )
            data_json = json.dumps(fact.data)
            self._conn.execute(
                "INSERT INTO facts (id, provider_id, timestamp, data, content_hash) "  # noqa: S608
                "VALUES (?, ?, ?, ?, ?)",
                [
                    str(fact.id),
                    str(fact.provider_id),
                    fact.timestamp.isoformat(),
                    data_json,
                    fact.content_hash,
                ],
            )

    def get_fact(self, fact_id: UUID) -> FactRecord:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, provider_id, timestamp, data, content_hash "  # noqa: S608
                "FROM facts WHERE id = ?",
                [str(fact_id)],
            ).fetchone()
            if row is None:
                raise NotFoundError(f"Fact {fact_id} not found.")
            return self._row_to_fact(row)

    def query_latest(
        self,
        provider_id: UUID,
        before: datetime | None = None,
    ) -> FactRecord | None:
        with self._lock:
            select = "SELECT id, provider_id, timestamp, data, content_hash FROM facts"
            if before is not None:
                row = self._conn.execute(
                    f"{select} "  # noqa: S608
                    "WHERE provider_id = ? AND timestamp <= ? "
                    "ORDER BY timestamp DESC LIMIT 1",
                    [str(provider_id), before.isoformat()],
                ).fetchone()
            else:
                row = self._conn.execute(
                    f"{select} "  # noqa: S608
                    "WHERE provider_id = ? "
                    "ORDER BY timestamp DESC LIMIT 1",
                    [str(provider_id)],
                ).fetchone()
            if row is None:
                return None
            return self._row_to_fact(row)

    def query_range(
        self,
        provider_id: UUID,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[FactRecord]:
        with self._lock:
            conditions = ["provider_id = ?"]
            params: list = [str(provider_id)]

            if start is not None:
                conditions.append("timestamp >= ?")
                params.append(start.isoformat())
            if end is not None:
                conditions.append("timestamp <= ?")
                params.append(end.isoformat())

            where = " AND ".join(conditions)
            rows = self._conn.execute(
                "SELECT id, provider_id, timestamp, data, content_hash "  # noqa: S608
                f"FROM facts WHERE {where} ORDER BY timestamp ASC",
                params,
            ).fetchall()
            return [self._row_to_fact(row) for row in rows]

    # -- Anchor operations ---------------------------------------------

    def store_anchor(self, anchor: MemoryAnchor) -> None:
        with self._lock:
            if self._exists("anchors", "handle", anchor.handle):
                raise ImmutabilityError(
                    f"Anchor {anchor.handle} already exists. "
                    "Anchors are immutable — advance, don't overwrite."
                )
            doc = anchor.model_dump(mode="json")
            data_json = json.dumps(doc)
            self._conn.execute(
                "INSERT INTO anchors (handle, timestamp, data) VALUES (?, ?, ?)",  # noqa: S608
                [str(anchor.handle), anchor.timestamp.isoformat(), data_json],
            )

    def get_anchor(self, handle: UUID) -> MemoryAnchor:
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM anchors WHERE handle = ?",  # noqa: S608
                [str(handle)],
            ).fetchone()
            if row is None:
                raise NotFoundError(f"Anchor {handle} not found.")
            return self._deserialize_anchor(row[0])

    def get_latest_anchor(self) -> MemoryAnchor | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM anchors ORDER BY timestamp DESC LIMIT 1",  # noqa: S608
            ).fetchone()
            if row is None:
                return None
            return self._deserialize_anchor(row[0])

    # -- Discovery -----------------------------------------------------

    def list_providers(self) -> list[UUID]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT provider_id FROM facts",  # noqa: S608
            ).fetchall()
            return [UUID(row[0]) for row in rows]

    def count_facts(self, provider_id: UUID | None = None) -> int:
        with self._lock:
            if provider_id is not None:
                row = self._conn.execute(
                    "SELECT COUNT(*) FROM facts WHERE provider_id = ?",  # noqa: S608
                    [str(provider_id)],
                ).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT COUNT(*) FROM facts",  # noqa: S608
                ).fetchone()
            return row[0] if row else 0

    # -- Internal helpers ──────────────────────────────────────────────

    def _exists(self, table: str, key_col: str, key_val: UUID) -> bool:
        """Check if a record exists."""
        row = self._conn.execute(
            f"SELECT 1 FROM {table} WHERE {key_col} = ?",  # noqa: S608
            [str(key_val)],
        ).fetchone()
        return row is not None

    @staticmethod
    def _row_to_fact(row) -> FactRecord:
        """Convert a DuckDB row to a FactRecord."""
        fact_id, provider_id, timestamp_str, data, content_hash = row
        # DuckDB may return data as str or dict depending on version
        if isinstance(data, str):
            data = json.loads(data)
        # Parse ISO 8601 timestamp back to datetime
        timestamp = datetime.fromisoformat(timestamp_str)
        return FactRecord(
            id=UUID(fact_id),
            provider_id=UUID(provider_id),
            timestamp=timestamp,
            data=data,
            content_hash=content_hash,
        )

    def _deserialize_anchor(self, data) -> MemoryAnchor:
        """Convert stored JSON to MemoryAnchor."""
        if isinstance(data, str):
            parsed = json.loads(data)
        else:
            parsed = data
        return MemoryAnchor.model_validate(parsed)
