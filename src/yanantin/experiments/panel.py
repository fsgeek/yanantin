"""Model-panel criteria and resolution against the live OpenRouter catalog.

A panel is defined as *criteria* — a curated candidate list with tier
annotations (family / size / cost), defended on first principles before
tool design starts. Resolution validates each candidate against the live
catalog (still available? context-length ok? not excluded?) and enriches
it with current pricing and context limits. The resolved panel plus the
catalog fingerprint plus the OTS stamp on the commit is the verifiable
record of "which models, current as of when."
"""

from __future__ import annotations

import fnmatch
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from yanantin.experiments.catalog import catalog_snapshot_sha


class CandidateModel(BaseModel):
    id: str
    family: str
    size_tier: str
    cost_tier: str


class PanelCriteria(BaseModel):
    panel_id: str
    rationale: str
    context_length_min: int = 8000
    exclude_patterns: list[str] = []
    candidates: list[CandidateModel]


class ResolvedModel(BaseModel):
    id: str
    family: str
    size_tier: str
    cost_tier: str
    prompt_cost: float
    completion_cost: float
    context_length: int
    native_max_tokens: int


class ResolvedPanel(BaseModel):
    panel_id: str
    rationale: str
    resolved_at: datetime
    catalog_snapshot_sha: str
    models: list[ResolvedModel]


def load_criteria(path: str | Path) -> PanelCriteria:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return PanelCriteria.model_validate(data)


def dump_resolved(panel: ResolvedPanel, path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        yaml.safe_dump(panel.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )


# Default applied when a catalog entry lacks top_provider.max_completion_tokens.
DEFAULT_NATIVE_MAX_TOKENS = 4096


def resolve_panel(
    criteria: PanelCriteria,
    catalog: list[dict[str, Any]],
    *,
    resolved_at: datetime | None = None,
) -> ResolvedPanel:
    """Validate each candidate against the live catalog and enrich it.

    Two failure modes, deliberately distinguished:

    - **Integrity:** a candidate id not present in the catalog raises
      ValueError. The user asked for a model that doesn't exist; that is a
      mistake to surface, not silently swallow.
    - **Policy filter:** a candidate matching `exclude_patterns` or failing
      `context_length_min` is dropped from the resolved set. The criteria
      YAML colocates these filters with the candidate pool — the contract
      is "here is my pool, here are filters to apply" — so a filter miss is
      expected behavior, not an error.

    The resolved panel is fingerprinted to the exact catalog passed.
    """
    by_id = {entry["id"]: entry for entry in catalog if "id" in entry}
    resolved: list[ResolvedModel] = []
    for cand in criteria.candidates:
        if any(fnmatch.fnmatch(cand.id, pat) for pat in criteria.exclude_patterns):
            continue
        entry = by_id.get(cand.id)
        if entry is None:
            raise ValueError(f"candidate {cand.id!r} not found in the OpenRouter catalog")
        ctx = int(entry.get("context_length", 0))
        if ctx < criteria.context_length_min:
            continue
        pricing = entry.get("pricing", {})
        native = (entry.get("top_provider", {}) or {}).get("max_completion_tokens")
        resolved.append(
            ResolvedModel(
                id=cand.id,
                family=cand.family,
                size_tier=cand.size_tier,
                cost_tier=cand.cost_tier,
                prompt_cost=float(pricing.get("prompt", 0.0)),
                completion_cost=float(pricing.get("completion", 0.0)),
                context_length=ctx,
                native_max_tokens=int(native) if native else DEFAULT_NATIVE_MAX_TOKENS,
            )
        )

    return ResolvedPanel(
        panel_id=criteria.panel_id,
        rationale=criteria.rationale,
        resolved_at=resolved_at or datetime.now(timezone.utc),
        catalog_snapshot_sha=catalog_snapshot_sha(catalog),
        models=resolved,
    )
