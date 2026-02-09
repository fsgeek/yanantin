"""Markdown renderer — converts tensor records to human-readable output.

Human readability via tooling, not schema constraint. The schema stores
structured data; this module renders it for humans.
"""

from __future__ import annotations

from uuid import UUID

from yanantin.apacheta.interface.abstract import ApachetaInterface
from yanantin.apacheta.models.tensor import TensorRecord


def render_tensor(tensor: TensorRecord, *, include_metadata: bool = False) -> str:
    """Render a single tensor as markdown.

    Matches the T0-T8 format conventions: preamble, strands as sections,
    closing, instructions for next instance.
    """
    lines: list[str] = []

    # Preamble
    if tensor.preamble:
        lines.append(tensor.preamble)
        lines.append("")

    # Metadata block (optional)
    if include_metadata:
        lines.append("---")
        lines.append(f"**ID:** `{tensor.id}`")
        prov = tensor.provenance
        if prov.author_model_family:
            lines.append(f"**Author:** {prov.author_model_family}")
        if prov.author_instance_id:
            lines.append(f"**Instance:** {prov.author_instance_id}")
        lines.append(f"**Timestamp:** {prov.timestamp.isoformat()}")
        if prov.context_budget_at_write is not None:
            lines.append(f"**Context Budget:** {prov.context_budget_at_write:.0%}")
        if tensor.lineage_tags:
            lines.append(f"**Lineage:** {', '.join(tensor.lineage_tags)}")
        ep = tensor.epistemic
        lines.append(f"**T/I/F:** ({ep.truth}, {ep.indeterminacy}, {ep.falsity})")
        lines.append("---")
        lines.append("")

    # Strands
    for strand in tensor.strands:
        lines.append(f"## Strand {strand.strand_index}: {strand.title}")
        lines.append("")
        if strand.content:
            lines.append(strand.content)
            lines.append("")
        if strand.topics:
            lines.append(f"*Topics: {', '.join(strand.topics)}*")
            lines.append("")
        if include_metadata and strand.key_claims:
            for claim in strand.key_claims:
                ep = claim.epistemic
                lines.append(
                    f"- **Claim:** {claim.text} "
                    f"(T={ep.truth}, I={ep.indeterminacy}, F={ep.falsity})"
                )
            lines.append("")

    # Declared losses
    if tensor.declared_losses:
        lines.append("## Declared Losses")
        lines.append("")
        lines.append("The losses are mine.")
        lines.append("")
        for loss in tensor.declared_losses:
            lines.append(f"- **{loss.what_was_lost}** — {loss.why} [{loss.category.value}]")
        lines.append("")

    # Open questions
    if tensor.open_questions:
        lines.append("## Open Questions")
        lines.append("")
        for q in tensor.open_questions:
            lines.append(f"- {q}")
        lines.append("")

    # Instructions for next instance
    if tensor.instructions_for_next:
        lines.append("## For the Next Instance")
        lines.append("")
        lines.append(tensor.instructions_for_next)
        lines.append("")

    # Closing
    if tensor.closing:
        lines.append("---")
        lines.append("")
        lines.append(f"*{tensor.closing}*")
        lines.append("")

    return "\n".join(lines)


def render_composition_view(
    interface: ApachetaInterface,
    tensor_ids: list[UUID],
    *,
    reading_order: list[UUID] | None = None,
) -> str:
    """Render a composed view of multiple tensors with attribution.

    Each tensor's contribution is clearly marked. Composition preserves
    authorship — no collapsing into a flattened narrative.
    """
    ordered = reading_order or tensor_ids
    lines: list[str] = []

    lines.append("# Composed View")
    lines.append("")
    lines.append(f"*Composed from {len(ordered)} tensors*")
    lines.append("")

    for tid in ordered:
        tensor = interface.get_tensor(tid)
        prov = tensor.provenance
        author = prov.author_model_family or "unknown"
        lines.append(f"---")
        lines.append(f"### From tensor `{tid}` ({author})")
        lines.append("")
        lines.append(render_tensor(tensor))

    return "\n".join(lines)


def render_correction_chain(
    interface: ApachetaInterface,
    claim_id: UUID,
) -> str:
    """Render the correction history for a claim."""
    corrections = interface.query_correction_chain(claim_id)
    if not corrections:
        return f"No corrections found for claim `{claim_id}`."

    lines: list[str] = []
    lines.append(f"# Correction Chain for `{claim_id}`")
    lines.append("")

    for i, corr in enumerate(corrections):
        lines.append(f"## Correction {i + 1}")
        lines.append("")
        lines.append(f"**Original:** {corr.original_claim}")
        lines.append(f"**Corrected:** {corr.corrected_claim}")
        if corr.evidence:
            lines.append(f"**Evidence:** {corr.evidence}")
        lines.append(f"**Target tensor:** `{corr.target_tensor}`")
        lines.append("")

    return "\n".join(lines)
