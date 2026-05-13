"""Pre-registration CLI for memory-tool experiments.

Resolves a panel's criteria against the live OpenRouter catalog, writes
the resolved manifest, patches the experiment's preregistration.yaml with
the resolution fingerprint, and (with --stage) git-adds the files. The
commit itself — which fires yanantin's OTS post-commit hook — is done by
scripts/register-experiment so a human is in the loop for the binding act.

Usage:
    python -m yanantin.experiments.preregister --exp <id> [--dry-run] [--stage]
    python -m yanantin.experiments.preregister --exp <id> --catalog-json <path>   # tests
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from yanantin.experiments.catalog import fetch_openrouter_catalog
from yanantin.experiments.panel import dump_resolved, load_criteria, resolve_panel

MEMTOOLS_ROOT = Path("experiments/memory_tools")


def _load_catalog(catalog_json: str | None) -> list[dict]:
    if catalog_json:
        body = json.loads(Path(catalog_json).read_text(encoding="utf-8"))
        data = body.get("data", body) if isinstance(body, dict) else body
        if not isinstance(data, list):
            raise ValueError(f"catalog file {catalog_json} has no 'data' list")
        return data
    return asyncio.run(fetch_openrouter_catalog())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="preregister")
    parser.add_argument("--exp", required=True, help="experiment id")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stage", action="store_true", help="git add the written files")
    parser.add_argument("--catalog-json", default=None, help="read catalog from file instead of the live API")
    args = parser.parse_args(argv)

    exp_dir = MEMTOOLS_ROOT / args.exp
    prereg_path = exp_dir / "preregistration.yaml"
    if not prereg_path.is_file():
        print(f"error: {prereg_path} not found", file=sys.stderr)
        return 2
    prereg = yaml.safe_load(prereg_path.read_text(encoding="utf-8")) or {}
    panel_id = prereg.get("panel_id")
    if not panel_id:
        print(f"error: {prereg_path} does not name a panel_id", file=sys.stderr)
        return 2

    criteria_path = MEMTOOLS_ROOT / "panels" / f"{panel_id}.criteria.yaml"
    if not criteria_path.is_file():
        print(f"error: {criteria_path} not found", file=sys.stderr)
        return 2

    try:
        criteria = load_criteria(criteria_path)
        catalog = _load_catalog(args.catalog_json)
        panel = resolve_panel(criteria, catalog, resolved_at=datetime.now(timezone.utc))
    except (ValueError, OSError) as exc:
        print(f"error: resolution failed: {exc}", file=sys.stderr)
        return 1

    resolved_path = MEMTOOLS_ROOT / "panels" / f"{panel_id}.resolved.yaml"
    if args.dry_run:
        print(f"[dry-run] would write {resolved_path} with {len(panel.models)} models")
        print(f"[dry-run] catalog_snapshot_sha={panel.catalog_snapshot_sha}")
        return 0

    dump_resolved(panel, resolved_path)
    prereg["panel_resolved"] = str(resolved_path)
    prereg["resolved_at"] = panel.resolved_at.isoformat()
    prereg["catalog_snapshot_sha"] = panel.catalog_snapshot_sha
    prereg_path.write_text(yaml.safe_dump(prereg, sort_keys=False), encoding="utf-8")
    print(f"wrote {resolved_path} ({len(panel.models)} models) and patched {prereg_path}")

    if args.stage:
        subprocess.run(
            ["git", "add", str(resolved_path), str(criteria_path), str(prereg_path)],
            check=True,
        )
        print("staged: " + ", ".join(str(p) for p in (resolved_path, criteria_path, prereg_path)))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
