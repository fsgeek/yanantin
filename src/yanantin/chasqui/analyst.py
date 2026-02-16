"""Analyst — surface cross-model patterns from gleaner claims.

The Analyst sits in the Chasqui pipeline after the Gleaner:

    Scout → Gleaner → **Analyst** → Verify → Respond

It takes the raw claim stream (4000+ claims from 800+ scout reports)
and distills it into actionable insights by:

1. Filtering garbage from models that produce corrupted output
2. Scoring model quality (claim density, reference density, confidence)
3. Clustering claims by their primary file reference
4. Detecting cross-model agreement (topology) vs single-model assertions (texture)
5. Producing a ranked report of distilled insights

Deterministic. No LLM calls. Uses word-overlap similarity for
within-cluster semantic grouping.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field

from yanantin.chasqui.gleaner import ExtractedClaim

logger = logging.getLogger(__name__)


# ── Data structures ──────────────────────────────────────────────────

@dataclass
class ModelProfile:
    """Quality profile for a scout model."""

    model_id: str
    claim_count: int = 0
    claims_with_refs: int = 0
    avg_confidence: float = 0.0
    garbage_count: int = 0

    @property
    def ref_ratio(self) -> float:
        """Fraction of claims with file references."""
        return self.claims_with_refs / self.claim_count if self.claim_count else 0.0

    @property
    def garbage_ratio(self) -> float:
        """Fraction of claims that are garbage."""
        return self.garbage_count / self.claim_count if self.claim_count else 0.0

    @property
    def quality_score(self) -> float:
        """Composite quality: high refs, high confidence, low garbage."""
        if self.claim_count == 0:
            return 0.0
        return (
            self.ref_ratio * 0.4
            + self.avg_confidence * 0.3
            + (1.0 - self.garbage_ratio) * 0.3
        )


@dataclass
class ClaimGroup:
    """Claims within a cluster that say similar things."""

    representative: str  # The highest-confidence claim text
    claims: list[ExtractedClaim] = field(default_factory=list)
    model_ids: set[str] = field(default_factory=set)
    claim_type: str = "factual"
    avg_confidence: float = 0.0
    verification_ratio: float = 0.0  # Fraction of claims that are verification meta

    @property
    def model_count(self) -> int:
        return len(self.model_ids)

    @property
    def is_topological(self) -> bool:
        """3+ distinct models agreeing = structural truth."""
        return self.model_count >= 3

    @property
    def is_original(self) -> bool:
        """Mostly original observations, not verification meta-claims."""
        return self.verification_ratio < 0.5


@dataclass
class ClaimCluster:
    """Claims about the same file, grouped by semantic similarity."""

    file_reference: str
    groups: list[ClaimGroup] = field(default_factory=list)
    total_claims: int = 0
    distinct_models: int = 0

    @property
    def topological_groups(self) -> list[ClaimGroup]:
        return [g for g in self.groups if g.is_topological]


@dataclass
class AnalysisReport:
    """Full analysis output."""

    total_claims_input: int
    claims_after_filter: int
    garbage_filtered: int
    verification_claims: int = 0  # Claims that are scouts reviewing scouts
    clusters: list[ClaimCluster] = field(default_factory=list)
    model_profiles: list[ModelProfile] = field(default_factory=list)
    topological_insights: list[ClaimGroup] = field(default_factory=list)
    verification_insights: list[ClaimGroup] = field(default_factory=list)  # Topology in verification layer
    textural_observations: list[ClaimGroup] = field(default_factory=list)
    open_questions: list[ExtractedClaim] = field(default_factory=list)  # High-quality unique claims the consensus missed


# ── Verification meta-claim detection ────────────────────────────────

_VERDICT_PATTERN = re.compile(
    r"\b(?:Verdict|CONFIRMED|DENIED|INDETERMINATE)\b", re.IGNORECASE
)
_VERIFICATION_PHRASES = re.compile(
    r"(?:The claim (?:is|states|asserts)|Evidence (?:shows|confirms|denies)|"
    r"Reasoning The (?:claim|file)|the claim is (?:fully |partially )?(?:supported|verified|denied))",
    re.IGNORECASE,
)


def is_verification_meta(claim_text: str) -> bool:
    """Detect claims that are scouts reviewing other scouts' claims.

    These are metadata about claims, not original observations.
    They contain verdict language and verification framing.
    """
    has_verdict = bool(_VERDICT_PATTERN.search(claim_text))
    has_verification = bool(_VERIFICATION_PHRASES.search(claim_text))
    return has_verdict or has_verification


# ── Garbage detection ────────────────────────────────────────────────

# Non-ASCII noise patterns (corrupted model output)
_GARBAGE_PATTERN = re.compile(
    r"[\u4e00-\u9fff\u0400-\u04ff\u0370-\u03ff\uac00-\ud7af]{3,}"
)

# Encoding artifacts
_ENCODING_ARTIFACTS = re.compile(r"[ÃÂ©®™]{2,}")


def is_garbage(claim_text: str) -> bool:
    """Detect corrupted or nonsensical claim text.

    Catches: CJK/Cyrillic/Greek/Korean character runs in English context,
    encoding artifacts, extremely short content after cleanup.
    """
    # Non-ASCII character runs in what should be English text
    if _GARBAGE_PATTERN.search(claim_text):
        return True

    # Encoding artifacts
    if _ENCODING_ARTIFACTS.search(claim_text):
        return True

    # Strip markdown formatting and check if anything substantive remains
    stripped = re.sub(r"[*_`#\-=>\[\]\(\)|:{}]", "", claim_text).strip()
    words = stripped.split()
    if len(words) < 4:
        return True

    # Ratio of alphabetic characters to total — low ratio = noise
    alpha = sum(1 for c in stripped if c.isalpha())
    if len(stripped) > 0 and alpha / len(stripped) < 0.4:
        return True

    return False


# ── Model quality scoring ────────────────────────────────────────────

def score_models(claims: list[ExtractedClaim]) -> dict[str, ModelProfile]:
    """Build quality profiles for each model that contributed claims."""
    profiles: dict[str, ModelProfile] = {}

    for claim in claims:
        model = claim.source_model
        if model not in profiles:
            profiles[model] = ModelProfile(model_id=model)
        p = profiles[model]
        p.claim_count += 1
        if claim.file_references:
            p.claims_with_refs += 1
        if is_garbage(claim.claim_text):
            p.garbage_count += 1

    # Compute average confidence per model
    confidence_sums: dict[str, float] = {}
    confidence_counts: dict[str, int] = {}
    for claim in claims:
        model = claim.source_model
        confidence_sums[model] = confidence_sums.get(model, 0.0) + claim.confidence
        confidence_counts[model] = confidence_counts.get(model, 0) + 1

    for model, p in profiles.items():
        if confidence_counts.get(model, 0) > 0:
            p.avg_confidence = confidence_sums[model] / confidence_counts[model]

    return profiles


def filter_garbage(
    claims: list[ExtractedClaim],
    model_profiles: dict[str, ModelProfile] | None = None,
    model_garbage_threshold: float = 0.5,
) -> tuple[list[ExtractedClaim], int]:
    """Remove garbage claims and claims from garbage-heavy models.

    Args:
        claims: Raw claims from gleaner.
        model_profiles: Pre-computed profiles (computed if None).
        model_garbage_threshold: Models with garbage ratio above this are excluded entirely.

    Returns:
        (filtered_claims, garbage_count)
    """
    if model_profiles is None:
        model_profiles = score_models(claims)

    # Identify garbage-heavy models
    bad_models = {
        model_id
        for model_id, profile in model_profiles.items()
        if profile.garbage_ratio > model_garbage_threshold
    }

    filtered = []
    garbage_count = 0

    for claim in claims:
        if claim.source_model in bad_models:
            garbage_count += 1
            continue
        if is_garbage(claim.claim_text):
            garbage_count += 1
            continue
        filtered.append(claim)

    if bad_models:
        logger.info(
            "Excluded %d garbage-heavy models: %s",
            len(bad_models),
            ", ".join(sorted(bad_models)),
        )
    logger.info(
        "Filtered %d garbage claims (%d → %d)",
        garbage_count, len(claims), len(filtered),
    )

    return filtered, garbage_count


# ── Word-level similarity ────────────────────────────────────────────

_STOP_WORDS = frozenset({
    "a", "an", "the", "in", "on", "at", "to", "of", "for", "is", "it",
    "by", "and", "or", "but", "not", "with", "from", "this", "that",
    "are", "was", "were", "be", "been", "has", "have", "had", "do",
    "does", "did", "will", "would", "could", "should", "may", "might",
    "can", "shall", "its", "as", "if", "then", "than", "so", "no",
    "yes", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "only", "own", "same", "very", "just",
    "about", "above", "after", "again", "also", "any", "because",
    "before", "between", "during", "here", "how", "into", "like",
    "many", "much", "over", "through", "under", "up", "what", "when",
    "where", "which", "while", "who", "why",
})


def _content_words(text: str) -> set[str]:
    """Extract content words (lowercased, no stop words, no formatting)."""
    cleaned = re.sub(r"[*_`#\-=>\[\]\(\)|:{}/\\]", " ", text.lower())
    words = set(cleaned.split())
    return words - _STOP_WORDS


def word_similarity(text_a: str, text_b: str) -> float:
    """Jaccard similarity on content words."""
    words_a = _content_words(text_a)
    words_b = _content_words(text_b)
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


# ── Clustering ───────────────────────────────────────────────────────

def _primary_reference(claim: ExtractedClaim) -> str:
    """Get the primary file reference for clustering."""
    if claim.file_references:
        # Strip line numbers for grouping
        ref = claim.file_references[0]
        return ref.rsplit(":", 1)[0]
    return ""


def cluster_claims(
    claims: list[ExtractedClaim],
    similarity_threshold: float = 0.35,
) -> list[ClaimCluster]:
    """Cluster claims by file reference, then sub-group by similarity.

    Claims without file references are grouped under "" (no-reference cluster).
    Within each file cluster, claims are grouped by word similarity into
    ClaimGroups. Each group represents a distinct assertion about the file.

    Args:
        claims: Filtered claims from gleaner.
        similarity_threshold: Jaccard threshold for grouping similar claims.

    Returns:
        Clusters sorted by number of topological groups (most interesting first).
    """
    # Phase 1: Group by primary file reference
    by_file: dict[str, list[ExtractedClaim]] = {}
    for claim in claims:
        ref = _primary_reference(claim)
        by_file.setdefault(ref, []).append(claim)

    clusters: list[ClaimCluster] = []

    for file_ref, file_claims in by_file.items():
        groups = _group_similar_claims(file_claims, similarity_threshold)
        all_models = set()
        for g in groups:
            all_models.update(g.model_ids)

        cluster = ClaimCluster(
            file_reference=file_ref,
            groups=groups,
            total_claims=len(file_claims),
            distinct_models=len(all_models),
        )
        clusters.append(cluster)

    # Sort: most topological groups first, then by total claims
    clusters.sort(
        key=lambda c: (len(c.topological_groups), c.total_claims),
        reverse=True,
    )

    return clusters


def _group_similar_claims(
    claims: list[ExtractedClaim],
    threshold: float,
) -> list[ClaimGroup]:
    """Group claims by word similarity within a file cluster.

    Simple greedy clustering: for each claim, find the first group
    whose representative is similar enough. If none, start a new group.
    """
    groups: list[ClaimGroup] = []

    # Sort by confidence so highest-confidence claims become representatives
    sorted_claims = sorted(claims, key=lambda c: c.confidence, reverse=True)

    for claim in sorted_claims:
        placed = False
        for group in groups:
            if word_similarity(claim.claim_text, group.representative) >= threshold:
                group.claims.append(claim)
                group.model_ids.add(claim.source_model)
                placed = True
                break

        if not placed:
            groups.append(ClaimGroup(
                representative=claim.claim_text,
                claims=[claim],
                model_ids={claim.source_model},
                claim_type=claim.claim_type,
            ))

    # Compute average confidence and verification ratio per group
    for group in groups:
        if group.claims:
            group.avg_confidence = sum(c.confidence for c in group.claims) / len(group.claims)
            meta_count = sum(1 for c in group.claims if is_verification_meta(c.claim_text))
            group.verification_ratio = meta_count / len(group.claims)

    # Sort by model count (topological first), then confidence
    groups.sort(
        key=lambda g: (g.model_count, g.avg_confidence),
        reverse=True,
    )

    return groups


# ── Full analysis pipeline ───────────────────────────────────────────

def analyze(
    claims: list[ExtractedClaim],
    model_garbage_threshold: float = 0.5,
    similarity_threshold: float = 0.35,
    min_models_for_topology: int = 3,
) -> AnalysisReport:
    """Full analysis pipeline: filter → cluster → detect topology.

    Args:
        claims: Raw claims from gleaner's extract_claims_from_cairn.
        model_garbage_threshold: Exclude models with garbage ratio above this.
        similarity_threshold: Jaccard threshold for grouping similar claims.
        min_models_for_topology: Minimum distinct models for a topological insight.

    Returns:
        AnalysisReport with clusters, model profiles, and ranked insights.
    """
    total_input = len(claims)
    logger.info("Analyst: processing %d claims", total_input)

    # Step 1: Score models
    model_profiles = score_models(claims)

    # Step 2: Filter garbage
    filtered, garbage_count = filter_garbage(
        claims, model_profiles, model_garbage_threshold
    )

    # Step 3: Cluster
    clusters = cluster_claims(filtered, similarity_threshold)

    # Step 3.5: Count verification meta-claims
    verification_count = sum(1 for c in filtered if is_verification_meta(c.claim_text))

    # Step 4: Extract topological insights, split by original vs verification
    topological: list[ClaimGroup] = []
    verification_topo: list[ClaimGroup] = []
    textural: list[ClaimGroup] = []

    # Step 5: Collect open questions — the claims the consensus missed.
    # High-quality unique observations, especially epistemic and architectural,
    # from singleton groups. The 3+ model consensus filter finds what's obvious.
    # Individual models asking questions or noticing patterns nobody else did
    # is where the interesting signal lives.
    open_questions: list[ExtractedClaim] = []

    for cluster in clusters:
        for group in cluster.groups:
            if group.model_count >= min_models_for_topology:
                if group.is_original:
                    topological.append(group)
                else:
                    verification_topo.append(group)
            elif group.model_count == 1 and len(group.claims) >= 2:
                textural.append(group)

            # Harvest unique observations from singleton groups
            if group.model_count == 1 and group.is_original:
                for claim in group.claims:
                    if (
                        claim.confidence >= 0.6
                        and not is_verification_meta(claim.claim_text)
                        and claim.claim_type in ("epistemic", "architectural", "structural", "missing")
                    ):
                        open_questions.append(claim)

    # Sort: epistemic first, then by confidence
    _type_priority = {"epistemic": 0, "architectural": 1, "structural": 2, "missing": 3}
    open_questions.sort(
        key=lambda c: (_type_priority.get(c.claim_type, 9), -c.confidence),
    )

    # Sort topological by model count then confidence
    topological.sort(
        key=lambda g: (g.model_count, g.avg_confidence),
        reverse=True,
    )
    verification_topo.sort(
        key=lambda g: (g.model_count, g.avg_confidence),
        reverse=True,
    )

    # Sort model profiles by quality
    sorted_profiles = sorted(
        model_profiles.values(),
        key=lambda p: p.quality_score,
        reverse=True,
    )

    report = AnalysisReport(
        total_claims_input=total_input,
        claims_after_filter=len(filtered),
        garbage_filtered=garbage_count,
        verification_claims=verification_count,
        clusters=clusters,
        model_profiles=sorted_profiles,
        topological_insights=topological,
        verification_insights=verification_topo,
        textural_observations=textural[:50],
        open_questions=open_questions[:30],
    )

    logger.info(
        "Analysis complete: %d claims → %d filtered (%d verification) → "
        "%d clusters → %d original topological, %d verification topological, "
        "%d open questions",
        total_input, len(filtered), verification_count, len(clusters),
        len(topological), len(verification_topo), len(open_questions),
    )

    return report


# ── Rendering ────────────────────────────────────────────────────────

def render_report(report: AnalysisReport, max_insights: int = 30) -> str:
    """Render an analysis report as human-readable markdown."""
    lines: list[str] = []

    lines.append("# Scout Corpus Analysis")
    lines.append("")
    lines.append(f"**Claims processed:** {report.total_claims_input}")
    lines.append(f"**After garbage filter:** {report.claims_after_filter} "
                 f"({report.garbage_filtered} removed)")
    lines.append(f"**Verification meta-claims:** {report.verification_claims} "
                 f"(scouts reviewing scouts)")
    lines.append(f"**Clusters:** {len(report.clusters)} (by file reference)")
    lines.append(f"**Original topological insights:** {len(report.topological_insights)} "
                 f"(3+ models agree, original observations)")
    lines.append(f"**Open questions:** {len(report.open_questions)} "
                 f"(unique observations the consensus missed)")
    lines.append(f"**Verification topological insights:** {len(report.verification_insights)} "
                 f"(3+ models agree, verification layer)")
    lines.append(f"**Models contributing:** {len(report.model_profiles)}")
    lines.append("")

    # Original topological insights
    lines.append("## Original Topological Insights (cross-model agreement)")
    lines.append("")
    if not report.topological_insights:
        lines.append("*None found.*")
    else:
        for i, group in enumerate(report.topological_insights[:max_insights], 1):
            models_str = ", ".join(sorted(group.model_ids)[:5])
            if group.model_count > 5:
                models_str += f" (+{group.model_count - 5} more)"
            lines.append(f"### {i}. [{group.claim_type}] {group.model_count} models agree")
            lines.append(f"**Representative claim:** {group.representative[:200]}")
            lines.append(f"**Models:** {models_str}")
            lines.append(f"**Claims in group:** {len(group.claims)}, "
                         f"avg confidence: {group.avg_confidence:.2f}")
            lines.append("")

    # Verification insights (collapsed summary)
    if report.verification_insights:
        lines.append(f"## Verification Layer ({len(report.verification_insights)} "
                     f"topological groups)")
        lines.append("")
        lines.append("*These are scouts reviewing other scouts' claims. "
                     "The verdicts themselves show cross-model agreement.*")
        lines.append("")
        for i, group in enumerate(report.verification_insights[:10], 1):
            lines.append(f"{i}. [{group.claim_type}] {group.model_count} models — "
                         f"{group.representative[:120]}")
        lines.append("")

    # Open questions — what individual models noticed that consensus missed
    if report.open_questions:
        lines.append(f"## Open Questions ({len(report.open_questions)} unique observations)")
        lines.append("")
        lines.append("*Claims from individual models that the consensus filter dropped. "
                     "Epistemic and architectural observations, not file-existence confirmations.*")
        lines.append("")
        for i, claim in enumerate(report.open_questions[:20], 1):
            lines.append(f"### {i}. [{claim.claim_type}] {claim.source_model}")
            lines.append(f"{claim.claim_text[:300]}")
            if claim.file_references:
                lines.append(f"  refs: {', '.join(claim.file_references[:3])}")
            lines.append("")

    # Top clusters
    lines.append("## Top File Clusters")
    lines.append("")
    for cluster in report.clusters[:15]:
        if not cluster.file_reference:
            continue
        topo_count = len(cluster.topological_groups)
        lines.append(f"- **`{cluster.file_reference}`**: "
                     f"{cluster.total_claims} claims, "
                     f"{cluster.distinct_models} models, "
                     f"{topo_count} topological groups")

    lines.append("")

    # Model quality
    lines.append("## Model Quality (top 10)")
    lines.append("")
    lines.append("| Model | Claims | Ref% | Confidence | Garbage% | Quality |")
    lines.append("|-------|--------|------|------------|----------|---------|")
    for profile in report.model_profiles[:10]:
        lines.append(
            f"| {profile.model_id[:40]} | {profile.claim_count} | "
            f"{profile.ref_ratio:.0%} | {profile.avg_confidence:.2f} | "
            f"{profile.garbage_ratio:.0%} | {profile.quality_score:.2f} |"
        )
    lines.append("")

    # Worst models
    worst = [p for p in report.model_profiles if p.garbage_ratio > 0.3]
    if worst:
        worst.sort(key=lambda p: p.garbage_ratio, reverse=True)
        lines.append("## Garbage-heavy Models")
        lines.append("")
        for p in worst[:10]:
            lines.append(f"- **{p.model_id}**: {p.garbage_ratio:.0%} garbage "
                         f"({p.garbage_count}/{p.claim_count})")
        lines.append("")

    return "\n".join(lines)
