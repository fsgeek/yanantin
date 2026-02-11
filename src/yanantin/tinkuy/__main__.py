"""Entry point for ``python -m yanantin.tinkuy``.

Modes:
    uv run python -m yanantin.tinkuy          # Print audit report
    uv run python -m yanantin.tinkuy --check   # Run succession check, exit non-zero on failure
"""

from __future__ import annotations

import sys
from pathlib import Path

from yanantin.tinkuy.audit import render_report, survey_codebase
from yanantin.tinkuy.succession import check_succession


def main() -> None:
    """Survey the codebase and print the audit report, or run succession check."""
    # Default: assume project root is three levels up from this file
    # (src/yanantin/tinkuy/__main__.py -> project root)
    project_root = Path(__file__).resolve().parent.parent.parent.parent

    args = sys.argv[1:]

    # Parse --check flag
    check_mode = "--check" in args
    remaining = [a for a in args if a != "--check"]

    # Allow override via positional argument
    if remaining:
        project_root = Path(remaining[0]).resolve()

    if not project_root.is_dir():
        print(f"Error: {project_root} is not a directory", file=sys.stderr)
        sys.exit(1)

    if check_mode:
        # Succession check: compare blueprint to reality
        issues = check_succession(project_root)
        if issues:
            print("Succession check FAILED:", file=sys.stderr)
            for issue in issues:
                print(f"  - {issue}", file=sys.stderr)
            sys.exit(1)
        else:
            print("Succession check passed. Blueprint matches reality.")
            sys.exit(0)
    else:
        # Default: print audit report
        report = survey_codebase(project_root)
        print(render_report(report))


if __name__ == "__main__":
    main()
