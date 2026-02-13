"""Gleaner — extract structured claims from scout and scour reports.

The Gleaner reads markdown reports from the cairn and extracts claims
that can be verified against the codebase. It sits in the processing
pipeline between Scout and Verify:

    Scout → **Gleaner** → Verify → Respond

Unlike the existing `extract_cairn_claims` in scorer.py (which only
finds sentences containing file paths), the Gleaner classifies claims
by type, scores confidence, and deduplicates across reports.

This module uses deterministic pattern matching — no LLM calls.
LLM-guided extraction is a future enhancement.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# ── Data structures ──────────────────────────────────────────────────

@dataclass
class ExtractedClaim:
    """A claim extracted from a scout/scour report."""

    claim_text: str           # The actual assertion
    source_file: str          # Which report it came from
    source_model: str         # Which model wrote the report
    file_references: list[str] = field(default_factory=list)  # Files mentioned
    claim_type: str = "factual"  # "factual" | "architectural" | "epistemic" | "missing"
    confidence: float = 0.5   # How clearly stated (0.0-1.0)
    context: str = ""         # Surrounding text for the claim


# ── Patterns ─────────────────────────────────────────────────────────

# File paths in backtick-wrapped references
_PATH_PATTERN = re.compile(
    r"`([a-zA-Z_][\w/.-]*(?:\.py|\.md|\.toml|\.yaml|\.yml|\.json|\.txt|\.cfg|\.ini)(?::\d+)?)`"
)

# Broader file path pattern (not backtick-wrapped, for less confident matches)
_BARE_PATH_PATTERN = re.compile(
    r"(?:src|tests|docs)/[\w/.-]+\.(?:py|md|toml|yaml|yml|json)"
)

# Provenance header patterns
_SCOUT_HEADER = re.compile(
    r"<!--\s*Chasqui Scout Tensor\s*(.*?)-->", re.DOTALL
)
_SCOUR_HEADER = re.compile(
    r"<!--\s*Chasqui Scour Tensor\s*(.*?)-->", re.DOTALL
)

# Sentence boundary: period/question/exclamation followed by whitespace
# Handles end-of-line and mid-paragraph boundaries
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.?!])\s+")

# Section heading pattern
_SECTION_HEADING = re.compile(
    r"(?:^|\n)(#{2,4})\s+\**(.+?)\**\s*$", re.MULTILINE
)

# ── Confidence signals ───────────────────────────────────────────────

# Definitive language → higher confidence
_DEFINITIVE_PATTERNS = [
    re.compile(r"\b(?:is|does|has|contains|defines|implements|returns|uses|creates|enforces)\b", re.IGNORECASE),
    re.compile(r"\b(?:always|every|all|never|none|must|exactly|precisely)\b", re.IGNORECASE),
]

# Hedged language → lower confidence
_HEDGED_PATTERNS = [
    re.compile(r"\b(?:seems?|appears?|might|could|may|possibly|probably|likely|perhaps|suggests?)\b", re.IGNORECASE),
    re.compile(r"\b(?:I think|I believe|I suspect|I guess|not sure|unclear|ambiguous)\b", re.IGNORECASE),
]

# Quantitative assertions → higher confidence (verifiable)
_QUANTITATIVE_PATTERN = re.compile(
    r"\b\d+\s+(?:tests?|files?|modules?|functions?|methods?|classes?|lines?|endpoints?|backends?|strands?|questions?)\b",
    re.IGNORECASE,
)

# ── Claim type signals ───────────────────────────────────────────────

# Architectural language
_ARCHITECTURAL_PATTERNS = [
    re.compile(r"\b(?:depends?\s+on|imports?|connects?\s+to|interfaces?\s+with|delegates?\s+to)\b", re.IGNORECASE),
    re.compile(r"\b(?:architecture|modular|separation\s+of\s+concerns|layer|pipeline|workflow)\b", re.IGNORECASE),
    re.compile(r"\b(?:enforces?|invariant|constraint|boundary|interface)\b", re.IGNORECASE),
]

# Epistemic language
_EPISTEMIC_PATTERNS = [
    re.compile(r"\b(?:I\s+don'?t\s+know|uncertain|unclear|ambiguous|I\s+disagree)\b", re.IGNORECASE),
    re.compile(r"\b(?:the\s+system\s+doesn'?t\s+know|not\s+clear\s+(?:whether|if|how))\b", re.IGNORECASE),
    re.compile(r"\b(?:open\s+question|remains?\s+unclear|unresolved|undetermined)\b", re.IGNORECASE),
    re.compile(r"\b(?:I\s+wonder|worth\s+asking|needs?\s+clarification)\b", re.IGNORECASE),
]

# Missing/absence language
_MISSING_PATTERNS = [
    re.compile(r"\b(?:no\s+\w+\s+(?:exists?|found|present|implemented|defined))\b", re.IGNORECASE),
    re.compile(r"\b(?:doesn'?t\s+exist|is\s+(?:not|n'?t)\s+(?:present|implemented|defined|available))\b", re.IGNORECASE),
    re.compile(r"\b(?:missing|absent|lacking|omitted|not\s+yet)\b", re.IGNORECASE),
    re.compile(r"\b(?:there\s+is\s+no|there\s+are\s+no|without\s+(?:a|any))\b", re.IGNORECASE),
    re.compile(r"\b(?:needed\s+but|required\s+but|should\s+(?:have|include|exist))\b", re.IGNORECASE),
    re.compile(r"\b(?:gap|hole|deficit)\b", re.IGNORECASE),
]


# ── Provenance extraction ────────────────────────────────────────────

def _extract_model_id(text: str) -> str:
    """Extract the model ID from a scout or scour provenance header.

    Handles both scout and scour header formats.
    """
    for pattern in (_SCOUT_HEADER, _SCOUR_HEADER):
        match = pattern.search(text)
        if match:
            header = match.group(1)
            model_match = re.search(r"Model:\s*(\S+)", header)
            if model_match:
                return model_match.group(1)
    return "unknown"


def _strip_headers(text: str) -> str:
    """Remove HTML comment headers from the text, return the body."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()


# ── Section extraction ───────────────────────────────────────────────

def _extract_section(body: str, heading_keyword: str) -> str:
    """Extract text from a section heading to the next same-or-higher heading.

    Returns the section body text, or empty string if the section is not found.
    """
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


def _extract_strands_section(body: str) -> str:
    """Extract the Strands section from the body.

    Looks for headings containing 'Strand' and captures everything
    until the next same-level-or-higher heading that isn't a strand.
    Falls back to the full body if no Strands section is found.
    """
    strands_start = re.search(
        r"(?:^|\n)(#{2,4})\s+\**Strands?\**",
        body,
        re.IGNORECASE,
    )
    if not strands_start:
        return body

    level = len(strands_start.group(1))
    start = strands_start.end()

    # Find the next heading at the same level or higher that isn't a strand
    end_pattern = re.compile(
        r"\n#{2," + str(level) + r"}\s+\**(?!.*[Ss]trand)",
        re.MULTILINE,
    )
    end_match = end_pattern.search(body, start)
    end = end_match.start() if end_match else len(body)
    return body[start:end]


# ── Sentence splitting ───────────────────────────────────────────────

def _split_sentences(text: str) -> list[str]:
    """Split text into sentences, handling markdown artifacts.

    Collapses internal newlines within each sentence so that
    multi-line markdown renders as a single sentence.
    Filters out trivially short fragments and headings.
    """
    # Normalize whitespace within lines but preserve paragraph breaks
    # First, collapse single newlines (markdown soft breaks) into spaces
    normalized = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    # Then split on sentence boundaries
    raw_sentences = _SENTENCE_BOUNDARY.split(normalized)

    sentences = []
    for s in raw_sentences:
        cleaned = s.strip()
        # Remove leading markdown noise (bullets, numbers, bold markers)
        cleaned = re.sub(r"^(?:[-*]\s+|\d+\.\s+|\*\*|\#{1,4}\s+)", "", cleaned)
        # Skip trivially short fragments
        if len(cleaned) < 25:
            continue
        # Skip pure headings or formatting-only lines
        if re.match(r"^#{1,6}\s", cleaned) or re.match(r"^[-=]{3,}$", cleaned):
            continue
        sentences.append(cleaned)
    return sentences


# ── File reference extraction ────────────────────────────────────────

def _extract_file_references(text: str) -> list[str]:
    """Extract file path references from text.

    Finds backtick-wrapped paths first (high confidence), then bare
    paths (lower confidence). Deduplicates.
    """
    refs: list[str] = []
    seen: set[str] = set()

    # Backtick-wrapped paths (higher reliability)
    for match in _PATH_PATTERN.finditer(text):
        raw = match.group(1)
        # Strip line number suffix for dedup purposes
        path = raw.rsplit(":", 1)[0]
        if path not in seen:
            seen.add(path)
            refs.append(raw)  # Keep the full reference including line number

    # Bare paths (lower reliability, only add if not already found)
    for match in _BARE_PATH_PATTERN.finditer(text):
        path = match.group(0)
        if path not in seen:
            seen.add(path)
            refs.append(path)

    return refs


# ── Claim classification ─────────────────────────────────────────────

def _classify_claim(sentence: str) -> str:
    """Classify a claim into one of the four types.

    Priority: missing > epistemic > architectural > factual
    Missing and epistemic claims are rarer and more interesting,
    so they take priority when multiple patterns match.
    """
    # Check for missing/absence claims first
    for pattern in _MISSING_PATTERNS:
        if pattern.search(sentence):
            return "missing"

    # Check for epistemic claims
    for pattern in _EPISTEMIC_PATTERNS:
        if pattern.search(sentence):
            return "epistemic"

    # Check for architectural claims
    for pattern in _ARCHITECTURAL_PATTERNS:
        if pattern.search(sentence):
            return "architectural"

    # Default to factual
    return "factual"


def _score_confidence(sentence: str, file_refs: list[str]) -> float:
    """Score how confidently a claim is stated.

    Higher scores for definitive language, file references,
    and quantitative assertions. Lower scores for hedged language.
    """
    score = 0.5  # baseline

    # File references boost confidence (verifiable)
    if file_refs:
        score += 0.15

    # Quantitative assertions boost confidence (checkable)
    if _QUANTITATIVE_PATTERN.search(sentence):
        score += 0.1

    # Definitive language boosts confidence
    definitive_count = sum(
        1 for p in _DEFINITIVE_PATTERNS if p.search(sentence)
    )
    score += min(definitive_count * 0.08, 0.15)

    # Hedged language reduces confidence
    hedged_count = sum(
        1 for p in _HEDGED_PATTERNS if p.search(sentence)
    )
    score -= min(hedged_count * 0.12, 0.25)

    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, round(score, 3)))


# ── Context extraction ───────────────────────────────────────────────

def _get_context(full_text: str, sentence: str, context_chars: int = 200) -> str:
    """Get surrounding text for a claim to provide context.

    Returns up to context_chars characters before and after the
    sentence in the source text.
    """
    # Find the sentence in the full text (approximate match since we
    # may have cleaned it)
    # Use the first 60 chars as a search key to find approximate location
    search_key = sentence[:60] if len(sentence) > 60 else sentence
    # Escape regex special chars for the search
    escaped = re.escape(search_key)
    match = re.search(escaped, full_text)
    if not match:
        # Try a looser match with first few words
        words = sentence.split()[:5]
        loose_key = r"\s+".join(re.escape(w) for w in words)
        match = re.search(loose_key, full_text)
        if not match:
            return ""

    start = max(0, match.start() - context_chars)
    end = min(len(full_text), match.end() + context_chars)
    context = full_text[start:end].strip()

    # Add ellipsis markers if we truncated
    if start > 0:
        context = "..." + context
    if end < len(full_text):
        context = context + "..."

    return context


# ── Claim filtering ──────────────────────────────────────────────────

def _is_substantive(sentence: str) -> bool:
    """Filter out non-substantive sentences.

    Rejects pure metadata, formatting artifacts, transitions,
    and other noise that doesn't contain verifiable claims.
    """
    # Too short to be a real claim
    if len(sentence) < 30:
        return False

    # Pure transitions or filler
    filler_patterns = [
        re.compile(r"^(?:Overall|In\s+summary|In\s+conclusion|To\s+summarize)\b", re.IGNORECASE),
        re.compile(r"^(?:Here\s+(?:is|are)|The\s+following|Below\s+(?:is|are))\b", re.IGNORECASE),
        re.compile(r"^(?:What\s+I\s+saw|What\s+it\s+made\s+me\s+think)\s*$", re.IGNORECASE),
        re.compile(r"^(?:Evidence|Observed|Inferences?)\s*:\s*$", re.IGNORECASE),
    ]
    for p in filler_patterns:
        if p.match(sentence):
            return False

    # Pure code blocks (no natural language claim)
    if sentence.strip().startswith("```"):
        return False

    # Lines that are mostly formatting
    stripped = re.sub(r"[*_`#\-=>\[\]\(\)]", "", sentence).strip()
    if len(stripped) < 20:
        return False

    return True


def _has_declarative_structure(sentence: str) -> bool:
    """Check if a sentence has declarative structure worth extracting.

    Looks for sentences that make assertions rather than being
    purely narrative or transitional.
    """
    # Contains a file path reference — always interesting
    if _PATH_PATTERN.search(sentence) or _BARE_PATH_PATTERN.search(sentence):
        return True

    # Quantitative assertion
    if _QUANTITATIVE_PATTERN.search(sentence):
        return True

    # Declarative statement starting with definite noun phrase + verb
    declarative = re.compile(
        r"^(?:The|This|Each|Every|All|It|That)\s+\w+\s+(?:is|does|has|are|was|were|contains?|defines?|implements?|uses?|creates?|enforces?|returns?)\b",
        re.IGNORECASE,
    )
    if declarative.match(sentence):
        return True

    # Normative claims (should, must, needs)
    normative = re.compile(r"\b(?:should|must|needs?\s+to|required?\s+to)\b", re.IGNORECASE)
    if normative.search(sentence):
        return True

    # Missing/absence claims are always interesting
    for pattern in _MISSING_PATTERNS:
        if pattern.search(sentence):
            return True

    # Epistemic claims are always interesting
    for pattern in _EPISTEMIC_PATTERNS:
        if pattern.search(sentence):
            return True

    return False


# ── Core extraction ──────────────────────────────────────────────────

def extract_claims_from_report(report_path: Path) -> list[ExtractedClaim]:
    """Parse a single scout/scour markdown report and extract claims.

    Focuses on the Strands section where substantive observations live,
    plus Open Questions (epistemic claims) and Declared Losses (epistemic
    claims about what was skipped).

    Args:
        report_path: Path to a scout or scour markdown file.

    Returns:
        List of extracted claims, sorted by confidence (highest first).
    """
    try:
        text = report_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        logger.warning("Cannot read report %s: %s", report_path, e)
        return []

    if not text.strip():
        logger.debug("Empty report: %s", report_path)
        return []

    source_file = str(report_path)
    source_model = _extract_model_id(text)
    body = _strip_headers(text)

    claims: list[ExtractedClaim] = []
    seen_texts: set[str] = set()  # Dedup within a single report

    # ── Extract from Strands section ──
    strands_text = _extract_strands_section(body)
    _extract_from_section(
        strands_text, body, source_file, source_model,
        claims, seen_texts,
    )

    # ── Extract from Open Questions section (epistemic claims) ──
    open_questions = _extract_section(body, r"Open\s+Questions")
    if open_questions:
        _extract_from_section(
            open_questions, body, source_file, source_model,
            claims, seen_texts,
            type_override="epistemic",
        )

    # ── Extract from Declared Losses section (epistemic claims) ──
    declared_losses = _extract_section(body, r"Declared\s+Losses")
    if declared_losses:
        _extract_from_section(
            declared_losses, body, source_file, source_model,
            claims, seen_texts,
            type_override="epistemic",
            confidence_penalty=0.1,  # Loss declarations are less verifiable
        )

    # ── Extract from Evidence section (verification reports) ──
    evidence = _extract_section(body, r"Evidence")
    if evidence:
        _extract_from_section(
            evidence, body, source_file, source_model,
            claims, seen_texts,
        )

    # ── Extract from Reasoning section ──
    reasoning = _extract_section(body, r"Reasoning")
    if reasoning:
        _extract_from_section(
            reasoning, body, source_file, source_model,
            claims, seen_texts,
        )

    # Sort by confidence, highest first
    claims.sort(key=lambda c: c.confidence, reverse=True)

    logger.info(
        "Gleaned %d claims from %s (model=%s)",
        len(claims), report_path.name, source_model,
    )
    return claims


def _extract_from_section(
    section_text: str,
    full_body: str,
    source_file: str,
    source_model: str,
    claims: list[ExtractedClaim],
    seen_texts: set[str],
    type_override: str | None = None,
    confidence_penalty: float = 0.0,
) -> None:
    """Extract claims from a section of text and append to the claims list.

    Args:
        section_text: The section to extract from.
        full_body: The complete report body (for context extraction).
        source_file: Path to the source report file.
        source_model: Model that wrote the report.
        claims: Accumulator list to append claims to.
        seen_texts: Set of already-seen claim texts for dedup.
        type_override: Force all claims to this type (e.g., "epistemic").
        confidence_penalty: Reduce confidence by this amount.
    """
    sentences = _split_sentences(section_text)

    for sentence in sentences:
        # Filter non-substantive sentences
        if not _is_substantive(sentence):
            continue

        # Check for declarative structure
        if not _has_declarative_structure(sentence):
            continue

        # Normalize for dedup
        norm = _normalize_for_dedup(sentence)
        if norm in seen_texts:
            continue
        seen_texts.add(norm)

        # Extract file references
        file_refs = _extract_file_references(sentence)

        # Classify and score
        claim_type = type_override or _classify_claim(sentence)
        confidence = _score_confidence(sentence, file_refs) - confidence_penalty
        confidence = max(0.0, min(1.0, round(confidence, 3)))

        # Get surrounding context
        context = _get_context(full_body, sentence)

        claims.append(ExtractedClaim(
            claim_text=sentence,
            source_file=source_file,
            source_model=source_model,
            file_references=file_refs,
            claim_type=claim_type,
            confidence=confidence,
            context=context,
        ))


# ── Cairn-level extraction ───────────────────────────────────────────

def extract_claims_from_cairn(
    cairn_dir: Path,
    pattern: str = "scout_*.md",
    max_reports: int = 50,
) -> list[ExtractedClaim]:
    """Scan the cairn for reports and extract claims from them.

    Processes the most recent max_reports files matching the pattern.
    Deduplicates similar claims across reports using fuzzy matching
    on claim_text.

    Args:
        cairn_dir: Path to the cairn directory.
        pattern: Glob pattern for report files. Use "*.md" for all reports,
            "scout_*.md" for scouts only, "scour_*.md" for scours only.
        max_reports: Maximum number of reports to process.

    Returns:
        Deduplicated claims sorted by confidence (highest first).
    """
    if not cairn_dir.is_dir():
        logger.warning("Cairn directory does not exist: %s", cairn_dir)
        return []

    # Find matching reports, most recent first (by modification time)
    report_files = sorted(
        cairn_dir.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:max_reports]

    if not report_files:
        logger.info("No reports matching '%s' in %s", pattern, cairn_dir)
        return []

    logger.info(
        "Processing %d reports from %s (pattern=%s)",
        len(report_files), cairn_dir, pattern,
    )

    all_claims: list[ExtractedClaim] = []
    for report_path in report_files:
        claims = extract_claims_from_report(report_path)
        all_claims.extend(claims)

    # Deduplicate across reports
    deduped = _deduplicate_claims(all_claims)

    # Sort by confidence (highest first)
    deduped.sort(key=lambda c: c.confidence, reverse=True)

    logger.info(
        "Gleaned %d unique claims from %d reports (%d before dedup)",
        len(deduped), len(report_files), len(all_claims),
    )
    return deduped


# ── Verification selection ───────────────────────────────────────────

def claims_for_verification(
    claims: list[ExtractedClaim],
    max_claims: int = 5,
) -> list[ExtractedClaim]:
    """Select the most verifiable claims for dispatch to judges.

    Prioritizes:
    1. Factual claims with file references (most checkable)
    2. Claims from different models (source diversity)
    3. Higher confidence claims (clearer assertions)

    Excludes claims that are too vague to verify (no file references
    and not quantitative).

    Args:
        claims: Full list of extracted claims.
        max_claims: Maximum number of claims to select.

    Returns:
        Selected claims ready for verification dispatch.
    """
    if not claims:
        return []

    # Phase 1: Filter to verifiable claims
    verifiable = []
    for claim in claims:
        # Must have file references OR be a quantitative assertion
        has_refs = bool(claim.file_references)
        has_quantity = bool(_QUANTITATIVE_PATTERN.search(claim.claim_text))

        if not has_refs and not has_quantity:
            continue

        # Skip epistemic claims (they're about unknowns, not checkable facts)
        if claim.claim_type == "epistemic":
            continue

        # Skip very low confidence claims
        if claim.confidence < 0.3:
            continue

        verifiable.append(claim)

    if not verifiable:
        logger.info("No verifiable claims found after filtering")
        return []

    # Phase 2: Select for diversity
    selected: list[ExtractedClaim] = []
    models_used: set[str] = set()

    # First pass: one claim per model (diversity)
    for claim in verifiable:
        if len(selected) >= max_claims:
            break
        if claim.source_model not in models_used:
            selected.append(claim)
            models_used.add(claim.source_model)

    # Second pass: fill remaining slots with best remaining claims
    if len(selected) < max_claims:
        for claim in verifiable:
            if len(selected) >= max_claims:
                break
            if claim not in selected:
                selected.append(claim)

    logger.info(
        "Selected %d claims for verification from %d verifiable (%d total)",
        len(selected), len(verifiable), len(claims),
    )
    return selected


# ── Deduplication ────────────────────────────────────────────────────

def _normalize_for_dedup(text: str) -> str:
    """Normalize text for fuzzy deduplication.

    Lowercases, strips markdown formatting, collapses whitespace,
    and removes backtick-wrapped content to compare the semantic
    core of the sentence.
    """
    normalized = text.lower()
    # Strip markdown formatting
    normalized = re.sub(r"[*_`#]", "", normalized)
    # Collapse whitespace
    normalized = re.sub(r"\s+", " ", normalized).strip()
    # Remove very short words (articles, prepositions) for fuzzier matching
    # Only for dedup purposes — we keep original text in the claim
    normalized = re.sub(r"\b(?:a|an|the|in|on|at|to|of|for|is|it|by)\b", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _deduplicate_claims(claims: list[ExtractedClaim]) -> list[ExtractedClaim]:
    """Deduplicate claims using normalized text comparison.

    When two claims are similar, keeps the one with higher confidence.
    Also merges file references from the duplicate into the survivor.
    """
    if not claims:
        return []

    # Group by normalized text
    groups: dict[str, list[ExtractedClaim]] = {}
    for claim in claims:
        norm = _normalize_for_dedup(claim.claim_text)
        # Further compress for grouping: take first 80 chars of normalized text
        # This catches claims that say the same thing with slight variations
        key = norm[:80]
        groups.setdefault(key, []).append(claim)

    deduped: list[ExtractedClaim] = []
    for key, group in groups.items():
        if len(group) == 1:
            deduped.append(group[0])
            continue

        # Keep the highest-confidence version
        group.sort(key=lambda c: c.confidence, reverse=True)
        winner = group[0]

        # Merge file references from all duplicates
        all_refs: list[str] = list(winner.file_references)
        seen_refs: set[str] = set(all_refs)
        for dup in group[1:]:
            for ref in dup.file_references:
                if ref not in seen_refs:
                    all_refs.append(ref)
                    seen_refs.add(ref)

        deduped.append(ExtractedClaim(
            claim_text=winner.claim_text,
            source_file=winner.source_file,
            source_model=winner.source_model,
            file_references=all_refs,
            claim_type=winner.claim_type,
            confidence=winner.confidence,
            context=winner.context,
        ))

    return deduped


# ── Adapter for scorer.VerifiableClaim compatibility ─────────────────

def to_verifiable_claims(
    claims: list[ExtractedClaim],
) -> list[tuple[str, str, str, str]]:
    """Convert ExtractedClaims to tuples compatible with dispatch_verify.

    Returns a list of (claim_text, file_path, source_model, source_file)
    tuples matching the parameters of coordinator.dispatch_verify.

    Claims without file references are skipped since dispatch_verify
    requires a specific file_path.
    """
    results = []
    for claim in claims:
        if not claim.file_references:
            continue
        # Use the first file reference as the primary file_path
        raw_ref = claim.file_references[0]
        # Strip line number suffix if present
        file_path = raw_ref.rsplit(":", 1)[0]
        results.append((
            claim.claim_text,
            file_path,
            claim.source_model,
            claim.source_file,
        ))
    return results
