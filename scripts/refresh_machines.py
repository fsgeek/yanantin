"""Nightly refresh of Objects: an incremental walk of each machine, landed here.

Tony's design (2026-10-26): give each re-walk a time and ignore what is older;
periodic full scans validate. For each machine:
  1. its cutoff is the start of its latest completed all-names walk (from the
     landing facts; yanantin.recorder.storage.local.linux.walks); none means a full walk;
  2. it is walked where it lives (scripts/walk_corpus.py over ssh, no credentials there),
     or here for --local;
  3. the walk is landed here with the memory guard (scripts/land_full_corpus.py).
An unreachable machine is skipped and reported. One machine failing does not stop the rest.

    uv run python scripts/refresh_machines.py --hosts ubuntu24 wam-nuc --local [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_DNS, uuid5

from yanantin.activity.backends.arango import ArangoDBActivityStreamStore
from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector
from yanantin.infra.config import ApachetaDBConfig
from yanantin.recorder.storage.local.linux.walks import latest_walk_start

REPO = Path(__file__).resolve().parents[1]
CORPUS = Path.home() / ".yanantin" / "corpus"
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=60"]
REMOTE_UV = "export PATH=$HOME/.local/bin:$PATH; uv run --quiet --python 3.14 --no-project --with yanantin==0.3.0 python -"


def provider_for(machine_id: str):
    return uuid5(NAMESPACE_DNS, f"yanantin.collector.filesystem.{machine_id}")


def cutoff_for(store: ArangoDBActivityStreamStore, provider) -> datetime | None:
    return latest_walk_start(f.data for f in store.query_range(provider))


def land(args_extra: list[str]) -> dict:
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "land_full_corpus.py"), "--no-reland", *args_extra],
        cwd=REPO, capture_output=True, text=True)
    done = [json.loads(line) for line in proc.stdout.splitlines() if line.startswith('{"phase": "landing"')]
    return {"exit": proc.returncode, "landing": done[0] if done else None,
            "stderr_tail": proc.stderr[-600:] if proc.returncode else ""}


def refresh_remote(host: str, store, overlap: float, dry: bool) -> dict:
    mid = subprocess.run([*SSH, host, "cat /etc/machine-id"], capture_output=True, text=True, timeout=60)
    if mid.returncode != 0:
        return {"host": host, "skipped": "unreachable", "detail": mid.stderr.strip()[-200:]}
    provider = provider_for(mid.stdout.strip())
    since = cutoff_for(store, provider)
    out = {"host": host, "provider_id": str(provider), "since": since.isoformat() if since else None}
    if dry:
        return {**out, "dry_run": True}
    walk_args = " --root /" + (f" --since {since.isoformat()} --overlap {overlap}" if since else "")
    walker = (REPO / "scripts" / "walk_corpus.py").read_text()
    walk = subprocess.run([*SSH, host, REMOTE_UV + walk_args], input=walker,
                          capture_output=True, text=True, timeout=4 * 3600)
    manifests = [line for line in walk.stdout.splitlines() if line.startswith('{"host"')]
    if walk.returncode != 0 or not manifests:
        return {**out, "failed": "walk", "detail": walk.stderr[-400:]}
    manifest = json.loads(manifests[-1])
    remote = Path(manifest["jsonl"])
    CORPUS.mkdir(parents=True, exist_ok=True)
    stem = remote.name.removesuffix(".jsonl.gz")
    for suffix in (".jsonl.gz", ".manifest.json"):
        cp = subprocess.run(["scp", "-q", "-o", "BatchMode=yes", f"{host}:{remote.parent}/{stem}{suffix}",
                             str(CORPUS / f"{stem}{suffix}")], capture_output=True, text=True)
        if cp.returncode != 0:
            return {**out, "failed": "copy", "detail": cp.stderr[-300:]}
    landed = land(["--from-jsonl", str(CORPUS / f"{stem}.jsonl.gz")])
    if landed["exit"] == 0 or landed["landing"]:
        # The walk is landed and kept here; the machine's copy is no longer needed.
        subprocess.run([*SSH, host, f"rm -f {remote.parent}/{stem}.jsonl.gz"], capture_output=True)
    return {**out, "entries": manifest["entries"], "walk_seconds": manifest["walk_seconds"], **landed}


def refresh_local(store, overlap: float, dry: bool) -> dict:
    provider = LinuxFilesystemCollector(Path("/")).get_provider_id()
    since = cutoff_for(store, provider)
    out = {"host": "local", "provider_id": str(provider), "since": since.isoformat() if since else None}
    if dry:
        return {**out, "dry_run": True}
    extra = ["--all-names"] + (["--since", since.isoformat(), "--overlap", str(overlap)] if since else [])
    return {**out, **land(extra)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hosts", nargs="*", default=[], help="ssh aliases of machines to walk")
    ap.add_argument("--local", action="store_true", help="also walk this machine")
    ap.add_argument("--overlap", type=float, default=60.0, help="minutes before the cutoff to include")
    ap.add_argument("--dry-run", action="store_true", help="report each machine's cutoff; walk nothing")
    args = ap.parse_args()

    cfg = ApachetaDBConfig()
    creds = cfg.get_app_credentials()
    store = ArangoDBActivityStreamStore(host=cfg.host_url, db_name=cfg.db["database"],
                                        username=creds["username"], password=creds["password"])
    started = datetime.now(timezone.utc).isoformat()
    results = [refresh_remote(h, store, args.overlap, args.dry_run) for h in args.hosts]
    if args.local:
        results.append(refresh_local(store, args.overlap, args.dry_run))
    print(json.dumps({"refresh_started": started, "machines": results}, indent=1, default=str))
    # A landing that completed is a success even when its throughput gate fails
    # (the gate measures speed; land_full_corpus exits 1 for it).
    failed = [r for r in results if "failed" in r or (r.get("exit") not in (None, 0) and not r.get("landing"))]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
