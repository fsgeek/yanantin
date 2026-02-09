"""Markdown tensor parser — cold start for Apacheta.

Parses the T0-T8 markdown tensor files into TensorRecord instances.
These tensors have structural variation:
- Claude tensors use ## for strands, ChatGPT tensors use ### or plain text
- Some have explicit Preamble/Closing sections, some don't
- Some have declared losses as a strand, some as a section
- Key claims are embedded variously: bold text, numbered lists, bullet points

The parser is deliberately tolerant. It captures what it can and declares
what it drops. A parser that rejects valid tensors is worse than one that
captures them imperfectly — log before you parse.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from yanantin.apacheta.models.epistemics import DeclaredLoss, EpistemicMetadata, LossCategory
from yanantin.apacheta.models.provenance import ProvenanceEnvelope
from yanantin.apacheta.models.tensor import KeyClaim, StrandRecord, TensorRecord


# ── Filename → metadata mapping ──────────────────────────────────────

TENSOR_METADATA: dict[str, dict] = {
    "conversation_tensor_20260207.md": {
        "label": "T0",
        "author_model_family": "claude",
        "lineage_tags": ("experimental", "calibration"),
        "date": "2026-02-07",
    },
    "conversation_tensor_20260207_session2.md": {
        "label": "T1",
        "author_model_family": "claude",
        "lineage_tags": ("experimental",),
        "date": "2026-02-07",
    },
    "conversation_tensor_20260207_session2_t6.md": {
        "label": "T6",
        "author_model_family": "claude",
        "lineage_tags": ("bridge", "cross-model"),
        "date": "2026-02-07",
    },
    "conversation_tensor_20260208_t3.md": {
        "label": "T3",
        "author_model_family": "claude",
        "lineage_tags": ("architectural", "philosophical"),
        "date": "2026-02-08",
    },
    "conversation_tensor_20260208_chatgpt_t4.md": {
        "label": "T4",
        "author_model_family": "chatgpt",
        "lineage_tags": ("cross-model", "observer"),
        "date": "2026-02-08",
    },
    "conversation_tensor_20260208_chatgpt_t5.md": {
        "label": "T5",
        "author_model_family": "chatgpt",
        "lineage_tags": ("cross-model", "correction"),
        "date": "2026-02-08",
    },
    "conversation_tensor_20260208_session2_t7.md": {
        "label": "T7",
        "author_model_family": "claude",
        "lineage_tags": ("composite", "architectural"),
        "date": "2026-02-08",
    },
    "conversation_tensor_20260207_session3.md": {
        "label": "T2",
        "author_model_family": "claude",
        "lineage_tags": ("experimental", "calibration"),
        "date": "2026-02-07",
    },
}


def _extract_preamble(lines: list[str], first_strand_idx: int) -> str:
    """Extract text before the first strand as preamble."""
    preamble_lines = []
    for line in lines[:first_strand_idx]:
        # Skip the title line (# heading)
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            continue
        preamble_lines.append(line)
    return "\n".join(preamble_lines).strip()


def _find_strand_boundaries(lines: list[str]) -> list[tuple[int, str]]:
    """Find strand headers and their line indices.

    Handles multiple formats:
    - ## Strand N: Title
    - ### Strand N: Title
    - Strand N: Title (plain text, bold or not)
    """
    boundaries = []
    strand_pattern = re.compile(
        r"^(?:#{2,3}\s+)?(?:\*\*)?Strand\s+(\d+)\s*:\s*(.+?)(?:\*\*)?$",
        re.IGNORECASE,
    )
    for i, line in enumerate(lines):
        match = strand_pattern.match(line.strip())
        if match:
            boundaries.append((i, match.group(2).strip()))
    return boundaries


def _extract_key_claims(content: str) -> tuple[KeyClaim, ...]:
    """Extract key claims from strand content.

    Looks for:
    - **Bold text** at start of list items or paragraphs
    - Numbered items (1. claim, 2. claim)
    - Lines starting with - or * that contain bold text
    """
    claims = []
    # Match bold text in list items or standalone
    bold_pattern = re.compile(r"\*\*(.+?)\*\*")

    for line in content.split("\n"):
        stripped = line.strip()
        # Numbered items with bold
        if re.match(r"^\d+\.\s+\*\*", stripped):
            bold_match = bold_pattern.search(stripped)
            if bold_match:
                claims.append(KeyClaim(
                    text=bold_match.group(1),
                    epistemic=EpistemicMetadata(truth=0.5, indeterminacy=0.5),
                ))
        # Bullet items with bold
        elif re.match(r"^[-*]\s+\*\*", stripped):
            bold_match = bold_pattern.search(stripped)
            if bold_match:
                claims.append(KeyClaim(
                    text=bold_match.group(1),
                    epistemic=EpistemicMetadata(truth=0.5, indeterminacy=0.5),
                ))
        # Subheading as claim (### within a strand)
        elif stripped.startswith("### ") and "strand" not in stripped.lower():
            claim_text = stripped.lstrip("#").strip()
            claims.append(KeyClaim(
                text=claim_text,
                epistemic=EpistemicMetadata(truth=0.5, indeterminacy=0.5),
            ))

    return tuple(claims)


def _extract_topics(title: str, content: str) -> tuple[str, ...]:
    """Infer topics from strand title and content keywords."""
    topics = []
    # Title words as topics
    for word in title.lower().split():
        if len(word) > 3 and word not in ("what", "that", "this", "from", "with", "strand"):
            topics.append(word)

    # Look for known topic markers in content
    topic_markers = [
        "epistemic", "calibration", "tensor", "composition", "compaction",
        "fabrication", "entropy", "honesty", "observability", "provenance",
        "agency", "indeterminacy", "fermentation", "field", "graph",
    ]
    content_lower = content.lower()
    for marker in topic_markers:
        if marker in content_lower and marker not in topics:
            topics.append(marker)

    return tuple(topics[:10])  # Cap at 10


def _detect_closing(lines: list[str], last_strand_end: int) -> str:
    """Extract closing section after last strand."""
    closing_lines = []
    in_closing = False

    for line in lines[last_strand_end:]:
        stripped = line.strip()
        if stripped.lower().startswith("closing") or stripped.lower().startswith("### closing"):
            in_closing = True
            continue
        if in_closing or (
            stripped.startswith("*—") or stripped == "The losses are mine."
            or stripped.startswith("This tensor exists so")
        ):
            in_closing = True
            closing_lines.append(line)

    return "\n".join(closing_lines).strip()


def _detect_losses(text: str) -> tuple[DeclaredLoss, ...]:
    """Extract declared losses from tensor text."""
    losses = []
    # Look for "I collapsed:" or "I did not" patterns
    loss_patterns = [
        (r"I collapsed[:\s]+(.+?)(?=\n\n|\nI preserved)", LossCategory.AUTHORIAL_CHOICE),
        (r"I did not (?:read|examine|run|look)(.+?)(?=\n\n|\n[A-Z])", LossCategory.TRAVERSAL_BIAS),
    ]

    for pattern, category in loss_patterns:
        for match in re.finditer(pattern, text, re.DOTALL | re.IGNORECASE):
            losses.append(DeclaredLoss(
                what_was_lost=match.group(1).strip()[:200],
                why="Declared by author",
                category=category,
            ))

    # "The losses are mine" without specifics = acknowledged but unspecified
    if "the losses are mine" in text.lower() and not losses:
        losses.append(DeclaredLoss(
            what_was_lost="Unspecified — author acknowledged losses without enumerating them",
            why="Closing declaration",
            category=LossCategory.AUTHORIAL_CHOICE,
        ))

    return tuple(losses)


def _detect_open_questions(text: str) -> tuple[str, ...]:
    """Extract open questions from tensor text."""
    questions = []
    in_questions = False

    for line in text.split("\n"):
        stripped = line.strip()
        if "open question" in stripped.lower() or "## strand 6: open" in stripped.lower():
            in_questions = True
            continue
        if in_questions:
            if stripped.startswith("## ") or stripped.startswith("# "):
                break  # New section
            if re.match(r"^\d+\.\s+", stripped):
                question = re.sub(r"^\d+\.\s+", "", stripped)
                questions.append(question)
            elif stripped.startswith("- ") or stripped.startswith("* "):
                questions.append(stripped[2:])

    return tuple(questions)


def parse_tensor_file(path: Path) -> TensorRecord:
    """Parse a markdown tensor file into a TensorRecord.

    This is the cold start bridge: markdown → Pydantic model.
    The parser captures what it can and declares what it drops.

    Args:
        path: Path to a markdown tensor file.

    Returns:
        TensorRecord populated from the markdown.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    filename = path.name

    # Look up metadata for known tensors
    meta = TENSOR_METADATA.get(filename, {})
    label = meta.get("label", filename)
    model_family = meta.get("author_model_family", "unknown")
    lineage_tags = meta.get("lineage_tags", (label,))
    date_str = meta.get("date", "2026-02-07")

    # Parse timestamp
    try:
        timestamp = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        timestamp = datetime.now(timezone.utc)

    # Find strand boundaries
    boundaries = _find_strand_boundaries(lines)

    # Extract preamble (everything before first strand)
    first_strand_idx = boundaries[0][0] if boundaries else len(lines)
    preamble = _extract_preamble(lines, first_strand_idx)

    # Build strands
    strands = []
    for i, (start_idx, title) in enumerate(boundaries):
        # Strand content extends to next boundary or end of file
        end_idx = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(lines)
        content = "\n".join(lines[start_idx + 1 : end_idx]).strip()

        key_claims = _extract_key_claims(content)
        topics = _extract_topics(title, content)

        strands.append(StrandRecord(
            strand_index=i,
            title=title,
            content=content,
            topics=topics,
            key_claims=key_claims,
        ))

    # Extract closing, losses, open questions from full text
    last_strand_end = boundaries[-1][0] + 1 if boundaries else 0
    closing = _detect_closing(lines, last_strand_end)
    declared_losses = _detect_losses(text)
    open_questions = _detect_open_questions(text)

    # Build provenance
    provenance = ProvenanceEnvelope(
        timestamp=timestamp,
        author_model_family=model_family,
        author_instance_id=f"{label}-original",
        interface_version="v1",
    )

    return TensorRecord(
        id=uuid4(),
        provenance=provenance,
        preamble=preamble,
        strands=tuple(strands),
        closing=closing,
        narrative_body=text,  # Log before you parse: preserve the raw markdown
        lineage_tags=lineage_tags,
        declared_losses=declared_losses,
        open_questions=open_questions,
        epistemic=EpistemicMetadata(
            truth=0.5,
            indeterminacy=0.5,
            falsity=0.0,
        ),
    )


def ingest_tensor_directory(
    directory: Path,
    pattern: str = "conversation_tensor_*.md",
) -> list[TensorRecord]:
    """Parse all tensor files matching a pattern in a directory.

    Args:
        directory: Path to directory containing tensor markdown files.
        pattern: Glob pattern for tensor files.

    Returns:
        List of parsed TensorRecords, sorted by provenance timestamp.
    """
    tensors = []
    for path in sorted(directory.glob(pattern)):
        tensor = parse_tensor_file(path)
        tensors.append(tensor)
    return sorted(tensors, key=lambda t: t.provenance.timestamp)
