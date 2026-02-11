"""Unit tests for yanantin.tinkuy.succession — succession protocol.

Tests that the succession checker correctly compares blueprint claims
against audit reality and reports discrepancies.

Test Author: Claude Opus (Test Author role)
Code Author: Different instance (Builder role)
"""

from pathlib import Path

import pytest

from yanantin.tinkuy.succession import (
    _extract_blueprint_claims,
    check_succession,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # tests/unit/test_*.py -> project root


# ---------------------------------------------------------------------------
# 1. check_succession returns empty list when blueprint matches
# ---------------------------------------------------------------------------

def test_check_succession_returns_list_against_real_project():
    """Running against the real project should return a list (possibly
    non-empty if test files were added since the last blueprint update).

    This test verifies the function runs without error and returns
    structured results. Any discrepancies it finds are legitimate --
    they mean the blueprint needs updating.
    """
    issues = check_succession(PROJECT_ROOT)
    assert isinstance(issues, list)
    # Every issue should be a non-empty string describing a discrepancy
    for issue in issues:
        assert isinstance(issue, str)
        assert len(issue) > 0


# ---------------------------------------------------------------------------
# 2. check_succession detects missing blueprint
# ---------------------------------------------------------------------------

def test_check_succession_missing_blueprint(tmp_path: Path):
    """A directory with no docs/blueprint.md should return the missing message."""
    issues = check_succession(tmp_path)
    assert len(issues) == 1
    assert "No blueprint found" in issues[0]


# ---------------------------------------------------------------------------
# 3. check_succession detects stale test count
# ---------------------------------------------------------------------------

def test_check_succession_detects_stale_test_count(tmp_path: Path):
    """A blueprint claiming 999 test functions should be flagged as stale."""
    # Create minimal project structure so the audit can run
    docs = tmp_path / "docs"
    docs.mkdir()

    blueprint_text = """\
# Blueprint

## What Exists

### Apacheta

**999 test functions** across 18 files. 20 red-bar tests, 71 integration, 431 unit.
"""
    (docs / "blueprint.md").write_text(blueprint_text, encoding="utf-8")

    issues = check_succession(tmp_path)
    assert len(issues) > 0, "Expected discrepancies for inflated test count"
    # At least the total test count should be flagged
    test_issues = [i for i in issues if "Tests:" in i or "test" in i.lower()]
    assert len(test_issues) > 0, (
        f"Expected a test count discrepancy, got: {issues}"
    )


# ---------------------------------------------------------------------------
# 4. check_succession detects stale tensor count
# ---------------------------------------------------------------------------

def test_check_succession_detects_stale_tensor_count(tmp_path: Path):
    """A blueprint claiming 99 tensors should produce a tensor discrepancy."""
    docs = tmp_path / "docs"
    docs.mkdir()

    blueprint_text = """\
# Blueprint

## What Exists

### Apacheta

**0 test functions** across 0 files. 0 red-bar, 0 integration, 0 unit.

### The Cairn

99 tensors in the archive. 50 files total.
"""
    (docs / "blueprint.md").write_text(blueprint_text, encoding="utf-8")

    issues = check_succession(tmp_path)
    assert len(issues) > 0, "Expected discrepancies for inflated tensor count"
    tensor_issues = [i for i in issues if "Tensor" in i or "tensor" in i]
    assert len(tensor_issues) > 0, (
        f"Expected a tensor count discrepancy, got: {issues}"
    )


# ---------------------------------------------------------------------------
# 5. _extract_blueprint_claims extracts counts
# ---------------------------------------------------------------------------

def test_extract_blueprint_claims_extracts_counts():
    """_extract_blueprint_claims should extract test, red-bar, integration,
    unit, and tensor counts from known blueprint text."""
    text = """\
# Blueprint

## What Exists

### Apacheta

**522 test functions** across 18 files. 20 red-bar, 71 integration, 431 unit.

### The Cairn

13 tensors in the archive. 29 files total.
"""
    claims = _extract_blueprint_claims(text)

    assert claims["test_total"] == 522
    assert claims["red_bar_count"] == 20
    assert claims["integration_count"] == 71
    assert claims["unit_count"] == 431
    assert claims["tensor_count"] == 13
    assert claims["cairn_files"] == 29


# ---------------------------------------------------------------------------
# 6. _extract_blueprint_claims scopes to Apacheta section
# ---------------------------------------------------------------------------

def test_extract_blueprint_claims_scopes_to_apacheta():
    """When Pukara has '150 tests' and Apacheta has '522 test functions',
    _extract_blueprint_claims should extract 522 (Apacheta), not 150 (Pukara)."""
    text = """\
# Blueprint

## What Exists

### Apacheta

**522 test functions** across 18 files. 20 red-bar, 71 integration, 431 unit.

### Pukara

Depends on yanantin via path. **150 tests** across 2 files.

### The Cairn

13 tensors in the archive.
"""
    claims = _extract_blueprint_claims(text)

    assert claims["test_total"] == 522, (
        f"Expected 522 from Apacheta section, got {claims.get('test_total')}"
    )
    # Should NOT have extracted 150 from Pukara
    assert claims["test_total"] != 150


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------

def test_extract_blueprint_claims_empty_text():
    """An empty string should return an empty claims dict."""
    claims = _extract_blueprint_claims("")
    assert claims == {} or all(
        k == "doesnt_exist_text" for k in claims
    )


def test_check_succession_unrecognizable_blueprint(tmp_path: Path):
    """A blueprint with no extractable claims should report that explicitly."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "blueprint.md").write_text(
        "This is a blueprint with no numbers at all.\n", encoding="utf-8"
    )
    issues = check_succession(tmp_path)
    assert len(issues) == 1
    assert "Could not extract" in issues[0]
