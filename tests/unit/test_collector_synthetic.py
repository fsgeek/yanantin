"""Tests for the SyntheticCollectorBase ABC."""

from __future__ import annotations

import pytest

from yanantin.collector._synthetic_base import SyntheticCollectorBase


class TestSyntheticCollectorBase:
    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            SyntheticCollectorBase()  # type: ignore[abstract]

    def test_concrete_subclass_works(self) -> None:
        class DummySynthetic(SyntheticCollectorBase[int]):
            def generate(self) -> int:
                return self._rng.randint(0, 100)

            def get_description(self) -> str:
                return "dummy"

        collector = DummySynthetic(seed=42)
        value = collector.collect()
        assert isinstance(value, int)
        assert 0 <= value <= 100

    def test_seeded_output_is_deterministic(self) -> None:
        class DummySynthetic(SyntheticCollectorBase[int]):
            def generate(self) -> int:
                return self._rng.randint(0, 1000000)

            def get_description(self) -> str:
                return "dummy"

        c1 = DummySynthetic(seed=42)
        c2 = DummySynthetic(seed=42)
        assert c1.collect() == c2.collect()

    def test_collect_batch_returns_correct_count(self) -> None:
        class DummySynthetic(SyntheticCollectorBase[int]):
            def generate(self) -> int:
                return self._rng.randint(0, 100)

            def get_description(self) -> str:
                return "dummy"

        collector = DummySynthetic(seed=42)
        batch = collector.collect_batch(7)
        assert len(batch) == 7

    def test_provider_id_derived_from_class_name(self) -> None:
        class AlphaSynthetic(SyntheticCollectorBase[int]):
            def generate(self) -> int:
                return 0

            def get_description(self) -> str:
                return "alpha"

        class BetaSynthetic(SyntheticCollectorBase[int]):
            def generate(self) -> int:
                return 0

            def get_description(self) -> str:
                return "beta"

        a = AlphaSynthetic(seed=1)
        b = BetaSynthetic(seed=1)
        assert a.get_provider_id() != b.get_provider_id()

        # Same class → same ID regardless of seed
        a1 = AlphaSynthetic(seed=1)
        a2 = AlphaSynthetic(seed=99)
        assert a1.get_provider_id() == a2.get_provider_id()

    def test_unseeded_still_works(self) -> None:
        class DummySynthetic(SyntheticCollectorBase[int]):
            def generate(self) -> int:
                return self._rng.randint(0, 100)

            def get_description(self) -> str:
                return "dummy"

        collector = DummySynthetic()  # no seed
        value = collector.collect()
        assert isinstance(value, int)
