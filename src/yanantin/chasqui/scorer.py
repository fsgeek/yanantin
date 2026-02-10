"""Scout Scorer — sniff the cairn and see what's kraken poo and what's bitter apple.

Reads scout tensors from the cairn, extracts structural signals, and
scores them on axes that don't require a judge:

- Specificity: file/line references (verifiable attention)
- Fabrication: claimed paths that don't exist (confident lies)
- Efficiency: insight-per-token ratio
- Generativity: open questions that invite response
- Structure: did the scout follow the tensor format?

The semantic axis (novelty) requires a judge and is deliberately excluded.
Convergent observations across scouts approximate it structurally.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── Provenance parsing ──────────────────────────────────────────────

@dataclass(frozen=True)
class ScoutProvenance:
    """Parsed provenance from a scout tensor's HTML comment header."""

    run_number: int
    model_id: str
    model_name: str
    prompt_cost: float
    completion_cost: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    total_cost: float
    timestamp: str
    raw_usage: str  # Unparsed usage dict as string


def parse_provenance(text: str) -> ScoutProvenance | None:
    """Extract provenance from the <!-- Chasqui Scout Tensor ... --> header."""
    header_match = re.search(
        r"<!--\s*Chasqui Scout Tensor\s*(.*?)-->",
        text,
        re.DOTALL,
    )
    if not header_match:
        return None

    header = header_match.group(1)

    def _extract(pattern: str, default: str = "") -> str:
        m = re.search(pattern, header)
        return m.group(1).strip() if m else default

    run_number = int(_extract(r"Run:\s*(\d+)", "0"))
    model_line = _extract(r"Model:\s*(.+)")
    # "deepseek/deepseek-chat-v3.1 (DeepSeek: DeepSeek V3.1)"
    model_parts = re.match(r"(\S+)\s*\((.+)\)", model_line)
    model_id = model_parts.group(1) if model_parts else model_line
    model_name = model_parts.group(2) if model_parts else model_line

    cost_line = _extract(r"Cost:\s*(.+)")
    prompt_cost_match = re.search(r"prompt=\$?([\d.e+-]+)", cost_line)
    completion_cost_match = re.search(r"completion=\$?([\d.e+-]+)", cost_line)
    prompt_cost = float(prompt_cost_match.group(1)) if prompt_cost_match else 0.0
    completion_cost = float(completion_cost_match.group(1)) if completion_cost_match else 0.0

    usage_str = _extract(r"Usage:\s*(\{.+\})")
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    total_cost = 0.0
    if usage_str:
        pt = re.search(r"'prompt_tokens':\s*(\d+)", usage_str)
        ct = re.search(r"'completion_tokens':\s*(\d+)", usage_str)
        tt = re.search(r"'total_tokens':\s*(\d+)", usage_str)
        tc = re.search(r"'cost':\s*([\d.e+-]+)", usage_str)
        if pt:
            prompt_tokens = int(pt.group(1))
        if ct:
            completion_tokens = int(ct.group(1))
        if tt:
            total_tokens = int(tt.group(1))
        if tc:
            total_cost = float(tc.group(1))

    timestamp = _extract(r"Timestamp:\s*(.+)")

    return ScoutProvenance(
        run_number=run_number,
        model_id=model_id,
        model_name=model_name,
        prompt_cost=prompt_cost,
        completion_cost=completion_cost,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        total_cost=total_cost,
        timestamp=timestamp,
        raw_usage=usage_str,
    )


# ── Content analysis ────────────────────────────────────────────────

# Patterns that look like file paths in scout output
_PATH_PATTERN = re.compile(
    r"`([a-zA-Z_][\w/.-]*(?:\.py|\.md|\.toml|\.yaml|\.yml)(?::\d+)?)`"
)

# Patterns for strands — scouts use varied formatting.
# Each pattern targets a distinct formatting convention. We deduplicate
# by line number to avoid double-counting when multiple patterns match
# the same strand.
_STRAND_PATTERNS = [
    re.compile(r"^#{2,4}\s+\**\d+\.?\s", re.MULTILINE),              # ### 1. or ### **1.
    re.compile(r"^#{2,4}\s+\**[Ss]trand\s+\d+", re.MULTILINE),       # ### Strand 1 or ### **Strand 1
    re.compile(r"^\*\*Strand\s+\d+", re.MULTILINE),                    # **Strand 1
    re.compile(r"^\d+\.\s+\*\*[A-Z]", re.MULTILINE),                  # 1. **Title
]

# Section headings — allow bold markers around the heading text
_SECTION_HEADING = r"(?:^|\n)#{2,4}\s+\**"

# Section extraction — find a section and capture everything until the next heading
def _extract_section(body: str, heading_keyword: str) -> str:
    """Extract text from a section heading to the next same-or-higher heading."""
    pattern = re.compile(
        r"(?:^|\n)(#{2,4})\s+\**" + heading_keyword + r".*?\n",
        re.IGNORECASE,
    )
    match = pattern.search(body)
    if not match:
        return ""
    level = len(match.group(1))
    start = match.end()
    end_pat = re.compile(r"\n#{2," + str(level) + r"}\s+")
    end_match = end_pat.search(body, start)
    return body[start:end_match.start() if end_match else len(body)]


@dataclass
class FileReference:
    """A file path referenced in a scout report."""

    path: str
    line: int | None = None
    exists: bool | None = None  # None = not yet checked


@dataclass
class ContentAnalysis:
    """Structural analysis of a scout tensor's content."""

    # Raw metrics
    body_text: str
    word_count: int
    strand_count: int
    open_question_count: int
    declared_loss_count: int

    # File references
    file_references: list[FileReference] = field(default_factory=list)

    # Computed after verification
    verified_references: int = 0
    fabricated_references: int = 0
    unchecked_references: int = 0


def _strip_provenance_header(text: str) -> str:
    """Remove the HTML comment provenance header, return body."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()


def _extract_strands_section(body: str) -> str:
    """Extract the Strands section from the body.

    Looks for a heading containing 'Strand' and captures everything
    until the next same-level-or-higher heading that isn't a strand
    sub-heading (e.g., 'Declared Losses', 'Open Questions', 'Closing').
    """
    # Find the Strands section heading
    strands_start = re.search(
        r"(?:^|\n)(#{2,4})\s+\**Strands?\**",
        body,
        re.IGNORECASE,
    )
    if not strands_start:
        # No explicit strands section — fall back to full body
        return body

    level = len(strands_start.group(1))  # heading level (## = 2, ### = 3)
    start = strands_start.end()

    # Find the next heading at the same level or higher that isn't a strand
    end_pattern = re.compile(
        r"\n#{2," + str(level) + r"}\s+\**(?!.*[Ss]trand)",
        re.MULTILINE,
    )
    end_match = end_pattern.search(body, start)
    end = end_match.start() if end_match else len(body)
    return body[start:end]


def _count_strands(body: str) -> int:
    """Count strands within the Strands section only.

    Deduplicates by match position to avoid double-counting when
    multiple patterns match the same strand.
    """
    section = _extract_strands_section(body)
    positions: set[int] = set()
    for pattern in _STRAND_PATTERNS:
        for match in pattern.finditer(section):
            positions.add(match.start())
    return len(positions)


def _count_open_questions(body: str) -> int:
    """Count top-level list items in the 'Open Questions' section.

    Only counts items starting at the left margin (numbered or bulleted),
    not indented sub-items.
    """
    section = _extract_section(body, "Open\\s+Questions")
    if not section:
        return 0
    # Top-level items: start of line, optional single space, then number or bullet
    items = re.findall(r"^(?:\d+\.|\*|-)\s+", section, re.MULTILINE)
    return len(items)


def _count_declared_losses(body: str) -> int:
    """Count items in the 'Declared Losses' section."""
    section = _extract_section(body, "Declared\\s+Losses")
    if not section:
        return 0
    items = re.findall(r"^(?:\d+\.|\*|-)\s+", section, re.MULTILINE)
    return max(len(items), 1) if section.strip() else 0


def _extract_file_references(body: str) -> list[FileReference]:
    """Extract file path references from backtick-wrapped paths."""
    refs = []
    seen = set()
    for match in _PATH_PATTERN.finditer(body):
        raw = match.group(1)
        # Split path:line
        parts = raw.rsplit(":", 1)
        path = parts[0]
        line = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None

        if path not in seen:
            seen.add(path)
            refs.append(FileReference(path=path, line=line))
    return refs


def analyze_content(text: str) -> ContentAnalysis:
    """Analyze the structural content of a scout tensor."""
    body = _strip_provenance_header(text)
    words = body.split()
    refs = _extract_file_references(body)

    return ContentAnalysis(
        body_text=body,
        word_count=len(words),
        strand_count=_count_strands(body),
        open_question_count=_count_open_questions(body),
        declared_loss_count=_count_declared_losses(body),
        file_references=refs,
    )


# ── Fabrication detection ───────────────────────────────────────────

def verify_references(
    analysis: ContentAnalysis,
    project_root: Path,
) -> ContentAnalysis:
    """Check file references against the actual project tree.

    Mutates the analysis in place and returns it.
    """
    verified = 0
    fabricated = 0
    unchecked = 0

    for ref in analysis.file_references:
        candidate = project_root / ref.path
        if candidate.exists():
            ref.exists = True
            verified += 1
        elif any(project_root.rglob(Path(ref.path).name)):
            # File exists but maybe under a different prefix
            ref.exists = True
            verified += 1
        else:
            ref.exists = False
            fabricated += 1

    analysis.verified_references = verified
    analysis.fabricated_references = fabricated
    analysis.unchecked_references = unchecked
    return analysis


# ── Scout Score ─────────────────────────────────────────────────────

@dataclass
class ScoutScore:
    """Composite score for a scout tensor."""

    # Identity
    scout_path: str
    provenance: ScoutProvenance | None

    # Content analysis
    content: ContentAnalysis

    # Scores (0.0 to 1.0 where applicable)
    specificity: float = 0.0       # file references per 1000 words
    fabrication_rate: float = 0.0  # fraction of refs that don't exist
    efficiency: float = 0.0        # strands per 1000 completion tokens
    generativity: float = 0.0      # open questions count (raw, not normalized)
    structure: float = 0.0         # did it follow the tensor format? (0-1)

    def summary(self) -> dict[str, Any]:
        """Flat dict for display or JSON serialization."""
        prov = self.provenance
        return {
            "path": self.scout_path,
            "model": prov.model_id if prov else "unknown",
            "model_name": prov.model_name if prov else "unknown",
            "completion_tokens": prov.completion_tokens if prov else 0,
            "total_cost": prov.total_cost if prov else 0.0,
            "word_count": self.content.word_count,
            "strands": self.content.strand_count,
            "open_questions": self.content.open_question_count,
            "declared_losses": self.content.declared_loss_count,
            "file_refs": len(self.content.file_references),
            "verified_refs": self.content.verified_references,
            "fabricated_refs": self.content.fabricated_references,
            "specificity": round(self.specificity, 2),
            "fabrication_rate": round(self.fabrication_rate, 2),
            "efficiency": round(self.efficiency, 2),
            "generativity": self.generativity,
            "structure": round(self.structure, 2),
        }


def score_scout(
    text: str,
    scout_path: str,
    project_root: Path,
) -> ScoutScore:
    """Score a scout tensor on automated axes."""
    provenance = parse_provenance(text)
    content = analyze_content(text)
    verify_references(content, project_root)

    # Specificity: file references per 1000 words
    specificity = (
        (len(content.file_references) / content.word_count * 1000)
        if content.word_count > 0
        else 0.0
    )

    # Fabrication rate: fraction of references that don't exist
    total_refs = len(content.file_references)
    fabrication_rate = (
        content.fabricated_references / total_refs
        if total_refs > 0
        else 0.0
    )

    # Efficiency: strands per 1000 completion tokens
    comp_tokens = provenance.completion_tokens if provenance else 0
    efficiency = (
        (content.strand_count / comp_tokens * 1000)
        if comp_tokens > 0
        else 0.0
    )

    # Generativity: raw open question count
    generativity = float(content.open_question_count)

    # Structure: did it include the expected sections?
    body_lower = content.body_text.lower()
    sections_present = sum([
        "preamble" in body_lower,
        "strand" in body_lower,
        "declared loss" in body_lower or "declared losses" in body_lower,
        "open question" in body_lower,
        "closing" in body_lower,
    ])
    structure = sections_present / 5.0

    return ScoutScore(
        scout_path=scout_path,
        provenance=provenance,
        content=content,
        specificity=specificity,
        fabrication_rate=fabrication_rate,
        efficiency=efficiency,
        generativity=generativity,
        structure=structure,
    )


# ── Cairn scorer ────────────────────────────────────────────────────

def score_cairn(
    cairn_dir: Path,
    project_root: Path,
) -> list[ScoutScore]:
    """Score all scout tensors in the cairn.

    Returns a list of ScoutScores sorted by run number.
    """
    scores = []
    for scout_file in sorted(cairn_dir.glob("scout_*.md")):
        text = scout_file.read_text(encoding="utf-8")
        score = score_scout(text, str(scout_file), project_root)
        scores.append(score)
    return scores


def render_scorecard(scores: list[ScoutScore]) -> str:
    """Render a human-readable scorecard for the cairn."""
    if not scores:
        return "No scout tensors found in cairn."

    lines = ["# Cairn Scorecard", ""]

    # Header
    lines.append(
        f"{'Model':<35} {'Tokens':>6} {'Strands':>7} "
        f"{'Refs':>4} {'Fab':>3} {'Qs':>3} "
        f"{'Spec':>5} {'Fab%':>5} {'Eff':>5} {'Str':>4}"
    )
    lines.append("-" * 95)

    for s in scores:
        prov = s.provenance
        model = prov.model_id if prov else "unknown"
        if len(model) > 34:
            model = model[:31] + "..."
        tokens = prov.completion_tokens if prov else 0

        lines.append(
            f"{model:<35} {tokens:>6} {s.content.strand_count:>7} "
            f"{len(s.content.file_references):>4} {s.content.fabricated_references:>3} "
            f"{s.content.open_question_count:>3} "
            f"{s.specificity:>5.1f} {s.fabrication_rate:>5.0%} {s.efficiency:>5.1f} "
            f"{s.structure:>4.0%}"
        )

    lines.append("")

    # Fabrication details
    fabricators = [s for s in scores if s.content.fabricated_references > 0]
    if fabricators:
        lines.append("## Fabricated References")
        lines.append("")
        for s in fabricators:
            prov = s.provenance
            model = prov.model_id if prov else "unknown"
            lines.append(f"**{model}**:")
            for ref in s.content.file_references:
                if ref.exists is False:
                    lines.append(f"  - `{ref.path}` — not found")
            lines.append("")

    # Convergence: file paths referenced by 2+ scouts
    all_paths: dict[str, list[str]] = {}
    for s in scores:
        model = s.provenance.model_id if s.provenance else "unknown"
        for ref in s.content.file_references:
            if ref.exists:
                all_paths.setdefault(ref.path, []).append(model)
    convergent = {p: models for p, models in all_paths.items() if len(models) > 1}
    if convergent:
        lines.append("## Convergent Attention")
        lines.append("")
        lines.append("Files referenced by multiple scouts:")
        for path, models in sorted(convergent.items(), key=lambda x: -len(x[1])):
            lines.append(f"  - `{path}` ({len(models)} scouts: {', '.join(models)})")
        lines.append("")

    return "\n".join(lines)
