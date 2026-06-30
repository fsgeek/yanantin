"""ArangoDB backend for Apacheta.

Document/graph-based persistent storage. The third backend alongside
in-memory and DuckDB. Three architecturally different backends
(dict, SQL, document/graph) keep the interface honest.

ArangoDB is the eventual production target — graph queries for
composition edges, lineage traversal, and the epistemic graph.
For now, same pattern as DuckDB: store full models as documents,
query logic in Python.

Design:
- Each record type → one collection
- Document _key = str(UUID)
- Document body = model.model_dump(mode="json")
- Immutability via check-before-insert
- Thread safety via RLock
- Graph features deferred to when queries demand them
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from uuid import UUID

from arango.database import StandardDatabase
from arango.exceptions import (
    ArangoClientError,
    ArangoServerError,
    DocumentInsertError,
    ServerConnectionError,
)

from yanantin.apacheta.interface.abstract import ApachetaInterface
from yanantin.infra.config import get_database
from yanantin.apacheta.interface.errors import (
    AccessDeniedError,
    BackendAuthError,
    BackendUnreachableError,
    DatabaseNotProvisionedError,
    ImmutabilityError,
    NotFoundError,
)
from yanantin.apacheta.models.base import ApachetaBaseModel
from yanantin.apacheta.models.composition import (
    BootstrapRecord,
    CompositionEdge,
    CorrectionRecord,
    DissentRecord,
    NegationRecord,
    RelationType,
    SchemaEvolutionRecord,
)
from yanantin.apacheta.models import ProvenanceEnvelope
from yanantin.apacheta.models.entities import EntityResolution
from yanantin.apacheta.models.provenance_edge import ProvenanceEdge
from yanantin.apacheta.models.tensor import TensorRecord
from yanantin.apacheta.storage_obfuscator import StorageObfuscator, TransparentObfuscator
from yanantin.llika.models import CompositionEdge as LlikaCompositionEdge
from yanantin.llika.models import EdgeResult, FindHit, FindResult, PathResult, PathStep


# ── Collection names ──────────────────────────────────────────────────
# Semantic names used in application code. The SchemaMap translates
# these to opaque identifiers at the storage boundary.

_SEMANTIC_COLLECTIONS = (
    "tensors",
    "composition_edges",
    "corrections",
    "dissents",
    "negations",
    "bootstraps",
    "evolutions",
    "entities",
    "records",
)

# Llika's native edge collection (semantic name). Mapped through the
# obfuscator like every other collection — under opaque storage the edge
# collection name is opaque too, closing the latent plaintext bypass that
# existed when this AQL lived in LlikaService against a raw handle.
_LLIKA_EDGE_COLLECTION = "llika_composition"

_LLIKA_DIRECTION_AQL = {"forward": "OUTBOUND", "backward": "INBOUND", "both": "ANY"}

# Edge-envelope fields that are framework shape, not content — stripped
# before reporting a vertex's content field NAMES (shape, never values).
_LLIKA_ENVELOPE_FIELDS = frozenset(
    {"_id", "_key", "_rev", "_from", "_to", "provenance", "lineage_tags"}
)

_SEMANTIC_MODEL = {
    "tensors": TensorRecord,
    "composition_edges": CompositionEdge,
    "corrections": CorrectionRecord,
    "dissents": DissentRecord,
    "negations": NegationRecord,
    "bootstraps": BootstrapRecord,
    "evolutions": SchemaEvolutionRecord,
    "entities": EntityResolution,
}


class ArangoDBBackend(ApachetaInterface):
    """ArangoDB implementation of ApachetaInterface.

    Thread-safe via RLock. Enforces immutability: duplicate _key
    on any store raises ImmutabilityError. Persistent to ArangoDB.
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
        self._username = username
        self._password = password
        self._db = self._connect_database()
        self._ensure_collections()

    def _connect_database(self) -> StandardDatabase:
        """Connect to the target database. Fail-stop if it doesn't exist.

        Database creation is an admin operation — done once with root,
        not by the application. The backend connects with least-privilege
        credentials and fails if the database isn't there.
        """
        try:
            db = get_database(
                host=self._host,
                db_name=self._db_name,
                username=self._username,
                password=self._password,
            )
            # Verify the connection works by listing collections
            db.collections()
            return db
        except Exception as e:
            raise self._discriminate_connection_failure(e) from e

    def _discriminate_connection_failure(self, e: Exception) -> ConnectionError:
        """Map a raw connection failure to a specific, remediation-honest error.

        The old blanket wrapper claimed every failure meant "must be
        provisioned by an admin" — true for exactly one of three causes.
        An operator (or a reasoning loop) reading that prefix goes looking
        for admin tooling when the real problem is a typo in the credentials
        or an unreachable host. We branch on the signal python-arango
        actually carries — the HTTP status code, and the transport-failure
        exception types — and say what's really wrong.
        """
        where = f"ArangoDB database '{self._db_name}' at {self._host}"

        # Transport-level failure: the host never answered. ServerConnectionError
        # is raised on a failed connect; ArangoClientError covers client-side
        # transport problems. Neither carries a meaningful HTTP status.
        if isinstance(e, (ServerConnectionError, ArangoClientError)):
            return BackendUnreachableError(
                f"Cannot reach {where}. Check the host, port, and network "
                f"(is the server running and listening?). Error: {e}"
            )

        # Server answered with a status code — branch on what it said.
        http_code = getattr(e, "http_code", None)
        if isinstance(e, ArangoServerError):
            if http_code in (401, 403):
                return BackendAuthError(
                    f"Authentication rejected by {where}. Check the credentials "
                    f"and that the user has access to this database — this is not "
                    f"a provisioning problem. Error: {e}"
                )
            if http_code == 404:
                return DatabaseNotProvisionedError(
                    f"Cannot connect to {where}. Database must be provisioned by "
                    f"an admin before the application can use it. Error: {e}"
                )

        # Unrecognized failure: don't pretend to know the cause. Say so.
        return ConnectionError(
            f"Unexpected failure connecting to {where}. Error: {e}"
        )

    def _ensure_collections(self) -> None:
        """Create collections (and supporting indexes) if they don't exist."""
        for name in _SEMANTIC_COLLECTIONS:
            mapped = self._map.collection_name(name)
            if not self._db.has_collection(mapped):
                self._db.create_collection(mapped)
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Create persistent indexes for open-record queries.

        Idempotent: check existing indexes before adding so we tolerate
        both fresh and dirty databases. Only the "records" collection
        gets indexes today; other collections' index needs are tracked
        on a separate track.
        """
        records = self._db.collection(self._map.collection_name("records"))
        author_path = self._map.field_path(("provenance", "author_instance_id"))
        # AQL's per-element array index marker — indexes each element
        # of the array, so `@tag IN doc.lineage_tags` can use the index.
        tags_indexed_field = self._map.field_path(("lineage_tags",)) + "[*]"
        desired: list[list[str]] = [
            [author_path],
            [tags_indexed_field],
        ]
        existing = {
            tuple(idx.get("fields", ()))
            for idx in records.indexes()
            if idx.get("type") == "persistent"
        }
        for fields in desired:
            if tuple(fields) not in existing:
                records.add_persistent_index(fields=fields)

    def close(self) -> None:
        """No-op: the ArangoDB client is owned by the get_database singleton and
        shared across consumers. A single backend must not close the shared
        connection out from under other borrowers; the connection is
        process-lived. Kept for interface/context-manager compatibility.
        """

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ── Internal ──────────────────────────────────────────────────

    def _enforce_access(self, caller: str, operation: str, target=None) -> None:
        if not self.check_access(caller, operation, target):
            raise AccessDeniedError(
                f"Access denied: {caller} cannot {operation}"
                + (f" on {target}" if target else "")
            )

    def _to_doc(self, record) -> dict:
        """Convert a Pydantic model to an ArangoDB document."""
        data = record.model_dump(mode="json")
        # ArangoDB uses _key as the document identifier
        data["_key"] = str(data.pop("id"))
        return self._map.obfuscate_document(data)

    def _from_doc(self, model_cls, doc: dict):
        """Convert an ArangoDB document back to a Pydantic model."""
        deobfuscated = self._map.deobfuscate_document(doc)
        # Restore 'id' from '_key' and strip ArangoDB metadata
        data = {k: v for k, v in deobfuscated.items() if not k.startswith("_")}
        data["id"] = doc["_key"]
        return model_cls.model_validate(data)

    def _store(self, collection_name: str, record_id: UUID, record) -> None:
        """Generic store: check immutability, insert.

        collection_name is semantic --- mapped to opaque via SchemaMap.
        """
        mapped = self._map.collection_name(collection_name)
        collection = self._db.collection(mapped)
        key = str(record_id)
        if collection.has(key):
            type_name = type(record).__name__
            raise ImmutabilityError(
                f"{type_name} {record_id} already exists. "
                "Tensors are immutable — compose, don't overwrite."
            )
        collection.insert(self._to_doc(record))

    def _get(self, collection_name: str, record_id: UUID, model_cls):
        """Generic get by UUID."""
        mapped = self._map.collection_name(collection_name)
        collection = self._db.collection(mapped)
        key = str(record_id)
        doc = collection.get(key)
        if doc is None:
            raise NotFoundError(f"{model_cls.__name__} {record_id} not found.")
        return self._from_doc(model_cls, doc)

    def _load_all(self, collection_name: str, model_cls) -> list:
        """Load all records from a collection."""
        mapped = self._map.collection_name(collection_name)
        collection = self._db.collection(mapped)
        return [self._from_doc(model_cls, doc) for doc in collection.all()]

    # ── Generic Operations ────────────────────────────────────────

    def _to_generic_doc(self, record_id: UUID, record: ApachetaBaseModel) -> dict:
        """Convert a generic record (no assumed 'id' field) to ArangoDB doc."""
        data = record.model_dump(mode="json")
        data.pop("id", None)  # Remove id if present — _key is authoritative
        data["_key"] = str(record_id)
        return self._map.obfuscate_document(data)

    def _from_generic_doc(self, doc: dict) -> ApachetaBaseModel:
        """Convert an ArangoDB document back to an ApachetaBaseModel."""
        deobfuscated = self._map.deobfuscate_document(doc)
        data = {k: v for k, v in deobfuscated.items() if not k.startswith("_")}
        data["id"] = doc["_key"]
        return ApachetaBaseModel.model_validate(data)

    def store_record(self, record_id: UUID, record: ApachetaBaseModel) -> None:
        with self._lock:
            self._enforce_access("system", "store_record", record_id)
            mapped = self._map.collection_name("records")
            collection = self._db.collection(mapped)
            key = str(record_id)
            if collection.has(key):
                raise ImmutabilityError(
                    f"Record {record_id} already exists. "
                    "Records are immutable — compose, don't overwrite."
                )
            collection.insert(self._to_generic_doc(record_id, record))

    def get_record(self, record_id: UUID) -> ApachetaBaseModel:
        with self._lock:
            self._enforce_access("system", "get_record", record_id)
            mapped = self._map.collection_name("records")
            collection = self._db.collection(mapped)
            doc = collection.get(str(record_id))
            if doc is None:
                raise NotFoundError(f"Record {record_id} not found.")
            return self._from_generic_doc(doc)

    # ── Graph (Llika) Operations ─────────────────────────────────
    # The GraphBackend capability (yanantin.apacheta.interface.graph),
    # deliberately OFF the public ApachetaInterface catalog. This AQL used
    # to live in LlikaService against a raw privileged handle; it moves here
    # so it routes through self._map — the edge collection name AND the
    # traversal field paths are obfuscated under opaque storage, closing the
    # latent plaintext bypass.

    def _llika_edge_collection(self):
        """Return the (obfuscator-mapped) llika edge collection, creating it
        on first use as an edge collection. Idempotent."""
        mapped = self._map.collection_name(_LLIKA_EDGE_COLLECTION)
        if not self._db.has_collection(mapped):
            self._db.create_collection(mapped, edge=True)
        return self._db.collection(mapped)

    def _llika_field_names(self, vertex: dict) -> tuple[str, ...]:
        """A vertex's content field NAMES (shape), envelope fields stripped.

        The vertex came from storage, so its keys may be obfuscated — run it
        back through the obfuscator (unknown keys pass through unchanged) so
        the reported shape is semantic, then strip framework-envelope fields.
        """
        readable = self._map.deobfuscate_document(vertex)
        return tuple(
            sorted(k for k in readable if k not in _LLIKA_ENVELOPE_FIELDS)
        )

    def link(
        self,
        from_ref: str,
        to_ref: str,
        relation_type: RelationType,
        provenance: ProvenanceEnvelope,
        **fields: object,
    ) -> EdgeResult:
        """Create one immutable edge from_ref -> to_ref. Append-only; no
        update/delete. provenance is per-call (transport trust — the caller
        supplies it; this backend records it verbatim). Returns a serializable
        EdgeResult, never the raw doc or the pydantic model."""
        with self._lock:
            edge = LlikaCompositionEdge(
                **{"_from": from_ref, "_to": to_ref},
                created_at=datetime.now(timezone.utc),
                relation_type=relation_type,
                provenance=provenance,
                **fields,
            )
            doc = edge.model_dump(by_alias=True, mode="json")
            self._llika_edge_collection().insert(self._map.obfuscate_document(doc))
            return EdgeResult(
                edge_id=str(edge.id),
                from_id=from_ref,
                to_id=to_ref,
                relation_type=edge.relation_type.value,
                created_at=doc["created_at"],
            )

    def walk(
        self,
        start_id: str,
        direction: str,
        depth: int,
        relation_types: list[str] | None = None,
        max_results: int = 50,
    ) -> list[PathResult]:
        """Traverse from start_id by structure (direction + depth + optional
        relation_type filter). Returns serializable PathResults carrying every
        intermediate vertex's id-ref + content shape. Capped at max_results.

        direction: "forward" (OUTBOUND) | "backward" (INBOUND) | "both" (ANY).
        relation_types: RelationType VALUES to follow (e.g. "composes_with");
            None follows all. The obfuscator leaves stored VALUES unchanged,
            so the filter value stays semantic; only the field PATH is mapped."""
        with self._lock:
            aql_dir = _LLIKA_DIRECTION_AQL[direction]
            mapped_edges = self._map.collection_name(_LLIKA_EDGE_COLLECTION)
            rel_path = self._map.field_path(("relation_type",))
            rel_filter = ""
            bind_vars: dict = {
                "start": start_id,
                "max_depth": depth,
                "max_results": max_results,
            }
            if relation_types:
                rel_filter = f"FILTER e.{rel_path} IN @relation_types"
                bind_vars["relation_types"] = relation_types
            aql = f"""
            FOR v, e, p IN 1..@max_depth {aql_dir} @start {mapped_edges}
                {rel_filter}
                LIMIT @max_results
                RETURN p
            """
            cursor = self._db.aql.execute(aql, bind_vars=bind_vars)
            results: list[PathResult] = []
            for p in cursor:
                steps = tuple(
                    PathStep(
                        record_id=vertex["_id"],
                        relation_type=edge.get(rel_path, edge.get("relation_type")),
                        field_names=self._llika_field_names(vertex),
                    )
                    for vertex, edge in zip(p["vertices"][1:], p["edges"])
                )
                results.append(PathResult(start_id=start_id, steps=steps))
            return results

    def neighbors(
        self,
        start_id: str,
        direction: str,
        relation_types: list[str] | None = None,
    ) -> list[PathResult]:
        """Depth-1 convenience: who is adjacent. walk(..., depth=1)."""
        return self.walk(
            start_id, direction, depth=1, relation_types=relation_types
        )

    def find(self, terms: str, limit: int = 10) -> FindResult:
        """Content-axis find over the open `records` lane: the records whose
        deobfuscated string content contains `terms` (case-insensitive
        substring). Returns bare-UUID addresses + a bounded snippet + the SHAPE
        of which fields matched — never full record content (the recall
        boundary; hydrate one hit deliberately via get_record).

        DELIBERATELY NAIVE — this is the first square metre of road, not the
        autobahn. A FULL SCAN with a Python substring match: no ArangoSearch
        view, no BM25, no analyzer/stemming. KNOWN GAPS (declared, each a gh
        issue in the find spec): relevance ranking, the filter / structure /
        window axes, value-obfuscation (gh #9 — this searches PLAINTEXT and
        only works under the transparent obfuscator), Pukara placement (gh #8),
        and the max_scan/scan_truncated guard (total_matched is EXACT here
        because the scan is complete). Replacing this body with an ArangoSearch
        view is the next slice; FindResult's SHAPE is the contract and does not
        change when the engine does."""
        needle = terms.lower()
        with self._lock:
            mapped = self._map.collection_name("records")
            collection = self._db.collection(mapped)
            hits: list[FindHit] = []
            total = 0
            for doc in collection.all():
                clear = self._map.deobfuscate_document(doc)
                matched_fields: list[str] = []
                snippet = ""
                for key, value in clear.items():
                    if key.startswith("_") or not isinstance(value, str):
                        continue
                    pos = value.lower().find(needle)
                    if pos == -1:
                        continue
                    matched_fields.append(key)
                    if not snippet:
                        lo = max(0, pos - 30)
                        hi = min(len(value), pos + len(needle) + 30)
                        snippet = value[lo:hi]
                if not matched_fields:
                    continue
                total += 1
                if len(hits) < limit:
                    hits.append(
                        FindHit(
                            record_id=doc["_key"],
                            snippet=snippet,
                            matched_fields=tuple(matched_fields),
                        )
                    )
            # Count-at-boundary model: the naive full scan knows `total` for
            # free, so total_matched is always exact. `truncated` is the
            # boundary signal — len(hits) == limit means we hit the cap (the
            # case where a view-backed engine would run a separate count).
            return FindResult(
                hits=tuple(hits),
                total_matched=total,
                truncated=len(hits) == limit and total > limit,
            )

    # ── Write Operations ─────────────────────────────────────────

    def store_tensor(self, tensor: TensorRecord) -> None:
        with self._lock:
            self._enforce_access("system", "store_tensor", tensor.id)
            self._store("tensors", tensor.id, tensor)

    def store_composition_edge(self, edge: CompositionEdge) -> None:
        with self._lock:
            self._enforce_access("system", "store_composition_edge", edge.id)
            self._store("composition_edges", edge.id, edge)

    def store_correction(self, correction: CorrectionRecord) -> None:
        with self._lock:
            self._enforce_access("system", "store_correction", correction.id)
            self._store("corrections", correction.id, correction)

    def store_dissent(self, dissent: DissentRecord) -> None:
        with self._lock:
            self._enforce_access("system", "store_dissent", dissent.id)
            self._store("dissents", dissent.id, dissent)

    def store_negation(self, negation: NegationRecord) -> None:
        with self._lock:
            self._enforce_access("system", "store_negation", negation.id)
            self._store("negations", negation.id, negation)

    def store_bootstrap(self, bootstrap: BootstrapRecord) -> None:
        with self._lock:
            self._enforce_access("system", "store_bootstrap", bootstrap.id)
            self._store("bootstraps", bootstrap.id, bootstrap)

    def store_evolution(self, evolution: SchemaEvolutionRecord) -> None:
        with self._lock:
            self._enforce_access("system", "store_evolution", evolution.id)
            self._store("evolutions", evolution.id, evolution)

    def store_entity(self, entity: EntityResolution) -> None:
        with self._lock:
            self._enforce_access("system", "store_entity", entity.id)
            self._store("entities", entity.id, entity)

    def _provenance_edge_collection(self):
        """Return the (obfuscator-mapped) provenance_edges collection, creating
        it on first use as an EDGE collection. Idempotent.

        Mirrors _llika_edge_collection: the collection MUST be edge-type
        (create_collection(edge=True)) so native graph traversal
        (FOR v IN OUTBOUND ...) works on its _from/_to. The generic _store
        path creates plain document collections and dumps without by_alias,
        so it cannot host edges — this is why provenance_edges gets its own
        store path rather than going through _store.
        """
        mapped = self._map.collection_name("provenance_edges")
        if not self._db.has_collection(mapped):
            self._db.create_collection(mapped, edge=True)
        return self._db.collection(mapped)

    def store_provenance_edge(self, edge: ProvenanceEdge) -> None:
        with self._lock:
            self._enforce_access("system", "store_provenance_edge", edge.id)
            collection = self._provenance_edge_collection()
            key = str(edge.id)
            if collection.has(key):
                raise ImmutabilityError(
                    f"ProvenanceEdge {edge.id} already exists. "
                    "Edges are append-only — no update, no overwrite."
                )
            # by_alias=True so _from/_to land as ArangoDB's native edge fields.
            doc = edge.model_dump(mode="json", by_alias=True)
            doc["_key"] = key
            collection.insert(self._map.obfuscate_document(doc))

    def list_provenance_edges(self) -> list[ProvenanceEdge]:
        with self._lock:
            collection = self._provenance_edge_collection()
            results: list[ProvenanceEdge] = []
            for doc in collection.all():
                deobfuscated = self._map.deobfuscate_document(doc)
                # _from/_to are native edge fields → map back to the model's
                # aliases; strip ArangoDB metadata; restore id from _key.
                data = {
                    k: v for k, v in deobfuscated.items() if not k.startswith("_")
                }
                data["_from"] = deobfuscated["_from"]
                data["_to"] = deobfuscated["_to"]
                data["id"] = doc["_key"]
                results.append(ProvenanceEdge.model_validate(data))
            return results

    # ── Read Operations ──────────────────────────────────────────

    def get_tensor(self, tensor_id: UUID) -> TensorRecord:
        with self._lock:
            self._enforce_access("system", "get_tensor", tensor_id)
            return self._get("tensors", tensor_id, TensorRecord)

    def get_strand(self, tensor_id: UUID, strand_index: int) -> TensorRecord:
        """Returns a projection of the tensor containing only the requested strand."""
        with self._lock:
            tensor = self.get_tensor(tensor_id)
            matching = [s for s in tensor.strands if s.strand_index == strand_index]
            if not matching:
                raise NotFoundError(
                    f"Strand {strand_index} not found in tensor {tensor_id}."
                )
            return TensorRecord(
                id=tensor.id,
                provenance=tensor.provenance,
                preamble=tensor.preamble,
                strands=matching,
                closing=tensor.closing,
                instructions_for_next=tensor.instructions_for_next,
                narrative_body=tensor.narrative_body,
                lineage_tags=tensor.lineage_tags,
                composition_equation=tensor.composition_equation,
                declared_losses=tensor.declared_losses,
                epistemic=tensor.epistemic,
                open_questions=tensor.open_questions,
            )

    def get_entity(self, entity_id: UUID) -> EntityResolution:
        with self._lock:
            self._enforce_access("system", "get_entity", entity_id)
            return self._get("entities", entity_id, EntityResolution)

    def list_tensors(self) -> list[TensorRecord]:
        with self._lock:
            return self._load_all("tensors", TensorRecord)

    # ── Query Operations ─────────────────────────────────────────
    # Same Python-side logic as in-memory and DuckDB backends.
    # AQL queries come when scale demands them.

    def query_tensors_for_budget(self, budget: float) -> list[TensorRecord]:
        with self._lock:
            return self._load_all("tensors", TensorRecord)

    def query_operational_principles(self) -> list[str]:
        with self._lock:
            principles = []
            for tensor in self._load_all("tensors", TensorRecord):
                for strand in tensor.strands:
                    for claim in strand.key_claims:
                        principles.append(claim.text)
            return principles

    def query_project_state(self) -> dict:
        with self._lock:
            tensors = self._load_all("tensors", TensorRecord)
            return {
                "tensor_count": len(tensors),
                "lineage_tags": sorted({
                    tag
                    for t in tensors
                    for tag in t.lineage_tags
                }),
                "model_families": sorted({
                    t.provenance.author_model_family
                    for t in tensors
                    if t.provenance.author_model_family
                }),
            }

    def query_claims_about(self, topic: str) -> list[dict]:
        with self._lock:
            results = []
            topic_lower = topic.lower()
            for tensor in self._load_all("tensors", TensorRecord):
                for strand in tensor.strands:
                    strand_matches = (
                        topic_lower in strand.title.lower()
                        or topic_lower in " ".join(strand.topics).lower()
                    )
                    for claim in strand.key_claims:
                        if strand_matches or topic_lower in claim.text.lower():
                            results.append({
                                "tensor_id": tensor.id,
                                "strand_index": strand.strand_index,
                                "claim": claim.text,
                                "epistemic": claim.epistemic.model_dump(),
                            })
            return results

    def query_correction_chain(self, claim_id: UUID) -> list[CorrectionRecord]:
        with self._lock:
            return [
                c for c in self._load_all("corrections", CorrectionRecord)
                if c.target_claim_id == claim_id
            ]

    def query_epistemic_status(self, claim_id: UUID) -> dict:
        with self._lock:
            corrections = self.query_correction_chain(claim_id)
            if corrections:
                latest = corrections[-1]
                return {
                    "current_claim": latest.corrected_claim,
                    "correction_count": len(corrections),
                    "original_claim": corrections[0].original_claim,
                }
            return {"current_claim": None, "correction_count": 0}

    def query_disagreements(self) -> list[dict]:
        with self._lock:
            results = []
            for d in self._load_all("dissents", DissentRecord):
                results.append({
                    "type": "dissent",
                    "target_tensor": d.target_tensor,
                    "framework": d.alternative_framework,
                })
            for n in self._load_all("negations", NegationRecord):
                results.append({
                    "type": "negation",
                    "tensor_a": n.tensor_a,
                    "tensor_b": n.tensor_b,
                    "reasoning": n.reasoning,
                })
            for c in self._load_all("corrections", CorrectionRecord):
                results.append({
                    "type": "correction",
                    "target_tensor": c.target_tensor,
                    "original": c.original_claim,
                    "corrected": c.corrected_claim,
                })
            return results

    def query_composition_graph(self) -> list[CompositionEdge]:
        with self._lock:
            return self._load_all("composition_edges", CompositionEdge)

    def query_lineage(self, tensor_id: UUID) -> list[TensorRecord]:
        with self._lock:
            tensors = self._load_all("tensors", TensorRecord)
            tensor_map = {t.id: t for t in tensors}
            if tensor_id not in tensor_map:
                raise NotFoundError(f"Tensor {tensor_id} not found.")
            lineage_tags = set(tensor_map[tensor_id].lineage_tags)
            return [
                t for t in tensors
                if set(t.lineage_tags) & lineage_tags
            ]

    def query_bridges(self) -> list[CompositionEdge]:
        with self._lock:
            return [
                e for e in self._load_all("composition_edges", CompositionEdge)
                if e.authored_mapping is not None
            ]

    def query_error_classes(self) -> list[dict]:
        with self._lock:
            results = []
            for tensor in self._load_all("tensors", TensorRecord):
                for strand in tensor.strands:
                    for topic in strand.topics:
                        if any(w in topic.lower() for w in ("error", "failure", "blind-spot", "anti-pattern")):
                            results.append({
                                "tensor_id": tensor.id,
                                "strand": strand.title,
                                "topic": topic,
                            })
            return results

    def query_open_questions(self) -> list[str]:
        with self._lock:
            questions = []
            for tensor in self._load_all("tensors", TensorRecord):
                questions.extend(tensor.open_questions)
            return questions

    def query_unreliable_signals(self) -> list[dict]:
        with self._lock:
            results = []
            for tensor in self._load_all("tensors", TensorRecord):
                for strand in tensor.strands:
                    for claim in strand.key_claims:
                        if claim.epistemic.indeterminacy > 0.5:
                            results.append({
                                "tensor_id": tensor.id,
                                "claim": claim.text,
                                "indeterminacy": claim.epistemic.indeterminacy,
                            })
            return results

    def query_anti_patterns(self) -> list[dict]:
        with self._lock:
            results = []
            for tensor in self._load_all("tensors", TensorRecord):
                for strand in tensor.strands:
                    for topic in strand.topics:
                        if "anti-pattern" in topic.lower():
                            results.append({
                                "tensor_id": tensor.id,
                                "strand": strand.title,
                                "topic": topic,
                            })
            return results

    def query_authorship(self, tensor_id: UUID) -> dict:
        with self._lock:
            tensor = self.get_tensor(tensor_id)
            return {
                "author_model_family": tensor.provenance.author_model_family,
                "author_instance_id": tensor.provenance.author_instance_id,
                "timestamp": tensor.provenance.timestamp.isoformat(),
                "context_budget": tensor.provenance.context_budget_at_write,
                "predecessors": [str(p) for p in tensor.provenance.predecessors_in_scope],
            }

    def query_cross_model(self) -> list[TensorRecord]:
        with self._lock:
            tensors = self._load_all("tensors", TensorRecord)
            families = {}
            for tensor in tensors:
                family = tensor.provenance.author_model_family
                if family:
                    families.setdefault(family, []).append(tensor)
            if len(families) <= 1:
                return []
            return tensors

    def query_reading_order(self, lineage_tag: str) -> list[TensorRecord]:
        with self._lock:
            matching = [
                t for t in self._load_all("tensors", TensorRecord)
                if lineage_tag in t.lineage_tags
            ]
            return sorted(matching, key=lambda t: t.provenance.timestamp)

    def query_unlearn(self, topic: str) -> dict:
        with self._lock:
            affected_claims = self.query_claims_about(topic)
            affected_tensors = {c["tensor_id"] for c in affected_claims}
            return {
                "topic": topic,
                "affected_claims": len(affected_claims),
                "affected_tensors": [str(t) for t in affected_tensors],
            }

    def query_losses(self, tensor_id: UUID) -> list[dict]:
        with self._lock:
            tensor = self.get_tensor(tensor_id)
            return [
                {
                    "what": loss.what_was_lost,
                    "why": loss.why,
                    "category": loss.category.value,
                }
                for loss in tensor.declared_losses
            ]

    def query_loss_patterns(self) -> list[dict]:
        with self._lock:
            by_category: dict[str, int] = {}
            for tensor in self._load_all("tensors", TensorRecord):
                for loss in tensor.declared_losses:
                    cat = loss.category.value
                    by_category[cat] = by_category.get(cat, 0) + 1
            return [
                {"category": cat, "count": count}
                for cat, count in sorted(by_category.items())
            ]

    def query_entities_by_uuid(self, entity_uuid: UUID) -> list[EntityResolution]:
        with self._lock:
            self._enforce_access("system", "query_entities_by_uuid", entity_uuid)
            return [
                entity
                for entity in self._load_all("entities", EntityResolution)
                if entity.entity_uuid == entity_uuid
            ]

    # ── Open-Record Queries (AQL-native) ─────────────────────────
    # AQL with indexes on the filtered fields. Not load-all-and-filter.
    # See cairn/T39 for why: arango was chosen for its query engine;
    # using it as a dict with extra latency throws away the reason
    # it's in the stack.

    def _open_records_collection_name(self) -> str:
        return self._map.collection_name("records")

    def _hydrate_open(self, doc: dict) -> tuple[UUID, ApachetaBaseModel]:
        key = doc["_key"]
        return UUID(key), self._from_generic_doc(doc)

    def list_open_records(
        self,
        limit: int | None = None,
    ) -> list[tuple[UUID, ApachetaBaseModel]]:
        with self._lock:
            self._enforce_access("system", "list_open_records")
            ts_path = self._map.field_path(("provenance", "timestamp"))
            bind_vars: dict[str, object] = {"@col": self._open_records_collection_name()}
            limit_clause = ""
            if limit is not None:
                limit_clause = " LIMIT @limit"
                bind_vars["limit"] = limit
            aql = (
                "FOR doc IN @@col "
                f"SORT doc.{ts_path} DESC"
                f"{limit_clause} "
                "RETURN doc"
            )
            cursor = self._db.aql.execute(aql, bind_vars=bind_vars)
            return [self._hydrate_open(doc) for doc in cursor]

    def query_open_by_author_instance(
        self,
        author_instance_id: str,
        limit: int | None = None,
    ) -> list[tuple[UUID, ApachetaBaseModel]]:
        with self._lock:
            self._enforce_access("system", "query_open_by_author_instance")
            author_path = self._map.field_path(("provenance", "author_instance_id"))
            ts_path = self._map.field_path(("provenance", "timestamp"))
            bind_vars: dict[str, object] = {
                "@col": self._open_records_collection_name(),
                "aid": author_instance_id,
            }
            limit_clause = ""
            if limit is not None:
                limit_clause = " LIMIT @limit"
                bind_vars["limit"] = limit
            # Records without provenance have doc.provenance == null, so
            # doc.provenance.author_instance_id is null and the == filter
            # naturally excludes them — conventional-not-structural contract
            # implemented by AQL's null semantics, no explicit skip needed.
            aql = (
                "FOR doc IN @@col "
                f"FILTER doc.{author_path} == @aid "
                f"SORT doc.{ts_path} DESC"
                f"{limit_clause} "
                "RETURN doc"
            )
            cursor = self._db.aql.execute(aql, bind_vars=bind_vars)
            return [self._hydrate_open(doc) for doc in cursor]

    def query_open_by_lineage_tag(
        self,
        tag: str,
        limit: int | None = None,
    ) -> list[tuple[UUID, ApachetaBaseModel]]:
        with self._lock:
            self._enforce_access("system", "query_open_by_lineage_tag")
            tags_path = self._map.field_path(("lineage_tags",))
            ts_path = self._map.field_path(("provenance", "timestamp"))
            bind_vars: dict[str, object] = {
                "@col": self._open_records_collection_name(),
                "tag": tag,
            }
            limit_clause = ""
            if limit is not None:
                limit_clause = " LIMIT @limit"
                bind_vars["limit"] = limit
            aql = (
                "FOR doc IN @@col "
                f"FILTER @tag IN doc.{tags_path} "
                f"SORT doc.{ts_path} DESC"
                f"{limit_clause} "
                "RETURN doc"
            )
            cursor = self._db.aql.execute(aql, bind_vars=bind_vars)
            return [self._hydrate_open(doc) for doc in cursor]

    def query_open_has_field(
        self,
        field: str,
        limit: int | None = None,
    ) -> list[tuple[UUID, ApachetaBaseModel]]:
        with self._lock:
            self._enforce_access("system", "query_open_has_field")
            # The caller's `field` is the semantic name; the stored name
            # goes through field_name for obfuscator translation.
            stored_field = self._map.field_name(field)
            ts_path = self._map.field_path(("provenance", "timestamp"))
            bind_vars: dict[str, object] = {
                "@col": self._open_records_collection_name(),
                "field": stored_field,
            }
            limit_clause = ""
            if limit is not None:
                limit_clause = " LIMIT @limit"
                bind_vars["limit"] = limit
            aql = (
                "FOR doc IN @@col "
                "FILTER HAS(doc, @field) "
                f"SORT doc.{ts_path} DESC"
                f"{limit_clause} "
                "RETURN doc"
            )
            cursor = self._db.aql.execute(aql, bind_vars=bind_vars)
            return [self._hydrate_open(doc) for doc in cursor]

    def list_author_instances(self) -> list[str]:
        with self._lock:
            self._enforce_access("system", "list_author_instances")
            author_path = self._map.field_path(("provenance", "author_instance_id"))
            aql = (
                "FOR doc IN @@col "
                f"FILTER doc.{author_path} != null "
                f"RETURN DISTINCT doc.{author_path}"
            )
            bind_vars = {"@col": self._open_records_collection_name()}
            cursor = self._db.aql.execute(aql, bind_vars=bind_vars)
            return [aid for aid in cursor if aid]

    # ── Record Counts ────────────────────────────────────────────

    def count_records(self) -> dict[str, int]:
        with self._lock:
            key_map = {
                "tensors": "tensors",
                "composition_edges": "edges",
                "corrections": "corrections",
                "dissents": "dissents",
                "negations": "negations",
                "bootstraps": "bootstraps",
                "evolutions": "evolutions",
                "entities": "entities",
                "records": "records",
            }
            return {
                key: self._db.collection(self._map.collection_name(table)).count()
                for table, key in key_map.items()
            }
