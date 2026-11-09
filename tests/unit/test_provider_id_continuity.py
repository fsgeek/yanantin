"""Continuity guard: the four Linux machines' provider IDs must never change.

Every object's key is uuid5(provider:uri), so 19M objects (2026-11-09) are keyed
through these IDs. A change to how a provider ID is derived, including normalizing
the machine-id through uuid.UUID(), would orphan all of them. The volume-identity
work (docs/design-machine-identity-evidence.md) has to keep these exact values;
the Codex review (finding 3) showed three spellings of one UUID giving three IDs.

The machine-ids here are synthetic: real ones are confidential (systemd, machine-id(5)).
The guard pins the derivation formula, which is what continuity depends on; on
2026-11-09 the same formula reproduced all four real machines' landed provider IDs.
"""

import importlib.util
from pathlib import Path

import pytest

from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector

_spec = importlib.util.spec_from_file_location(
    "refresh_machines", Path(__file__).parents[2] / "scripts" / "refresh_machines.py")
rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rm)

MACHINES = [  # labels name the real machines whose derivation this mirrors
    ("WAM-THREADRIPPER WSL", "0a1b2c3d4e5f60718293a4b5c6d7e8f9", "54d0b414-e2da-504b-ae99-d2455a0fd5fd"),
    ("wam-nuc", "1b2c3d4e5f60718293a4b5c6d7e8f90a", "43e17b99-254c-571f-bdb2-85a6afa4ff0c"),
    ("wam-desktop", "2c3d4e5f60718293a4b5c6d7e8f90a1b", "15b1069f-55a5-5ec3-995b-efda9c2769bb"),
    ("gazelle", "3d4e5f60718293a4b5c6d7e8f90a1b2c", "99416a06-d231-57d4-a94f-e62993e6cb90"),
]


@pytest.mark.parametrize("name,machine_id,provider", MACHINES, ids=[m[0] for m in MACHINES])
def test_refresh_derives_the_landed_provider(name, machine_id, provider):
    assert str(rm.provider_for(machine_id)) == provider


@pytest.mark.parametrize("name,machine_id,provider", MACHINES, ids=[m[0] for m in MACHINES])
def test_the_collector_derives_the_landed_provider(name, machine_id, provider, tmp_path):
    collector = LinuxFilesystemCollector(tmp_path, machine_id=machine_id)
    assert str(collector.get_provider_id()) == provider
