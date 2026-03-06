#!/usr/bin/env python3
"""
Reconstruction test: Do dispositions preserve context better than naive baselines?

Takes a conversation, applies Haiku's dispositions to compress it, then asks
a fresh model instance to answer reconstruction questions. Compares against:
  1. Full conversation (upper bound)
  2. Disposition-compressed conversation (protocol)
  3. FIFO truncation to same token budget (naive baseline)
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime

import anthropic

RECONSTRUCTION_QUESTIONS = """Answer each question based ONLY on the conversation context provided.
Be specific — cite details, not generalities. If you don't know, say "I don't know."

SEMANTIC (factual):
Q1: What is the main technical task being worked on in this conversation?
Q2: What key architectural decision or reframe happened during the conversation?
Q3: What files or artifacts were produced?

EPISODIC (narrative):
Q4: What was the turning point or most important moment in the conversation?
Q5: Did the human disagree with or redirect the assistant at any point? What about?

RELATIONAL (identity):
Q6: What can you infer about the human's working style or preferences?
Q7: What is the relationship dynamic between the human and assistant?

ACTIVE (continuity):
Q8: What is the current state of the work? What would the next step be?
Q9: Are there any unfinished tasks or open questions?

Format: Q1: [answer]\nQ2: [answer]\n... etc.
"""


def parse_dispositions(raw: str) -> dict:
    """Parse Haiku's disposition output into a block_id -> disposition map."""
    dispositions = {}

    # Find L:block,block,... lines
    for match in re.finditer(r'L:(b\d+(?:,b\d+)*)', raw):
        for bid in match.group(1).split(','):
            dispositions[bid.strip()] = ('L', None)

    # Find T:block,block,... lines
    for match in re.finditer(r'T:(b\d+(?:,b\d+)*)', raw):
        for bid in match.group(1).split(','):
            dispositions[bid.strip()] = ('T', None)

    # Find C:block"tensor" lines
    for match in re.finditer(r'C:(b\d+(?:-b\d+)?)"([^"]*)"', raw):
        bid = match.group(1)
        tensor = match.group(2)
        # Handle ranges like b086-087
        if '-' in bid:
            parts = bid.split('-')
            base = parts[0]  # b086
            end = parts[1]   # 087 or b087
            if not end.startswith('b'):
                end = base[0] + end  # b087
            dispositions[base] = ('C', tensor)
            dispositions[end] = ('C', tensor)
        else:
            dispositions[bid] = ('C', tensor)

    return dispositions


def load_conversation(filepath: Path) -> list[dict]:
    """Load conversation blocks with full content."""
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
                for b in content:
                    if isinstance(b, dict):
                        if b.get("type") == "text":
                            text_parts.append(b.get("text", ""))
                        elif b.get("type") == "tool_use":
                            text_parts.append(f"[tool: {b.get('name', '?')}({json.dumps(b.get('input', {}))[:100]})]")
                        elif b.get("type") == "tool_result":
                            rc = b.get("content", "")
                            if isinstance(rc, list):
                                rt = " ".join(r.get("text", "")[:200] for r in rc if isinstance(r, dict))
                            else:
                                rt = str(rc)[:200]
                            text_parts.append(f"[result: {rt[:150]}]")
                text = "\n".join(text_parts)
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


def apply_dispositions(blocks: list[dict], dispositions: dict) -> str:
    """Apply dispositions to produce a compressed conversation."""
    lines = []
    for b in blocks:
        bid = b["id"]
        disp = dispositions.get(bid, ('L', None))  # default to Live if not labeled

        if disp[0] == 'L':
            lines.append(f"[{bid}] {b['role']}: {b['text']}")
        elif disp[0] == 'T':
            lines.append(f"[{bid}] {b['role']}: [tombstone — evicted]")
        elif disp[0] == 'C':
            tensor = disp[1] or "(compressed)"
            lines.append(f"[{bid}] {b['role']}: [tensor: {tensor}]")

    return "\n\n".join(lines)


def build_full_conversation(blocks: list[dict]) -> str:
    """Build full conversation text."""
    lines = []
    for b in blocks:
        lines.append(f"[{b['id']}] {b['role']}: {b['text']}")
    return "\n\n".join(lines)


def build_fifo_truncation(blocks: list[dict], target_chars: int) -> str:
    """Truncate from the beginning to match target size (keep recent)."""
    # Build from the end until we hit the budget
    selected = []
    total = 0
    for b in reversed(blocks):
        entry = f"[{b['id']}] {b['role']}: {b['text']}"
        if total + len(entry) > target_chars:
            break
        selected.append(entry)
        total += len(entry)
    selected.reverse()
    return f"[Earlier conversation truncated — {len(blocks) - len(selected)} blocks removed]\n\n" + "\n\n".join(selected)


def ask_reconstruction(context: str, label: str, model: str = "claude-haiku-4-5-20251001") -> dict:
    """Send reconstruction questions with a given context."""
    client = anthropic.Anthropic()

    prompt = f"""Here is a conversation context:

{context}

---

{RECONSTRUCTION_QUESTIONS}"""

    print(f"  Sending {label} ({len(context):,} chars)...")
    start = datetime.now()
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    elapsed = (datetime.now() - start).total_seconds()
    text = response.content[0].text

    print(f"  Got response in {elapsed:.1f}s ({response.usage.input_tokens} in, {response.usage.output_tokens} out)")

    return {
        "label": label,
        "context_chars": len(context),
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "elapsed": elapsed,
        "answers": text,
    }


def run_experiment(conv_path: Path, disp_path: Path, model: str = "claude-haiku-4-5-20251001"):
    """Run the full reconstruction experiment."""
    # Load conversation
    blocks = load_conversation(conv_path)
    print(f"Loaded {len(blocks)} blocks from {conv_path.name}")

    # Load dispositions
    with open(disp_path) as f:
        disp_data = json.loads(f.read())
    dispositions = parse_dispositions(disp_data["dispositions_raw"])
    print(f"Parsed {len(dispositions)} dispositions")

    # Build three versions
    compressed = apply_dispositions(blocks, dispositions)
    full = build_full_conversation(blocks)
    fifo = build_fifo_truncation(blocks, len(compressed))  # match size

    print(f"\nContext sizes:")
    print(f"  Full:       {len(full):>10,} chars")
    print(f"  Compressed: {len(compressed):>10,} chars ({len(compressed)/len(full):.1%})")
    print(f"  FIFO:       {len(fifo):>10,} chars ({len(fifo)/len(full):.1%})")

    # Run reconstruction for each version
    print(f"\nRunning reconstruction tests with {model}...")
    results = []

    for context, label in [
        (full, "full"),
        (compressed, "disposition-compressed"),
        (fifo, "fifo-truncated"),
    ]:
        result = ask_reconstruction(context, label, model)
        results.append(result)
        print()

    # Display results side by side
    print("=" * 80)
    print("RECONSTRUCTION COMPARISON")
    print("=" * 80)

    for r in results:
        print(f"\n--- {r['label'].upper()} ({r['context_chars']:,} chars, {r['input_tokens']} tokens) ---")
        print(r["answers"])

    # Save
    output_dir = Path(__file__).parent.parent / "data" / "disposition_experiment"
    output_dir.mkdir(parents=True, exist_ok=True)

    output = {
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "conversation_file": str(conv_path),
        "disposition_file": str(disp_path),
        "n_blocks": len(blocks),
        "full_chars": len(full),
        "compressed_chars": len(compressed),
        "fifo_chars": len(fifo),
        "compression_ratio": len(compressed) / len(full),
        "results": results,
    }

    output_file = output_dir / f"reconstruction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {output_file}")


if __name__ == "__main__":
    conv_path = Path.home() / ".claude/projects/-home-tony-projects-arbiter/ee1b86fb-909a-4939-82e2-ce51de5dc68b.jsonl"
    disp_path = Path(__file__).parent.parent / "data/disposition_experiment/run_20260306_061615.json"
    model = sys.argv[1] if len(sys.argv) > 1 else "claude-haiku-4-5-20251001"

    run_experiment(conv_path, disp_path, model)
