"""CLI smoke test for `python -m yanantin.collector`.

Characterization test (Phase 1 Task 5): runs a collect+store command end-to-end
through the module entry point with NO live DB (--store memory). Locks the CLI's
exit-0 behavior across the __main__ repoint onto the canonical stack.
"""

import subprocess
import sys


def test_synthetic_fs_to_memory_store_runs():
    r = subprocess.run(
        [sys.executable, "-m", "yanantin.collector", "synthetic", "fs", "5",
         "--store", "memory"],
        capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, r.stderr
    assert "Stored" in r.stdout, r.stdout
