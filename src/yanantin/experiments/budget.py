"""Per-run cost budget for the memory-tool harness.

OpenRouter responses carry per-call cost on `usage['cost']`. The runner
adds each completed call's cost to a CostBudget; when a call would push
the total over the ceiling, the runner halts before issuing it. This is
the runaway guard the spec calls for: an experiment can't silently burn
through more than its pre-registered budget.

Asymmetry to note: `ok()` is strict-less (False at exact ceiling); the
rejection check on `add()` is strict-greater (a charge bringing the total
exactly to the ceiling is allowed). That asymmetry lets a single boundary
charge land, then the next call gets a clean "no, we're done" from `ok()`.
"""

from __future__ import annotations


class BudgetExceeded(RuntimeError):
    """Raised when a charge would push the running total past the ceiling."""


class CostBudget:
    """Stateful running total against a fixed ceiling (US dollars)."""

    def __init__(self, ceiling_usd: float) -> None:
        if ceiling_usd < 0:
            raise ValueError(f"ceiling_usd must be non-negative, got {ceiling_usd!r}")
        self._ceiling = float(ceiling_usd)
        self._spent = 0.0

    @property
    def ceiling_usd(self) -> float:
        return self._ceiling

    @property
    def spent_usd(self) -> float:
        return self._spent

    @property
    def remaining_usd(self) -> float:
        return self._ceiling - self._spent

    def ok(self) -> bool:
        return self._spent < self._ceiling

    def add(self, cost_usd: float) -> None:
        if cost_usd < 0:
            raise ValueError(f"cost must be non-negative, got {cost_usd!r}")
        new_total = self._spent + cost_usd
        if new_total > self._ceiling:
            raise BudgetExceeded(
                f"adding {cost_usd:.6f} to {self._spent:.6f} would exceed "
                f"ceiling {self._ceiling:.6f}"
            )
        self._spent = new_total
