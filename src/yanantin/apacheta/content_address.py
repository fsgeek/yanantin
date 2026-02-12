"""Content addressing for cairn documents.

The cairn accumulates stones — tensors, scout reports, scour documents,
compaction records. Duplicate documents can creep in through symlinks,
re-ingestion, or concurrent writers. Content addressing gives each
document an identity derived from what it says, not where it lives.

Hash-based identity naturally suppresses duplicates: same content,
same hash, regardless of filename or path.

    uv run python -m yanantin.apacheta.content_address docs/cairn/
    uv run python -m yanantin.apacheta.content_address --check FILE
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

# Prefix length for content hashes. 16 hex chars = 64 bits.
# Birthday bound: ~4 billion documents before 50% collision probability.
# The cairn will not reach that scale.
HASH_PREFIX_LENGTH = 16


def content_hash(text: str) -> str:
    """Compute a stable content hash for a document.

    Normalization:
    - Convert all line endings to \\n (handles \\r\\n, \\r)
    - Collapse runs of whitespace-only lines into a single blank line
    - Strip trailing whitespace from each line
    - Strip leading/trailing blank lines from the whole document

    The result is a SHA-256 hex digest prefix, truncated to
    HASH_PREFIX_LENGTH characters. Same content always produces the
    same hash regardless of trailing whitespace or line ending
    differences.
    """
    # Normalize line endings to \n
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    # Process line by line: strip trailing whitespace
    lines = [line.rstrip() for line in normalized.split("\n")]

    # Collapse runs of blank lines into a single blank line
    collapsed: list[str] = []
    prev_blank = False
    for line in lines:
        if line == "":
            if not prev_blank:
                collapsed.append(line)
            prev_blank = True
        else:
            collapsed.append(line)
            prev_blank = False

    # Strip leading and trailing blank lines
    while collapsed and collapsed[0] == "":
        collapsed.pop(0)
    while collapsed and collapsed[-1] == "":
        collapsed.pop()

    # Join and hash
    content = "\n".join(collapsed)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return digest[:HASH_PREFIX_LENGTH]


class ContentIndex:
    """Index of content hashes for a directory of markdown files.

    Scans a directory tree for .md files, computes content hashes,
    and tracks which paths share the same content.
    """

    def __init__(self) -> None:
        self._hash_to_paths: dict[str, list[Path]] = {}
        self._path_to_hash: dict[Path, str] = {}

    @classmethod
    def from_directory(cls, directory: Path) -> ContentIndex:
        """Build an index by scanning a directory tree for .md files."""
        index = cls()
        if not directory.is_dir():
            return index

        for md_path in sorted(directory.rglob("*.md")):
            # Skip hidden files
            if md_path.name.startswith("."):
                continue
            index.register(md_path)

        return index

    def register(self, path: Path) -> str:
        """Add a file to the index. Returns its content hash.

        If the file cannot be read, returns an empty string and
        does not add it to the index.
        """
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""

        h = content_hash(text)
        resolved = path.resolve()

        self._hash_to_paths.setdefault(h, [])
        if resolved not in [p.resolve() for p in self._hash_to_paths[h]]:
            self._hash_to_paths[h].append(path)
        self._path_to_hash[resolved] = h

        return h

    def duplicates(self) -> dict[str, list[Path]]:
        """Return only hashes that map to more than one path."""
        return {
            h: paths
            for h, paths in self._hash_to_paths.items()
            if len(paths) > 1
        }

    def has_content(self, text: str) -> bool:
        """Check if content with this hash already exists in the index."""
        h = content_hash(text)
        return h in self._hash_to_paths

    def lookup(self, text: str) -> list[Path]:
        """Find all paths containing this content."""
        h = content_hash(text)
        return list(self._hash_to_paths.get(h, []))

    def hash_for_path(self, path: Path) -> str | None:
        """Get the content hash for a registered path."""
        return self._path_to_hash.get(path.resolve())

    def __len__(self) -> int:
        """Number of unique content hashes in the index."""
        return len(self._hash_to_paths)


def deduplicate_report(directory: Path) -> str:
    """Scan a directory for duplicate .md files and produce a report.

    Does not delete anything — reports only.
    """
    index = ContentIndex.from_directory(directory)
    dupes = index.duplicates()

    if not dupes:
        total = len(index)
        return f"No duplicates found among {total} documents in {directory}."

    parts: list[str] = []
    parts.append(f"Duplicate report for {directory}")
    parts.append(f"{'─' * 60}")
    parts.append(f"Total unique hashes: {len(index)}")
    parts.append(f"Duplicate groups: {len(dupes)}")

    total_extra = sum(len(paths) - 1 for paths in dupes.values())
    parts.append(f"Redundant copies: {total_extra}")
    parts.append("")

    for h, paths in sorted(dupes.items()):
        parts.append(f"  hash: {h}")
        for i, p in enumerate(paths):
            marker = "  (original)" if i == 0 else "  (duplicate)"
            # Show path relative to directory if possible
            try:
                display = p.relative_to(directory)
            except ValueError:
                display = p
            parts.append(f"    {display}{marker}")
        parts.append("")

    return "\n".join(parts)


def _check_file(filepath: Path, cairn_dir: Path) -> str:
    """Check if a file's content already exists in the cairn."""
    try:
        text = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return f"Error reading {filepath}: {e}"

    h = content_hash(text)
    index = ContentIndex.from_directory(cairn_dir)

    existing = index.lookup(text)
    # Filter out the file itself
    existing = [p for p in existing if p.resolve() != filepath.resolve()]

    if existing:
        matches = ", ".join(str(p) for p in existing)
        return f"DUPLICATE: {filepath.name} (hash {h}) matches: {matches}"
    else:
        return f"UNIQUE: {filepath.name} (hash {h}) — no duplicates in {cairn_dir}"


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Content-address cairn documents and detect duplicates",
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Directory to scan for duplicates, or file to check with --check",
    )
    parser.add_argument(
        "--check",
        metavar="FILE",
        help="Check if FILE's content already exists in the cairn",
    )

    args = parser.parse_args()

    if args.check:
        filepath = Path(args.check).resolve()
        # Use the positional arg as cairn dir, or default
        cairn_dir = Path(args.path).resolve() if args.path else _default_cairn_dir()
        print(_check_file(filepath, cairn_dir))
    elif args.path:
        directory = Path(args.path).resolve()
        if not directory.is_dir():
            print(f"Error: {directory} is not a directory.", file=sys.stderr)
            sys.exit(1)
        print(deduplicate_report(directory))
    else:
        # Default: scan the cairn
        cairn_dir = _default_cairn_dir()
        print(deduplicate_report(cairn_dir))


def _default_cairn_dir() -> Path:
    """Resolve the default cairn directory from project structure."""
    # Same pattern as rummage.py
    project_root = Path(__file__).resolve().parents[3]
    return project_root / "docs" / "cairn"


if __name__ == "__main__":
    main()
