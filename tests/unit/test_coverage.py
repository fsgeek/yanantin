"""Tests for the coverage tracker — the watchman at the helm.

Verifies that:
- Cairn scanning correctly extracts file references and timestamps
- Coverage weights give unreviewed files maximum priority
- Recently reviewed files get lower (but nonzero) weight
- The coverage report distinguishes reviewed from unreviewed files
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from yanantin.chasqui.coverage import (
    EPOCH_ZERO,
    coverage_report,
    coverage_weights,
    scan_cairn_coverage,
    stalest_files,
    unreviewed_files,
)


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def cairn_dir(tmp_path):
    """Create a temporary cairn directory with synthetic scout reports."""
    cairn = tmp_path / "cairn"
    cairn.mkdir()

    # Scout report 1: reviews src/yanantin/foo.py
    report1 = cairn / "scout_0001_20260218_test-model.md"
    report1.write_text(
        "<!-- Chasqui Scout Tensor\n"
        "     Run: 1\n"
        "     Model: test/model-a (Test Model A)\n"
        "     Timestamp: 2026-02-18T10:00:00+00:00\n"
        "-->\n\n"
        "# Scout Report\n\n"
        "The file `src/yanantin/foo.py` has interesting patterns.\n"
        "Also looked at `src/yanantin/bar.py:42` for comparison.\n"
    )

    # Scout report 2: reviews src/yanantin/foo.py again (later)
    report2 = cairn / "scout_0002_20260218_test-model.md"
    report2.write_text(
        "<!-- Chasqui Scout Tensor\n"
        "     Run: 2\n"
        "     Model: test/model-b (Test Model B)\n"
        "     Timestamp: 2026-02-18T14:00:00+00:00\n"
        "-->\n\n"
        "# Scout Report\n\n"
        "The file `src/yanantin/foo.py` was reviewed again.\n"
        "Also `tests/test_baz.py` was examined.\n"
    )

    return cairn


@pytest.fixture
def project_root(tmp_path):
    """Create a minimal project structure."""
    root = tmp_path / "project"
    root.mkdir()

    # Create source files
    src = root / "src" / "yanantin"
    src.mkdir(parents=True)
    (src / "foo.py").write_text("# foo")
    (src / "bar.py").write_text("# bar")
    (src / "baz.py").write_text("# baz — never reviewed")

    tests = root / "tests"
    tests.mkdir()
    (tests / "test_baz.py").write_text("# test_baz")

    return root


# ── scan_cairn_coverage ─────────────────────────────────────────────


def test_scan_cairn_coverage_extracts_file_references(cairn_dir):
    """Scanning the cairn should find all file paths referenced in reports."""
    coverage = scan_cairn_coverage(cairn_dir)

    assert "src/yanantin/foo.py" in coverage
    assert "src/yanantin/bar.py" in coverage
    assert "tests/test_baz.py" in coverage


def test_scan_cairn_coverage_uses_latest_timestamp(cairn_dir):
    """When a file is reviewed in multiple reports, use the latest timestamp."""
    coverage = scan_cairn_coverage(cairn_dir)

    # foo.py was in both reports; latest is 14:00
    assert coverage["src/yanantin/foo.py"] == datetime(
        2026, 2, 18, 14, 0, 0, tzinfo=timezone.utc
    )

    # bar.py was only in report 1; timestamp is 10:00
    assert coverage["src/yanantin/bar.py"] == datetime(
        2026, 2, 18, 10, 0, 0, tzinfo=timezone.utc
    )


def test_scan_cairn_coverage_empty_cairn(tmp_path):
    """An empty cairn directory returns an empty coverage map."""
    cairn = tmp_path / "empty_cairn"
    cairn.mkdir()
    coverage = scan_cairn_coverage(cairn)
    assert coverage == {}


def test_scan_cairn_coverage_nonexistent_dir(tmp_path):
    """A nonexistent directory returns an empty coverage map."""
    coverage = scan_cairn_coverage(tmp_path / "does_not_exist")
    assert coverage == {}


# ── coverage_weights ────────────────────────────────────────────────


def test_coverage_weights_unreviewed_gets_maximum_weight(project_root):
    """Files not in the coverage map should get maximum weight (epoch 0)."""
    coverage_map = {
        "src/yanantin/foo.py": datetime(2026, 2, 18, 14, 0, 0, tzinfo=timezone.utc),
    }
    candidates = [
        project_root / "src" / "yanantin" / "foo.py",
        project_root / "src" / "yanantin" / "baz.py",  # not reviewed
    ]
    now = datetime(2026, 2, 18, 15, 0, 0, tzinfo=timezone.utc)

    weights = coverage_weights(candidates, coverage_map, project_root, now=now)

    assert len(weights) == 2
    # foo.py: reviewed 1 hour ago = 3600 seconds
    assert weights[0] == pytest.approx(3600.0, abs=1)
    # baz.py: never reviewed, epoch 0 = ~1.77 billion seconds
    assert weights[1] > weights[0] * 100  # massively higher


def test_coverage_weights_recently_reviewed_gets_minimum(project_root):
    """A file just reviewed should get minimum weight (1.0)."""
    now = datetime(2026, 2, 18, 15, 0, 0, tzinfo=timezone.utc)
    coverage_map = {
        "src/yanantin/foo.py": now,  # reviewed right now
    }
    candidates = [project_root / "src" / "yanantin" / "foo.py"]

    weights = coverage_weights(candidates, coverage_map, project_root, now=now)

    # Age is 0 seconds, minimum weight is 1.0
    assert weights[0] == 1.0


def test_coverage_weights_ordering(project_root):
    """Weights should be ordered: never > old > recent."""
    now = datetime(2026, 2, 18, 15, 0, 0, tzinfo=timezone.utc)
    coverage_map = {
        "src/yanantin/foo.py": now - timedelta(hours=1),   # 1 hour ago
        "src/yanantin/bar.py": now - timedelta(days=7),    # 1 week ago
        # baz.py: not in map = epoch 0
    }
    candidates = [
        project_root / "src" / "yanantin" / "foo.py",
        project_root / "src" / "yanantin" / "bar.py",
        project_root / "src" / "yanantin" / "baz.py",
    ]

    weights = coverage_weights(candidates, coverage_map, project_root, now=now)

    # baz (never) > bar (1 week) > foo (1 hour)
    assert weights[2] > weights[1] > weights[0]


# ── coverage_report ─────────────────────────────────────────────────


def test_coverage_report_includes_all_source_files(project_root):
    """The coverage report should list every .py file in the project."""
    coverage_map = {
        "src/yanantin/foo.py": datetime(2026, 2, 18, 14, 0, tzinfo=timezone.utc),
    }

    report = coverage_report(coverage_map, project_root)

    # All .py files should appear
    assert "src/yanantin/foo.py" in report
    assert "src/yanantin/bar.py" in report
    assert "src/yanantin/baz.py" in report
    assert "tests/test_baz.py" in report


def test_coverage_report_reviewed_vs_unreviewed(project_root):
    """Reviewed files have timestamps, unreviewed files have None."""
    coverage_map = {
        "src/yanantin/foo.py": datetime(2026, 2, 18, 14, 0, tzinfo=timezone.utc),
    }

    report = coverage_report(coverage_map, project_root)

    assert report["src/yanantin/foo.py"] is not None
    assert report["src/yanantin/baz.py"] is None


# ── unreviewed_files ────────────────────────────────────────────────


def test_unreviewed_files_lists_all_uncovered(project_root):
    """unreviewed_files should return all files not in the coverage map."""
    coverage_map = {
        "src/yanantin/foo.py": datetime(2026, 2, 18, 14, 0, tzinfo=timezone.utc),
    }

    unreviewed = unreviewed_files(coverage_map, project_root)

    assert "src/yanantin/foo.py" not in unreviewed
    assert "src/yanantin/bar.py" in unreviewed
    assert "src/yanantin/baz.py" in unreviewed


def test_unreviewed_files_empty_when_all_reviewed(project_root):
    """If every file has been reviewed, the list should be empty."""
    now = datetime(2026, 2, 18, 14, 0, tzinfo=timezone.utc)
    # Review every .py file
    coverage_map = {}
    for path in project_root.rglob("*.py"):
        rel = str(path.relative_to(project_root))
        coverage_map[rel] = now

    unreviewed = unreviewed_files(coverage_map, project_root)
    assert unreviewed == []


# ── stalest_files ───────────────────────────────────────────────────


def test_stalest_files_never_reviewed_first(project_root):
    """Never-reviewed files should appear before reviewed files."""
    now = datetime(2026, 2, 18, 15, 0, tzinfo=timezone.utc)
    coverage_map = {
        "src/yanantin/foo.py": now,
    }

    stalest = stalest_files(coverage_map, project_root, n=10)

    # First entries should be None (never reviewed)
    never = [path for path, ts in stalest if ts is None]
    reviewed = [path for path, ts in stalest if ts is not None]

    assert len(never) > 0
    # Never-reviewed should come before reviewed in the list
    if reviewed:
        first_reviewed_idx = next(
            i for i, (_, ts) in enumerate(stalest) if ts is not None
        )
        last_never_idx = max(
            i for i, (_, ts) in enumerate(stalest) if ts is None
        )
        assert last_never_idx < first_reviewed_idx


def test_stalest_files_respects_n_limit(project_root):
    """stalest_files should return at most N entries."""
    coverage_map = {}
    stalest = stalest_files(coverage_map, project_root, n=2)
    assert len(stalest) == 2


# ── Integration: scan + weight ──────────────────────────────────────


def test_scan_then_weight_integration(cairn_dir, project_root):
    """End-to-end: scan cairn, compute weights, verify ordering."""
    coverage_map = scan_cairn_coverage(cairn_dir)

    # foo.py is reviewed most recently, bar.py less recently
    # baz.py is never reviewed (not in any report)
    candidates = [
        project_root / "src" / "yanantin" / "foo.py",
        project_root / "src" / "yanantin" / "bar.py",
        project_root / "src" / "yanantin" / "baz.py",
    ]

    now = datetime(2026, 2, 18, 16, 0, 0, tzinfo=timezone.utc)
    weights = coverage_weights(candidates, coverage_map, project_root, now=now)

    # baz (never) > bar (6 hours ago) > foo (2 hours ago)
    assert weights[2] > weights[1] > weights[0]


# ── Red-bar: coverage tracker must exist ────────────────────────────


def test_coverage_module_importable():
    """The coverage tracker must be importable as a chasqui module."""
    from yanantin.chasqui import coverage  # noqa: F401


def test_scout_file_selection_accepts_coverage_map():
    """select_files_for_scout must accept a coverage_map parameter."""
    import inspect
    from yanantin.chasqui.scout import select_files_for_scout

    sig = inspect.signature(select_files_for_scout)
    assert "coverage_map" in sig.parameters, (
        "select_files_for_scout must accept coverage_map parameter. "
        "Without it, file selection can't be weighted by coverage freshness."
    )


# ── Tensor coverage ───────────────────────────────────────────────


from yanantin.chasqui.coverage import (
    list_tensors,
    scan_tensor_coverage,
    stalest_tensors,
    dynamic_scour_targets,
)


@pytest.fixture
def tensor_cairn(tmp_path):
    """Create a cairn with tensors and scour reports."""
    cairn = tmp_path / "cairn"
    cairn.mkdir()

    # Tensors
    (cairn / "T0_20260207_bounded_verification.md").write_text("# T0")
    (cairn / "T1_20260207_seven_projects.md").write_text("# T1")
    (cairn / "T2_20260207_calibration_recovery.md").write_text("# T2")
    (cairn / "T3_20260208_the_finishing_school.md").write_text("# T3")

    # Scour report that references T0 and T1
    (cairn / "scour_0001_20260220_test-model.md").write_text(
        "<!-- Chasqui Scour Tensor\n"
        "     Run: 1\n"
        "     Model: test/model-a (Test Model A)\n"
        "     Target: T0*\n"
        "     Scope: tensor\n"
        "     Timestamp: 2026-02-20T10:00:00+00:00\n"
        "-->\n\n"
        "# Tensor Analysis\n\n"
        "T0 discusses bounded verification. T1 is referenced too.\n"
    )

    # Later scour that references T0 again
    (cairn / "scour_0002_20260225_test-model.md").write_text(
        "<!-- Chasqui Scour Tensor\n"
        "     Run: 2\n"
        "     Model: test/model-b (Test Model B)\n"
        "     Target: T*\n"
        "     Scope: tensor\n"
        "     Timestamp: 2026-02-25T14:00:00+00:00\n"
        "-->\n\n"
        "# Tensor Analysis\n\n"
        "T0 is foundational. T2 extends the calibration theme.\n"
    )

    return cairn


def test_list_tensors(tensor_cairn):
    """list_tensors finds all T*_*.md files and extracts numbers."""
    tensors = list_tensors(tensor_cairn)
    assert tensors == ["0", "1", "2", "3"]


def test_scan_tensor_coverage_extracts_refs(tensor_cairn):
    """Scanning scour reports extracts tensor references."""
    cov = scan_tensor_coverage(tensor_cairn)
    assert "0" in cov  # T0 in both reports
    assert "1" in cov  # T1 in report 1
    assert "2" in cov  # T2 in report 2


def test_scan_tensor_coverage_uses_latest(tensor_cairn):
    """When a tensor appears in multiple reports, use latest timestamp."""
    cov = scan_tensor_coverage(tensor_cairn)
    # T0 in both reports; latest is Feb 25
    assert cov["0"] == datetime(2026, 2, 25, 14, 0, 0, tzinfo=timezone.utc)
    # T1 only in report 1; Feb 20
    assert cov["1"] == datetime(2026, 2, 20, 10, 0, 0, tzinfo=timezone.utc)


def test_stalest_tensors_never_scoured_first(tensor_cairn):
    """Tensors never referenced in scour reports come first."""
    stalest = stalest_tensors(tensor_cairn, n=10)
    # T3 is never scoured
    assert stalest[0] == ("3", None)


def test_stalest_tensors_ordering(tensor_cairn):
    """After never-scoured, ordered by oldest coverage first."""
    stalest = stalest_tensors(tensor_cairn, n=10)
    # T3 (never) first, then T1 (Feb 20), then T0/T2 (Feb 25)
    assert stalest[0][0] == "3"
    assert stalest[1][0] == "1"


def test_dynamic_scour_targets_includes_stalest(tensor_cairn):
    """Dynamic targets should include the stalest tensors."""
    targets = dynamic_scour_targets(tensor_cairn)
    target_patterns = [t for t, _ in targets]
    # T3 is never scoured, should appear as T3*
    assert "T3*" in target_patterns


def test_dynamic_scour_targets_includes_fixed(tensor_cairn):
    """Dynamic targets always include synthesis and introspection."""
    targets = dynamic_scour_targets(tensor_cairn)
    scopes = [s for _, s in targets]
    assert "synthesis" in scopes
    assert "introspection" in scopes


def test_dynamic_scour_targets_includes_wildcard(tensor_cairn):
    """Dynamic targets always include T* wildcard for broad coverage."""
    targets = dynamic_scour_targets(tensor_cairn)
    assert ("T*", "tensor") in targets
