"""Rummage — search through tensors, scours, and scout reports.

The cairn accumulates stones. This tool helps you find which stones
mention what. Searches across tensor files, scout reports, scour
documents, and compaction records.

Knows about structure: can search within strands, declared losses,
open questions, or across everything. Returns matches with context.

    uv run python -m yanantin.apacheta.rummage "shared memory"
    uv run python -m yanantin.apacheta.rummage --strands "fabrication"
    uv run python -m yanantin.apacheta.rummage --losses "context"
    uv run python -m yanantin.apacheta.rummage --sources all "Indaleko"
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CAIRN_DIR = PROJECT_ROOT / "docs" / "cairn"

# Known tensor/scour sources beyond the local cairn
KNOWN_SOURCES: dict[str, Path] = {
    "cairn": CAIRN_DIR,
    "ai-honesty": Path.home() / ".claude" / "projects" / "-home-tony-projects-ai-honesty" / "memory",
}

SectionKind = Literal["preamble", "strand", "loss", "question", "closing", "other"]


@dataclass
class Section:
    """A parsed section from a tensor/scour document."""

    kind: SectionKind
    title: str
    content: str
    line_start: int
    line_end: int


@dataclass
class Document:
    """A parsed tensor, scour, or scout document."""

    path: Path
    source: str  # which source collection it came from
    raw_text: str
    sections: list[Section] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def is_tensor(self) -> bool:
        return self.name.startswith("T") and self.name.endswith(".md")

    @property
    def is_scout(self) -> bool:
        return self.name.startswith("scout_")

    @property
    def is_scour(self) -> bool:
        return "_scour_" in self.name or "scour_" in self.name

    @property
    def is_compaction(self) -> bool:
        return self.path.parent.name == "compaction"

    @property
    def kind_label(self) -> str:
        if self.is_tensor:
            return "tensor"
        if self.is_scout:
            return "scout"
        if self.is_scour:
            return "scour"
        if self.is_compaction:
            return "compaction"
        return "document"


@dataclass
class Match:
    """A search result."""

    document: Document
    section: Section | None  # None = matched in full text
    line_number: int
    line_text: str
    context_before: list[str]
    context_after: list[str]


def _classify_section(heading: str) -> SectionKind:
    """Classify a markdown heading into a section kind."""
    lower = heading.lower()
    if "preamble" in lower:
        return "preamble"
    if "strand" in lower:
        return "strand"
    if "loss" in lower or "dropped" in lower:
        return "loss"
    if "question" in lower:
        return "question"
    if "closing" in lower or "for later" in lower or "next instance" in lower:
        return "closing"
    return "other"


def parse_document(path: Path, source: str) -> Document:
    """Parse a markdown document into sections."""
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return Document(path=path, source=source, raw_text="")

    lines = raw.splitlines()
    sections: list[Section] = []
    current_title = ""
    current_kind: SectionKind = "other"
    current_start = 0
    current_lines: list[str] = []

    for i, line in enumerate(lines):
        if re.match(r"^#{1,3}\s+", line):
            # Save previous section
            if current_lines:
                sections.append(Section(
                    kind=current_kind,
                    title=current_title,
                    content="\n".join(current_lines),
                    line_start=current_start,
                    line_end=i - 1,
                ))

            heading_text = re.sub(r"^#{1,3}\s+", "", line).strip()
            current_title = heading_text
            current_kind = _classify_section(heading_text)
            current_start = i
            current_lines = [line]
        else:
            current_lines.append(line)

    # Final section
    if current_lines:
        sections.append(Section(
            kind=current_kind,
            title=current_title,
            content="\n".join(current_lines),
            line_start=current_start,
            line_end=len(lines) - 1,
        ))

    return Document(path=path, source=source, raw_text=raw, sections=sections)


def discover_documents(
    sources: list[str] | None = None,
) -> list[Document]:
    """Find and parse all documents across configured sources."""
    if sources is None:
        sources = list(KNOWN_SOURCES.keys())

    documents: list[Document] = []
    for source_name in sources:
        source_path = KNOWN_SOURCES.get(source_name)
        if source_path is None or not source_path.is_dir():
            continue

        # Scan for markdown files (including subdirectories like compaction/)
        for md_path in sorted(source_path.rglob("*.md")):
            # Skip hidden files and MEMORY.md
            if md_path.name.startswith(".") or md_path.name == "MEMORY.md":
                continue
            documents.append(parse_document(md_path, source_name))

    return documents


def search(
    query: str,
    documents: list[Document],
    section_filter: SectionKind | None = None,
    case_sensitive: bool = False,
    context_lines: int = 2,
) -> list[Match]:
    """Search documents for a pattern. Returns matches with context."""
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(query, flags)
    except re.error:
        # If query isn't valid regex, escape it
        pattern = re.compile(re.escape(query), flags)

    matches: list[Match] = []

    for doc in documents:
        lines = doc.raw_text.splitlines()

        if section_filter:
            # Search only within matching sections
            for section in doc.sections:
                if section.kind != section_filter:
                    continue
                section_lines = section.content.splitlines()
                for j, line in enumerate(section_lines):
                    if pattern.search(line):
                        abs_line = section.line_start + j
                        matches.append(Match(
                            document=doc,
                            section=section,
                            line_number=abs_line + 1,
                            line_text=line,
                            context_before=lines[max(0, abs_line - context_lines):abs_line],
                            context_after=lines[abs_line + 1:abs_line + 1 + context_lines],
                        ))
        else:
            # Search full text
            for i, line in enumerate(lines):
                if pattern.search(line):
                    # Find which section this line belongs to
                    in_section = None
                    for section in doc.sections:
                        if section.line_start <= i <= section.line_end:
                            in_section = section
                            break

                    matches.append(Match(
                        document=doc,
                        section=in_section,
                        line_number=i + 1,
                        line_text=line,
                        context_before=lines[max(0, i - context_lines):i],
                        context_after=lines[i + 1:i + 1 + context_lines],
                    ))

    return matches


def render_matches(matches: list[Match], verbose: bool = False) -> str:
    """Render search results for display."""
    if not matches:
        return "No matches found."

    # Group by document
    by_doc: dict[str, list[Match]] = {}
    for m in matches:
        key = f"{m.document.source}:{m.document.name}"
        by_doc.setdefault(key, []).append(m)

    parts: list[str] = []
    parts.append(f"Found {len(matches)} matches across {len(by_doc)} documents.\n")

    for doc_key, doc_matches in by_doc.items():
        doc = doc_matches[0].document
        parts.append(f"── {doc.kind_label}: {doc.name} ({doc.source}) ──")

        for m in doc_matches:
            section_label = f" [{m.section.kind}: {m.section.title}]" if m.section else ""
            parts.append(f"  L{m.line_number}{section_label}")

            if verbose:
                for ctx in m.context_before:
                    parts.append(f"    | {ctx}")
                parts.append(f"  > | {m.line_text}")
                for ctx in m.context_after:
                    parts.append(f"    | {ctx}")
                parts.append("")
            else:
                # Compact: just the matching line, truncated
                text = m.line_text.strip()
                if len(text) > 120:
                    text = text[:117] + "..."
                parts.append(f"    {text}")

        parts.append("")

    return "\n".join(parts)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Rummage through tensors, scours, and scout reports",
    )
    parser.add_argument("query", help="Search pattern (text or regex)")
    parser.add_argument(
        "--strands", action="store_const", const="strand", dest="section",
        help="Search only within strand sections",
    )
    parser.add_argument(
        "--losses", action="store_const", const="loss", dest="section",
        help="Search only within declared losses sections",
    )
    parser.add_argument(
        "--questions", action="store_const", const="question", dest="section",
        help="Search only within open questions sections",
    )
    parser.add_argument(
        "--closing", action="store_const", const="closing", dest="section",
        help="Search only within closing/next-instance sections",
    )
    parser.add_argument(
        "--sources", nargs="+", default=None,
        help=f"Sources to search (default: all). Available: {', '.join(KNOWN_SOURCES.keys())}",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show context around matches",
    )
    parser.add_argument(
        "--case-sensitive", action="store_true",
        help="Case-sensitive search",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List all available documents instead of searching",
    )

    args = parser.parse_args()

    if args.list:
        docs = discover_documents(args.sources)
        for doc in docs:
            sections = len(doc.sections)
            strands = sum(1 for s in doc.sections if s.kind == "strand")
            print(f"  {doc.kind_label:11s}  {doc.source:12s}  {doc.name}")
            if strands:
                print(f"               {sections} sections, {strands} strands")
        print(f"\n{len(docs)} documents across {len(set(d.source for d in docs))} sources.")
        return

    documents = discover_documents(args.sources)
    matches = search(
        query=args.query,
        documents=documents,
        section_filter=args.section,
        case_sensitive=args.case_sensitive,
    )
    print(render_matches(matches, verbose=args.verbose))


if __name__ == "__main__":
    main()
