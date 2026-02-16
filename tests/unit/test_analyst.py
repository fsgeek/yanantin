"""Tests for Chasqui analyst — cross-model topology detection.

Tests the analysis pipeline: garbage filtering, model quality scoring,
claim clustering, cross-model agreement detection, and report rendering.
Uses synthetic claims to avoid dependency on the cairn corpus.
"""

from __future__ import annotations

import pytest

from yanantin.chasqui.analyst import (
    AnalysisReport,
    ClaimCluster,
    ClaimGroup,
    ModelProfile,
    analyze,
    cluster_claims,
    filter_garbage,
    is_garbage,
    is_verification_meta,
    render_report,
    score_models,
    word_similarity,
)
from yanantin.chasqui.gleaner import ExtractedClaim


# ── Helpers ──────────────────────────────────────────────────────────


def _claim(
    text: str,
    model: str = "test/model-a",
    refs: list[str] | None = None,
    claim_type: str = "factual",
    confidence: float = 0.65,
    source_file: str = "scout_0001.md",
) -> ExtractedClaim:
    """Build a synthetic claim for testing."""
    return ExtractedClaim(
        claim_text=text,
        source_file=source_file,
        source_model=model,
        file_references=refs or [],
        claim_type=claim_type,
        confidence=confidence,
    )


# ── Garbage detection ────────────────────────────────────────────────


class TestIsGarbage:
    """Test garbage claim detection."""

    def test_clean_english_claim(self):
        assert not is_garbage(
            "The file src/yanantin/apacheta/models/base.py defines the base model class."
        )

    def test_cjk_noise(self):
        assert is_garbage(
            "comp handle-align 乎 Covid问整保 Resistance obligations cherry females"
        )

    def test_encoding_artifacts(self):
        assert is_garbage("The fileÃÂ©®™ contains important ÃÂÃÂ data structures")

    def test_too_few_words(self):
        assert is_garbage("Yes confirmed")

    def test_low_alpha_ratio(self):
        assert is_garbage("|||---|||===|||---|||===|||---|||")

    def test_borderline_short_but_substantive(self):
        # 4+ words, mostly alpha, no garbage patterns
        assert not is_garbage("The interface defines twenty six abstract methods clearly")

    def test_mixed_formatting_not_garbage(self):
        assert not is_garbage(
            "The `ApachetaInterface` in `src/yanantin/apacheta/interface/abstract.py` "
            "defines 26 methods."
        )


# ── Verification meta-claim detection ────────────────────────────────


class TestIsVerificationMeta:
    """Test detection of scouts reviewing other scouts."""

    def test_verdict_confirmed(self):
        assert is_verification_meta("Verdict CONFIRMED — the file exists as claimed.")

    def test_verdict_denied(self):
        assert is_verification_meta("Verdict DENIED — no such function exists.")

    def test_claim_states(self):
        assert is_verification_meta(
            "The claim states that the file contains 26 methods."
        )

    def test_evidence_shows(self):
        assert is_verification_meta(
            "Evidence shows that the interface has the expected structure."
        )

    def test_original_observation(self):
        assert not is_verification_meta(
            "The backends directory contains three implementations: memory, DuckDB, and ArangoDB."
        )

    def test_original_architectural(self):
        assert not is_verification_meta(
            "The operator pipeline composes tensors through the abstract interface."
        )

    def test_indeterminate_verdict(self):
        assert is_verification_meta(
            "INDETERMINATE — cannot verify without runtime access."
        )


# ── Model quality scoring ────────────────────────────────────────────


class TestScoreModels:
    """Test model quality profiling."""

    def test_single_model_profile(self):
        claims = [
            _claim("Claim one about file.py", model="test/a", refs=["file.py"]),
            _claim("Claim two about file.py", model="test/a", refs=["file.py"]),
            _claim("Claim three no ref", model="test/a"),
        ]
        profiles = score_models(claims)
        assert "test/a" in profiles
        p = profiles["test/a"]
        assert p.claim_count == 3
        assert p.claims_with_refs == 2
        assert p.ref_ratio == pytest.approx(2 / 3)

    def test_multiple_models(self):
        claims = [
            _claim("Claim", model="test/a"),
            _claim("Claim", model="test/b"),
            _claim("Claim", model="test/b"),
        ]
        profiles = score_models(claims)
        assert len(profiles) == 2
        assert profiles["test/a"].claim_count == 1
        assert profiles["test/b"].claim_count == 2

    def test_quality_score_rewards_refs(self):
        claims = [
            _claim("Good claim", model="test/good", refs=["file.py"], confidence=0.7),
            _claim("Bad claim no ref", model="test/bad", confidence=0.3),
        ]
        profiles = score_models(claims)
        assert profiles["test/good"].quality_score > profiles["test/bad"].quality_score

    def test_empty_claims(self):
        profiles = score_models([])
        assert len(profiles) == 0

    def test_garbage_counted(self):
        claims = [
            _claim("乎 Covid问整保 garbage text here", model="test/bad"),
            _claim("Normal English claim about the codebase structure", model="test/bad"),
        ]
        profiles = score_models(claims)
        assert profiles["test/bad"].garbage_count == 1
        assert profiles["test/bad"].garbage_ratio == pytest.approx(0.5)


# ── Garbage filtering ────────────────────────────────────────────────


class TestFilterGarbage:
    """Test claim and model-level garbage filtering."""

    def test_removes_garbage_claims(self):
        claims = [
            _claim("Normal claim about the architecture of the system", model="test/a"),
            _claim("乎 Covid问整保 garbage", model="test/b"),
        ]
        filtered, count = filter_garbage(claims)
        assert len(filtered) == 1
        assert count == 1
        assert filtered[0].source_model == "test/a"

    def test_excludes_garbage_heavy_models(self):
        claims = [
            _claim("乎 Covid问整保 garbage one", model="test/bad"),
            _claim("乎 Covid问整保 garbage two", model="test/bad"),
            _claim("乎 Covid问整保 garbage three", model="test/bad"),
            _claim("One good claim from bad model", model="test/bad"),
            _claim("Normal claim from good model about architecture", model="test/good"),
        ]
        filtered, count = filter_garbage(claims, model_garbage_threshold=0.5)
        # test/bad has 75% garbage → excluded entirely (all 4 claims)
        assert len(filtered) == 1
        assert filtered[0].source_model == "test/good"

    def test_keeps_all_clean_claims(self):
        claims = [
            _claim("Claim one about the codebase structure", model="test/a"),
            _claim("Claim two about the interface design", model="test/b"),
        ]
        filtered, count = filter_garbage(claims)
        assert len(filtered) == 2
        assert count == 0

    def test_empty_input(self):
        filtered, count = filter_garbage([])
        assert len(filtered) == 0
        assert count == 0


# ── Word similarity ──────────────────────────────────────────────────


class TestWordSimilarity:
    """Test Jaccard similarity on content words."""

    def test_identical_texts(self):
        text = "The interface defines 26 abstract methods"
        assert word_similarity(text, text) == pytest.approx(1.0)

    def test_completely_different(self):
        a = "Architecture defines structural boundaries"
        b = "Quantum mechanics explains particle behavior"
        sim = word_similarity(a, b)
        assert sim < 0.2

    def test_similar_claims(self):
        a = "The file docs/predecessors.md is not present"
        b = "The file docs/predecessors.md does not exist"
        sim = word_similarity(a, b)
        assert sim > 0.3  # Significant overlap

    def test_empty_text(self):
        assert word_similarity("", "something here") == 0.0
        assert word_similarity("", "") == 0.0

    def test_stop_words_ignored(self):
        a = "The quick brown fox"
        b = "A quick brown fox"
        # "the" and "a" are stop words, "quick", "brown", "fox" remain
        assert word_similarity(a, b) == pytest.approx(1.0)


# ── Claim clustering ─────────────────────────────────────────────────


class TestClusterClaims:
    """Test clustering by file reference and similarity."""

    def test_groups_by_file_reference(self):
        claims = [
            _claim("Claim about file A", refs=["file_a.py"]),
            _claim("Another claim about file A", refs=["file_a.py"]),
            _claim("Claim about file B", refs=["file_b.py"]),
        ]
        clusters = cluster_claims(claims)
        refs = {c.file_reference for c in clusters}
        assert "file_a.py" in refs
        assert "file_b.py" in refs

    def test_no_ref_claims_grouped_separately(self):
        claims = [
            _claim("Claim with no file reference at all"),
            _claim("Another claim without references"),
            _claim("Claim about file A", refs=["file_a.py"]),
        ]
        clusters = cluster_claims(claims)
        no_ref = [c for c in clusters if c.file_reference == ""]
        assert len(no_ref) == 1

    def test_similar_claims_grouped_together(self):
        claims = [
            _claim(
                "The file predecessors.md is not present in the repository",
                model="test/a", refs=["predecessors.md"],
            ),
            _claim(
                "The file predecessors.md does not exist in the repository",
                model="test/b", refs=["predecessors.md"],
            ),
        ]
        clusters = cluster_claims(claims, similarity_threshold=0.3)
        pred_cluster = [c for c in clusters if c.file_reference == "predecessors.md"]
        assert len(pred_cluster) == 1
        # Both claims should be in the same group (similar enough)
        assert len(pred_cluster[0].groups) == 1
        assert pred_cluster[0].groups[0].model_count == 2

    def test_dissimilar_claims_separate_groups(self):
        claims = [
            _claim(
                "The interface defines 26 abstract methods",
                model="test/a", refs=["abstract.py"],
            ),
            _claim(
                "Performance benchmarks show 100ms latency",
                model="test/b", refs=["abstract.py"],
            ),
        ]
        clusters = cluster_claims(claims, similarity_threshold=0.5)
        abstract_cluster = [c for c in clusters if c.file_reference == "abstract.py"]
        assert len(abstract_cluster) == 1
        # Should be in different groups (too dissimilar)
        assert len(abstract_cluster[0].groups) == 2

    def test_topological_detection(self):
        """3+ models agreeing on same claim = topological."""
        claims = [
            _claim("The backends directory contains three implementations",
                   model="test/a", refs=["backends/"]),
            _claim("The backends directory has three backend implementations",
                   model="test/b", refs=["backends/"]),
            _claim("The backends directory includes three implementations",
                   model="test/c", refs=["backends/"]),
        ]
        clusters = cluster_claims(claims, similarity_threshold=0.3)
        backend_cluster = [c for c in clusters if c.file_reference == "backends/"]
        assert len(backend_cluster) == 1
        topo = backend_cluster[0].topological_groups
        assert len(topo) >= 1
        assert topo[0].model_count >= 3

    def test_empty_input(self):
        clusters = cluster_claims([])
        assert len(clusters) == 0

    def test_strips_line_numbers_for_grouping(self):
        claims = [
            _claim("Claim about line 10", refs=["file.py:10"]),
            _claim("Claim about line 20", refs=["file.py:20"]),
        ]
        clusters = cluster_claims(claims)
        file_refs = {c.file_reference for c in clusters}
        # Both should cluster under "file.py" (line numbers stripped)
        assert "file.py" in file_refs


# ── Full analysis pipeline ───────────────────────────────────────────


class TestAnalyze:
    """Test end-to-end analysis pipeline."""

    def test_produces_report(self):
        claims = [
            _claim("The interface defines methods", model="test/a", refs=["file.py"]),
            _claim("The interface has methods defined", model="test/b", refs=["file.py"]),
            _claim("The interface contains method definitions", model="test/c", refs=["file.py"]),
        ]
        report = analyze(claims)
        assert isinstance(report, AnalysisReport)
        assert report.total_claims_input == 3
        assert report.claims_after_filter <= 3

    def test_filters_garbage_in_pipeline(self):
        claims = [
            _claim("Normal claim about the project architecture", model="test/good"),
            _claim("乎 Covid问整保 garbage", model="test/bad"),
        ]
        report = analyze(claims)
        assert report.garbage_filtered >= 1
        assert report.claims_after_filter < report.total_claims_input

    def test_topological_insights_extracted(self):
        # 4 models making similar claims about same file
        claims = [
            _claim("The red bar tests enforce immutability constraints",
                   model=f"test/model-{c}", refs=["test_immutability.py"])
            for c in "abcd"
        ]
        report = analyze(claims, similarity_threshold=0.3)
        assert len(report.topological_insights) >= 1
        assert report.topological_insights[0].model_count >= 4

    def test_verification_claims_separated(self):
        """Verification meta-claims go to verification_insights, not topological."""
        original_claims = [
            _claim("The backends directory contains three implementations",
                   model=f"test/orig-{c}", refs=["backends/"])
            for c in "abcd"
        ]
        verification_claims = [
            _claim("Verdict CONFIRMED — the claim is fully supported by the code",
                   model=f"test/verify-{c}", refs=["backends/"])
            for c in "abcde"
        ]
        report = analyze(original_claims + verification_claims, similarity_threshold=0.3)
        # Should have both original and verification insights
        assert report.verification_claims > 0

    def test_model_profiles_sorted_by_quality(self):
        claims = [
            _claim("Good claim with ref", model="test/good", refs=["file.py"], confidence=0.8),
            _claim("Bad claim no ref", model="test/bad", confidence=0.3),
        ]
        report = analyze(claims)
        assert len(report.model_profiles) == 2
        # Higher quality model should be first
        assert report.model_profiles[0].quality_score >= report.model_profiles[1].quality_score

    def test_empty_input(self):
        report = analyze([])
        assert report.total_claims_input == 0
        assert report.claims_after_filter == 0
        assert len(report.clusters) == 0
        assert len(report.topological_insights) == 0


# ── Report rendering ─────────────────────────────────────────────────


class TestRenderReport:
    """Test markdown report rendering."""

    def test_renders_non_empty(self):
        claims = [
            _claim("Test claim about architecture", model="test/a", refs=["file.py"]),
        ]
        report = analyze(claims)
        text = render_report(report)
        assert "Scout Corpus Analysis" in text
        assert "Claims processed" in text

    def test_renders_topological_section(self):
        claims = [
            _claim("The backends include three implementations",
                   model=f"test/{c}", refs=["backends/"])
            for c in "abcd"
        ]
        report = analyze(claims, similarity_threshold=0.3)
        text = render_report(report)
        assert "Topological Insights" in text
        assert "models agree" in text

    def test_renders_model_quality_table(self):
        claims = [
            _claim("Claim", model="test/a", refs=["file.py"], confidence=0.7),
        ]
        report = analyze(claims)
        text = render_report(report)
        assert "Model Quality" in text
        assert "test/a" in text

    def test_empty_report_renders(self):
        report = analyze([])
        text = render_report(report)
        assert "Scout Corpus Analysis" in text
        assert "Claims processed:** 0" in text


# ── ModelProfile properties ──────────────────────────────────────────


class TestModelProfile:
    """Test ModelProfile computed properties."""

    def test_ref_ratio(self):
        p = ModelProfile(model_id="test", claim_count=10, claims_with_refs=7)
        assert p.ref_ratio == pytest.approx(0.7)

    def test_ref_ratio_zero_claims(self):
        p = ModelProfile(model_id="test", claim_count=0)
        assert p.ref_ratio == 0.0

    def test_garbage_ratio(self):
        p = ModelProfile(model_id="test", claim_count=10, garbage_count=3)
        assert p.garbage_ratio == pytest.approx(0.3)

    def test_quality_score_perfect(self):
        p = ModelProfile(
            model_id="test", claim_count=10, claims_with_refs=10,
            avg_confidence=1.0, garbage_count=0,
        )
        assert p.quality_score == pytest.approx(1.0)

    def test_quality_score_zero(self):
        p = ModelProfile(model_id="test", claim_count=0)
        assert p.quality_score == 0.0


# ── ClaimGroup properties ────────────────────────────────────────────


class TestClaimGroup:
    """Test ClaimGroup computed properties."""

    def test_is_topological_three_plus(self):
        g = ClaimGroup(
            representative="test",
            model_ids={"a", "b", "c"},
        )
        assert g.is_topological is True

    def test_not_topological_two_models(self):
        g = ClaimGroup(
            representative="test",
            model_ids={"a", "b"},
        )
        assert g.is_topological is False

    def test_model_count(self):
        g = ClaimGroup(
            representative="test",
            model_ids={"a", "b", "c", "d"},
        )
        assert g.model_count == 4


# ── Integration with real cairn (if available) ───────────────────────


class TestRealCairn:
    """Integration tests against the actual cairn corpus."""

    @pytest.fixture()
    def cairn_claims(self):
        from pathlib import Path
        from yanantin.chasqui.gleaner import extract_claims_from_cairn

        cairn = Path(__file__).resolve().parents[2] / "docs" / "cairn"
        if not cairn.is_dir():
            pytest.skip("Cairn directory not available")
        # Use a small sample for speed
        return extract_claims_from_cairn(cairn, pattern="scout_*.md", max_reports=50)

    def test_analyze_real_corpus(self, cairn_claims):
        if len(cairn_claims) < 10:
            pytest.skip("Not enough claims in sample")
        report = analyze(cairn_claims)
        assert report.total_claims_input > 0
        assert report.claims_after_filter > 0
        assert len(report.clusters) > 0

    def test_multiple_models_in_real_data(self, cairn_claims):
        if len(cairn_claims) < 10:
            pytest.skip("Not enough claims in sample")
        report = analyze(cairn_claims)
        assert len(report.model_profiles) > 1

    def test_render_real_report(self, cairn_claims):
        if len(cairn_claims) < 10:
            pytest.skip("Not enough claims in sample")
        report = analyze(cairn_claims)
        text = render_report(report)
        assert len(text) > 100
