import pytest

from yanantin.experiments.budget import BudgetExceeded, CostBudget


def test_constructor_rejects_negative_ceiling():
    with pytest.raises(ValueError):
        CostBudget(-0.01)


def test_initial_state_and_properties():
    budget = CostBudget(1.5)

    assert budget.ceiling_usd == pytest.approx(1.5)
    assert budget.spent_usd == pytest.approx(0.0)
    assert budget.remaining_usd == pytest.approx(1.5)
    assert budget.ok() is True


def test_ok_is_false_exactly_at_ceiling():
    budget = CostBudget(1.0)
    budget.add(1.0)

    assert budget.spent_usd == pytest.approx(1.0)
    assert budget.remaining_usd == pytest.approx(0.0)
    assert budget.ok() is False


def test_add_rejects_negative_charge_without_mutation():
    budget = CostBudget(2.0)
    budget.add(0.25)

    with pytest.raises(ValueError):
        budget.add(-0.01)

    assert budget.spent_usd == pytest.approx(0.25)
    assert budget.remaining_usd == pytest.approx(1.75)
    assert budget.ok() is True


def test_add_raises_budget_exceeded_and_does_not_mutate():
    budget = CostBudget(1.0)
    budget.add(0.9)

    with pytest.raises(BudgetExceeded):
        budget.add(0.11)

    assert budget.spent_usd == pytest.approx(0.9)
    assert budget.remaining_usd == pytest.approx(0.1)
    assert budget.ok() is True


def test_exactly_hitting_ceiling_is_allowed_but_blocks_future_charges():
    budget = CostBudget(1.0)
    budget.add(0.4)
    budget.add(0.6)

    assert budget.spent_usd == pytest.approx(1.0)
    assert budget.ok() is False

    with pytest.raises(BudgetExceeded):
        budget.add(0.0001)

    assert budget.spent_usd == pytest.approx(1.0)
    assert budget.remaining_usd == pytest.approx(0.0)


def test_zero_ceiling_starts_not_ok_and_only_allows_zero_charge():
    budget = CostBudget(0.0)

    assert budget.spent_usd == pytest.approx(0.0)
    assert budget.remaining_usd == pytest.approx(0.0)
    assert budget.ok() is False

    budget.add(0.0)
    assert budget.spent_usd == pytest.approx(0.0)

    with pytest.raises(BudgetExceeded):
        budget.add(1e-9)
