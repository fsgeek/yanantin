"""Integration contract tests for LlikaService.

These tests intentionally use the live apacheta_test database. A mock cannot
prove that an edge written by link() is traversable by walk().
"""

from __future__ import annotations

import inspect
import os
from dataclasses import FrozenInstanceError, dataclass
from uuid import uuid4

import pytest
from tiksi.provenance import SourceIdentifier

from yanantin.apacheta.backends.arango import ArangoDBBackend
from yanantin.apacheta.interface.errors import BackendUnreachableError
from yanantin.apacheta.models.base import ApachetaBaseModel
from yanantin.apacheta.models import ProvenanceEnvelope
from yanantin.apacheta.models.composition import RelationType
from yanantin.infra.config import ApachetaDBConfig
from yanantin.llika import EdgeResult, LlikaService, PathResult, PathStep


pytestmark = pytest.mark.integration

EDGE_COLLECTION = "llika_composition"
ENVELOPE_FIELD_NAMES = {
    "_id",
    "_key",
    "_rev",
    "_from",
    "_to",
    "provenance",
    "lineage_tags",
}


@dataclass
class LiveGraph:
    service: LlikaService
    backend: ArangoDBBackend
    collection_name: str
    tag: str
    record_ids: list[str]

    @property
    def db(self):
        return self.backend._db

    def vertex(self, label: str, **fields: object) -> str:
        doc = {
            "_key": f"{label}_{uuid4().hex}",
            "label": label,
            "test_tag": self.tag,
            **fields,
        }
        inserted = self.db.collection(self.collection_name).insert(doc)
        return inserted["_id"]


def _provenance() -> ProvenanceEnvelope:
    return ProvenanceEnvelope(
        source=SourceIdentifier(identifier=uuid4(), description="llika test"),
        author_model_family="test",
    )


def _live_arango_backend() -> ArangoDBBackend:
    if os.environ.get("APACHETA_SKIP_ARANGO"):
        pytest.skip("APACHETA_SKIP_ARANGO is set")

    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    try:
        return ArangoDBBackend(
            host=cfg.host_url,
            db_name="apacheta_test",
            username=creds["username"],
            password=creds["password"],
        )
    except (BackendUnreachableError, ConnectionError) as exc:
        pytest.skip(
            "Live ArangoDB apacheta_test is unreachable from this environment: "
            f"{exc}"
        )


@pytest.fixture(scope="session")
def live_arango_available() -> None:
    backend = _live_arango_backend()
    backend.close()


@pytest.fixture
def live_graph(live_arango_available: None) -> LiveGraph:
    backend = _live_arango_backend()
    db = backend._db
    collection_name = f"llika_it_{uuid4().hex}"
    tag = f"llika_it_{uuid4().hex}"
    db.create_collection(collection_name)
    record_ids: list[str] = []

    try:
        yield LiveGraph(
            service=LlikaService(backend, _provenance()),
            backend=backend,
            collection_name=collection_name,
            tag=tag,
            record_ids=record_ids,
        )
    finally:
        if db.has_collection(EDGE_COLLECTION):
            db.aql.execute(
                f"""
                FOR e IN {EDGE_COLLECTION}
                    FILTER e.test_tag == @tag
                    REMOVE e IN {EDGE_COLLECTION}
                """,
                bind_vars={"tag": tag},
            )
        if db.has_collection("records"):
            records = db.collection("records")
            for record_id in record_ids:
                records.delete(record_id, ignore_missing=True)
        if db.has_collection(collection_name):
            db.delete_collection(collection_name)
        backend.close()


def _far_ends(paths: list[PathResult]) -> set[str]:
    return {path.steps[-1].record_id for path in paths if path.steps}


def test_constructor_takes_graph_backend_and_holds_no_db_handle(
    live_graph: LiveGraph,
) -> None:
    params = list(inspect.signature(LlikaService.__init__).parameters)
    start = live_graph.vertex("tenant_a")
    target = live_graph.vertex("tenant_b")
    live_graph.service.link(
        start,
        target,
        RelationType.COMPOSES_WITH,
        test_tag=live_graph.tag,
    )

    assert params == ["self", "backend", "provenance"]
    assert isinstance(live_graph.service, LlikaService)
    assert live_graph.service._backend is live_graph.backend
    assert not hasattr(live_graph.service, "_db")
    assert not hasattr(live_graph.service, "db")
    assert live_graph.db.has_collection(EDGE_COLLECTION)
    assert target in _far_ends(live_graph.service.walk(start, "forward", depth=1))


def test_link_round_trip_edge_is_traversable_by_walk(live_graph: LiveGraph) -> None:
    start = live_graph.vertex("roundtrip_a")
    target = live_graph.vertex("roundtrip_b")

    edge = live_graph.service.link(
        start,
        target,
        RelationType.COMPOSES_WITH,
        test_tag=live_graph.tag,
    )
    paths = live_graph.service.walk(start, "forward", depth=1)

    assert isinstance(edge, EdgeResult)
    assert not isinstance(edge, dict)
    assert edge.from_id == start
    assert edge.to_id == target
    assert edge.relation_type == RelationType.COMPOSES_WITH.value
    assert isinstance(edge.created_at, str)
    assert target in _far_ends(paths)
    assert target in _far_ends(live_graph.backend.walk(start, "forward", depth=1))


def test_get_delegates_to_backend_get_record(live_graph: LiveGraph) -> None:
    record_id = uuid4()
    live_graph.record_ids.append(str(record_id))
    record = ApachetaBaseModel(
        provenance=_provenance(),
        lineage_tags=(live_graph.tag,),
        llika_get_probe=f"value_{uuid4().hex}",
    )
    live_graph.backend.store_record(record_id, record)

    fetched = live_graph.service.get(record_id)

    assert fetched == live_graph.backend.get_record(record_id)
    assert getattr(fetched, "llika_get_probe") == record.llika_get_probe


def test_walk_returns_serializable_shape_without_arango_envelope_or_values(
    live_graph: LiveGraph,
) -> None:
    start = live_graph.vertex("shape_a")
    secret_value = f"secret_{uuid4().hex}"
    target = live_graph.vertex(
        "shape_b",
        content=secret_value,
        rank=1,
        provenance={"source": "should not leak"},
        lineage_tags=["should not leak"],
    )
    live_graph.service.link(
        start,
        target,
        RelationType.COMPOSES_WITH,
        test_tag=live_graph.tag,
    )

    paths = live_graph.service.walk(start, "forward", depth=1)
    path = next(path for path in paths if path.steps[-1].record_id == target)
    step = path.steps[-1]

    assert isinstance(path, PathResult)
    assert isinstance(step, PathStep)
    assert path.start_id == start
    assert isinstance(path.steps, tuple)
    assert isinstance(step.record_id, str)
    assert "/" in step.record_id
    assert step.relation_type == RelationType.COMPOSES_WITH.value
    assert isinstance(step.field_names, tuple)
    assert all(isinstance(name, str) for name in step.field_names)
    assert ENVELOPE_FIELD_NAMES.isdisjoint(step.field_names)
    assert "content" in step.field_names
    assert secret_value not in step.field_names


def test_walk_depth_three_includes_intermediate_connective_tissue(
    live_graph: LiveGraph,
) -> None:
    a = live_graph.vertex("chain_a")
    b = live_graph.vertex("chain_b")
    c = live_graph.vertex("chain_c")
    d = live_graph.vertex("chain_d")
    for left, right in [(a, b), (b, c), (c, d)]:
        live_graph.service.link(
            left,
            right,
            RelationType.COMPOSES_WITH,
            test_tag=live_graph.tag,
        )

    paths = live_graph.service.walk(a, "forward", depth=3)

    assert any([step.record_id for step in path.steps] == [b, c, d] for path in paths)


def test_direction_controls_forward_backward_and_both_traversal(
    live_graph: LiveGraph,
) -> None:
    upstream = live_graph.vertex("direction_upstream")
    middle = live_graph.vertex("direction_middle")
    downstream = live_graph.vertex("direction_downstream")
    live_graph.service.link(
        upstream,
        middle,
        RelationType.COMPOSES_WITH,
        test_tag=live_graph.tag,
    )
    live_graph.service.link(
        middle,
        downstream,
        RelationType.COMPOSES_WITH,
        test_tag=live_graph.tag,
    )

    forward = live_graph.service.walk(middle, "forward", depth=1)
    backward = live_graph.service.walk(middle, "backward", depth=1)
    both = live_graph.service.walk(middle, "both", depth=1)

    assert _far_ends(forward) == {downstream}
    assert _far_ends(backward) == {upstream}
    assert _far_ends(forward) != _far_ends(backward)
    assert _far_ends(both) == {upstream, downstream}


def test_relation_filter_uses_lowercase_relation_values(
    live_graph: LiveGraph,
) -> None:
    start = live_graph.vertex("filter_start")
    composes_target = live_graph.vertex("filter_composes")
    bridges_target = live_graph.vertex("filter_bridges")
    live_graph.service.link(
        start,
        composes_target,
        RelationType.COMPOSES_WITH,
        test_tag=live_graph.tag,
    )
    live_graph.service.link(
        start,
        bridges_target,
        RelationType.BRIDGES,
        test_tag=live_graph.tag,
    )

    paths = live_graph.service.walk(
        start,
        "forward",
        depth=1,
        relation_types=[RelationType.COMPOSES_WITH.value],
    )

    assert _far_ends(paths) == {composes_target}
    assert all(
        step.relation_type == RelationType.COMPOSES_WITH.value
        for path in paths
        for step in path.steps
    )
    assert bridges_target not in _far_ends(paths)


def test_walk_caps_results_at_max_results_when_more_matches_exist(
    live_graph: LiveGraph,
) -> None:
    start = live_graph.vertex("truncate_start")
    for index in range(8):
        target = live_graph.vertex(f"truncate_{index}")
        live_graph.service.link(
            start,
            target,
            RelationType.COMPOSES_WITH,
            test_tag=live_graph.tag,
        )

    paths = live_graph.service.walk(start, "forward", depth=1, max_results=5)

    assert len(paths) == 5


def test_neighbors_are_depth_one_only(live_graph: LiveGraph) -> None:
    start = live_graph.vertex("neighbors_a")
    immediate = live_graph.vertex("neighbors_b")
    two_hops_away = live_graph.vertex("neighbors_c")
    live_graph.service.link(
        start,
        immediate,
        RelationType.COMPOSES_WITH,
        test_tag=live_graph.tag,
    )
    live_graph.service.link(
        immediate,
        two_hops_away,
        RelationType.COMPOSES_WITH,
        test_tag=live_graph.tag,
    )

    neighbors = live_graph.service.neighbors(start, "forward")

    assert all(len(path.steps) == 1 for path in neighbors)
    assert immediate in _far_ends(neighbors)
    assert two_hops_away not in _far_ends(neighbors)


def test_no_find_or_mutation_surface_and_results_are_frozen(
    live_graph: LiveGraph,
) -> None:
    service = live_graph.service
    edge = EdgeResult(
        edge_id="edge-id",
        from_id="vertices/a",
        to_id="vertices/b",
        relation_type=RelationType.COMPOSES_WITH.value,
        created_at="2026-06-01T00:00:00+00:00",
    )
    step = PathStep(
        record_id="vertices/b",
        relation_type=RelationType.COMPOSES_WITH.value,
        field_names=("label",),
    )
    path = PathResult(start_id="vertices/a", steps=(step,))

    assert not hasattr(service, "find")
    assert not hasattr(service, "update")
    assert not hasattr(service, "delete")
    with pytest.raises(FrozenInstanceError):
        edge.to_id = "vertices/c"
    with pytest.raises(FrozenInstanceError):
        step.record_id = "vertices/c"
    with pytest.raises(FrozenInstanceError):
        path.start_id = "vertices/c"
