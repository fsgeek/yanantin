"""ArangoDB backend for the activity stream store.

Document-based persistent storage with index-driven temporal queries.
Uses AQL for query pushdown — the composite persistent index on
(provider_id, timestamp) makes temporal queries O(log n).

Design:
- Two collections: activity_facts and activity_anchors
- Persistent sorted index on activity_facts (provider_id, timestamp)
- Persistent sorted index on activity_anchors (timestamp)
- Thread safety via RLock
- Least-privilege: separate user with rw on these collections only
"""

from __future__ import annotations

import threading
from uuid import UUID
from datetime import datetime

from arango import ArangoClient
from arango.database import StandardDatabase

from yanantin.activity.models import FactRecord, MemoryAnchor
from yanantin.activity.store import ActivityStreamStore
from yanantin.apacheta.interface.errors import ImmutabilityError, NotFoundError


_COLLECTIONS = ("activity_facts", "activity_anchors")


class ArangoDBActivityStreamStore(ActivityStreamStore):
    """ArangoDB implementation of ActivityStreamStore.

    Thread-safe via RLock. Enforces immutability. Uses AQL with
    persistent sorted indexes for O(log n) temporal queries.
    """

    def __init__(
        self,
        host: str = "http://localhost:8529",
        db_name: str = "apacheta",
        username: str = "",
        password: str = "",
    ) -> None:
        self._lock = threading.RLock()
        self._client = ArangoClient(hosts=host)
        self._host = host
        self._db_name = db_name
        self._db = self._connect_database(username, password)
        self._ensure_collections()

    def _connect_database(self, username: str, password: str) -> StandardDatabase:
        """Connect to the target database. Fail-stop if it doesn't exist."""
        try:
            db = self._client.db(self._db_name, username=username, password=password)
            db.collections()
            return db
        except Exception as e:
            raise ConnectionError(
                f"Cannot connect to ArangoDB database '{self._db_name}' at {self._host}. "
                f"Database must be provisioned by an admin before the application can use it. "
                f"Error: {e}"
            ) from e

    def _ensure_collections(self) -> None:
        """Create collections and indexes if they don't exist."""
        for name in _COLLECTIONS:
            if not self._db.has_collection(name):
                self._db.create_collection(name)

        # Persistent sorted index for temporal queries on facts
        facts_col = self._db.collection("activity_facts")
        facts_col.add_index(
            {"type": "persistent", "fields": ["provider_id", "timestamp"], "sparse": False},
        )

        # Persistent sorted index for temporal anchor queries
        anchors_col = self._db.collection("activity_anchors")
        anchors_col.add_index(
            {"type": "persistent", "fields": ["timestamp"], "sparse": False},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # -- Fact operations -----------------------------------------------

    def store_fact(self, fact: FactRecord) -> None:
        with self._lock:
            col = self._db.collection("activity_facts")
            key = str(fact.id)
            if col.has(key):
                raise ImmutabilityError(
                    f"Fact {fact.id} already exists. "
                    "Facts are immutable — append, don't overwrite."
                )
            doc = fact.model_dump(mode="json")
            doc["_key"] = key
            doc.pop("id", None)
            # Store provider_id and timestamp as top-level fields for indexing
            doc["provider_id"] = str(fact.provider_id)
            doc["timestamp"] = fact.timestamp.isoformat()
            col.insert(doc)

    def get_fact(self, fact_id: UUID) -> FactRecord:
        with self._lock:
            col = self._db.collection("activity_facts")
            doc = col.get(str(fact_id))
            if doc is None:
                raise NotFoundError(f"Fact {fact_id} not found.")
            return self._doc_to_fact(doc)

    def query_latest(
        self,
        provider_id: UUID,
        before: datetime | None = None,
    ) -> FactRecord | None:
        with self._lock:
            if before is not None:
                cursor = self._db.aql.execute(
                    "FOR doc IN activity_facts "
                    "  FILTER doc.provider_id == @provider_id "
                    "  FILTER doc.timestamp <= @before "
                    "  SORT doc.timestamp DESC "
                    "  LIMIT 1 "
                    "  RETURN doc",
                    bind_vars={
                        "provider_id": str(provider_id),
                        "before": before.isoformat(),
                    },
                )
            else:
                cursor = self._db.aql.execute(
                    "FOR doc IN activity_facts "
                    "  FILTER doc.provider_id == @provider_id "
                    "  SORT doc.timestamp DESC "
                    "  LIMIT 1 "
                    "  RETURN doc",
                    bind_vars={"provider_id": str(provider_id)},
                )
            docs = list(cursor)
            if not docs:
                return None
            return self._doc_to_fact(docs[0])

    def query_range(
        self,
        provider_id: UUID,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[FactRecord]:
        with self._lock:
            filters = ["doc.provider_id == @provider_id"]
            bind_vars: dict = {"provider_id": str(provider_id)}

            if start is not None:
                filters.append("doc.timestamp >= @start")
                bind_vars["start"] = start.isoformat()
            if end is not None:
                filters.append("doc.timestamp <= @end")
                bind_vars["end"] = end.isoformat()

            filter_clause = " FILTER ".join([""] + filters)
            cursor = self._db.aql.execute(
                f"FOR doc IN activity_facts"
                f"  {filter_clause}"
                f"  SORT doc.timestamp ASC"
                f"  RETURN doc",
                bind_vars=bind_vars,
            )
            return [self._doc_to_fact(doc) for doc in cursor]

    # -- Anchor operations ---------------------------------------------

    def store_anchor(self, anchor: MemoryAnchor) -> None:
        with self._lock:
            col = self._db.collection("activity_anchors")
            key = str(anchor.handle)
            if col.has(key):
                raise ImmutabilityError(
                    f"Anchor {anchor.handle} already exists. "
                    "Anchors are immutable — advance, don't overwrite."
                )
            doc = anchor.model_dump(mode="json")
            doc["_key"] = key
            doc.pop("handle", None)
            doc["timestamp"] = anchor.timestamp.isoformat()
            col.insert(doc)

    def get_anchor(self, handle: UUID) -> MemoryAnchor:
        with self._lock:
            col = self._db.collection("activity_anchors")
            doc = col.get(str(handle))
            if doc is None:
                raise NotFoundError(f"Anchor {handle} not found.")
            return self._doc_to_anchor(doc)

    def get_latest_anchor(self) -> MemoryAnchor | None:
        with self._lock:
            cursor = self._db.aql.execute(
                "FOR doc IN activity_anchors "
                "  SORT doc.timestamp DESC "
                "  LIMIT 1 "
                "  RETURN doc"
            )
            docs = list(cursor)
            if not docs:
                return None
            return self._doc_to_anchor(docs[0])

    # -- Discovery -----------------------------------------------------

    def list_providers(self) -> list[UUID]:
        with self._lock:
            cursor = self._db.aql.execute(
                "FOR doc IN activity_facts "
                "  COLLECT provider = doc.provider_id "
                "  RETURN provider"
            )
            return [UUID(p) for p in cursor]

    def count_facts(self, provider_id: UUID | None = None) -> int:
        with self._lock:
            if provider_id is not None:
                cursor = self._db.aql.execute(
                    "RETURN LENGTH("
                    "  FOR doc IN activity_facts "
                    "    FILTER doc.provider_id == @provider_id "
                    "    RETURN 1"
                    ")",
                    bind_vars={"provider_id": str(provider_id)},
                )
            else:
                cursor = self._db.aql.execute(
                    "RETURN LENGTH(activity_facts)"
                )
            results = list(cursor)
            return results[0] if results else 0

    # -- Internal helpers ──────────────────────────────────────────────

    @staticmethod
    def _doc_to_fact(doc: dict) -> FactRecord:
        """Convert an ArangoDB document to a FactRecord."""
        data = {k: v for k, v in doc.items() if not k.startswith("_")}
        data["id"] = doc["_key"]
        return FactRecord.model_validate(data)

    @staticmethod
    def _doc_to_anchor(doc: dict) -> MemoryAnchor:
        """Convert an ArangoDB document to a MemoryAnchor."""
        data = {k: v for k, v in doc.items() if not k.startswith("_")}
        data["handle"] = doc["_key"]
        return MemoryAnchor.model_validate(data)
