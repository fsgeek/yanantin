"""DuckDB backend for Apacheta.

SQL-based persistent storage. Keeps the interface honest alongside
the in-memory backend — if the interface leaks backend-specific
assumptions, one of the two backends will expose it.

Design:
- (id UUID, data JSON) per table — full model serialized as JSON
- Immutability via check-before-insert (same as in-memory)
- Thread safety via RLock (same as in-memory)
- Query logic in Python (same as in-memory) — push to SQL when scale demands
- File-backed by default, :memory: for tests
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from uuid import UUID

import duckdb

from yanantin.apacheta.interface.abstract import ApachetaInterface
from yanantin.apacheta.interface.errors import (
    AccessDeniedError,
    ImmutabilityError,
    NotFoundError,
)
from yanantin.apacheta.models.composition import (
    BootstrapRecord,
    CompositionEdge,
    CorrectionRecord,
    DissentRecord,
    NegationRecord,
    RelationType,
    SchemaEvolutionRecord,
)
from yanantin.apacheta.models.entities import EntityResolution
from yanantin.apacheta.models.tensor import TensorRecord


# ── Schema ────────────────────────────────────────────────────────────

_TABLES = (
    "tensors",
    "composition_edges",
    "corrections",
    "dissents",
    "negations",
    "bootstraps",
    "evolutions",
    "entities",
)

_DDL = "\n".join(
    f"CREATE TABLE IF NOT EXISTS {t} (id VARCHAR PRIMARY KEY, data JSON NOT NULL);"
    for t in _TABLES
)

# Map table names to Pydantic model classes for deserialization
_TABLE_MODEL = {
    "tensors": TensorRecord,
    "composition_edges": CompositionEdge,
    "corrections": CorrectionRecord,
    "dissents": DissentRecord,
    "negations": NegationRecord,
    "bootstraps": BootstrapRecord,
    "evolutions": SchemaEvolutionRecord,
    "entities": EntityResolution,
}


class DuckDBBackend(ApachetaInterface):
    """DuckDB implementation of ApachetaInterface.

    Thread-safe via RLock. Enforces immutability: duplicate UUID
    on any store raises ImmutabilityError. Persistent to file.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._lock = threading.RLock()
        self._db_path = str(db_path)
        self._conn = duckdb.connect(self._db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(_DDL)

    def close(self) -> None:
        self._conn.close()

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

    @staticmethod
    def _serialize(record) -> str:
        """Serialize a Pydantic model to a JSON string."""
        return json.dumps(record.model_dump(mode="json"))

    @staticmethod
    def _deserialize(model_cls, data):
        """Deserialize from DuckDB JSON column to Pydantic model."""
        if isinstance(data, str):
            return model_cls.model_validate_json(data)
        # DuckDB may return parsed dict/list
        return model_cls.model_validate(data)

    def _exists(self, table: str, record_id: UUID) -> bool:
        result = self._conn.execute(
            f"SELECT 1 FROM {table} WHERE id = ?",  # noqa: S608
            [str(record_id)],
        ).fetchone()
        return result is not None

    def _store(self, table: str, record_id: UUID, record) -> None:
        """Generic store: check immutability, insert."""
        if self._exists(table, record_id):
            type_name = type(record).__name__
            raise ImmutabilityError(
                f"{type_name} {record_id} already exists. "
                "Tensors are immutable — compose, don't overwrite."
            )
        self._conn.execute(
            f"INSERT INTO {table} VALUES (?, ?)",  # noqa: S608
            [str(record_id), self._serialize(record)],
        )

    def _get(self, table: str, record_id: UUID, model_cls):
        """Generic get by UUID."""
        result = self._conn.execute(
            f"SELECT data FROM {table} WHERE id = ?",  # noqa: S608
            [str(record_id)],
        ).fetchone()
        if not result:
            raise NotFoundError(f"{model_cls.__name__} {record_id} not found.")
        return self._deserialize(model_cls, result[0])

    def _load_all(self, table: str, model_cls) -> list:
        """Load all records from a table."""
        rows = self._conn.execute(
            f"SELECT data FROM {table}",  # noqa: S608
        ).fetchall()
        return [self._deserialize(model_cls, row[0]) for row in rows]

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

    # ── Read Operations ──────────────────────────────────────────

    def get_tensor(self, tensor_id: UUID) -> TensorRecord:
        with self._lock:
            self._enforce_access("system", "get_tensor", tensor_id)
            return self._get("tensors", tensor_id, TensorRecord)

    def get_strand(self, tensor_id: UUID, strand_index: int) -> TensorRecord:
        """Returns a projection of the tensor containing only the requested strand.

        The returned TensorRecord shares the source tensor's UUID — it is a
        view, not a new entity. This is intentional: a strand carries its
        tensor's provenance. Storing the result would raise ImmutabilityError
        (duplicate UUID), which is the correct guard.
        """
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
    # Same logic as in-memory backend. Data loaded from DuckDB,
    # filtered in Python. Push to SQL when scale demands it.

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

    # ── Record Counts ────────────────────────────────────────────

    def count_records(self) -> dict[str, int]:
        with self._lock:
            counts = {}
            # Use the same keys as the in-memory backend
            key_map = {
                "tensors": "tensors",
                "composition_edges": "edges",
                "corrections": "corrections",
                "dissents": "dissents",
                "negations": "negations",
                "bootstraps": "bootstraps",
                "evolutions": "evolutions",
                "entities": "entities",
            }
            for table, key in key_map.items():
                result = self._conn.execute(
                    f"SELECT COUNT(*) FROM {table}",  # noqa: S608
                ).fetchone()
                counts[key] = result[0]
            return counts
