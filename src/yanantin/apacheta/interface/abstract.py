"""Abstract interface for Apacheta — the only API to the tensor database.

All backends implement this interface. Operators consume it.
No code outside this interface touches storage internals.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

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

INTERFACE_VERSION = "v1"


class ApachetaInterface(ABC):
    """Abstract base for all Apacheta storage backends.

    Design constraints:
    - Immutable: store raises ImmutabilityError on duplicate UUID
    - No delete, no update on stored records
    - Thread-safe from v1 (5 parallel instances is the operational model)
    - Access control hook on every operation
    """

    # ── Version ──────────────────────────────────────────────────

    def get_interface_version(self) -> str:
        return INTERFACE_VERSION

    # ── Access Control Hook ──────────────────────────────────────

    def check_access(self, caller: str, operation: str, target: UUID | None = None) -> bool:
        """Check whether caller is allowed to perform operation on target.

        Always returns True in v1. Hook exists so backends can override
        without interface changes.
        """
        return True

    # ── Write Operations ─────────────────────────────────────────
    # All produce new records. None modify existing ones.

    @abstractmethod
    def store_tensor(self, tensor: TensorRecord) -> None: ...

    @abstractmethod
    def store_composition_edge(self, edge: CompositionEdge) -> None: ...

    @abstractmethod
    def store_correction(self, correction: CorrectionRecord) -> None: ...

    @abstractmethod
    def store_dissent(self, dissent: DissentRecord) -> None: ...

    @abstractmethod
    def store_negation(self, negation: NegationRecord) -> None: ...

    @abstractmethod
    def store_bootstrap(self, bootstrap: BootstrapRecord) -> None: ...

    @abstractmethod
    def store_evolution(self, evolution: SchemaEvolutionRecord) -> None: ...

    @abstractmethod
    def store_entity(self, entity: EntityResolution) -> None: ...

    # ── Read Operations ──────────────────────────────────────────

    @abstractmethod
    def get_tensor(self, tensor_id: UUID) -> TensorRecord: ...

    @abstractmethod
    def get_strand(self, tensor_id: UUID, strand_index: int) -> TensorRecord: ...

    @abstractmethod
    def list_tensors(self) -> list[TensorRecord]: ...

    # ── Query Operations ─────────────────────────────────────────
    # Organized by category. Initial implementations can be simple.

    # Bootstrap queries
    @abstractmethod
    def query_tensors_for_budget(self, budget: float) -> list[TensorRecord]:
        """Q1: Which tensors fit within this context budget?"""
        ...

    @abstractmethod
    def query_operational_principles(self) -> list[str]:
        """Q2: What operational principles have been declared?"""
        ...

    @abstractmethod
    def query_project_state(self) -> dict:
        """Q3: Current project state across tensors."""
        ...

    # Epistemic queries
    @abstractmethod
    def query_claims_about(self, topic: str) -> list[dict]:
        """Q4: All claims about a topic, across tensors."""
        ...

    @abstractmethod
    def query_correction_chain(self, claim_id: UUID) -> list[CorrectionRecord]:
        """Q5: Full correction history for a claim."""
        ...

    @abstractmethod
    def query_epistemic_status(self, claim_id: UUID) -> dict:
        """Q6: Current epistemic status of a claim (including corrections)."""
        ...

    @abstractmethod
    def query_disagreements(self) -> list[dict]:
        """Q7: All disagreements (dissent, negation, correction)."""
        ...

    # Lineage queries
    @abstractmethod
    def query_composition_graph(self) -> list[CompositionEdge]:
        """Q8: The full composition graph."""
        ...

    @abstractmethod
    def query_lineage(self, tensor_id: UUID) -> list[TensorRecord]:
        """Q9: Lineage of a tensor (predecessors and successors)."""
        ...

    @abstractmethod
    def query_bridges(self) -> list[CompositionEdge]:
        """Q10: All bridge compositions (edges with authored mappings)."""
        ...

    # Evolution queries
    @abstractmethod
    def query_error_classes(self) -> list[dict]:
        """Q11: Known error classes across tensors."""
        ...

    @abstractmethod
    def query_open_questions(self) -> list[str]:
        """Q12: All open questions across tensors."""
        ...

    @abstractmethod
    def query_unreliable_signals(self) -> list[dict]:
        """Q13: Signals flagged as unreliable."""
        ...

    @abstractmethod
    def query_anti_patterns(self) -> list[dict]:
        """Q14: Known anti-patterns."""
        ...

    # Provenance queries
    @abstractmethod
    def query_authorship(self, tensor_id: UUID) -> dict:
        """Q15: Who authored a tensor and from what context."""
        ...

    @abstractmethod
    def query_cross_model(self) -> list[TensorRecord]:
        """Q16: Tensors authored by different model families."""
        ...

    @abstractmethod
    def query_reading_order(self, lineage_tag: str) -> list[TensorRecord]:
        """Q17: Recommended reading order for a lineage."""
        ...

    # Defensive queries
    @abstractmethod
    def query_unlearn(self, topic: str) -> dict:
        """Q18: What would need to change if this claim were wrong?"""
        ...

    # Loss queries
    @abstractmethod
    def query_losses(self, tensor_id: UUID) -> list[dict]:
        """Q19: Declared losses for a tensor."""
        ...

    @abstractmethod
    def query_loss_patterns(self) -> list[dict]:
        """Q20: Loss patterns across tensors."""
        ...

    # ── Record Counts (for monotonicity verification) ────────────

    @abstractmethod
    def count_records(self) -> dict[str, int]:
        """Return counts of each record type. Used by red-bar tests."""
        ...
