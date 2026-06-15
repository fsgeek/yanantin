"""Tests for ProvenanceEdge model."""
from uuid import uuid4

import pytest

from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.apacheta.interface.errors import ImmutabilityError
from yanantin.apacheta.models.provenance import ProvenanceEnvelope
from yanantin.apacheta.models.provenance_edge import ProvenanceEdge


def test_provenance_edge_fields():
    edge = ProvenanceEdge(
        _from="entities/abc123",
        _to="records/def456",
        relation_type="contains",
    )
    # The Pydantic field names are from_ref/to_ref; "_from"/"_to" are the
    # ArangoDB aliases used only for (de)serialization. Every downstream
    # consumer (Tasks 3, 5) reads edge.from_ref / edge.to_ref, so the test
    # asserts on those — the plan's draft used edge._from, which Pydantic v2
    # does not expose as an attribute (recorded finding, 2026-06-15).
    assert edge.from_ref == "entities/abc123"
    assert edge.to_ref == "records/def456"
    assert edge.relation_type == "contains"
    assert edge.id is not None
    dumped = edge.model_dump(by_alias=True)
    assert dumped["_from"] == "entities/abc123"
    assert dumped["_to"] == "records/def456"


def test_provenance_edge_requires_from_and_to():
    with pytest.raises(Exception):
        ProvenanceEdge(relation_type="contains")


def test_provenance_edge_from_must_include_collection():
    with pytest.raises(ValueError, match="must be collection/key"):
        ProvenanceEdge(_from="abc123", _to="records/def456", relation_type="contains")


def test_provenance_edge_to_must_include_collection():
    with pytest.raises(ValueError, match="must be collection/key"):
        ProvenanceEdge(_from="entities/abc123", _to="def456", relation_type="contains")


def test_provenance_edge_frozen():
    edge = ProvenanceEdge(
        _from="entities/abc123",
        _to="records/def456",
        relation_type="contains",
    )
    with pytest.raises(Exception):
        edge.relation_type = "other"


def test_store_provenance_edge_in_memory():
    backend = InMemoryBackend()
    predecessor_id = uuid4()
    provenance = ProvenanceEnvelope(
        author_model_family="unit-test-model",
        author_instance_id="provenance-edge-test",
        context_budget_at_write=0.42,
        predecessors_in_scope=(predecessor_id,),
    )
    edge = ProvenanceEdge(
        id=uuid4(),
        _from="entities/abc123",
        _to="records/def456",
        relation_type="contains",
        provenance=provenance,
    )
    backend.store_provenance_edge(edge)
    edges = backend.list_provenance_edges()
    assert len(edges) == 1
    stored = edges[0]
    assert stored.id == edge.id
    assert stored.from_ref == "entities/abc123"
    assert stored.to_ref == "records/def456"
    assert stored.relation_type == "contains"
    assert stored.provenance == provenance
    assert stored.provenance.model_dump(mode="json") == provenance.model_dump(mode="json")


def test_store_provenance_edge_allows_same_refs_with_distinct_ids():
    backend = InMemoryBackend()
    edge_a = ProvenanceEdge(
        id=uuid4(),
        _from="entities/abc123",
        _to="records/def456",
        relation_type="contains",
        provenance=ProvenanceEnvelope(author_instance_id="edge-a"),
    )
    edge_b = ProvenanceEdge(
        id=uuid4(),
        _from="entities/abc123",
        _to="records/def456",
        relation_type="contains",
        provenance=ProvenanceEnvelope(author_instance_id="edge-b"),
    )

    backend.store_provenance_edge(edge_a)
    backend.store_provenance_edge(edge_b)

    edges_by_id = {edge.id: edge for edge in backend.list_provenance_edges()}
    assert len(edges_by_id) == 2
    assert set(edges_by_id) == {edge_a.id, edge_b.id}
    assert edges_by_id[edge_a.id].from_ref == "entities/abc123"
    assert edges_by_id[edge_a.id].to_ref == "records/def456"
    assert edges_by_id[edge_a.id].provenance.author_instance_id == "edge-a"
    assert edges_by_id[edge_b.id].from_ref == "entities/abc123"
    assert edges_by_id[edge_b.id].to_ref == "records/def456"
    assert edges_by_id[edge_b.id].provenance.author_instance_id == "edge-b"


def test_list_provenance_edges_returns_independent_copies():
    backend = InMemoryBackend()
    edge = ProvenanceEdge(
        id=uuid4(),
        _from="entities/abc123",
        _to="records/def456",
        relation_type="contains",
        provenance=ProvenanceEnvelope(author_instance_id="stored-copy"),
    )
    backend.store_provenance_edge(edge)

    first = backend.list_provenance_edges()[0]
    second = backend.list_provenance_edges()[0]

    assert first == second
    assert first == edge
    assert first is not edge
    assert first is not second
    assert first.provenance is not edge.provenance
    assert first.provenance is not second.provenance
    assert second.provenance.author_instance_id == "stored-copy"


def test_store_provenance_edge_immutable():
    backend = InMemoryBackend()
    edge = ProvenanceEdge(
        _from="entities/abc123",
        _to="records/def456",
        relation_type="contains",
    )
    backend.store_provenance_edge(edge)
    with pytest.raises(ImmutabilityError):
        backend.store_provenance_edge(edge)


def test_list_provenance_edges_empty():
    backend = InMemoryBackend()
    assert backend.list_provenance_edges() == []
