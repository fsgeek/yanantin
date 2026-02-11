"""Unit tests for yanantin.tinkuy.audit — codebase audit tool.

Tests that the audit module correctly surveys the Yanantin project
filesystem and produces accurate structured reports.

Test Author: Claude Opus (Test Author role)
Code Author: Different instance (Builder role)
"""

import json
from pathlib import Path

import pytest

from yanantin.tinkuy.audit import (
    APACHETA_LAYERS,
    CodebaseReport,
    render_report,
    survey_codebase,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # tests/unit/test_*.py -> project root


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def report() -> CodebaseReport:
    """Survey the real project once per module — it's read-only."""
    return survey_codebase(PROJECT_ROOT)


# ---------------------------------------------------------------------------
# 1. survey_codebase returns CodebaseReport with non-empty source_layers
# ---------------------------------------------------------------------------

def test_survey_codebase_returns_report(report: CodebaseReport):
    """survey_codebase returns a CodebaseReport with non-empty source_layers."""
    assert isinstance(report, CodebaseReport)
    assert len(report.source_layers) > 0


# ---------------------------------------------------------------------------
# 2. source layers contain expected layers
# ---------------------------------------------------------------------------

def test_source_layers_contain_expected_keys(report: CodebaseReport):
    """source_layers has keys for all expected Apacheta layers."""
    expected = {"models", "interface", "backends", "operators", "renderer", "ingest", "clients"}
    actual = set(report.source_layers.keys())
    assert expected == actual, f"Missing: {expected - actual}, Extra: {actual - expected}"


def test_source_layers_match_apacheta_layers_constant(report: CodebaseReport):
    """source_layers keys match the APACHETA_LAYERS constant exactly."""
    assert tuple(report.source_layers.keys()) == APACHETA_LAYERS


# ---------------------------------------------------------------------------
# 3. source layer file counts are positive
# ---------------------------------------------------------------------------

def test_source_layer_file_counts_positive(report: CodebaseReport):
    """Each source layer should have file_count > 0 and len(files) == file_count."""
    for layer_name, layer in report.source_layers.items():
        assert layer.file_count > 0, f"Layer '{layer_name}' has file_count == 0"
        assert len(layer.files) == layer.file_count, (
            f"Layer '{layer_name}': file_count={layer.file_count} "
            f"but len(files)={len(layer.files)}"
        )


# ---------------------------------------------------------------------------
# 4. test summary has positive counts
# ---------------------------------------------------------------------------

def test_test_summary_positive_counts(report: CodebaseReport):
    """Test summary should have positive counts and total == sum of parts."""
    ts = report.test_summary
    assert ts.unit_count > 0, "Expected unit tests"
    assert ts.red_bar_count > 0, "Expected red-bar tests"
    assert ts.total > 0, "Expected total > 0"
    assert ts.total == ts.unit_count + ts.integration_count + ts.red_bar_count, (
        f"total={ts.total} != unit={ts.unit_count} + "
        f"integration={ts.integration_count} + red_bar={ts.red_bar_count}"
    )


# ---------------------------------------------------------------------------
# 5. cairn summary finds tensors
# ---------------------------------------------------------------------------

def test_cairn_summary_finds_tensors(report: CodebaseReport):
    """Cairn should contain tensors, and at least one should start with T0 or T1."""
    cs = report.cairn_summary
    assert cs.tensor_count > 0, "Expected tensors in docs/cairn/"
    has_early_tensor = any(
        name.startswith("T0") or name.startswith("T1")
        for name in cs.tensor_names
    )
    assert has_early_tensor, (
        f"Expected a tensor starting with T0 or T1, got: {cs.tensor_names}"
    )


# ---------------------------------------------------------------------------
# 6. cairn summary finds scout reports (may be 0)
# ---------------------------------------------------------------------------

def test_cairn_summary_scout_count(report: CodebaseReport):
    """Scout count should be non-negative (may be 0 in some environments)."""
    cs = report.cairn_summary
    assert cs.scout_count >= 0


# ---------------------------------------------------------------------------
# 7. chasqui_files is non-empty
# ---------------------------------------------------------------------------

def test_chasqui_files_non_empty(report: CodebaseReport):
    """Should find Chasqui source files like coordinator.py, scout.py."""
    assert len(report.chasqui_files) > 0, "Expected Chasqui source files"
    # Verify some expected files are present
    expected_files = {"coordinator.py", "scout.py"}
    found = set(report.chasqui_files)
    assert expected_files.issubset(found), (
        f"Missing expected Chasqui files: {expected_files - found}"
    )


# ---------------------------------------------------------------------------
# 8. render_report produces markdown with expected headings
# ---------------------------------------------------------------------------

def test_render_report_produces_markdown(report: CodebaseReport):
    """Rendered report should start with the title and contain expected sections."""
    output = render_report(report)
    assert output.startswith("# Codebase Audit Report"), (
        f"Expected report to start with title, got: {output[:80]!r}"
    )
    assert "## Apacheta Source Layers" in output
    assert "## Test Summary" in output


# ---------------------------------------------------------------------------
# 9. render_report contains actual data
# ---------------------------------------------------------------------------

def test_render_report_contains_data(report: CodebaseReport):
    """Rendered output should contain layer names and test file names."""
    output = render_report(report)
    # Layer names should appear in the table
    assert "models" in output
    assert "backends" in output
    # At least one test file name should appear
    assert "test_" in output


# ---------------------------------------------------------------------------
# 10. CodebaseReport serializes to valid JSON
# ---------------------------------------------------------------------------

def test_codebase_report_serializes_to_json(report: CodebaseReport):
    """model_dump_json() should produce valid, parseable JSON."""
    json_str = report.model_dump_json()
    parsed = json.loads(json_str)
    assert isinstance(parsed, dict)
    assert "source_layers" in parsed
    assert "test_summary" in parsed
    assert "cairn_summary" in parsed
    assert "timestamp" in parsed


# ---------------------------------------------------------------------------
# 11. survey_codebase on non-existent dir returns empty layers
# ---------------------------------------------------------------------------

def test_survey_codebase_nonexistent_dir(tmp_path: Path):
    """When src/yanantin/apacheta doesn't exist, layers should have file_count == 0."""
    # tmp_path exists but has no project structure inside it
    report = survey_codebase(tmp_path)
    assert isinstance(report, CodebaseReport)
    for layer_name, layer in report.source_layers.items():
        assert layer.file_count == 0, (
            f"Layer '{layer_name}' should be empty for non-existent dir, "
            f"got file_count={layer.file_count}"
        )
    assert report.test_summary.total == 0
    assert report.cairn_summary.tensor_count == 0
