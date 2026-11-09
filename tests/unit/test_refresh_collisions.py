"""Detector 1 (docs/design-machine-identity-evidence.md): within one refresh,
two aliases that yield the same provider are either one machine (walk it
once) or a collision (refuse the second). Keyed landing replaces, so a
collision walked twice would overwrite one filesystem's records with the
other's (Codex review, finding 1)."""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "refresh_machines", Path(__file__).parents[2] / "scripts" / "refresh_machines.py")
rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rm)


def test_distinct_providers_all_walk():
    walk, skipped = rm.plan_walks([("a", "p1", "10.0.0.1:22"), ("b", "p2", "10.0.0.2:22")])
    assert walk == ["a", "b"] and skipped == []


def test_aliases_of_one_endpoint_walk_once_and_name_the_others():
    # Tony's ubuntu18/20/22/24: one machine at 192.168.111.150.
    walk, skipped = rm.plan_walks([
        ("ubuntu24", "p1", "192.168.111.150:22"), ("ubuntu22", "p1", "192.168.111.150:22")])
    assert walk == ["ubuntu24"]
    assert skipped == [{"host": "ubuntu22", "skipped": "same machine as ubuntu24",
                        "detail": "same provider p1 and same ssh endpoint 192.168.111.150:22"}]


def test_same_provider_at_different_endpoints_is_a_collision():
    walk, skipped = rm.plan_walks([("vm1", "p1", "10.0.0.5:22"), ("vm2", "p1", "10.0.0.6:22")])
    assert walk == ["vm1"]
    assert skipped[0]["host"] == "vm2" and skipped[0]["failed"] == "identity_collision"
    assert "vm1" in skipped[0]["detail"] and "p1" in skipped[0]["detail"]
