"""Weaver — extract composition declarations from tensor prose.

Reads markdown tensors, finds composition-related language, and
returns structured declarations. Deterministic: regex and keyword
matching only, no LLM calls.

Conservative by design: only extracts declarations where the text
clearly states composition intent. Ambiguous references get low
confidence.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CAIRN_DIR = PROJECT_ROOT / "docs" / "cairn"

# Additional tensor sources (same as rummage.py)
KNOWN_SOURCES: dict[str, Path] = {
    "cairn": CAIRN_DIR,
    "ai-honesty": Path.home()
    / ".claude"
    / "projects"
    / "-home-tony-projects-ai-honesty"
    / "memory",
}

# Tensor name patterns — matches T0, T1, T₀, T₁, T10, T₁₀, etc.
# Unicode subscript digits: ₀₁₂₃₄₅₆₇₈₉
# Also handles LaTeX: T_0, T_{12}
_SUBSCRIPT_MAP = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")

_TENSOR_REF = re.compile(
    r"""
    (?<!\w)                 # Not preceded by word char (avoids mid-word match)
    T                       # Literal T
    (?:                     # Followed by:
        [₀₁₂₃₄₅₆₇₈₉]+   #   Unicode subscript digits
        | _\{?\d+\}?       #   LaTeX subscript: _0, _{12}
        | \d+              #   Plain digits
    )
    (?![_\w])              # Not followed by _ or word char (avoids T0_20260207)
    """,
    re.VERBOSE,
)

# ── Data Structures ──────────────────────────────────────────────


@dataclass
class CompositionDeclaration:
    """A single composition declaration extracted from tensor prose."""

    source: str  # tensor name, e.g. "T15"
    targets: list[str]  # tensor names, e.g. ["T0", "T14"]
    relation: str  # composes_with, does_not_compose_with, corrects, bridges, branches_from, read
    evidence: str  # the quoted text
    confidence: str  # high, medium, low


@dataclass
class TensorFile:
    """A discovered tensor file with its metadata."""

    path: Path
    source_name: str  # which source collection
    tensor_name: str  # normalized name, e.g. "T15"
    raw_text: str = ""

    @property
    def display_name(self) -> str:
        return f"{self.tensor_name} ({self.path.name})"


# ── Normalization ────────────────────────────────────────────────


def normalize_tensor_name(raw: str) -> str:
    """Normalize tensor references to canonical form.

    T₀ -> T0, T₁₂ -> T12, T0 -> T0, T_0 -> T0, T_{12} -> T12, etc.
    """
    # First handle unicode subscripts
    result = raw.translate(_SUBSCRIPT_MAP)
    # Then handle LaTeX subscripts: T_0 -> T0, T_{12} -> T12
    result = re.sub(r"_\{?(\d+)\}?", r"\1", result)
    return result


def _extract_tensor_refs(text: str) -> list[str]:
    """Find all tensor references in a string, normalized."""
    refs = _TENSOR_REF.findall(text)
    return sorted(set(normalize_tensor_name(r) for r in refs))


# ── Pattern Matching ─────────────────────────────────────────────
#
# Each pattern is a tuple of:
#   (compiled regex, relation type, confidence, description)
#
# Patterns are ordered from most explicit to least. The first match
# wins per sentence, but all sentences are scanned.
#
# The regex should capture enough context for the evidence string.

_PATTERNS: list[tuple[re.Pattern[str], str, str, str]] = [
    # Explicit composition declarations
    (
        re.compile(
            r"(?:this\s+tensor\s+)?(?:does\s+not|doesn't|does\s+NOT)\s+compose\s+with\b",
            re.IGNORECASE,
        ),
        "does_not_compose_with",
        "high",
        "explicit non-composition declaration",
    ),
    (
        re.compile(
            r"(?:this\s+tensor\s+)?composes?\s+with\b",
            re.IGNORECASE,
        ),
        "composes_with",
        "high",
        "explicit composition declaration",
    ),
    # Predecessor/successor declarations
    (
        re.compile(
            r"predecessor:\s*`?[^`\n]*`?",
            re.IGNORECASE,
        ),
        "composes_with",
        "high",
        "predecessor declaration",
    ),
    (
        re.compile(
            r"successor\s+to\b",
            re.IGNORECASE,
        ),
        "composes_with",
        "high",
        "successor declaration",
    ),
    # Correction declarations
    (
        re.compile(
            r"(?:does\s+not|doesn't)\s+modify\b",
            re.IGNORECASE,
        ),
        "composes_with",
        "high",
        "non-modification composition (composes without modifying)",
    ),
    (
        re.compile(
            r"\bcorrects?\b.*\bclaim\b",
            re.IGNORECASE,
        ),
        "corrects",
        "medium",
        "correction of a claim",
    ),
    # Bridge declarations
    (
        re.compile(
            r"\bbridge\s+(?:between|tensor|composition)\b",
            re.IGNORECASE,
        ),
        "bridges",
        "high",
        "bridge declaration",
    ),
    (
        re.compile(
            r"\bconnects?\b.*(?:and|to|with)\b",
            re.IGNORECASE,
        ),
        "bridges",
        "low",
        "connection language (may not be composition)",
    ),
    # Branch declarations
    (
        re.compile(
            r"\bbranch(?:es|ed|ing)?\s+from\b",
            re.IGNORECASE,
        ),
        "branches_from",
        "high",
        "branch declaration",
    ),
    # Reading declarations — explicit "only read" is high confidence
    (
        re.compile(
            r"\bonly\s+read\b",
            re.IGNORECASE,
        ),
        "read",
        "high",
        "explicit selective reading declaration",
    ),
    # "didn't read" / "not read" / "haven't read" = did not read
    (
        re.compile(
            r"(?:didn't|did\s+not|haven't|hasn't|not)\s+read\b",
            re.IGNORECASE,
        ),
        "does_not_compose_with",
        "medium",
        "explicit non-reading declaration",
    ),
    # "read T0-T7" or "read T₀-T₈" range patterns (before single-ref)
    (
        re.compile(
            r"\bread\s+(?:T[_₀₁₂₃₄₅₆₇₈₉\d]+)\s*[-–—]\s*(?:T[_₀₁₂₃₄₅₆₇₈₉\d]+)",
            re.IGNORECASE,
        ),
        "read",
        "medium",
        "reading range declaration",
    ),
    # "I read T0" is medium confidence
    (
        re.compile(
            r"\bread\s+(?:T[_₀₁₂₃₄₅₆₇₈₉\d]+)",
            re.IGNORECASE,
        ),
        "read",
        "medium",
        "reading declaration",
    ),
    # "traversed T₀–T₃ backward"
    (
        re.compile(
            r"\btraversed?\b.*T[_₀₁₂₃₄₅₆₇₈₉\d]+",
            re.IGNORECASE,
        ),
        "read",
        "medium",
        "traversal declaration",
    ),
    # Equation-style declarations: T₂ = f(T₀ + T₁ + x₂)
    (
        re.compile(
            r"T[_₀₁₂₃₄₅₆₇₈₉\d]+\s*=\s*f\(",
            re.IGNORECASE,
        ),
        "composes_with",
        "high",
        "composition equation",
    ),
]


def _sentence_boundaries(text: str) -> list[str]:
    """Split text into sentence-like chunks for evidence extraction.

    Not a perfect sentence splitter — good enough for extracting
    context around pattern matches. Splits on period-space, newlines,
    and bullet points.
    """
    # Split on newlines first (markdown is line-oriented)
    lines = text.splitlines()
    sentences: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            sentences.append(stripped)
    return sentences


def _expand_tensor_range(start: str, end: str) -> list[str]:
    """Expand a tensor range like T0-T7 into [T0, T1, ..., T7]."""
    start_n = normalize_tensor_name(start)
    end_n = normalize_tensor_name(end)

    try:
        s = int(start_n[1:])
        e = int(end_n[1:])
    except (ValueError, IndexError):
        return [start_n, end_n]

    if e < s:
        s, e = e, s

    return [f"T{i}" for i in range(s, e + 1)]


_RANGE_PATTERN = re.compile(
    r"(T(?:[₀₁₂₃₄₅₆₇₈₉]+|_\{?\d+\}?|\d+))\s*[-–—]\s*(T(?:[₀₁₂₃₄₅₆₇₈₉]+|_\{?\d+\}?|\d+))"
)


def _extract_targets_from_sentence(
    sentence: str, source_name: str
) -> list[str]:
    """Extract tensor targets from a sentence, handling ranges.

    Returns normalized tensor names, excluding the source tensor.
    """
    targets: list[str] = []

    # First handle ranges
    for match in _RANGE_PATTERN.finditer(sentence):
        expanded = _expand_tensor_range(match.group(1), match.group(2))
        targets.extend(expanded)

    # Then handle individual refs not already covered by ranges
    individual = _extract_tensor_refs(sentence)
    for ref in individual:
        if ref not in targets:
            targets.append(ref)

    # Remove self-references
    targets = [t for t in targets if t != source_name]

    return targets


# ── Core Extraction ──────────────────────────────────────────────


def extract_tensor_name_from_path(path: Path) -> str:
    """Extract tensor name from filename.

    Examples:
        T15_20260212_the_enemy.md -> T15
        conversation_tensor_20260207.md -> T0
        conversation_tensor_20260208_t3.md -> T3
        conversation_tensor_20260207_session2.md -> T1
        conversation_tensor_20260207_session2_t6.md -> T6
        conversation_tensor_20260208_chatgpt_t4.md -> T4
        conversation_tensor_20260208_chatgpt_t5.md -> T5
        conversation_tensor_20260208_session2_t7.md -> T7
    """
    name = path.stem

    # Direct tensor naming: T15_20260212_the_enemy
    if re.match(r"^T\d+", name):
        match = re.match(r"^(T\d+)", name)
        if match:
            return match.group(1)

    # Legacy naming with explicit tensor number: ..._t3, ..._t6, etc.
    tn_match = re.search(r"_t(\d+)$", name, re.IGNORECASE)
    if tn_match:
        return f"T{tn_match.group(1)}"

    # Legacy session-based naming without explicit tensor number
    # conversation_tensor_20260207.md is T0
    # conversation_tensor_20260207_session2.md is T1
    # conversation_tensor_20260207_session3.md is T2
    if name == "conversation_tensor_20260207":
        return "T0"
    session_match = re.search(r"_session(\d+)$", name)
    if session_match:
        session_num = int(session_match.group(1))
        # session2 -> T1, session3 -> T2
        return f"T{session_num - 1}"

    # Fallback: use the filename
    return name


def extract_composition_declarations(
    text: str, tensor_name: str
) -> list[CompositionDeclaration]:
    """Parse a tensor's markdown text for composition-related language.

    Returns structured declarations with source, targets, relation type,
    evidence (quoted text), and confidence level.

    Conservative: only extracts where the text clearly states composition
    intent. Ambiguous references get low confidence or are skipped.
    """
    declarations: list[CompositionDeclaration] = []
    sentences = _sentence_boundaries(text)

    # Track what we've already declared to avoid duplicates
    seen: set[tuple[str, str, tuple[str, ...]]] = set()

    # Lookahead window: how many subsequent lines to check when
    # a pattern matches but the current line has no tensor refs
    _LOOKAHEAD = 3

    for i, sentence in enumerate(sentences):
        for pattern, relation, confidence, desc in _PATTERNS:
            match = pattern.search(sentence)
            if not match:
                continue

            # For "only read" patterns, extract targets only from AFTER
            # the match — "T1-T7 content (only read T0 and T14)" should
            # yield T0, T14, not T1-T7.
            if desc == "explicit selective reading declaration":
                after_match = sentence[match.start():]
                targets = _extract_targets_from_sentence(
                    after_match, tensor_name
                )
            # For composition equations like "T₂ = f(T₀ + T₁ + x₂)",
            # only emit if the LHS tensor is the current tensor being
            # scanned. Otherwise, it's describing another tensor's
            # composition, not ours.
            elif desc == "composition equation":
                lhs_text = sentence[match.start():match.end()]
                lhs_refs = _extract_tensor_refs(lhs_text)
                if not lhs_refs or lhs_refs[0] != tensor_name:
                    continue
                # Targets are from inside f() — everything after "f("
                after_f = sentence[match.end():]
                targets = _extract_targets_from_sentence(
                    after_f, tensor_name
                )
            else:
                targets = _extract_targets_from_sentence(
                    sentence, tensor_name
                )

            # If no targets found, look ahead a few lines for refs.
            # Handles cases like "T₆ is a bridge tensor. It connects:"
            # followed by "- T₁ → T₄/T₅" on the next line.
            evidence_extra = ""
            if not targets:
                for j in range(1, _LOOKAHEAD + 1):
                    if i + j >= len(sentences):
                        break
                    next_line = sentences[i + j]
                    lookahead_targets = _extract_targets_from_sentence(
                        next_line, tensor_name
                    )
                    if lookahead_targets:
                        targets = lookahead_targets
                        evidence_extra = " " + next_line
                        break

            if not targets:
                continue

            # Dedup key: relation + sorted targets
            key = (tensor_name, relation, tuple(sorted(targets)))
            if key in seen:
                continue
            seen.add(key)

            # Truncate evidence to reasonable length
            evidence = sentence + evidence_extra
            if len(evidence) > 300:
                # Center on the match
                start = max(0, match.start() - 100)
                end = min(len(evidence), match.end() + 200)
                evidence = evidence[start:end]
                if start > 0:
                    evidence = "..." + evidence
                if end < len(sentence):
                    evidence = evidence + "..."

            declarations.append(
                CompositionDeclaration(
                    source=tensor_name,
                    targets=targets,
                    relation=relation,
                    evidence=evidence,
                    confidence=confidence,
                )
            )

            # Only one pattern match per sentence to avoid noise
            break

    return declarations


# ── Corpus Scanning ──────────────────────────────────────────────


def discover_tensors(
    cairn_dir: Path | None = None,
    sources: list[str] | None = None,
) -> list[TensorFile]:
    """Find all tensor files in the cairn and other known sources.

    Returns TensorFile objects with raw text loaded.
    """
    if sources is None:
        sources = list(KNOWN_SOURCES.keys())

    # Override cairn dir if provided
    effective_sources = dict(KNOWN_SOURCES)
    if cairn_dir is not None:
        effective_sources["cairn"] = cairn_dir

    tensors: list[TensorFile] = []
    seen_names: set[str] = set()

    for source_name in sources:
        source_path = effective_sources.get(source_name)
        if source_path is None or not source_path.is_dir():
            continue

        for md_path in sorted(source_path.rglob("*.md")):
            # Skip hidden files, MEMORY.md, non-tensor files
            if md_path.name.startswith(".") or md_path.name == "MEMORY.md":
                continue

            # Only process files that look like tensors
            stem = md_path.stem
            is_tensor = (
                re.match(r"^T\d+", stem)  # T15_... style
                or "conversation_tensor" in stem  # Legacy style
            )
            if not is_tensor:
                continue

            tensor_name = extract_tensor_name_from_path(md_path)

            # Skip duplicates (symlinks, copies across sources)
            if tensor_name in seen_names:
                continue
            seen_names.add(tensor_name)

            try:
                raw_text = md_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            tensors.append(
                TensorFile(
                    path=md_path,
                    source_name=source_name,
                    tensor_name=tensor_name,
                    raw_text=raw_text,
                )
            )

    # Sort by tensor number
    def _sort_key(t: TensorFile) -> int:
        m = re.match(r"T(\d+)", t.tensor_name)
        return int(m.group(1)) if m else 999

    tensors.sort(key=_sort_key)
    return tensors


def weave_corpus(
    cairn_dir: Path | None = None,
    sources: list[str] | None = None,
) -> list[CompositionDeclaration]:
    """Discover all tensors and extract composition declarations.

    Returns the complete list of declarations across the corpus.
    """
    if cairn_dir is None:
        cairn_dir = CAIRN_DIR

    tensors = discover_tensors(cairn_dir=cairn_dir, sources=sources)
    all_declarations: list[CompositionDeclaration] = []

    for tensor in tensors:
        declarations = extract_composition_declarations(
            tensor.raw_text, tensor.tensor_name
        )
        all_declarations.extend(declarations)

    return all_declarations


# ── Rendering ────────────────────────────────────────────────────

# Relation display names
_RELATION_LABELS: dict[str, str] = {
    "composes_with": "Composes With",
    "does_not_compose_with": "Does Not Compose With",
    "corrects": "Corrects",
    "bridges": "Bridges",
    "branches_from": "Branches From",
    "read": "Read",
}


def render_graph(declarations: list[CompositionDeclaration]) -> str:
    """Render the composition graph as human-readable text.

    Groups by relation type, shows edges with evidence.
    """
    if not declarations:
        return "No composition declarations found."

    # Collect all tensor names (nodes)
    nodes: set[str] = set()
    for d in declarations:
        nodes.add(d.source)
        nodes.update(d.targets)

    # Group by relation type
    by_relation: dict[str, list[CompositionDeclaration]] = {}
    for d in declarations:
        by_relation.setdefault(d.relation, []).append(d)

    parts: list[str] = []
    parts.append("Composition Graph")
    parts.append("=" * 60)
    parts.append("")

    # Node summary
    sorted_nodes = sorted(nodes, key=lambda n: (int(re.sub(r"\D", "", n) or "999"), n))
    parts.append(f"Nodes ({len(sorted_nodes)} tensors): {', '.join(sorted_nodes)}")
    parts.append(f"Edges: {len(declarations)} declarations")
    parts.append("")

    # Edges grouped by relation
    for relation in [
        "composes_with",
        "does_not_compose_with",
        "corrects",
        "bridges",
        "branches_from",
        "read",
    ]:
        group = by_relation.get(relation, [])
        if not group:
            continue

        label = _RELATION_LABELS.get(relation, relation)
        parts.append(f"-- {label} ({len(group)} edges) --")
        parts.append("")

        for d in group:
            targets_str = ", ".join(d.targets)
            parts.append(f"  {d.source} -> {targets_str}  [{d.confidence}]")

            # Truncate evidence for display
            ev = d.evidence
            if len(ev) > 120:
                ev = ev[:117] + "..."
            parts.append(f"    \"{ev}\"")
            parts.append("")

    # Summary statistics
    parts.append("-" * 60)
    confidence_counts = {"high": 0, "medium": 0, "low": 0}
    for d in declarations:
        confidence_counts[d.confidence] = confidence_counts.get(d.confidence, 0) + 1
    parts.append(
        f"Confidence: {confidence_counts['high']} high, "
        f"{confidence_counts['medium']} medium, "
        f"{confidence_counts['low']} low"
    )

    return "\n".join(parts)


def render_json(declarations: list[CompositionDeclaration]) -> str:
    """Render declarations as JSON for programmatic consumption."""
    return json.dumps(
        [asdict(d) for d in declarations],
        indent=2,
        ensure_ascii=False,
    )


def render_tensor_declarations(
    tensor_name: str, declarations: list[CompositionDeclaration]
) -> str:
    """Render declarations for a single tensor."""
    filtered = [d for d in declarations if d.source == tensor_name]
    if not filtered:
        return f"No composition declarations found for {tensor_name}."

    parts: list[str] = []
    parts.append(f"Composition declarations for {tensor_name}")
    parts.append("=" * 60)
    parts.append("")

    for d in filtered:
        targets_str = ", ".join(d.targets)
        label = _RELATION_LABELS.get(d.relation, d.relation)
        parts.append(f"  {label}: {targets_str}  [{d.confidence}]")
        parts.append(f"    \"{d.evidence}\"")
        parts.append("")

    return "\n".join(parts)
