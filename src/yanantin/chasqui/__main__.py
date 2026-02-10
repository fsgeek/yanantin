"""Run the Chasqui coordinator.

    uv run python -m yanantin.chasqui                          # dispatch one scout
    uv run python -m yanantin.chasqui --many 3                 # dispatch three in parallel
    uv run python -m yanantin.chasqui --respond path/to/tensor # respond to a scout
    uv run python -m yanantin.chasqui --seed 42                # reproducible model selection
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from yanantin.chasqui.coordinator import dispatch_many, dispatch_respond, dispatch_scout


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chasqui — dispatch scout messengers into the codebase",
    )
    parser.add_argument(
        "--many", type=int, default=None,
        help="Dispatch N scouts in parallel (default: 1)",
    )
    parser.add_argument(
        "--respond", type=str, default=None,
        help="Respond to a previous scout's tensor (path to .md file)",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Seed for reproducible model selection",
    )
    parser.add_argument(
        "--max-tokens", type=int, default=4000,
        help="Max tokens for scout response (default: 4000)",
    )
    parser.add_argument(
        "--temperature", type=float, default=0.7,
        help="Sampling temperature (default: 0.7)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output results as JSON",
    )
    args = parser.parse_args()

    kwargs = {
        "seed": args.seed,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
    }

    if args.respond:
        results = [asyncio.run(dispatch_respond(tensor_path=args.respond, **kwargs))]
    elif args.many:
        results = asyncio.run(dispatch_many(n=args.many, **kwargs))
    else:
        results = [asyncio.run(dispatch_scout(**kwargs))]

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        for r in results:
            if "error" in r:
                print(f"Error: {r['error']}", file=sys.stderr)
                continue

            mode = r.get("mode", "scout")
            if mode == "respond":
                print(f"Response #{r['run_number']}")
                print(f"  To:     {r['responding_to']}")
                print(f"  From:   {r['previous_model']}")
            else:
                print(f"Scout #{r['run_number']}")

            print(f"  Model:  {r['model']} ({r['model_name']})")
            print(f"  Cost:   ${r['cost_per_million']:.4f}/M tokens")
            print(f"  Pool:   {r['pool_size']} models available")
            print(f"  Output: {r['content_length']} chars")
            print(f"  Cairn:  {r['cairn_path']}")
            print()


if __name__ == "__main__":
    main()
