"""Every package imports on its own, in a fresh interpreter.

Found 2026-10-26: `import yanantin.machine` failed with a circular import unless
yanantin.collector had been imported first (collector/__init__ re-exported
machine.linux eagerly, and machine.linux imports from the collector package).
A test suite imports everything in some order, so it never saw this.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

MODULES = [
    "yanantin.machine",
    "yanantin.machine.base",
    "yanantin.machine.linux",
    "yanantin.collector",
    "yanantin.collector.storage.local.linux.collector",
    "yanantin.recorder",
    "yanantin.core.aql",
    "yanantin.recorder.storage.objects_find",
    "yanantin.eval.finding_chains",
]


@pytest.mark.parametrize("module", MODULES)
def test_imports_alone(module):
    proc = subprocess.run([sys.executable, "-c", f"import {module}"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-800:]


def test_collector_still_re_exports_machine_names():
    proc = subprocess.run(
        [sys.executable, "-c", "from yanantin.collector import MachineConfigCollector, collect_machine_config"],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-800:]
