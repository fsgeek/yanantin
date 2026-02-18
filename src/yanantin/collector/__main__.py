"""Run the Yanantin collector.

    uv run python -m yanantin.collector                    # show machine config
    uv run python -m yanantin.collector filesystem /path   # filesystem snapshot
    uv run python -m yanantin.collector checksum /file     # file checksums
    uv run python -m yanantin.collector fs-events /path    # incremental changes
    uv run python -m yanantin.collector dropbox            # Dropbox listing
    uv run python -m yanantin.collector synthetic fs 100   # synthetic filesystem
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from yanantin.collector.machine_config import (
    collect_and_record,
    collect_machine_config,
    render_machine_config,
)


def _parse_since(value: str | None) -> datetime | None:
    """Parse an ISO datetime string into a timezone-aware datetime."""
    if value is None:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _cmd_default(args: argparse.Namespace) -> None:
    """Default behavior — machine config with optional recording."""
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
        print("  Use --record to persist this snapshot to Apacheta.")
        print()


def _cmd_filesystem(args: argparse.Namespace) -> None:
    """Filesystem snapshot collector."""
    from yanantin.collector.filesystem import LinuxFilesystemCollector

    root = Path(args.path)
    if not root.exists():
        print(f"  Error: {root} does not exist", file=sys.stderr)
        sys.exit(1)

    since = _parse_since(getattr(args, "since", None))
    collector = LinuxFilesystemCollector(root)
    snapshot = collector.collect(since=since)

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
        # Show first 20 entries
        for entry in snapshot.entries[:20]:
            kind = "d" if entry.is_directory else "f"
            link = f" -> {entry.link_target}" if entry.link_target else ""
            print(f"  [{kind}] {entry.path}{link}")
        if len(snapshot.entries) > 20:
            print(f"  ... and {len(snapshot.entries) - 20} more")
        print()

    if getattr(args, "record", False):
        from yanantin.apacheta.backends.memory import InMemoryBackend
        from yanantin.collector.filesystem.recorder import FilesystemRecorder
        from yanantin.collector.models import WranglerEnvelope
        from yanantin.collector.wranglers import DirectWrangler

        backend = InMemoryBackend()
        wrangler = DirectWrangler()
        recorder = FilesystemRecorder(backend)
        envelope = WranglerEnvelope(data=snapshot, provider_id=collector.get_provider_id())
        wrangler.deliver(envelope)
        received = wrangler.receive()
        tensor_id = recorder.record(received)
        if args.json:
            print(json.dumps({"recorded": True, "tensor_id": str(tensor_id)}))
        else:
            print(f"  Recorded as tensor {tensor_id}")
            print()


def _cmd_checksum(args: argparse.Namespace) -> None:
    """Checksum collector."""
    from yanantin.collector.checksum import ChecksumCollector

    file_path = Path(args.path)
    if not file_path.exists():
        print(f"  Error: {file_path} does not exist", file=sys.stderr)
        sys.exit(1)

    algorithms = tuple(args.algorithms.split(",")) if args.algorithms else None
    collector = ChecksumCollector(file_path, **({"algorithms": algorithms} if algorithms else {}))
    data = collector.collect()

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

    if getattr(args, "record", False):
        from yanantin.apacheta.backends.memory import InMemoryBackend
        from yanantin.collector.checksum import ChecksumRecorder
        from yanantin.collector.models import WranglerEnvelope
        from yanantin.collector.wranglers import DirectWrangler

        backend = InMemoryBackend()
        wrangler = DirectWrangler()
        recorder = ChecksumRecorder(backend)
        envelope = WranglerEnvelope(data=data, provider_id=collector.get_provider_id())
        wrangler.deliver(envelope)
        received = wrangler.receive()
        tensor_id = recorder.record(received)
        if args.json:
            print(json.dumps({"recorded": True, "tensor_id": str(tensor_id)}))
        else:
            print(f"  Recorded as tensor {tensor_id}")
            print()


def _cmd_fs_events(args: argparse.Namespace) -> None:
    """Filesystem events collector."""
    from yanantin.collector.fs_events import FsIncrementalCollector

    volumes = [args.path]
    state_file = Path(args.state_file) if args.state_file else Path(".fs_events_state.json")
    since = _parse_since(getattr(args, "since", None))

    collector = FsIncrementalCollector(volumes, state_file)
    batch = collector.collect(since=since)

    if args.json:
        print(batch.model_dump_json(indent=2))
    else:
        print()
        print(f"  Filesystem Events")
        print("  " + "\u2500" * 40)
        print(f"  Volumes:  {', '.join(batch.volumes)}")
        print(f"  Events:   {len(batch.events)}")
        print(f"  Last run: {batch.last_run or 'first run'}")
        if since:
            print(f"  Since:    {since.isoformat()}")
        print()
        # Show first 20 events
        for event in batch.events[:20]:
            print(f"  [{event.event_type:8s}] {event.file_path}")
        if len(batch.events) > 20:
            print(f"  ... and {len(batch.events) - 20} more")
        print()

    if getattr(args, "record", False):
        from yanantin.apacheta.backends.memory import InMemoryBackend
        from yanantin.collector.fs_events.recorder import FsEventRecorder
        from yanantin.collector.models import WranglerEnvelope
        from yanantin.collector.wranglers import DirectWrangler

        backend = InMemoryBackend()
        wrangler = DirectWrangler()
        recorder = FsEventRecorder(backend)
        envelope = WranglerEnvelope(data=batch, provider_id=collector.get_provider_id())
        wrangler.deliver(envelope)
        received = wrangler.receive()
        tensor_id = recorder.record(received)
        if args.json:
            print(json.dumps({"recorded": True, "tensor_id": str(tensor_id)}))
        else:
            print(f"  Recorded as tensor {tensor_id}")
            print()


def _cmd_dropbox(args: argparse.Namespace) -> None:
    """Dropbox collector."""
    from yanantin.collector.dropbox import DropboxCollector

    config_dir = Path(args.config_dir) if args.config_dir else Path.home() / ".config" / "yanantin" / "dropbox"
    collector = DropboxCollector(config_dir)
    listing = collector.collect()

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

    if getattr(args, "record", False):
        from yanantin.apacheta.backends.memory import InMemoryBackend
        from yanantin.collector.dropbox.recorder import DropboxRecorder
        from yanantin.collector.models import WranglerEnvelope
        from yanantin.collector.wranglers import DirectWrangler

        backend = InMemoryBackend()
        wrangler = DirectWrangler()
        recorder = DropboxRecorder(backend)
        envelope = WranglerEnvelope(data=listing, provider_id=collector.get_provider_id())
        wrangler.deliver(envelope)
        received = wrangler.receive()
        tensor_id = recorder.record(received)
        if args.json:
            print(json.dumps({"recorded": True, "tensor_id": str(tensor_id)}))
        else:
            print(f"  Recorded as tensor {tensor_id}")
            print()


def _cmd_synthetic(args: argparse.Namespace) -> None:
    """Synthetic data generators."""
    collector_type = args.type
    count = args.count
    seed = args.seed

    if collector_type == "fs":
        from yanantin.collector.filesystem import SyntheticFilesystemCollector

        collector = SyntheticFilesystemCollector(seed=seed)
        snapshot = collector.collect()
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

    elif collector_type == "checksum":
        from yanantin.collector.checksum import SyntheticChecksumCollector

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
        from yanantin.collector.fs_events import SyntheticFsEventCollector

        collector = SyntheticFsEventCollector(seed=seed, events_per_batch=count)
        batch = collector.collect()
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

    elif collector_type == "dropbox":
        from yanantin.collector.dropbox import SyntheticDropboxCollector

        collector = SyntheticDropboxCollector(seed=seed, total_entries=count)
        listing = collector.collect()
        if args.json:
            print(listing.model_dump_json(indent=2))
        else:
            print()
            print(f"  Synthetic Dropbox (seed={seed}, count={count})")
            print("  " + "\u2500" * 40)
            print(f"  Files:   {listing.total_files}")
            print(f"  Folders: {listing.total_folders}")
            print()

    else:
        print(f"  Unknown synthetic type: {collector_type}", file=sys.stderr)
        print("  Available: fs, checksum, events, dropbox", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collector \u2014 bring human-side data into Yanantin",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    subparsers = parser.add_subparsers(dest="command")

    # filesystem
    fs_parser = subparsers.add_parser("filesystem", help="Filesystem snapshot")
    fs_parser.add_argument("path", help="Root directory to scan")
    fs_parser.add_argument("--record", action="store_true", help="Record to Apacheta")
    fs_parser.add_argument("--since", default=None, help="ISO datetime filter (mtime >= since)")

    # checksum
    cksum_parser = subparsers.add_parser("checksum", help="File checksums")
    cksum_parser.add_argument("path", help="File to hash")
    cksum_parser.add_argument(
        "--algorithms", default=None,
        help="Comma-separated hash algorithms (default: sha256,sha1,md5)",
    )
    cksum_parser.add_argument("--record", action="store_true", help="Record to Apacheta")

    # fs-events
    fse_parser = subparsers.add_parser("fs-events", help="Incremental filesystem changes")
    fse_parser.add_argument("path", help="Volume to monitor")
    fse_parser.add_argument(
        "--state-file", default=None,
        help="State file path (default: .fs_events_state.json)",
    )
    fse_parser.add_argument("--record", action="store_true", help="Record to Apacheta")
    fse_parser.add_argument("--since", default=None, help="ISO datetime filter")

    # dropbox
    dbx_parser = subparsers.add_parser("dropbox", help="Dropbox file listing")
    dbx_parser.add_argument(
        "--config-dir", default=None,
        help="Dropbox config directory (default: ~/.config/yanantin/dropbox)",
    )
    dbx_parser.add_argument("--record", action="store_true", help="Record to Apacheta")

    # synthetic
    syn_parser = subparsers.add_parser("synthetic", help="Synthetic data generators")
    syn_parser.add_argument("type", help="Generator type: fs, checksum, events, dropbox")
    syn_parser.add_argument("count", nargs="?", type=int, default=10, help="Number of items")
    syn_parser.add_argument("--seed", type=int, default=42, help="Random seed")

    # Legacy flags for default (no subcommand) behavior
    parser.add_argument("--record", action="store_true", help="Record snapshot to Apacheta")
    parser.add_argument(
        "--backend", choices=["memory"], default="memory",
        help="Storage backend for --record (default: memory)",
    )

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
    elif args.command == "synthetic":
        _cmd_synthetic(args)


if __name__ == "__main__":
    main()
