"""Red-bar test: Provenance invariant.

Every record has provenance. This is structural, not optional.
"""

from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.apacheta.models import (
    BootstrapRecord,
    CompositionEdge,
    CorrectionRecord,
    DissentRecord,
    EntityResolution,
    NegationRecord,
    ProvenanceEnvelope,
    RelationType,
    SchemaEvolutionRecord,
    TensorRecord,
)
from uuid import uuid4


def test_tensor_has_provenance():
    tensor = TensorRecord()
    assert isinstance(tensor.provenance, ProvenanceEnvelope)
    assert tensor.provenance.interface_version == "v1"


def test_composition_edge_has_provenance():
    edge = CompositionEdge(
        from_tensor=uuid4(),
        to_tensor=uuid4(),
        relation_type=RelationType.COMPOSES_WITH,
    )
    assert isinstance(edge.provenance, ProvenanceEnvelope)


def test_correction_has_provenance():
    corr = CorrectionRecord(
        target_tensor=uuid4(),
        original_claim="old",
        corrected_claim="new",
    )
    assert isinstance(corr.provenance, ProvenanceEnvelope)


def test_dissent_has_provenance():
    d = DissentRecord(
        target_tensor=uuid4(),
        alternative_framework="alt",
        reasoning="because",
    )
    assert isinstance(d.provenance, ProvenanceEnvelope)


def test_negation_has_provenance():
    n = NegationRecord(
        tensor_a=uuid4(),
        tensor_b=uuid4(),
        reasoning="different lineages",
    )
    assert isinstance(n.provenance, ProvenanceEnvelope)


def test_bootstrap_has_provenance():
    b = BootstrapRecord(
        instance_id="test",
        context_budget=0.8,
    )
    assert isinstance(b.provenance, ProvenanceEnvelope)


def test_evolution_has_provenance():
    e = SchemaEvolutionRecord(
        from_version="v1",
        to_version="v2",
    )
    assert isinstance(e.provenance, ProvenanceEnvelope)


def test_entity_has_provenance():
    e = EntityResolution(
        entity_uuid=uuid4(),
        identity_type="ai",
    )
    assert isinstance(e.provenance, ProvenanceEnvelope)


def test_stored_records_retain_provenance():
    """Provenance survives store/retrieve roundtrip."""
    backend = InMemoryBackend()
    tensor = TensorRecord(
        provenance=ProvenanceEnvelope(
            author_model_family="claude",
            author_instance_id="test-session",
        ),
    )
    backend.store_tensor(tensor)
    retrieved = backend.get_tensor(tensor.id)
    assert retrieved.provenance.author_model_family == "claude"
    assert retrieved.provenance.author_instance_id == "test-session"
