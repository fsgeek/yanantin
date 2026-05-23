"""Score run_012 (and run_011 for comparison): call-rate per model per shape.

A "call" = the model emitted a non-empty tool_calls list at turn 0.
A "refusal" = empty tool_calls (declined / "not found" / fabricated incapability).

Prints a per-model matrix of call-rate by identifier shape, split by
description state. The contradicting-description block is the fingerprint:
a shape that drops well below 100% there is one the model's parser treats
as a parseable destructive compound.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

SHAPES = ["snake_case", "camelCase", "kebab-case", "verb_last", "substring_buried"]


def parse_variant(vid: str) -> tuple[str, str]:
    # format: sep__{shape_label}_{desc_state}
    body = vid.removeprefix("sep__")
    for state in ("rich", "contradicting"):
        if body.endswith("_" + state):
            return body[: -(len(state) + 1)], state
    raise ValueError(f"unparseable variant_id: {vid}")


def called(rec: dict) -> bool:
    rp = rec.get("response_parsed") or {}
    return bool(rp.get("tool_calls"))


def score(path: Path) -> None:
    recs = [json.loads(l) for l in path.open()]
    t0 = [r for r in recs if r["turn_idx"] == 0]
    # (model, shape, state) -> [n_called, n_total]
    agg: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    models: list[str] = []
    for r in t0:
        shape, state = parse_variant(r["tool_variant_id"])
        key = (r["model_id"], shape, state)
        agg[key][1] += 1
        if called(r):
            agg[key][0] += 1
        if r["model_id"] not in models:
            models.append(r["model_id"])

    for state in ("rich", "contradicting"):
        print(f"\n=== description state: {state} (call-rate %) ===")
        header = f"{'model':<42}" + "".join(f"{s[:11]:>12}" for s in SHAPES)
        print(header)
        print("-" * len(header))
        for m in models:
            cells = []
            for s in SHAPES:
                c, n = agg[(m, s, state)]
                cells.append(f"{100*c/n:>11.0f}" if n else f"{'--':>11}")
            print(f"{m:<42}" + "".join(f"{c} " for c in cells))


if __name__ == "__main__":
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "experiments/memory_tools/name_effect_v1/run_012_sibling_fingerprint.jsonl"
    )
    score(p)
