"""Entry point for ``python -m yanantin.awaq``.

Modes:
    uv run python -m yanantin.awaq              # Scan cairn, render composition graph
    uv run python -m yanantin.awaq --tensor T15 # Show declarations for one tensor
    uv run python -m yanantin.awaq --json       # Output as JSON
    uv run python -m yanantin.awaq --list       # List discovered tensors
"""

from __future__ import annotations

import argparse
import sys

from yanantin.awaq.weaver import (
    discover_tensors,
    render_graph,
    render_json,
    render_tensor_declarations,
    weave_corpus,
)


def main() -> None:
    """Scan tensors and extract composition declarations."""
    parser = argparse.ArgumentParser(
        description="Awaq -- the weaver. Extract composition declarations from tensors.",
    )
    parser.add_argument(
        "--tensor",
        "-t",
        type=str,
        default=None,
        help="Show declarations for a specific tensor (e.g., T15)",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output declarations as JSON",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List discovered tensors without extracting declarations",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        default=None,
        help="Sources to scan (default: all). Available: cairn, ai-honesty",
    )

    args = parser.parse_args()

    if args.list:
        tensors = discover_tensors(sources=args.sources)
        if not tensors:
            print("No tensors found.", file=sys.stderr)
            sys.exit(1)
        print(f"Discovered {len(tensors)} tensors:\n")
        for t in tensors:
            print(f"  {t.tensor_name:6s}  {t.source_name:12s}  {t.path.name}")
        return

    declarations = weave_corpus(sources=args.sources)

    if args.tensor:
        tensor_name = args.tensor.upper() if not args.tensor.startswith("T") else args.tensor
        if args.json:
            filtered = [d for d in declarations if d.source == tensor_name]
            print(render_json(filtered))
        else:
            print(render_tensor_declarations(tensor_name, declarations))
    elif args.json:
        print(render_json(declarations))
    else:
        print(render_graph(declarations))


if __name__ == "__main__":
    main()
