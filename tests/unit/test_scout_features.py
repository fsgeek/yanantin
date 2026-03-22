"""Unit tests for scout-related helpers added by the builder."""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from yanantin.apacheta.models.composition import CompositionEdge, RelationType
from yanantin.chasqui.coordinator import _record_verification_edge
from yanantin.chasqui.scout import (
    gather_prior_findings,
    pick_vantage_directory,
    select_files_for_scout,
)


def _write_file(path: Path, contents: str = "pass\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def test_pick_vantage_directory_uses_coverage_weights(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    root.mkdir()

    _write_file(root / "area_a" / "first.py")
    _write_file(root / "area_a" / "notes.md")
    _write_file(root / "area_b" / "hotspot.py")

    coverage_map = {
        "area_a/first.py": 1.0,
        "area_a/notes.md": 1.0,
        "area_b/hotspot.py": 5.0,
    }

    import yanantin.chasqui.coverage as coverage_module

    def fake_coverage_weights(files, _coverage_map, project_root):
        return [coverage_map[str(path.relative_to(project_root))] for path in files]

    monkeypatch.setattr(coverage_module, "coverage_weights", fake_coverage_weights)

    def deterministic_choice(seq, weights, k):
        assert k == 1
        winner = max(range(len(weights)), key=lambda idx: weights[idx])
        return [seq[winner]]

    monkeypatch.setattr(random, "choices", deterministic_choice)

    chosen = pick_vantage_directory(root, coverage_map)

    assert chosen == root / "area_b"
    assert chosen.is_absolute()


def test_pick_vantage_directory_skips_noise_and_falls_back_to_root(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()

    _write_file(root / "lonely.py")  # skipped: parent is project root
    _write_file(root / "docs" / "cairn" / "report.md")  # skipped: cairn subtree
    _write_file(root / "__pycache__" / "ghost.py")  # skipped: noise directory

    chosen = pick_vantage_directory(root)

    assert chosen == root


def test_select_files_for_scout_limits_candidates_to_vantage(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    root.mkdir()

    _write_file(root / "pkg_a" / "inside.py", "print('a')\n")
    _write_file(root / "pkg_a" / "nested" / "deep.md", "nested\n")
    _write_file(root / "pkg_b" / "other.py", "print('b')\n")

    vantage = root / "pkg_a"
    captured: dict[str, list[Path]] = {}

    def deterministic_sample(population, k):
        population_list = list(population)
        captured["population"] = population_list
        return population_list[:k]

    monkeypatch.setattr(random, "sample", deterministic_sample)

    selected = select_files_for_scout(root, max_files=5, vantage=vantage)

    assert captured["population"], "Expected candidates to be recorded"
    assert all(path.is_relative_to(vantage) for path in captured["population"])
    assert all(path.is_relative_to(vantage) for path, _ in selected)


def test_gather_prior_findings_formats_verified_claims(tmp_path):
    root = tmp_path / "workspace"
    vantage = root / "pkg" / "alpha"
    vantage.mkdir(parents=True)

    cairn_dir = root / "docs" / "cairn"
    edges_dir = cairn_dir / "edges"
    edges_dir.mkdir(parents=True)

    def write_edge(name: str, data: dict) -> None:
        (edges_dir / name).write_text(json.dumps(data), encoding="utf-8")

    write_edge(
        "20260324_confirms.json",
        {
            "claim_file": "pkg/alpha/utils.py",
            "relation": "confirms",
            "claim_text": "Guard rails tightened",
            "verified_by": "reviewer-a",
        },
    )

    long_claim = "X" * 130
    write_edge(
        "20260323_denies.json",
        {
            "claim_file": "pkg/alpha/legacy.md",
            "relation": "denies",
            "claim_text": long_claim,
            "verified_by": "reviewer-b",
        },
    )

    write_edge(
        "20260322_confirms.json",
        {
            "claim_file": "pkg/alpha/old.py",
            "relation": "confirms",
            "claim_text": "Should not be listed once limit reached",
            "verified_by": "reviewer-c",
        },
    )

    write_edge(
        "20260320_other.json",
        {
            "claim_file": "pkg/beta/misc.py",
            "relation": "confirms",
            "claim_text": "Different vantage",
            "verified_by": "reviewer-d",
        },
    )

    (edges_dir / "bad.json").write_text("{not-json", encoding="utf-8")

    summary = gather_prior_findings(
        vantage=vantage,
        root=root,
        cairn_dir=cairn_dir,
        max_findings=2,
    )

    assert summary.startswith("## Prior Findings in Your Area")
    assert summary.endswith("What did they miss?\n")

    bullet_lines = [line for line in summary.splitlines() if line.startswith("- [")]
    assert len(bullet_lines) == 2
    assert bullet_lines[0] == "- [CONFIRMED] Guard rails tightened (verified by `reviewer-a`)"

    truncated_claim = long_claim[:117] + "..."
    assert truncated_claim in bullet_lines[1]
    assert "[DENIED]" in bullet_lines[1]
    assert "`reviewer-b`" in bullet_lines[1]
    assert "Should not be listed" not in summary


@pytest.mark.parametrize("scenario", ["missing_edges", "vantage_outside_root"])
def test_gather_prior_findings_returns_empty_when_no_data(tmp_path, scenario):
    root = tmp_path / "workspace"
    root.mkdir()
    vantage = root / "pkg"
    vantage.mkdir(parents=True)

    cairn_dir = root / "docs" / "cairn"

    if scenario == "missing_edges":
        pass  # Edges directory intentionally absent
    else:
        edges_dir = cairn_dir / "edges"
        edges_dir.mkdir(parents=True)
        (edges_dir / "edge.json").write_text(
            json.dumps(
                {
                    "claim_file": "pkg/sample.py",
                    "relation": "confirms",
                    "claim_text": "A claim",
                    "verified_by": "reviewer",
                }
            ),
            encoding="utf-8",
        )
        vantage = tmp_path / "outside"
        vantage.mkdir(parents=True)

    summary = gather_prior_findings(vantage=vantage, root=root, cairn_dir=cairn_dir)

    assert summary == ""


@pytest.mark.parametrize(
    "verdict, relation",
    [("CONFIRMED", "confirms"), ("DENIED", "denies")],
)
def test_record_verification_edge_writes_json(verdict, relation, tmp_path, monkeypatch):
    cairn_dir = tmp_path / f"cairn_{relation}"
    cairn_dir.mkdir()

    from yanantin.chasqui import coordinator as coordinator_module

    fixed_now = datetime(2026, 3, 21, 12, 34, tzinfo=timezone.utc)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now

    monkeypatch.setattr(coordinator_module, "datetime", FixedDateTime)

    result = {
        "verdict": verdict,
        "cairn_path": "docs/cairn/scout_0001.md",
        "source_tensor": "docs/cairn/scout_0000.md",
        "claim": "Claim text",
        "file_path": "src/example.py",
        "source_model": "source",
        "model": "judge",
        "run_number": 7,
    }

    _record_verification_edge(result, cairn_dir)

    edges_dir = cairn_dir / "edges"
    edge_files = list(edges_dir.glob("*.json"))
    assert len(edge_files) == 1
    edge_path = edge_files[0]

    assert relation in edge_path.name
    assert "0007" in edge_path.name
    assert not list(edges_dir.glob("*.tmp"))

    data = json.loads(edge_path.read_text(encoding="utf-8"))
    assert data["relation"] == relation
    assert data["from_report"] == result["cairn_path"]
    assert data["to_report"] == result["source_tensor"]
    assert data["claim_text"] == result["claim"]
    assert data["claim_file"] == result["file_path"]
    assert data["claim_by"] == result["source_model"]
    assert data["verified_by"] == result["model"]
    assert data["timestamp"] == fixed_now.isoformat()


def test_composition_edge_accepts_new_relation_types():
    edge = CompositionEdge(
        from_tensor=uuid4(),
        to_tensor=uuid4(),
        relation_type=RelationType.DEPENDS_ON,
    )

    assert edge.relation_type is RelationType.DEPENDS_ON
    assert RelationType.CONFIRMS.value == "confirms"
    assert RelationType.DENIES.value == "denies"
