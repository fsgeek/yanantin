"""Unit tests for the chasqui scorer."""

import textwrap

import pytest

from yanantin.chasqui.scorer import (
    ContentAnalysis,
    FileReference,
    analyze_content,
    parse_provenance,
    render_scorecard,
    score_scout,
    verify_references,
)


SAMPLE_PROVENANCE_HEADER = textwrap.dedent(
    """\
    <!-- Chasqui Scout Tensor
         Run: 2
         Model: deepseek/deepseek-chat-v3.1 (DeepSeek: DeepSeek V3.1)
         Cost: prompt=$1.5e-07/M, completion=$7.5e-07/M
         Usage: {'prompt_tokens': 6307, 'completion_tokens': 912, 'total_tokens': 7219, 'cost': 0.00163005, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0}, 'cost_details': {}, 'completion_tokens_details': {'reasoning_tokens': 0}}
         Timestamp: 2026-02-10T00:56:50.584915+00:00
    -->
    """
)


class TestParseProvenance:
    def test_extracts_values_from_sample_header(self):
        provenance = parse_provenance(SAMPLE_PROVENANCE_HEADER)

        assert provenance is not None
        assert provenance.run_number == 2
        assert provenance.model_id == "deepseek/deepseek-chat-v3.1"
        assert provenance.completion_tokens == 912
        assert provenance.total_cost == pytest.approx(0.00163005)

    def test_returns_none_without_header(self):
        assert parse_provenance("## Strands\nNo comment header here.") is None


class TestAnalyzeContent:
    def test_counts_sections_and_file_references(self):
        body = textwrap.dedent(
            """\
            ## Preamble
            Brief setup referencing `src/foo/bar.py`.

            ## Strands
            #### 1. First strand covers inputs.
            #### 2. Second strand details findings.
            #### 3. Third strand cites `tests/test_baz.py:42`.

            ## Declared Losses
            1. Lost telemetry detail.
            2. Lost comparison to baseline.

            ## Open Questions
            1. How do we stabilize the run?
            2. Which dataset should be replayed?
            """
        )

        analysis = analyze_content(body)

        assert analysis.strand_count == 3
        assert analysis.open_question_count == 2
        assert analysis.declared_loss_count == 2
        assert len(analysis.file_references) == 2
        assert analysis.file_references[0].path == "src/foo/bar.py"
        assert analysis.file_references[0].line is None
        assert analysis.file_references[1].path == "tests/test_baz.py"
        assert analysis.file_references[1].line == 42


class TestVerifyReferences:
    def test_marks_existing_and_missing_paths(self, tmp_path):
        real_file = tmp_path / "src" / "foo.py"
        real_file.parent.mkdir(parents=True)
        real_file.write_text("print('ok')\n")

        analysis = ContentAnalysis(
            body_text="",
            word_count=1,
            strand_count=0,
            open_question_count=0,
            declared_loss_count=0,
            file_references=[
                FileReference(path="src/foo.py"),
                FileReference(path="missing/data.py"),
            ],
        )

        verify_references(analysis, tmp_path)

        assert analysis.file_references[0].exists is True
        assert analysis.file_references[1].exists is False
        assert analysis.verified_references == 1
        assert analysis.fabricated_references == 1


class TestScoreScout:
    def test_pipeline_metrics_reflect_structure_and_references(self, scored_scout):
        assert scored_scout.specificity > 0
        assert scored_scout.fabrication_rate == pytest.approx(0.5)
        assert scored_scout.structure == pytest.approx(1.0)
        assert scored_scout.content.verified_references == 1
        assert scored_scout.content.fabricated_references == 1


class TestRenderScorecard:
    def test_includes_heading(self, scored_scout):
        output = render_scorecard([scored_scout])
        assert "Cairn Scorecard" in output


@pytest.fixture
def scored_scout(tmp_path):
    real_file = tmp_path / "src" / "foo" / "bar.py"
    real_file.parent.mkdir(parents=True)
    real_file.write_text("pass\n")

    scout_text = textwrap.dedent(
        """\
        <!-- Chasqui Scout Tensor
             Run: 7
             Model: anthropic/claude-3-haiku (Anthropic: Claude 3 Haiku)
             Cost: prompt=$0.01/M, completion=$0.02/M
             Usage: {'prompt_tokens': 2000, 'completion_tokens': 400, 'total_tokens': 2400, 'cost': 0.42}
             Timestamp: 2026-02-12T12:00:00Z
        -->
        ## Preamble
        This tensor cites `src/foo/bar.py` for reproducibility.

        ## Strands
        #### 1. Observes the system behavior.
        #### 2. Points out `missing/path.py` for further investigation.

        ## Declared Losses
        1. Lost fuller log context.

        ## Open Questions
        1. What other signals should we collect?

        ## Closing
        Ready for follow-up analysis.
        """
    )

    return score_scout(scout_text, "docs/cairn/sample.md", tmp_path)
