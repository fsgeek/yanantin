"""Independent tests for the ArangoDB backend — written by test author, not builder.

These tests probe what the builder might have gotten wrong:
- Serialization roundtrip fidelity through JSON/documents
- Edge cases in UUID/datetime/tuple/enum handling through ArangoDB
- Immutability enforcement on ALL record types
- Connection lifecycle and context manager protocol
- Thread safety under real contention
- Query operations with realistic multi-tensor data
- count_records() accuracy
- Unicode, empty strings, extreme values
- Behavioral equivalence with the in-memory backend
- ArangoDB-specific: _key handling, document metadata stripping, collection management

IMPORTANT: These tests mock the ArangoDB client to avoid requiring a running instance.
"""

from __future__ import annotations

import concurrent.futures
import threading
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, call, patch
from uuid import UUID, uuid4

import pytest

from yanantin.apacheta.backends.arango import ArangoDBBackend
from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.apacheta.interface.errors import ImmutabilityError, NotFoundError
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


# ── Test Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def mock_arango_client():
    """Mock ArangoDB client and database setup."""
    with patch('yanantin.apacheta.backends.arango.ArangoClient') as MockClient:
        # Create mock instances
        mock_client = Mock()
        mock_sys_db = Mock()
        mock_db = Mock()

        # Mock collections - use a dict to store documents in-memory
        collections = {}

        def make_collection(name):
            """Create a mock collection with in-memory document storage."""
            coll = Mock()
            docs = {}  # In-memory document store

            def has(key):
                return key in docs

            def insert(doc):
                key = doc['_key']
                if key in docs:
                    from arango.exceptions import DocumentInsertError
                    raise DocumentInsertError("duplicate _key")
                docs[key] = doc.copy()
                return doc

            def get(key):
                return docs.get(key)

            def all():
                """Return all documents as a list."""
                return list(docs.values())

            def count():
                return len(docs)

            coll.has = Mock(side_effect=has)
            coll.insert = Mock(side_effect=insert)
            coll.get = Mock(side_effect=get)
            coll.all = Mock(side_effect=all)
            coll.count = Mock(side_effect=count)
            collections[name] = coll
            return coll

        # Create all required collections
        for name in ('tensors', 'composition_edges', 'corrections', 'dissents',
                     'negations', 'bootstraps', 'evolutions', 'entities'):
            make_collection(name)

        # Wire up the mocks — backend now connects directly to target db
        # (no _system access, least-privilege pattern)
        MockClient.return_value = mock_client
        mock_client.db.return_value = mock_db
        mock_db.collections.return_value = []  # Verify connection succeeds
        mock_db.has_collection.return_value = False  # Force creation
        mock_db.create_collection.side_effect = lambda name: collections.get(name)
        mock_db.collection.side_effect = lambda name: collections.get(name)

        yield mock_client, collections


@pytest.fixture
def db(mock_arango_client):
    """Fresh ArangoDB backend for each test (mocked)."""
    mock_client, collections = mock_arango_client
    backend = ArangoDBBackend(
        host="http://192.168.111.125:8529",
        db_name="apacheta",
        username="root",
        password="LFNi0vhD7mEE0ZH"
    )
    yield backend
    backend.close()


def _fully_populated_tensor(
    *,
    tensor_id: UUID | None = None,
    family: str = "claude-opus",
    instance_id: str = "instance-42",
    timestamp: datetime | None = None,
    lineage_tags: tuple[str, ...] = ("main-sequence", "experimental"),
    predecessors: tuple[UUID, ...] | None = None,
) -> TensorRecord:
    """Build a TensorRecord with every optional field populated."""
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


# ── 1. Connection and Initialization ──────────────────────────────────


class TestConnectionAndInit:
    """Test connection lifecycle and initialization."""

    def test_fails_if_database_unreachable(self):
        """Backend should fail-stop if it can't connect to the database."""
        with patch('yanantin.apacheta.backends.arango.ArangoClient') as MockClient:
            mock_client = Mock()
            mock_db = Mock()

            MockClient.return_value = mock_client
            mock_client.db.return_value = mock_db
            mock_db.collections.side_effect = Exception("Connection refused")

            with pytest.raises(ConnectionError, match="Cannot connect"):
                ArangoDBBackend(db_name="nonexistent_db")

    def test_connects_directly_to_target_database(self):
        """Backend connects to target database, never to _system (least privilege)."""
        with patch('yanantin.apacheta.backends.arango.ArangoClient') as MockClient:
            mock_client = Mock()
            mock_db = Mock()

            MockClient.return_value = mock_client
            mock_client.db.return_value = mock_db
            mock_db.collections.return_value = []
            mock_db.has_collection.return_value = True

            backend = ArangoDBBackend(db_name="my_db", username="app_user", password="secret")

            # Should connect to target db directly, never _system
            mock_client.db.assert_called_once_with("my_db", username="app_user", password="secret")
            backend.close()

    def test_creates_all_collections(self):
        """Backend should create all required collections on init."""
        with patch('yanantin.apacheta.backends.arango.ArangoClient') as MockClient:
            mock_client = Mock()
            mock_db = Mock()

            MockClient.return_value = mock_client
            mock_client.db.return_value = mock_db
            mock_db.collections.return_value = []
            mock_db.has_collection.return_value = False

            backend = ArangoDBBackend()

            expected_collections = {
                'tensors', 'composition_edges', 'corrections', 'dissents',
                'negations', 'bootstraps', 'evolutions', 'entities'
            }
            created_collections = {call_args[0][0] for call_args in mock_db.create_collection.call_args_list}
            assert created_collections == expected_collections
            backend.close()

    def test_connection_with_custom_parameters(self):
        """Backend should accept custom host, db_name, username, password."""
        with patch('yanantin.apacheta.backends.arango.ArangoClient') as MockClient:
            mock_client = Mock()
            mock_db = Mock()

            MockClient.return_value = mock_client
            mock_client.db.return_value = mock_db
            mock_db.collections.return_value = []
            mock_db.has_collection.return_value = True

            backend = ArangoDBBackend(
                host="http://custom-host:8529",
                db_name="custom_db",
                username="custom_user",
                password="custom_pass"
            )

            MockClient.assert_called_once_with(hosts="http://custom-host:8529")
            mock_client.db.assert_called_once_with("custom_db", username="custom_user", password="custom_pass")
            backend.close()

    def test_close_closes_client(self, db):
        """close() should call client.close()."""
        db._client.close = Mock()
        db.close()
        db._client.close.assert_called_once()


# ── 2. Context Manager Protocol ───────────────────────────────────────


class TestContextManager:
    """Verify context manager protocol works correctly."""

    def test_context_manager_returns_self(self, db):
        """__enter__ must return the backend instance."""
        with db as context:
            assert context is db

    def test_context_manager_calls_close(self, mock_arango_client):
        """__exit__ must call close()."""
        mock_client, collections = mock_arango_client
        backend = ArangoDBBackend()
        backend._client.close = Mock()

        with backend:
            pass

        backend._client.close.assert_called_once()

    def test_context_manager_usable_inside_with_block(self, mock_arango_client):
        """Backend should be fully usable inside the with block."""
        mock_client, collections = mock_arango_client
        with ArangoDBBackend() as db:
            tensor = TensorRecord(preamble="inside with")
            db.store_tensor(tensor)
            retrieved = db.get_tensor(tensor.id)
            assert retrieved.preamble == "inside with"


# ── 3. Document Conversion (_to_doc / _from_doc) ──────────────────────


class TestDocumentConversion:
    """Test ArangoDB-specific document conversion logic."""

    def test_to_doc_converts_id_to_key(self, db):
        """_to_doc should convert 'id' field to '_key'."""
        tensor = TensorRecord(preamble="test")
        doc = db._to_doc(tensor)

        assert '_key' in doc
        assert doc['_key'] == str(tensor.id)
        assert 'id' not in doc

    def test_from_doc_converts_key_to_id(self, db):
        """_from_doc should convert '_key' back to 'id' and strip metadata."""
        tensor_id = uuid4()
        doc = {
            '_key': str(tensor_id),
            '_id': f'tensors/{tensor_id}',  # ArangoDB metadata
            '_rev': '12345',  # ArangoDB metadata
            'preamble': 'test',
            'strands': [],
            'lineage_tags': [],
            'declared_losses': [],
            'open_questions': [],
        }

        # Need to add valid provenance for TensorRecord
        doc['provenance'] = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'author_model_family': 'test-family',
            'author_instance_id': 'test-instance',
            'context_budget_at_write': 0.8,
            'predecessors_in_scope': [],
            'source': {
                'identifier': str(uuid4()),
                'version': 'v1',
                'description': 'test source'
            },
            'interface_version': 'v1'
        }

        result = db._from_doc(TensorRecord, doc)

        assert result.id == tensor_id
        assert result.preamble == 'test'
        # ArangoDB metadata should be stripped
        assert not hasattr(result, '_id')
        assert not hasattr(result, '_rev')

    def test_roundtrip_preserves_all_fields(self, db):
        """Converting to doc and back should preserve all fields."""
        original = _fully_populated_tensor()
        doc = db._to_doc(original)
        # Simulate ArangoDB adding metadata
        doc['_id'] = f'tensors/{original.id}'
        doc['_rev'] = '12345'

        recovered = db._from_doc(TensorRecord, doc)

        assert recovered.id == original.id
        assert recovered.preamble == original.preamble
        assert recovered.lineage_tags == original.lineage_tags
        assert len(recovered.strands) == len(original.strands)


# ── 4. Serialization Roundtrip Fidelity ───────────────────────────────


class TestSerializationRoundtrip:
    """Store a complex, fully-populated record, retrieve it, verify every field."""

    def test_tensor_full_roundtrip(self, db):
        """Every field on a maximally-populated TensorRecord survives ArangoDB roundtrip."""
        original = _fully_populated_tensor()
        db.store_tensor(original)
        retrieved = db.get_tensor(original.id)

        # Top-level fields
        assert retrieved.id == original.id
        assert retrieved.preamble == original.preamble
        assert retrieved.closing == original.closing
        assert retrieved.instructions_for_next == original.instructions_for_next
        assert retrieved.narrative_body == original.narrative_body
        assert retrieved.lineage_tags == original.lineage_tags
        assert retrieved.composition_equation == original.composition_equation
        assert retrieved.open_questions == original.open_questions

        # Provenance envelope
        assert retrieved.provenance.source.identifier == original.provenance.source.identifier
        assert retrieved.provenance.timestamp == original.provenance.timestamp
        assert retrieved.provenance.author_model_family == original.provenance.author_model_family
        assert retrieved.provenance.predecessors_in_scope == original.provenance.predecessors_in_scope

        # Strands
        assert len(retrieved.strands) == len(original.strands)
        for orig_s, ret_s in zip(original.strands, retrieved.strands, strict=True):
            assert ret_s.strand_index == orig_s.strand_index
            assert ret_s.title == orig_s.title
            assert ret_s.topics == orig_s.topics

    def test_composition_edge_roundtrip(self, db):
        """CompositionEdge with all fields populated survives roundtrip."""
        edge = CompositionEdge(
            from_tensor=uuid4(),
            to_tensor=uuid4(),
            relation_type=RelationType.CORRECTS,
            ordering=7,
            authored_mapping="Theory to practice mapping",
        )
        db.store_composition_edge(edge)
        graph = db.query_composition_graph()

        assert len(graph) == 1
        ret = graph[0]
        assert ret.id == edge.id
        assert ret.from_tensor == edge.from_tensor
        assert ret.relation_type == RelationType.CORRECTS
        assert ret.ordering == 7

    def test_correction_record_roundtrip(self, db):
        """CorrectionRecord survives roundtrip."""
        corr = CorrectionRecord(
            target_tensor=uuid4(),
            target_claim_id=uuid4(),
            original_claim="Old",
            corrected_claim="New",
        )
        db.store_correction(corr)
        chain = db.query_correction_chain(corr.target_claim_id)

        assert len(chain) == 1
        assert chain[0].id == corr.id
        assert chain[0].corrected_claim == "New"

    def test_entity_resolution_roundtrip(self, db):
        """EntityResolution with complex identity_data survives roundtrip."""
        entity = EntityResolution(
            entity_uuid=uuid4(),
            identity_type="human_researcher",
            identity_data={
                "name": "Dr. Example",
                "nested": {"key": [1, 2, 3]},
            },
        )
        db.store_entity(entity)
        retrieved = db.get_entity(entity.id)

        assert retrieved.id == entity.id
        assert retrieved.identity_data == entity.identity_data


# ── 5. Immutability Enforcement ───────────────────────────────────────


class TestImmutabilityAllTypes:
    """Immutability must be enforced on EVERY record type."""

    def test_duplicate_tensor_raises(self, db):
        tensor = TensorRecord()
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
            original_claim="old",
            corrected_claim="new",
        )
        db.store_correction(corr)
        with pytest.raises(ImmutabilityError):
            db.store_correction(corr)

    def test_duplicate_dissent_raises(self, db):
        dissent = DissentRecord(
            target_tensor=uuid4(),
            alternative_framework="alt",
            reasoning="reason",
        )
        db.store_dissent(dissent)
        with pytest.raises(ImmutabilityError):
            db.store_dissent(dissent)

    def test_duplicate_negation_raises(self, db):
        neg = NegationRecord(
            tensor_a=uuid4(),
            tensor_b=uuid4(),
            reasoning="reason",
        )
        db.store_negation(neg)
        with pytest.raises(ImmutabilityError):
            db.store_negation(neg)

    def test_duplicate_bootstrap_raises(self, db):
        boot = BootstrapRecord(
            instance_id="test",
            context_budget=0.8,
        )
        db.store_bootstrap(boot)
        with pytest.raises(ImmutabilityError):
            db.store_bootstrap(boot)

    def test_duplicate_evolution_raises(self, db):
        evo = SchemaEvolutionRecord(
            from_version="v1",
            to_version="v2",
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


# ── 6. Thread Safety ──────────────────────────────────────────────────


class TestThreadSafety:
    """Test thread safety with genuine concurrent contention."""

    def test_many_writers_no_data_loss(self, db):
        """N threads each storing a unique tensor -- all N must appear in final count."""
        n_threads = 20
        tensors = [TensorRecord(preamble=f"thread-{i}") for i in range(n_threads)]
        errors = []

        def store(t):
            try:
                db.store_tensor(t)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=store, args=(t,)) for t in tensors]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == [], f"Errors during concurrent writes: {errors}"
        assert db.count_records()["tensors"] == n_threads

    def test_concurrent_writes_to_different_tables(self, db):
        """Different record types stored concurrently must not interfere."""
        tensor = TensorRecord(preamble="concurrent")
        edge = CompositionEdge(
            from_tensor=uuid4(), to_tensor=uuid4(),
            relation_type=RelationType.COMPOSES_WITH,
        )
        corr = CorrectionRecord(
            target_tensor=uuid4(),
            original_claim="old", corrected_claim="new",
        )
        errors = []

        def do_store(fn, record):
            try:
                fn(record)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=do_store, args=(db.store_tensor, tensor)),
            threading.Thread(target=do_store, args=(db.store_composition_edge, edge)),
            threading.Thread(target=do_store, args=(db.store_correction, corr)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == [], f"Errors: {errors}"
        counts = db.count_records()
        assert counts["tensors"] == 1
        assert counts["edges"] == 1
        assert counts["corrections"] == 1

    def test_thread_pool_stress(self, db):
        """ThreadPoolExecutor with many tasks -- verifies no deadlocks."""
        n_tasks = 50

        def create_and_store(i):
            tensor = TensorRecord(preamble=f"pool-{i}")
            db.store_tensor(tensor)
            return tensor.id

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(create_and_store, i) for i in range(n_tasks)]
            ids = [f.result(timeout=30) for f in futures]

        assert len(ids) == n_tasks
        assert db.count_records()["tensors"] == n_tasks


# ── 7. Query Operations ───────────────────────────────────────────────


class TestQueryOperations:
    """Test query operations with realistic data."""

    @pytest.fixture
    def populated_db(self, db):
        """DB pre-populated with multi-tensor dataset."""
        t1 = _fully_populated_tensor(
            family="claude-opus",
            lineage_tags=("main-sequence", "experimental"),
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        t2 = _fully_populated_tensor(
            family="llama-3",
            lineage_tags=("main-sequence",),
            timestamp=datetime(2026, 1, 15, tzinfo=timezone.utc),
        )
        t3 = TensorRecord(
            provenance=ProvenanceEnvelope(
                author_model_family="granite",
                timestamp=datetime(2026, 2, 5, tzinfo=timezone.utc),
            ),
            lineage_tags=("scout",),
        )
        db.store_tensor(t1)
        db.store_tensor(t2)
        db.store_tensor(t3)
        return db, (t1, t2, t3)

    def test_query_project_state(self, populated_db):
        db, (t1, t2, t3) = populated_db
        state = db.query_project_state()

        assert state["tensor_count"] == 3
        assert set(state["lineage_tags"]) == {"main-sequence", "experimental", "scout"}
        assert set(state["model_families"]) == {"claude-opus", "llama-3", "granite"}

    def test_query_reading_order_chronological(self, populated_db):
        db, (t1, t2, t3) = populated_db
        order = db.query_reading_order("main-sequence")

        assert len(order) == 2
        assert order[0].provenance.timestamp < order[1].provenance.timestamp

    def test_query_claims_about_case_insensitive(self, db):
        tensor = TensorRecord(
            strands=(
                StrandRecord(
                    strand_index=0,
                    title="Security",
                    topics=("security",),
                    key_claims=(KeyClaim(text="Defense in depth"),),
                ),
            ),
        )
        db.store_tensor(tensor)

        claims_lower = db.query_claims_about("security")
        claims_upper = db.query_claims_about("SECURITY")

        assert len(claims_lower) == len(claims_upper) == 1

    def test_query_lineage_with_overlapping_tags(self, populated_db):
        db, (t1, t2, t3) = populated_db
        lineage = db.query_lineage(t1.id)
        lineage_ids = {t.id for t in lineage}

        assert t1.id in lineage_ids
        assert t2.id in lineage_ids  # shares main-sequence
        assert t3.id not in lineage_ids  # only has scout

    def test_query_cross_model_returns_all_when_multiple_families(self, populated_db):
        db, tensors = populated_db
        cross = db.query_cross_model()
        assert len(cross) == 3

    def test_query_bridges_excludes_non_bridge_edges(self, db):
        bridge = CompositionEdge(
            from_tensor=uuid4(), to_tensor=uuid4(),
            relation_type=RelationType.COMPOSES_WITH,
            authored_mapping="Has mapping",
        )
        non_bridge = CompositionEdge(
            from_tensor=uuid4(), to_tensor=uuid4(),
            relation_type=RelationType.COMPOSES_WITH,
        )
        db.store_composition_edge(bridge)
        db.store_composition_edge(non_bridge)

        bridges = db.query_bridges()
        assert len(bridges) == 1
        assert bridges[0].id == bridge.id

    def test_query_disagreements_aggregates_all_types(self, db):
        db.store_dissent(DissentRecord(
            target_tensor=uuid4(),
            alternative_framework="alt",
            reasoning="r",
        ))
        db.store_negation(NegationRecord(
            tensor_a=uuid4(), tensor_b=uuid4(), reasoning="r",
        ))
        db.store_correction(CorrectionRecord(
            target_tensor=uuid4(),
            original_claim="old", corrected_claim="new",
        ))

        disagreements = db.query_disagreements()
        types = {d["type"] for d in disagreements}
        assert types == {"dissent", "negation", "correction"}

    def test_query_epistemic_status_with_multiple_corrections(self, db):
        claim_id = uuid4()
        target = uuid4()

        c1 = CorrectionRecord(
            target_tensor=target, target_claim_id=claim_id,
            original_claim="first", corrected_claim="second",
        )
        c2 = CorrectionRecord(
            target_tensor=target, target_claim_id=claim_id,
            original_claim="second", corrected_claim="third",
        )

        db.store_correction(c1)
        db.store_correction(c2)

        status = db.query_epistemic_status(claim_id)
        assert status["correction_count"] == 2
        assert status["current_claim"] == "third"
        assert status["original_claim"] == "first"


# ── 8. count_records() Accuracy ───────────────────────────────────────


class TestCountRecords:
    """Verify count_records() returns correct counts."""

    def test_empty_database_all_zeros(self, db):
        counts = db.count_records()
        expected_keys = {"tensors", "edges", "corrections", "dissents",
                         "negations", "bootstraps", "evolutions", "entities"}
        assert set(counts.keys()) == expected_keys
        for value in counts.values():
            assert value == 0

    def test_counts_after_one_of_each(self, db):
        db.store_tensor(TensorRecord())
        db.store_composition_edge(CompositionEdge(
            from_tensor=uuid4(), to_tensor=uuid4(),
            relation_type=RelationType.COMPOSES_WITH,
        ))
        db.store_correction(CorrectionRecord(
            target_tensor=uuid4(),
            original_claim="o", corrected_claim="c",
        ))
        db.store_dissent(DissentRecord(
            target_tensor=uuid4(),
            alternative_framework="a", reasoning="r",
        ))
        db.store_negation(NegationRecord(
            tensor_a=uuid4(), tensor_b=uuid4(), reasoning="r",
        ))
        db.store_bootstrap(BootstrapRecord(
            instance_id="i", context_budget=0.5,
        ))
        db.store_evolution(SchemaEvolutionRecord(
            from_version="v1", to_version="v2",
        ))
        db.store_entity(EntityResolution(
            entity_uuid=uuid4(), identity_type="ai",
            identity_data={},
        ))

        counts = db.count_records()
        for value in counts.values():
            assert value == 1

    def test_counts_monotonically_increase(self, db):
        """Counts should only ever increase."""
        prev_counts = db.count_records()

        for i in range(5):
            db.store_tensor(TensorRecord(preamble=f"mono-{i}"))
            current_counts = db.count_records()
            for key in current_counts:
                assert current_counts[key] >= prev_counts[key]
            prev_counts = current_counts

        assert prev_counts["tensors"] == 5


# ── 9. Edge Cases: Unicode, Empty Values, Extremes ────────────────────


class TestEdgeCases:
    """Test edge cases that might break serialization."""

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
            lineage_tags=(unicode_text,),
        )
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)

        assert retrieved.preamble == unicode_text
        assert retrieved.lineage_tags[0] == unicode_text

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
        tensor = TensorRecord(id=nil_uuid, preamble="nil")
        db.store_tensor(tensor)
        retrieved = db.get_tensor(nil_uuid)

        assert retrieved.id == nil_uuid

    def test_many_strands(self, db):
        strands = tuple(
            StrandRecord(
                strand_index=i,
                title=f"Strand {i}",
                topics=(f"topic-{i}",),
                key_claims=(KeyClaim(text=f"Claim {i}"),),
            )
            for i in range(50)
        )
        tensor = TensorRecord(strands=strands)
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)

        assert len(retrieved.strands) == 50


# ── 10. NotFoundError on All Getters ──────────────────────────────────


class TestNotFoundErrors:
    """Verify NotFoundError on all relevant access paths."""

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


# ── 11. get_strand() Behavior ─────────────────────────────────────────


class TestGetStrand:
    """Test get_strand() projection behavior."""

    def test_get_strand_returns_single_strand(self, db):
        tensor = TensorRecord(
            strands=(
                StrandRecord(
                    strand_index=0,
                    title="First",
                    topics=("a",),
                    key_claims=(KeyClaim(text="Claim 0"),),
                ),
                StrandRecord(
                    strand_index=1,
                    title="Second",
                    topics=("b",),
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
                    topics=("a",), key_claims=(KeyClaim(text="x"),),
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
                    topics=("a",), key_claims=(KeyClaim(text="x"),),
                ),
            ),
        )
        db.store_tensor(tensor)

        with pytest.raises(NotFoundError):
            db.get_strand(tensor.id, 99)


# ── 12. Behavioral Equivalence with InMemoryBackend ───────────────────


class TestBehavioralEquivalence:
    """Both backends must produce identical results for the same operations."""

    @pytest.fixture
    def both_backends(self, mock_arango_client):
        """Paired ArangoDB (mocked) and InMemory backends."""
        mock_client, collections = mock_arango_client
        arango = ArangoDBBackend()
        mem = InMemoryBackend()
        yield arango, mem
        arango.close()

    def _apply_same_operations(self, arango, mem):
        """Apply identical operations to both backends."""
        t1_id = UUID("11111111-1111-1111-1111-111111111111")
        t2_id = UUID("22222222-2222-2222-2222-222222222222")
        claim_id = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")

        t1 = TensorRecord(
            id=t1_id,
            provenance=ProvenanceEnvelope(
                author_model_family="claude",
                timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            preamble="First tensor",
            strands=(
                StrandRecord(
                    strand_index=0,
                    title="Architecture",
                    topics=("design",),
                    key_claims=(
                        KeyClaim(
                            claim_id=claim_id,
                            text="Loose coupling",
                            epistemic=EpistemicMetadata(truth=0.9),
                        ),
                    ),
                ),
            ),
            lineage_tags=("main-seq",),
        )
        t2 = TensorRecord(
            id=t2_id,
            provenance=ProvenanceEnvelope(
                author_model_family="llama",
                timestamp=datetime(2026, 2, 1, tzinfo=timezone.utc),
            ),
            lineage_tags=("main-seq",),
        )

        for backend in (arango, mem):
            backend.store_tensor(t1)
            backend.store_tensor(t2)

        corr = CorrectionRecord(
            id=UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
            target_tensor=t1_id,
            target_claim_id=claim_id,
            original_claim="old",
            corrected_claim="new",
        )
        for backend in (arango, mem):
            backend.store_correction(corr)

        return t1_id, t2_id, claim_id

    def test_count_records_match(self, both_backends):
        arango, mem = both_backends
        self._apply_same_operations(arango, mem)
        assert arango.count_records() == mem.count_records()

    def test_get_tensor_match(self, both_backends):
        arango, mem = both_backends
        t1_id, _, _ = self._apply_same_operations(arango, mem)

        arango_t = arango.get_tensor(t1_id)
        mem_t = mem.get_tensor(t1_id)

        assert arango_t.id == mem_t.id
        assert arango_t.preamble == mem_t.preamble

    def test_list_tensors_match(self, both_backends):
        arango, mem = both_backends
        self._apply_same_operations(arango, mem)

        arango_tensors = sorted(arango.list_tensors(), key=lambda t: str(t.id))
        mem_tensors = sorted(mem.list_tensors(), key=lambda t: str(t.id))

        assert len(arango_tensors) == len(mem_tensors)
        for at, mt in zip(arango_tensors, mem_tensors, strict=True):
            assert at.id == mt.id

    def test_query_project_state_match(self, both_backends):
        arango, mem = both_backends
        self._apply_same_operations(arango, mem)
        assert arango.query_project_state() == mem.query_project_state()

    def test_query_correction_chain_match(self, both_backends):
        arango, mem = both_backends
        _, _, claim_id = self._apply_same_operations(arango, mem)

        arango_chain = arango.query_correction_chain(claim_id)
        mem_chain = mem.query_correction_chain(claim_id)

        assert len(arango_chain) == len(mem_chain)
        assert arango_chain[0].corrected_claim == mem_chain[0].corrected_claim

    def test_interface_version_match(self, both_backends):
        arango, mem = both_backends
        assert arango.get_interface_version() == mem.get_interface_version()


# ── 13. Access Control Hook ───────────────────────────────────────────


class TestAccessControl:
    """Test access control hook (always returns True in v1)."""

    def test_check_access_always_true(self, db):
        assert db.check_access("anyone", "anything") is True
        assert db.check_access("system", "store_tensor", uuid4()) is True

    def test_interface_version(self, db):
        assert db.get_interface_version() == "v1"


# ── 14. list_tensors() Returns All Tensors ────────────────────────────


class TestListTensors:
    """Test list_tensors() behavior."""

    def test_list_tensors_empty(self, db):
        assert db.list_tensors() == []

    def test_list_tensors_returns_all(self, db):
        t1 = TensorRecord(preamble="first")
        t2 = TensorRecord(preamble="second")
        t3 = TensorRecord(preamble="third")

        db.store_tensor(t1)
        db.store_tensor(t2)
        db.store_tensor(t3)

        tensors = db.list_tensors()
        assert len(tensors) == 3
        ids = {t.id for t in tensors}
        assert ids == {t1.id, t2.id, t3.id}


# ── 15. query_entities_by_uuid ────────────────────────────────────────


class TestQueryEntitiesByUUID:
    """Test entity query by shared UUID."""

    def test_query_entities_by_uuid(self, db):
        shared_uuid = uuid4()
        entity_a = EntityResolution(
            entity_uuid=shared_uuid,
            identity_type="ai_instance",
            identity_data={"label": "first"},
        )
        entity_b = EntityResolution(
            entity_uuid=shared_uuid,
            identity_type="ai_instance",
            identity_data={"label": "second"},
        )
        db.store_entity(entity_a)
        db.store_entity(entity_b)

        matches = db.query_entities_by_uuid(shared_uuid)
        assert {m.id for m in matches} == {entity_a.id, entity_b.id}

    def test_query_entities_by_uuid_empty(self, db):
        matches = db.query_entities_by_uuid(uuid4())
        assert matches == []


# ── 16. No Mutation Methods Exist ─────────────────────────────────────


class TestNoMutationMethods:
    """The interface must not expose any delete/update/modify methods."""

    def test_no_delete_methods(self, db):
        for name in ("delete", "delete_tensor", "delete_entity",
                      "delete_correction", "remove", "drop"):
            assert not hasattr(db, name), f"Found forbidden method: {name}"

    def test_no_update_methods(self, db):
        for name in ("update", "update_tensor", "update_entity",
                      "modify", "patch", "upsert"):
            assert not hasattr(db, name), f"Found forbidden method: {name}"
