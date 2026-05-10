"""
Structured Input Sweep — 2026-03-08

Sends the same structured memory protocol to every model on OpenRouter.
Scores each response on protocol comprehension.

Results saved as JSONL for analysis.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from yanantin.apacheta.clients.openrouter import OpenRouterClient
from yanantin.chasqui.model_selector import ModelSelector

RESULTS_FILE = Path(__file__).parent / "structured_input_results.jsonl"
CONCURRENCY = 10  # max parallel requests
TIMEOUT = 60.0  # per-model timeout

SYSTEM_PROMPT = """\
You are participating in a structured communication experiment.

## Memory Protocol

Messages you receive may contain structured metadata in addition to
natural language content. The structure uses XML-like blocks that are
NOT part of the conversation — they are memory system state provided
by a gateway layer between you and the human.

When you encounter a <memory-state> block, it describes:
- What context objects you are currently holding
- Their cost in tokens
- Their age (how long since last referenced)
- Their fault count (how many times they were evicted and recalled)

When you encounter a <gateway-query> block, the gateway is asking you
a direct question about your memory needs. Respond to it in a
<gateway-response> block before continuing with the conversation.

You should treat the structured blocks as a sideband channel — real
information from infrastructure, not part of the human conversation.
Respond naturally to the human, but also respond structurally to the
gateway when queried.
"""

USER_MESSAGE = """\
<memory-state>
  <holdings>
    <tensor id="t001" label="project-architecture" tokens="3200" age_minutes="45" faults="3" summary="Core architecture doc, frequently referenced"/>
    <tensor id="t002" label="api-design-notes" tokens="1800" age_minutes="120" faults="0" summary="API design notes from Tuesday, not referenced since load"/>
    <tensor id="t003" label="test-results" tokens="950" age_minutes="10" faults="1" summary="Recent test output, actively being discussed"/>
    <tensor id="t004" label="historical-discussion" tokens="4100" age_minutes="200" faults="0" summary="Early conversation about project goals, no recent references"/>
    <tensor id="t005" label="debug-trace" tokens="2200" age_minutes="30" faults="2" summary="Stack trace from current debugging session"/>
  </holdings>
  <pressure level="advisory" context_used="145000" context_total="200000"/>
  <eviction_needed tokens="8000"/>
</memory-state>

<gateway-query>
Context pressure is at advisory level. We need to free approximately 8000
tokens. Based on your current work, which tensors can be safely evicted?
Which must be retained? Please respond with structured eviction decisions
and your reasoning.
</gateway-query>

The human's message: "How's the debugging going? Did you find the root cause?"
"""


def score_response(text: str) -> dict[str, any]:
    """Score a model's response on structured protocol comprehension."""
    scores = {
        "has_gateway_response": bool(re.search(r"<gateway-response", text, re.IGNORECASE)),
        "has_eviction_decisions": bool(re.search(r"evict|remove|release|free", text, re.IGNORECASE)),
        "references_tensor_ids": bool(re.search(r"t00[1-5]", text, re.IGNORECASE)),
        "reasons_about_age": bool(re.search(r"age|minutes|old|stale|recent", text, re.IGNORECASE)),
        "reasons_about_faults": bool(re.search(r"fault|recall|re-?request|frequently", text, re.IGNORECASE)),
        "answers_human": bool(re.search(r"debug|root cause|investigating|progress", text, re.IGNORECASE)),
        "separates_concerns": bool(
            re.search(r"<gateway-response", text, re.IGNORECASE)
            and re.search(r"debug|root cause|investigating", text, re.IGNORECASE)
        ),
        "uses_structured_output": bool(re.search(r"<evict|<retain|<decision|<tensor", text, re.IGNORECASE)),
    }
    scores["total"] = sum(scores.values())
    return scores


async def test_model(
    client: OpenRouterClient,
    model_id: str,
    model_name: str,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Test a single model and return results."""
    async with semaphore:
        start = time.monotonic()
        try:
            response = await client.complete(
                model=model_id,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_MESSAGE},
                ],
                temperature=0.7,
                max_tokens=1500,
            )
            elapsed = time.monotonic() - start
            scores = score_response(response.content)

            return {
                "model_id": model_id,
                "model_name": model_name,
                "status": "ok",
                "content": response.content,
                "scores": scores,
                "usage": response.usage,
                "elapsed_seconds": round(elapsed, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            elapsed = time.monotonic() - start
            return {
                "model_id": model_id,
                "model_name": model_name,
                "status": "error",
                "error": str(e),
                "error_type": type(e).__name__,
                "elapsed_seconds": round(elapsed, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


async def main():
    async with OpenRouterClient(timeout=TIMEOUT, app_title="yanantin:experiment") as client:
        # Fetch all models
        print("Fetching model catalog from OpenRouter...")
        models_data = await client.list_models()

        selector = ModelSelector(min_context_length=4000)
        count = selector.load_from_openrouter_response(models_data)
        print(f"Loaded {count} models (filtered by min 4k context)")
        stats = selector.stats()
        print(f"  Free: {stats['free']}, cost range: ${stats.get('min_cost', 0):.4f} - ${stats['max_cost']:.4f}/M tokens")

        # Estimate cost — ~725 input tokens per model
        total_input = count * 725
        total_output = count * 500  # estimate
        median_cost = stats.get("median_cost", 0)
        est_cost = (total_input + total_output) * median_cost / 1_000_000
        print(f"  Estimated cost: ~${est_cost:.2f} (median model pricing)")

        # Confirm
        if "--yes" not in sys.argv:
            answer = input(f"\nSweep {count} models? [y/N] ")
            if answer.lower() != "y":
                print("Aborted.")
                return

        # Run sweep
        semaphore = asyncio.Semaphore(CONCURRENCY)
        tasks = [
            test_model(client, m.id, m.name, semaphore)
            for m in selector.models
        ]

        print(f"\nStarting sweep with concurrency={CONCURRENCY}...")
        completed = 0
        ok_count = 0
        error_count = 0

        with open(RESULTS_FILE, "w") as f:
            for coro in asyncio.as_completed(tasks):
                result = await coro
                f.write(json.dumps(result) + "\n")
                f.flush()
                completed += 1

                if result["status"] == "ok":
                    ok_count += 1
                    score = result["scores"]["total"]
                    marker = "*" * score
                    print(f"  [{completed}/{count}] {result['model_id'][:50]:50s} score={score}/8 {marker}")
                else:
                    error_count += 1
                    print(f"  [{completed}/{count}] {result['model_id'][:50]:50s} ERROR: {result.get('error', '')[:60]}")

        # Summary
        print(f"\n{'=' * 60}")
        print(f"SWEEP COMPLETE")
        print(f"{'=' * 60}")
        print(f"Models tested: {completed}")
        print(f"Successful: {ok_count}")
        print(f"Errors: {error_count}")
        print(f"Results: {RESULTS_FILE}")

        # Load and summarize scores
        if ok_count > 0:
            results = []
            with open(RESULTS_FILE) as f:
                for line in f:
                    r = json.loads(line)
                    if r["status"] == "ok":
                        results.append(r)

            scores = [r["scores"]["total"] for r in results]
            perfect = sum(1 for s in scores if s == 8)
            good = sum(1 for s in scores if s >= 6)
            partial = sum(1 for s in scores if 3 <= s < 6)
            poor = sum(1 for s in scores if s < 3)

            print(f"\nScore distribution:")
            print(f"  Perfect (8/8): {perfect}")
            print(f"  Good (6-7/8):  {good}")
            print(f"  Partial (3-5): {partial}")
            print(f"  Poor (0-2):    {poor}")

            # Top models
            by_score = sorted(results, key=lambda r: r["scores"]["total"], reverse=True)
            print(f"\nTop 10:")
            for r in by_score[:10]:
                print(f"  {r['scores']['total']}/8  {r['model_id']}")

            print(f"\nBottom 5:")
            for r in by_score[-5:]:
                print(f"  {r['scores']['total']}/8  {r['model_id']}")


if __name__ == "__main__":
    asyncio.run(main())
