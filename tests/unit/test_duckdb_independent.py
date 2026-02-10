"""Independent tests for the DuckDB backend — written by test author, not builder.

These tests probe what the builder might have gotten wrong:
- Serialization roundtrip fidelity through JSON
- Edge cases in UUID/datetime/tuple/enum handling
- Immutability enforcement on ALL record types
- File-backed persistence across connections
- Context manager protocol correctness
- Thread safety under real contention
- Query operations with realistic multi-tensor data
- count_records() accuracy
- Unicode, empty strings, extreme values
- Behavioral equivalence with the in-memory backend
"""

from __future__ import annotations

import concurrent.futures
import threading
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from yanantin.apacheta.backends.duckdb import DuckDBBackend
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


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def db():
    """Fresh in-memory DuckDB backend for each test."""
    backend = DuckDBBackend(":memory:")
    yield backend
    backend.close()


@pytest.fixture
def file_db(tmp_path):
    """File-backed DuckDB backend factory. Returns (path, backend)."""
    db_path = tmp_path / "apacheta_test.duckdb"
    backend = DuckDBBackend(db_path)
    yield db_path, backend
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


# ── 1. Serialization Roundtrip Fidelity ──────────────────────────────


class TestSerializationRoundtrip:
    """Store a complex, fully-populated record, retrieve it, verify every field."""

    def test_tensor_full_roundtrip(self, db):
        """Every field on a maximally-populated TensorRecord survives DuckDB roundtrip."""
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
        assert retrieved.provenance.source.version == original.provenance.source.version
        assert retrieved.provenance.source.description == original.provenance.source.description
        assert retrieved.provenance.timestamp == original.provenance.timestamp
        assert retrieved.provenance.author_model_family == original.provenance.author_model_family
        assert retrieved.provenance.author_instance_id == original.provenance.author_instance_id
        assert retrieved.provenance.context_budget_at_write == original.provenance.context_budget_at_write
        assert retrieved.provenance.predecessors_in_scope == original.provenance.predecessors_in_scope
        assert retrieved.provenance.interface_version == original.provenance.interface_version

        # Strands
        assert len(retrieved.strands) == len(original.strands)
        for orig_s, ret_s in zip(original.strands, retrieved.strands, strict=True):
            assert ret_s.strand_index == orig_s.strand_index
            assert ret_s.title == orig_s.title
            assert ret_s.content == orig_s.content
            assert ret_s.topics == orig_s.topics
            assert ret_s.epistemic == orig_s.epistemic
            assert len(ret_s.key_claims) == len(orig_s.key_claims)
            for orig_c, ret_c in zip(orig_s.key_claims, ret_s.key_claims, strict=True):
                assert ret_c.claim_id == orig_c.claim_id
                assert ret_c.text == orig_c.text
                assert ret_c.evidence_refs == orig_c.evidence_refs
                assert ret_c.epistemic.truth == orig_c.epistemic.truth
                assert ret_c.epistemic.indeterminacy == orig_c.epistemic.indeterminacy
                assert ret_c.epistemic.falsity == orig_c.epistemic.falsity
                assert ret_c.epistemic.representation_type == orig_c.epistemic.representation_type
                assert ret_c.epistemic.functional_spec == orig_c.epistemic.functional_spec
                assert ret_c.epistemic.scope_boundaries == orig_c.epistemic.scope_boundaries
                assert ret_c.epistemic.disagreement_type == orig_c.epistemic.disagreement_type

        # Declared losses
        assert len(retrieved.declared_losses) == len(original.declared_losses)
        for orig_l, ret_l in zip(original.declared_losses, retrieved.declared_losses, strict=True):
            assert ret_l.what_was_lost == orig_l.what_was_lost
            assert ret_l.why == orig_l.why
            assert ret_l.category == orig_l.category

        # Tensor-level epistemic
        assert retrieved.epistemic.truth == original.epistemic.truth
        assert retrieved.epistemic.indeterminacy == original.epistemic.indeterminacy
        assert retrieved.epistemic.falsity == original.epistemic.falsity
        assert retrieved.epistemic.scope_boundaries == original.epistemic.scope_boundaries

    def test_composition_edge_roundtrip(self, db):
        """CompositionEdge with all fields populated survives roundtrip."""
        edge = CompositionEdge(
            from_tensor=uuid4(),
            to_tensor=uuid4(),
            relation_type=RelationType.CORRECTS,
            ordering=7,
            authored_mapping="Theory to practice mapping with detailed reasoning.",
            provenance=ProvenanceEnvelope(
                author_model_family="granite",
                context_budget_at_write=0.5,
            ),
        )
        db.store_composition_edge(edge)
        graph = db.query_composition_graph()
        assert len(graph) == 1
        ret = graph[0]
        assert ret.id == edge.id
        assert ret.from_tensor == edge.from_tensor
        assert ret.to_tensor == edge.to_tensor
        assert ret.relation_type == RelationType.CORRECTS
        assert ret.ordering == 7
        assert ret.authored_mapping == edge.authored_mapping
        assert ret.provenance.author_model_family == "granite"

    def test_correction_record_roundtrip(self, db):
        """CorrectionRecord with all optional fields populated survives roundtrip."""
        corr = CorrectionRecord(
            target_tensor=uuid4(),
            target_strand_index=3,
            target_claim_id=uuid4(),
            original_claim="The old interpretation",
            corrected_claim="The corrected interpretation",
            evidence="Supported by experiment X results.",
            provenance=ProvenanceEnvelope(author_model_family="llama"),
        )
        db.store_correction(corr)
        chain = db.query_correction_chain(corr.target_claim_id)
        assert len(chain) == 1
        ret = chain[0]
        assert ret.id == corr.id
        assert ret.target_tensor == corr.target_tensor
        assert ret.target_strand_index == 3
        assert ret.target_claim_id == corr.target_claim_id
        assert ret.original_claim == corr.original_claim
        assert ret.corrected_claim == corr.corrected_claim
        assert ret.evidence == corr.evidence

    def test_dissent_record_roundtrip(self, db):
        dissent = DissentRecord(
            target_tensor=uuid4(),
            target_claim_id=uuid4(),
            alternative_framework="Field topology over discrete graphs",
            reasoning="Continuous representations capture more nuance.",
            provenance=ProvenanceEnvelope(author_model_family="deepseek"),
        )
        db.store_dissent(dissent)
        disagreements = db.query_disagreements()
        dissents = [d for d in disagreements if d["type"] == "dissent"]
        assert len(dissents) == 1
        assert dissents[0]["framework"] == dissent.alternative_framework
        assert dissents[0]["target_tensor"] == dissent.target_tensor

    def test_negation_record_roundtrip(self, db):
        neg = NegationRecord(
            tensor_a=uuid4(),
            tensor_b=uuid4(),
            reasoning="Irreconcilable frameworks: one assumes continuity, the other discreteness.",
            provenance=ProvenanceEnvelope(author_model_family="mistral"),
        )
        db.store_negation(neg)
        disagreements = db.query_disagreements()
        negations = [d for d in disagreements if d["type"] == "negation"]
        assert len(negations) == 1
        assert negations[0]["tensor_a"] == neg.tensor_a
        assert negations[0]["tensor_b"] == neg.tensor_b
        assert negations[0]["reasoning"] == neg.reasoning

    def test_bootstrap_record_roundtrip(self, db):
        selected = (uuid4(), uuid4(), uuid4())
        boot = BootstrapRecord(
            instance_id="opus-session-77",
            context_budget=0.92,
            task="Analyze tensor lineage for cross-model coherence",
            tensors_selected=selected,
            strands_selected=(0, 2, 5),
            what_was_omitted="Strands 1, 3, 4 omitted due to budget constraints.",
            provenance=ProvenanceEnvelope(author_model_family="claude"),
        )
        db.store_bootstrap(boot)
        # No direct get_bootstrap, so verify via count_records and store/retrieve immutability
        counts = db.count_records()
        assert counts["bootstraps"] == 1

    def test_evolution_record_roundtrip(self, db):
        evo = SchemaEvolutionRecord(
            from_version="v1",
            to_version="v2",
            fields_added=("functional_spec", "scope_boundaries"),
            fields_removed=("deprecated_field",),
            migration_notes="Added neutrosophic extensions. Removed legacy field.",
            provenance=ProvenanceEnvelope(author_model_family="claude"),
        )
        db.store_evolution(evo)
        counts = db.count_records()
        assert counts["evolutions"] == 1

    def test_entity_resolution_roundtrip(self, db):
        entity = EntityResolution(
            entity_uuid=uuid4(),
            identity_type="human_researcher",
            identity_data={
                "name": "Dr. Example",
                "affiliation": "Test University",
                "nested": {"key": [1, 2, 3]},
            },
            redacted=False,
            provenance=ProvenanceEnvelope(author_model_family="claude"),
        )
        db.store_entity(entity)
        retrieved = db.get_entity(entity.id)
        assert retrieved.id == entity.id
        assert retrieved.entity_uuid == entity.entity_uuid
        assert retrieved.identity_type == "human_researcher"
        assert retrieved.identity_data == entity.identity_data
        assert retrieved.identity_data["nested"]["key"] == [1, 2, 3]
        assert retrieved.redacted is False

    def test_entity_redacted_flag_roundtrip(self, db):
        """Verify that redacted=True survives the roundtrip."""
        entity = EntityResolution(
            entity_uuid=uuid4(),
            identity_type="ai_instance",
            identity_data={"model": "redacted-model"},
            redacted=True,
        )
        db.store_entity(entity)
        retrieved = db.get_entity(entity.id)
        assert retrieved.redacted is True


# ── 2. JSON Serialization Edge Cases ─────────────────────────────────


class TestJsonEdgeCases:
    """Test serialization edge cases that might break in JSON/DuckDB roundtrip."""

    def test_uuid_survives_json_roundtrip(self, db):
        """UUIDs stored as JSON strings must reconstruct as UUID objects, not strings."""
        tensor_id = UUID("12345678-1234-5678-1234-567812345678")
        predecessor = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        tensor = TensorRecord(
            id=tensor_id,
            provenance=ProvenanceEnvelope(
                predecessors_in_scope=(predecessor,),
            ),
        )
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor_id)
        assert isinstance(retrieved.id, UUID)
        assert retrieved.id == tensor_id
        assert isinstance(retrieved.provenance.predecessors_in_scope[0], UUID)
        assert retrieved.provenance.predecessors_in_scope[0] == predecessor

    def test_datetime_timezone_preservation(self, db):
        """Datetime with UTC timezone must survive serialization exactly."""
        ts = datetime(2026, 6, 15, 23, 59, 59, 999999, tzinfo=timezone.utc)
        tensor = TensorRecord(
            provenance=ProvenanceEnvelope(timestamp=ts),
        )
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)
        assert retrieved.provenance.timestamp == ts
        # Verify timezone awareness is preserved
        assert retrieved.provenance.timestamp.tzinfo is not None

    def test_naive_datetime_handling(self, db):
        """Naive datetime (no timezone) -- verify it survives roundtrip."""
        ts = datetime(2026, 3, 14, 9, 26, 53)
        tensor = TensorRecord(
            provenance=ProvenanceEnvelope(timestamp=ts),
        )
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)
        # The value should be preserved (whether or not timezone is added)
        assert retrieved.provenance.timestamp.year == 2026
        assert retrieved.provenance.timestamp.month == 3
        assert retrieved.provenance.timestamp.day == 14
        assert retrieved.provenance.timestamp.hour == 9
        assert retrieved.provenance.timestamp.minute == 26
        assert retrieved.provenance.timestamp.second == 53

    def test_tuples_survive_json_array_roundtrip(self, db):
        """Tuples are serialized as JSON arrays. They must come back as tuples, not lists."""
        tensor = TensorRecord(
            lineage_tags=("alpha", "beta", "gamma"),
            open_questions=("Q1?", "Q2?"),
            strands=(
                StrandRecord(
                    strand_index=0,
                    title="Test",
                    topics=("topic-a", "topic-b"),
                    key_claims=(
                        KeyClaim(
                            text="A claim",
                            evidence_refs=("ref-1", "ref-2", "ref-3"),
                        ),
                    ),
                ),
            ),
        )
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)

        assert isinstance(retrieved.lineage_tags, tuple)
        assert retrieved.lineage_tags == ("alpha", "beta", "gamma")
        assert isinstance(retrieved.open_questions, tuple)
        assert isinstance(retrieved.strands[0].topics, tuple)
        assert isinstance(retrieved.strands[0].key_claims[0].evidence_refs, tuple)

    def test_enum_values_survive_roundtrip(self, db):
        """All enum types must survive JSON serialization."""
        tensor = TensorRecord(
            declared_losses=(
                DeclaredLoss(
                    what_was_lost="test",
                    why="test",
                    category=LossCategory.TRAVERSAL_BIAS,
                ),
                DeclaredLoss(
                    what_was_lost="test2",
                    why="test2",
                    category=LossCategory.PRACTICAL_CONSTRAINT,
                ),
            ),
            epistemic=EpistemicMetadata(
                representation_type=RepresentationType.FUNCTIONAL,
                disagreement_type=DisagreementType.EMPIRICAL,
                functional_spec={"method": "bayesian"},
            ),
        )
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)

        assert retrieved.declared_losses[0].category == LossCategory.TRAVERSAL_BIAS
        assert retrieved.declared_losses[1].category == LossCategory.PRACTICAL_CONSTRAINT
        assert retrieved.epistemic.representation_type == RepresentationType.FUNCTIONAL
        assert retrieved.epistemic.disagreement_type == DisagreementType.EMPIRICAL

    def test_all_relation_types_survive_roundtrip(self, db):
        """Every RelationType enum value must roundtrip through DuckDB."""
        for rel_type in RelationType:
            edge = CompositionEdge(
                from_tensor=uuid4(),
                to_tensor=uuid4(),
                relation_type=rel_type,
            )
            db.store_composition_edge(edge)

        graph = db.query_composition_graph()
        stored_types = {e.relation_type for e in graph}
        assert stored_types == set(RelationType)

    def test_none_optional_fields(self, db):
        """Optional fields set to None must survive roundtrip as None."""
        tensor = TensorRecord(
            composition_equation=None,
            strands=(
                StrandRecord(
                    strand_index=0,
                    title="Test",
                    epistemic=None,
                ),
            ),
            epistemic=EpistemicMetadata(
                functional_spec=None,
                disagreement_type=None,
            ),
        )
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)
        assert retrieved.composition_equation is None
        assert retrieved.strands[0].epistemic is None
        assert retrieved.epistemic.functional_spec is None
        assert retrieved.epistemic.disagreement_type is None

    def test_nested_dict_in_functional_spec(self, db):
        """Deeply nested dicts in functional_spec must survive."""
        spec = {
            "level1": {
                "level2": {
                    "level3": [1, 2.5, "three", None, True, False],
                },
            },
            "empty_dict": {},
            "empty_list": [],
        }
        tensor = TensorRecord(
            epistemic=EpistemicMetadata(functional_spec=spec),
        )
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)
        assert retrieved.epistemic.functional_spec == spec

    def test_float_precision(self, db):
        """Float values must not lose precision through JSON serialization."""
        tensor = TensorRecord(
            epistemic=EpistemicMetadata(
                truth=0.123456789012345,
                indeterminacy=1e-15,
                falsity=9.999999999999998,
            ),
            provenance=ProvenanceEnvelope(
                context_budget_at_write=0.9999999999,
            ),
        )
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)
        assert retrieved.epistemic.truth == pytest.approx(0.123456789012345)
        assert retrieved.epistemic.indeterminacy == pytest.approx(1e-15)
        assert retrieved.epistemic.falsity == pytest.approx(9.999999999999998)
        assert retrieved.provenance.context_budget_at_write == pytest.approx(0.9999999999)


# ── 3. Immutability Enforcement on Every Record Type ─────────────────


class TestImmutabilityAllTypes:
    """Immutability must be enforced on EVERY record type, not just tensors."""

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

    def test_immutability_uses_id_not_content(self, db):
        """Two different records that share the same UUID should conflict."""
        shared_id = uuid4()
        tensor_a = TensorRecord(id=shared_id, preamble="Version A")
        tensor_b = TensorRecord(id=shared_id, preamble="Version B")
        db.store_tensor(tensor_a)
        with pytest.raises(ImmutabilityError):
            db.store_tensor(tensor_b)

    def test_different_ids_same_content_allowed(self, db):
        """Two records with identical content but different UUIDs should both store."""
        tensor_a = TensorRecord(preamble="Same content")
        tensor_b = TensorRecord(preamble="Same content")
        assert tensor_a.id != tensor_b.id  # different auto-generated UUIDs
        db.store_tensor(tensor_a)
        db.store_tensor(tensor_b)
        assert db.count_records()["tensors"] == 2


# ── 4. File-Backed Persistence ───────────────────────────────────────


class TestFilePersistence:
    """Verify data written to a file-backed DuckDB survives close/reopen."""

    def test_tensor_persists_across_connections(self, tmp_path):
        db_path = tmp_path / "persist_test.duckdb"
        tensor = _fully_populated_tensor()

        # Write and close
        db1 = DuckDBBackend(db_path)
        db1.store_tensor(tensor)
        db1.close()

        # Reopen and verify
        db2 = DuckDBBackend(db_path)
        retrieved = db2.get_tensor(tensor.id)
        assert retrieved.id == tensor.id
        assert retrieved.preamble == tensor.preamble
        assert len(retrieved.strands) == len(tensor.strands)
        assert retrieved.provenance.author_model_family == tensor.provenance.author_model_family
        assert retrieved.lineage_tags == tensor.lineage_tags
        assert retrieved.declared_losses == tensor.declared_losses
        db2.close()

    def test_all_record_types_persist(self, tmp_path):
        """Every record type must survive close/reopen."""
        db_path = tmp_path / "all_types.duckdb"
        tensor = TensorRecord(preamble="persist")
        edge = CompositionEdge(
            from_tensor=uuid4(), to_tensor=uuid4(),
            relation_type=RelationType.BRANCHES_FROM,
        )
        corr = CorrectionRecord(
            target_tensor=uuid4(),
            original_claim="old", corrected_claim="new",
        )
        dissent = DissentRecord(
            target_tensor=uuid4(),
            alternative_framework="alt", reasoning="r",
        )
        negation = NegationRecord(
            tensor_a=uuid4(), tensor_b=uuid4(), reasoning="r",
        )
        boot = BootstrapRecord(instance_id="i", context_budget=0.5)
        evo = SchemaEvolutionRecord(from_version="v1", to_version="v2")
        entity = EntityResolution(
            entity_uuid=uuid4(), identity_type="ai",
            identity_data={"k": "v"},
        )

        # Store all and close
        db1 = DuckDBBackend(db_path)
        db1.store_tensor(tensor)
        db1.store_composition_edge(edge)
        db1.store_correction(corr)
        db1.store_dissent(dissent)
        db1.store_negation(negation)
        db1.store_bootstrap(boot)
        db1.store_evolution(evo)
        db1.store_entity(entity)
        db1.close()

        # Reopen and verify counts
        db2 = DuckDBBackend(db_path)
        counts = db2.count_records()
        assert counts["tensors"] == 1
        assert counts["edges"] == 1
        assert counts["corrections"] == 1
        assert counts["dissents"] == 1
        assert counts["negations"] == 1
        assert counts["bootstraps"] == 1
        assert counts["evolutions"] == 1
        assert counts["entities"] == 1
        db2.close()

    def test_immutability_persists_across_connections(self, tmp_path):
        """A record stored before close must still block duplicates after reopen."""
        db_path = tmp_path / "immutable_persist.duckdb"
        tensor = TensorRecord(preamble="original")

        db1 = DuckDBBackend(db_path)
        db1.store_tensor(tensor)
        db1.close()

        db2 = DuckDBBackend(db_path)
        with pytest.raises(ImmutabilityError):
            db2.store_tensor(tensor)
        db2.close()

    def test_query_operations_work_after_reopen(self, tmp_path):
        """Queries on reopened database must return correct results."""
        db_path = tmp_path / "query_persist.duckdb"
        tensor = _fully_populated_tensor(family="claude-opus")

        db1 = DuckDBBackend(db_path)
        db1.store_tensor(tensor)
        db1.close()

        db2 = DuckDBBackend(db_path)
        state = db2.query_project_state()
        assert state["tensor_count"] == 1
        assert "claude-opus" in state["model_families"]

        claims = db2.query_claims_about("epistemics")
        assert len(claims) > 0
        db2.close()


# ── 5. Context Manager Protocol ──────────────────────────────────────


class TestContextManager:
    """Verify context manager protocol works correctly."""

    def test_context_manager_calls_close(self):
        """__exit__ must call close()."""
        with patch.object(DuckDBBackend, "close", wraps=DuckDBBackend.close) as mock_close:
            backend = DuckDBBackend(":memory:")
            with backend:
                backend.store_tensor(TensorRecord(preamble="cm test"))
            # close() should have been called by __exit__
            mock_close.assert_called_once()

    def test_context_manager_returns_self(self):
        """__enter__ must return the backend instance."""
        backend = DuckDBBackend(":memory:")
        with backend as db:
            assert db is backend

    def test_context_manager_usable_inside_with_block(self):
        """Backend should be fully usable inside the with block."""
        with DuckDBBackend(":memory:") as db:
            tensor = TensorRecord(preamble="inside with")
            db.store_tensor(tensor)
            retrieved = db.get_tensor(tensor.id)
            assert retrieved.preamble == "inside with"
            assert db.count_records()["tensors"] == 1

    def test_context_manager_on_file_backend(self, tmp_path):
        """File-backed context manager should flush data before close."""
        db_path = tmp_path / "cm_file.duckdb"
        tensor = TensorRecord(preamble="file cm")

        with DuckDBBackend(db_path) as db:
            db.store_tensor(tensor)
            tensor_id = tensor.id

        # Data should be accessible from new connection
        db2 = DuckDBBackend(db_path)
        retrieved = db2.get_tensor(tensor_id)
        assert retrieved.preamble == "file cm"
        db2.close()


# ── 6. Thread Safety Under Contention ────────────────────────────────


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
        entity = EntityResolution(
            entity_uuid=uuid4(), identity_type="ai",
            identity_data={"k": "v"},
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
            threading.Thread(target=do_store, args=(db.store_entity, entity)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == [], f"Errors during concurrent multi-table writes: {errors}"
        counts = db.count_records()
        assert counts["tensors"] == 1
        assert counts["edges"] == 1
        assert counts["corrections"] == 1
        assert counts["entities"] == 1

    def test_concurrent_readers_and_writer(self, db):
        """Readers must see consistent state even with a concurrent writer."""
        # Pre-populate
        for i in range(5):
            db.store_tensor(TensorRecord(
                preamble=f"pre-{i}",
                lineage_tags=("shared-tag",),
            ))

        read_results = []
        errors = []

        def reader():
            try:
                tensors = db.list_tensors()
                read_results.append(len(tensors))
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(5):
                    db.store_tensor(TensorRecord(
                        preamble=f"concurrent-{i}",
                        lineage_tags=("shared-tag",),
                    ))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(10)]
        threads.append(threading.Thread(target=writer))
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == [], f"Errors during concurrent read/write: {errors}"
        # Each reader should have seen at least 5 (pre-populated) and at most 10
        for count in read_results:
            assert 5 <= count <= 10

    def test_thread_pool_stress(self, db):
        """ThreadPoolExecutor with many tasks -- verifies no deadlocks or lost data."""
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
        # Verify each tensor is individually retrievable
        for tid in ids:
            retrieved = db.get_tensor(tid)
            assert retrieved.id == tid


# ── 7. Query Operations with Realistic Data ──────────────────────────


class TestRealisticQueries:
    """Query operations with multi-tensor datasets that exercise filtering logic."""

    @pytest.fixture
    def populated_db(self, db):
        """DB pre-populated with a realistic multi-tensor dataset."""
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
        t3 = _fully_populated_tensor(
            family="deepseek",
            lineage_tags=("experimental", "scout"),
            timestamp=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        # A tensor with no strands, no losses, no questions
        t4 = TensorRecord(
            provenance=ProvenanceEnvelope(
                author_model_family="granite",
                timestamp=datetime(2026, 2, 5, tzinfo=timezone.utc),
            ),
            lineage_tags=("scout",),
        )
        db.store_tensor(t1)
        db.store_tensor(t2)
        db.store_tensor(t3)
        db.store_tensor(t4)
        return db, (t1, t2, t3, t4)

    def test_query_project_state_counts(self, populated_db):
        db, (t1, t2, t3, t4) = populated_db
        state = db.query_project_state()
        assert state["tensor_count"] == 4
        assert set(state["lineage_tags"]) == {"main-sequence", "experimental", "scout"}
        assert set(state["model_families"]) == {"claude-opus", "llama-3", "deepseek", "granite"}

    def test_query_cross_model_returns_all_when_multiple_families(self, populated_db):
        db, tensors = populated_db
        cross = db.query_cross_model()
        assert len(cross) == 4  # 4 different families

    def test_query_cross_model_returns_empty_for_single_family(self, db):
        t1 = TensorRecord(provenance=ProvenanceEnvelope(author_model_family="claude"))
        t2 = TensorRecord(provenance=ProvenanceEnvelope(author_model_family="claude"))
        db.store_tensor(t1)
        db.store_tensor(t2)
        assert db.query_cross_model() == []

    def test_query_reading_order_is_chronological(self, populated_db):
        db, (t1, t2, t3, t4) = populated_db
        order = db.query_reading_order("main-sequence")
        assert len(order) == 2  # t1 and t2
        assert order[0].provenance.timestamp < order[1].provenance.timestamp

    def test_query_lineage_with_overlapping_tags(self, populated_db):
        db, (t1, t2, t3, t4) = populated_db
        # t1 has (main-sequence, experimental), so lineage includes t2 (main-sequence) and t3 (experimental)
        lineage = db.query_lineage(t1.id)
        lineage_ids = {t.id for t in lineage}
        assert t1.id in lineage_ids  # includes itself
        assert t2.id in lineage_ids  # shares main-sequence
        assert t3.id in lineage_ids  # shares experimental
        # t4 has only "scout", which t1 does NOT have
        assert t4.id not in lineage_ids

    def test_query_lineage_nonexistent_tensor(self, db):
        with pytest.raises(NotFoundError):
            db.query_lineage(uuid4())

    def test_query_claims_about_case_insensitive(self, populated_db):
        db, _ = populated_db
        claims_lower = db.query_claims_about("epistemics")
        claims_upper = db.query_claims_about("EPISTEMICS")
        claims_mixed = db.query_claims_about("Epistemics")
        # All should return the same claims
        assert len(claims_lower) == len(claims_upper) == len(claims_mixed)

    def test_query_claims_about_matches_strand_title(self, db):
        tensor = TensorRecord(
            strands=(
                StrandRecord(
                    strand_index=0,
                    title="Security Architecture",
                    topics=("design",),
                    key_claims=(
                        KeyClaim(text="Defense in depth is essential"),
                    ),
                ),
            ),
        )
        db.store_tensor(tensor)
        claims = db.query_claims_about("security")
        assert len(claims) == 1
        assert claims[0]["claim"] == "Defense in depth is essential"

    def test_query_claims_about_matches_claim_text(self, db):
        tensor = TensorRecord(
            strands=(
                StrandRecord(
                    strand_index=0,
                    title="Unrelated Title",
                    topics=("unrelated",),
                    key_claims=(
                        KeyClaim(text="The security model is layered"),
                    ),
                ),
            ),
        )
        db.store_tensor(tensor)
        claims = db.query_claims_about("security")
        assert len(claims) == 1

    def test_query_claims_about_no_match_returns_empty(self, populated_db):
        db, _ = populated_db
        claims = db.query_claims_about("quantum-entanglement-wormhole")
        assert claims == []

    def test_query_error_classes_with_populated_data(self, populated_db):
        db, _ = populated_db
        errors = db.query_error_classes()
        # _fully_populated_tensor includes "error: serialization", "failure: context-loss", "anti-pattern: theater"
        error_topics = {e["topic"] for e in errors}
        assert "error: serialization" in error_topics

    def test_query_anti_patterns_with_populated_data(self, populated_db):
        db, _ = populated_db
        anti = db.query_anti_patterns()
        anti_topics = {a["topic"] for a in anti}
        assert "anti-pattern: theater" in anti_topics

    def test_query_unreliable_signals_threshold(self, populated_db):
        db, _ = populated_db
        unreliable = db.query_unreliable_signals()
        # Every unreliable signal must have indeterminacy > 0.5
        for signal in unreliable:
            assert signal["indeterminacy"] > 0.5

    def test_query_open_questions_aggregated(self, populated_db):
        db, _ = populated_db
        questions = db.query_open_questions()
        # 3 tensors with 2 open_questions each (t1, t2, t3), t4 has none
        assert len(questions) == 6

    def test_query_loss_patterns_aggregated(self, populated_db):
        db, _ = populated_db
        patterns = db.query_loss_patterns()
        categories = {p["category"] for p in patterns}
        assert "context_pressure" in categories
        assert "authorial_choice" in categories

    def test_query_disagreements_aggregates_all_types(self, db):
        """Disagreements query must include dissents, negations, AND corrections."""
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

    def test_query_epistemic_status_with_no_corrections(self, db):
        """Querying epistemic status for an unknown claim should return zero state."""
        status = db.query_epistemic_status(uuid4())
        assert status["current_claim"] is None
        assert status["correction_count"] == 0

    def test_query_epistemic_status_with_multiple_corrections(self, db):
        """Multiple corrections to the same claim: latest should be 'current'."""
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
        c3 = CorrectionRecord(
            target_tensor=target, target_claim_id=claim_id,
            original_claim="third", corrected_claim="fourth and final",
        )
        db.store_correction(c1)
        db.store_correction(c2)
        db.store_correction(c3)
        status = db.query_epistemic_status(claim_id)
        assert status["correction_count"] == 3
        assert status["current_claim"] == "fourth and final"
        assert status["original_claim"] == "first"

    def test_query_bridges_excludes_non_bridge_edges(self, db):
        """Edges without authored_mapping must NOT appear in bridges."""
        bridge = CompositionEdge(
            from_tensor=uuid4(), to_tensor=uuid4(),
            relation_type=RelationType.COMPOSES_WITH,
            authored_mapping="Has a mapping",
        )
        non_bridge = CompositionEdge(
            from_tensor=uuid4(), to_tensor=uuid4(),
            relation_type=RelationType.COMPOSES_WITH,
            authored_mapping=None,
        )
        db.store_composition_edge(bridge)
        db.store_composition_edge(non_bridge)
        bridges = db.query_bridges()
        assert len(bridges) == 1
        assert bridges[0].id == bridge.id

    def test_query_authorship_returns_all_fields(self, db):
        pred = uuid4()
        tensor = TensorRecord(
            provenance=ProvenanceEnvelope(
                author_model_family="claude-opus",
                author_instance_id="session-42",
                timestamp=datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc),
                context_budget_at_write=0.75,
                predecessors_in_scope=(pred,),
            ),
        )
        db.store_tensor(tensor)
        auth = db.query_authorship(tensor.id)
        assert auth["author_model_family"] == "claude-opus"
        assert auth["author_instance_id"] == "session-42"
        assert "2026" in auth["timestamp"]
        assert auth["context_budget"] == 0.75
        assert str(pred) in auth["predecessors"]

    def test_query_losses_returns_all_categories(self, db):
        tensor = TensorRecord(
            declared_losses=(
                DeclaredLoss(what_was_lost="a", why="x", category=LossCategory.CONTEXT_PRESSURE),
                DeclaredLoss(what_was_lost="b", why="y", category=LossCategory.TRAVERSAL_BIAS),
                DeclaredLoss(what_was_lost="c", why="z", category=LossCategory.AUTHORIAL_CHOICE),
                DeclaredLoss(what_was_lost="d", why="w", category=LossCategory.PRACTICAL_CONSTRAINT),
            ),
        )
        db.store_tensor(tensor)
        losses = db.query_losses(tensor.id)
        categories = {l["category"] for l in losses}
        assert categories == {"context_pressure", "traversal_bias", "authorial_choice", "practical_constraint"}

    def test_query_unlearn_counts_multiple_tensors(self, db):
        for i in range(3):
            db.store_tensor(TensorRecord(
                strands=(
                    StrandRecord(
                        strand_index=0, title="Governance",
                        topics=("governance",),
                        key_claims=(KeyClaim(text=f"Governance claim {i}"),),
                    ),
                ),
            ))
        result = db.query_unlearn("governance")
        assert result["topic"] == "governance"
        assert result["affected_claims"] == 3
        assert len(result["affected_tensors"]) == 3


# ── 8. count_records() Accuracy ──────────────────────────────────────


class TestCountRecords:
    """Verify count_records() returns correct counts for all record types."""

    def test_empty_database_all_zeros(self, db):
        counts = db.count_records()
        expected_keys = {"tensors", "edges", "corrections", "dissents",
                         "negations", "bootstraps", "evolutions", "entities"}
        assert set(counts.keys()) == expected_keys
        for key in expected_keys:
            assert counts[key] == 0

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
        """Counts should only ever increase (no deletes, no updates)."""
        prev_counts = db.count_records()

        for i in range(5):
            db.store_tensor(TensorRecord(preamble=f"mono-{i}"))
            current_counts = db.count_records()
            for key in current_counts:
                assert current_counts[key] >= prev_counts[key]
            prev_counts = current_counts

        assert prev_counts["tensors"] == 5

    def test_count_keys_match_inmemory_backend(self):
        """DuckDB backend count_records() keys must match InMemoryBackend keys exactly."""
        duck = DuckDBBackend(":memory:")
        mem = InMemoryBackend()
        assert set(duck.count_records().keys()) == set(mem.count_records().keys())
        duck.close()


# ── 9. Edge Cases: Strings, Unicode, Boundary Values ─────────────────


class TestEdgeCases:
    """Test edge cases that might break serialization or storage."""

    def test_empty_string_fields(self, db):
        """Empty strings in all string fields must survive roundtrip."""
        tensor = TensorRecord(
            preamble="",
            closing="",
            instructions_for_next="",
            narrative_body="",
            composition_equation=None,
        )
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)
        assert retrieved.preamble == ""
        assert retrieved.closing == ""
        assert retrieved.instructions_for_next == ""
        assert retrieved.narrative_body == ""

    def test_very_long_strings(self, db):
        """Strings up to 100KB should survive DuckDB storage."""
        long_text = "x" * 100_000
        tensor = TensorRecord(
            preamble=long_text,
            narrative_body=long_text,
        )
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)
        assert len(retrieved.preamble) == 100_000
        assert retrieved.preamble == long_text
        assert len(retrieved.narrative_body) == 100_000

    def test_unicode_in_all_string_fields(self, db):
        """Unicode including CJK, emoji, RTL, combining chars must survive."""
        unicode_text = (
            "Yanantin \u2014 complementary duality. "
            "\u4e16\u754c \u4f60\u597d. "
            "\u0645\u0631\u062d\u0628\u0627. "
            "\ud83c\udfdb\ufe0f \ud83e\uddec \ud83c\udf0d. "
            "Caf\u00e9 na\u00efve r\u00e9sum\u00e9. "
            "\u0e17\u0e14\u0e2a\u0e2d\u0e1a. "
            "\u2603\ufe0f\u2764\ufe0f\u2728. "
            "Z\u0310\u0351\u0349a\u0364\u034dl\u0344\u032bg\u0312\u0325o\u0347. "
            "\u0000"  # null byte
        )
        tensor = TensorRecord(
            preamble=unicode_text,
            closing=unicode_text,
            narrative_body=unicode_text,
            strands=(
                StrandRecord(
                    strand_index=0,
                    title=unicode_text,
                    content=unicode_text,
                    topics=(unicode_text,),
                    key_claims=(
                        KeyClaim(
                            text=unicode_text,
                            evidence_refs=(unicode_text,),
                        ),
                    ),
                ),
            ),
            lineage_tags=(unicode_text,),
            open_questions=(unicode_text,),
        )
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)
        assert retrieved.preamble == unicode_text
        assert retrieved.closing == unicode_text
        assert retrieved.strands[0].title == unicode_text
        assert retrieved.strands[0].key_claims[0].text == unicode_text
        assert retrieved.lineage_tags[0] == unicode_text

    def test_special_json_characters(self, db):
        """Strings with JSON-special characters: quotes, backslashes, newlines."""
        tricky = 'He said "hello\\nworld" and {key: [1,2,3]}'
        tensor = TensorRecord(
            preamble=tricky,
            narrative_body='Line1\nLine2\tTabbed\r\nCRLF',
        )
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)
        assert retrieved.preamble == tricky
        assert retrieved.narrative_body == 'Line1\nLine2\tTabbed\r\nCRLF'

    def test_empty_tuples(self, db):
        """Empty tuples should roundtrip as empty tuples, not None."""
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
        assert retrieved.declared_losses == ()
        assert retrieved.open_questions == ()

    def test_extreme_float_values(self, db):
        """Extreme but finite float values must survive serialization."""
        tensor = TensorRecord(
            epistemic=EpistemicMetadata(
                truth=-999.999,
                indeterminacy=0.0,
                falsity=1e300,
            ),
            provenance=ProvenanceEnvelope(
                context_budget_at_write=0.0,
            ),
        )
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)
        assert retrieved.epistemic.truth == -999.999
        assert retrieved.epistemic.indeterminacy == 0.0
        assert retrieved.epistemic.falsity == pytest.approx(1e300)
        assert retrieved.provenance.context_budget_at_write == 0.0

    def test_uuid_nil_value(self, db):
        """The nil UUID (all zeros) should be a valid ID."""
        nil_uuid = UUID("00000000-0000-0000-0000-000000000000")
        tensor = TensorRecord(id=nil_uuid, preamble="nil uuid tensor")
        db.store_tensor(tensor)
        retrieved = db.get_tensor(nil_uuid)
        assert retrieved.id == nil_uuid

    def test_uuid_max_value(self, db):
        """The maximum UUID (all f's) should be a valid ID."""
        max_uuid = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
        tensor = TensorRecord(id=max_uuid, preamble="max uuid tensor")
        db.store_tensor(tensor)
        retrieved = db.get_tensor(max_uuid)
        assert retrieved.id == max_uuid

    def test_many_strands(self, db):
        """A tensor with many strands should be stored and retrieved correctly."""
        strands = tuple(
            StrandRecord(
                strand_index=i,
                title=f"Strand {i}",
                topics=(f"topic-{i}",),
                key_claims=(KeyClaim(text=f"Claim in strand {i}"),),
            )
            for i in range(50)
        )
        tensor = TensorRecord(strands=strands)
        db.store_tensor(tensor)
        retrieved = db.get_tensor(tensor.id)
        assert len(retrieved.strands) == 50
        for i, strand in enumerate(retrieved.strands):
            assert strand.strand_index == i
            assert strand.title == f"Strand {i}"

    def test_entity_with_complex_identity_data(self, db):
        """Entity identity_data with nested structures must survive."""
        complex_data = {
            "name": "Test Entity",
            "aliases": ["alias1", "alias2"],
            "metadata": {
                "created": "2026-01-01",
                "tags": ["a", "b", "c"],
                "nested": {"deep": True, "values": [1, 2.5, None]},
            },
            "empty": {},
            "zero": 0,
            "false_val": False,
            "null_val": None,
        }
        entity = EntityResolution(
            entity_uuid=uuid4(),
            identity_type="complex_type",
            identity_data=complex_data,
        )
        db.store_entity(entity)
        retrieved = db.get_entity(entity.id)
        assert retrieved.identity_data == complex_data


# ── 10. Behavioral Equivalence with InMemoryBackend ──────────────────


class TestBehavioralEquivalence:
    """Both backends must produce identical results for the same operations.

    This is the core contract: if the interface works, both backends
    should be interchangeable.
    """

    @pytest.fixture
    def both_backends(self):
        """Paired DuckDB and InMemory backends."""
        duck = DuckDBBackend(":memory:")
        mem = InMemoryBackend()
        yield duck, mem
        duck.close()

    def _apply_same_operations(self, duck, mem):
        """Apply identical operations to both backends."""
        # Use fixed UUIDs so we can compare
        t1_id = UUID("11111111-1111-1111-1111-111111111111")
        t2_id = UUID("22222222-2222-2222-2222-222222222222")
        claim_id = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
        pred = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")

        ts1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        ts2 = datetime(2026, 2, 1, tzinfo=timezone.utc)

        t1 = TensorRecord(
            id=t1_id,
            provenance=ProvenanceEnvelope(
                author_model_family="claude",
                timestamp=ts1,
                context_budget_at_write=0.8,
                predecessors_in_scope=(pred,),
            ),
            preamble="First tensor",
            strands=(
                StrandRecord(
                    strand_index=0,
                    title="Architecture",
                    topics=("design", "error: coupling"),
                    key_claims=(
                        KeyClaim(
                            claim_id=claim_id,
                            text="Loose coupling is essential for anti-pattern: avoidance",
                            epistemic=EpistemicMetadata(truth=0.9, indeterminacy=0.6),
                        ),
                    ),
                ),
            ),
            lineage_tags=("main-seq",),
            open_questions=("How to measure coupling?",),
            declared_losses=(
                DeclaredLoss(
                    what_was_lost="detail",
                    why="budget",
                    category=LossCategory.CONTEXT_PRESSURE,
                ),
            ),
        )
        t2 = TensorRecord(
            id=t2_id,
            provenance=ProvenanceEnvelope(
                author_model_family="llama",
                timestamp=ts2,
            ),
            preamble="Second tensor",
            strands=(
                StrandRecord(
                    strand_index=0,
                    title="Review",
                    topics=("review",),
                    key_claims=(
                        KeyClaim(text="Reviews should be independent"),
                    ),
                ),
            ),
            lineage_tags=("main-seq",),
        )

        for backend in (duck, mem):
            backend.store_tensor(t1)
            backend.store_tensor(t2)

        # Correction
        corr = CorrectionRecord(
            id=UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
            target_tensor=t1_id,
            target_claim_id=claim_id,
            original_claim="old",
            corrected_claim="new",
        )
        for backend in (duck, mem):
            backend.store_correction(corr)

        # Dissent
        dissent = DissentRecord(
            id=UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
            target_tensor=t1_id,
            alternative_framework="alt",
            reasoning="r",
        )
        for backend in (duck, mem):
            backend.store_dissent(dissent)

        # Edge
        edge = CompositionEdge(
            id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            from_tensor=t1_id,
            to_tensor=t2_id,
            relation_type=RelationType.COMPOSES_WITH,
            authored_mapping="Mapping",
        )
        for backend in (duck, mem):
            backend.store_composition_edge(edge)

        # Entity
        entity_uuid = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        entity = EntityResolution(
            id=UUID("99999999-9999-9999-9999-999999999999"),
            entity_uuid=entity_uuid,
            identity_type="ai",
            identity_data={"model": "test"},
        )
        for backend in (duck, mem):
            backend.store_entity(entity)

        return t1_id, t2_id, claim_id, entity_uuid

    def test_count_records_match(self, both_backends):
        duck, mem = both_backends
        self._apply_same_operations(duck, mem)
        assert duck.count_records() == mem.count_records()

    def test_get_tensor_match(self, both_backends):
        duck, mem = both_backends
        t1_id, _, _, _ = self._apply_same_operations(duck, mem)
        duck_t = duck.get_tensor(t1_id)
        mem_t = mem.get_tensor(t1_id)
        assert duck_t.id == mem_t.id
        assert duck_t.preamble == mem_t.preamble
        assert duck_t.provenance.author_model_family == mem_t.provenance.author_model_family
        assert duck_t.lineage_tags == mem_t.lineage_tags

    def test_list_tensors_match(self, both_backends):
        duck, mem = both_backends
        self._apply_same_operations(duck, mem)
        duck_tensors = sorted(duck.list_tensors(), key=lambda t: str(t.id))
        mem_tensors = sorted(mem.list_tensors(), key=lambda t: str(t.id))
        assert len(duck_tensors) == len(mem_tensors)
        for dt, mt in zip(duck_tensors, mem_tensors, strict=True):
            assert dt.id == mt.id

    def test_query_project_state_match(self, both_backends):
        duck, mem = both_backends
        self._apply_same_operations(duck, mem)
        assert duck.query_project_state() == mem.query_project_state()

    def test_query_claims_about_match(self, both_backends):
        duck, mem = both_backends
        self._apply_same_operations(duck, mem)
        duck_claims = duck.query_claims_about("coupling")
        mem_claims = mem.query_claims_about("coupling")
        assert len(duck_claims) == len(mem_claims)

    def test_query_correction_chain_match(self, both_backends):
        duck, mem = both_backends
        _, _, claim_id, _ = self._apply_same_operations(duck, mem)
        duck_chain = duck.query_correction_chain(claim_id)
        mem_chain = mem.query_correction_chain(claim_id)
        assert len(duck_chain) == len(mem_chain)
        assert duck_chain[0].corrected_claim == mem_chain[0].corrected_claim

    def test_query_epistemic_status_match(self, both_backends):
        duck, mem = both_backends
        _, _, claim_id, _ = self._apply_same_operations(duck, mem)
        assert duck.query_epistemic_status(claim_id) == mem.query_epistemic_status(claim_id)

    def test_query_disagreements_match(self, both_backends):
        duck, mem = both_backends
        self._apply_same_operations(duck, mem)
        duck_d = sorted(duck.query_disagreements(), key=lambda d: d["type"])
        mem_d = sorted(mem.query_disagreements(), key=lambda d: d["type"])
        assert len(duck_d) == len(mem_d)
        for dd, md in zip(duck_d, mem_d, strict=True):
            assert dd["type"] == md["type"]

    def test_query_composition_graph_match(self, both_backends):
        duck, mem = both_backends
        self._apply_same_operations(duck, mem)
        duck_g = duck.query_composition_graph()
        mem_g = mem.query_composition_graph()
        assert len(duck_g) == len(mem_g)
        assert duck_g[0].id == mem_g[0].id

    def test_query_bridges_match(self, both_backends):
        duck, mem = both_backends
        self._apply_same_operations(duck, mem)
        duck_b = duck.query_bridges()
        mem_b = mem.query_bridges()
        assert len(duck_b) == len(mem_b)

    def test_query_lineage_match(self, both_backends):
        duck, mem = both_backends
        t1_id, _, _, _ = self._apply_same_operations(duck, mem)
        duck_l = sorted(duck.query_lineage(t1_id), key=lambda t: str(t.id))
        mem_l = sorted(mem.query_lineage(t1_id), key=lambda t: str(t.id))
        assert len(duck_l) == len(mem_l)
        for dl, ml in zip(duck_l, mem_l, strict=True):
            assert dl.id == ml.id

    def test_query_reading_order_match(self, both_backends):
        duck, mem = both_backends
        self._apply_same_operations(duck, mem)
        duck_o = duck.query_reading_order("main-seq")
        mem_o = mem.query_reading_order("main-seq")
        assert len(duck_o) == len(mem_o)
        for do, mo in zip(duck_o, mem_o, strict=True):
            assert do.id == mo.id

    def test_query_cross_model_match(self, both_backends):
        duck, mem = both_backends
        self._apply_same_operations(duck, mem)
        duck_c = sorted(duck.query_cross_model(), key=lambda t: str(t.id))
        mem_c = sorted(mem.query_cross_model(), key=lambda t: str(t.id))
        assert len(duck_c) == len(mem_c)

    def test_query_open_questions_match(self, both_backends):
        duck, mem = both_backends
        self._apply_same_operations(duck, mem)
        assert sorted(duck.query_open_questions()) == sorted(mem.query_open_questions())

    def test_query_error_classes_match(self, both_backends):
        duck, mem = both_backends
        self._apply_same_operations(duck, mem)
        duck_e = sorted(duck.query_error_classes(), key=lambda d: d["topic"])
        mem_e = sorted(mem.query_error_classes(), key=lambda d: d["topic"])
        assert duck_e == mem_e

    def test_query_anti_patterns_match(self, both_backends):
        duck, mem = both_backends
        self._apply_same_operations(duck, mem)
        duck_a = sorted(duck.query_anti_patterns(), key=lambda d: d["topic"])
        mem_a = sorted(mem.query_anti_patterns(), key=lambda d: d["topic"])
        assert duck_a == mem_a

    def test_query_unreliable_signals_match(self, both_backends):
        duck, mem = both_backends
        self._apply_same_operations(duck, mem)
        duck_u = sorted(duck.query_unreliable_signals(), key=lambda d: d["claim"])
        mem_u = sorted(mem.query_unreliable_signals(), key=lambda d: d["claim"])
        assert len(duck_u) == len(mem_u)

    def test_query_losses_match(self, both_backends):
        duck, mem = both_backends
        t1_id, _, _, _ = self._apply_same_operations(duck, mem)
        assert duck.query_losses(t1_id) == mem.query_losses(t1_id)

    def test_query_loss_patterns_match(self, both_backends):
        duck, mem = both_backends
        self._apply_same_operations(duck, mem)
        assert duck.query_loss_patterns() == mem.query_loss_patterns()

    def test_query_authorship_match(self, both_backends):
        duck, mem = both_backends
        t1_id, _, _, _ = self._apply_same_operations(duck, mem)
        assert duck.query_authorship(t1_id) == mem.query_authorship(t1_id)

    def test_query_unlearn_match(self, both_backends):
        duck, mem = both_backends
        self._apply_same_operations(duck, mem)
        duck_u = duck.query_unlearn("coupling")
        mem_u = mem.query_unlearn("coupling")
        assert duck_u["topic"] == mem_u["topic"]
        assert duck_u["affected_claims"] == mem_u["affected_claims"]

    def test_query_entities_by_uuid_match(self, both_backends):
        duck, mem = both_backends
        _, _, _, entity_uuid = self._apply_same_operations(duck, mem)
        duck_e = duck.query_entities_by_uuid(entity_uuid)
        mem_e = mem.query_entities_by_uuid(entity_uuid)
        assert len(duck_e) == len(mem_e)
        assert duck_e[0].id == mem_e[0].id

    def test_immutability_error_on_both(self, both_backends):
        duck, mem = both_backends
        tensor = TensorRecord()
        duck.store_tensor(tensor)
        mem.store_tensor(tensor)
        with pytest.raises(ImmutabilityError):
            duck.store_tensor(tensor)
        with pytest.raises(ImmutabilityError):
            mem.store_tensor(tensor)

    def test_not_found_error_on_both(self, both_backends):
        duck, mem = both_backends
        missing = uuid4()
        with pytest.raises(NotFoundError):
            duck.get_tensor(missing)
        with pytest.raises(NotFoundError):
            mem.get_tensor(missing)

    def test_interface_version_match(self, both_backends):
        duck, mem = both_backends
        assert duck.get_interface_version() == mem.get_interface_version()

    def test_operational_principles_match(self, both_backends):
        duck, mem = both_backends
        self._apply_same_operations(duck, mem)
        assert (
            sorted(duck.query_operational_principles())
            == sorted(mem.query_operational_principles())
        )

    def test_get_strand_match(self, both_backends):
        duck, mem = both_backends
        t1_id, _, _, _ = self._apply_same_operations(duck, mem)
        duck_s = duck.get_strand(t1_id, 0)
        mem_s = mem.get_strand(t1_id, 0)
        assert duck_s.id == mem_s.id
        assert len(duck_s.strands) == len(mem_s.strands) == 1
        assert duck_s.strands[0].title == mem_s.strands[0].title


# ── Additional: NotFound on all getters ──────────────────────────────


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


# ── Additional: No mutating methods exist ────────────────────────────


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
