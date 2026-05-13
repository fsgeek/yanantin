from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys

import yaml

from yanantin.experiments.preregister import main


def _catalog_fixture_path() -> Path:
    return (Path(__file__).parent / "fixtures" / "openrouter_models_sample.json").resolve()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _init_tmp_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)


def _write_memory_tool_layout(tmp_path: Path, exp: str = "exp_alpha", panel: str = "panel_alpha") -> Path:
    mem_root = tmp_path / "experiments" / "memory_tools"
    (mem_root / exp).mkdir(parents=True, exist_ok=True)
    (mem_root / "panels").mkdir(parents=True, exist_ok=True)

    prereg = {
        "experiment_id": exp,
        "panel_id": panel,
        "tool_variants": ["find_objects_v1"],
        "prompt_templates": ["name_effect_v1"],
    }
    (mem_root / exp / "preregistration.yaml").write_text(
        yaml.safe_dump(prereg, sort_keys=False), encoding="utf-8"
    )

    criteria = {
        "panel_id": panel,
        "rationale": "test panel",
        "context_length_min": 0,
        "exclude_patterns": [],
        "candidates": [
            {
                "id": "meta-llama/llama-4-scout",
                "family": "llama",
                "size_tier": "large-open",
                "cost_tier": "cheap",
            }
        ],
    }
    (mem_root / "panels" / f"{panel}.criteria.yaml").write_text(
        yaml.safe_dump(criteria, sort_keys=False), encoding="utf-8"
    )
    return mem_root


def test_preregister_writes_resolved_manifest_and_prereg_fields(tmp_path: Path, monkeypatch) -> None:
    mem_root = _write_memory_tool_layout(tmp_path)
    monkeypatch.chdir(tmp_path)

    rc = main(
        [
            "--exp",
            "exp_alpha",
            "--catalog-json",
            str(_catalog_fixture_path()),
        ]
    )

    assert rc == 0
    resolved_path = mem_root / "panels" / "panel_alpha.resolved.yaml"
    prereg_path = mem_root / "exp_alpha" / "preregistration.yaml"

    assert resolved_path.exists()
    prereg = yaml.safe_load(prereg_path.read_text(encoding="utf-8"))
    resolved = yaml.safe_load(resolved_path.read_text(encoding="utf-8"))

    assert prereg["panel_resolved"] == "experiments/memory_tools/panels/panel_alpha.resolved.yaml"
    assert "resolved_at" in prereg
    datetime.fromisoformat(prereg["resolved_at"].replace("Z", "+00:00"))
    assert prereg["catalog_snapshot_sha"] == resolved["catalog_snapshot_sha"]
    assert len(prereg["catalog_snapshot_sha"]) == 64
    assert all(c in "0123456789abcdef" for c in prereg["catalog_snapshot_sha"])
    assert isinstance(resolved["models"], list)
    assert len(resolved["models"]) >= 1


def test_preregister_dry_run_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    mem_root = _write_memory_tool_layout(tmp_path)
    prereg_path = mem_root / "exp_alpha" / "preregistration.yaml"
    before = prereg_path.read_text(encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    rc = main(
        [
            "--exp",
            "exp_alpha",
            "--dry-run",
            "--catalog-json",
            str(_catalog_fixture_path()),
        ]
    )

    assert rc == 0
    assert prereg_path.read_text(encoding="utf-8") == before
    assert not (mem_root / "panels" / "panel_alpha.resolved.yaml").exists()


def test_preregister_stage_git_adds_expected_three_files(tmp_path: Path, monkeypatch) -> None:
    mem_root = _write_memory_tool_layout(tmp_path)
    _init_tmp_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    rc = main(
        [
            "--exp",
            "exp_alpha",
            "--stage",
            "--catalog-json",
            str(_catalog_fixture_path()),
        ]
    )
    assert rc == 0

    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    expected = {
        "experiments/memory_tools/exp_alpha/preregistration.yaml",
        "experiments/memory_tools/panels/panel_alpha.criteria.yaml",
        "experiments/memory_tools/panels/panel_alpha.resolved.yaml",
    }
    assert set(staged) == expected
    assert (mem_root / "panels" / "panel_alpha.resolved.yaml").exists()


def test_preregister_errors_when_preregistration_missing(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "experiments" / "memory_tools" / "ghost_exp").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    rc = main(["--exp", "ghost_exp", "--catalog-json", str(_catalog_fixture_path())])
    err = capsys.readouterr().err

    assert rc != 0
    assert "preregistration.yaml" in err
    assert "error" in err.lower()


def test_preregister_errors_when_panel_id_missing(tmp_path: Path, monkeypatch, capsys) -> None:
    mem_root = tmp_path / "experiments" / "memory_tools"
    (mem_root / "exp_alpha").mkdir(parents=True)
    (mem_root / "exp_alpha" / "preregistration.yaml").write_text(
        yaml.safe_dump({"experiment_id": "exp_alpha"}, sort_keys=False), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    rc = main(["--exp", "exp_alpha", "--catalog-json", str(_catalog_fixture_path())])
    err = capsys.readouterr().err

    assert rc != 0
    assert "panel_id" in err
    assert "error" in err.lower()


def test_register_script_fails_fast_when_preregistration_missing(tmp_path: Path) -> None:
    script = _repo_root() / "scripts" / "register-experiment"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_repo_root() / "src") + os.pathsep + env.get("PYTHONPATH", "")

    proc = subprocess.run(
        [str(script), "ghost_exp"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
    )

    assert proc.returncode != 0
    assert "missing" in proc.stderr.lower()
    assert "preregistration.yaml" in proc.stderr


def test_module_entrypoint_works_with_catalog_json(tmp_path: Path) -> None:
    _write_memory_tool_layout(tmp_path)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_repo_root() / "src") + os.pathsep + env.get("PYTHONPATH", "")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "yanantin.experiments.preregister",
            "--exp",
            "exp_alpha",
            "--catalog-json",
            str(_catalog_fixture_path()),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
    )

    assert proc.returncode == 0
    prereg = yaml.safe_load(
        (tmp_path / "experiments" / "memory_tools" / "exp_alpha" / "preregistration.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert prereg["panel_resolved"] == "experiments/memory_tools/panels/panel_alpha.resolved.yaml"
