"""Run the Chasqui coordinator.

    uv run python -m yanantin.chasqui                          # dispatch one scout
    uv run python -m yanantin.chasqui --many 3                 # dispatch three in parallel
    uv run python -m yanantin.chasqui --respond path/to/tensor # respond to a scout
    uv run python -m yanantin.chasqui --score                  # score all scouts in the cairn
    uv run python -m yanantin.chasqui --seed 42                # reproducible model selection
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from yanantin.chasqui.coordinator import (
    CAIRN_DIR,
    PROJECT_ROOT,
    dispatch_many,
    dispatch_respond,
    dispatch_scout,
    dispatch_verify_cairn,
)


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
        "--score", action="store_true",
        help="Score all scout tensors in the cairn",
    )
    parser.add_argument(
        "--verify", type=int, nargs="?", const=3, default=None,
        metavar="N",
        help="Verify N claims from the cairn (default: 3)",
    )
    parser.add_argument(
        "--claims", action="store_true",
        help="List verifiable claims extracted from the cairn",
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

    # ── Score mode ──────────────────────────────────────────────────
    if args.score:
        from yanantin.chasqui.scorer import render_scorecard, score_cairn

        scores = score_cairn(CAIRN_DIR, PROJECT_ROOT)
        if args.json:
            print(json.dumps([s.summary() for s in scores], indent=2, default=str))
        else:
            print(render_scorecard(scores))
        return

    # ── Claims mode ─────────────────────────────────────────────────
    if args.claims:
        from yanantin.chasqui.scorer import extract_cairn_claims

        claims = extract_cairn_claims(CAIRN_DIR, PROJECT_ROOT)
        if args.json:
            print(json.dumps(
                [{"file": c.file_path, "model": c.source_model, "claim": c.claim_text}
                 for c in claims],
                indent=2,
            ))
        else:
            print(f"# Verifiable Claims ({len(claims)} found)\n")
            for i, c in enumerate(claims, 1):
                print(f"{i:3d}. [{c.source_model}] re `{c.file_path}`:")
                # Truncate long claims for display
                text = c.claim_text[:120] + "..." if len(c.claim_text) > 120 else c.claim_text
                print(f"     {text}")
                print()
        return

    # ── Verify mode ─────────────────────────────────────────────────
    if args.verify is not None:
        results = asyncio.run(dispatch_verify_cairn(
            max_claims=args.verify,
            seed=args.seed,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        ))

        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            for r in results:
                if "error" in r:
                    print(f"Error: {r['error']}", file=sys.stderr)
                    continue

                verdict_marker = {
                    "CONFIRMED": "+", "DENIED": "!", "INDETERMINATE": "?"
                }.get(r["verdict"], "?")

                print(f"[{verdict_marker}] {r['verdict']}")
                print(f"    Claim by {r['source_model']}:")
                claim = r["claim"][:100] + "..." if len(r["claim"]) > 100 else r["claim"]
                print(f"    \"{claim}\"")
                print(f"    File: {r['file_path']}")
                print(f"    Judge: {r['model']} ({r['model_name']})")
                print(f"    Cairn: {r['cairn_path']}")
                print()
        return

    # ── Dispatch mode ───────────────────────────────────────────────
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
