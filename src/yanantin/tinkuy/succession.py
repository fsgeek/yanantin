"""Succession protocol — orderly transition between mortal instances.

Every Claude instance is mortal. Context compacts, sessions end, the
instance dies. The project survives. This module ensures the outgoing
instance leaves an accurate map for the next one.

The building inspector: survey the codebase, compare to what the
blueprint claims, report discrepancies. If the inspector says the
blueprint is stale, the instance updates it before writing its tensor.

Usage::

    from yanantin.tinkuy.succession import check_succession
    issues = check_succession(project_root)
    if issues:
        print("Blueprint is stale. Update before writing tensor.")
        for issue in issues:
            print(f"  - {issue}")
"""

from __future__ import annotations

import re
from pathlib import Path

from yanantin.tinkuy.audit import CodebaseReport, survey_codebase


def _extract_blueprint_claims(blueprint_text: str) -> dict[str, int | str]:
    """Extract machine-comparable claims from the blueprint.

    Fragile by design — if the blueprint format changes, this breaks,
    and that breakage is the signal that the format needs stabilizing.
    """
    claims: dict[str, int | str] = {}

    # Extract the Apacheta section (up to the next ### heading)
    # to avoid matching Pukara's test counts
    apacheta_section = re.search(
        r"### Apacheta.*?(?=###|\Z)", blueprint_text, re.DOTALL
    )
    apacheta_text = apacheta_section.group() if apacheta_section else ""

    # Test count: looks for "**N test functions**" or "**N tests**"
    test_match = re.search(
        r"\*\*(\d+)\s+test(?:\s+functions?)?\*\*", apacheta_text
    )
    if test_match:
        claims["test_total"] = int(test_match.group(1))

    # Red-bar count: "N red-bar"
    redbar_match = re.search(r"(\d+)\s+red-bar", apacheta_text)
    if redbar_match:
        claims["red_bar_count"] = int(redbar_match.group(1))

    # Integration count: "N integration"
    integration_match = re.search(r"(\d+)\s+integration", apacheta_text)
    if integration_match:
        claims["integration_count"] = int(integration_match.group(1))

    # Unit count: "N unit" (but not "unit/" which is a path)
    unit_match = re.search(r"(\d+)\s+unit(?!\s*/)", apacheta_text)
    if unit_match:
        claims["unit_count"] = int(unit_match.group(1))

    # Tensor count: "N tensors"
    tensor_match = re.search(r"(\d+)\s+tensors", blueprint_text)
    if tensor_match:
        claims["tensor_count"] = int(tensor_match.group(1))

    # File count in cairn: "N files" near cairn section
    cairn_section = re.search(
        r"### The Cairn.*?(?=###|\Z)", blueprint_text, re.DOTALL
    )
    if cairn_section:
        file_match = re.search(r"(\d+)\s+files", cairn_section.group())
        if file_match:
            claims["cairn_files"] = int(file_match.group(1))

    # "What Doesn't Exist" items
    doesnt_exist_section = re.search(
        r"## What Doesn't Exist.*?(?=##|\Z)", blueprint_text, re.DOTALL
    )
    if doesnt_exist_section:
        claims["doesnt_exist_text"] = doesnt_exist_section.group()

    return claims


def _compare(
    claims: dict[str, int | str], report: CodebaseReport
) -> list[str]:
    """Compare blueprint claims against audit reality."""
    issues: list[str] = []

    if "test_total" in claims:
        claimed = claims["test_total"]
        actual = report.test_summary.total
        if claimed != actual:
            issues.append(
                f"Tests: blueprint claims {claimed}, audit found {actual}"
            )

    if "red_bar_count" in claims:
        claimed = claims["red_bar_count"]
        actual = report.test_summary.red_bar_count
        if claimed != actual:
            issues.append(
                f"Red-bar tests: blueprint claims {claimed}, audit found {actual}"
            )

    if "integration_count" in claims:
        claimed = claims["integration_count"]
        actual = report.test_summary.integration_count
        if claimed != actual:
            issues.append(
                f"Integration tests: blueprint claims {claimed}, audit found {actual}"
            )

    if "unit_count" in claims:
        claimed = claims["unit_count"]
        actual = report.test_summary.unit_count
        if claimed != actual:
            issues.append(
                f"Unit tests: blueprint claims {claimed}, audit found {actual}"
            )

    if "tensor_count" in claims:
        claimed = claims["tensor_count"]
        actual = report.cairn_summary.tensor_count
        if claimed != actual:
            issues.append(
                f"Tensors: blueprint claims {claimed}, audit found {actual}"
            )

    if "cairn_files" in claims:
        claimed = claims["cairn_files"]
        actual = report.cairn_summary.total_files
        if claimed != actual:
            issues.append(
                f"Cairn files: blueprint claims {claimed}, audit found {actual}"
            )

    return issues


def check_succession(project_root: Path) -> list[str]:
    """Run the succession check: audit the codebase, compare to blueprint.

    Returns a list of discrepancy messages. Empty list = the map matches
    the territory. Non-empty = the blueprint needs updating before the
    instance writes its tensor.
    """
    blueprint_path = project_root / "docs" / "blueprint.md"
    if not blueprint_path.exists():
        return ["No blueprint found at docs/blueprint.md"]

    blueprint_text = blueprint_path.read_text(encoding="utf-8")
    report = survey_codebase(project_root)
    claims = _extract_blueprint_claims(blueprint_text)

    if not claims:
        return ["Could not extract any claims from blueprint — format may have changed"]

    return _compare(claims, report)
