"""Tests for Awaq materializer — wiring declarations into Apacheta edges.

Tests the full pipeline: label extraction, declaration→edge conversion,
and materialization through an InMemoryBackend. No ArangoDB or network.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.apacheta.models.composition import CompositionEdge, NegationRecord, RelationType
from yanantin.awaq.materialize import (
    MaterializeResult,
    declarations_to_edges,
    discover_cairn_tensors,
    ensure_tensors_stored,
    extract_label,
    materialize,
)
from yanantin.awaq.weaver import CompositionDeclaration

# ── Project paths ────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CAIRN_DIR = PROJECT_ROOT / "docs" / "cairn"


# ── extract_label ────────────────────────────────────────────────


class TestExtractLabel:
    """Label extraction from cairn filenames."""

    def test_known_metadata_t0(self):
        p = Path("T0_20260207_bounded_verification.md")
        assert extract_label(p) == "T0"

    def test_known_metadata_t7(self):
        p = Path("T7_20260208_the_wanderer.md")
        assert extract_label(p) == "T7"

    def test_unknown_modern_t9(self):
        p = Path("T9_20260210_the_wheel.md")
        assert extract_label(p) == "T9"

    def test_unknown_modern_t16(self):
        p = Path("T16_20260215_the_builder.md")
        assert extract_label(p) == "T16"

    def test_legacy_naming_falls_through(self):
        """Legacy names not matching T{N}_ pattern use path.stem."""
        p = Path("some_other_file.md")
        assert extract_label(p) == "some_other_file"

    def test_two_digit_number(self):
        p = Path("T12_20260210_the_fortress.md")
        assert extract_label(p) == "T12"


# ── discover_cairn_tensors ───────────────────────────────────────


class TestDiscoverCairnTensors:
    """Tests that cairn discovery finds and labels tensors."""

    def test_finds_tensors_in_cairn(self):
        label_map = discover_cairn_tensors(CAIRN_DIR)
        assert len(label_map) >= 15  # T0-T7, T9-T16 (no T8)

    def test_t0_present(self):
        label_map = discover_cairn_tensors(CAIRN_DIR)
        assert "T0" in label_map

    def test_t16_present(self):
        label_map = discover_cairn_tensors(CAIRN_DIR)
        assert "T16" in label_map

    def test_t8_absent(self):
        """T8 is intentionally unwritten."""
        label_map = discover_cairn_tensors(CAIRN_DIR)
        assert "T8" not in label_map

    def test_records_have_valid_uuids(self):
        label_map = discover_cairn_tensors(CAIRN_DIR)
        for label, (filename, tensor) in label_map.items():
            assert isinstance(tensor.id, UUID)

    def test_deduplicates_by_label(self):
        """Each label should appear exactly once."""
        label_map = discover_cairn_tensors(CAIRN_DIR)
        # If there were duplicates, they'd be collapsed
        assert len(set(label_map.keys())) == len(label_map)


# ── declarations_to_edges ────────────────────────────────────────


class TestDeclarationsToEdges:
    """Convert Awaq declarations to typed edge objects."""

    @pytest.fixture()
    def uuid_map(self):
        return {
            "T0": UUID("00000000-0000-0000-0000-000000000000"),
            "T1": UUID("11111111-1111-1111-1111-111111111111"),
            "T2": UUID("22222222-2222-2222-2222-222222222222"),
        }

    def test_composes_with_creates_edge(self, uuid_map):
        decls = [CompositionDeclaration(
            source="T1",
            targets=["T0"],
            relation="composes_with",
            evidence="Predecessor: T₀",
            confidence="high",
        )]
        edges, negations, unknown = declarations_to_edges(decls, uuid_map)
        assert len(edges) == 1
        assert len(negations) == 0
        assert edges[0].relation_type == RelationType.COMPOSES_WITH
        assert edges[0].from_tensor == uuid_map["T1"]
        assert edges[0].to_tensor == uuid_map["T0"]

    def test_does_not_compose_creates_negation(self, uuid_map):
        decls = [CompositionDeclaration(
            source="T1",
            targets=["T2"],
            relation="does_not_compose_with",
            evidence="T1 hasn't read T2",
            confidence="medium",
        )]
        edges, negations, unknown = declarations_to_edges(decls, uuid_map)
        assert len(edges) == 0
        assert len(negations) == 1
        assert negations[0].tensor_a == uuid_map["T1"]
        assert negations[0].tensor_b == uuid_map["T2"]

    def test_bridges_creates_bridges_edge(self, uuid_map):
        decls = [CompositionDeclaration(
            source="T0",
            targets=["T1"],
            relation="bridges",
            evidence="Connects lineages",
            confidence="low",
        )]
        edges, negations, unknown = declarations_to_edges(decls, uuid_map)
        assert len(edges) == 1
        assert edges[0].relation_type == RelationType.BRIDGES
        assert edges[0].authored_mapping is not None

    def test_read_creates_composes_with_mapping(self, uuid_map):
        decls = [CompositionDeclaration(
            source="T1",
            targets=["T0"],
            relation="read",
            evidence="Read T0 mid-session",
            confidence="medium",
        )]
        edges, negations, unknown = declarations_to_edges(decls, uuid_map)
        assert len(edges) == 1
        assert edges[0].relation_type == RelationType.COMPOSES_WITH
        assert edges[0].authored_mapping == "Read T0 mid-session"

    def test_corrects_creates_corrects_edge(self, uuid_map):
        decls = [CompositionDeclaration(
            source="T2",
            targets=["T0"],
            relation="corrects",
            evidence="Corrects T0's calibration",
            confidence="high",
        )]
        edges, negations, unknown = declarations_to_edges(decls, uuid_map)
        assert len(edges) == 1
        assert edges[0].relation_type == RelationType.CORRECTS

    def test_unknown_source_skipped(self, uuid_map):
        decls = [CompositionDeclaration(
            source="T99",
            targets=["T0"],
            relation="composes_with",
            evidence="test",
            confidence="low",
        )]
        edges, negations, unknown = declarations_to_edges(decls, uuid_map)
        assert len(edges) == 0
        assert "T99" in unknown

    def test_unknown_target_skipped(self, uuid_map):
        decls = [CompositionDeclaration(
            source="T0",
            targets=["T99"],
            relation="composes_with",
            evidence="test",
            confidence="low",
        )]
        edges, negations, unknown = declarations_to_edges(decls, uuid_map)
        assert len(edges) == 0
        assert "T99" in unknown

    def test_multiple_targets_expand(self, uuid_map):
        decls = [CompositionDeclaration(
            source="T0",
            targets=["T1", "T2"],
            relation="composes_with",
            evidence="Composes with both",
            confidence="high",
        )]
        edges, negations, unknown = declarations_to_edges(decls, uuid_map)
        assert len(edges) == 2
        targets = {e.to_tensor for e in edges}
        assert uuid_map["T1"] in targets
        assert uuid_map["T2"] in targets

    def test_provenance_set_on_edges(self, uuid_map):
        decls = [CompositionDeclaration(
            source="T0",
            targets=["T1"],
            relation="composes_with",
            evidence="test",
            confidence="high",
        )]
        edges, _, _ = declarations_to_edges(decls, uuid_map)
        assert edges[0].provenance.author_model_family == "awaq"
        assert edges[0].provenance.author_instance_id == "materializer-v1"

    def test_empty_declarations_produce_nothing(self, uuid_map):
        edges, negations, unknown = declarations_to_edges([], uuid_map)
        assert len(edges) == 0
        assert len(negations) == 0
        assert len(unknown) == 0


# ── ensure_tensors_stored ────────────────────────────────────────


class TestEnsureTensorsStored:
    """Storing tensors and building label→UUID map."""

    def test_stores_in_empty_backend(self):
        backend = InMemoryBackend()
        label_map = discover_cairn_tensors(CAIRN_DIR)
        uuid_map, stored, skipped = ensure_tensors_stored(backend, label_map)
        assert stored > 0
        assert len(uuid_map) == len(label_map)

    def test_skips_already_stored(self):
        backend = InMemoryBackend()
        label_map = discover_cairn_tensors(CAIRN_DIR)
        # Store once
        ensure_tensors_stored(backend, label_map)
        # Store again — should skip all
        # Need fresh label_map with same tensor objects
        _, stored, skipped = ensure_tensors_stored(backend, label_map)
        assert stored == 0
        assert skipped == len(label_map)

    def test_uuid_map_contains_all_labels(self):
        backend = InMemoryBackend()
        label_map = discover_cairn_tensors(CAIRN_DIR)
        uuid_map, _, _ = ensure_tensors_stored(backend, label_map)
        for label in label_map:
            assert label in uuid_map
            assert isinstance(uuid_map[label], UUID)


# ── Full materialize pipeline ────────────────────────────────────


class TestMaterialize:
    """End-to-end materialization with InMemoryBackend."""

    def test_materialize_produces_edges(self):
        from yanantin.awaq.weaver import weave_corpus
        backend = InMemoryBackend()
        decls = weave_corpus()
        result = materialize(backend, decls, CAIRN_DIR)
        assert isinstance(result, MaterializeResult)
        assert result.edges_stored > 0

    def test_materialize_produces_negations(self):
        from yanantin.awaq.weaver import weave_corpus
        backend = InMemoryBackend()
        decls = weave_corpus()
        result = materialize(backend, decls, CAIRN_DIR)
        assert result.negations_stored > 0

    def test_t8_is_only_unknown(self):
        from yanantin.awaq.weaver import weave_corpus
        backend = InMemoryBackend()
        decls = weave_corpus()
        result = materialize(backend, decls, CAIRN_DIR)
        # T8 is intentionally unwritten — should be the only unknown
        assert result.skipped_unknown == ["T8"] or result.skipped_unknown == []

    def test_composition_graph_queryable(self):
        from yanantin.awaq.weaver import weave_corpus
        backend = InMemoryBackend()
        decls = weave_corpus()
        materialize(backend, decls, CAIRN_DIR)
        graph = backend.query_composition_graph()
        assert len(graph) > 0
        assert all(isinstance(e, CompositionEdge) for e in graph)

    def test_idempotent_materialization(self):
        from yanantin.awaq.weaver import weave_corpus
        backend = InMemoryBackend()
        decls = weave_corpus()
        r1 = materialize(backend, decls, CAIRN_DIR)
        # Second run should skip everything
        r2 = materialize(backend, decls, CAIRN_DIR)
        assert r2.tensors_stored == 0
        assert r2.tensors_skipped == r1.tensors_stored + r1.tensors_skipped

    def test_all_stored_tensors_retrievable(self):
        from yanantin.awaq.weaver import weave_corpus
        backend = InMemoryBackend()
        decls = weave_corpus()
        materialize(backend, decls, CAIRN_DIR)
        tensors = backend.list_tensors()
        assert len(tensors) >= 15
