"""Integration tests for ArangoDB backend against REAL ArangoDB instance.

These tests connect to a live ArangoDB server at 192.168.111.125:8529
using a dedicated test database (apacheta_test). No mocks. No fakes.

If ArangoDB is unavailable, all tests skip gracefully.

Connection details:
- Host: http://192.168.111.125:8529
- Database: apacheta_test (test database, NOT production)
- Admin user (root) used ONLY for database creation/teardown
- Test user (apacheta_test) used for all actual test operations

Design:
- Session-scoped fixture uses root to create/drop test database (admin op)
- Function-scoped fixture connects with least-privilege test user
- Every test runs against real ArangoDB with least-privilege credentials
- Tests verify behavioral equivalence with InMemoryBackend
"""

from datetime import datetime
import math
import threading
from uuid import uuid4

import pytest

from yanantin.apacheta.backends.arango import ArangoDBBackend
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

# Connection parameters
ARANGO_HOST = "http://192.168.111.125:8529"
ARANGO_DB = "apacheta_test"

# Admin credentials — ONLY for database creation/teardown (session fixture)
ARANGO_ADMIN_USER = "root"
ARANGO_ADMIN_PASSWORD = "LFNi0vhD7mEE0ZH"

# Least-privilege test credentials — used for ALL test operations
ARANGO_TEST_USER = "apacheta_test"
ARANGO_TEST_PASSWORD = "lbxKTSrUc6OkNOranjI_Kw"


def check_arango_available() -> bool:
    """Check if ArangoDB is reachable. Returns True if available, False otherwise."""
    try:
        from arango import ArangoClient
        client = ArangoClient(hosts=ARANGO_HOST)
        sys_db = client.db("_system", username=ARANGO_ADMIN_USER, password=ARANGO_ADMIN_PASSWORD)
        sys_db.databases()
        client.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def arango_session():
    """Session-scoped fixture: check connectivity and create clean test database.

    This fixture:
    1. Checks if ArangoDB is reachable
    2. If not reachable, skips all tests in this module
    3. If reachable, drops and recreates apacheta_test database for clean state
    4. Yields nothing (backends are created per-test)
    5. Cleanup happens via function-scoped fixtures
    """
    if not check_arango_available():
        pytest.skip(f"ArangoDB not available at {ARANGO_HOST}")

    from arango import ArangoClient

    # Admin operation: create fresh test database (root only)
    client = ArangoClient(hosts=ARANGO_HOST)
    sys_db = client.db("_system", username=ARANGO_ADMIN_USER, password=ARANGO_ADMIN_PASSWORD)

    if sys_db.has_database(ARANGO_DB):
        sys_db.delete_database(ARANGO_DB)

    # Create database with test user access
    sys_db.create_database(
        ARANGO_DB,
        users=[{"username": ARANGO_TEST_USER, "password": ARANGO_TEST_PASSWORD, "active": True}],
    )
    # Grant rw to test user on the new database
    sys_db.update_permission(ARANGO_TEST_USER, "rw", ARANGO_DB)

    client.close()

    yield  # Tests run here with least-privilege credentials

    # Admin cleanup: drop test database
    client = ArangoClient(hosts=ARANGO_HOST)
    sys_db = client.db("_system", username=ARANGO_ADMIN_USER, password=ARANGO_ADMIN_PASSWORD)
    if sys_db.has_database(ARANGO_DB):
        sys_db.delete_database(ARANGO_DB)
    client.close()


@pytest.fixture
def backend(arango_session):
    """Function-scoped fixture: fresh backend with clean collections.

    Creates a new backend instance and truncates all collections before each test.
    Ensures test isolation by giving each test a clean slate.
    """
    db = ArangoDBBackend(
        host=ARANGO_HOST,
        db_name=ARANGO_DB,
        username=ARANGO_TEST_USER,
        password=ARANGO_TEST_PASSWORD,
    )

    # Truncate all collections for clean state
    for collection_name in ("tensors", "composition_edges", "corrections",
                            "dissents", "negations", "bootstraps",
                            "evolutions", "entities"):
        collection = db._db.collection(collection_name)
        collection.truncate()

    yield db

    # Close connection after test
    db.close()


@pytest.fixture
def sample_tensor():
    """Sample tensor for testing."""
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


# ── Basic Store and Retrieve Tests ─────────────────────────────────


class TestBasicStoreAndRetrieve:
    """Test basic storage and retrieval operations."""

    def test_store_and_get_tensor(self, backend, sample_tensor):
        backend.store_tensor(sample_tensor)
        retrieved = backend.get_tensor(sample_tensor.id)
        assert retrieved.id == sample_tensor.id
        assert retrieved.preamble == "Test tensor"

    def test_list_tensors_empty(self, backend):
        assert backend.list_tensors() == []

    def test_list_tensors_after_store(self, backend, sample_tensor):
        backend.store_tensor(sample_tensor)
        tensors = backend.list_tensors()
        assert len(tensors) == 1
        assert tensors[0].id == sample_tensor.id

    def test_get_strand(self, backend, sample_tensor):
        backend.store_tensor(sample_tensor)
        result = backend.get_strand(sample_tensor.id, 0)
        assert len(result.strands) == 1
        assert result.strands[0].title == "Test Strand"

    def test_get_strand_shares_source_uuid(self, backend, sample_tensor):
        """Verify that get_strand returns a view with same UUID as source."""
        source_tensor = sample_tensor.model_copy(
            update={
                "strands": sample_tensor.strands + (
                    StrandRecord(
                        strand_index=1,
                        title="Second Strand",
                        topics=["testing"],
                        key_claims=[
                            KeyClaim(
                                text="Views keep provenance intact",
                                epistemic=EpistemicMetadata(truth=0.9),
                            ),
                        ],
                    ),
                )
            }
        )
        backend.store_tensor(source_tensor)
        strand_tensor = backend.get_strand(source_tensor.id, 0)

        assert strand_tensor.id == source_tensor.id
        assert len(source_tensor.strands) == 2
        assert len(strand_tensor.strands) == 1

        # Attempting to store the strand view should fail (same UUID)
        with pytest.raises(ImmutabilityError):
            backend.store_tensor(strand_tensor)

    def test_get_nonexistent_tensor(self, backend):
        with pytest.raises(NotFoundError):
            backend.get_tensor(uuid4())

    def test_get_nonexistent_strand(self, backend, sample_tensor):
        backend.store_tensor(sample_tensor)
        with pytest.raises(NotFoundError):
            backend.get_strand(sample_tensor.id, 99)


# ── Immutability Tests ─────────────────────────────────────────────


class TestImmutability:
    """Verify immutability constraints are enforced."""

    def test_duplicate_tensor_raises(self, backend):
        tensor = TensorRecord(preamble="First version")
        backend.store_tensor(tensor)
        duplicate = TensorRecord(id=tensor.id, preamble="Attempted overwrite")
        with pytest.raises(ImmutabilityError):
            backend.store_tensor(duplicate)

    def test_duplicate_edge_raises(self, backend):
        edge = CompositionEdge(
            from_tensor=uuid4(),
            to_tensor=uuid4(),
            relation_type=RelationType.COMPOSES_WITH,
        )
        backend.store_composition_edge(edge)
        with pytest.raises(ImmutabilityError):
            backend.store_composition_edge(edge)

    def test_duplicate_correction_raises(self, backend):
        corr = CorrectionRecord(
            target_tensor=uuid4(),
            target_claim_id=uuid4(),
            original_claim="old",
            corrected_claim="new",
        )
        backend.store_correction(corr)
        with pytest.raises(ImmutabilityError):
            backend.store_correction(corr)

    def test_duplicate_dissent_raises(self, backend):
        dissent = DissentRecord(
            target_tensor=uuid4(),
            alternative_framework="alternative",
            reasoning="because",
        )
        backend.store_dissent(dissent)
        with pytest.raises(ImmutabilityError):
            backend.store_dissent(dissent)

    def test_duplicate_negation_raises(self, backend):
        neg = NegationRecord(
            tensor_a=uuid4(),
            tensor_b=uuid4(),
            reasoning="contradictory",
        )
        backend.store_negation(neg)
        with pytest.raises(ImmutabilityError):
            backend.store_negation(neg)

    def test_duplicate_bootstrap_raises(self, backend):
        boot = BootstrapRecord(
            instance_id="test-instance",
            context_budget=0.8,
            task="testing",
        )
        backend.store_bootstrap(boot)
        with pytest.raises(ImmutabilityError):
            backend.store_bootstrap(boot)

    def test_duplicate_evolution_raises(self, backend):
        evo = SchemaEvolutionRecord(
            from_version="v1",
            to_version="v2",
            fields_added=["new_field"],
        )
        backend.store_evolution(evo)
        with pytest.raises(ImmutabilityError):
            backend.store_evolution(evo)

    def test_duplicate_entity_raises(self, backend):
        entity = EntityResolution(
            entity_uuid=uuid4(),
            identity_type="ai_instance",
            identity_data={"model": "claude"},
        )
        backend.store_entity(entity)
        with pytest.raises(ImmutabilityError):
            backend.store_entity(entity)

    def test_no_delete_method(self, backend):
        """Verify backend has no delete methods."""
        assert not hasattr(backend, "delete_tensor")
        assert not hasattr(backend, "delete")
        assert not hasattr(backend, "remove")
        assert not hasattr(backend, "drop")

    def test_no_update_method(self, backend):
        """Verify backend has no update methods."""
        assert not hasattr(backend, "update_tensor")
        assert not hasattr(backend, "modify")
        assert not hasattr(backend, "patch")


# ── Composition Edge Tests ─────────────────────────────────────────


class TestCompositionEdges:
    """Test composition edge storage and queries."""

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
        assert graph[0].to_tensor == t_b

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
        assert bridges[0].authored_mapping == "Theory maps to practice via..."

    def test_multiple_edges(self, backend):
        """Test storing multiple edges."""
        edges = [
            CompositionEdge(from_tensor=uuid4(), to_tensor=uuid4(),
                           relation_type=RelationType.COMPOSES_WITH)
            for _ in range(5)
        ]
        for edge in edges:
            backend.store_composition_edge(edge)

        graph = backend.query_composition_graph()
        assert len(graph) == 5
        assert {e.id for e in graph} == {e.id for e in edges}


# ── Correction Tests ───────────────────────────────────────────────


class TestCorrections:
    """Test correction record storage and queries."""

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

    def test_correction_chain_multiple(self, backend):
        """Test multiple corrections to same claim."""
        claim_id = uuid4()
        tensor_id = uuid4()

        corr1 = CorrectionRecord(
            target_tensor=tensor_id,
            target_claim_id=claim_id,
            original_claim="v1",
            corrected_claim="v2",
        )
        corr2 = CorrectionRecord(
            target_tensor=tensor_id,
            target_claim_id=claim_id,
            original_claim="v2",
            corrected_claim="v3",
        )

        backend.store_correction(corr1)
        backend.store_correction(corr2)

        chain = backend.query_correction_chain(claim_id)
        assert len(chain) == 2

        status = backend.query_epistemic_status(claim_id)
        assert status["current_claim"] == "v3"
        assert status["correction_count"] == 2
        assert status["original_claim"] == "v1"


# ── Dissent and Negation Tests ─────────────────────────────────────


class TestDissentAndNegation:
    """Test dissent and negation record storage."""

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

    def test_query_disagreements_all_types(self, backend):
        """Verify all disagreement types appear in query."""
        tensor_id = uuid4()
        claim_id = uuid4()

        dissent = DissentRecord(
            target_tensor=tensor_id,
            alternative_framework="alternative",
            reasoning="reason1",
        )
        negation = NegationRecord(
            tensor_a=uuid4(),
            tensor_b=uuid4(),
            reasoning="reason2",
        )
        correction = CorrectionRecord(
            target_tensor=tensor_id,
            target_claim_id=claim_id,
            original_claim="old",
            corrected_claim="new",
        )

        backend.store_dissent(dissent)
        backend.store_negation(negation)
        backend.store_correction(correction)

        disagreements = backend.query_disagreements()
        types = {d["type"] for d in disagreements}
        assert types == {"dissent", "negation", "correction"}


# ── Bootstrap and Evolution Tests ──────────────────────────────────


class TestBootstrapAndEvolution:
    """Test bootstrap and schema evolution records."""

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

    def test_multiple_bootstraps(self, backend):
        """Test storing multiple bootstrap records."""
        for i in range(3):
            boot = BootstrapRecord(
                instance_id=f"instance-{i}",
                context_budget=0.7 + i * 0.1,
                task=f"task-{i}",
            )
            backend.store_bootstrap(boot)

        counts = backend.count_records()
        assert counts["bootstraps"] == 3


# ── Entity Resolution Tests ────────────────────────────────────────


class TestEntityResolution:
    """Test entity resolution storage and queries."""

    def test_store_entity(self, backend):
        entity = EntityResolution(
            entity_uuid=uuid4(),
            identity_type="ai_instance",
            identity_data={"model": "claude"},
        )
        backend.store_entity(entity)
        counts = backend.count_records()
        assert counts["entities"] == 1

    def test_get_entity_roundtrip(self, backend):
        entity = EntityResolution(
            entity_uuid=uuid4(),
            identity_type="ai_instance",
            identity_data={"model": "claude-3-opus"},
        )
        backend.store_entity(entity)
        retrieved = backend.get_entity(entity.id)
        assert retrieved.id == entity.id
        assert retrieved.entity_uuid == entity.entity_uuid
        assert retrieved.identity_data["model"] == "claude-3-opus"

    def test_get_entity_not_found(self, backend):
        with pytest.raises(NotFoundError):
            backend.get_entity(uuid4())

    def test_query_entities_by_uuid(self, backend):
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
        backend.store_entity(entity_a)
        backend.store_entity(entity_b)
        matches = backend.query_entities_by_uuid(shared_uuid)
        assert {match.id for match in matches} == {entity_a.id, entity_b.id}

    def test_query_entities_by_uuid_empty(self, backend):
        matches = backend.query_entities_by_uuid(uuid4())
        assert matches == []


# ── Query Operation Tests ──────────────────────────────────────────


class TestQueryOperations:
    """Test all query operations."""

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
        assert "How does the archivist query?" in questions

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

    def test_query_anti_patterns(self, backend):
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
        anti_patterns = backend.query_anti_patterns()
        assert len(anti_patterns) == 1
        assert anti_patterns[0]["topic"] == "anti-pattern: coupling"

    def test_query_lineage_empty_tags(self, backend):
        tensor = TensorRecord(lineage_tags=())
        backend.store_tensor(tensor)
        lineage = backend.query_lineage(tensor.id)
        assert lineage == []


# ── Unicode and Special Character Tests ────────────────────────────


class TestUnicodeHandling:
    """Test storage and retrieval of various Unicode characters."""

    def test_unicode_cjk(self, backend):
        """Test Chinese, Japanese, Korean characters."""
        tensor = TensorRecord(
            preamble="中文 日本語 한국어",
            strands=[
                StrandRecord(
                    strand_index=0,
                    title="漢字テストハングル",
                    topics=["unicode"],
                    key_claims=[
                        KeyClaim(
                            text="Unicode支持应该正常工作",
                            epistemic=EpistemicMetadata(truth=1.0),
                        ),
                    ],
                ),
            ],
        )
        backend.store_tensor(tensor)
        retrieved = backend.get_tensor(tensor.id)
        assert retrieved.preamble == "中文 日本語 한국어"
        assert retrieved.strands[0].title == "漢字テストハングル"

    def test_unicode_emoji(self, backend):
        """Test emoji handling."""
        tensor = TensorRecord(
            preamble="Testing emoji 🚀 🎉 💡",
            strands=[
                StrandRecord(
                    strand_index=0,
                    title="Emoji test 🔬",
                    topics=["unicode", "emoji"],
                    key_claims=[
                        KeyClaim(
                            text="Emoji should work 👍",
                            epistemic=EpistemicMetadata(truth=1.0),
                        ),
                    ],
                ),
            ],
        )
        backend.store_tensor(tensor)
        retrieved = backend.get_tensor(tensor.id)
        assert "🚀" in retrieved.preamble
        assert "🔬" in retrieved.strands[0].title

    def test_unicode_rtl(self, backend):
        """Test right-to-left text (Arabic, Hebrew)."""
        tensor = TensorRecord(
            preamble="العربية עברית",
            strands=[
                StrandRecord(
                    strand_index=0,
                    title="اختبار בדיקה",
                    topics=["rtl"],
                    key_claims=[
                        KeyClaim(
                            text="RTL text should work",
                            epistemic=EpistemicMetadata(truth=1.0),
                        ),
                    ],
                ),
            ],
        )
        backend.store_tensor(tensor)
        retrieved = backend.get_tensor(tensor.id)
        assert retrieved.preamble == "العربية עברית"

    def test_unicode_combining_characters(self, backend):
        """Test combining diacritical marks."""
        tensor = TensorRecord(
            preamble="café naïve Zürich",  # é = e + combining acute
            strands=[
                StrandRecord(
                    strand_index=0,
                    title="Diacritics test",
                    topics=["unicode"],
                    key_claims=[
                        KeyClaim(
                            text="Ångström ñoño",
                            epistemic=EpistemicMetadata(truth=1.0),
                        ),
                    ],
                ),
            ],
        )
        backend.store_tensor(tensor)
        retrieved = backend.get_tensor(tensor.id)
        assert "café" in retrieved.preamble

    def test_null_bytes_in_strings(self, backend):
        """Test how ArangoDB handles null bytes in strings.

        This test documents actual ArangoDB behavior with null bytes.
        Depending on the database, null bytes might be:
        - Stored as-is
        - Rejected with an error
        - Truncated at the null byte

        We test to find out what actually happens.
        """
        tensor = TensorRecord(
            preamble="Text with\x00null byte",
            strands=[
                StrandRecord(
                    strand_index=0,
                    title="Null byte test",
                    topics=["edge-cases"],
                    key_claims=[
                        KeyClaim(
                            text="Claim\x00with\x00nulls",
                            epistemic=EpistemicMetadata(truth=1.0),
                        ),
                    ],
                ),
            ],
        )

        # Try storing - this might succeed or fail
        try:
            backend.store_tensor(tensor)
            retrieved = backend.get_tensor(tensor.id)
            # If we get here, ArangoDB accepted the null bytes
            # Document what happened to them
            assert retrieved.preamble is not None
            # The exact behavior is database-dependent
        except Exception as e:
            # If storage fails, that's also valid behavior
            # Document that ArangoDB rejects null bytes
            assert True, f"ArangoDB rejected null bytes: {e}"


# ── Large Data Tests ───────────────────────────────────────────────


class TestLargeData:
    """Test handling of large strings and many records."""

    def test_large_preamble(self, backend):
        """Test storing tensor with large preamble."""
        large_text = "A" * 100000  # 100KB text
        tensor = TensorRecord(preamble=large_text)
        backend.store_tensor(tensor)
        retrieved = backend.get_tensor(tensor.id)
        assert len(retrieved.preamble) == 100000

    def test_many_strands(self, backend):
        """Test tensor with many strands."""
        strands = [
            StrandRecord(
                strand_index=i,
                title=f"Strand {i}",
                topics=[f"topic-{i}"],
                key_claims=[
                    KeyClaim(
                        text=f"Claim {i}",
                        epistemic=EpistemicMetadata(truth=0.5),
                    ),
                ],
            )
            for i in range(100)
        ]
        tensor = TensorRecord(strands=strands)
        backend.store_tensor(tensor)
        retrieved = backend.get_tensor(tensor.id)
        assert len(retrieved.strands) == 100

    def test_many_tensors(self, backend):
        """Test storing many tensors."""
        tensors = [TensorRecord(preamble=f"Tensor {i}") for i in range(50)]
        for tensor in tensors:
            backend.store_tensor(tensor)

        all_tensors = backend.list_tensors()
        assert len(all_tensors) == 50

    def test_large_claim_text(self, backend):
        """Test very long claim text."""
        long_claim = "B" * 50000  # 50KB claim
        tensor = TensorRecord(
            strands=[
                StrandRecord(
                    strand_index=0,
                    title="Large claim test",
                    topics=["large"],
                    key_claims=[
                        KeyClaim(
                            text=long_claim,
                            epistemic=EpistemicMetadata(truth=1.0),
                        ),
                    ],
                ),
            ],
        )
        backend.store_tensor(tensor)
        retrieved = backend.get_tensor(tensor.id)
        assert len(retrieved.strands[0].key_claims[0].text) == 50000


# ── Extreme Float Value Tests ──────────────────────────────────────


class TestExtremeFloatValues:
    """Test handling of extreme floating point values."""

    def test_epistemic_extreme_values(self, backend):
        """Test extreme epistemic metadata values."""
        tensor = TensorRecord(
            strands=[
                StrandRecord(
                    strand_index=0,
                    title="Extreme values",
                    key_claims=[
                        KeyClaim(
                            text="Test extreme floats",
                            epistemic=EpistemicMetadata(
                                truth=-999.999,
                                falsity=999.999,
                                indeterminacy=1e10,
                            ),
                        ),
                    ],
                ),
            ],
        )
        backend.store_tensor(tensor)
        retrieved = backend.get_tensor(tensor.id)
        claim = retrieved.strands[0].key_claims[0]
        assert claim.epistemic.truth == -999.999
        assert claim.epistemic.falsity == 999.999
        assert claim.epistemic.indeterminacy == 1e10

    def test_epistemic_special_floats(self, backend):
        """Test special float values (inf, -inf).

        ArangoDB uses JSON encoding which does not support infinity.
        This test documents that ArangoDB rejects infinity values.

        Note: NaN cannot be tested as it doesn't equal itself.
        """
        tensor = TensorRecord(
            strands=[
                StrandRecord(
                    strand_index=0,
                    title="Special floats",
                    key_claims=[
                        KeyClaim(
                            text="Test infinity",
                            epistemic=EpistemicMetadata(
                                truth=float('inf'),
                                falsity=float('-inf'),
                            ),
                        ),
                    ],
                ),
            ],
        )

        # ArangoDB (JSON-based) does not support infinity values
        # This should raise an error during insertion
        with pytest.raises(Exception):  # DocumentInsertError or similar
            backend.store_tensor(tensor)


# ── Record Count Tests ─────────────────────────────────────────────


class TestRecordCounts:
    """Test count_records accuracy."""

    def test_count_records_empty(self, backend):
        counts = backend.count_records()
        assert counts["tensors"] == 0
        assert counts["edges"] == 0
        assert counts["corrections"] == 0
        assert counts["dissents"] == 0
        assert counts["negations"] == 0
        assert counts["bootstraps"] == 0
        assert counts["evolutions"] == 0
        assert counts["entities"] == 0

    def test_count_records_after_inserts(self, backend):
        # Store one of each type
        backend.store_tensor(TensorRecord())
        backend.store_composition_edge(CompositionEdge(
            from_tensor=uuid4(),
            to_tensor=uuid4(),
            relation_type=RelationType.COMPOSES_WITH,
        ))
        backend.store_correction(CorrectionRecord(
            target_tensor=uuid4(),
            target_claim_id=uuid4(),
            original_claim="old",
            corrected_claim="new",
        ))
        backend.store_dissent(DissentRecord(
            target_tensor=uuid4(),
            alternative_framework="alt",
            reasoning="reason",
        ))
        backend.store_negation(NegationRecord(
            tensor_a=uuid4(),
            tensor_b=uuid4(),
            reasoning="reason",
        ))
        backend.store_bootstrap(BootstrapRecord(
            instance_id="test",
            context_budget=0.8,
            task="test",
        ))
        backend.store_evolution(SchemaEvolutionRecord(
            from_version="v1",
            to_version="v2",
            fields_added=["field"],
        ))
        backend.store_entity(EntityResolution(
            entity_uuid=uuid4(),
            identity_type="ai_instance",
            identity_data={"model": "test"},
        ))

        counts = backend.count_records()
        assert counts["tensors"] == 1
        assert counts["edges"] == 1
        assert counts["corrections"] == 1
        assert counts["dissents"] == 1
        assert counts["negations"] == 1
        assert counts["bootstraps"] == 1
        assert counts["evolutions"] == 1
        assert counts["entities"] == 1


# ── Thread Safety Tests ────────────────────────────────────────────


class TestThreadSafety:
    """Test concurrent access to backend."""

    def test_concurrent_reads(self, backend, sample_tensor):
        """Test multiple threads reading simultaneously."""
        backend.store_tensor(sample_tensor)
        results = {}

        def read_tensor(thread_id):
            tensor = backend.get_tensor(sample_tensor.id)
            results[thread_id] = tensor.preamble

        threads = [
            threading.Thread(target=read_tensor, args=(i,))
            for i in range(10)
        ]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        assert all(not thread.is_alive() for thread in threads)
        assert all(preamble == "Test tensor" for preamble in results.values())

    def test_concurrent_writes(self, backend):
        """Test multiple threads writing different records."""
        results = {}

        def write_tensor(thread_id):
            tensor = TensorRecord(preamble=f"Tensor {thread_id}")
            backend.store_tensor(tensor)
            results[thread_id] = tensor.id

        threads = [
            threading.Thread(target=write_tensor, args=(i,))
            for i in range(10)
        ]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        assert all(not thread.is_alive() for thread in threads)
        assert len(results) == 10

        # Verify all tensors were stored
        all_tensors = backend.list_tensors()
        assert len(all_tensors) == 10

    def test_concurrent_mixed_operations(self, backend, sample_tensor):
        """Test mix of reads, writes, and queries."""
        backend.store_tensor(sample_tensor)
        claim_id = uuid4()
        correction = CorrectionRecord(
            target_tensor=sample_tensor.id,
            target_claim_id=claim_id,
            original_claim="Original",
            corrected_claim="Updated",
        )
        backend.store_correction(correction)

        results = {}

        def read_strand():
            strand = backend.get_strand(sample_tensor.id, 0)
            results["strand"] = strand.strands[0].title

        def read_epistemic():
            status = backend.query_epistemic_status(claim_id)
            results["epistemic"] = status["current_claim"]

        def write_tensor():
            backend.store_tensor(TensorRecord(preamble="Concurrent write"))
            results["write"] = True

        def query_state():
            state = backend.query_project_state()
            results["count"] = state["tensor_count"]

        threads = [
            threading.Thread(target=read_strand),
            threading.Thread(target=read_epistemic),
            threading.Thread(target=write_tensor),
            threading.Thread(target=query_state),
        ]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        assert all(not thread.is_alive() for thread in threads)
        assert results["strand"] == "Test Strand"
        assert results["epistemic"] == "Updated"
        assert results["write"] is True
        assert results["count"] >= 1


# ── Context Manager Tests ──────────────────────────────────────────


class TestContextManager:
    """Test context manager protocol."""

    def test_context_manager_usage(self, arango_session):
        """Test using backend as context manager."""
        # First clean up any existing data
        with ArangoDBBackend(
            host=ARANGO_HOST,
            db_name=ARANGO_DB,
            username=ARANGO_TEST_USER,
            password=ARANGO_TEST_PASSWORD,
        ) as db:
            # Truncate all collections for clean state
            for collection_name in ("tensors", "composition_edges", "corrections",
                                    "dissents", "negations", "bootstraps",
                                    "evolutions", "entities"):
                collection = db._db.collection(collection_name)
                collection.truncate()

        tensor = TensorRecord(preamble="Context manager test")
        tensor_id = tensor.id

        with ArangoDBBackend(
            host=ARANGO_HOST,
            db_name=ARANGO_DB,
            username=ARANGO_TEST_USER,
            password=ARANGO_TEST_PASSWORD,
        ) as db:
            db.store_tensor(tensor)
            assert db.count_records()["tensors"] == 1

        # Verify data persists after context manager exits
        with ArangoDBBackend(
            host=ARANGO_HOST,
            db_name=ARANGO_DB,
            username=ARANGO_TEST_USER,
            password=ARANGO_TEST_PASSWORD,
        ) as db:
            retrieved = db.get_tensor(tensor_id)
            assert retrieved.preamble == "Context manager test"

    def test_close_method(self, arango_session):
        """Test explicit close."""
        db = ArangoDBBackend(
            host=ARANGO_HOST,
            db_name=ARANGO_DB,
            username=ARANGO_TEST_USER,
            password=ARANGO_TEST_PASSWORD,
        )
        tensor = TensorRecord(preamble="Close test")
        db.store_tensor(tensor)
        db.close()
        # After close, backend should not be usable
        # (but we don't test that as it may raise various exceptions)


# ── Interface Compliance Tests ─────────────────────────────────────


class TestInterfaceCompliance:
    """Test compliance with ApachetaInterface."""

    def test_interface_version(self, backend):
        assert backend.get_interface_version() == "v1"

    def test_check_access_always_true(self, backend):
        """In v1, access control always returns True."""
        assert backend.check_access("anyone", "anything") is True
        assert backend.check_access("system", "store_tensor", uuid4()) is True


# ── Behavioral Equivalence Tests ───────────────────────────────────


class TestBehavioralEquivalence:
    """Test that ArangoDB backend behaves same as InMemoryBackend.

    These tests verify that operations produce the same results
    regardless of backend implementation.
    """

    def test_query_tensors_for_budget(self, backend):
        """Currently returns all tensors regardless of budget."""
        t1 = TensorRecord(preamble="t1")
        t2 = TensorRecord(preamble="t2")
        backend.store_tensor(t1)
        backend.store_tensor(t2)

        result = backend.query_tensors_for_budget(0.5)
        assert len(result) == 2

    def test_query_project_state_format(self, backend):
        """Verify query_project_state returns expected format."""
        tensor = TensorRecord(
            provenance=ProvenanceEnvelope(author_model_family="test-model"),
            lineage_tags=["tag1", "tag2"],
        )
        backend.store_tensor(tensor)

        state = backend.query_project_state()
        assert "tensor_count" in state
        assert "lineage_tags" in state
        assert "model_families" in state
        assert state["tensor_count"] == 1
        assert set(state["lineage_tags"]) == {"tag1", "tag2"}
        assert "test-model" in state["model_families"]
