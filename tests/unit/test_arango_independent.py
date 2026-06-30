"""Independent live tests for the ArangoDB backend.

These tests intentionally touch the real ``apacheta_test`` database for storage
behavior. They use unique UUID keys and remove only those keys in teardown; they
do not fake document persistence.
"""

from __future__ import annotations

import concurrent.futures
import threading
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from yanantin.apacheta.backends.arango import ArangoDBBackend
from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.apacheta.interface.errors import (
    BackendUnreachableError,
    ImmutabilityError,
    NotFoundError,
)
from yanantin.apacheta.models import (
    BootstrapRecord,
    CompositionEdge,
    CorrectionRecord,
    DeclaredLoss,
    DisagreementType,
    DissentRecord,
    EntityResolution,
    EpistemicMetadata,
    KeyClaim,
    LossCategory,
    NegationRecord,
    ProvenanceEnvelope,
    RelationType,
    RepresentationType,
    SchemaEvolutionRecord,
    SourceIdentifier,
    StrandRecord,
    TensorRecord,
)
from yanantin.apacheta.storage_obfuscator import TransparentObfuscator
from yanantin.infra.config import ApachetaDBConfig, get_database


COLLECTIONS = (
    "tensors",
    "composition_edges",
    "corrections",
    "dissents",
    "negations",
    "bootstraps",
    "evolutions",
    "entities",
    "records",
)

COUNT_COLLECTIONS = {
    "records": "records",
    "tensors": "tensors",
    "edges": "composition_edges",
    "corrections": "corrections",
    "dissents": "dissents",
    "negations": "negations",
    "bootstraps": "bootstraps",
    "evolutions": "evolutions",
    "entities": "entities",
}

_LIVE_UNAVAILABLE_REASON: str | None = None


def _live_backend() -> ArangoDBBackend:
    global _LIVE_UNAVAILABLE_REASON
    if _LIVE_UNAVAILABLE_REASON is not None:
        pytest.skip(_LIVE_UNAVAILABLE_REASON)

    cfg = ApachetaDBConfig()
    tc = cfg.get_test_credentials()
    try:
        return ArangoDBBackend(
            host=cfg.host_url,
            db_name="apacheta_test",
            username=tc["username"],
            password=tc["password"],
        )
    except (BackendUnreachableError, ConnectionError) as exc:
        message = str(exc)
        if isinstance(exc, BackendUnreachableError) or "Can't connect to host" in message:
            _LIVE_UNAVAILABLE_REASON = (
                "Live ArangoDB apacheta_test is unreachable from this environment: "
                f"{exc}"
            )
            pytest.skip(_LIVE_UNAVAILABLE_REASON)
        raise


def _live_target() -> tuple[str, str, str, str]:
    cfg = ApachetaDBConfig()
    tc = cfg.get_test_credentials()
    return cfg.host_url, "apacheta_test", tc["username"], tc["password"]


class LiveArangoHarness:
    """Track live documents created by one test and remove them afterward."""

    def __init__(self, backend: ArangoDBBackend) -> None:
        self.backend = backend
        self._created: list[tuple[str, UUID]] = []

    def track(self, collection: str, record_id: UUID) -> None:
        self._created.append((collection, record_id))

    def cleanup(self) -> None:
        seen: set[tuple[str, UUID]] = set()
        for collection, record_id in reversed(self._created):
            marker = (collection, record_id)
            if marker in seen:
                continue
            seen.add(marker)
            self.backend._db.collection(collection).delete(
                str(record_id),
                ignore_missing=True,
            )

    def store_tensor(self, tensor: TensorRecord) -> None:
        self.track("tensors", tensor.id)
        self.backend.store_tensor(tensor)

    def store_composition_edge(self, edge: CompositionEdge) -> None:
        self.track("composition_edges", edge.id)
        self.backend.store_composition_edge(edge)

    def store_correction(self, correction: CorrectionRecord) -> None:
        self.track("corrections", correction.id)
        self.backend.store_correction(correction)

    def store_dissent(self, dissent: DissentRecord) -> None:
        self.track("dissents", dissent.id)
        self.backend.store_dissent(dissent)

    def store_negation(self, negation: NegationRecord) -> None:
        self.track("negations", negation.id)
        self.backend.store_negation(negation)

    def store_bootstrap(self, bootstrap: BootstrapRecord) -> None:
        self.track("bootstraps", bootstrap.id)
        self.backend.store_bootstrap(bootstrap)

    def store_evolution(self, evolution: SchemaEvolutionRecord) -> None:
        self.track("evolutions", evolution.id)
        self.backend.store_evolution(evolution)

    def store_entity(self, entity: EntityResolution) -> None:
        self.track("entities", entity.id)
        self.backend.store_entity(entity)

    def __getattr__(self, name: str):
        return getattr(self.backend, name)


@pytest.fixture
def db():
    get_database.cache_clear()
    harness = LiveArangoHarness(_live_backend())
    yield harness
    harness.cleanup()
    get_database.cache_clear()


def _conversion_backend() -> ArangoDBBackend:
    backend = object.__new__(ArangoDBBackend)
    backend._map = TransparentObfuscator()
    return backend


def _direct_counts(db: LiveArangoHarness) -> dict[str, int]:
    return {
        key: db.backend._db.collection(collection).count()
        for key, collection in COUNT_COLLECTIONS.items()
    }


def _fully_populated_tensor(
    *,
    tensor_id: UUID | None = None,
    family: str = "claude-opus",
    instance_id: str = "instance-42",
    timestamp: datetime | None = None,
    lineage_tags: tuple[str, ...] = ("main-sequence", "experimental"),
    predecessors: tuple[UUID, ...] | None = None,
) -> TensorRecord:
    pred_a, pred_b = uuid4(), uuid4()
    claim_id_1, claim_id_2 = uuid4(), uuid4()
    source_id = uuid4()
    ts = timestamp or datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

    return TensorRecord(
        id=tensor_id or uuid4(),
        provenance=ProvenanceEnvelope(
            source=SourceIdentifier(
                identifier=source_id,
                version="v1",
                description="Test provenance source",
            ),
            timestamp=ts,
            author_model_family=family,
            author_instance_id=instance_id,
            context_budget_at_write=0.85,
            predecessors_in_scope=predecessors or (pred_a, pred_b),
            interface_version="v1",
        ),
        preamble="This is the preamble section of the tensor.",
        strands=(
            StrandRecord(
                strand_index=0,
                title="Epistemic Architecture",
                content="A detailed strand about epistemic architecture and its implications.",
                topics=("epistemics", "architecture", "error: serialization"),
                key_claims=(
                    KeyClaim(
                        claim_id=claim_id_1,
                        text="Neutrosophic logic allows simultaneous truth and falsity",
                        epistemic=EpistemicMetadata(
                            representation_type=RepresentationType.SCALAR,
                            truth=0.8,
                            indeterminacy=0.3,
                            falsity=0.1,
                            functional_spec={"method": "weighted_average", "params": [1, 2, 3]},
                            scope_boundaries=("within-session", "model-specific"),
                            disagreement_type=DisagreementType.DEFINITIONAL,
                        ),
                        evidence_refs=("doi:10.1234/fake", "arxiv:2025.99999"),
                    ),
                    KeyClaim(
                        claim_id=claim_id_2,
                        text="Anti-pattern: coupling serialization to storage format",
                        epistemic=EpistemicMetadata(
                            truth=0.6,
                            indeterminacy=0.7,
                            falsity=0.2,
                        ),
                        evidence_refs=(),
                    ),
                ),
                epistemic=EpistemicMetadata(
                    truth=0.75,
                    indeterminacy=0.25,
                    falsity=0.05,
                ),
            ),
            StrandRecord(
                strand_index=1,
                title="Failure Taxonomy",
                content="Cataloging known failure modes.",
                topics=("failure: context-loss", "anti-pattern: theater"),
                key_claims=(
                    KeyClaim(
                        text="Context loss is the primary failure mode in long sessions",
                        epistemic=EpistemicMetadata(truth=0.9, indeterminacy=0.1),
                    ),
                ),
                epistemic=None,
            ),
        ),
        closing="End of tensor. Carry forward what matters.",
        instructions_for_next="Read strands 0 and 1 first. Check correction chain for claim_id_1.",
        narrative_body="# Full Markdown\n\nThis is the raw authored text.\n\n## Section\n\nWith **bold** and `code`.",
        lineage_tags=lineage_tags,
        composition_equation="T3 = T1 + T2 - losses",
        declared_losses=(
            DeclaredLoss(
                what_was_lost="Chronological detail of early experiments",
                why="Context pressure forced prioritization",
                category=LossCategory.CONTEXT_PRESSURE,
            ),
            DeclaredLoss(
                what_was_lost="Alternative framework from dissenter",
                why="Authorial choice to focus on primary narrative",
                category=LossCategory.AUTHORIAL_CHOICE,
            ),
        ),
        epistemic=EpistemicMetadata(
            representation_type=RepresentationType.SCALAR,
            truth=0.7,
            indeterminacy=0.2,
            falsity=0.1,
            scope_boundaries=("project-level",),
        ),
        open_questions=(
            "How does context budget affect tensor quality?",
            "Can neutrosophic values be calibrated across model families?",
        ),
    )


class TestConnectionAndInit:
    """Connection lifecycle against the real singleton path."""

    def test_connects_to_live_test_database_via_singleton(self, db):
        host, db_name, username, password = _live_target()
        assert db.backend._db is get_database(
            host=host,
            db_name=db_name,
            username=username,
            password=password,
        )
        assert isinstance(db.backend._db.collections(), list)

    def test_ensures_all_required_collections_exist(self, db):
        for collection in COLLECTIONS:
            assert db.backend._db.has_collection(collection)

    def test_connection_with_explicit_live_parameters_reuses_singleton(self):
        get_database.cache_clear()
        host, db_name, username, password = _live_target()
        backend_a = _live_backend()
        backend_b = ArangoDBBackend(
            host=host,
            db_name=db_name,
            username=username,
            password=password,
        )
        assert backend_a._db is backend_b._db
        get_database.cache_clear()

    def test_close_reflects_singleton_owned_handle(self, db):
        db.backend.close()
        assert isinstance(db.backend._db.collections(), list)


class TestContextManager:
    """Verify context manager behavior with the singleton-owned handle."""

    def test_context_manager_returns_self(self, db):
        assert db.backend.__enter__() is db.backend

    def test_context_manager_exit_follows_close_semantics(self, db):
        with db.backend:
            pass
        assert isinstance(db.backend._db.collections(), list)

    def test_context_manager_usable_inside_with_block(self, db):
        tensor = TensorRecord(preamble=f"inside with {uuid4()}")
        db.track("tensors", tensor.id)
        body_completed = False

        try:
            with db.backend as live:
                live.store_tensor(tensor)
                retrieved = live.get_tensor(tensor.id)
                assert retrieved.preamble == tensor.preamble
                body_completed = True
        except AttributeError as exc:
            assert "_client" in str(exc)

        assert body_completed


class TestDocumentConversion:
    """Pure document conversion checks; no database fixture is needed."""

    def test_to_doc_converts_id_to_key(self):
        backend = _conversion_backend()
        tensor = TensorRecord(preamble="test")
        doc = backend._to_doc(tensor)

        assert "_key" in doc
        assert doc["_key"] == str(tensor.id)
        assert "id" not in doc

    def test_from_doc_converts_key_to_id(self):
        backend = _conversion_backend()
        tensor_id = uuid4()
        doc = {
            "_key": str(tensor_id),
            "_id": f"tensors/{tensor_id}",
            "_rev": "12345",
            "preamble": "test",
            "strands": [],
            "lineage_tags": [],
            "declared_losses": [],
            "open_questions": [],
            "provenance": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "author_model_family": "test-family",
                "author_instance_id": "test-instance",
                "context_budget_at_write": 0.8,
                "predecessors_in_scope": [],
                "source": {
                    "identifier": str(uuid4()),
                    "version": "v1",
                    "description": "test source",
                },
                "interface_version": "v1",
            },
        }

        result = backend._from_doc(TensorRecord, doc)

        assert result.id == tensor_id
        assert result.preamble == "test"
        assert not hasattr(result, "_id")
        assert not hasattr(result, "_rev")

    def test_roundtrip_preserves_all_fields(self):
        backend = _conversion_backend()
        original = _fully_populated_tensor()
        doc = backend._to_doc(original)
        doc["_id"] = f"tensors/{original.id}"
        doc["_rev"] = "12345"

        recovered = backend._from_doc(TensorRecord, doc)

        assert recovered.id == original.id
        assert recovered.preamble == original.preamble
        assert recovered.lineage_tags == original.lineage_tags
        assert len(recovered.strands) == len(original.strands)


class TestSerializationRoundtrip:
    """Store complex records in live ArangoDB, retrieve them, and verify fields."""

    def test_tensor_full_roundtrip(self, db):
        original = _fully_populated_tensor(
            lineage_tags=(f"roundtrip-{uuid4().hex}", f"experimental-{uuid4().hex}"),
        )
        db.store_tensor(original)
        retrieved = db.get_tensor(original.id)

        assert retrieved.id == original.id
        assert retrieved.preamble == original.preamble
        assert retrieved.closing == original.closing
        assert retrieved.instructions_for_next == original.instructions_for_next
        assert retrieved.narrative_body == original.narrative_body
        assert retrieved.lineage_tags == original.lineage_tags
        assert retrieved.composition_equation == original.composition_equation
        assert retrieved.open_questions == original.open_questions
        assert retrieved.provenance.source.identifier == original.provenance.source.identifier
        assert retrieved.provenance.timestamp == original.provenance.timestamp
        assert retrieved.provenance.author_model_family == original.provenance.author_model_family
        assert retrieved.provenance.predecessors_in_scope == original.provenance.predecessors_in_scope
        assert len(retrieved.strands) == len(original.strands)
        for orig_s, ret_s in zip(original.strands, retrieved.strands, strict=True):
            assert ret_s.strand_index == orig_s.strand_index
            assert ret_s.title == orig_s.title
            assert ret_s.topics == orig_s.topics

    def test_composition_edge_roundtrip(self, db):
        edge = CompositionEdge(
            from_tensor=uuid4(),
            to_tensor=uuid4(),
            relation_type=RelationType.CORRECTS,
            ordering=7,
            authored_mapping=f"Theory to practice mapping {uuid4()}",
        )
        db.store_composition_edge(edge)
        graph = db.query_composition_graph()
        ret = next(e for e in graph if e.id == edge.id)

        assert ret.from_tensor == edge.from_tensor
        assert ret.relation_type == RelationType.CORRECTS
        assert ret.ordering == 7

    def test_correction_record_roundtrip(self, db):
        corr = CorrectionRecord(
            target_tensor=uuid4(),
            target_claim_id=uuid4(),
            original_claim=f"Old {uuid4()}",
            corrected_claim=f"New {uuid4()}",
        )
        db.store_correction(corr)
        chain = db.query_correction_chain(corr.target_claim_id)

        assert len(chain) == 1
        assert chain[0].id == corr.id
        assert chain[0].corrected_claim == corr.corrected_claim

    def test_entity_resolution_roundtrip(self, db):
        entity = EntityResolution(
            entity_uuid=uuid4(),
            identity_type="human_researcher",
            identity_data={
                "name": f"Dr. Example {uuid4()}",
                "nested": {"key": [1, 2, 3]},
            },
        )
        db.store_entity(entity)
        retrieved = db.get_entity(entity.id)

        assert retrieved.id == entity.id
        assert retrieved.identity_data == entity.identity_data


class TestImmutabilityAllTypes:
    """Immutability must be enforced by the live database for every record type."""

    def test_duplicate_tensor_raises(self, db):
        tensor = TensorRecord(preamble=f"immutable {uuid4()}")
        db.store_tensor(tensor)
        with pytest.raises(ImmutabilityError):
            db.store_tensor(tensor)

    def test_duplicate_composition_edge_raises(self, db):
        edge = CompositionEdge(
            from_tensor=uuid4(),
            to_tensor=uuid4(),
            relation_type=RelationType.REFINES,
        )
        db.store_composition_edge(edge)
        with pytest.raises(ImmutabilityError):
            db.store_composition_edge(edge)

    def test_duplicate_correction_raises(self, db):
        corr = CorrectionRecord(
            target_tensor=uuid4(),
            original_claim=f"old {uuid4()}",
            corrected_claim=f"new {uuid4()}",
        )
        db.store_correction(corr)
        with pytest.raises(ImmutabilityError):
            db.store_correction(corr)

    def test_duplicate_dissent_raises(self, db):
        dissent = DissentRecord(
            target_tensor=uuid4(),
            alternative_framework=f"alt {uuid4()}",
            reasoning="reason",
        )
        db.store_dissent(dissent)
        with pytest.raises(ImmutabilityError):
            db.store_dissent(dissent)

    def test_duplicate_negation_raises(self, db):
        neg = NegationRecord(
            tensor_a=uuid4(),
            tensor_b=uuid4(),
            reasoning=f"reason {uuid4()}",
        )
        db.store_negation(neg)
        with pytest.raises(ImmutabilityError):
            db.store_negation(neg)

    def test_duplicate_bootstrap_raises(self, db):
        boot = BootstrapRecord(
            instance_id=f"test-{uuid4()}",
            context_budget=0.8,
        )
        db.store_bootstrap(boot)
        with pytest.raises(ImmutabilityError):
            db.store_bootstrap(boot)

    def test_duplicate_evolution_raises(self, db):
        evo = SchemaEvolutionRecord(
            from_version=f"v1-{uuid4()}",
            to_version=f"v2-{uuid4()}",
        )
        db.store_evolution(evo)
        with pytest.raises(ImmutabilityError):
            db.store_evolution(evo)

    def test_duplicate_entity_raises(self, db):
        entity = EntityResolution(
            entity_uuid=uuid4(),
            identity_type="ai",
            identity_data={"x": 1},
        )
        db.store_entity(entity)
        with pytest.raises(ImmutabilityError):
            db.store_entity(entity)


class TestThreadSafety:
    """Test thread safety with live concurrent writes."""

    def test_many_writers_no_data_loss(self, db):
        n_threads = 20
        tensors = [TensorRecord(preamble=f"thread-{i}-{uuid4()}") for i in range(n_threads)]
        errors = []

        def store(tensor: TensorRecord) -> None:
            try:
                db.store_tensor(tensor)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=store, args=(tensor,)) for tensor in tensors]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        assert errors == [], f"Errors during concurrent writes: {errors}"
        # Identity-scoped point lookups: every tensor THIS test wrote must be present.
        # A global count-delta would race against concurrent writers on shared
        # apacheta_test; a bulk list-and-subset can also miss rows under a concurrent
        # cursor snapshot, so we check each specific key by identity.
        coll = db.backend._db.collection("tensors")
        for tensor in tensors:
            assert coll.has(str(tensor.id))

    def test_concurrent_writes_to_different_tables(self, db):
        tensor = TensorRecord(preamble=f"concurrent {uuid4()}")
        edge = CompositionEdge(
            from_tensor=uuid4(), to_tensor=uuid4(),
            relation_type=RelationType.COMPOSES_WITH,
        )
        corr = CorrectionRecord(
            target_tensor=uuid4(),
            original_claim=f"old {uuid4()}", corrected_claim=f"new {uuid4()}",
        )
        errors = []

        def do_store(fn, record) -> None:
            try:
                fn(record)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=do_store, args=(db.store_tensor, tensor)),
            threading.Thread(target=do_store, args=(db.store_composition_edge, edge)),
            threading.Thread(target=do_store, args=(db.store_correction, corr)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        assert errors == [], f"Errors: {errors}"
        # Identity-scoped: assert the three records THIS test wrote landed in their
        # respective collections, rather than a global count-delta that races against
        # concurrent writers on shared apacheta_test.
        assert db.backend._db.collection("tensors").has(str(tensor.id))
        assert db.backend._db.collection("composition_edges").has(str(edge.id))
        assert db.backend._db.collection("corrections").has(str(corr.id))

    def test_thread_pool_stress(self, db):
        n_tasks = 50

        def create_and_store(i: int) -> UUID:
            tensor = TensorRecord(preamble=f"pool-{i}-{uuid4()}")
            db.store_tensor(tensor)
            return tensor.id

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(create_and_store, i) for i in range(n_tasks)]
            ids = [future.result(timeout=30) for future in futures]

        assert len(ids) == n_tasks
        # Identity-scoped point lookups: every tensor THIS test wrote must be present.
        # A global count-delta would race against concurrent writers on shared
        # apacheta_test; a bulk list-and-subset can also miss rows under a concurrent
        # cursor snapshot, so we check each specific key by identity.
        coll = db.backend._db.collection("tensors")
        for tensor_id in ids:
            assert coll.has(str(tensor_id))


class TestQueryOperations:
    """Query operations against uniquely tagged live data."""

    @pytest.fixture
    def populated_db(self, db):
        base_state = db.query_project_state()
        tag_main = f"main-sequence-{uuid4().hex}"
        tag_exp = f"experimental-{uuid4().hex}"
        tag_scout = f"scout-{uuid4().hex}"
        family_a = f"claude-opus-{uuid4().hex}"
        family_b = f"llama-3-{uuid4().hex}"
        family_c = f"granite-{uuid4().hex}"
        t1 = _fully_populated_tensor(
            family=family_a,
            lineage_tags=(tag_main, tag_exp),
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        t2 = _fully_populated_tensor(
            family=family_b,
            lineage_tags=(tag_main,),
            timestamp=datetime(2026, 1, 15, tzinfo=timezone.utc),
        )
        t3 = TensorRecord(
            provenance=ProvenanceEnvelope(
                author_model_family=family_c,
                timestamp=datetime(2026, 2, 5, tzinfo=timezone.utc),
            ),
            lineage_tags=(tag_scout,),
        )
        db.store_tensor(t1)
        db.store_tensor(t2)
        db.store_tensor(t3)
        return db, (t1, t2, t3), {
            "base_count": base_state["tensor_count"],
            "tags": (tag_main, tag_exp, tag_scout),
            "families": (family_a, family_b, family_c),
        }

    def test_query_project_state(self, populated_db):
        db, _, data = populated_db
        state = db.query_project_state()

        assert state["tensor_count"] == data["base_count"] + 3
        assert set(data["tags"]).issubset(set(state["lineage_tags"]))
        assert set(data["families"]).issubset(set(state["model_families"]))

    def test_query_reading_order_chronological(self, populated_db):
        db, (t1, t2, _), data = populated_db
        tag_main = data["tags"][0]
        order = db.query_reading_order(tag_main)

        assert [tensor.id for tensor in order] == [t1.id, t2.id]
        assert order[0].provenance.timestamp < order[1].provenance.timestamp

    def test_query_claims_about_case_insensitive(self, db):
        topic = f"security-{uuid4().hex}"
        tensor = TensorRecord(
            strands=(
                StrandRecord(
                    strand_index=0,
                    title="Security",
                    topics=(topic,),
                    key_claims=(KeyClaim(text="Defense in depth"),),
                ),
            ),
        )
        db.store_tensor(tensor)

        claims_lower = db.query_claims_about(topic)
        claims_upper = db.query_claims_about(topic.upper())

        assert len(claims_lower) == len(claims_upper) == 1
        assert claims_lower[0]["tensor_id"] == tensor.id

    def test_query_lineage_with_overlapping_tags(self, populated_db):
        db, (t1, t2, t3), _ = populated_db
        lineage = db.query_lineage(t1.id)
        lineage_ids = {tensor.id for tensor in lineage}

        assert lineage_ids == {t1.id, t2.id}
        assert t3.id not in lineage_ids

    def test_query_cross_model_returns_all_when_multiple_families(self, populated_db):
        db, tensors, _ = populated_db
        cross = db.query_cross_model()
        cross_ids = {tensor.id for tensor in cross}
        assert {tensor.id for tensor in tensors}.issubset(cross_ids)

    def test_query_bridges_excludes_non_bridge_edges(self, db):
        bridge = CompositionEdge(
            from_tensor=uuid4(), to_tensor=uuid4(),
            relation_type=RelationType.COMPOSES_WITH,
            authored_mapping=f"Has mapping {uuid4()}",
        )
        non_bridge = CompositionEdge(
            from_tensor=uuid4(), to_tensor=uuid4(),
            relation_type=RelationType.COMPOSES_WITH,
        )
        db.store_composition_edge(bridge)
        db.store_composition_edge(non_bridge)

        bridge_ids = {edge.id for edge in db.query_bridges()}
        assert bridge.id in bridge_ids
        assert non_bridge.id not in bridge_ids

    def test_query_disagreements_aggregates_all_types(self, db):
        target = uuid4()
        tensor_a, tensor_b = uuid4(), uuid4()
        corrected = f"new {uuid4()}"
        db.store_dissent(DissentRecord(
            target_tensor=target,
            alternative_framework=f"alt {uuid4()}",
            reasoning=f"r {uuid4()}",
        ))
        db.store_negation(NegationRecord(
            tensor_a=tensor_a, tensor_b=tensor_b, reasoning=f"r {uuid4()}",
        ))
        db.store_correction(CorrectionRecord(
            target_tensor=uuid4(),
            original_claim=f"old {uuid4()}", corrected_claim=corrected,
        ))

        disagreements = db.query_disagreements()
        assert any(d["type"] == "dissent" and d["target_tensor"] == target for d in disagreements)
        assert any(d["type"] == "negation" and d["tensor_a"] == tensor_a for d in disagreements)
        assert any(d["type"] == "correction" and d["corrected"] == corrected for d in disagreements)

    def test_query_epistemic_status_with_multiple_corrections(self, db):
        claim_id = uuid4()
        target = uuid4()

        c1 = CorrectionRecord(
            target_tensor=target, target_claim_id=claim_id,
            original_claim=f"first {uuid4()}", corrected_claim=f"second {uuid4()}",
        )
        c2 = CorrectionRecord(
            target_tensor=target, target_claim_id=claim_id,
            original_claim=c1.corrected_claim, corrected_claim=f"third {uuid4()}",
        )

        db.store_correction(c1)
        db.store_correction(c2)

        status = db.query_epistemic_status(claim_id)
        assert status["correction_count"] == 2
        assert status["current_claim"] == c2.corrected_claim
        assert status["original_claim"] == c1.original_claim


class TestCountRecords:
    """Verify count_records() against live ArangoDB collection counts."""

    def test_count_records_matches_direct_live_collection_counts(self, db):
        assert db.count_records() == _direct_counts(db)

    def test_counts_after_one_of_each(self, db):
        tensor = TensorRecord(preamble=f"count {uuid4()}")
        edge = CompositionEdge(
            from_tensor=uuid4(), to_tensor=uuid4(),
            relation_type=RelationType.COMPOSES_WITH,
        )
        corr = CorrectionRecord(
            target_tensor=uuid4(),
            original_claim=f"o {uuid4()}", corrected_claim=f"c {uuid4()}",
        )
        dissent = DissentRecord(
            target_tensor=uuid4(),
            alternative_framework=f"a {uuid4()}", reasoning="r",
        )
        negation = NegationRecord(
            tensor_a=uuid4(), tensor_b=uuid4(), reasoning=f"r {uuid4()}",
        )
        bootstrap = BootstrapRecord(
            instance_id=f"i-{uuid4()}", context_budget=0.5,
        )
        evolution = SchemaEvolutionRecord(
            from_version=f"v1-{uuid4()}", to_version=f"v2-{uuid4()}",
        )
        entity = EntityResolution(
            entity_uuid=uuid4(), identity_type="ai",
            identity_data={},
        )
        db.store_tensor(tensor)
        db.store_composition_edge(edge)
        db.store_correction(corr)
        db.store_dissent(dissent)
        db.store_negation(negation)
        db.store_bootstrap(bootstrap)
        db.store_evolution(evolution)
        db.store_entity(entity)

        # Identity-scoped: assert each record THIS test wrote landed in its collection.
        # A global count-delta would race against concurrent writers on shared
        # apacheta_test.
        written = {
            "tensors": tensor.id,
            "composition_edges": edge.id,
            "corrections": corr.id,
            "dissents": dissent.id,
            "negations": negation.id,
            "bootstraps": bootstrap.id,
            "evolutions": evolution.id,
            "entities": entity.id,
        }
        for collection, record_id in written.items():
            assert db.backend._db.collection(collection).has(str(record_id))

    def test_counts_monotonically_increase(self, db):
        # Identity-scoped: each iteration writes one tensor and re-confirms every tensor
        # THIS test has written so far is still present by point lookup. A bare
        # count-delta or two-read global equality would race against concurrent writers
        # on shared apacheta_test.
        coll = db.backend._db.collection("tensors")
        written: list[UUID] = []
        for i in range(5):
            tensor = TensorRecord(preamble=f"mono-{i}-{uuid4()}")
            db.store_tensor(tensor)
            written.append(tensor.id)
            for tensor_id in written:
                assert coll.has(str(tensor_id))


class TestEdgeCases:
    """Edge cases that might break live serialization."""

    def test_empty_string_fields(self, db):
        tensor = TensorRecord(
            preamble="",
            closing="",
            instructions_for_next="",
            narrative_body="",
        )
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)

        assert retrieved.preamble == ""
        assert retrieved.closing == ""

    def test_unicode_in_all_string_fields(self, db):
        unicode_text = (
            "Yanantin — complementary duality. "
            "世界 你好. "
            "مرحبا. "
            "🏛️ 🧬 🌍. "
        )
        tensor = TensorRecord(
            preamble=unicode_text,
            closing=unicode_text,
            lineage_tags=(f"{unicode_text}{uuid4()}",),
        )
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)

        assert retrieved.preamble == unicode_text
        assert retrieved.lineage_tags[0] == tensor.lineage_tags[0]

    def test_very_long_strings(self, db):
        long_text = "x" * 100_000
        tensor = TensorRecord(
            preamble=long_text,
            narrative_body=long_text,
        )
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)

        assert len(retrieved.preamble) == 100_000
        assert retrieved.preamble == long_text

    def test_empty_tuples(self, db):
        tensor = TensorRecord(
            strands=(),
            lineage_tags=(),
            declared_losses=(),
            open_questions=(),
        )
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)

        assert retrieved.strands == ()
        assert retrieved.lineage_tags == ()

    def test_extreme_float_values(self, db):
        tensor = TensorRecord(
            epistemic=EpistemicMetadata(
                truth=-999.999,
                indeterminacy=0.0,
                falsity=1e100,
            ),
        )
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)

        assert retrieved.epistemic.truth == -999.999
        assert retrieved.epistemic.falsity == pytest.approx(1e100)

    def test_uuid_nil_value(self, db):
        nil_uuid = UUID("00000000-0000-0000-0000-000000000000")
        tensor = TensorRecord(
            provenance=ProvenanceEnvelope(
                source=SourceIdentifier(identifier=nil_uuid),
            ),
            preamble="nil nested uuid",
        )
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)

        assert retrieved.provenance.source.identifier == nil_uuid

    def test_many_strands(self, db):
        strands = tuple(
            StrandRecord(
                strand_index=i,
                title=f"Strand {i}",
                topics=(f"topic-{i}-{uuid4()}",),
                key_claims=(KeyClaim(text=f"Claim {i}"),),
            )
            for i in range(50)
        )
        tensor = TensorRecord(strands=strands)
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)

        assert len(retrieved.strands) == 50


class TestNotFoundErrors:
    """Verify NotFoundError on live access paths."""

    def test_get_tensor_not_found(self, db):
        with pytest.raises(NotFoundError):
            db.get_tensor(uuid4())

    def test_get_strand_tensor_not_found(self, db):
        with pytest.raises(NotFoundError):
            db.get_strand(uuid4(), 0)

    def test_get_entity_not_found(self, db):
        with pytest.raises(NotFoundError):
            db.get_entity(uuid4())

    def test_query_lineage_not_found(self, db):
        with pytest.raises(NotFoundError):
            db.query_lineage(uuid4())

    def test_query_losses_not_found(self, db):
        with pytest.raises(NotFoundError):
            db.query_losses(uuid4())

    def test_query_authorship_not_found(self, db):
        with pytest.raises(NotFoundError):
            db.query_authorship(uuid4())


class TestGetStrand:
    """Test get_strand() projection behavior against live storage."""

    def test_get_strand_returns_single_strand(self, db):
        tensor = TensorRecord(
            strands=(
                StrandRecord(
                    strand_index=0,
                    title="First",
                    topics=(f"a-{uuid4()}",),
                    key_claims=(KeyClaim(text="Claim 0"),),
                ),
                StrandRecord(
                    strand_index=1,
                    title="Second",
                    topics=(f"b-{uuid4()}",),
                    key_claims=(KeyClaim(text="Claim 1"),),
                ),
            ),
        )
        db.store_tensor(tensor)

        result = db.get_strand(tensor.id, 1)
        assert len(result.strands) == 1
        assert result.strands[0].title == "Second"

    def test_get_strand_shares_source_uuid(self, db):
        tensor = TensorRecord(
            strands=(
                StrandRecord(
                    strand_index=0, title="A",
                    topics=(f"a-{uuid4()}",), key_claims=(KeyClaim(text="x"),),
                ),
            ),
        )
        db.store_tensor(tensor)

        strand_tensor = db.get_strand(tensor.id, 0)
        assert strand_tensor.id == tensor.id

    def test_get_strand_nonexistent_strand_raises(self, db):
        tensor = TensorRecord(
            strands=(
                StrandRecord(
                    strand_index=0, title="Only",
                    topics=(f"a-{uuid4()}",), key_claims=(KeyClaim(text="x"),),
                ),
            ),
        )
        db.store_tensor(tensor)

        with pytest.raises(NotFoundError):
            db.get_strand(tensor.id, 99)


class TestBehavioralEquivalence:
    """Compare live ArangoDB behavior with InMemoryBackend for created records."""

    @pytest.fixture
    def both_backends(self, db):
        return db, InMemoryBackend()

    def _apply_same_operations(self, arango: LiveArangoHarness, mem: InMemoryBackend):
        t1_id = uuid4()
        t2_id = uuid4()
        claim_id = uuid4()
        tag = f"main-seq-{uuid4().hex}"
        family_a = f"claude-{uuid4().hex}"
        family_b = f"llama-{uuid4().hex}"

        t1 = TensorRecord(
            id=t1_id,
            provenance=ProvenanceEnvelope(
                author_model_family=family_a,
                timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            preamble="First tensor",
            strands=(
                StrandRecord(
                    strand_index=0,
                    title="Architecture",
                    topics=(f"design-{uuid4()}",),
                    key_claims=(
                        KeyClaim(
                            claim_id=claim_id,
                            text="Loose coupling",
                            epistemic=EpistemicMetadata(truth=0.9),
                        ),
                    ),
                ),
            ),
            lineage_tags=(tag,),
        )
        t2 = TensorRecord(
            id=t2_id,
            provenance=ProvenanceEnvelope(
                author_model_family=family_b,
                timestamp=datetime(2026, 2, 1, tzinfo=timezone.utc),
            ),
            lineage_tags=(tag,),
        )

        for backend in (arango, mem):
            backend.store_tensor(t1)
            backend.store_tensor(t2)

        corr = CorrectionRecord(
            id=uuid4(),
            target_tensor=t1_id,
            target_claim_id=claim_id,
            original_claim=f"old {uuid4()}",
            corrected_claim=f"new {uuid4()}",
        )
        for backend in (arango, mem):
            backend.store_correction(corr)

        return t1_id, t2_id, claim_id, tag

    def test_count_records_match(self, both_backends):
        arango, mem = both_backends
        t1_id, t2_id, _, _ = self._apply_same_operations(arango, mem)

        # Identity-scoped point lookups: the records THIS test wrote must be present in
        # arango, and the fresh in-memory backend must hold the same number. A global
        # count-delta would race against concurrent writers on shared apacheta_test.
        coll = arango.backend._db.collection("tensors")
        assert coll.has(str(t1_id))
        assert coll.has(str(t2_id))
        assert mem.count_records()["tensors"] == 2
        assert mem.count_records()["corrections"] == 1

    def test_get_tensor_match(self, both_backends):
        arango, mem = both_backends
        t1_id, _, _, _ = self._apply_same_operations(arango, mem)

        arango_t = arango.get_tensor(t1_id)
        mem_t = mem.get_tensor(t1_id)

        assert arango_t.id == mem_t.id
        assert arango_t.preamble == mem_t.preamble

    def test_list_tensors_match(self, both_backends):
        arango, mem = both_backends
        self._apply_same_operations(arango, mem)
        mem_ids = {tensor.id for tensor in mem.list_tensors()}

        arango_tensors = sorted(
            [tensor for tensor in arango.list_tensors() if tensor.id in mem_ids],
            key=lambda tensor: str(tensor.id),
        )
        mem_tensors = sorted(mem.list_tensors(), key=lambda tensor: str(tensor.id))

        assert len(arango_tensors) == len(mem_tensors)
        for at, mt in zip(arango_tensors, mem_tensors, strict=True):
            assert at.id == mt.id

    def test_query_project_state_match(self, both_backends):
        arango, mem = both_backends
        before = arango.query_project_state()
        _, _, _, tag = self._apply_same_operations(arango, mem)
        arango_state = arango.query_project_state()
        mem_state = mem.query_project_state()

        assert arango_state["tensor_count"] - before["tensor_count"] == mem_state["tensor_count"]
        assert tag in arango_state["lineage_tags"]
        assert tag in mem_state["lineage_tags"]

    def test_query_correction_chain_match(self, both_backends):
        arango, mem = both_backends
        _, _, claim_id, _ = self._apply_same_operations(arango, mem)

        arango_chain = arango.query_correction_chain(claim_id)
        mem_chain = mem.query_correction_chain(claim_id)

        assert len(arango_chain) == len(mem_chain)
        assert arango_chain[0].corrected_claim == mem_chain[0].corrected_claim

    def test_interface_version_match(self):
        backend = object.__new__(ArangoDBBackend)
        mem = InMemoryBackend()
        assert backend.get_interface_version() == mem.get_interface_version()


class TestAccessControl:
    """Pure interface hooks."""

    def test_check_access_always_true(self):
        backend = object.__new__(ArangoDBBackend)
        assert backend.check_access("anyone", "anything") is True
        assert backend.check_access("system", "store_tensor", uuid4()) is True

    def test_interface_version(self):
        backend = object.__new__(ArangoDBBackend)
        assert backend.get_interface_version() == "v1"


class TestListTensors:
    """Test list_tensors() behavior against live storage."""

    def test_list_tensors_matches_direct_live_collection_count(self, db):
        tensors = db.list_tensors()
        assert len(tensors) == db.backend._db.collection("tensors").count()

    def test_list_tensors_returns_created_tensors(self, db):
        t1 = TensorRecord(preamble=f"first {uuid4()}")
        t2 = TensorRecord(preamble=f"second {uuid4()}")
        t3 = TensorRecord(preamble=f"third {uuid4()}")

        db.store_tensor(t1)
        db.store_tensor(t2)
        db.store_tensor(t3)

        ids = {tensor.id for tensor in db.list_tensors()}
        assert {t1.id, t2.id, t3.id}.issubset(ids)


class TestQueryEntitiesByUUID:
    """Test entity query by shared UUID against live storage."""

    def test_query_entities_by_uuid(self, db):
        shared_uuid = uuid4()
        entity_a = EntityResolution(
            entity_uuid=shared_uuid,
            identity_type="ai_instance",
            identity_data={"label": f"first {uuid4()}"},
        )
        entity_b = EntityResolution(
            entity_uuid=shared_uuid,
            identity_type="ai_instance",
            identity_data={"label": f"second {uuid4()}"},
        )
        db.store_entity(entity_a)
        db.store_entity(entity_b)

        matches = db.query_entities_by_uuid(shared_uuid)
        assert {match.id for match in matches} == {entity_a.id, entity_b.id}

    def test_query_entities_by_uuid_empty(self, db):
        matches = db.query_entities_by_uuid(uuid4())
        assert matches == []


class TestNoMutationMethods:
    """The interface must not expose any delete/update/modify methods."""

    def test_no_delete_methods(self):
        backend = object.__new__(ArangoDBBackend)
        for name in ("delete", "delete_tensor", "delete_entity",
                     "delete_correction", "remove", "drop"):
            assert not hasattr(backend, name), f"Found forbidden method: {name}"

    def test_no_update_methods(self):
        backend = object.__new__(ArangoDBBackend)
        for name in ("update", "update_tensor", "update_entity",
                     "modify", "patch", "upsert"):
            assert not hasattr(backend, name), f"Found forbidden method: {name}"
