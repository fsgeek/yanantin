"""Red bar (Phase 1 Task 8): every recorder package must import standalone.

The recorder<->collector circular import meant that importing a concrete
recorder package in a FRESH interpreter failed unless ``yanantin.collector``
had been imported first (which primed ``sys.modules``).

A recorder legitimately depends on the collector's *data models*, but the
back-edge was ``collector/__init__`` eagerly reaching FORWARD into the
concrete domain recorders. These tests run each import in its own
subprocess (a genuinely fresh interpreter, empty ``sys.modules``) with NO
prior ``import yanantin.collector`` so the cycle cannot be masked.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

# Each entry pairs the recorder package with a concrete recorder symbol it
# must fully expose. A *partially initialized* module (the cycle symptom)
# raises ImportError on the submodule import OR leaves the symbol unbound,
# so asserting the symbol resolves catches the half-initialized failure mode
# that a bare ``import`` could mask.
RECORDER_PACKAGES = [
    ("yanantin.recorder.storage.local.linux", "FilesystemRecorder"),
    ("yanantin.recorder.storage.cloud.dropbox", "DropboxRecorder"),
    ("yanantin.recorder.activity.linux", "FsEventRecorder"),
    ("yanantin.recorder.storage.local.checksum", "ChecksumRecorder"),
    ("yanantin.recorder.semantic.openrouter", "OpenRouterFactRecorder"),
]


@pytest.mark.parametrize("module,symbol", RECORDER_PACKAGES)
def test_recorder_imports_standalone(module: str, symbol: str) -> None:
    """Importing the recorder package alone must not raise ImportError.

    Each runs in a fresh interpreter (its own subprocess, empty
    ``sys.modules``) with NO prior ``import yanantin.collector`` so the
    cycle cannot be masked by a primed module cache. The probe also asserts
    a concrete recorder symbol resolves — a partially initialized module
    (the cycle symptom) would leave it unbound even if the package shell
    imported.
    """
    probe = (
        f"import {module} as m\n"
        f"assert hasattr(m, {symbol!r}), "
        f"'{module} imported but {symbol} did not bind (partially initialized)'\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"fresh-interpreter import of {module} failed:\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
