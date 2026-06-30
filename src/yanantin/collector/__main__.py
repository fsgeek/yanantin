"""Run the Yanantin collector.

    uv run python -m yanantin.collector                                   # machine config
    uv run python -m yanantin.collector filesystem /path --store arango   # store facts
    uv run python -m yanantin.collector checksum /file --store duckdb     # store facts
    uv run python -m yanantin.collector fs-events /path --store arango    # store facts
    uv run python -m yanantin.collector dropbox --store arango            # store facts
    uv run python -m yanantin.collector openrouter /export.csv --store arango  # store facts
    uv run python -m yanantin.collector synthetic fs 100 --store memory   # synthetic facts
    uv run python -m yanantin.collector status --store arango             # what the system knows
    uv run python -m yanantin.collector materialize <handle> --store arango  # temporal view

Environment variables for ArangoDB backend:
    YANANTIN_ARANGO_HOST     (default: http://localhost:8529)
    YANANTIN_ARANGO_DB       (default: apacheta)
    YANANTIN_ARANGO_USER     (default: "")
    YANANTIN_ARANGO_PASSWORD (default: "")

Environment variables for DuckDB backend:
    YANANTIN_DUCKDB_PATH     (default: ~/.local/share/yanantin/activity.duckdb)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID


_STORE_CHOICES = ["memory", "duckdb", "arango"]


def _parse_since(value: str | None) -> datetime | None:
    """Parse an ISO datetime string into a timezone-aware datetime."""
    if value is None:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _add_store_flag(parser: argparse.ArgumentParser) -> None:
    """Add --store flag to a subparser."""
    parser.add_argument(
        "--store", choices=_STORE_CHOICES, default=None,
        help="Store facts in activity stream (memory, duckdb, arango)",
    )


def _report_pipeline(result, args: argparse.Namespace) -> None:
    """Report the result of a fact-recording pipeline run."""
    if args.json:
        print(json.dumps({
            "stored": True,
            "backend": result.backend,
            "fact_count": result.fact_count,
            "provider_id": str(result.provider_id),
            "anchor_handle": str(result.anchor_handle) if result.anchor_handle else None,
            "anchor_flushed": result.anchor_flushed,
        }))
    else:
        print(f"  Stored {result.fact_count} facts [{result.backend}]")
        print(f"  Provider: {result.provider_id}")
        if result.anchor_flushed:
            print(f"  Anchor:   {result.anchor_handle}")
        print()


def _store_facts(store_name, recorder_cls, data, provider_id, args):
    """Common path: open store, record facts, wire anchor, report."""
    from yanantin.transport.models import WranglerEnvelope
    from yanantin.collector.pipeline import open_store, record_and_anchor

    store = open_store(store_name)
    recorder = recorder_cls(store)
    envelope = WranglerEnvelope(data=data, provider_id=provider_id)
    result = record_and_anchor(store, recorder, envelope, backend_name=store_name)
    _report_pipeline(result, args)


# -- Subcommand handlers -----------------------------------------------


def _cmd_default(args: argparse.Namespace) -> None:
    """Default behavior — machine config (the exception that IS a tensor)."""
    from yanantin.machine.linux import (
        collect_and_record,
        collect_machine_config,
        render_machine_config,
    )

    data = collect_machine_config()

    if args.json:
        print(data.model_dump_json(indent=2))
    else:
        print()
        print("  Yanantin Collector")
        print("  " + "\u2500" * 40)
        print()
        print("  Machine Configuration")
        print("  " + "\u2500" * 25)
        print(render_machine_config(data))
        print()

    if args.record:
        from yanantin.apacheta.backends.memory import InMemoryBackend

        backend = InMemoryBackend()
        tensor_id = collect_and_record(backend)
        if args.json:
            print(json.dumps({"recorded": True, "tensor_id": str(tensor_id)}))
        else:
            print(f"  Recorded as tensor {tensor_id}")
            print()
    elif not args.json:
        print("  Use --json for machine-readable output.")
        print("  Use --record to persist machine config as a tensor.")
        print("  Use subcommands with --store to collect facts.")
        print()


def _cmd_filesystem(args: argparse.Namespace) -> None:
    """Filesystem snapshot collector."""
    from yanantin.collector.storage.local.linux import LinuxFilesystemCollector

    root = Path(args.path)
    if not root.exists():
        print(f"  Error: {root} does not exist", file=sys.stderr)
        sys.exit(1)

    since = _parse_since(getattr(args, "since", None))
    collector = LinuxFilesystemCollector(root)
    snapshot = collector.collect(since=since)

    if not args.json or not args.store:
        if args.json:
            print(snapshot.model_dump_json(indent=2))
        else:
            print()
            print(f"  Filesystem Snapshot: {snapshot.root_path}")
            print("  " + "\u2500" * 40)
            print(f"  Files:   {snapshot.total_files}")
            print(f"  Dirs:    {snapshot.total_dirs}")
            print(f"  Errors:  {snapshot.error_count}")
            print(f"  Entries: {len(snapshot.entries)}")
            if since:
                print(f"  Since:   {since.isoformat()}")
            print()
            for entry in snapshot.entries[:20]:
                kind = "d" if entry.is_directory else "f"
                link = f" -> {entry.link_target}" if entry.link_target else ""
                print(f"  [{kind}] {entry.path}{link}")
            if len(snapshot.entries) > 20:
                print(f"  ... and {len(snapshot.entries) - 20} more")
            print()

    if args.store:
        from yanantin.recorder.storage.local.linux import FilesystemFactRecorder
        _store_facts(args.store, FilesystemFactRecorder, snapshot, collector.get_provider_id(), args)


def _cmd_checksum(args: argparse.Namespace) -> None:
    """Checksum collector."""
    from yanantin.collector.storage.local.checksum import ChecksumCollector

    file_path = Path(args.path)
    if not file_path.exists():
        print(f"  Error: {file_path} does not exist", file=sys.stderr)
        sys.exit(1)

    algorithms = tuple(args.algorithms.split(",")) if args.algorithms else None
    collector = ChecksumCollector(file_path, **({"algorithms": algorithms} if algorithms else {}))
    data = collector.collect()

    if not args.json or not args.store:
        if args.json:
            print(data.model_dump_json(indent=2))
        else:
            print()
            print(f"  Checksums: {data.file_path}")
            print("  " + "\u2500" * 40)
            print(f"  Size: {data.file_size:,} bytes")
            for alg, digest in data.checksums.items():
                print(f"  {alg:8s}: {digest}")
            print()

    if args.store:
        from yanantin.recorder.storage.local.checksum import ChecksumFactRecorder
        _store_facts(args.store, ChecksumFactRecorder, data, collector.get_provider_id(), args)


def _cmd_fs_events(args: argparse.Namespace) -> None:
    """Filesystem events collector."""
    from yanantin.collector.activity.linux import FsIncrementalCollector

    volumes = [args.path]
    state_file = Path(args.state_file) if args.state_file else Path(".fs_events_state.json")
    since = _parse_since(getattr(args, "since", None))

    collector = FsIncrementalCollector(volumes, state_file)
    batch = collector.collect(since=since)

    if not args.json or not args.store:
        if args.json:
            print(batch.model_dump_json(indent=2))
        else:
            print()
            print("  Filesystem Events")
            print("  " + "\u2500" * 40)
            print(f"  Volumes:  {', '.join(batch.volumes)}")
            print(f"  Events:   {len(batch.events)}")
            print(f"  Last run: {batch.last_run or 'first run'}")
            if since:
                print(f"  Since:    {since.isoformat()}")
            print()
            for event in batch.events[:20]:
                print(f"  [{event.event_type:8s}] {event.file_path}")
            if len(batch.events) > 20:
                print(f"  ... and {len(batch.events) - 20} more")
            print()

    if args.store:
        from yanantin.recorder.activity.linux import FsEventFactRecorder
        _store_facts(args.store, FsEventFactRecorder, batch, collector.get_provider_id(), args)


def _cmd_openrouter(args: argparse.Namespace) -> None:
    """OpenRouter activity collector — reads a CSV export."""
    from yanantin.collector.semantic.openrouter.collector import (
        OpenRouterActivityCollector,
    )

    csv_path = Path(args.path)
    if not csv_path.exists():
        print(f"  Error: {csv_path} does not exist", file=sys.stderr)
        sys.exit(1)

    since = _parse_since(getattr(args, "since", None))
    collector = OpenRouterActivityCollector(csv_path)
    activity = collector.collect(since=since)

    if not args.json or not args.store:
        if args.json:
            print(activity.model_dump_json(indent=2))
        else:
            print()
            print(f"  OpenRouter Activity: {activity.source_file}")
            print("  " + "─" * 40)
            print(f"  Rows: {len(activity.rows)}")
            if since:
                print(f"  Since: {since.isoformat()}")
            print()
            for row in activity.rows[:20]:
                print(f"  [{row.created_at.isoformat()}] {row.model_permaslug}")
            if len(activity.rows) > 20:
                print(f"  ... and {len(activity.rows) - 20} more")
            print()

    if args.store:
        from yanantin.recorder.semantic.openrouter.fact_recorder import (
            OpenRouterFactRecorder,
        )
        _store_facts(args.store, OpenRouterFactRecorder, activity, collector.get_provider_id(), args)


def _cmd_dropbox(args: argparse.Namespace) -> None:
    """Dropbox collector."""
    from yanantin.collector.storage.cloud.dropbox import DropboxCollector

    config_dir = Path(args.config_dir) if args.config_dir else Path.home() / ".config" / "yanantin" / "dropbox"
    collector = DropboxCollector(config_dir)
    listing = collector.collect()

    if not args.json or not args.store:
        if args.json:
            print(listing.model_dump_json(indent=2))
        else:
            print()
            print(f"  Dropbox Listing: {listing.account_email}")
            print("  " + "\u2500" * 40)
            print(f"  Files:   {listing.total_files}")
            print(f"  Folders: {listing.total_folders}")
            print()
            for entry in listing.entries[:20]:
                kind = "d" if entry.entry_type == "folder" else "f"
                size = f" ({entry.size:,}B)" if entry.size else ""
                print(f"  [{kind}] {entry.path_display}{size}")
            if len(listing.entries) > 20:
                print(f"  ... and {len(listing.entries) - 20} more")
            print()

    if args.store:
        from yanantin.recorder.storage.cloud.dropbox import DropboxFactRecorder
        _store_facts(args.store, DropboxFactRecorder, listing, collector.get_provider_id(), args)


def _cmd_synthetic(args: argparse.Namespace) -> None:
    """Synthetic data generators."""
    collector_type = args.type
    count = args.count
    seed = args.seed

    if collector_type == "fs":
        from yanantin.collector.storage.local.linux import SyntheticFilesystemCollector

        collector = SyntheticFilesystemCollector(seed=seed)
        snapshot = collector.collect()

        if not args.json or not args.store:
            if args.json:
                print(snapshot.model_dump_json(indent=2))
            else:
                print()
                print(f"  Synthetic Filesystem (seed={seed})")
                print("  " + "\u2500" * 40)
                print(f"  Entries: {len(snapshot.entries)}")
                print(f"  Files:   {snapshot.total_files}")
                print(f"  Dirs:    {snapshot.total_dirs}")
                print()

        if args.store:
            from yanantin.recorder.storage.local.linux import FilesystemFactRecorder
            _store_facts(args.store, FilesystemFactRecorder, snapshot, collector.get_provider_id(), args)

    elif collector_type == "checksum":
        from yanantin.collector.storage.local.checksum import SyntheticChecksumCollector

        collector = SyntheticChecksumCollector(seed=seed)
        items = collector.collect_batch(count)
        if args.json:
            import json as json_mod
            print(json_mod.dumps([item.model_dump(mode="json") for item in items], indent=2))
        else:
            print()
            print(f"  Synthetic Checksums (seed={seed}, count={count})")
            print("  " + "\u2500" * 40)
            for item in items[:10]:
                print(f"  {item.file_path}: {item.checksums.get('sha256', '')[:16]}...")
            if len(items) > 10:
                print(f"  ... and {len(items) - 10} more")
            print()

    elif collector_type == "events":
        from yanantin.collector.activity.linux import SyntheticFsEventCollector

        collector = SyntheticFsEventCollector(seed=seed, events_per_batch=count)
        batch = collector.collect()

        if not args.json or not args.store:
            if args.json:
                print(batch.model_dump_json(indent=2))
            else:
                print()
                print(f"  Synthetic FS Events (seed={seed}, count={count})")
                print("  " + "\u2500" * 40)
                print(f"  Events: {len(batch.events)}")
                for event in batch.events[:10]:
                    print(f"  [{event.event_type:8s}] {event.file_path}")
                if len(batch.events) > 10:
                    print(f"  ... and {len(batch.events) - 10} more")
                print()

        if args.store:
            from yanantin.recorder.activity.linux import FsEventFactRecorder
            _store_facts(args.store, FsEventFactRecorder, batch, collector.get_provider_id(), args)

    elif collector_type == "dropbox":
        from yanantin.collector.storage.cloud.dropbox import SyntheticDropboxCollector

        collector = SyntheticDropboxCollector(seed=seed, total_entries=count)
        listing = collector.collect()

        if not args.json or not args.store:
            if args.json:
                print(listing.model_dump_json(indent=2))
            else:
                print()
                print(f"  Synthetic Dropbox (seed={seed}, count={count})")
                print("  " + "\u2500" * 40)
                print(f"  Files:   {listing.total_files}")
                print(f"  Folders: {listing.total_folders}")
                print()

        if args.store:
            from yanantin.recorder.storage.cloud.dropbox import DropboxFactRecorder
            _store_facts(args.store, DropboxFactRecorder, listing, collector.get_provider_id(), args)

    else:
        print(f"  Unknown synthetic type: {collector_type}", file=sys.stderr)
        print("  Available: fs, checksum, events, dropbox", file=sys.stderr)
        sys.exit(1)


def _cmd_cloud_synthetic(args: argparse.Namespace) -> None:
    """Run the synthetic cloud storage TOPOLOGY end-to-end: census → fan-out
    (storage + activity legs) → depth-1 feedback edge, against a live ArangoDB
    Objects collection. This is the executable proof of the ayllu data-flow
    topology — a future instance runs this and SEES the feedback edge and fan-out
    turn. Spec: docs/superpowers/specs/2026-06-28-ayllu-cloud-topology-design.md.
    """
    from uuid import uuid4

    from yanantin.activity.backends.memory import InMemoryActivityStreamStore
    from yanantin.collector.storage.cloud.synthetic import SyntheticCloudCollector
    from yanantin.core.khipu import Khipu
    from yanantin.core.registration import Registrar
    from yanantin.core.storage_obfuscator import TransparentObfuscator
    from yanantin.infra.config import ApachetaDBConfig, get_database
    from yanantin.recorder.storage.cloud.synthetic import (
        CloudFactRecorder,
        CloudStorageRecorder,
    )
    from yanantin.recorder.storage.cloud.synthetic.monitor import (
        StorageActivityMonitor,
    )
    from yanantin.recorder.storage.objects_definition import OBJECTS_DEFINITION

    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials() if args.tier == "test" else cfg.get_app_credentials()
    db_name = "apacheta_test" if args.tier == "test" else cfg.db["database"]
    db = get_database(
        host=cfg.host_url, db_name=db_name,
        username=creds["username"], password=creds["password"],
    )

    # Ephemeral per-run collections unless --persist: this is a demonstration of
    # the topology, restartable by design. --persist writes into the well-known
    # Objects so the run is queryable afterward.
    if args.persist:
        catalog, objects, rels = "StorageRegistrants", "Objects", "Relationships"
    else:
        sfx = uuid4().hex[:8]
        catalog, objects, rels = f"Cat_{sfx}", f"Obj_{sfx}", f"Rel_{sfx}"

    registrar = Registrar(
        db=db, khipu=Khipu(db=db, obfuscator=TransparentObfuscator()),
        catalog_collection=catalog,
        name="synthetic-cloud-topology",
        description="runs the cloud fan-out + feedback topology",
        owned_collection=objects, owned_edge_collection=rels,
        owned_definition=OBJECTS_DEFINITION,
    )
    store = InMemoryActivityStreamStore()
    collector = SyntheticCloudCollector(
        seed=args.seed, total_entries=args.entries, change_count=args.changes,
    )
    monitor = StorageActivityMonitor(
        collector, CloudStorageRecorder(registrar), CloudFactRecorder(store),
    )

    try:
        n_census = monitor.census()
        cycles = monitor.poll_until_quiet()
        delta_cycle = cycles[0]
        objects_now = db.collection(objects).count()
        facts_now = store.count_facts()

        report = {
            "census_objects": n_census,
            "poll_cycles_to_quiet": len(cycles),
            "changes_seen": delta_cycle.changes_seen,
            "fan_out_storage_updates": delta_cycle.objects_updated,
            "fan_out_activity_facts": delta_cycle.facts_recorded,
            "feedback_recollects": delta_cycle.recollects,
            "objects_total": objects_now,
            "activity_facts_total": facts_now,
            "persisted": args.persist,
        }
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print()
            print("  Synthetic Cloud Topology — executable")
            print("  " + "─" * 44)
            print(f"  Census:            {n_census} objects -> Objects")
            print(f"  Fan-out (1 delta): {delta_cycle.objects_updated} storage updates "
                  f"+ {delta_cycle.facts_recorded} activity facts")
            print(f"  Feedback edge:     {delta_cycle.recollects} re-collects (depth-1)")
            print(f"  Termination:       {len(cycles)} bounded poll cycles to quiet")
            print(f"  Objects total:     {objects_now} (idempotent — many changes, one doc)")
            print()
            print("  The feedback edge and fan-out turned. Topology made flesh.")
            print()
    finally:
        if not args.persist:
            for n in (catalog, objects, rels):
                if db.has_collection(n):
                    db.delete_collection(n)


def _cmd_status(args: argparse.Namespace) -> None:
    """Show what the activity stream knows."""
    from yanantin.collector.pipeline import open_store

    store = open_store(args.store)
    providers = store.list_providers()
    total = store.count_facts()
    latest_anchor = store.get_latest_anchor()

    if args.json:
        data = {
            "backend": args.store,
            "total_facts": total,
            "provider_count": len(providers),
            "providers": [
                {"id": str(p), "facts": store.count_facts(p)}
                for p in providers
            ],
            "latest_anchor": {
                "handle": str(latest_anchor.handle),
                "timestamp": latest_anchor.timestamp.isoformat(),
                "cursor_count": len(latest_anchor.cursors),
            } if latest_anchor else None,
        }
        print(json.dumps(data, indent=2))
    else:
        print()
        print("  Activity Stream Status")
        print("  " + "\u2500" * 40)
        print(f"  Backend:   {args.store}")
        print(f"  Facts:     {total:,}")
        print(f"  Providers: {len(providers)}")
        print()

        if providers:
            print("  Providers:")
            for p in providers:
                count = store.count_facts(p)
                print(f"    {p}  ({count:,} facts)")
            print()

        if latest_anchor:
            print("  Latest Anchor:")
            print(f"    Handle:    {latest_anchor.handle}")
            print(f"    Timestamp: {latest_anchor.timestamp.isoformat()}")
            print(f"    Cursors:   {len(latest_anchor.cursors)}")
            print()
        else:
            print("  No anchors yet.")
            print()


def _cmd_materialize(args: argparse.Namespace) -> None:
    """Resolve an anchor against current streams."""
    from yanantin.activity.anchor import MemoryAnchorService
    from yanantin.collector.pipeline import open_store

    try:
        handle = UUID(args.handle)
    except ValueError:
        print(f"  Error: '{args.handle}' is not a valid UUID", file=sys.stderr)
        sys.exit(1)

    store = open_store(args.store)
    service = MemoryAnchorService(store)

    try:
        view = service.materialize(handle)
    except Exception as e:
        print(f"  Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        data = {
            "handle": str(view.handle),
            "timestamp": view.timestamp.isoformat(),
            "provider_count": len(view.providers),
            "fact_count": len(view.facts),
            "providers": [str(p) for p in view.providers],
            "facts": {
                str(pid): {
                    "id": str(f.id),
                    "timestamp": f.timestamp.isoformat(),
                    "content_hash": f.content_hash,
                    "data_keys": list(f.data.keys()),
                }
                for pid, f in view.facts.items()
            },
        }
        print(json.dumps(data, indent=2))
    else:
        print()
        print(f"  Anchor View: {view.handle}")
        print("  " + "\u2500" * 40)
        print(f"  Timestamp: {view.timestamp.isoformat()}")
        print(f"  Providers: {len(view.providers)}")
        print(f"  Facts:     {len(view.facts)}")
        print()

        if view.facts:
            print("  Resolved Facts:")
            for pid, fact in view.facts.items():
                print(f"    Provider {pid}:")
                print(f"      Fact:      {fact.id}")
                print(f"      Time:      {fact.timestamp.isoformat()}")
                print(f"      Hash:      {fact.content_hash}")
                print(f"      Data keys: {list(fact.data.keys())}")
            print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collector \u2014 bring human-side data into Yanantin",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    subparsers = parser.add_subparsers(dest="command")

    # filesystem
    fs_parser = subparsers.add_parser("filesystem", help="Filesystem snapshot")
    fs_parser.add_argument("path", help="Root directory to scan")
    fs_parser.add_argument("--since", default=None, help="ISO datetime filter (mtime >= since)")
    _add_store_flag(fs_parser)

    # checksum
    cksum_parser = subparsers.add_parser("checksum", help="File checksums")
    cksum_parser.add_argument("path", help="File to hash")
    cksum_parser.add_argument(
        "--algorithms", default=None,
        help="Comma-separated hash algorithms (default: sha256,sha1,md5)",
    )
    _add_store_flag(cksum_parser)

    # fs-events
    fse_parser = subparsers.add_parser("fs-events", help="Incremental filesystem changes")
    fse_parser.add_argument("path", help="Volume to monitor")
    fse_parser.add_argument(
        "--state-file", default=None,
        help="State file path (default: .fs_events_state.json)",
    )
    fse_parser.add_argument("--since", default=None, help="ISO datetime filter")
    _add_store_flag(fse_parser)

    # dropbox
    dbx_parser = subparsers.add_parser("dropbox", help="Dropbox file listing")
    dbx_parser.add_argument(
        "--config-dir", default=None,
        help="Dropbox config directory (default: ~/.config/yanantin/dropbox)",
    )
    _add_store_flag(dbx_parser)

    # openrouter
    or_parser = subparsers.add_parser("openrouter", help="OpenRouter activity CSV export")
    or_parser.add_argument("path", help="OpenRouter activity CSV file to read")
    or_parser.add_argument("--since", default=None, help="ISO datetime filter (created_at > since)")
    _add_store_flag(or_parser)

    # synthetic
    syn_parser = subparsers.add_parser("synthetic", help="Synthetic data generators")
    syn_parser.add_argument("type", help="Generator type: fs, checksum, events, dropbox")
    syn_parser.add_argument("count", nargs="?", type=int, default=10, help="Number of items")
    syn_parser.add_argument("--seed", type=int, default=42, help="Random seed")
    _add_store_flag(syn_parser)

    # cloud-synthetic — run the cloud fan-out + feedback topology end-to-end
    cloud_parser = subparsers.add_parser(
        "cloud-synthetic",
        help="Run the synthetic cloud topology (census + fan-out + feedback edge)",
    )
    cloud_parser.add_argument("--seed", type=int, default=0, help="Ground-truth seed")
    cloud_parser.add_argument("--entries", type=int, default=12, help="Initial census size")
    cloud_parser.add_argument("--changes", type=int, default=3, help="Delta change count")
    cloud_parser.add_argument(
        "--tier", choices=["test", "app"], default="test",
        help="DB tier (default: test → apacheta_test)",
    )
    cloud_parser.add_argument(
        "--persist", action="store_true",
        help="Write into the well-known Objects (default: ephemeral per-run collections)",
    )
    cloud_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # status — what the activity stream knows
    status_parser = subparsers.add_parser("status", help="Activity stream status")
    status_parser.add_argument("--json", action="store_true", help="Output as JSON")
    status_parser.add_argument(
        "--store", choices=_STORE_CHOICES, required=True,
        help="Backend to query",
    )

    # materialize — resolve an anchor against current streams
    mat_parser = subparsers.add_parser("materialize", help="Resolve an anchor to a temporal view")
    mat_parser.add_argument("handle", help="Anchor handle UUID to materialize")
    mat_parser.add_argument("--json", action="store_true", help="Output as JSON")
    mat_parser.add_argument(
        "--store", choices=_STORE_CHOICES, required=True,
        help="Backend to query",
    )

    # Legacy flag for default (no subcommand) behavior — machine config as tensor
    parser.add_argument("--record", action="store_true", help="Record machine config as tensor")

    args = parser.parse_args()

    if args.command is None:
        _cmd_default(args)
    elif args.command == "filesystem":
        _cmd_filesystem(args)
    elif args.command == "checksum":
        _cmd_checksum(args)
    elif args.command == "fs-events":
        _cmd_fs_events(args)
    elif args.command == "dropbox":
        _cmd_dropbox(args)
    elif args.command == "openrouter":
        _cmd_openrouter(args)
    elif args.command == "synthetic":
        _cmd_synthetic(args)
    elif args.command == "cloud-synthetic":
        _cmd_cloud_synthetic(args)
    elif args.command == "status":
        _cmd_status(args)
    elif args.command == "materialize":
        _cmd_materialize(args)


if __name__ == "__main__":
    main()
