"""The nightly refresh must not land a walk under an identity other than the one
whose cutoff it used, and one host's timeout must not abort the other hosts.

Codex review of docs/design-machine-identity-evidence.md (2026-11-04), findings 6
and 14: refresh read the cutoff from one identity read, then accepted whatever
provider the walk's manifest reported.
"""

import importlib.util
import subprocess
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "refresh_machines", Path(__file__).parents[2] / "scripts" / "refresh_machines.py")
rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rm)


def test_a_manifest_from_the_expected_provider_is_accepted():
    assert rm.identity_mismatch("abc", {"provider_id": "abc"}) is None


def test_a_manifest_from_another_provider_is_rejected():
    reason = rm.identity_mismatch("abc", {"provider_id": "xyz", "machine_id": "m2"})
    assert reason is not None
    assert "xyz" in reason and "abc" in reason


def test_a_manifest_without_a_provider_is_rejected():
    assert rm.identity_mismatch("abc", {}) is not None


def test_one_hosts_timeout_is_reported_and_does_not_raise():
    def hangs(host):
        raise subprocess.TimeoutExpired(cmd="ssh", timeout=60)
    assert rm.per_host(hangs, "gazelle") == {"host": "gazelle", "failed": "timeout",
                                              "detail": "ssh timed out after 60 s"}


def test_a_normal_result_passes_through():
    assert rm.per_host(lambda h: {"host": h, "landed": 1}, "nuc") == {"host": "nuc", "landed": 1}
