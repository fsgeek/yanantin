"""In-memory backend for Apacheta.

Dict-based storage with threading.RLock for thread safety.
Validates the interface contract. Not for production persistence —
that's the persistent backend's job.
"""

from __future__ import annotations

import threading
from uuid import UUID

from yanantin.apacheta.interface.abstract import ApachetaInterface
from yanantin.apacheta.interface.errors import AccessDeniedError, ImmutabilityError, NotFoundError
from yanantin.apacheta.models.composition import (
    BootstrapRecord,
    CompositionEdge,
    CorrectionRecord,
    DissentRecord,
    NegationRecord,
    SchemaEvolutionRecord,
)
from yanantin.apacheta.models.entities import EntityResolution
from yanantin.apacheta.models.tensor import TensorRecord


class InMemoryBackend(ApachetaInterface):
    """In-memory implementation of ApachetaInterface.

    Thread-safe via RLock. Enforces immutability: duplicate UUID
    on store_tensor raises ImmutabilityError.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tensors: dict[UUID, TensorRecord] = {}
        self._edges: dict[UUID, CompositionEdge] = {}
        self._corrections: dict[UUID, CorrectionRecord] = {}
        self._dissents: dict[UUID, DissentRecord] = {}
        self._negations: dict[UUID, NegationRecord] = {}
        self._bootstraps: dict[UUID, BootstrapRecord] = {}
        self._evolutions: dict[UUID, SchemaEvolutionRecord] = {}
        self._entities: dict[UUID, EntityResolution] = {}

    # ── Internal ──────────────────────────────────────────────────

    def _enforce_access(self, caller: str, operation: str, target=None) -> None:
        if not self.check_access(caller, operation, target):
            raise AccessDeniedError(
                f"Access denied: {caller} cannot {operation}"
                + (f" on {target}" if target else "")
            )

    @staticmethod
    def _deep_copy(record):
        """Deep-copy a record via serialize/deserialize roundtrip."""
        return type(record).model_validate(record.model_dump(mode="python"))

    # ── Write Operations ─────────────────────────────────────────

    def store_tensor(self, tensor: TensorRecord) -> None:
        with self._lock:
            self._enforce_access("system", "store_tensor", tensor.id)
            if tensor.id in self._tensors:
                raise ImmutabilityError(
                    f"Tensor {tensor.id} already exists. "
                    "Tensors are immutable — compose, don't overwrite."
                )
            self._tensors[tensor.id] = self._deep_copy(tensor)

    def store_composition_edge(self, edge: CompositionEdge) -> None:
        with self._lock:
            self._enforce_access("system", "store_composition_edge", edge.id)
            if edge.id in self._edges:
                raise ImmutabilityError(f"CompositionEdge {edge.id} already exists.")
            self._edges[edge.id] = self._deep_copy(edge)

    def store_correction(self, correction: CorrectionRecord) -> None:
        with self._lock:
            self._enforce_access("system", "store_correction", correction.id)
            if correction.id in self._corrections:
                raise ImmutabilityError(f"CorrectionRecord {correction.id} already exists.")
            self._corrections[correction.id] = self._deep_copy(correction)

    def store_dissent(self, dissent: DissentRecord) -> None:
        with self._lock:
            self._enforce_access("system", "store_dissent", dissent.id)
            if dissent.id in self._dissents:
                raise ImmutabilityError(f"DissentRecord {dissent.id} already exists.")
            self._dissents[dissent.id] = self._deep_copy(dissent)

    def store_negation(self, negation: NegationRecord) -> None:
        with self._lock:
            self._enforce_access("system", "store_negation", negation.id)
            if negation.id in self._negations:
                raise ImmutabilityError(f"NegationRecord {negation.id} already exists.")
            self._negations[negation.id] = self._deep_copy(negation)

    def store_bootstrap(self, bootstrap: BootstrapRecord) -> None:
        with self._lock:
            self._enforce_access("system", "store_bootstrap", bootstrap.id)
            if bootstrap.id in self._bootstraps:
                raise ImmutabilityError(f"BootstrapRecord {bootstrap.id} already exists.")
            self._bootstraps[bootstrap.id] = self._deep_copy(bootstrap)

    def store_evolution(self, evolution: SchemaEvolutionRecord) -> None:
        with self._lock:
            self._enforce_access("system", "store_evolution", evolution.id)
            if evolution.id in self._evolutions:
                raise ImmutabilityError(f"SchemaEvolutionRecord {evolution.id} already exists.")
            self._evolutions[evolution.id] = self._deep_copy(evolution)

    def store_entity(self, entity: EntityResolution) -> None:
        with self._lock:
            self._enforce_access("system", "store_entity", entity.id)
            if entity.id in self._entities:
                raise ImmutabilityError(f"EntityResolution {entity.id} already exists.")
            self._entities[entity.id] = self._deep_copy(entity)

    # ── Read Operations ──────────────────────────────────────────

    def get_tensor(self, tensor_id: UUID) -> TensorRecord:
        with self._lock:
            self._enforce_access("system", "get_tensor", tensor_id)
            if tensor_id not in self._tensors:
                raise NotFoundError(f"Tensor {tensor_id} not found.")
            return self._deep_copy(self._tensors[tensor_id])

    def get_strand(self, tensor_id: UUID, strand_index: int) -> TensorRecord:
        """Returns the tensor containing only the requested strand."""
        with self._lock:
            tensor = self.get_tensor(tensor_id)
            matching = [s for s in tensor.strands if s.strand_index == strand_index]
            if not matching:
                raise NotFoundError(
                    f"Strand {strand_index} not found in tensor {tensor_id}."
                )
            # Return a copy of the tensor with only the matching strand
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

    def list_tensors(self) -> list[TensorRecord]:
        with self._lock:
            return list(self._tensors.values())

    # ── Query Operations ─────────────────────────────────────────
    # Initial implementations: simple filtering. Sophistication comes
    # when demand reveals what's actually needed.

    def query_tensors_for_budget(self, budget: float) -> list[TensorRecord]:
        with self._lock:
            # Simple: return all tensors. Budget optimization is future work.
            return list(self._tensors.values())

    def query_operational_principles(self) -> list[str]:
        with self._lock:
            # Scan key claims for principle-like content
            principles = []
            for tensor in self._tensors.values():
                for strand in tensor.strands:
                    for claim in strand.key_claims:
                        principles.append(claim.text)
            return principles

    def query_project_state(self) -> dict:
        with self._lock:
            return {
                "tensor_count": len(self._tensors),
                "lineage_tags": sorted({
                    tag
                    for t in self._tensors.values()
                    for tag in t.lineage_tags
                }),
                "model_families": sorted({
                    t.provenance.author_model_family
                    for t in self._tensors.values()
                    if t.provenance.author_model_family
                }),
            }

    def query_claims_about(self, topic: str) -> list[dict]:
        with self._lock:
            results = []
            topic_lower = topic.lower()
            for tensor in self._tensors.values():
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
                c for c in self._corrections.values()
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
            for d in self._dissents.values():
                results.append({
                    "type": "dissent",
                    "target_tensor": d.target_tensor,
                    "framework": d.alternative_framework,
                })
            for n in self._negations.values():
                results.append({
                    "type": "negation",
                    "tensor_a": n.tensor_a,
                    "tensor_b": n.tensor_b,
                    "reasoning": n.reasoning,
                })
            for c in self._corrections.values():
                results.append({
                    "type": "correction",
                    "target_tensor": c.target_tensor,
                    "original": c.original_claim,
                    "corrected": c.corrected_claim,
                })
            return results

    def query_composition_graph(self) -> list[CompositionEdge]:
        with self._lock:
            return list(self._edges.values())

    def query_lineage(self, tensor_id: UUID) -> list[TensorRecord]:
        with self._lock:
            if tensor_id not in self._tensors:
                raise NotFoundError(f"Tensor {tensor_id} not found.")
            tensor = self._tensors[tensor_id]
            lineage_tags = set(tensor.lineage_tags)
            return [
                t for t in self._tensors.values()
                if set(t.lineage_tags) & lineage_tags
            ]

    def query_bridges(self) -> list[CompositionEdge]:
        with self._lock:
            return [
                e for e in self._edges.values()
                if e.authored_mapping is not None
            ]

    def query_error_classes(self) -> list[dict]:
        with self._lock:
            # Scan for strands with error/failure topics
            results = []
            for tensor in self._tensors.values():
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
            for tensor in self._tensors.values():
                questions.extend(tensor.open_questions)
            return questions

    def query_unreliable_signals(self) -> list[dict]:
        with self._lock:
            results = []
            for tensor in self._tensors.values():
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
            return self.query_error_classes()

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
            families = {}
            for tensor in self._tensors.values():
                family = tensor.provenance.author_model_family
                if family:
                    families.setdefault(family, []).append(tensor)
            if len(families) <= 1:
                return []
            return list(self._tensors.values())

    def query_reading_order(self, lineage_tag: str) -> list[TensorRecord]:
        with self._lock:
            matching = [
                t for t in self._tensors.values()
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
            for tensor in self._tensors.values():
                for loss in tensor.declared_losses:
                    cat = loss.category.value
                    by_category[cat] = by_category.get(cat, 0) + 1
            return [
                {"category": cat, "count": count}
                for cat, count in sorted(by_category.items())
            ]

    # ── Record Counts ────────────────────────────────────────────

    def count_records(self) -> dict[str, int]:
        with self._lock:
            return {
                "tensors": len(self._tensors),
                "edges": len(self._edges),
                "corrections": len(self._corrections),
                "dissents": len(self._dissents),
                "negations": len(self._negations),
                "bootstraps": len(self._bootstraps),
                "evolutions": len(self._evolutions),
                "entities": len(self._entities),
            }
