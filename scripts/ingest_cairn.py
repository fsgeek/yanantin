#!/usr/bin/env python3
"""Ingest cairn tensor files into ArangoDB.

Finds all tensor files (T*.md) in docs/cairn/, parses them through the
markdown parser, and stores them in ArangoDB via ArangoDBBackend.

Follows "log before you parse" principle:
- Log raw filename before attempting to parse
- If parse fails, log error and continue
- Handle ImmutabilityError gracefully (skip already-stored tensors)
- Print summary at end: total files, parsed, stored, skipped, failed

Usage:
    uv run python scripts/ingest_cairn.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from yanantin.apacheta.backends.arango import ArangoDBBackend
from yanantin.apacheta.ingest.markdown_parser import parse_tensor_file
from yanantin.apacheta.interface.errors import ImmutabilityError


def find_tensor_files(cairn_dir: Path) -> list[Path]:
    """Find all tensor markdown files in the cairn directory.

    Looks for files matching T*.md pattern (T0-T12, etc.) and
    conversation_tensor_*.md patterns.
    Excludes scout reports (scout_*.md).
    Deduplicates by resolved path (symlinks and targets).

    Args:
        cairn_dir: Path to docs/cairn/ directory.

    Returns:
        List of paths to tensor files, sorted by name.
    """
    tensor_files = []
    seen_resolved = set()

    # Find all T*.md files (numbered tensors, including symlinks)
    for path in sorted(cairn_dir.glob("T*.md")):
        # Resolve symlinks to actual files
        resolved = path.resolve()
        if not resolved.exists():
            print(f"Warning: {path.name} is a broken symlink, skipping")
            continue

        # Skip if we've already seen this resolved path
        if resolved in seen_resolved:
            print(f"Skipping duplicate: {path.name} -> {resolved.name} (already queued)")
            continue

        seen_resolved.add(resolved)
        tensor_files.append(resolved)
        if path != resolved:
            print(f"Found tensor file: {path.name} -> {resolved.name}")
        else:
            print(f"Found tensor file: {path.name}")

    # Also find conversation_tensor_*.md files that might not be symlinked
    for path in sorted(cairn_dir.glob("conversation_tensor_*.md")):
        resolved = path.resolve()
        if not resolved.exists():
            continue

        if resolved in seen_resolved:
            # Already found via T*.md symlink
            continue

        seen_resolved.add(resolved)
        tensor_files.append(resolved)
        print(f"Found tensor file: {path.name}")

    return sorted(tensor_files, key=lambda p: p.name)


def ingest_tensor(backend: ArangoDBBackend, path: Path) -> tuple[bool, str]:
    """Attempt to parse and store a single tensor file.

    Args:
        backend: ArangoDBBackend instance for storage.
        path: Path to tensor markdown file.

    Returns:
        Tuple of (success, message).
        - (True, "stored") if parsed and stored successfully
        - (True, "skipped") if already exists (ImmutabilityError)
        - (False, error_msg) if parse or store failed
    """
    try:
        # Log before parsing (raw filename)
        print(f"\nProcessing: {path.name}")
        print(f"  Full path: {path}")

        # Parse the tensor
        tensor = parse_tensor_file(path)
        print(f"  Parsed as: {tensor.provenance.author_model_family} "
              f"{tensor.provenance.author_instance_id}")
        print(f"  Tensor ID: {tensor.id}")
        print(f"  Strands: {len(tensor.strands)}")

        # Store in ArangoDB
        backend.store_tensor(tensor)
        print(f"  ✓ Stored successfully")
        return True, "stored"

    except ImmutabilityError as e:
        # Already exists — this is expected, not an error
        print(f"  ⊙ Already exists, skipping")
        return True, "skipped"

    except Exception as e:
        # Parse or store failure — log and continue
        error_msg = f"{type(e).__name__}: {e}"
        print(f"  ✗ Failed: {error_msg}")
        return False, error_msg


def main() -> int:
    """Main entry point for cairn ingestion.

    Returns:
        Exit code: 0 on success, 1 on failure.
    """
    # Find project root (scripts/ is at project root)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    cairn_dir = project_root / "docs" / "cairn"

    if not cairn_dir.exists():
        print(f"Error: cairn directory not found at {cairn_dir}")
        return 1

    print(f"Cairn directory: {cairn_dir}")
    print(f"Looking for tensor files (T*.md)...\n")

    # Find all tensor files
    tensor_files = find_tensor_files(cairn_dir)

    if not tensor_files:
        print("No tensor files found.")
        return 0

    print(f"\nFound {len(tensor_files)} tensor file(s)")
    print("=" * 60)

    # Connect to ArangoDB with least-privilege credentials
    print("\nConnecting to ArangoDB...")
    print("  Host: http://192.168.111.125:8529")
    print("  Database: apacheta")
    print("  User: apacheta_app")

    try:
        backend = ArangoDBBackend(
            host="http://192.168.111.125:8529",
            db_name="apacheta",
            username="apacheta_app",
            password="cxO4YV5JVjj1aE416puRrA",
        )
        print("  ✓ Connected")
    except Exception as e:
        print(f"  ✗ Connection failed: {e}")
        return 1

    # Process each tensor file
    print("\n" + "=" * 60)
    print("Processing tensors...")
    print("=" * 60)

    stored_count = 0
    skipped_count = 0
    failed_count = 0
    failed_files = []

    for path in tensor_files:
        success, status = ingest_tensor(backend, path)
        if success:
            if status == "stored":
                stored_count += 1
            elif status == "skipped":
                skipped_count += 1
        else:
            failed_count += 1
            failed_files.append((path.name, status))

    # Print summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total files found:  {len(tensor_files)}")
    print(f"Stored:             {stored_count}")
    print(f"Skipped (existing): {skipped_count}")
    print(f"Failed:             {failed_count}")

    if failed_files:
        print("\nFailed files:")
        for filename, error in failed_files:
            print(f"  - {filename}")
            print(f"    {error}")

    # Close backend
    backend.close()

    # Exit with appropriate code
    if failed_count > 0:
        print(f"\n⚠ {failed_count} file(s) failed to ingest")
        return 1
    else:
        print("\n✓ All tensor files processed successfully")
        return 0


if __name__ == "__main__":
    sys.exit(main())
