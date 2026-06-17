"""SyntheticCollectorBase — deterministic synthetic data generators.

Private module. Import from yanantin.collector directly.
"""

from __future__ import annotations

import random
from abc import abstractmethod
from datetime import datetime
from typing import TypeVar
from uuid import NAMESPACE_DNS, UUID, uuid5

from yanantin.collector._collector_base import CollectorBase

DataT = TypeVar("DataT")


class SyntheticCollectorBase(CollectorBase[DataT]):
    """Base for synthetic data generators paired with real collectors.

    The synthetic twin must produce DataT instances indistinguishable
    from the real collector's output in structure. Seeded RNG ensures
    reproducibility across runs.
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    @abstractmethod
    def generate(self) -> DataT:
        """Generate a single synthetic data item."""
        ...

    def collect(self, since: datetime | None = None) -> DataT:
        """Collect by generating synthetic data."""
        return self.generate()

    def collect_batch(self, count: int) -> list[DataT]:
        """Generate multiple synthetic items."""
        return [self.generate() for _ in range(count)]

    def get_provider_id(self) -> UUID:
        """Provider ID derived from the class name."""
        return uuid5(
            NAMESPACE_DNS,
            f"yanantin.synthetic.{self.__class__.__name__}",
        )
