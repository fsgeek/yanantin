"""Walk one machine's filesystem to gzipped JSONL, with no database and no credentials.

Runs on the machine being walked, from the published package, so nothing but
this file needs to reach it:

    ssh HOST 'uv run --python 3.14 --no-project --with yanantin==0.2.0 python - --root /' < scripts/walk_corpus.py

Writes ~/.yanantin/corpus/walk-<host>-<stamp>.jsonl.gz and a .manifest.json beside it
(host, machine-id, provider id, counts, times), and prints the manifest. Landing happens
elsewhere (scripts/land_full_corpus.py --from-jsonl), where the credentials are.
"""

from __future__ import annotations

import argparse
import json
import socket
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

# Import order matters in yanantin 0.2.0: yanantin.machine alone is circular.
from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector
from yanantin.recorder.storage.local.linux.batch_landing import write_entries_jsonl

ap = argparse.ArgumentParser()
ap.add_argument("--root", default="/")
ap.add_argument("--out-dir", default=str(Path.home() / ".yanantin" / "corpus"))
args = ap.parse_args()

host = socket.gethostname()
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
out = Path(args.out_dir) / f"walk-{host}-{stamp}.jsonl.gz"
out.parent.mkdir(parents=True, exist_ok=True)

# Save-it-all at the collector, as the July landing decided (land_full_corpus.py
# --all-names): .git, .venv, __pycache__, node_modules are observed too. The path
# excludes (/proc, /sys, /mnt, ...) stay; they are pseudo-filesystems and other silos.
collector = LinuxFilesystemCollector(Path(args.root), exclude_names=frozenset())
started = datetime.now(timezone.utc).isoformat()
t0 = time.monotonic()
entries = write_entries_jsonl(collector.stream_entries(), out)
manifest = {
    "host": host,
    "machine_id": collector._machine_id,
    "provider_id": str(collector.get_provider_id()),
    "root": str(Path(args.root).resolve()),
    "all_names": True,
    "entries": entries,
    "jsonl": str(out),
    "jsonl_bytes": out.stat().st_size,
    "started": started,
    "walk_seconds": round(time.monotonic() - t0, 1),
    "yanantin": version("yanantin"),
}
out.with_suffix("").with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=1))
print(json.dumps(manifest))
