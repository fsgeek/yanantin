"""Unit tests for the in-memory backend."""

from datetime import datetime
import threading
from uuid import uuid4

import pytest

from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.apacheta.interface.errors import ImmutabilityError, NotFoundError
from yanantin.apacheta.models import (
    BootstrapRecord,
    CompositionEdge,
    CorrectionRecord,
    DeclaredLoss,
    DissentRecord,
    EntityResolution,
    EpistemicMetadata,
    KeyClaim,
    LossCategory,
    NegationRecord,
    ProvenanceEnvelope,
    RelationType,
    SchemaEvolutionRecord,
    StrandRecord,
    TensorRecord,
)


@pytest.fixture
def backend():
    return InMemoryBackend()


@pytest.fixture
def sample_tensor():
    return TensorRecord(
        provenance=ProvenanceEnvelope(
            author_model_family="claude",
            timestamp=datetime(2026, 2, 7),
        ),
        preamble="Test tensor",
        strands=[
            StrandRecord(
                strand_index=0,
                title="Test Strand",
                topics=["testing"],
                key_claims=[
                    KeyClaim(
                        text="Tests validate correctness",
                        epistemic=EpistemicMetadata(truth=0.95),
                    ),
                ],
            ),
        ],
        lineage_tags=["test-sequence"],
    )


class TestStoreAndRetrieve:
    def test_store_and_get_tensor(self, backend, sample_tensor):
        backend.store_tensor(sample_tensor)
        retrieved = backend.get_tensor(sample_tensor.id)
        assert retrieved.id == sample_tensor.id
        assert retrieved.preamble == "Test tensor"

    def test_list_tensors(self, backend, sample_tensor):
        assert backend.list_tensors() == []
        backend.store_tensor(sample_tensor)
        tensors = backend.list_tensors()
        assert len(tensors) == 1
        assert tensors[0].id == sample_tensor.id

    def test_get_strand(self, backend, sample_tensor):
        backend.store_tensor(sample_tensor)
        result = backend.get_strand(sample_tensor.id, 0)
        assert len(result.strands) == 1
        assert result.strands[0].title == "Test Strand"

    def test_get_nonexistent_tensor(self, backend):
        with pytest.raises(NotFoundError):
            backend.get_tensor(uuid4())

    def test_get_nonexistent_strand(self, backend, sample_tensor):
        backend.store_tensor(sample_tensor)
        with pytest.raises(NotFoundError):
            backend.get_strand(sample_tensor.id, 99)


class TestCompositionEdgeStorage:
    def test_store_and_query_edges(self, backend):
        t_a, t_b = uuid4(), uuid4()
        edge = CompositionEdge(
            from_tensor=t_a,
            to_tensor=t_b,
            relation_type=RelationType.COMPOSES_WITH,
        )
        backend.store_composition_edge(edge)
        graph = backend.query_composition_graph()
        assert len(graph) == 1
        assert graph[0].from_tensor == t_a

    def test_bridge_query(self, backend):
        edge = CompositionEdge(
            from_tensor=uuid4(),
            to_tensor=uuid4(),
            relation_type=RelationType.COMPOSES_WITH,
            authored_mapping="Theory maps to practice via...",
        )
        backend.store_composition_edge(edge)
        bridges = backend.query_bridges()
        assert len(bridges) == 1


class TestCorrectionStorage:
    def test_store_correction(self, backend):
        claim_id = uuid4()
        corr = CorrectionRecord(
            target_tensor=uuid4(),
            target_claim_id=claim_id,
            original_claim="Entropy measures truth",
            corrected_claim="Entropy measures familiarity",
        )
        backend.store_correction(corr)
        chain = backend.query_correction_chain(claim_id)
        assert len(chain) == 1
        assert chain[0].corrected_claim == "Entropy measures familiarity"

    def test_epistemic_status_after_correction(self, backend):
        claim_id = uuid4()
        corr = CorrectionRecord(
            target_tensor=uuid4(),
            target_claim_id=claim_id,
            original_claim="Old claim",
            corrected_claim="New claim",
        )
        backend.store_correction(corr)
        status = backend.query_epistemic_status(claim_id)
        assert status["current_claim"] == "New claim"
        assert status["correction_count"] == 1


class TestDissentAndNegation:
    def test_store_dissent(self, backend):
        dissent = DissentRecord(
            target_tensor=uuid4(),
            alternative_framework="Field topology",
            reasoning="Continuous > discrete",
        )
        backend.store_dissent(dissent)
        disagreements = backend.query_disagreements()
        assert any(d["type"] == "dissent" for d in disagreements)

    def test_store_negation(self, backend):
        neg = NegationRecord(
            tensor_a=uuid4(),
            tensor_b=uuid4(),
            reasoning="Different lineages",
        )
        backend.store_negation(neg)
        disagreements = backend.query_disagreements()
        assert any(d["type"] == "negation" for d in disagreements)


class TestBootstrapAndEvolution:
    def test_store_bootstrap(self, backend):
        boot = BootstrapRecord(
            instance_id="test-instance",
            context_budget=0.80,
            task="Testing",
        )
        backend.store_bootstrap(boot)
        counts = backend.count_records()
        assert counts["bootstraps"] == 1

    def test_store_evolution(self, backend):
        evo = SchemaEvolutionRecord(
            from_version="v1",
            to_version="v2",
            fields_added=["functional_spec"],
        )
        backend.store_evolution(evo)
        counts = backend.count_records()
        assert counts["evolutions"] == 1


class TestEntityResolutionStorage:
    def test_store_entity(self, backend):
        entity = EntityResolution(
            entity_uuid=uuid4(),
            identity_type="ai_instance",
            identity_data={"model": "claude"},
        )
        backend.store_entity(entity)
        counts = backend.count_records()
        assert counts["entities"] == 1


class TestQueryOperations:
    def test_query_claims_about(self, backend, sample_tensor):
        backend.store_tensor(sample_tensor)
        claims = backend.query_claims_about("testing")
        assert len(claims) == 1
        assert "Tests validate correctness" in claims[0]["claim"]

    def test_query_open_questions(self, backend):
        tensor = TensorRecord(
            open_questions=["How does the archivist query?", "What is minimum viable Apacheta?"],
        )
        backend.store_tensor(tensor)
        questions = backend.query_open_questions()
        assert len(questions) == 2

    def test_query_losses(self, backend):
        tensor = TensorRecord(
            declared_losses=[
                DeclaredLoss(
                    what_was_lost="chronological detail",
                    why="curvature over precision",
                    category=LossCategory.AUTHORIAL_CHOICE,
                ),
            ],
        )
        backend.store_tensor(tensor)
        losses = backend.query_losses(tensor.id)
        assert len(losses) == 1
        assert losses[0]["category"] == "authorial_choice"

    def test_query_loss_patterns(self, backend):
        for _ in range(3):
            tensor = TensorRecord(
                declared_losses=[
                    DeclaredLoss(
                        what_was_lost="something",
                        why="pressure",
                        category=LossCategory.CONTEXT_PRESSURE,
                    ),
                ],
            )
            backend.store_tensor(tensor)
        patterns = backend.query_loss_patterns()
        assert any(p["category"] == "context_pressure" and p["count"] == 3 for p in patterns)

    def test_query_authorship(self, backend, sample_tensor):
        backend.store_tensor(sample_tensor)
        auth = backend.query_authorship(sample_tensor.id)
        assert auth["author_model_family"] == "claude"

    def test_query_lineage(self, backend):
        t1 = TensorRecord(lineage_tags=["seq-a"])
        t2 = TensorRecord(lineage_tags=["seq-a"])
        t3 = TensorRecord(lineage_tags=["seq-b"])
        backend.store_tensor(t1)
        backend.store_tensor(t2)
        backend.store_tensor(t3)
        lineage = backend.query_lineage(t1.id)
        assert len(lineage) == 2  # t1 and t2 share seq-a

    def test_query_reading_order(self, backend):
        t1 = TensorRecord(
            provenance=ProvenanceEnvelope(timestamp=datetime(2026, 2, 7)),
            lineage_tags=["experimental"],
        )
        t2 = TensorRecord(
            provenance=ProvenanceEnvelope(timestamp=datetime(2026, 2, 8)),
            lineage_tags=["experimental"],
        )
        backend.store_tensor(t2)  # store out of order
        backend.store_tensor(t1)
        ordered = backend.query_reading_order("experimental")
        assert ordered[0].id == t1.id  # earlier first

    def test_query_cross_model(self, backend):
        t1 = TensorRecord(provenance=ProvenanceEnvelope(author_model_family="claude"))
        t2 = TensorRecord(provenance=ProvenanceEnvelope(author_model_family="chatgpt"))
        backend.store_tensor(t1)
        backend.store_tensor(t2)
        cross = backend.query_cross_model()
        assert len(cross) == 2

    def test_query_unreliable_signals(self, backend):
        tensor = TensorRecord(
            strands=[
                StrandRecord(
                    strand_index=0,
                    title="Uncertain",
                    key_claims=[
                        KeyClaim(
                            text="Agency is indeterminate",
                            epistemic=EpistemicMetadata(indeterminacy=0.8),
                        ),
                    ],
                ),
            ],
        )
        backend.store_tensor(tensor)
        unreliable = backend.query_unreliable_signals()
        assert len(unreliable) == 1
        assert unreliable[0]["indeterminacy"] == 0.8

    def test_query_project_state(self, backend, sample_tensor):
        backend.store_tensor(sample_tensor)
        state = backend.query_project_state()
        assert state["tensor_count"] == 1
        assert "test-sequence" in state["lineage_tags"]

    def test_query_unlearn(self, backend, sample_tensor):
        backend.store_tensor(sample_tensor)
        result = backend.query_unlearn("testing")
        assert result["affected_claims"] == 1

    def test_interface_version(self, backend):
        assert backend.get_interface_version() == "v1"

    def test_check_access_always_true(self, backend):
        assert backend.check_access("anyone", "anything") is True


class TestUntestedQueries:
    def test_query_operational_principles(self, backend):
        tensor = TensorRecord(
            strands=[
                StrandRecord(
                    strand_index=0,
                    title="Principles",
                    topics=["operations"],
                    key_claims=[
                        KeyClaim(text="Maintain open logs", epistemic=EpistemicMetadata(truth=0.8)),
                        KeyClaim(text="Prefer simple invariants", epistemic=EpistemicMetadata(truth=0.7)),
                    ],
                ),
            ],
        )
        backend.store_tensor(tensor)

        principles = backend.query_operational_principles()

        assert principles == ["Maintain open logs", "Prefer simple invariants"]

    def test_query_error_classes(self, backend):
        tensor = TensorRecord(
            strands=[
                StrandRecord(
                    strand_index=0,
                    title="Observability",
                    topics=["error: indexing", "resilience"],
                    key_claims=[
                        KeyClaim(text="Index carefully", epistemic=EpistemicMetadata(truth=0.6)),
                    ],
                ),
            ],
        )
        backend.store_tensor(tensor)

        matches = backend.query_error_classes()

        assert any(match["topic"] == "error: indexing" for match in matches)

    def test_query_anti_patterns_delegates_to_error_classes(self, backend):
        tensor = TensorRecord(
            strands=[
                StrandRecord(
                    strand_index=0,
                    title="Failure Taxonomy",
                    topics=["anti-pattern: coupling"],
                    key_claims=[
                        KeyClaim(text="Avoid tight coupling", epistemic=EpistemicMetadata(truth=0.9)),
                    ],
                ),
            ],
        )
        backend.store_tensor(tensor)

        errors = backend.query_error_classes()
        anti_patterns = backend.query_anti_patterns()

        assert anti_patterns == errors

    def test_query_lineage_empty_tags(self, backend):
        tensor = TensorRecord(lineage_tags=())
        backend.store_tensor(tensor)

        lineage = backend.query_lineage(tensor.id)

        # Currently, empty lineage tags mean no tensor (even itself) is returned.
        assert lineage == []

    def test_epistemic_accepts_extreme_values(self):
        metadata = EpistemicMetadata(truth=-5.0, falsity=999.0)

        assert metadata.truth == -5.0
        assert metadata.falsity == 999.0

    def test_concurrent_reads_with_reentrant_lock(self, backend, sample_tensor):
        backend.store_tensor(sample_tensor)
        claim_id = uuid4()
        correction = CorrectionRecord(
            target_tensor=sample_tensor.id,
            target_claim_id=claim_id,
            original_claim="Original claim",
            corrected_claim="Updated claim",
        )
        backend.store_correction(correction)
        results = {}

        def read_strand():
            strand_tensor = backend.get_strand(sample_tensor.id, 0)
            results["strand_title"] = strand_tensor.strands[0].title

        def read_epistemic_status():
            status = backend.query_epistemic_status(claim_id)
            results["current_claim"] = status["current_claim"]

        def read_unlearn():
            unlearn = backend.query_unlearn("testing")
            results["unlearn_claims"] = unlearn["affected_claims"]

        def write_tensor():
            backend.store_tensor(TensorRecord(lineage_tags=["concurrent"]))
            results["writer_done"] = True

        threads = [
            threading.Thread(target=read_strand),
            threading.Thread(target=read_epistemic_status),
            threading.Thread(target=read_unlearn),
            threading.Thread(target=write_tensor),
        ]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2)

        assert all(not thread.is_alive() for thread in threads)
        assert results["strand_title"] == "Test Strand"
        assert results["current_claim"] == "Updated claim"
        assert results["unlearn_claims"] >= 1
        assert results["writer_done"] is True
