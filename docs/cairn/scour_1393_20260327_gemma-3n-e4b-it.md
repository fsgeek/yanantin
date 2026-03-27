<!-- Chasqui Scour Tensor
     Run: 1393
     Model: google/gemma-3n-e4b-it (Google: Gemma 3n 4B)
     Target: src/yanantin/chasqui
     Scope: introspection
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 18515, 'completion_tokens': 1782, 'total_tokens': 20297, 'cost': 0.00044158, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00044158, 'upstream_inference_prompt_cost': 0.0003703, 'upstream_inference_completions_cost': 7.128e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-27T11:13:28.867000+00:00
     GenerationID: gen-1774609929-B2VtgBtRVxe6Kfrw8REi
-->

```python
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from yanantin.chasqui.coordinator import (
    CAIRN_DIR,
    PROJECT_ROOT,
    dispatch_investigate,
    dispatch_many,
    dispatch_respond,
    dispatch_scour,
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
        "--scour", type=str, default=None,
        help="Scour a specific target (file, directory, tensor glob)",
    )
    parser.add_argument(
        "--scope", type=str, default="introspection",
        choices=["introspection", "external", "tensor", "synthesis"],
        help="Scope for scouring (default: introspection)",
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
        "--analyze", action="store_true",
        help="Analyze scout corpus: cross-model topology detection",
    )
    parser.add_argument(
        "--investigate", type=int, nargs="?", const=5, default=None,
        metavar="N",
        help="Investigate N open questions from the analyst (default: 5)",
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

    # ── Analyze mode ────────────────────────────────────────────────
    if args.analyze:
        from yanantin.chasqui.analyst import analyze, render_report
        from yanantin.chasqui.gleaner import extract_claims_from_cairn

        claims = extract_claims_from_cairn(CAIRN_DIR, pattern="scout_*.md", max_reports=2000)
        report = analyze(claims)
        if args.json:
            print(json.dumps({
                "total_claims": report.total_claims_input,
                "after_filter": report.claims_after_filter,
                "garbage_filtered": report.garbage_filtered,
                "clusters": len(report.clusters),
                "topological_insights": len(report.topological_insights),
                "models": len(report.model_profiles),
                "top_insights": [
                    {
                        "claim": g.representative[:200],
                        "models": g.model_count,
                        "type": g.claim_type,
                        "confidence": round(g.avg_confidence, 3),
                    }
                    for g in report.topological_insights[:20]
                ],
            }, indent=2, default=str))
        else:
            print(f"# Investigation Results ({len(results)} questions)\n")
            for r in results:
                if "error" in r:
                    print(f"Error: {r['error']}", file=sys.stderr)
                    continue

                verdict_marker = {
                    "CONFIRMED": "+", "DENIED": "!", "INDETERMINATE": "?"
                }.get(r["verdict"], "?")

                print(f"[ {verdict_marker} ] {r['verdict']}")
                print(f"    Question by {r['source_model']} ({r['model_name']})")
                print(f"    {r['claim']}")
                print(f"        File: {r['file_path']}")
                print(f"        Cairn: {r['cairn_path']}")
        return

    # ── Verify mode ────────────────────────────────────────────────
    if args.verify is not None:
        asyncio.run(dispatch_verify_cairn(
            max_claims=args.verify,
            seed=args.seed,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        ))
        return

    # ── Scour mode ──────────────────────────────────────────────────
    if args.scour:
        from yanantin.chasqui.scourer import dispatch_scour

        asyncio.run(dispatch_scour(
            args.scour,
            scope=args.scope,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        ))
        return

    # ── Respond mode ────────────────────────────────────────────────
    if args.respond:
        from yanantin.chasqui.respond import dispatch_respond

        asyncio.run(dispatch_respond(
            args.respond,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        ))
        return
```