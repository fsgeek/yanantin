"""Tests for the Awaq weaver — composition declaration extraction from tensors.

Written by a test author who did not write the code under test.
Tests cover: normalize_tensor_name, extract_tensor_name_from_path,
extract_composition_declarations, discover_tensors, weave_corpus,
and render_graph.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from yanantin.awaq.weaver import (
    CompositionDeclaration,
    TensorFile,
    discover_tensors,
    extract_composition_declarations,
    extract_tensor_name_from_path,
    normalize_tensor_name,
    render_graph,
    weave_corpus,
)

CAIRN_DIR = Path(__file__).resolve().parents[2] / "docs" / "cairn"


# ── normalize_tensor_name ────────────────────────────────────────


class TestNormalizeTensorName:
    """Verify canonical normalization of tensor name variants."""

    def test_unicode_subscript_single_digit(self):
        assert normalize_tensor_name("T\u2080") == "T0"

    def test_unicode_subscript_double_digit(self):
        assert normalize_tensor_name("T\u2081\u2082") == "T12"

    def test_unicode_subscript_all_digits(self):
        """Every subscript digit normalizes correctly."""
        subscripts = "\u2080\u2081\u2082\u2083\u2084\u2085\u2086\u2087\u2088\u2089"
        assert normalize_tensor_name("T" + subscripts) == "T0123456789"

    def test_latex_single_digit(self):
        assert normalize_tensor_name("T_0") == "T0"

    def test_latex_braced_multi_digit(self):
        assert normalize_tensor_name("T_{12}") == "T12"

    def test_latex_braced_single_digit(self):
        assert normalize_tensor_name("T_{5}") == "T5"

    def test_plain_single_digit_unchanged(self):
        assert normalize_tensor_name("T0") == "T0"

    def test_plain_multi_digit_unchanged(self):
        assert normalize_tensor_name("T15") == "T15"

    def test_non_tensor_string_passthrough(self):
        assert normalize_tensor_name("hello") == "hello"

    def test_non_tensor_with_underscore_passthrough(self):
        # A string with _{ but no digits after it should still transform
        # based on the regex — but a plain word should be unchanged.
        assert normalize_tensor_name("word") == "word"

    def test_empty_string(self):
        assert normalize_tensor_name("") == ""


# ── extract_tensor_name_from_path ────────────────────────────────


class TestExtractTensorNameFromPath:
    """Extract canonical tensor name from file paths."""

    def test_modern_naming(self):
        p = Path("docs/cairn/T15_20260212_the_enemy.md")
        assert extract_tensor_name_from_path(p) == "T15"

    def test_modern_naming_single_digit(self):
        p = Path("docs/cairn/T0_20260207_bounded_verification.md")
        assert extract_tensor_name_from_path(p) == "T0"

    def test_modern_naming_double_digit(self):
        p = Path("docs/cairn/T13_20260211_the_gradient.md")
        assert extract_tensor_name_from_path(p) == "T13"

    def test_legacy_first_tensor(self):
        """conversation_tensor_20260207.md is T0."""
        p = Path("docs/cairn/conversation_tensor_20260207.md")
        assert extract_tensor_name_from_path(p) == "T0"

    def test_legacy_session2(self):
        """conversation_tensor_20260207_session2.md is T1."""
        p = Path("docs/cairn/conversation_tensor_20260207_session2.md")
        assert extract_tensor_name_from_path(p) == "T1"

    def test_legacy_session3(self):
        """conversation_tensor_20260207_session3.md is T2."""
        p = Path("docs/cairn/conversation_tensor_20260207_session3.md")
        assert extract_tensor_name_from_path(p) == "T2"

    def test_legacy_explicit_t3(self):
        """conversation_tensor_20260208_t3.md -> T3."""
        p = Path("docs/cairn/conversation_tensor_20260208_t3.md")
        assert extract_tensor_name_from_path(p) == "T3"

    def test_legacy_chatgpt_t4(self):
        p = Path("docs/cairn/conversation_tensor_20260208_chatgpt_t4.md")
        assert extract_tensor_name_from_path(p) == "T4"

    def test_legacy_chatgpt_t5(self):
        p = Path("docs/cairn/conversation_tensor_20260208_chatgpt_t5.md")
        assert extract_tensor_name_from_path(p) == "T5"

    def test_legacy_session2_t6(self):
        p = Path("docs/cairn/conversation_tensor_20260207_session2_t6.md")
        assert extract_tensor_name_from_path(p) == "T6"

    def test_legacy_session2_t7(self):
        p = Path("docs/cairn/conversation_tensor_20260208_session2_t7.md")
        assert extract_tensor_name_from_path(p) == "T7"

    def test_unknown_filename_returns_stem(self):
        """Non-tensor filenames fall through to returning the stem."""
        p = Path("docs/random_file.md")
        assert extract_tensor_name_from_path(p) == "random_file"


# ── extract_composition_declarations ─────────────────────────────


class TestExtractCompositionDeclarations:
    """Test the core composition extraction from synthetic tensor text."""

    def test_composes_with(self):
        text = "This tensor composes with T0 and T1."
        decls = extract_composition_declarations(text, "T2")
        assert len(decls) >= 1
        d = decls[0]
        assert d.relation == "composes_with"
        assert "T0" in d.targets
        assert "T1" in d.targets
        assert d.confidence == "high"
        assert d.source == "T2"

    def test_does_not_compose_with(self):
        text = "This tensor does not compose with T0."
        decls = extract_composition_declarations(text, "T3")
        assert len(decls) >= 1
        d = decls[0]
        assert d.relation == "does_not_compose_with"
        assert "T0" in d.targets
        assert d.confidence == "high"

    def test_doesnt_compose_with_contraction(self):
        text = "This tensor doesn't compose with T5."
        decls = extract_composition_declarations(text, "T4")
        assert len(decls) >= 1
        assert decls[0].relation == "does_not_compose_with"
        assert "T5" in decls[0].targets

    def test_bridge_between(self):
        text = "This is a bridge between T1 and T4."
        decls = extract_composition_declarations(text, "T6")
        assert len(decls) >= 1
        d = decls[0]
        assert d.relation == "bridges"
        assert "T1" in d.targets
        assert "T4" in d.targets

    def test_only_read(self):
        text = "I only read T0 and T14."
        decls = extract_composition_declarations(text, "T15")
        assert len(decls) >= 1
        d = decls[0]
        assert d.relation == "read"
        assert d.targets == ["T0", "T14"]
        assert d.confidence == "high"

    def test_only_read_excludes_prior_refs(self):
        """'only read' should extract targets from after the match only."""
        text = "T1-T7 content (only read T0 and T14)"
        decls = extract_composition_declarations(text, "T15")
        read_decls = [d for d in decls if d.relation == "read" and d.confidence == "high"]
        assert len(read_decls) >= 1
        d = read_decls[0]
        # Should NOT include T1-T7 — only T0 and T14
        assert "T0" in d.targets
        assert "T14" in d.targets
        for i in range(1, 8):
            assert f"T{i}" not in d.targets

    def test_range_expansion(self):
        """T0-T7 should produce 8 targets."""
        text = "I read T0-T7 in one sitting."
        decls = extract_composition_declarations(text, "T9")
        # Should find a read declaration with range expansion
        read_decls = [d for d in decls if d.relation == "read"]
        assert len(read_decls) >= 1
        d = read_decls[0]
        expected = [f"T{i}" for i in range(8)]
        for t in expected:
            assert t in d.targets, f"Expected {t} in targets {d.targets}"
        assert len(d.targets) == 8

    def test_range_expansion_unicode_subscripts(self):
        """T\u2080-T\u2087 should also expand to 8 targets."""
        text = "I read T\u2080\u2013T\u2087 backward."
        decls = extract_composition_declarations(text, "T9")
        read_decls = [d for d in decls if d.relation == "read"]
        assert len(read_decls) >= 1
        d = read_decls[0]
        expected = [f"T{i}" for i in range(8)]
        for t in expected:
            assert t in d.targets

    def test_no_composition_language(self):
        """Text without composition language returns empty list."""
        text = "This is just a regular paragraph about nothing in particular."
        decls = extract_composition_declarations(text, "T0")
        assert decls == []

    def test_self_reference_excluded(self):
        """Source tensor should not appear in its own targets."""
        text = "T5 composes with T3 and T5."
        decls = extract_composition_declarations(text, "T5")
        for d in decls:
            assert "T5" not in d.targets

    def test_read_medium_confidence(self):
        """'read T0' (without 'only') should be medium confidence."""
        text = "I read T0 before writing this."
        decls = extract_composition_declarations(text, "T9")
        read_decls = [d for d in decls if d.relation == "read"]
        assert len(read_decls) >= 1
        assert read_decls[0].confidence == "medium"

    def test_branches_from(self):
        text = "This tensor branches from T3."
        decls = extract_composition_declarations(text, "T8")
        assert len(decls) >= 1
        d = decls[0]
        assert d.relation == "branches_from"
        assert "T3" in d.targets
        assert d.confidence == "high"

    def test_corrects_claim(self):
        text = "This corrects a claim from T2."
        decls = extract_composition_declarations(text, "T5")
        assert len(decls) >= 1
        d = decls[0]
        assert d.relation == "corrects"
        assert "T2" in d.targets
        assert d.confidence == "medium"

    def test_predecessor_declaration(self):
        text = "Predecessor: `T6`"
        decls = extract_composition_declarations(text, "T7")
        assert len(decls) >= 1
        d = decls[0]
        assert d.relation == "composes_with"
        assert "T6" in d.targets
        assert d.confidence == "high"

    def test_successor_to(self):
        text = "This tensor is a successor to T4."
        decls = extract_composition_declarations(text, "T5")
        assert len(decls) >= 1
        d = decls[0]
        assert d.relation == "composes_with"
        assert "T4" in d.targets

    def test_composition_equation(self):
        """T2 = f(T0 + T1 + x2) should compose T2 with T0, T1."""
        text = "T\u2082 = f(T\u2080 + T\u2081 + x\u2082)"
        decls = extract_composition_declarations(text, "T2")
        compose_decls = [d for d in decls if d.relation == "composes_with"]
        assert len(compose_decls) >= 1
        d = compose_decls[0]
        assert "T0" in d.targets
        assert "T1" in d.targets

    def test_composition_equation_wrong_lhs_skipped(self):
        """Equation for a different tensor is not emitted for current tensor."""
        text = "T\u2082 = f(T\u2080 + T\u2081 + x\u2082)"
        decls = extract_composition_declarations(text, "T5")
        compose_eq = [
            d for d in decls
            if d.relation == "composes_with"
            and d.evidence and "f(" in d.evidence
        ]
        assert len(compose_eq) == 0

    def test_evidence_captured(self):
        text = "This tensor composes with T0 and T1."
        decls = extract_composition_declarations(text, "T2")
        assert len(decls) >= 1
        assert "composes with" in decls[0].evidence.lower()

    def test_deduplication(self):
        """Same relation + same targets should not produce duplicate declarations."""
        text = (
            "This composes with T0 and T1.\n"
            "Again, this composes with T0 and T1.\n"
        )
        decls = extract_composition_declarations(text, "T2")
        compose_decls = [d for d in decls if d.relation == "composes_with"]
        # Targets [T0, T1] should appear at most once
        target_sets = [tuple(sorted(d.targets)) for d in compose_decls]
        assert len(target_sets) == len(set(target_sets))

    def test_multiple_relation_types(self):
        """A tensor can declare multiple relation types."""
        text = (
            "This composes with T0.\n"
            "It does not compose with T3.\n"
            "It branches from T1.\n"
        )
        decls = extract_composition_declarations(text, "T5")
        relations = {d.relation for d in decls}
        assert "composes_with" in relations
        assert "does_not_compose_with" in relations
        assert "branches_from" in relations

    def test_didnt_read_becomes_does_not_compose(self):
        text = "I didn't read T4."
        decls = extract_composition_declarations(text, "T10")
        assert len(decls) >= 1
        d = decls[0]
        assert d.relation == "does_not_compose_with"
        assert "T4" in d.targets


# ── discover_tensors ─────────────────────────────────────────────


class TestDiscoverTensors:
    """Test tensor file discovery and deduplication."""

    def test_discovers_tensors_in_cairn(self):
        """discover_tensors finds tensor files in the cairn directory."""
        tensors = discover_tensors(cairn_dir=CAIRN_DIR, sources=["cairn"])
        assert len(tensors) > 0

    def test_all_tensors_have_tensor_names(self):
        tensors = discover_tensors(cairn_dir=CAIRN_DIR, sources=["cairn"])
        for t in tensors:
            assert t.tensor_name.startswith("T")

    def test_all_tensors_have_raw_text(self):
        tensors = discover_tensors(cairn_dir=CAIRN_DIR, sources=["cairn"])
        for t in tensors:
            assert len(t.raw_text) > 0

    def test_sorted_by_tensor_number(self):
        tensors = discover_tensors(cairn_dir=CAIRN_DIR, sources=["cairn"])
        import re

        numbers = []
        for t in tensors:
            m = re.match(r"T(\d+)", t.tensor_name)
            if m:
                numbers.append(int(m.group(1)))
        assert numbers == sorted(numbers)

    def test_deduplication_by_canonical_name(self, tmp_path: Path):
        """If both old and new naming exist for the same tensor,
        discover_tensors should only count it once."""
        # Create two files that map to the same tensor name
        modern = tmp_path / "T0_20260207_test.md"
        legacy = tmp_path / "conversation_tensor_20260207.md"
        modern.write_text("# Modern T0", encoding="utf-8")
        legacy.write_text("# Legacy T0", encoding="utf-8")

        tensors = discover_tensors(cairn_dir=tmp_path, sources=["cairn"])
        names = [t.tensor_name for t in tensors]
        assert names.count("T0") == 1

    def test_skips_non_tensor_files(self, tmp_path: Path):
        """Non-tensor markdown files are ignored."""
        (tmp_path / "README.md").write_text("# Not a tensor", encoding="utf-8")
        (tmp_path / "T1_20260207_test.md").write_text("# Tensor", encoding="utf-8")

        tensors = discover_tensors(cairn_dir=tmp_path, sources=["cairn"])
        assert len(tensors) == 1
        assert tensors[0].tensor_name == "T1"

    def test_skips_hidden_files(self, tmp_path: Path):
        (tmp_path / ".T1_hidden.md").write_text("# Hidden", encoding="utf-8")
        tensors = discover_tensors(cairn_dir=tmp_path, sources=["cairn"])
        assert len(tensors) == 0

    def test_empty_directory(self, tmp_path: Path):
        tensors = discover_tensors(cairn_dir=tmp_path, sources=["cairn"])
        assert tensors == []

    def test_nonexistent_source_ignored(self, tmp_path: Path):
        """Non-existent source paths are silently skipped."""
        tensors = discover_tensors(
            cairn_dir=tmp_path / "no_such_dir",
            sources=["cairn"],
        )
        assert tensors == []

    def test_tensor_file_display_name(self):
        tf = TensorFile(
            path=Path("docs/cairn/T15_20260212_the_enemy.md"),
            source_name="cairn",
            tensor_name="T15",
            raw_text="content",
        )
        assert tf.display_name == "T15 (T15_20260212_the_enemy.md)"


# ── weave_corpus ─────────────────────────────────────────────────


class TestWeaveCorpus:
    """Integration-style tests: run against the actual cairn."""

    def test_returns_nonempty_list(self):
        decls = weave_corpus(cairn_dir=CAIRN_DIR, sources=["cairn"])
        assert len(decls) > 0

    def test_declarations_have_required_fields(self):
        decls = weave_corpus(cairn_dir=CAIRN_DIR, sources=["cairn"])
        for d in decls:
            assert isinstance(d.source, str) and d.source
            assert isinstance(d.targets, list) and len(d.targets) > 0
            assert d.relation in {
                "composes_with",
                "does_not_compose_with",
                "corrects",
                "bridges",
                "branches_from",
                "read",
            }
            assert isinstance(d.evidence, str) and d.evidence
            assert d.confidence in {"high", "medium", "low"}

    def test_sources_are_tensor_names(self):
        decls = weave_corpus(cairn_dir=CAIRN_DIR, sources=["cairn"])
        for d in decls:
            assert d.source.startswith("T")

    def test_targets_are_tensor_names(self):
        decls = weave_corpus(cairn_dir=CAIRN_DIR, sources=["cairn"])
        for d in decls:
            for t in d.targets:
                assert t.startswith("T")

    def test_synthetic_corpus(self, tmp_path: Path):
        """weave_corpus on a synthetic cairn extracts the expected relation."""
        tensor_file = tmp_path / "T5_20260212_test.md"
        tensor_file.write_text(
            "# T5\n\nThis tensor composes with T0 and T1.\n",
            encoding="utf-8",
        )
        decls = weave_corpus(cairn_dir=tmp_path, sources=["cairn"])
        assert len(decls) >= 1
        assert decls[0].source == "T5"
        assert "T0" in decls[0].targets
        assert "T1" in decls[0].targets


# ── render_graph ─────────────────────────────────────────────────


class TestRenderGraph:
    """Test the human-readable graph renderer."""

    def test_empty_declarations(self):
        output = render_graph([])
        assert output == "No composition declarations found."

    def test_nonempty_output(self):
        decls = [
            CompositionDeclaration(
                source="T0",
                targets=["T1"],
                relation="composes_with",
                evidence="T0 composes with T1",
                confidence="high",
            ),
        ]
        output = render_graph(decls)
        assert len(output) > 0

    def test_contains_section_header(self):
        decls = [
            CompositionDeclaration(
                source="T0",
                targets=["T1"],
                relation="composes_with",
                evidence="T0 composes with T1",
                confidence="high",
            ),
        ]
        output = render_graph(decls)
        assert "Composes With" in output

    def test_contains_tensor_names(self):
        decls = [
            CompositionDeclaration(
                source="T5",
                targets=["T3", "T4"],
                relation="bridges",
                evidence="bridge between T3 and T4",
                confidence="high",
            ),
        ]
        output = render_graph(decls)
        assert "T5" in output
        assert "T3" in output
        assert "T4" in output

    def test_contains_composition_graph_title(self):
        decls = [
            CompositionDeclaration(
                source="T0",
                targets=["T1"],
                relation="read",
                evidence="read T1",
                confidence="medium",
            ),
        ]
        output = render_graph(decls)
        assert "Composition Graph" in output

    def test_multiple_relation_types_rendered(self):
        decls = [
            CompositionDeclaration(
                source="T0",
                targets=["T1"],
                relation="composes_with",
                evidence="composes with T1",
                confidence="high",
            ),
            CompositionDeclaration(
                source="T2",
                targets=["T3"],
                relation="does_not_compose_with",
                evidence="does not compose with T3",
                confidence="high",
            ),
            CompositionDeclaration(
                source="T4",
                targets=["T5"],
                relation="read",
                evidence="read T5",
                confidence="medium",
            ),
        ]
        output = render_graph(decls)
        assert "Composes With" in output
        assert "Does Not Compose With" in output
        assert "Read" in output

    def test_confidence_summary(self):
        decls = [
            CompositionDeclaration(
                source="T0",
                targets=["T1"],
                relation="composes_with",
                evidence="composes with T1",
                confidence="high",
            ),
            CompositionDeclaration(
                source="T2",
                targets=["T3"],
                relation="read",
                evidence="read T3",
                confidence="medium",
            ),
        ]
        output = render_graph(decls)
        assert "Confidence:" in output
        assert "1 high" in output
        assert "1 medium" in output

    def test_edge_count_in_output(self):
        decls = [
            CompositionDeclaration(
                source="T0",
                targets=["T1"],
                relation="composes_with",
                evidence="composes with T1",
                confidence="high",
            ),
        ]
        output = render_graph(decls)
        assert "1 declarations" in output or "Edges: 1" in output

    def test_bridges_section_header(self):
        decls = [
            CompositionDeclaration(
                source="T6",
                targets=["T1", "T4"],
                relation="bridges",
                evidence="bridge between T1 and T4",
                confidence="high",
            ),
        ]
        output = render_graph(decls)
        assert "Bridges" in output

    def test_branches_from_section_header(self):
        decls = [
            CompositionDeclaration(
                source="T8",
                targets=["T3"],
                relation="branches_from",
                evidence="branches from T3",
                confidence="high",
            ),
        ]
        output = render_graph(decls)
        assert "Branches From" in output
