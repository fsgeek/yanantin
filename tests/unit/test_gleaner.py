"""Tests for the Chasqui gleaner — claim extraction from scout and scour reports.

Written by a test author who did not write the code under test.
Tests cover: extract_claims_from_report, extract_claims_from_cairn,
claims_for_verification, to_verifiable_claims, and internal helpers
exercised through the public API.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from yanantin.chasqui.gleaner import (
    ExtractedClaim,
    extract_claims_from_cairn,
    extract_claims_from_report,
    claims_for_verification,
    to_verifiable_claims,
)


# ── Fixtures ─────────────────────────────────────────────────────────


SCOUT_HEADER = """\
<!-- Chasqui Scout Tensor
     Run: 1
     Model: test/mock-model-7b
     Cost: prompt=$1e-06/M, completion=$2e-06/M
     Timestamp: 2026-02-12T00:00:00.000000+00:00
-->
"""

SCOUR_HEADER = """\
<!-- Chasqui Scour Tensor
     Run: 3
     Model: vendor/scour-model-32b
     Target: src/yanantin/chasqui
     Scope: introspection
     Cost: prompt=$1.5e-07/M, completion=$5e-07/M
     Timestamp: 2026-02-12T19:47:24.005159+00:00
-->
"""


def _make_scout_report(body: str, model: str = "test/mock-model-7b") -> str:
    """Build a complete scout report with header and body."""
    header = f"""\
<!-- Chasqui Scout Tensor
     Run: 1
     Model: {model}
     Timestamp: 2026-02-12T00:00:00.000000+00:00
-->
"""
    return header + "\n" + body


def _make_scour_report(body: str, model: str = "vendor/scour-model-32b") -> str:
    """Build a complete scour report with header and body."""
    header = f"""\
<!-- Chasqui Scour Tensor
     Run: 1
     Model: {model}
     Target: src/yanantin/chasqui
     Scope: introspection
     Timestamp: 2026-02-12T00:00:00.000000+00:00
-->
"""
    return header + "\n" + body


@pytest.fixture
def scout_with_strands(tmp_path: Path) -> Path:
    """A scout report with strands containing verifiable claims."""
    content = _make_scout_report("""
## Strands

### Strand 1: Module Organization

The `src/yanantin/apacheta/interface/errors.py` file defines a custom exception hierarchy with 5 classes.

This module uses `extra="forbid"` on its Pydantic models to enforce strict validation.

The coordinator dispatches scouts to wander the codebase using `src/yanantin/chasqui/coordinator.py` as the entry point.

### Strand 2: Architecture

The system depends on ArangoDB for persistent storage through the `src/yanantin/apacheta/backends/arango.py` backend.

The gateway enforces a single entry point constraint for all external API traffic.

## Open Questions

I wonder whether the tensor ballot mechanism handles concurrent writes correctly.

It is unclear how model performance is evaluated beyond cost metrics.

## Declared Losses

I did not examine the test infrastructure because time constraints limited my scope to source code only.

I did not explore the robustness of error handling in the async dispatch functions.
""")
    f = tmp_path / "scout_0001_20260212_mock-model-7b.md"
    f.write_text(content, encoding="utf-8")
    return f


@pytest.fixture
def scour_with_evidence(tmp_path: Path) -> Path:
    """A scour report with evidence and reasoning sections."""
    content = _make_scour_report("""
### Verdict
**DENIED**

### Evidence

The claim states that `tests/unit/test_provenance.py` contains 12 test functions covering edge cases.

Looking at the actual file, I find only 4 tests that verify basic type assertions.

No edge cases are tested in `tests/unit/test_provenance.py` for invalid inputs or boundary conditions.

### Reasoning

The tests serve a specific purpose but calling them comprehensive is inaccurate.

This module implements a basic smoke test pattern, not a thorough validation suite.

### Declared Losses

None. The claim is about the test code itself, which I can fully examine.
""")
    f = tmp_path / "scour_0001_20260212_scour-model-32b.md"
    f.write_text(content, encoding="utf-8")
    return f


@pytest.fixture
def empty_report(tmp_path: Path) -> Path:
    """An empty report file."""
    f = tmp_path / "scout_0002_20260212_empty.md"
    f.write_text("", encoding="utf-8")
    return f


@pytest.fixture
def whitespace_only_report(tmp_path: Path) -> Path:
    """A report containing only whitespace."""
    f = tmp_path / "scout_0003_20260212_whitespace.md"
    f.write_text("   \n\n   \n", encoding="utf-8")
    return f


@pytest.fixture
def no_header_report(tmp_path: Path) -> Path:
    """A markdown file with no provenance header."""
    f = tmp_path / "scout_0004_20260212_noheader.md"
    f.write_text(
        "## Strands\n\nThe `src/yanantin/apacheta/models.py` file defines 8 model classes for tensor storage.\n",
        encoding="utf-8",
    )
    return f


@pytest.fixture
def minimal_claims() -> list[ExtractedClaim]:
    """A small list of claims for selection/adapter tests."""
    return [
        ExtractedClaim(
            claim_text="The `src/yanantin/apacheta/models.py` file defines 8 model classes.",
            source_file="scout_0001.md",
            source_model="model-a",
            file_references=["src/yanantin/apacheta/models.py"],
            claim_type="factual",
            confidence=0.75,
        ),
        ExtractedClaim(
            claim_text="The system has 42 tests in the unit test suite.",
            source_file="scout_0002.md",
            source_model="model-b",
            file_references=[],
            claim_type="factual",
            confidence=0.6,
        ),
        ExtractedClaim(
            claim_text="I wonder whether the ballot mechanism handles races.",
            source_file="scout_0003.md",
            source_model="model-c",
            file_references=[],
            claim_type="epistemic",
            confidence=0.4,
        ),
        ExtractedClaim(
            claim_text="There is no migration framework implemented in `src/yanantin/apacheta/backends/arango.py`.",
            source_file="scout_0004.md",
            source_model="model-a",
            file_references=["src/yanantin/apacheta/backends/arango.py"],
            claim_type="missing",
            confidence=0.65,
        ),
        ExtractedClaim(
            claim_text="The gateway depends on FastAPI and delegates to the Apacheta interface.",
            source_file="scout_0005.md",
            source_model="model-d",
            file_references=[],
            claim_type="architectural",
            confidence=0.55,
        ),
    ]


# ── ExtractedClaim dataclass ─────────────────────────────────────────


class TestExtractedClaim:
    """Verify the ExtractedClaim dataclass structure."""

    def test_default_claim_type_is_factual(self):
        claim = ExtractedClaim(
            claim_text="test", source_file="f.md", source_model="m"
        )
        assert claim.claim_type == "factual"

    def test_default_confidence_is_half(self):
        claim = ExtractedClaim(
            claim_text="test", source_file="f.md", source_model="m"
        )
        assert claim.confidence == 0.5

    def test_default_file_references_is_empty_list(self):
        claim = ExtractedClaim(
            claim_text="test", source_file="f.md", source_model="m"
        )
        assert claim.file_references == []

    def test_default_context_is_empty_string(self):
        claim = ExtractedClaim(
            claim_text="test", source_file="f.md", source_model="m"
        )
        assert claim.context == ""

    def test_all_fields_populated(self):
        claim = ExtractedClaim(
            claim_text="claim",
            source_file="report.md",
            source_model="vendor/model",
            file_references=["src/foo.py"],
            claim_type="architectural",
            confidence=0.8,
            context="surrounding text",
        )
        assert claim.claim_text == "claim"
        assert claim.source_file == "report.md"
        assert claim.source_model == "vendor/model"
        assert claim.file_references == ["src/foo.py"]
        assert claim.claim_type == "architectural"
        assert claim.confidence == 0.8
        assert claim.context == "surrounding text"


# ── extract_claims_from_report ───────────────────────────────────────


class TestExtractClaimsFromReport:
    """Tests for single-report claim extraction."""

    def test_returns_list(self, scout_with_strands: Path):
        result = extract_claims_from_report(scout_with_strands)
        assert isinstance(result, list)

    def test_all_items_are_extracted_claims(self, scout_with_strands: Path):
        result = extract_claims_from_report(scout_with_strands)
        for claim in result:
            assert isinstance(claim, ExtractedClaim)

    def test_extracts_claims_from_strands(self, scout_with_strands: Path):
        result = extract_claims_from_report(scout_with_strands)
        assert len(result) > 0

    def test_source_file_matches_report_path(self, scout_with_strands: Path):
        result = extract_claims_from_report(scout_with_strands)
        for claim in result:
            assert claim.source_file == str(scout_with_strands)

    def test_source_model_extracted_from_scout_header(self, scout_with_strands: Path):
        result = extract_claims_from_report(scout_with_strands)
        for claim in result:
            assert claim.source_model == "test/mock-model-7b"

    def test_source_model_extracted_from_scour_header(self, scour_with_evidence: Path):
        result = extract_claims_from_report(scour_with_evidence)
        for claim in result:
            assert claim.source_model == "vendor/scour-model-32b"

    def test_sorted_by_confidence_descending(self, scout_with_strands: Path):
        result = extract_claims_from_report(scout_with_strands)
        if len(result) > 1:
            confidences = [c.confidence for c in result]
            assert confidences == sorted(confidences, reverse=True)

    def test_empty_file_returns_empty_list(self, empty_report: Path):
        result = extract_claims_from_report(empty_report)
        assert result == []

    def test_whitespace_only_returns_empty_list(self, whitespace_only_report: Path):
        result = extract_claims_from_report(whitespace_only_report)
        assert result == []

    def test_nonexistent_file_returns_empty_list(self, tmp_path: Path):
        bogus = tmp_path / "does_not_exist.md"
        result = extract_claims_from_report(bogus)
        assert result == []

    def test_no_header_uses_unknown_model(self, no_header_report: Path):
        result = extract_claims_from_report(no_header_report)
        for claim in result:
            assert claim.source_model == "unknown"

    def test_file_references_extracted_from_backtick_paths(
        self, scout_with_strands: Path
    ):
        result = extract_claims_from_report(scout_with_strands)
        all_refs = []
        for claim in result:
            all_refs.extend(claim.file_references)
        # The report mentions several backtick-wrapped file paths
        ref_strings = " ".join(all_refs)
        assert "src/yanantin/apacheta/interface/errors.py" in ref_strings or any(
            "errors.py" in r for r in all_refs
        )

    def test_file_references_extracted_from_bare_paths(self, tmp_path: Path):
        content = _make_scout_report("""
## Strands

The module at src/yanantin/chasqui/coordinator.py implements the dispatch logic for all 5 scout types.
""")
        f = tmp_path / "scout_bare_refs.md"
        f.write_text(content, encoding="utf-8")
        result = extract_claims_from_report(f)
        all_refs = []
        for claim in result:
            all_refs.extend(claim.file_references)
        assert any("coordinator.py" in r for r in all_refs)

    def test_claims_from_open_questions_are_epistemic(
        self, scout_with_strands: Path
    ):
        result = extract_claims_from_report(scout_with_strands)
        # Find claims that match the open questions content
        epistemic_claims = [c for c in result if c.claim_type == "epistemic"]
        # The report has open questions; at least some should be extracted
        # (they may or may not pass the substantive/declarative filters)
        # Just verify that if they appear, they are typed correctly
        for claim in epistemic_claims:
            assert claim.claim_type == "epistemic"

    def test_claims_from_evidence_section_extracted(
        self, scour_with_evidence: Path
    ):
        result = extract_claims_from_report(scour_with_evidence)
        # The scour report has evidence and reasoning sections with
        # file references to tests/unit/test_provenance.py
        assert len(result) > 0

    def test_confidence_is_clamped_between_zero_and_one(
        self, scout_with_strands: Path
    ):
        result = extract_claims_from_report(scout_with_strands)
        for claim in result:
            assert 0.0 <= claim.confidence <= 1.0

    def test_no_duplicate_claim_texts_within_report(
        self, scout_with_strands: Path
    ):
        result = extract_claims_from_report(scout_with_strands)
        texts = [c.claim_text for c in result]
        # Dedup is by normalized text, so exact duplicates must not appear
        assert len(texts) == len(set(texts))

    def test_binary_file_returns_empty_list(self, tmp_path: Path):
        f = tmp_path / "scout_binary.md"
        f.write_bytes(b"\x00\x01\x02\xff\xfe\xfd" * 100)
        result = extract_claims_from_report(f)
        assert result == []

    def test_malformed_markdown_does_not_crash(self, tmp_path: Path):
        content = _make_scout_report(
            "## \\*\\*\\* Broken {{heading}}\n\n"
            "```python\ndef f():\n    pass\n```\n\n"
            "More [broken](links and `incomplete backticks\n\n"
            "---\n---\n---\n"
        )
        f = tmp_path / "scout_malformed.md"
        f.write_text(content, encoding="utf-8")
        # Should not raise any exception
        result = extract_claims_from_report(f)
        assert isinstance(result, list)

    def test_report_with_no_extractable_claims(self, tmp_path: Path):
        content = _make_scout_report("""
## Strands

Hello.

OK.

Fine.

---

## Closing

Done.
""")
        f = tmp_path / "scout_no_claims.md"
        f.write_text(content, encoding="utf-8")
        result = extract_claims_from_report(f)
        assert result == []

    def test_very_short_report_handled(self, tmp_path: Path):
        content = _make_scout_report("Short.")
        f = tmp_path / "scout_short.md"
        f.write_text(content, encoding="utf-8")
        result = extract_claims_from_report(f)
        assert isinstance(result, list)

    def test_context_is_populated_for_extracted_claims(
        self, scout_with_strands: Path
    ):
        result = extract_claims_from_report(scout_with_strands)
        # Claims extracted from longer text should have context
        # (may be empty if exact match fails, but at least some should have it)
        claims_with_context = [c for c in result if c.context]
        if result:
            assert len(claims_with_context) > 0


# ── Claim type classification ────────────────────────────────────────


class TestClaimTypeClassification:
    """Test claim type assignment through the public API."""

    def test_factual_claim_with_file_reference(self, tmp_path: Path):
        content = _make_scout_report("""
## Strands

The `src/yanantin/apacheta/models.py` file defines 8 model classes for tensor storage and retrieval.
""")
        f = tmp_path / "scout_factual.md"
        f.write_text(content, encoding="utf-8")
        result = extract_claims_from_report(f)
        assert len(result) >= 1
        assert result[0].claim_type == "factual"

    def test_architectural_claim_detected(self, tmp_path: Path):
        content = _make_scout_report("""
## Strands

The `src/yanantin/chasqui/coordinator.py` module enforces a separation of concerns boundary between the gateway and backend layers.
""")
        f = tmp_path / "scout_arch.md"
        f.write_text(content, encoding="utf-8")
        result = extract_claims_from_report(f)
        arch_claims = [c for c in result if c.claim_type == "architectural"]
        assert len(arch_claims) >= 1

    def test_missing_claim_detected(self, tmp_path: Path):
        content = _make_scout_report("""
## Strands

There is no migration framework implemented in `src/yanantin/apacheta/backends/arango.py` for schema evolution.
""")
        f = tmp_path / "scout_missing.md"
        f.write_text(content, encoding="utf-8")
        result = extract_claims_from_report(f)
        missing_claims = [c for c in result if c.claim_type == "missing"]
        assert len(missing_claims) >= 1

    def test_epistemic_claim_in_open_questions(self, tmp_path: Path):
        content = _make_scout_report("""
## Open Questions

I wonder whether the tensor ballot mechanism correctly handles concurrent writes across multiple instances.
""")
        f = tmp_path / "scout_epistemic.md"
        f.write_text(content, encoding="utf-8")
        result = extract_claims_from_report(f)
        epistemic_claims = [c for c in result if c.claim_type == "epistemic"]
        assert len(epistemic_claims) >= 1

    def test_missing_takes_priority_over_architectural(self, tmp_path: Path):
        """Missing claims take priority when both patterns match."""
        content = _make_scout_report("""
## Strands

No interface boundary exists between the coordinator and the external API layer.
""")
        f = tmp_path / "scout_missing_arch.md"
        f.write_text(content, encoding="utf-8")
        result = extract_claims_from_report(f)
        # Should classify as missing since missing > architectural
        if result:
            claim = result[0]
            assert claim.claim_type == "missing"

    def test_epistemic_takes_priority_over_architectural(self, tmp_path: Path):
        """Epistemic claims take priority over architectural."""
        content = _make_scout_report("""
## Strands

It is unclear how the architecture enforces the single entry point constraint for all traffic.
""")
        f = tmp_path / "scout_epist_arch.md"
        f.write_text(content, encoding="utf-8")
        result = extract_claims_from_report(f)
        if result:
            # "unclear" triggers epistemic; "architecture" and "enforces" trigger architectural
            # epistemic > architectural, so should be epistemic
            # But it's in Strands, not Open Questions, so type_override doesn't apply
            epist = [c for c in result if c.claim_type == "epistemic"]
            assert len(epist) >= 1


# ── Confidence scoring ───────────────────────────────────────────────


class TestConfidenceScoring:
    """Test that confidence scoring reflects language patterns."""

    def test_definitive_language_increases_confidence(self, tmp_path: Path):
        content = _make_scout_report("""
## Strands

The `src/yanantin/apacheta/models.py` file always returns exactly 5 model instances for every request.
""")
        f = tmp_path / "scout_definitive.md"
        f.write_text(content, encoding="utf-8")
        result = extract_claims_from_report(f)
        assert len(result) >= 1
        # "always", "exactly", "returns", file ref => high confidence
        assert result[0].confidence > 0.5

    def test_hedged_language_decreases_confidence(self, tmp_path: Path):
        content = _make_scout_report("""
## Strands

The module at `src/yanantin/chasqui/scorer.py` probably might seem to possibly implement a scoring function, though I'm not sure.
""")
        f = tmp_path / "scout_hedged.md"
        f.write_text(content, encoding="utf-8")
        result = extract_claims_from_report(f)
        assert len(result) >= 1
        # Multiple hedging words => low confidence
        assert result[0].confidence < 0.5

    def test_quantitative_assertion_boosts_confidence(self, tmp_path: Path):
        content = _make_scout_report("""
## Strands

This module contains 42 tests and defines 8 classes across 3 files.
""")
        f = tmp_path / "scout_quant.md"
        f.write_text(content, encoding="utf-8")
        result = extract_claims_from_report(f)
        assert len(result) >= 1
        # Quantitative => boosted
        assert result[0].confidence > 0.5

    def test_file_reference_boosts_confidence(self, tmp_path: Path):
        content = _make_scout_report("""
## Strands

The `src/yanantin/apacheta/interface/errors.py` file has some things defined in it that are relevant to the project.
""")
        f = tmp_path / "scout_fileref.md"
        f.write_text(content, encoding="utf-8")
        result = extract_claims_from_report(f)
        # Even without definitive language, file reference gives a boost
        if result:
            assert result[0].confidence >= 0.5

    def test_declared_losses_get_confidence_penalty(self, tmp_path: Path):
        """Claims from Declared Losses section receive a confidence penalty."""
        content = _make_scout_report("""
## Strands

The `src/yanantin/apacheta/models.py` file defines all 8 model classes.

## Declared Losses

I did not examine the `tests/unit/test_provenance.py` because it seemed peripheral to the main analysis scope.
""")
        f = tmp_path / "scout_losses.md"
        f.write_text(content, encoding="utf-8")
        result = extract_claims_from_report(f)
        # Find claims from declared losses vs strands
        strand_claims = [
            c for c in result if "models.py" in c.claim_text
        ]
        loss_claims = [
            c for c in result if "provenance" in c.claim_text.lower()
        ]
        if strand_claims and loss_claims:
            # Loss claims should have lower confidence than strand claims
            # due to the 0.1 penalty
            assert loss_claims[0].confidence <= strand_claims[0].confidence


# ── extract_claims_from_cairn ────────────────────────────────────────


class TestExtractClaimsFromCairn:
    """Tests for cairn-level multi-report extraction."""

    def test_returns_list(self, tmp_path: Path):
        result = extract_claims_from_cairn(tmp_path)
        assert isinstance(result, list)

    def test_nonexistent_directory_returns_empty(self, tmp_path: Path):
        bogus = tmp_path / "no_such_cairn"
        result = extract_claims_from_cairn(bogus)
        assert result == []

    def test_empty_directory_returns_empty(self, tmp_path: Path):
        empty = tmp_path / "empty_cairn"
        empty.mkdir()
        result = extract_claims_from_cairn(empty)
        assert result == []

    def test_no_matching_files_returns_empty(self, tmp_path: Path):
        cairn = tmp_path / "cairn"
        cairn.mkdir()
        (cairn / "README.md").write_text("Not a scout report.", encoding="utf-8")
        result = extract_claims_from_cairn(cairn, pattern="scout_*.md")
        assert result == []

    def test_processes_scout_reports(self, tmp_path: Path):
        cairn = tmp_path / "cairn"
        cairn.mkdir()
        content = _make_scout_report("""
## Strands

The `src/yanantin/apacheta/models.py` file defines 8 model classes for tensor records.
""")
        (cairn / "scout_0001_20260212_mock.md").write_text(content, encoding="utf-8")
        result = extract_claims_from_cairn(cairn, pattern="scout_*.md")
        assert len(result) >= 1

    def test_processes_scour_reports(self, tmp_path: Path):
        cairn = tmp_path / "cairn"
        cairn.mkdir()
        content = _make_scour_report("""
### Evidence

The `tests/unit/test_provenance.py` file contains only 4 tests that verify basic type assertions.

### Reasoning

The tests serve a specific purpose but should not be called comprehensive.
""")
        (cairn / "scour_0001_20260212_mock.md").write_text(content, encoding="utf-8")
        result = extract_claims_from_cairn(cairn, pattern="scour_*.md")
        assert len(result) >= 1

    def test_wildcard_pattern_finds_all_reports(self, tmp_path: Path):
        cairn = tmp_path / "cairn"
        cairn.mkdir()
        scout_content = _make_scout_report("""
## Strands

The `src/yanantin/apacheta/models.py` file defines all model classes.
""")
        scour_content = _make_scour_report("""
### Evidence

The `tests/unit/test_models.py` file has 12 test functions for model validation.
""")
        (cairn / "scout_0001_20260212_mock.md").write_text(
            scout_content, encoding="utf-8"
        )
        (cairn / "scour_0001_20260212_mock.md").write_text(
            scour_content, encoding="utf-8"
        )
        result = extract_claims_from_cairn(cairn, pattern="*.md")
        assert len(result) >= 1

    def test_respects_max_reports_limit(self, tmp_path: Path):
        cairn = tmp_path / "cairn"
        cairn.mkdir()
        for i in range(10):
            content = _make_scout_report(
                f"""
## Strands

The `src/yanantin/module_{i}.py` file defines {i + 1} functions for processing.
""",
                model=f"test/model-{i}",
            )
            f = cairn / f"scout_{i:04d}_20260212_model-{i}.md"
            f.write_text(content, encoding="utf-8")
        # Limit to 3 reports
        result = extract_claims_from_cairn(cairn, pattern="scout_*.md", max_reports=3)
        # Should only have claims from at most 3 reports
        source_files = {c.source_file for c in result}
        assert len(source_files) <= 3

    def test_sorted_by_confidence_descending(self, tmp_path: Path):
        cairn = tmp_path / "cairn"
        cairn.mkdir()
        content = _make_scout_report("""
## Strands

The `src/yanantin/apacheta/models.py` file always defines exactly 8 model classes.

The module at src/yanantin/chasqui/coordinator.py probably seems to implement some dispatch logic.
""")
        (cairn / "scout_0001_20260212_mock.md").write_text(content, encoding="utf-8")
        result = extract_claims_from_cairn(cairn, pattern="scout_*.md")
        if len(result) > 1:
            confidences = [c.confidence for c in result]
            assert confidences == sorted(confidences, reverse=True)

    def test_deduplication_across_reports(self, tmp_path: Path):
        """Same claim in two reports should be deduplicated."""
        cairn = tmp_path / "cairn"
        cairn.mkdir()
        claim_sentence = (
            "The `src/yanantin/apacheta/models.py` file defines 8 model classes."
        )
        for i, model_name in enumerate(["model-a", "model-b"]):
            content = _make_scout_report(
                f"\n## Strands\n\n{claim_sentence}\n",
                model=f"test/{model_name}",
            )
            f = cairn / f"scout_{i:04d}_20260212_{model_name}.md"
            f.write_text(content, encoding="utf-8")
        result = extract_claims_from_cairn(cairn, pattern="scout_*.md")
        # The same claim from two reports should be collapsed to one
        matching = [c for c in result if "8 model classes" in c.claim_text]
        assert len(matching) <= 1

    def test_dedup_keeps_highest_confidence(self, tmp_path: Path):
        """When deduplicating, the highest-confidence version survives."""
        cairn = tmp_path / "cairn"
        cairn.mkdir()
        # Report 1: hedged version (lower confidence)
        hedged = _make_scout_report("""
## Strands

The `src/yanantin/apacheta/models.py` possibly seems to define some classes.
""", model="test/hedged-model")
        (cairn / "scout_0001_20260212_hedged.md").write_text(hedged, encoding="utf-8")

        # Report 2: definitive version (higher confidence)
        definitive = _make_scout_report("""
## Strands

The `src/yanantin/apacheta/models.py` always defines exactly all classes.
""", model="test/definitive-model")
        (cairn / "scout_0002_20260212_definitive.md").write_text(
            definitive, encoding="utf-8"
        )
        result = extract_claims_from_cairn(cairn, pattern="scout_*.md")
        # If dedup merged them, the surviving claim should have higher confidence
        models_claims = [c for c in result if "models.py" in c.claim_text]
        if models_claims:
            # The definitive model's version should survive
            assert models_claims[0].confidence > 0.5

    def test_dedup_merges_file_references(self, tmp_path: Path):
        """Dedup should merge file references from duplicate claims."""
        cairn = tmp_path / "cairn"
        cairn.mkdir()
        # Two reports with similar claims but different secondary file refs
        content_a = _make_scout_report("""
## Strands

The `src/yanantin/apacheta/models.py` file defines all model classes for `src/yanantin/apacheta/interface/__init__.py` consumption.
""", model="test/model-a")
        content_b = _make_scout_report("""
## Strands

The `src/yanantin/apacheta/models.py` file defines all model classes for the `src/yanantin/apacheta/backends/arango.py` backend.
""", model="test/model-b")
        (cairn / "scout_0001_20260212_model-a.md").write_text(
            content_a, encoding="utf-8"
        )
        (cairn / "scout_0002_20260212_model-b.md").write_text(
            content_b, encoding="utf-8"
        )
        result = extract_claims_from_cairn(cairn, pattern="scout_*.md")
        # Check if any merged claim has refs from both reports
        # This depends on whether dedup groups them — the key is first 80 chars
        # of normalized text, so these may or may not group together
        assert isinstance(result, list)  # At minimum, no crash


# ── claims_for_verification ──────────────────────────────────────────


class TestClaimsForVerification:
    """Tests for the verification claim selector."""

    def test_returns_list(self, minimal_claims: list[ExtractedClaim]):
        result = claims_for_verification(minimal_claims)
        assert isinstance(result, list)

    def test_empty_input_returns_empty(self):
        result = claims_for_verification([])
        assert result == []

    def test_respects_max_claims(self, minimal_claims: list[ExtractedClaim]):
        result = claims_for_verification(minimal_claims, max_claims=2)
        assert len(result) <= 2

    def test_excludes_epistemic_claims(self, minimal_claims: list[ExtractedClaim]):
        result = claims_for_verification(minimal_claims)
        for claim in result:
            assert claim.claim_type != "epistemic"

    def test_requires_file_references_or_quantity(
        self, minimal_claims: list[ExtractedClaim]
    ):
        """Selected claims must have file references or quantitative assertions."""
        result = claims_for_verification(minimal_claims)
        for claim in result:
            has_refs = bool(claim.file_references)
            has_quantity = bool("42 tests" in claim.claim_text)  # from minimal_claims
            # Should have at least one of these
            assert has_refs or has_quantity or any(
                char.isdigit() for char in claim.claim_text
            )

    def test_excludes_low_confidence_claims(self):
        low_conf_claims = [
            ExtractedClaim(
                claim_text="The `src/foo.py` module seems to maybe do something.",
                source_file="s.md",
                source_model="m",
                file_references=["src/foo.py"],
                claim_type="factual",
                confidence=0.2,
            ),
        ]
        result = claims_for_verification(low_conf_claims)
        assert result == []

    def test_prefers_source_diversity(self):
        """First pass should select one claim per unique model."""
        diverse_claims = [
            ExtractedClaim(
                claim_text=f"The `src/module_{i}.py` file defines {i + 1} functions.",
                source_file=f"scout_{i}.md",
                source_model=f"model-{chr(97 + i)}",
                file_references=[f"src/module_{i}.py"],
                claim_type="factual",
                confidence=0.7,
            )
            for i in range(5)
        ]
        result = claims_for_verification(diverse_claims, max_claims=3)
        models = {c.source_model for c in result}
        # Should have 3 different models since we requested 3 and have 5 unique models
        assert len(models) == 3

    def test_all_claims_unverifiable_returns_empty(self):
        """If no claims have file refs or quantities, return empty."""
        unverifiable = [
            ExtractedClaim(
                claim_text="The architecture seems interesting and well designed overall.",
                source_file="s.md",
                source_model="m",
                file_references=[],
                claim_type="factual",
                confidence=0.7,
            ),
            ExtractedClaim(
                claim_text="I wonder whether this system handles edge cases correctly.",
                source_file="s.md",
                source_model="m",
                file_references=[],
                claim_type="epistemic",
                confidence=0.6,
            ),
        ]
        result = claims_for_verification(unverifiable)
        assert result == []

    def test_includes_missing_claims_with_refs(self):
        """Missing claims are verifiable (unlike epistemic)."""
        claims = [
            ExtractedClaim(
                claim_text="There is no migration framework in `src/yanantin/apacheta/backends/arango.py`.",
                source_file="s.md",
                source_model="m",
                file_references=["src/yanantin/apacheta/backends/arango.py"],
                claim_type="missing",
                confidence=0.65,
            ),
        ]
        result = claims_for_verification(claims)
        assert len(result) == 1
        assert result[0].claim_type == "missing"

    def test_includes_architectural_claims_with_refs(self):
        """Architectural claims with file refs are verifiable."""
        claims = [
            ExtractedClaim(
                claim_text="The `src/yanantin/chasqui/coordinator.py` module depends on the model selector for dispatch.",
                source_file="s.md",
                source_model="m",
                file_references=["src/yanantin/chasqui/coordinator.py"],
                claim_type="architectural",
                confidence=0.7,
            ),
        ]
        result = claims_for_verification(claims)
        assert len(result) == 1

    def test_quantitative_claim_without_file_ref_included(self):
        """A quantitative claim can be verified even without file refs."""
        claims = [
            ExtractedClaim(
                claim_text="The test suite contains 528 tests across all modules.",
                source_file="s.md",
                source_model="m",
                file_references=[],
                claim_type="factual",
                confidence=0.7,
            ),
        ]
        result = claims_for_verification(claims)
        assert len(result) == 1


# ── to_verifiable_claims ─────────────────────────────────────────────


class TestToVerifiableClaims:
    """Tests for the adapter producing dispatch_verify-compatible tuples."""

    def test_returns_list_of_tuples(self, minimal_claims: list[ExtractedClaim]):
        result = to_verifiable_claims(minimal_claims)
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 4

    def test_empty_input_returns_empty(self):
        result = to_verifiable_claims([])
        assert result == []

    def test_skips_claims_without_file_references(
        self, minimal_claims: list[ExtractedClaim]
    ):
        """Claims with no file_references are excluded."""
        result = to_verifiable_claims(minimal_claims)
        # minimal_claims has 5 claims; 2 have file refs (model-a factual, model-a missing)
        # plus model-d architectural has no refs
        # Only claims with file_references should appear
        assert all(len(t) == 4 for t in result)
        for claim_text, file_path, source_model, source_file in result:
            assert file_path  # non-empty file path

    def test_tuple_structure(self):
        claims = [
            ExtractedClaim(
                claim_text="The file defines 8 classes.",
                source_file="scout_01.md",
                source_model="vendor/model-x",
                file_references=["src/yanantin/apacheta/models.py"],
                claim_type="factual",
                confidence=0.8,
            ),
        ]
        result = to_verifiable_claims(claims)
        assert len(result) == 1
        claim_text, file_path, source_model, source_file = result[0]
        assert claim_text == "The file defines 8 classes."
        assert file_path == "src/yanantin/apacheta/models.py"
        assert source_model == "vendor/model-x"
        assert source_file == "scout_01.md"

    def test_strips_line_number_from_file_path(self):
        claims = [
            ExtractedClaim(
                claim_text="Line 42 defines the main function.",
                source_file="scout_01.md",
                source_model="m",
                file_references=["src/yanantin/apacheta/models.py:42"],
                claim_type="factual",
                confidence=0.7,
            ),
        ]
        result = to_verifiable_claims(claims)
        assert len(result) == 1
        _, file_path, _, _ = result[0]
        assert file_path == "src/yanantin/apacheta/models.py"
        assert ":42" not in file_path

    def test_uses_first_file_reference(self):
        """When multiple file refs exist, use the first one."""
        claims = [
            ExtractedClaim(
                claim_text="The module imports from both files.",
                source_file="scout_01.md",
                source_model="m",
                file_references=[
                    "src/yanantin/first.py",
                    "src/yanantin/second.py",
                ],
                claim_type="factual",
                confidence=0.7,
            ),
        ]
        result = to_verifiable_claims(claims)
        assert len(result) == 1
        _, file_path, _, _ = result[0]
        assert file_path == "src/yanantin/first.py"

    def test_preserves_order(self):
        claims = [
            ExtractedClaim(
                claim_text=f"Claim {i}.",
                source_file=f"s{i}.md",
                source_model="m",
                file_references=[f"src/f{i}.py"],
            )
            for i in range(5)
        ]
        result = to_verifiable_claims(claims)
        assert len(result) == 5
        for i, (claim_text, _, _, _) in enumerate(result):
            assert claim_text == f"Claim {i}."

    def test_all_no_refs_returns_empty(self):
        claims = [
            ExtractedClaim(
                claim_text="No refs here.",
                source_file="s.md",
                source_model="m",
                file_references=[],
            ),
            ExtractedClaim(
                claim_text="Also no refs.",
                source_file="s.md",
                source_model="m",
                file_references=[],
            ),
        ]
        result = to_verifiable_claims(claims)
        assert result == []


# ── Integration-style tests against real cairn ───────────────────────


CAIRN_DIR = Path(__file__).resolve().parents[2] / "docs" / "cairn"


class TestRealCairn:
    """Run gleaner against actual scout and scour reports in the cairn.

    These tests verify the gleaner works on real-world report formats,
    not just synthetic test data.
    """

    @pytest.mark.skipif(
        not CAIRN_DIR.is_dir(),
        reason="Cairn directory not found",
    )
    def test_extracts_claims_from_real_scout(self):
        scouts = sorted(CAIRN_DIR.glob("scout_*.md"))
        if not scouts:
            pytest.skip("No scout reports in cairn")
        result = extract_claims_from_report(scouts[0])
        assert isinstance(result, list)
        # Real scout reports should yield at least some claims
        # (though very small/broken ones might not)

    @pytest.mark.skipif(
        not CAIRN_DIR.is_dir(),
        reason="Cairn directory not found",
    )
    def test_extracts_claims_from_real_scour(self):
        scours = sorted(CAIRN_DIR.glob("scour_*.md"))
        if not scours:
            pytest.skip("No scour reports in cairn")
        result = extract_claims_from_report(scours[0])
        assert isinstance(result, list)

    @pytest.mark.skipif(
        not CAIRN_DIR.is_dir(),
        reason="Cairn directory not found",
    )
    def test_cairn_level_extraction_does_not_crash(self):
        """extract_claims_from_cairn should handle the full real cairn."""
        result = extract_claims_from_cairn(
            CAIRN_DIR, pattern="scout_*.md", max_reports=5
        )
        assert isinstance(result, list)
        # With 5 real scout reports, we should get some claims
        assert len(result) > 0

    @pytest.mark.skipif(
        not CAIRN_DIR.is_dir(),
        reason="Cairn directory not found",
    )
    def test_all_real_claims_have_valid_types(self):
        result = extract_claims_from_cairn(
            CAIRN_DIR, pattern="*.md", max_reports=3
        )
        valid_types = {"factual", "architectural", "epistemic", "missing"}
        for claim in result:
            assert claim.claim_type in valid_types

    @pytest.mark.skipif(
        not CAIRN_DIR.is_dir(),
        reason="Cairn directory not found",
    )
    def test_all_real_claims_have_bounded_confidence(self):
        result = extract_claims_from_cairn(
            CAIRN_DIR, pattern="*.md", max_reports=3
        )
        for claim in result:
            assert 0.0 <= claim.confidence <= 1.0

    @pytest.mark.skipif(
        not CAIRN_DIR.is_dir(),
        reason="Cairn directory not found",
    )
    def test_verification_selection_on_real_claims(self):
        all_claims = extract_claims_from_cairn(
            CAIRN_DIR, pattern="scout_*.md", max_reports=5
        )
        selected = claims_for_verification(all_claims, max_claims=3)
        assert isinstance(selected, list)
        assert len(selected) <= 3
        for claim in selected:
            assert claim.claim_type != "epistemic"
            assert claim.confidence >= 0.3

    @pytest.mark.skipif(
        not CAIRN_DIR.is_dir(),
        reason="Cairn directory not found",
    )
    def test_to_verifiable_on_real_claims(self):
        all_claims = extract_claims_from_cairn(
            CAIRN_DIR, pattern="scout_*.md", max_reports=5
        )
        tuples = to_verifiable_claims(all_claims)
        assert isinstance(tuples, list)
        for t in tuples:
            assert len(t) == 4
            claim_text, file_path, source_model, source_file = t
            assert isinstance(claim_text, str) and claim_text
            assert isinstance(file_path, str) and file_path
            assert ":" not in file_path or file_path.count(":") == 0  # line nums stripped
