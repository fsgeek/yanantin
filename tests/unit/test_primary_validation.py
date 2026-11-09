"""0.3.1 step 3 (Codex review, finding 9): an empty, malformed or all-zero
machine-id must never become a provider. Before this, an empty file produced a
provider, and a machine without /etc/machine-id silently got a hostname-derived
identity that a rename would change."""

import importlib.util
from pathlib import Path

import pytest

from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector
from yanantin.machine.base import _get_machine_id

_spec = importlib.util.spec_from_file_location(
    "refresh_machines", Path(__file__).parents[2] / "scripts" / "refresh_machines.py")
rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rm)

GOOD = "8ae0edf526f3453ab1abaf04e1c75a4a"
BAD = ["", "   ", "0" * 32, "not-a-machine-id", GOOD[:-1], GOOD.upper() + "x"]


def test_the_reader_returns_a_valid_id(tmp_path):
    f = tmp_path / "machine-id"
    f.write_text(GOOD + "\n")
    assert _get_machine_id(f) == GOOD


@pytest.mark.parametrize("content", BAD)
def test_the_reader_refuses_invalid_ids(tmp_path, content):
    f = tmp_path / "machine-id"
    f.write_text(content)
    with pytest.raises(RuntimeError, match="machine-id"):
        _get_machine_id(f)


def test_the_reader_refuses_a_missing_file_instead_of_guessing(tmp_path):
    with pytest.raises(RuntimeError, match="will not guess"):
        _get_machine_id(tmp_path / "absent")


@pytest.mark.parametrize("machine_id", BAD)
def test_the_collector_refuses_invalid_explicit_ids(tmp_path, machine_id):
    with pytest.raises(ValueError, match="machine-id"):
        LinuxFilesystemCollector(tmp_path, machine_id=machine_id)


@pytest.mark.parametrize("machine_id", BAD)
def test_refresh_never_derives_a_provider_from_an_invalid_id(machine_id):
    assert rm.provider_from_machine_id(machine_id) is None
    assert rm.provider_from_machine_id(GOOD) == rm.provider_for(GOOD)
