"""Continuity guard: the four Linux machines' provider IDs must never change.

Every object's key is uuid5(provider:uri), so 19M objects (2026-11-09) are keyed
through these IDs. A change to how a provider ID is derived, including normalizing
the machine-id through uuid.UUID(), would orphan all of them. The volume-identity
work (docs/design-machine-identity-evidence.md) has to keep these exact values;
the Codex review (finding 3) showed three spellings of one UUID giving three IDs.

Values are the real machine-ids and the provider IDs their walks landed under.
"""

import importlib.util
from pathlib import Path

import pytest

from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector

_spec = importlib.util.spec_from_file_location(
    "refresh_machines", Path(__file__).parents[2] / "scripts" / "refresh_machines.py")
rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rm)

MACHINES = [
    ("WAM-THREADRIPPER WSL", "8ae0edf526f3453ab1abaf04e1c75a4a", "192c0842-b05a-5dd7-b975-28581b8372fb"),
    ("wam-nuc", "e8c598ae711b42b5b963eb35fc946d2b", "2e78dff1-62b1-59f4-982e-3fcd232ca2e7"),
    ("wam-desktop", "e328729faaa04bc1ba3ea69cbdb21870", "a33a049b-66cd-5ce1-b783-8f2c4ae97ae8"),
    ("gazelle", "503227dc8dd2970b17a61e456a5d1a3b", "8a63fa49-639b-5d37-af33-9482e3ff7134"),
]


@pytest.mark.parametrize("name,machine_id,provider", MACHINES, ids=[m[0] for m in MACHINES])
def test_refresh_derives_the_landed_provider(name, machine_id, provider):
    assert str(rm.provider_for(machine_id)) == provider


@pytest.mark.parametrize("name,machine_id,provider", MACHINES, ids=[m[0] for m in MACHINES])
def test_the_collector_derives_the_landed_provider(name, machine_id, provider, tmp_path):
    collector = LinuxFilesystemCollector(tmp_path, machine_id=machine_id)
    assert str(collector.get_provider_id()) == provider
