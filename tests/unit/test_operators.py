"""Unit tests for Apacheta composition operators."""

from uuid import uuid4

import pytest

from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.apacheta.models import (
    RelationType,
    StrandRecord,
    TensorRecord,
)
from yanantin.apacheta.operators.bootstrap import bootstrap
from yanantin.apacheta.operators.compose import compose
from yanantin.apacheta.operators.correct import correct
from yanantin.apacheta.operators.dissent import dissent
from yanantin.apacheta.operators.evolve import evolve
from yanantin.apacheta.operators.negate import negate
from yanantin.apacheta.operators.project import project


@pytest.fixture
def backend():
    return InMemoryBackend()


@pytest.fixture
def two_tensors(backend):
    t_a = TensorRecord(
        preamble="Tensor A",
        strands=[
            StrandRecord(strand_index=0, title="Theory", topics=["math", "logic"]),
            StrandRecord(strand_index=1, title="Practice", topics=["code", "testing"]),
        ],
        lineage_tags=["seq-a"],
    )
    t_b = TensorRecord(
        preamble="Tensor B",
        strands=[
            StrandRecord(strand_index=0, title="Observation", topics=["math"]),
        ],
        lineage_tags=["seq-b"],
    )
    backend.store_tensor(t_a)
    backend.store_tensor(t_b)
    return t_a, t_b


class TestCompose:
    def test_creates_edge(self, backend, two_tensors):
        t_a, t_b = two_tensors
        edge = compose(backend, t_a.id, t_b.id)
        assert edge.relation_type == RelationType.COMPOSES_WITH
        assert edge.from_tensor == t_a.id
        assert edge.to_tensor == t_b.id

    def test_edge_stored_through_interface(self, backend, two_tensors):
        t_a, t_b = two_tensors
        compose(backend, t_a.id, t_b.id)
        graph = backend.query_composition_graph()
        assert len(graph) == 1

    def test_non_commutative(self, backend, two_tensors):
        """compose(A, B) != compose(B, A) — ordering matters."""
        t_a, t_b = two_tensors
        edge_ab = compose(backend, t_a.id, t_b.id, ordering=1)
        edge_ba = compose(backend, t_b.id, t_a.id, ordering=2)
        assert edge_ab.from_tensor == t_a.id
        assert edge_ba.from_tensor == t_b.id
        assert edge_ab.id != edge_ba.id

    def test_bridge_has_mapping(self, backend, two_tensors):
        t_a, t_b = two_tensors
        edge = compose(
            backend, t_a.id, t_b.id,
            authored_mapping="Theory strands in A map to observation in B",
        )
        assert edge.authored_mapping is not None
        bridges = backend.query_bridges()
        assert len(bridges) == 1


class TestProject:
    def test_filter_by_index(self, backend, two_tensors):
        t_a, _ = two_tensors
        strands = project(backend, t_a.id, strand_indices=[0])
        assert len(strands) == 1
        assert strands[0].title == "Theory"

    def test_filter_by_topic(self, backend, two_tensors):
        t_a, _ = two_tensors
        strands = project(backend, t_a.id, topics=["code"])
        assert len(strands) == 1
        assert strands[0].title == "Practice"

    def test_no_filter_returns_all(self, backend, two_tensors):
        t_a, _ = two_tensors
        strands = project(backend, t_a.id)
        assert len(strands) == 2


class TestCorrect:
    def test_creates_correction(self, backend, two_tensors):
        t_a, _ = two_tensors
        corr = correct(
            backend, t_a.id,
            original_claim="Old claim",
            corrected_claim="New claim",
            evidence="Observed in testing",
        )
        assert corr.original_claim == "Old claim"
        assert corr.corrected_claim == "New claim"

    def test_original_preserved(self, backend, two_tensors):
        """Correction preserves the original — both are queryable."""
        t_a, t_b = two_tensors
        claim_id = uuid4()
        correct(
            backend, t_a.id,
            original_claim="Entropy measures truth",
            corrected_claim="Entropy measures familiarity",
            correcting_tensor=t_b.id,
            target_claim_id=claim_id,
        )
        chain = backend.query_correction_chain(claim_id)
        assert len(chain) == 1
        assert chain[0].original_claim == "Entropy measures truth"

    def test_creates_edge_when_correcting_tensor_given(self, backend, two_tensors):
        t_a, t_b = two_tensors
        correct(
            backend, t_a.id,
            original_claim="old",
            corrected_claim="new",
            correcting_tensor=t_b.id,
        )
        graph = backend.query_composition_graph()
        assert any(e.relation_type == RelationType.CORRECTS for e in graph)


class TestDissent:
    def test_creates_dissent_and_edge(self, backend, two_tensors):
        t_a, t_b = two_tensors
        record = dissent(
            backend, t_b.id, t_a.id,
            alternative_framework="Field topology",
            reasoning="Continuous > discrete",
        )
        assert record.alternative_framework == "Field topology"
        graph = backend.query_composition_graph()
        assert any(e.relation_type == RelationType.DISSENTS_FROM for e in graph)


class TestNegate:
    def test_creates_negation_and_edge(self, backend, two_tensors):
        t_a, t_b = two_tensors
        record = negate(backend, t_a.id, t_b.id, reasoning="Different lineages")
        assert record.reasoning == "Different lineages"
        graph = backend.query_composition_graph()
        assert any(e.relation_type == RelationType.DOES_NOT_COMPOSE_WITH for e in graph)


class TestBootstrap:
    def test_selects_all_when_no_ids(self, backend, two_tensors):
        record, selected = bootstrap(
            backend,
            instance_id="test-instance",
            context_budget=0.80,
        )
        assert len(selected) == 2
        assert record.context_budget == 0.80

    def test_persisted(self, backend, two_tensors):
        bootstrap(
            backend,
            instance_id="test",
            context_budget=0.50,
            task="Testing bootstrap",
        )
        counts = backend.count_records()
        assert counts["bootstraps"] == 1

    def test_selective_bootstrap(self, backend, two_tensors):
        t_a, _ = two_tensors
        record, selected = bootstrap(
            backend,
            instance_id="selective",
            context_budget=0.10,
            tensor_ids=[t_a.id],
            what_was_omitted="Tensor B — not relevant",
        )
        assert len(selected) == 1
        assert record.what_was_omitted == "Tensor B — not relevant"


class TestEvolve:
    def test_records_evolution(self, backend):
        record = evolve(
            backend,
            from_version="v1",
            to_version="v2",
            fields_added=["functional_spec"],
            migration_notes="Added functional T/I/F",
        )
        assert record.from_version == "v1"
        assert record.to_version == "v2"
        counts = backend.count_records()
        assert counts["evolutions"] == 1
