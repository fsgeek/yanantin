"""Tests for ProvenanceEdge model."""
import pytest
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
