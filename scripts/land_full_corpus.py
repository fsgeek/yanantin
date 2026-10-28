#!/usr/bin/env python3
# scripts/land_full_corpus.py
"""The full-corpus landing run (goal 2026-07-03, criteria 5-6).

Walk → gzipped JSONL (the retained raw + restart point) → batch landing into
the well-known Objects/Relationships through the Registrar batch APIs → shape
report as an activity fact → throughput gate → re-land idempotence check.

    uv run python scripts/land_full_corpus.py --smoke     # /usr/lib -> apacheta_test, ephemeral
    uv run python scripts/land_full_corpus.py             # / -> production apacheta
    uv run python scripts/land_full_corpus.py --from-jsonl WALK.jsonl.gz --no-reland
        # land another machine's walk (scripts/walk_corpus.py), read with its manifest

The report prints as JSON; every claim in it is measured, none asserted.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from yanantin.activity.backends.arango import ArangoDBActivityStreamStore
from yanantin.activity.models import FactRecord
from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector
from yanantin.collector.storage.local.linux.shape_report import (
    _AGE_BUCKET_DAYS,
    _quantile,
    CollectorShapeReport,
)
from yanantin.core.khipu import Khipu
from yanantin.core.registration import Registrar
from yanantin.core.storage_obfuscator import TransparentObfuscator
from yanantin.infra.config import ApachetaDBConfig, get_database, objects_params
from yanantin.recorder.storage.local.linux.batch_landing import (
    _read_entries_jsonl,
    assert_landing_throughput,
    land_jsonl,
    write_entries_jsonl,
)
from yanantin.recorder.storage.local.linux.registration import (
    RECORDER_ID,
    LinuxStorageRegistration,
)
from yanantin.recorder.storage.objects_definition import OBJECTS_DEFINITION


class _ShapeAccumulator:
    """CollectorShapeReport computed incrementally — same math as
    from_snapshot(), without materializing 2.2M entries."""

    def __init__(self, root_path: str) -> None:
        self._now = datetime.now(timezone.utc)
        self._root_depth = root_path.rstrip("/").count("/")
        self.file_count = 0
        self.dir_count = 0
        self.age_buckets: Counter[str] = Counter()
        self.max_depth = 0
        self.ext_counts: Counter[str] = Counter()
        self.sizes: list[int] = []

    def add(self, entry) -> None:
        age_days = (self._now - entry.timestamps.modified).total_seconds() / 86400.0
        label = f">{_AGE_BUCKET_DAYS[-1]}"
        for bound in _AGE_BUCKET_DAYS:
            if age_days <= bound:
                label = f"<={bound}"
                break
        self.age_buckets[label] += 1
        depth = entry.path.rstrip("/").count("/") - self._root_depth
        self.max_depth = max(self.max_depth, depth)
        if entry.is_directory:
            self.dir_count += 1
        else:
            self.file_count += 1
            name = entry.name
            dot = name.rfind(".")
            self.ext_counts[name[dot:].lower() if dot > 0 else ""] += 1
            self.sizes.append(entry.size)

    def report(self) -> CollectorShapeReport:
        sizes = sorted(self.sizes)
        dirs = self.dir_count
        return CollectorShapeReport(
            object_count=self.file_count + self.dir_count,
            file_count=self.file_count,
            dir_count=self.dir_count,
            mtime_age_buckets=dict(self.age_buckets),
            max_depth=self.max_depth,
            mean_files_per_dir=round(self.file_count / dirs, 3) if dirs else 0.0,
            extension_counts=dict(self.ext_counts),
            size_p50=_quantile(sizes, 0.50),
            size_p90=_quantile(sizes, 0.90),
            size_p99=_quantile(sizes, 0.99),
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default="/", help="walk root (default /)")
    ap.add_argument(
        "--smoke",
        action="store_true",
        help="smoke run: /usr/lib -> apacheta_test ephemeral collections",
    )
    ap.add_argument("--out", default=None, help="JSONL(.gz) output path")
    ap.add_argument(
        "--all-names",
        action="store_true",
        help="observe EVERYTHING: lift the exclude-names filter (__pycache__/"
        ".git/.venv/...) — save-it-all at the collector; the path excludes "
        "(/mnt,/proc,...) stay, they are the tenant/pseudo-fs boundary",
    )
    ap.add_argument(
        "--from-jsonl",
        default=None,
        help="land a walk made elsewhere (scripts/walk_corpus.py) instead of walking; "
        "its .manifest.json beside it names the machine",
    )
    ap.add_argument("--no-reland", action="store_true", help="skip the idempotence re-land")
    ap.add_argument(
        "--since",
        default=None,
        help="local incremental walk: keep entries modified or changed after this ISO "
        "time minus --overlap minutes (the previous walk's start)",
    )
    ap.add_argument("--overlap", type=float, default=60.0)
    ap.add_argument(
        "--mem-guard-gib",
        type=float,
        default=9.0,
        help="pause before each write while the database container uses more than this "
        "(arango-objects runs under a 12 GiB cap since 2026-10-28); 0 disables",
    )
    ap.add_argument("--container", default="arango-objects",
                    help="the container the landing writes to (the guard watches it)")
    args = ap.parse_args()
    manifest = None
    if args.from_jsonl:
        mpath = Path(args.from_jsonl).with_suffix("").with_suffix(".manifest.json")
        manifest = json.loads(mpath.read_text())
        args.root = manifest["root"]

    cfg = ApachetaDBConfig()
    if args.smoke:
        args.root = "/usr/lib" if args.root == "/" else args.root
        creds = cfg.get_test_credentials()
        db_name = "apacheta_test"
        sfx = uuid4().hex[:8]
        catalog, objects, rels = f"LandCat_{sfx}", f"LandObj_{sfx}", f"LandRel_{sfx}"
    else:
        catalog, objects, rels = "StorageRegistrants", "Objects", "Relationships"

    if args.smoke:
        target = {"host": cfg.host_url, "db_name": db_name,
                  "username": creds["username"], "password": creds["password"]}
    else:
        # The file index has its own server since 2026-10-28 (arango-objects).
        target = objects_params()
        db_name = target["db_name"]
    db = get_database(**target)

    corpus_dir = Path.home() / ".yanantin" / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.from_jsonl:
        jsonl_path = Path(args.from_jsonl)
    else:
        jsonl_path = Path(args.out) if args.out else corpus_dir / f"walk-{stamp}.jsonl.gz"

    summary: dict = {
        "root": args.root,
        "db": db_name,
        "objects_collection": objects,
        "jsonl": str(jsonl_path),
        "baseline_objects": db.collection(objects).count()
        if db.has_collection(objects)
        else 0,
        "baseline_relationships": db.collection(rels).count()
        if db.has_collection(rels)
        else 0,
    }

    # ── Phase 1: walk → JSONL, shape accumulated on the way past ──
    if manifest is not None:
        # The walking machine's identity, rebuilt from its machine-id; the
        # provider id must come out the same, or the objects would land as
        # another machine's.
        collector = LinuxFilesystemCollector(Path(args.root), machine_id=manifest["machine_id"])
        if str(collector.get_provider_id()) != manifest["provider_id"]:
            raise SystemExit(f"provider id mismatch: manifest {manifest['provider_id']}, "
                             f"recomputed {collector.get_provider_id()}")
        summary["host"] = manifest["host"]
    elif args.all_names:
        collector = LinuxFilesystemCollector(Path(args.root), exclude_names=frozenset())
    else:
        collector = LinuxFilesystemCollector(Path(args.root))
    provider_id = collector.get_provider_id()
    summary["provider_id"] = str(provider_id)
    shape = _ShapeAccumulator(str(Path(args.root).resolve()))

    walk_started = datetime.now(timezone.utc)
    cutoff = None
    if args.since and manifest is None:
        cutoff = datetime.fromisoformat(args.since) - timedelta(minutes=args.overlap)

    def _observed():
        for entry in collector.stream_entries(since=cutoff):
            shape.add(entry)
            yield entry

    t0 = time.monotonic()
    if manifest is not None:
        walked = 0
        for entry in _read_entries_jsonl(jsonl_path):
            shape.add(entry)
            walked += 1
    else:
        walked = write_entries_jsonl(_observed(), jsonl_path)
    walk_elapsed = time.monotonic() - t0
    summary["walked_entries"] = walked
    summary["walk_seconds"] = round(walk_elapsed, 1)
    summary["jsonl_bytes"] = jsonl_path.stat().st_size
    print(json.dumps({"phase": "walk", **summary}), flush=True)

    # ── Phase 2: registrar + registration (idempotent re-registration) ──
    registrar = Registrar(
        db=db,
        khipu=Khipu(db=db, obfuscator=TransparentObfuscator()),
        catalog_collection=catalog,
        name="full-corpus landing",
        description="batch landing of the full filesystem walk",
        owned_collection=objects,
        owned_edge_collection=rels,
        owned_definition=OBJECTS_DEFINITION,
    )
    # Per-registrant idempotent registration: production already holds the
    # recorder (06-28) but THIS collector lineage may be new — register only
    # what's missing, mirroring LinuxStorageRegistration.register()'s shapes.
    registration = LinuxStorageRegistration(registrar, collector)
    if registrar.lookup_by_identifier(RECORDER_ID) is None:
        registrar.register(
            registrant_id=RECORDER_ID,
            registrant_name="linux-local-storage recorder",
            registrant_kind="provider",
            description="records linux filesystem snapshots into Objects",
            contributes_to=[
                t.model_dump(mode="json") for t in registration.CONTRIBUTES_TO
            ],
        )
    if registrar.lookup_by_identifier(provider_id) is None:
        registrar.register(
            registrant_id=provider_id,
            registrant_name="linux-local-storage collector"
            + (f" ({manifest['host']})" if manifest else ""),
            registrant_kind="provider",
            description=collector.get_description(),
            contributes_to=[],
        )
    summary["registered"] = True

    # ── Phase 3: batch landing + gate ──
    paused = {"seconds": 0.0, "times": 0, "checked": 0.0}

    def _mem_guard() -> None:
        """Hold while the database container is near its memory cap: a landing that
        pushes it into the cap restarts it and drops every client's connection."""
        import docker

        # A stats call takes ~2 s (it samples twice); checking before every flush
        # halved throughput. Every 30 s is enough to catch growth toward the cap.
        if time.monotonic() - paused["checked"] < 30:
            return
        paused["checked"] = time.monotonic()
        container = docker.from_env().containers.get(args.container)
        limit = args.mem_guard_gib * 2**30
        def used() -> int:
            # As `docker stats` reports it: usage minus reclaimable inactive file cache.
            m = container.stats(stream=False)["memory_stats"]
            return m.get("usage", 0) - m.get("stats", {}).get("inactive_file", 0)

        while used() > limit:
            if paused["times"] == 0 or paused["seconds"] % 300 < 30:
                print(json.dumps({"phase": "paused", "container_mem_gib": round(used() / 2**30, 1)}), flush=True)
            paused["times"] += 1
            time.sleep(30)
            paused["seconds"] += 30

    report = land_jsonl(registrar, jsonl_path, provider_id,
                        before_flush=_mem_guard if args.mem_guard_gib > 0 else None)
    summary["mem_guard_paused_seconds"] = paused["seconds"]
    summary["landing"] = report.model_dump(mode="json")
    gate_error = None
    try:
        assert_landing_throughput(report)
    except AssertionError as exc:
        gate_error = str(exc)
    summary["throughput_gate"] = gate_error or "PASS"
    summary["objects_after_landing"] = db.collection(objects).count()
    summary["relationships_after_landing"] = db.collection(rels).count()
    print(json.dumps({"phase": "landing", **{k: summary[k] for k in ('landing', 'throughput_gate', 'objects_after_landing', 'relationships_after_landing')}}), flush=True)

    # ── Phase 4: shape report as an activity fact, then read it back ──
    store = ArangoDBActivityStreamStore(**target)
    shape_report = shape.report()
    store.store_fact(
        FactRecord(
            provider_id=provider_id,
            timestamp=datetime.now(timezone.utc),
            data={
                **shape_report.to_fact_data(),
                "landing": report.model_dump(mode="json"),
                "jsonl": str(jsonl_path),
                # What this walk covered, so the next one knows its cutoff
                # (the previous walk's start) and nobody reads an incremental
                # walk's shape as the whole machine's.
                "walk": manifest if manifest is not None else {
                    "host": None,
                    "root": str(Path(args.root).resolve()),
                    "all_names": bool(args.all_names),
                    "incremental": cutoff is not None,
                    "since": args.since,
                    "cutoff": cutoff.isoformat() if cutoff else None,
                    "started": walk_started.isoformat(),
                },
            },
        )
    )
    back = store.query_latest(provider_id)
    summary["shape_fact_roundtrip"] = bool(
        back is not None and back.data.get("object_count") == shape_report.object_count
    )

    # ── Phase 5: re-land — idempotence at scale ──
    if args.no_reland:
        summary["idempotent"] = None  # not checked
    else:
        reland = land_jsonl(registrar, jsonl_path, provider_id)
        summary["reland_seconds"] = round(reland.landing_elapsed_seconds, 1)
        summary["objects_after_reland"] = db.collection(objects).count()
        summary["relationships_after_reland"] = db.collection(rels).count()
        summary["idempotent"] = (
            summary["objects_after_reland"] == summary["objects_after_landing"]
            and summary["relationships_after_reland"]
            == summary["relationships_after_landing"]
        )

    if args.smoke:
        for name in (catalog, objects, rels):
            if db.has_collection(name):
                db.delete_collection(name)
        summary["ephemeral_collections_dropped"] = True

    print(json.dumps({"phase": "done", **summary}, indent=1), flush=True)
    ok = summary["idempotent"] is not False and summary["shape_fact_roundtrip"] and (
        gate_error is None or args.smoke  # smoke corpus is below the gate size
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
