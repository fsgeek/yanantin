from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from uuid import uuid4

import pytest
from pydantic import ValidationError
from tiksi.provenance import SourceIdentifier

from yanantin.apacheta.models import ProvenanceEnvelope
from yanantin.apacheta.models.composition import RelationType
from yanantin.infra.config import ApachetaDBConfig, get_database
from yanantin.llika import CompositionEdge, LlikaService, Path


EDGE_COLLECTION = "llika_composition"

pytestmark = pytest.mark.integration


@dataclass(frozen=True)
class LlikaHarness:
    service: LlikaService
    vertex_collection_name: str
    vertex_collection: object
    test_run_id: str

    def create_vertex(self, label: str, **extra: object) -> str:
        key = f"{label}_{uuid4().hex}"
        self.vertex_collection.insert(
            {"_key": key, "label": label, "test_run_id": self.test_run_id, **extra}
        )
        return f"{self.vertex_collection_name}/{key}"

    def link(
        self,
        from_id: str,
        to_id: str,
        relation_type: RelationType = RelationType.COMPOSES_WITH,
    ) -> CompositionEdge:
        return self.service.link(
            from_id,
            to_id,
            relation_type,
            test_run_id=self.test_run_id,
        )


@pytest.fixture
def provenance() -> ProvenanceEnvelope:
    return ProvenanceEnvelope(
        source=SourceIdentifier(identifier=uuid4(), description="llika test"),
        author_model_family="test",
    )


@pytest.fixture
def db():
    credentials = ApachetaDBConfig().get_test_credentials()
    return get_database(
        db_name="apacheta_test",
        username=credentials["username"],
        password=credentials["password"],
    )


@pytest.fixture
def llika_harness(db, provenance: ProvenanceEnvelope) -> Iterator[LlikaHarness]:
    test_run_id = f"llika_{uuid4().hex}"
    vertex_collection_name = f"llika_test_{uuid4().hex}"
    had_edge_collection = db.has_collection(EDGE_COLLECTION)

    db.create_collection(vertex_collection_name)
    vertex_collection = db.collection(vertex_collection_name)
    service = LlikaService(db, provenance)

    try:
        yield LlikaHarness(
            service=service,
            vertex_collection_name=vertex_collection_name,
            vertex_collection=vertex_collection,
            test_run_id=test_run_id,
        )
    finally:
        if db.has_collection(EDGE_COLLECTION):
            db.aql.execute(
                """
                FOR edge IN @@edge_collection
                    FILTER edge.test_run_id == @test_run_id
                    REMOVE edge IN @@edge_collection
                """,
                bind_vars={
                    "@edge_collection": EDGE_COLLECTION,
                    "test_run_id": test_run_id,
                },
            )
            if not had_edge_collection:
                db.delete_collection(EDGE_COLLECTION)

        if db.has_collection(vertex_collection_name):
            db.delete_collection(vertex_collection_name)


def _vertex_keys(path: Path) -> list[str]:
    return [vertex["_key"] for vertex in path.vertices]


def test_linked_edge_is_traversable_by_find(llika_harness: LlikaHarness) -> None:
    source = llika_harness.create_vertex("source")
    target = llika_harness.create_vertex("target", role="round_trip_target")

    edge = llika_harness.link(source, target)
    paths = llika_harness.service.find(
        source,
        predicate=lambda vertex: vertex.get("_id") == target,
        max_depth=1,
    )

    assert len(paths) == 1
    assert paths[0].vertices[-1]["_id"] == target
    assert paths[0].edges[0]["id"] == str(edge.id)
    assert paths[0].edges[0]["_from"] == source
    assert paths[0].edges[0]["_to"] == target


def test_find_returns_path_and_stops_path_at_predicate_match(
    llika_harness: LlikaHarness,
) -> None:
    source = llika_harness.create_vertex("source")
    midpoint = llika_harness.create_vertex("midpoint", match_name="stop_here")
    beyond = llika_harness.create_vertex("beyond", match_name="too_far")
    llika_harness.link(source, midpoint)
    llika_harness.link(midpoint, beyond)

    paths = llika_harness.service.find(
        source,
        predicate=lambda vertex: vertex.get("match_name") == "stop_here",
        max_depth=2,
    )

    assert len(paths) == 1
    assert isinstance(paths[0], Path)
    assert len(paths[0].vertices) == 2
    assert len(paths[0].edges) == 1
    assert paths[0].vertices[0]["_id"] == source
    assert paths[0].vertices[-1]["_id"] == midpoint
    assert beyond not in [vertex["_id"] for vertex in paths[0].vertices]


def test_find_carries_unmentioned_intermediate_vertices_in_multi_hop_path(
    llika_harness: LlikaHarness,
) -> None:
    source = llika_harness.create_vertex("source")
    bridge_one = llika_harness.create_vertex("bridge_one")
    bridge_two = llika_harness.create_vertex("bridge_two")
    far_end = llika_harness.create_vertex("far_end", discovery_target=True)
    llika_harness.link(source, bridge_one)
    llika_harness.link(bridge_one, bridge_two)
    llika_harness.link(bridge_two, far_end)

    paths = llika_harness.service.find(
        source,
        predicate=lambda vertex: vertex.get("discovery_target") is True,
        max_depth=3,
    )

    assert len(paths) == 1
    assert [vertex["_id"] for vertex in paths[0].vertices] == [
        source,
        bridge_one,
        bridge_two,
        far_end,
    ]
    assert len(paths[0].edges) == 3
    assert _vertex_keys(paths[0]) == [
        source.split("/", 1)[1],
        bridge_one.split("/", 1)[1],
        bridge_two.split("/", 1)[1],
        far_end.split("/", 1)[1],
    ]


def test_find_observably_truncates_to_max_results(
    llika_harness: LlikaHarness,
) -> None:
    source = llika_harness.create_vertex("source")
    max_results = 3

    for index in range(max_results + 2):
        target = llika_harness.create_vertex(
            f"target_{index}",
            truncation_match=True,
        )
        llika_harness.link(source, target)

    paths = llika_harness.service.find(
        source,
        predicate=lambda vertex: vertex.get("truncation_match") is True,
        max_depth=1,
        max_results=max_results,
    )

    assert len(paths) == max_results
    assert all(path.vertices[-1].get("truncation_match") is True for path in paths)


def test_edges_are_immutable_and_service_has_no_update_or_delete_affordance(
    llika_harness: LlikaHarness,
) -> None:
    source = llika_harness.create_vertex("source")
    target = llika_harness.create_vertex("target")
    edge = llika_harness.link(source, target)

    for name in ("update", "delete"):
        assert not hasattr(LlikaService, name)
        assert not hasattr(llika_harness.service, name)
        assert not hasattr(CompositionEdge, name)
        assert not hasattr(edge, name)

    with pytest.raises((TypeError, ValidationError)):
        edge.to_ref = source
