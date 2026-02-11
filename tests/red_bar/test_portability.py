"""Red-bar test: No hardcoded absolute paths in test files.

Tests must work in CI, not just on the developer's machine. Any test
that hardcodes absolute home directory paths will pass locally and fail
in GitHub Actions. A flatworm caught this when CI broke after the
Tinkuy tests were added.

The fix: derive paths from __file__ or use pytest fixtures.
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_no_hardcoded_home_paths_in_tests():
    """No test file should contain hardcoded absolute home directory paths.

    Tests run in CI where the checkout path is different. Paths
    must be derived from __file__ or from pytest fixtures like
    tmp_path. This catches the "works on my machine" anti-pattern.
    """
    test_dirs = [
        PROJECT_ROOT / "tests" / "unit",
        PROJECT_ROOT / "tests" / "integration",
        PROJECT_ROOT / "tests" / "red_bar",
    ]

    # This file is the guard — it needs to describe the pattern it catches
    self_path = Path(__file__).resolve()
    hardcoded_pattern = re.compile(r'(?<![_\w])/home/\w+/')
    violations = []

    for test_dir in test_dirs:
        if not test_dir.is_dir():
            continue
        for path in sorted(test_dir.glob("*.py")):
            if path.resolve() == self_path:
                continue  # The guard doesn't guard itself
            content = path.read_text(encoding="utf-8")
            for i, line in enumerate(content.splitlines(), 1):
                # Skip comments that explain the rule
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if hardcoded_pattern.search(line):
                    violations.append(f"{path.name}:{i}: {stripped}")

    assert not violations, (
        f"Hardcoded home paths found in test files (will break in CI):\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_no_hardcoded_home_paths_in_source():
    """No source file should contain hardcoded /home/ paths.

    Source code must be portable. Configuration belongs in config
    files, not in Python source.
    """
    src_dir = PROJECT_ROOT / "src" / "yanantin"

    hardcoded_pattern = re.compile(r'(?<![_\w])/home/\w+/')
    violations = []

    for path in sorted(src_dir.rglob("*.py")):
        content = path.read_text(encoding="utf-8")
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if hardcoded_pattern.search(line):
                rel = path.relative_to(src_dir)
                violations.append(f"{rel}:{i}: {stripped}")

    assert not violations, (
        f"Hardcoded home paths found in source files:\n"
        + "\n".join(f"  {v}" for v in violations)
    )
