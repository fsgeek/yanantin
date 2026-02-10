"""Model selection for Chasqui scouts.

Picks models weighted inversely by cost. Cheap models get dispatched
more often. Over time, the cairn accumulates data on which models
notice what — and whether noticing more is worth paying more.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelInfo:
    """A model available through OpenRouter."""

    id: str
    name: str
    prompt_cost: float  # $/M tokens
    completion_cost: float  # $/M tokens
    context_length: int = 0

    @property
    def total_cost_per_million(self) -> float:
        return self.prompt_cost + self.completion_cost


@dataclass
class ModelSelector:
    """Cost-weighted random model selection.

    Models are weighted inversely by cost: a model at $0.10/M is
    10x more likely to be selected than one at $1.00/M. Free models
    get a small nominal cost to avoid division by zero.

    The selector can be filtered by constraints (minimum context length,
    excluded families, etc.) and seeded for reproducibility.
    """

    models: list[ModelInfo] = field(default_factory=list)
    min_context_length: int = 8_000
    exclude_patterns: list[str] = field(default_factory=list)
    _rng: random.Random = field(default_factory=random.Random)

    def seed(self, value: int) -> None:
        """Seed the RNG for reproducible selection."""
        self._rng = random.Random(value)

    def load_from_openrouter_response(self, models_data: list[dict[str, Any]]) -> int:
        """Parse the OpenRouter /models response into ModelInfo objects.

        Returns the number of models loaded after filtering.
        """
        loaded = []
        for entry in models_data:
            model_id = entry.get("id", "")

            # Skip if matches exclude pattern
            if any(pat in model_id for pat in self.exclude_patterns):
                continue

            # Extract pricing — OpenRouter nests this under "pricing"
            pricing = entry.get("pricing", {})
            try:
                prompt_cost = float(pricing.get("prompt", "0"))
                completion_cost = float(pricing.get("completion", "0"))
            except (ValueError, TypeError):
                prompt_cost = 0.0
                completion_cost = 0.0

            context_length = entry.get("context_length", 0) or 0
            if context_length < self.min_context_length:
                continue

            loaded.append(ModelInfo(
                id=model_id,
                name=entry.get("name", model_id),
                prompt_cost=prompt_cost,
                completion_cost=completion_cost,
                context_length=context_length,
            ))

        self.models = loaded
        return len(loaded)

    def select(self) -> ModelInfo:
        """Pick a model weighted inversely by cost.

        Raises ValueError if no models are loaded.
        """
        if not self.models:
            raise ValueError("No models loaded. Call load_from_openrouter_response first.")

        # Inverse cost weighting. Free models get nominal cost of $0.001/M
        # to avoid infinite weight while still being heavily favored.
        weights = []
        for m in self.models:
            cost = m.total_cost_per_million
            if cost <= 0:
                cost = 0.001  # Nominal cost for free models
            weights.append(1.0 / cost)

        return self._rng.choices(self.models, weights=weights, k=1)[0]

    def select_n(self, n: int) -> list[ModelInfo]:
        """Pick n models (with replacement). May return duplicates."""
        return [self.select() for _ in range(n)]

    def stats(self) -> dict[str, Any]:
        """Summary statistics about the model pool."""
        if not self.models:
            return {"count": 0}

        costs = [m.total_cost_per_million for m in self.models]
        free_count = sum(1 for c in costs if c <= 0)
        return {
            "count": len(self.models),
            "free": free_count,
            "min_cost": min(c for c in costs if c > 0) if any(c > 0 for c in costs) else 0,
            "max_cost": max(costs),
            "median_cost": sorted(costs)[len(costs) // 2],
        }
