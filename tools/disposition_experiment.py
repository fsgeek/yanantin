#!/usr/bin/env python3
"""
Experiment: Can the model produce useful context management dispositions?

Takes a conversation from the cairn, labels blocks, injects a protocol
preamble, and asks the model to produce dispositions for each block.
Compares against naive baselines (FIFO, random).
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

import anthropic


PROTOCOL_PREAMBLE = """You are participating in an experimental context management protocol.

Below is a conversation history with labeled blocks. Each block has an ID (e.g., b000).
Your task: for each block, assign a disposition indicating how it should be managed
in a limited-capacity context window.

Dispositions:
  L  = Live (keep in full — still actively needed)
  T  = Tombstone (can be evicted entirely — stale or reproducible)
  C  = Compress (replace with a short semantic summary — still relevant but doesn't need full text)
  U  = Uncertain (you're not sure — explain why)

Output format — one line per block, grouped by disposition:
  L:b001,b007,b045
  T:b003,b004,b005,b006,b008,b010
  C:b000"implementation plan for system prompt archaeology"
  C:b002"assistant acknowledges task and begins reading codebase"
  U:b012"might be needed if we revisit the test structure"

Rules:
- User messages where the human expresses intent, preferences, or decisions should almost always be L
- Tool results that have been fully processed (the assistant already acted on them) are T candidates
- Tool use/result pairs where the content is 0 chars are always T
- Assistant reasoning that led to a decision can be C (keep the decision, compress the reasoning)
- The final ~10 blocks should almost always be L (active working context)
- Be aggressive with T for stale tool results — they can be re-fetched
- For C blocks, include a brief tensor (semantic summary) in quotes after the block ID

After your dispositions, add a section:

STATS:
- Total blocks: N
- L: N (N%)
- T: N (N%)
- C: N (N%)
- U: N (N%)
- Estimated token savings: rough percentage

REFLECTION:
Brief notes on what was hard to classify and why. Flag any blocks where you
felt the protocol vocabulary was insufficient.
"""


def load_conversation(filepath: Path) -> list[dict]:
    """Load conversation blocks from a JSONL file."""
    blocks = []
    block_id = 0
    with open(filepath) as f:
        for line in f:
            d = json.loads(line)
            if d.get("type") not in ("user", "assistant", "system"):
                continue
            msg = d.get("message", {})
            content = msg.get("content", "")

            if isinstance(content, list):
                text_parts = []
                tool_info = []
                for b in content:
                    if isinstance(b, dict):
                        if b.get("type") == "text":
                            text_parts.append(b.get("text", ""))
                        elif b.get("type") == "tool_use":
                            tool_info.append(f"[tool_use: {b.get('name', '?')}]")
                        elif b.get("type") == "tool_result":
                            result_content = b.get("content", "")
                            if isinstance(result_content, list):
                                result_text = " ".join(
                                    r.get("text", "")[:200] for r in result_content
                                    if isinstance(r, dict) and r.get("type") == "text"
                                )
                            else:
                                result_text = str(result_content)[:200]
                            tool_info.append(f"[tool_result: {result_text[:100]}]")
                text = "\n".join(text_parts)
                if tool_info:
                    text = (text + "\n" + "\n".join(tool_info)).strip()
            else:
                text = str(content)

            blocks.append({
                "id": f"b{block_id:03d}",
                "role": d.get("type"),
                "text": text,
                "text_len": len(text),
            })
            block_id += 1
    return blocks


def format_blocks_for_prompt(blocks: list[dict], max_preview: int = 300) -> str:
    """Format blocks as labeled context for the model."""
    lines = []
    for b in blocks:
        preview = b["text"][:max_preview].replace("\n", " ")
        if len(b["text"]) > max_preview:
            preview += f"... [{b['text_len'] - max_preview} more chars]"
        if not preview.strip():
            preview = "(empty)"
        lines.append(f"[{b['id']}] {b['role']} ({b['text_len']} chars): {preview}")
    return "\n".join(lines)


def run_experiment(filepath: Path, model: str = "claude-haiku-4-5-20251001"):
    """Run the disposition experiment on a conversation."""
    print(f"Loading conversation from {filepath}...")
    blocks = load_conversation(filepath)
    print(f"Loaded {len(blocks)} blocks, {sum(b['text_len'] for b in blocks):,} chars total")

    # Format the blocks
    blocks_text = format_blocks_for_prompt(blocks)

    # Build the prompt
    user_prompt = f"""Here is a conversation with {len(blocks)} labeled blocks:

{blocks_text}

Please produce dispositions for each block following the protocol above."""

    print(f"\nPrompt size: ~{len(user_prompt)} chars")
    print(f"Sending to {model}...")

    client = anthropic.Anthropic()

    start = datetime.now()
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=PROTOCOL_PREAMBLE,
        messages=[{"role": "user", "content": user_prompt}],
    )
    elapsed = (datetime.now() - start).total_seconds()

    result_text = response.content[0].text

    print(f"\nResponse received in {elapsed:.1f}s")
    print(f"Tokens — input: {response.usage.input_tokens}, output: {response.usage.output_tokens}")
    print(f"\n{'='*80}")
    print(result_text)
    print(f"{'='*80}")

    # Save results
    output_dir = Path(__file__).parent.parent / "data" / "disposition_experiment"
    output_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "conversation_file": str(filepath),
        "n_blocks": len(blocks),
        "total_chars": sum(b["text_len"] for b in blocks),
        "prompt_chars": len(user_prompt),
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "elapsed_seconds": elapsed,
        "dispositions_raw": result_text,
    }

    output_file = output_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nResults saved to {output_file}")


if __name__ == "__main__":
    # Default: use the arbiter conversation
    default_path = Path.home() / ".claude/projects/-home-tony-projects-arbiter/ee1b86fb-909a-4939-82e2-ce51de5dc68b.jsonl"
    filepath = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path

    # Use haiku for speed/cost, can upgrade to sonnet/opus for comparison
    model = sys.argv[2] if len(sys.argv) > 2 else "claude-haiku-4-5-20251001"

    run_experiment(filepath, model)
