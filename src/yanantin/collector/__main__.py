"""Run the Yanantin collector.

    uv run python -m yanantin.collector                    # show machine config
    uv run python -m yanantin.collector --json             # JSON output
    uv run python -m yanantin.collector --record           # collect and record to Apacheta
"""

from __future__ import annotations

import argparse

from yanantin.collector.machine_config import (
    collect_and_record,
    collect_machine_config,
    render_machine_config,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collector \u2014 bring human-side data into Yanantin",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--record", action="store_true", help="Record snapshot to Apacheta")
    parser.add_argument(
        "--backend", choices=["memory"], default="memory",
        help="Storage backend for --record (default: memory)",
    )
    args = parser.parse_args()

    # Collect
    data = collect_machine_config()

    if args.json:
        print(data.model_dump_json(indent=2))
    else:
        # Greeting + display
        print()
        print("  Yanantin Collector")
        print("  " + "\u2500" * 40)
        print()
        print("  Machine Configuration")
        print("  " + "\u2500" * 25)
        print(render_machine_config(data))
        print()

    if args.record:
        from yanantin.apacheta.backends.memory import InMemoryBackend

        backend = InMemoryBackend()
        tensor_id = collect_and_record(backend)
        if args.json:
            import json

            print(json.dumps({"recorded": True, "tensor_id": str(tensor_id)}))
        else:
            print(f"  Recorded as tensor {tensor_id}")
            print()
    elif not args.json:
        print("  Use --json for machine-readable output.")
        print("  Use --record to persist this snapshot to Apacheta.")
        print()


if __name__ == "__main__":
    main()
