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

from arango.database import StandardDatabase

from yanantin.infra.config import get_database
from yanantin.activity.models import FactRecord, MemoryAnchor
from yanantin.activity.store import ActivityStreamStore
from yanantin.apacheta.interface.errors import ImmutabilityError, NotFoundError
from yanantin.apacheta.storage_obfuscator import StorageObfuscator, TransparentObfuscator


_SEMANTIC_COLLECTIONS = ("activity_facts", "activity_anchors")


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
        obfuscator: StorageObfuscator | None = None,
    ) -> None:
        self._lock = threading.RLock()
        # Transparent only as an explicit, greppable fallback — never via a
        # silent `or` default (see tests/red_bar/test_obfuscator_default_is_explicit).
        if obfuscator is None:
            obfuscator = TransparentObfuscator()
        self._map = obfuscator
        self._host = host
        self._db_name = db_name
        self._db = self._connect_database(username, password)
        self._ensure_collections()

    def _connect_database(self, username: str, password: str) -> StandardDatabase:
        """Connect to the target database via the shared singleton. Fail-stop
        if it doesn't exist.

        NOTE: the failure-discrimination here is the OLD blanket wrapper; the
        three-way discrimination (auth/unreachable/not-provisioned) is tracked
        as a single fix for both backends — see
        docs/plans/2026-06-01-arango-conn-error-discrimination-is-wrong.md.
        This retrofit changes only WHERE the client comes from.
        """
        try:
            db = get_database(
                host=self._host,
                db_name=self._db_name,
                username=username,
                password=password,
            )
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
        for name in _SEMANTIC_COLLECTIONS:
            mapped = self._map.collection_name(name)
            if not self._db.has_collection(mapped):
                self._db.create_collection(mapped)

        # Persistent sorted index for temporal queries on facts
        facts_col = self._db.collection(self._map.collection_name("activity_facts"))
        facts_col.add_index(
            {
                "type": "persistent",
                "fields": [
                    self._map.field_name("provider_id"),
                    self._map.field_name("timestamp"),
                ],
                "sparse": False,
            },
        )

        # Persistent sorted index for temporal anchor queries
        anchors_col = self._db.collection(self._map.collection_name("activity_anchors"))
        anchors_col.add_index(
            {
                "type": "persistent",
                "fields": [self._map.field_name("timestamp")],
                "sparse": False,
            },
        )

    def close(self) -> None:
        """No-op: the ArangoDB client is owned by the get_database singleton and
        shared across consumers. See ArangoDBBackend.close() in apacheta.
        """

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # -- Fact operations -----------------------------------------------

    def store_fact(self, fact: FactRecord) -> None:
        with self._lock:
            col = self._db.collection(self._map.collection_name("activity_facts"))
            key = str(fact.id)
            if col.has(key):
                raise ImmutabilityError(
                    f"Fact {fact.id} already exists. "
                    "Facts are immutable — append, don't overwrite."
                )
            doc = fact.model_dump(mode="json")
            # Build mapped document: _key + mapped field names
            mapped_doc = {"_key": key}
            for k, v in doc.items():
                if k == "id":
                    continue  # moved to _key
                elif k == "provider_id":
                    mapped_doc[self._map.field_name(k)] = str(v)
                elif k == "timestamp":
                    mapped_doc[self._map.field_name(k)] = fact.timestamp.isoformat()
                else:
                    mapped_doc[self._map.field_name(k)] = v
            col.insert(mapped_doc)

    def get_fact(self, fact_id: UUID) -> FactRecord:
        with self._lock:
            col = self._db.collection(self._map.collection_name("activity_facts"))
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
            col = self._map.collection_name("activity_facts")
            f_pid = self._map.field_name("provider_id")
            f_ts = self._map.field_name("timestamp")
            if before is not None:
                cursor = self._db.aql.execute(
                    f"FOR doc IN {col} "
                    f"  FILTER doc.{f_pid} == @provider_id "
                    f"  FILTER doc.{f_ts} <= @before "
                    f"  SORT doc.{f_ts} DESC "
                    f"  LIMIT 1 "
                    f"  RETURN doc",
                    bind_vars={
                        "provider_id": str(provider_id),
                        "before": before.isoformat(),
                    },
                )
            else:
                cursor = self._db.aql.execute(
                    f"FOR doc IN {col} "
                    f"  FILTER doc.{f_pid} == @provider_id "
                    f"  SORT doc.{f_ts} DESC "
                    f"  LIMIT 1 "
                    f"  RETURN doc",
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
            col = self._map.collection_name("activity_facts")
            f_pid = self._map.field_name("provider_id")
            f_ts = self._map.field_name("timestamp")

            filters = [f"doc.{f_pid} == @provider_id"]
            bind_vars: dict = {"provider_id": str(provider_id)}

            if start is not None:
                filters.append(f"doc.{f_ts} >= @start")
                bind_vars["start"] = start.isoformat()
            if end is not None:
                filters.append(f"doc.{f_ts} <= @end")
                bind_vars["end"] = end.isoformat()

            filter_clause = " FILTER ".join([""] + filters)
            cursor = self._db.aql.execute(
                f"FOR doc IN {col}"
                f"  {filter_clause}"
                f"  SORT doc.{f_ts} ASC"
                f"  RETURN doc",
                bind_vars=bind_vars,
            )
            return [self._doc_to_fact(doc) for doc in cursor]

    # -- Anchor operations ---------------------------------------------

    def store_anchor(self, anchor: MemoryAnchor) -> None:
        with self._lock:
            col = self._db.collection(self._map.collection_name("activity_anchors"))
            key = str(anchor.handle)
            if col.has(key):
                raise ImmutabilityError(
                    f"Anchor {anchor.handle} already exists. "
                    "Anchors are immutable — advance, don't overwrite."
                )
            doc = anchor.model_dump(mode="json")
            # Build mapped document
            mapped_doc = {"_key": key}
            for k, v in doc.items():
                if k == "handle":
                    continue  # moved to _key
                elif k == "timestamp":
                    mapped_doc[self._map.field_name(k)] = anchor.timestamp.isoformat()
                elif k == "cursors":
                    # Cursors contain model fields --- obfuscate nested dicts
                    mapped_doc[self._map.field_name(k)] = [
                        self._map.obfuscate_document(c) if isinstance(c, dict) else c
                        for c in v
                    ]
                else:
                    mapped_doc[self._map.field_name(k)] = v
            col.insert(mapped_doc)

    def get_anchor(self, handle: UUID) -> MemoryAnchor:
        with self._lock:
            col = self._db.collection(self._map.collection_name("activity_anchors"))
            doc = col.get(str(handle))
            if doc is None:
                raise NotFoundError(f"Anchor {handle} not found.")
            return self._doc_to_anchor(doc)

    def get_latest_anchor(self) -> MemoryAnchor | None:
        with self._lock:
            col = self._map.collection_name("activity_anchors")
            f_ts = self._map.field_name("timestamp")
            cursor = self._db.aql.execute(
                f"FOR doc IN {col} "
                f"  SORT doc.{f_ts} DESC "
                f"  LIMIT 1 "
                f"  RETURN doc"
            )
            docs = list(cursor)
            if not docs:
                return None
            return self._doc_to_anchor(docs[0])

    # -- Discovery -----------------------------------------------------

    def list_providers(self) -> list[UUID]:
        with self._lock:
            col = self._map.collection_name("activity_facts")
            f_pid = self._map.field_name("provider_id")
            cursor = self._db.aql.execute(
                f"FOR doc IN {col} "
                f"  COLLECT provider = doc.{f_pid} "
                f"  RETURN provider"
            )
            return [UUID(p) for p in cursor]

    def count_facts(self, provider_id: UUID | None = None) -> int:
        with self._lock:
            # Regime-1 form (AQL field-mapping guardrail §6): collection via @@col
            # bind; field via field_path (the sanctioned primitive) as a LITERAL
            # dotted path — NOT doc[@f] dynamic access, because activity_facts has
            # a persistent index on (provider_id, timestamp) that dynamic access
            # would defeat (§6.1 decision, verified against the live index).
            col = self._map.collection_name("activity_facts")
            if provider_id is not None:
                pid_path = self._map.field_path(("provider_id",))
                cursor = self._db.aql.execute(
                    "RETURN LENGTH("
                    "  FOR doc IN @@col "
                    f"    FILTER doc.{pid_path} == @provider_id "
                    "    RETURN 1"
                    ")",
                    bind_vars={"@col": col, "provider_id": str(provider_id)},
                )
            else:
                cursor = self._db.aql.execute(
                    "RETURN LENGTH(@@col)",
                    bind_vars={"@col": col},
                )
            results = list(cursor)
            return results[0] if results else 0

    # -- Internal helpers ──────────────────────────────────────────────

    def _doc_to_fact(self, doc: dict) -> FactRecord:
        """Convert an ArangoDB document to a FactRecord."""
        # Reverse-map field names, then strip ArangoDB metadata
        deobfuscated = self._map.deobfuscate_document(doc)
        data = {k: v for k, v in deobfuscated.items() if not k.startswith("_")}
        data["id"] = doc["_key"]
        return FactRecord.model_validate(data)

    def _doc_to_anchor(self, doc: dict) -> MemoryAnchor:
        """Convert an ArangoDB document to a MemoryAnchor."""
        deobfuscated = self._map.deobfuscate_document(doc)
        data = {k: v for k, v in deobfuscated.items() if not k.startswith("_")}
        data["handle"] = doc["_key"]
        return MemoryAnchor.model_validate(data)
