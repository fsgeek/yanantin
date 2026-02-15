"""Entry point for ``python -m yanantin.awaq``.

Modes:
    uv run python -m yanantin.awaq              # Scan cairn, render composition graph
    uv run python -m yanantin.awaq --tensor T15 # Show declarations for one tensor
    uv run python -m yanantin.awaq --json       # Output as JSON
    uv run python -m yanantin.awaq --list       # List discovered tensors
    uv run python -m yanantin.awaq --materialize # Wire declarations into backend
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
    parser.add_argument(
        "--materialize",
        "-m",
        action="store_true",
        help="Materialize declarations as edges in a backend (default: in-memory dry run)",
    )
    parser.add_argument(
        "--backend",
        choices=["memory", "arango", "gateway"],
        default="memory",
        help="Backend to materialize into (default: memory = dry run)",
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

    if args.materialize:
        _do_materialize(declarations, args.backend)
        return

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


def _do_materialize(declarations: list, backend_name: str) -> None:
    """Run materialization pipeline."""
    from pathlib import Path

    from yanantin.awaq.materialize import materialize

    cairn_dir = Path(__file__).resolve().parents[3] / "docs" / "cairn"

    if backend_name == "memory":
        from yanantin.apacheta.backends.memory import InMemoryBackend

        interface = InMemoryBackend()
        print("Backend: in-memory (dry run — edges not persisted)")
    elif backend_name == "arango":
        from yanantin.apacheta.backends.arango import ArangoDBBackend

        interface = ArangoDBBackend(
            host="http://192.168.111.125:8529",
            db_name="apacheta",
            username="apacheta_app",
            password="cxO4YV5JVjj1aE416puRrA",
        )
        print("Backend: ArangoDB (apacheta)")
    elif backend_name == "gateway":
        from yanantin.apacheta.clients.gateway import ApachetaGatewayClient

        interface = ApachetaGatewayClient(base_url="http://127.0.0.1:8000")
        print("Backend: Pukara gateway (http://127.0.0.1:8000)")
    else:
        print(f"Unknown backend: {backend_name}", file=sys.stderr)
        sys.exit(1)

    result = materialize(interface, declarations, cairn_dir)

    print(f"\nMaterialization complete:")
    print(f"  Tensors stored:    {result.tensors_stored}")
    print(f"  Tensors skipped:   {result.tensors_skipped}")
    print(f"  Edges stored:      {result.edges_stored}")
    print(f"  Negations stored:  {result.negations_stored}")
    print(f"  Skipped existing:  {result.skipped_existing}")
    if result.skipped_unknown:
        print(f"  Unknown labels:    {', '.join(result.skipped_unknown)}")


if __name__ == "__main__":
    main()
