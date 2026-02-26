"""Red-bar tests: Jabberwock module structural invariants.

These tests enforce that the Jabberwock NER module exists, is importable,
and maintains its structural contracts. They exist because:
- Module removal or renaming silently breaks dependent code.
- Frozen models prevent event mutation (event-sourced correctness).
- Stored records use extra="allow" (forward-compatible deserialization).
- Resolved views use extra="forbid" (strict ephemeral snapshots).
- ROOT_BANDERSNATCH_ID inconsistency breaks the provenance chain.

Test author: separate from builder (CI enforces separation).
"""

from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError


# -- Module existence ------------------------------------------------------


def test_jabberwock_module_exists():
    """The jabberwock module must be importable."""
    import yanantin.jabberwock  # noqa: F401


def test_jabberwock_models_importable():
    """All model classes must be importable from the package."""
    from yanantin.jabberwock import (  # noqa: F401
        Frabjous,
        Jabberwock,
        MomeResult,
        Rath,
        Tove,
        Vorpal,
    )


def test_jabberwock_constants_importable():
    """All provider constants must be importable."""
    from yanantin.jabberwock import (  # noqa: F401
        JABBERWOCK_PROVIDER,
        RATH_PROVIDER,
        ROOT_BANDERSNATCH_ID,
        TOVE_PROVIDER,
        VORPAL_PROVIDER,
    )


def test_brillig_service_exists():
    """The Brillig resolution service must be importable."""
    from yanantin.jabberwock import Brillig  # noqa: F401

    assert inspect.isclass(Brillig), "Brillig must be a class"


def test_normalize_functions_importable():
    """Normalization functions must be importable."""
    from yanantin.jabberwock import normalize_gimble, register_normalizer  # noqa: F401

    assert callable(normalize_gimble)
    assert callable(register_normalizer)


# -- ROOT_BANDERSNATCH_ID consistency -------------------------------------


def test_root_bandersnatch_consistent_across_imports():
    """ROOT_BANDERSNATCH_ID must be the same value no matter how imported."""
    from yanantin.jabberwock import ROOT_BANDERSNATCH_ID as from_package
    from yanantin.jabberwock.models import ROOT_BANDERSNATCH_ID as from_models

    assert from_package == from_models, (
        "ROOT_BANDERSNATCH_ID differs between package and models imports. "
        "This breaks the provenance chain -- the root entity must have "
        "a single consistent identity."
    )


def test_root_bandersnatch_is_uuid5():
    """ROOT_BANDERSNATCH_ID must be a deterministic uuid5, not random."""
    from uuid import NAMESPACE_DNS, uuid5

    from yanantin.jabberwock.models import ROOT_BANDERSNATCH_ID

    expected = uuid5(NAMESPACE_DNS, "yanantin.jabberwock.root")
    assert ROOT_BANDERSNATCH_ID == expected, (
        f"ROOT_BANDERSNATCH_ID is {ROOT_BANDERSNATCH_ID} but expected "
        f"{expected}. Deterministic ID is required for bootstrap "
        f"idempotence and cross-instance consistency."
    )


# -- Models enforce frozen (immutability) ----------------------------------


_FROZEN_MODELS = [
    ("Jabberwock", {"brillig": "2026-01-01T00:00:00+00:00", "bandersnatch": "00000000-0000-0000-0000-000000000001"}),
    ("Tove", {"wabe": "test", "gimble": "test", "gyre_from": "2026-01-01T00:00:00+00:00", "bandersnatch": "00000000-0000-0000-0000-000000000001", "brillig": "2026-01-01T00:00:00+00:00"}),
    ("Vorpal", {"tulgey": "test", "snicker_snack": "x", "bandersnatch": "00000000-0000-0000-0000-000000000001", "brillig": "2026-01-01T00:00:00+00:00"}),
    ("Rath", {"jabberwock_id": "00000000-0000-0000-0000-000000000001", "borogove_id": "00000000-0000-0000-0000-000000000002", "mimsy": "test", "gyre_from": "2026-01-01T00:00:00+00:00", "bandersnatch": "00000000-0000-0000-0000-000000000001", "brillig": "2026-01-01T00:00:00+00:00"}),
]


@pytest.mark.parametrize("model_name,kwargs", _FROZEN_MODELS, ids=[m[0] for m in _FROZEN_MODELS])
def test_model_frozen(model_name, kwargs):
    """All Jabberwock event models must be frozen (immutable).

    Events don't mutate. This is the correctness invariant of an
    event-sourced system. If any model allows field assignment,
    the append-only contract is broken.
    """
    import yanantin.jabberwock.models as models_module

    cls = getattr(models_module, model_name)
    instance = cls(**kwargs)

    # Try to mutate the first field -- must raise
    first_field = next(iter(cls.model_fields))
    with pytest.raises(ValidationError):
        setattr(instance, first_field, getattr(instance, first_field))


# -- Stored records: extra="allow" (event-sourced forward compat) ----------


_ALLOW_MODELS = [
    ("Jabberwock", {"brillig": "2026-01-01T00:00:00+00:00", "bandersnatch": "00000000-0000-0000-0000-000000000001"}),
    ("Tove", {"wabe": "test", "gimble": "test", "gyre_from": "2026-01-01T00:00:00+00:00", "bandersnatch": "00000000-0000-0000-0000-000000000001", "brillig": "2026-01-01T00:00:00+00:00"}),
    ("Vorpal", {"tulgey": "test", "snicker_snack": "x", "bandersnatch": "00000000-0000-0000-0000-000000000001", "brillig": "2026-01-01T00:00:00+00:00"}),
    ("Rath", {"jabberwock_id": "00000000-0000-0000-0000-000000000001", "borogove_id": "00000000-0000-0000-0000-000000000002", "mimsy": "test", "gyre_from": "2026-01-01T00:00:00+00:00", "bandersnatch": "00000000-0000-0000-0000-000000000001", "brillig": "2026-01-01T00:00:00+00:00"}),
]


@pytest.mark.parametrize("model_name,kwargs", _ALLOW_MODELS, ids=[m[0] for m in _ALLOW_MODELS])
def test_stored_record_extra_allow(model_name, kwargs):
    """Stored records must accept extra fields (extra='allow').

    Event-sourced systems persist events forever. Future versions may
    add fields. Old code must deserialize new records without breaking.
    extra='allow' passes unknown fields through silently.
    """
    import yanantin.jabberwock.models as models_module

    cls = getattr(models_module, model_name)
    extended_kwargs = {**kwargs, "future_field": "should_be_accepted"}
    instance = cls(**extended_kwargs)  # must NOT raise
    assert instance is not None


# -- Resolved views: extra="forbid" (strict snapshots) --------------------


_FORBID_VIEWS = [
    ("Frabjous", {"jabberwock": {"brillig": "2026-01-01T00:00:00+00:00", "bandersnatch": "00000000-0000-0000-0000-000000000001"}, "callooh": "2026-01-01T00:00:00+00:00"}),
    ("MomeResult", {}),
]


@pytest.mark.parametrize("model_name,kwargs", _FORBID_VIEWS, ids=[m[0] for m in _FORBID_VIEWS])
def test_view_extra_forbid(model_name, kwargs):
    """Resolved views must reject extra fields (extra='forbid').

    Views are ephemeral snapshots — never stored, constructed fresh.
    Strict validation catches errors. No forward-compat needed.
    """
    import yanantin.jabberwock.models as models_module

    cls = getattr(models_module, model_name)
    bad_kwargs = {**kwargs, "totally_bogus_field": "should_not_be_accepted"}
    with pytest.raises(ValidationError):
        cls(**bad_kwargs)


# -- Brillig service has expected methods ----------------------------------


def test_brillig_has_required_methods():
    """Brillig must expose all service methods from the spec."""
    from yanantin.jabberwock import Brillig

    required_methods = [
        "bootstrap",
        "beamish",
        "outgrabe",
        "slithy",
        "galumph",
        "uffish",
        "mome_vorpals",
        "claim_mome",
        "whiffling",
        "add_rath",
    ]
    for method_name in required_methods:
        assert hasattr(Brillig, method_name), (
            f"Brillig must have method '{method_name}'. "
            f"See docs/jabberwock-spec.md for the service interface."
        )
        assert callable(getattr(Brillig, method_name)), (
            f"Brillig.{method_name} must be callable."
        )
