"""Tests for the Chasqui model selector."""

import pytest

from yanantin.chasqui.model_selector import ModelInfo, ModelSelector


class DummyRandom:
    """Records weights passed to random.choices and returns the last item."""

    def __init__(self):
        self.last_weights: list[float] | None = None
        self.calls = 0

    def choices(self, seq, weights, k):
        self.last_weights = list(weights)
        self.calls += 1
        return [seq[-1]]


def test_load_filters_by_context_and_exclusions():
    selector = ModelSelector(min_context_length=16_000, exclude_patterns=["bad/"])
    models_loaded = selector.load_from_openrouter_response([
        {
            "id": "bad/model",
            "name": "SkipThis",
            "context_length": 128_000,
            "pricing": {"prompt": "0.1", "completion": "0.2"},
        },
        {
            "id": "kept/model",
            "name": "Kept",
            "context_length": 20_000,
            "pricing": {"prompt": "0.12", "completion": "0.08"},
        },
        {
            "id": "zero-cost",
            "context_length": 64_000,
            "pricing": {"prompt": "abc", "completion": None},
        },
        {
            "id": "short-context",
            "context_length": 4_000,
        },
    ])

    assert models_loaded == 2
    assert [m.id for m in selector.models] == ["kept/model", "zero-cost"]
    assert selector.models[0].name == "Kept"
    assert selector.models[0].total_cost_per_million == pytest.approx(0.2)
    assert selector.models[1].total_cost_per_million == 0.0


def test_select_uses_inverse_cost_weights_and_nominal_free_cost():
    selector = ModelSelector()
    selector.models = [
        ModelInfo(id="expensive", name="Expensive", prompt_cost=1.0, completion_cost=1.0, context_length=32_000),
        ModelInfo(id="free", name="Free", prompt_cost=0.0, completion_cost=0.0, context_length=32_000),
    ]
    dummy = DummyRandom()
    selector._rng = dummy

    picked = selector.select()

    assert picked.id == "free"
    assert dummy.last_weights == pytest.approx([0.5, 1 / 0.001])


def test_select_raises_when_no_models_loaded():
    selector = ModelSelector()
    with pytest.raises(ValueError, match="No models loaded"):
        selector.select()


def test_select_n_calls_select_for_each_pick():
    selector = ModelSelector()
    selector.models = [
        ModelInfo(id="alpha", name="Alpha", prompt_cost=0.25, completion_cost=0.05, context_length=16_000),
        ModelInfo(id="beta", name="Beta", prompt_cost=0.1, completion_cost=0.1, context_length=16_000),
    ]
    dummy = DummyRandom()
    selector._rng = dummy

    picks = selector.select_n(3)

    assert len(picks) == 3
    assert all(p.id == "beta" for p in picks)
    assert dummy.calls == 3


def test_stats_report_cost_summary():
    selector = ModelSelector()
    selector.models = [
        ModelInfo(id="free", name="Free", prompt_cost=0.0, completion_cost=0.0, context_length=16_000),
        ModelInfo(id="cheap", name="Cheap", prompt_cost=0.2, completion_cost=0.1, context_length=16_000),
        ModelInfo(id="expensive", name="Expensive", prompt_cost=0.4, completion_cost=0.5, context_length=16_000),
    ]

    stats = selector.stats()

    assert stats["count"] == 3
    assert stats["free"] == 1
    assert stats["min_cost"] == pytest.approx(0.3)
    assert stats["max_cost"] == pytest.approx(0.9)
    assert stats["median_cost"] == pytest.approx(0.3)


def test_stats_empty_pool():
    selector = ModelSelector()
    assert selector.stats() == {"count": 0}
