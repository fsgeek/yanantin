"""Codebase audit tool — generates ground truth from the filesystem.

This module surveys the actual project directory structure and produces
a structured report of what exists. It does NOT parse the blueprint or
any other documentation. A Master Builder instance can compare this
report to what the blueprint claims.

No dependencies on other yanantin modules. Filesystem inspection only.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel


class LayerReport(BaseModel):
    """Report for a single Apacheta source layer."""

    file_count: int
    files: list[str]


class TestSummary(BaseModel):
    """Aggregate test statistics across all test categories."""

    unit_count: int
    integration_count: int
    red_bar_count: int
    total: int
    unit_files: list[str]
    integration_files: list[str]
    red_bar_files: list[str]


class CairnSummary(BaseModel):
    """Summary of the docs/cairn/ tensor archive."""

    tensor_count: int
    tensor_names: list[str]
    scout_count: int
    scout_names: list[str]
    other_count: int
    total_files: int


class CodebaseReport(BaseModel):
    """Complete audit report of the Yanantin codebase."""

    timestamp: datetime
    source_layers: dict[str, LayerReport]
    test_summary: TestSummary
    cairn_summary: CairnSummary
    chasqui_files: list[str]
    scripts: list[str]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_TEST_FUNC_RE = re.compile(r"^\s*def test_", re.MULTILINE)


def _list_py_files(directory: Path, *, exclude_init: bool = True) -> list[str]:
    """List .py filenames in a directory, optionally excluding __init__.py."""
    if not directory.is_dir():
        return []
    names = sorted(
        p.name
        for p in directory.iterdir()
        if p.is_file() and p.suffix == ".py" and (not exclude_init or p.name != "__init__.py")
    )
    return names


def _count_test_functions(file_path: Path) -> int:
    """Count lines matching ``^\\s*def test_`` in a Python file."""
    try:
        text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0
    return len(_TEST_FUNC_RE.findall(text))


def _survey_test_dir(directory: Path) -> tuple[int, list[str]]:
    """Return (test_function_count, file_list) for a test directory."""
    files = _list_py_files(directory, exclude_init=True)
    count = 0
    for name in files:
        count += _count_test_functions(directory / name)
    return count, files


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

APACHETA_LAYERS = (
    "models",
    "interface",
    "backends",
    "operators",
    "renderer",
    "ingest",
    "clients",
)


def survey_codebase(project_root: Path) -> CodebaseReport:
    """Survey the filesystem under *project_root* and return a CodebaseReport.

    This function reads only the filesystem. It does not import any
    yanantin code or parse any documentation files for their semantic
    content.
    """
    project_root = Path(project_root)

    # --- Apacheta source layers ---
    apacheta_root = project_root / "src" / "yanantin" / "apacheta"
    source_layers: dict[str, LayerReport] = {}
    for layer_name in APACHETA_LAYERS:
        layer_dir = apacheta_root / layer_name
        files = _list_py_files(layer_dir, exclude_init=True)
        source_layers[layer_name] = LayerReport(file_count=len(files), files=files)

    # --- Chasqui ---
    chasqui_root = project_root / "src" / "yanantin" / "chasqui"
    chasqui_files = _list_py_files(chasqui_root, exclude_init=True)

    # --- Tests ---
    tests_root = project_root / "tests"
    unit_count, unit_files = _survey_test_dir(tests_root / "unit")
    integration_count, integration_files = _survey_test_dir(tests_root / "integration")
    red_bar_count, red_bar_files = _survey_test_dir(tests_root / "red_bar")

    test_summary = TestSummary(
        unit_count=unit_count,
        integration_count=integration_count,
        red_bar_count=red_bar_count,
        total=unit_count + integration_count + red_bar_count,
        unit_files=unit_files,
        integration_files=integration_files,
        red_bar_files=red_bar_files,
    )

    # --- Cairn ---
    cairn_dir = project_root / "docs" / "cairn"
    tensors: list[str] = []
    scouts: list[str] = []
    other_md: list[str] = []

    if cairn_dir.is_dir():
        for p in sorted(cairn_dir.iterdir()):
            if not p.is_file() or p.suffix != ".md":
                continue
            if p.name.startswith("T") and p.name[1:2].isdigit():
                tensors.append(p.stem)
            elif p.name.startswith("scout_"):
                scouts.append(p.stem)
            else:
                other_md.append(p.stem)

    cairn_summary = CairnSummary(
        tensor_count=len(tensors),
        tensor_names=tensors,
        scout_count=len(scouts),
        scout_names=scouts,
        other_count=len(other_md),
        total_files=len(tensors) + len(scouts) + len(other_md),
    )

    # --- Scripts ---
    scripts_dir = project_root / "scripts"
    scripts = _list_py_files(scripts_dir, exclude_init=True)

    return CodebaseReport(
        timestamp=datetime.now(UTC),
        source_layers=source_layers,
        test_summary=test_summary,
        cairn_summary=cairn_summary,
        chasqui_files=chasqui_files,
        scripts=scripts,
    )


def render_report(report: CodebaseReport) -> str:
    """Render a CodebaseReport as human-readable markdown."""
    lines: list[str] = []

    lines.append("# Codebase Audit Report")
    lines.append(f"*Generated: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}*")
    lines.append("")

    # --- Apacheta source layers ---
    lines.append("## Apacheta Source Layers")
    lines.append("")
    lines.append("| Layer | Files | Contents |")
    lines.append("|-------|-------|----------|")

    total_source_files = 0
    for layer_name, layer in report.source_layers.items():
        contents = ", ".join(layer.files) if layer.files else "(empty)"
        lines.append(f"| {layer_name} | {layer.file_count} | {contents} |")
        total_source_files += layer.file_count

    lines.append("")
    lines.append(f"**Total Apacheta source files:** {total_source_files}")
    lines.append("")

    # --- Test summary ---
    ts = report.test_summary
    lines.append("## Test Summary")
    lines.append("")
    lines.append(f"- Unit: {ts.unit_count} tests across {len(ts.unit_files)} files")
    lines.append(f"- Integration: {ts.integration_count} tests across {len(ts.integration_files)} files")
    lines.append(f"- Red-bar: {ts.red_bar_count} tests across {len(ts.red_bar_files)} files")
    lines.append(f"- **Total: {ts.total}**")
    lines.append("")

    if ts.unit_files:
        lines.append("### Unit test files")
        for f in ts.unit_files:
            lines.append(f"- {f}")
        lines.append("")

    if ts.integration_files:
        lines.append("### Integration test files")
        for f in ts.integration_files:
            lines.append(f"- {f}")
        lines.append("")

    if ts.red_bar_files:
        lines.append("### Red-bar test files")
        for f in ts.red_bar_files:
            lines.append(f"- {f}")
        lines.append("")

    # --- Cairn ---
    cs = report.cairn_summary
    lines.append("## Cairn")
    lines.append("")
    tensor_names = ", ".join(cs.tensor_names) if cs.tensor_names else "(none)"
    lines.append(f"- Tensors: {cs.tensor_count} ({tensor_names})")
    scout_names = ", ".join(cs.scout_names) if cs.scout_names else "(none)"
    lines.append(f"- Scout reports: {cs.scout_count} ({scout_names})")
    if cs.other_count > 0:
        lines.append(f"- Other markdown files: {cs.other_count}")
    lines.append(f"- Total files: {cs.total_files}")
    lines.append("")

    # --- Chasqui ---
    lines.append("## Chasqui")
    lines.append("")
    if report.chasqui_files:
        names = ", ".join(report.chasqui_files)
        lines.append(f"- {len(report.chasqui_files)} source files: {names}")
    else:
        lines.append("- (no source files found)")
    lines.append("")

    # --- Scripts ---
    lines.append("## Scripts")
    lines.append("")
    if report.scripts:
        names = ", ".join(report.scripts)
        lines.append(f"- {len(report.scripts)} scripts: {names}")
    else:
        lines.append("- (no scripts found)")
    lines.append("")

    return "\n".join(lines)
