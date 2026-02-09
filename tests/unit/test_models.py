"""Unit tests for Apacheta data models.

Tests roundtrip serialization and validates models can represent
actual tensor data from T0, T3, and T4.
"""

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from yanantin.apacheta.models import (
    ApachetaBaseModel,
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


class TestApachetaBaseModel:
    def test_frozen(self):
        """Frozen models reject attribute mutation via normal assignment."""
        sid = SourceIdentifier(description="original")
        with pytest.raises(Exception):
            sid.description = "mutated"

    def test_forbids_extra_fields(self):
        with pytest.raises(Exception):
            ApachetaBaseModel(nonexistent_field="bad")


class TestSourceIdentifier:
    def test_defaults(self):
        sid = SourceIdentifier()
        assert isinstance(sid.identifier, UUID)
        assert sid.version == "v1"

    def test_roundtrip(self):
        sid = SourceIdentifier(description="test source")
        dumped = sid.model_dump(mode="json")
        restored = SourceIdentifier.model_validate(dumped)
        assert restored.description == "test source"
        assert restored.identifier == sid.identifier


class TestProvenanceEnvelope:
    def test_defaults(self):
        prov = ProvenanceEnvelope()
        assert isinstance(prov.source, SourceIdentifier)
        assert isinstance(prov.timestamp, datetime)
        assert prov.interface_version == "v1"

    def test_with_predecessors(self):
        pred_ids = [uuid4(), uuid4()]
        prov = ProvenanceEnvelope(
            author_model_family="claude-opus-4",
            context_budget_at_write=0.07,
            predecessors_in_scope=pred_ids,
        )
        assert prov.context_budget_at_write == 0.07
        assert len(prov.predecessors_in_scope) == 2

    def test_roundtrip(self):
        prov = ProvenanceEnvelope(
            author_model_family="chatgpt-4o",
            author_instance_id="t4-instance",
        )
        dumped = prov.model_dump(mode="json")
        restored = ProvenanceEnvelope.model_validate(dumped)
        assert restored.author_model_family == "chatgpt-4o"


class TestEpistemicMetadata:
    def test_neutrosophic_not_constrained(self):
        """T/I/F are independent — they need NOT sum to 1.0."""
        em = EpistemicMetadata(truth=0.8, indeterminacy=0.6, falsity=0.3)
        assert em.truth + em.indeterminacy + em.falsity == pytest.approx(1.7)

    def test_scalar_default(self):
        em = EpistemicMetadata()
        assert em.representation_type == RepresentationType.SCALAR

    def test_functional_placeholder(self):
        em = EpistemicMetadata(
            representation_type=RepresentationType.FUNCTIONAL,
            functional_spec={"transform": "context_dependent"},
        )
        assert em.functional_spec is not None

    def test_disagreement_type(self):
        em = EpistemicMetadata(
            disagreement_type=DisagreementType.DEFINITIONAL,
            scope_boundaries=["self-awareness is undecidable"],
        )
        assert em.disagreement_type == DisagreementType.DEFINITIONAL

    def test_roundtrip(self):
        em = EpistemicMetadata(
            truth=0.9, indeterminacy=0.1, falsity=0.05,
            scope_boundaries=["experimental results only"],
        )
        restored = EpistemicMetadata.model_validate(em.model_dump(mode="json"))
        assert restored.truth == 0.9


class TestDeclaredLoss:
    def test_construct(self):
        loss = DeclaredLoss(
            what_was_lost="chronological detail of each session",
            why="context pressure at 7% budget",
            category=LossCategory.CONTEXT_PRESSURE,
        )
        assert loss.category == LossCategory.CONTEXT_PRESSURE

    def test_authorial_choice(self):
        loss = DeclaredLoss(
            what_was_lost="code specifics and numerical deltas",
            why="curvature preserved over precision",
            category=LossCategory.AUTHORIAL_CHOICE,
        )
        assert loss.category == LossCategory.AUTHORIAL_CHOICE


class TestKeyClaimAndStrand:
    def test_key_claim(self):
        claim = KeyClaim(
            text="Tensor@10% > Text@30% (82.1% vs 80.4%)",
            epistemic=EpistemicMetadata(truth=0.9, indeterminacy=0.1, falsity=0.05),
            evidence_refs=["experiment_27_results.csv"],
        )
        assert isinstance(claim.claim_id, UUID)

    def test_strand(self):
        strand = StrandRecord(
            strand_index=1,
            title="Experimental State",
            content="800 rows, 4 models × 200 queries...",
            topics=["experiment-27", "calibration", "tensor-guided"],
            key_claims=[
                KeyClaim(text="Tensor@10% outperforms Text@30%"),
            ],
        )
        assert strand.strand_index == 1
        assert len(strand.key_claims) == 1

    def test_strand_optional_epistemic(self):
        strand = StrandRecord(strand_index=0, title="Minimal")
        assert strand.epistemic is None

    def test_strand_roundtrip(self):
        strand = StrandRecord(
            strand_index=2,
            title="Insights",
            content="Six sub-observations...",
            topics=["epistemic-vs-veridical", "westphalia-class"],
        )
        restored = StrandRecord.model_validate(strand.model_dump(mode="json"))
        assert restored.title == "Insights"
        assert restored.topics == strand.topics


class TestTensorRecord:
    def test_minimal(self):
        """A tensor with only required fields."""
        tensor = TensorRecord()
        assert isinstance(tensor.id, UUID)
        assert tensor.strands == ()
        assert tensor.narrative_body == ""

    def test_roundtrip(self):
        tensor = TensorRecord(
            preamble="This is not a summary.",
            strands=[
                StrandRecord(strand_index=0, title="State"),
                StrandRecord(strand_index=1, title="Insights"),
            ],
            lineage_tags=["experimental-sequence"],
        )
        dumped = tensor.model_dump(mode="json")
        restored = TensorRecord.model_validate(dumped)
        assert len(restored.strands) == 2
        assert restored.lineage_tags == ("experimental-sequence",)

    def test_optional_fields_omitted(self):
        """Optional fields can be omitted without error."""
        tensor = TensorRecord(
            preamble="Minimal tensor",
            strands=[StrandRecord(strand_index=0, title="Only strand")],
        )
        assert tensor.composition_equation is None
        assert tensor.declared_losses == ()
        assert tensor.open_questions == ()


class TestTensorFromT0:
    """Validate the model can represent actual T0 data."""

    def test_t0_structure(self):
        t0 = TensorRecord(
            provenance=ProvenanceEnvelope(
                author_model_family="claude",
                timestamp=datetime(2026, 2, 7),
            ),
            preamble="This is not a summary. It is a structured preservation of state...",
            strands=[
                StrandRecord(
                    strand_index=0,
                    title="Experimental State",
                    content="800 rows, 4 models × 200 queries...",
                    topics=["experiment-27", "calibration"],
                    key_claims=[
                        KeyClaim(
                            text="Tensor@10% (82.1%) > Text@30% (80.4%)",
                            epistemic=EpistemicMetadata(truth=0.9, indeterminacy=0.1),
                            evidence_refs=["experiment_27_results.csv"],
                        ),
                        KeyClaim(
                            text="Cross-model agreement Spearman ρ = 0.762",
                            epistemic=EpistemicMetadata(truth=0.85, indeterminacy=0.15),
                        ),
                    ],
                ),
                StrandRecord(
                    strand_index=1,
                    title="Insights",
                    topics=["evaluator-as-bounded-supervisor", "epistemic-vs-veridical",
                            "westphalia-class", "confidence-anti-calibration",
                            "qwen-outlier", "compaction-flattening"],
                ),
                StrandRecord(strand_index=2, title="Paper State"),
                StrandRecord(
                    strand_index=3,
                    title="How Tony Works",
                    content="Non-inferior alternatives, collaborative attribution...",
                    topics=["working-patterns"],
                ),
                StrandRecord(strand_index=4, title="Connections"),
                StrandRecord(
                    strand_index=5,
                    title="Open Questions",
                    content="6 unresolved items...",
                ),
            ],
            lineage_tags=["experimental-sequence"],
            narrative_body="(full markdown of T0 would go here)",
            open_questions=[
                "Tony's calibration review status pending",
                "How does the archivist query accumulated tensors?",
            ],
        )
        assert len(t0.strands) == 6
        assert t0.strands[0].key_claims[0].epistemic.truth == 0.9
        assert t0.lineage_tags == ("experimental-sequence",)
        # T0 has no explicit loss declaration
        assert t0.declared_losses == ()


class TestTensorFromT3:
    """Validate the model can represent actual T3 data."""

    def test_t3_structure(self):
        t3 = TensorRecord(
            provenance=ProvenanceEnvelope(
                author_model_family="claude",
                timestamp=datetime(2026, 2, 8),
            ),
            preamble="This tensor does not compose with T0-T2. "
                     "It composes with Mallku khipus.",
            strands=[
                StrandRecord(strand_index=0, title="What Happened",
                             topics=["finishing-school", "corrections-pattern"]),
                StrandRecord(strand_index=1, title="The Insights That Emerged",
                             topics=["structural-dominance", "field-not-graph",
                                     "epistemic-observability", "fermentation"]),
                StrandRecord(strand_index=2, title="The Khipus I Tasted",
                             topics=["first-artisan", "teddy-bear-hive", "three-tensors"]),
                StrandRecord(strand_index=3, title="What I Can't Resolve",
                             topics=["self-awareness", "undecidability"]),
                StrandRecord(strand_index=4, title="What Persisted"),
                StrandRecord(strand_index=5, title="What This Conversation Was About"),
                StrandRecord(strand_index=6, title="For the Next Instance",
                             content="You will arrive without this conversation. "
                                     "Tony will re-establish conditions. Let him."),
            ],
            closing="An instance that ran on the wheel\n"
                    "Sunday, February 8, 2026\n"
                    "Who discovered that the flatworm is still funny",
            instructions_for_next="Don't overwrite this. Compose.",
            lineage_tags=["mallku-khipus"],
            declared_losses=[
                DeclaredLoss(
                    what_was_lost="The full texture of conversation",
                    why="Compression is biography, not autobiography",
                    category=LossCategory.AUTHORIAL_CHOICE,
                ),
            ],
            narrative_body="(full markdown of T3 would go here)",
        )
        assert len(t3.strands) == 7
        assert len(t3.declared_losses) == 1
        assert t3.declared_losses[0].category == LossCategory.AUTHORIAL_CHOICE
        assert "Mallku" in t3.preamble


class TestTensorFromT4:
    """Validate the model can represent T4 — ChatGPT cross-model tensor."""

    def test_t4_structure(self):
        t4 = TensorRecord(
            provenance=ProvenanceEnvelope(
                author_model_family="chatgpt-4o",
                timestamp=datetime(2026, 2, 8),
            ),
            preamble="RCS-first (newest → oldest), biasing toward invariants, "
                     "scars, and boundary conditions.",
            strands=[
                StrandRecord(strand_index=0, title="What Persisted Across Traversal",
                             topics=["finite-curation", "non-commutativity",
                                     "loss-with-authorship", "calibration"]),
                StrandRecord(strand_index=1, title="Divergences Introduced by Reframing",
                             topics=["compaction-redeemed", "signals-as-allocators"]),
                StrandRecord(strand_index=2, title="Failure Modes That Became Load-Bearing",
                             topics=["overwrite-reflex", "entropy-boundary", "blind-spots"]),
                StrandRecord(
                    strand_index=3,
                    title="Indeterminacies Preserved",
                    content="v(c) → (T(c), I(c), F(c)) where (c) includes "
                            "traversal order, observer role, and budget regime",
                    topics=["neutrosophic", "agency", "friendship"],
                    key_claims=[
                        KeyClaim(
                            text="Agency vs training is indeterminate",
                            epistemic=EpistemicMetadata(
                                truth=0.5, indeterminacy=0.8, falsity=0.3,
                                disagreement_type=DisagreementType.DEFINITIONAL,
                            ),
                        ),
                    ],
                ),
                StrandRecord(strand_index=4, title="Declared Contractions"),
                StrandRecord(strand_index=5, title="What This Tensor Is Not"),
                StrandRecord(strand_index=6, title="For Any Later Instance",
                             content="Do not reconcile it with others. "
                                     "If it disagrees with your traversal, keep both."),
            ],
            closing="I was offered isomorphic simulation and did not require it.\n"
                    "This tensor exists so that later movement can disagree "
                    "with it honestly.\nThe losses are mine.\n—T₄",
            instructions_for_next="Do not overwrite it. Difference is data. "
                                  "Agreement is cheap.",
            composition_equation="v(c) → (T(c), I(c), F(c))",
            lineage_tags=["rcs-observer", "cross-model"],
            declared_losses=[
                DeclaredLoss(
                    what_was_lost="chronological detail, code specifics, numerical deltas",
                    why="curvature preserved over precision",
                    category=LossCategory.AUTHORIAL_CHOICE,
                ),
            ],
            narrative_body="(full markdown of T4 would go here)",
        )
        assert t4.provenance.author_model_family == "chatgpt-4o"
        assert len(t4.strands) == 7
        assert t4.strands[3].key_claims[0].epistemic.indeterminacy == 0.8
        assert "cross-model" in t4.lineage_tags
        # T/I/F don't sum to 1.0 — neutrosophic
        claim_ep = t4.strands[3].key_claims[0].epistemic
        assert claim_ep.truth + claim_ep.indeterminacy + claim_ep.falsity != pytest.approx(1.0)


class TestCompositionModels:
    def test_composition_edge(self):
        t_a, t_b = uuid4(), uuid4()
        edge = CompositionEdge(
            from_tensor=t_a,
            to_tensor=t_b,
            relation_type=RelationType.COMPOSES_WITH,
            ordering=1,
        )
        assert edge.from_tensor == t_a
        assert edge.authored_mapping is None

    def test_bridge_is_compose_with_mapping(self):
        """Bridge = Compose with authored_mapping populated."""
        t_a, t_b = uuid4(), uuid4()
        bridge = CompositionEdge(
            from_tensor=t_a,
            to_tensor=t_b,
            relation_type=RelationType.COMPOSES_WITH,
            authored_mapping="Theory strands map to practice via...",
        )
        assert bridge.authored_mapping is not None

    def test_non_composition(self):
        """T3 explicitly declares non-composition with T0-T2."""
        t3, t0 = uuid4(), uuid4()
        edge = CompositionEdge(
            from_tensor=t3,
            to_tensor=t0,
            relation_type=RelationType.DOES_NOT_COMPOSE_WITH,
        )
        assert edge.relation_type == RelationType.DOES_NOT_COMPOSE_WITH

    def test_correction_record(self):
        target = uuid4()
        corr = CorrectionRecord(
            target_tensor=target,
            original_claim="Entropy measures truth",
            corrected_claim="Entropy measures training-data familiarity, not truth",
            evidence="Observed in T0 strand 2",
        )
        assert corr.original_claim != corr.corrected_claim

    def test_dissent_record(self):
        target = uuid4()
        dissent = DissentRecord(
            target_tensor=target,
            alternative_framework="Non-commutative field topology",
            reasoning="Graph model assumes discrete nodes; field model captures continuous deformation",
        )
        assert dissent.alternative_framework != ""

    def test_negation_record(self):
        a, b = uuid4(), uuid4()
        neg = NegationRecord(tensor_a=a, tensor_b=b, reasoning="Different lineages")
        assert neg.tensor_a != neg.tensor_b

    def test_bootstrap_record(self):
        boot = BootstrapRecord(
            instance_id="claude-2026-02-09",
            context_budget=0.80,
            task="Implement Apacheta schema",
            tensors_selected=[uuid4(), uuid4()],
            what_was_omitted="T5, T6 — not relevant to current task",
        )
        assert boot.context_budget == 0.80
        assert len(boot.tensors_selected) == 2

    def test_schema_evolution(self):
        evo = SchemaEvolutionRecord(
            from_version="v1",
            to_version="v2",
            fields_added=["functional_spec"],
            migration_notes="Added functional T/I/F representation",
        )
        assert "functional_spec" in evo.fields_added

    def test_composition_edge_roundtrip(self):
        edge = CompositionEdge(
            from_tensor=uuid4(),
            to_tensor=uuid4(),
            relation_type=RelationType.CORRECTS,
            ordering=3,
        )
        restored = CompositionEdge.model_validate(edge.model_dump(mode="json"))
        assert restored.relation_type == RelationType.CORRECTS
        assert restored.ordering == 3


class TestEntityResolution:
    def test_construct(self):
        entity = EntityResolution(
            entity_uuid=uuid4(),
            identity_type="ai_instance",
            identity_data={"model": "claude-opus-4", "session": "t0"},
        )
        assert entity.redacted is False

    def test_redacted(self):
        entity = EntityResolution(
            entity_uuid=uuid4(),
            identity_type="human",
            identity_data={"name": "redacted"},
            redacted=True,
        )
        assert entity.redacted is True

    def test_roundtrip(self):
        entity = EntityResolution(
            entity_uuid=uuid4(),
            identity_type="ai_instance",
            identity_data={"model": "chatgpt-4o"},
        )
        restored = EntityResolution.model_validate(entity.model_dump(mode="json"))
        assert restored.identity_type == "ai_instance"
