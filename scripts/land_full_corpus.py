#!/usr/bin/env python3
# scripts/land_full_corpus.py
"""The full-corpus landing run (goal 2026-07-03, criteria 5-6).

Walk → gzipped JSONL (the retained raw + restart point) → batch landing into
the well-known Objects/Relationships through the Registrar batch APIs → shape
report as an activity fact → throughput gate → re-land idempotence check.

    uv run python scripts/land_full_corpus.py --smoke     # /usr/lib -> apacheta_test, ephemeral
    uv run python scripts/land_full_corpus.py             # / -> production apacheta

The report prints as JSON; every claim in it is measured, none asserted.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
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
from yanantin.infra.config import ApachetaDBConfig, get_database
from yanantin.recorder.storage.local.linux.batch_landing import (
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
    args = ap.parse_args()

    cfg = ApachetaDBConfig()
    if args.smoke:
        args.root = "/usr/lib" if args.root == "/" else args.root
        creds = cfg.get_test_credentials()
        db_name = "apacheta_test"
        sfx = uuid4().hex[:8]
        catalog, objects, rels = f"LandCat_{sfx}", f"LandObj_{sfx}", f"LandRel_{sfx}"
    else:
        creds = cfg.get_app_credentials()
        db_name = cfg.db["database"]
        catalog, objects, rels = "StorageRegistrants", "Objects", "Relationships"

    db = get_database(
        host=cfg.host_url,
        db_name=db_name,
        username=creds["username"],
        password=creds["password"],
    )

    corpus_dir = Path.home() / ".yanantin" / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
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
    collector = (
        LinuxFilesystemCollector(Path(args.root), exclude_names=frozenset())
        if args.all_names
        else LinuxFilesystemCollector(Path(args.root))
    )
    provider_id = collector.get_provider_id()
    summary["provider_id"] = str(provider_id)
    shape = _ShapeAccumulator(str(Path(args.root).resolve()))

    def _observed():
        for entry in collector.stream_entries():
            shape.add(entry)
            yield entry

    t0 = time.monotonic()
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
            registrant_name="linux-local-storage collector",
            registrant_kind="provider",
            description=collector.get_description(),
            contributes_to=[],
        )
    summary["registered"] = True

    # ── Phase 3: batch landing + gate ──
    report = land_jsonl(registrar, jsonl_path, provider_id)
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
    store = ArangoDBActivityStreamStore(
        host=cfg.host_url,
        db_name=db_name,
        username=creds["username"],
        password=creds["password"],
    )
    shape_report = shape.report()
    store.store_fact(
        FactRecord(
            provider_id=provider_id,
            timestamp=datetime.now(timezone.utc),
            data={
                **shape_report.to_fact_data(),
                "landing": report.model_dump(mode="json"),
                "jsonl": str(jsonl_path),
            },
        )
    )
    back = store.query_latest(provider_id)
    summary["shape_fact_roundtrip"] = bool(
        back is not None and back.data.get("object_count") == shape_report.object_count
    )

    # ── Phase 5: re-land — idempotence at scale ──
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
    ok = summary["idempotent"] and summary["shape_fact_roundtrip"] and (
        gate_error is None or args.smoke  # smoke corpus is below the gate size
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
