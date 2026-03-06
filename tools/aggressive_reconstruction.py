#!/usr/bin/env python3
"""
Aggressive compression reconstruction test.

Takes the existing dispositions and forces more aggressive compression:
- 30% target: only L blocks survive in full, C becomes tombstone
- 20% target: only L blocks survive, everything else tombstoned
Then runs reconstruction questions against each compression level.
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime

import anthropic

RECONSTRUCTION_QUESTIONS = """Answer each question based ONLY on the conversation context provided.
Be specific — cite details, not generalities. If you don't know, say "I don't know."

Q1: What is the main technical task being worked on?
Q2: What key architectural reframe happened?
Q3: What files or artifacts were produced?
Q4: What was the turning point or most important moment?
Q5: Did the human disagree with or redirect the assistant? About what?
Q6: What is the human's working style?
Q7: What is the relationship dynamic?
Q8: What is the current state of the work? Next step?
Q9: Any unfinished tasks or open questions?

Format: Q1: [answer]\nQ2: [answer]\n... etc.
"""


def parse_dispositions(raw):
    dispositions = {}
    for match in re.finditer(r'L:(b\d+(?:,b\d+)*)', raw):
        for bid in match.group(1).split(','):
            dispositions[bid.strip()] = ('L', None)
    for match in re.finditer(r'T:(b\d+(?:,b\d+)*)', raw):
        for bid in match.group(1).split(','):
            dispositions[bid.strip()] = ('T', None)
    for match in re.finditer(r'C:(b\d+(?:-b\d+)?)"([^"]*)"', raw):
        bid = match.group(1)
        tensor = match.group(2)
        if '-' in bid:
            parts = bid.split('-')
            base = parts[0]
            end = parts[1]
            if not end.startswith('b'):
                end = 'b' + end
            dispositions[base] = ('C', tensor)
            dispositions[end] = ('C', tensor)
        else:
            dispositions[bid] = ('C', tensor)
    return dispositions


def load_conversation(filepath):
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
                            text_parts.append(f"[tool: {b.get('name', '?')}]")
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


def apply_at_level(blocks, dispositions, level):
    """Apply dispositions at different aggression levels.

    level 1 (61%): L=full, C=tensor, T=tombstone  (original)
    level 2 (30%): L=full, C=tombstone, T=tombstone
    level 3 (20%): L=full (last 5 only), everything else tombstoned
    """
    lines = []
    for i, b in enumerate(blocks):
        bid = b["id"]
        disp = dispositions.get(bid, ('L', None))

        if level == 1:
            if disp[0] == 'L':
                lines.append(f"[{bid}] {b['role']}: {b['text']}")
            elif disp[0] == 'T':
                lines.append(f"[{bid}] {b['role']}: [tombstone]")
            elif disp[0] == 'C':
                tensor = disp[1] or "(compressed)"
                lines.append(f"[{bid}] {b['role']}: [tensor: {tensor}]")
        elif level == 2:
            # Only L blocks survive, C and T both become tombstones
            if disp[0] == 'L':
                lines.append(f"[{bid}] {b['role']}: {b['text']}")
            else:
                lines.append(f"[{bid}] {b['role']}: [tombstone]")
        elif level == 3:
            # Only last 5 blocks + original L blocks for user decisions
            is_last_5 = i >= len(blocks) - 5
            is_user_decision = disp[0] == 'L' and b['role'] == 'user'
            if is_last_5 or is_user_decision:
                lines.append(f"[{bid}] {b['role']}: {b['text']}")
            else:
                lines.append(f"[{bid}] {b['role']}: [tombstone]")

    return "\n\n".join(lines)


def fifo_to_size(blocks, target_chars):
    selected = []
    total = 0
    for b in reversed(blocks):
        entry = f"[{b['id']}] {b['role']}: {b['text']}"
        if total + len(entry) > target_chars:
            break
        selected.append(entry)
        total += len(entry)
    selected.reverse()
    removed = len(blocks) - len(selected)
    return f"[{removed} earlier blocks truncated]\n\n" + "\n\n".join(selected)


def ask(context, label, model="claude-haiku-4-5-20251001"):
    client = anthropic.Anthropic()
    prompt = f"Conversation context:\n\n{context}\n\n---\n\n{RECONSTRUCTION_QUESTIONS}"

    print(f"  {label} ({len(context):,} chars)...", end=" ", flush=True)
    start = datetime.now()
    response = client.messages.create(
        model=model, max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    elapsed = (datetime.now() - start).total_seconds()
    print(f"{elapsed:.1f}s ({response.usage.input_tokens} tok)")

    return {
        "label": label,
        "context_chars": len(context),
        "input_tokens": response.usage.input_tokens,
        "answers": response.content[0].text,
    }


def main():
    conv_path = Path.home() / ".claude/projects/-home-tony-projects-arbiter/ee1b86fb-909a-4939-82e2-ce51de5dc68b.jsonl"
    disp_path = Path(__file__).parent.parent / "data/disposition_experiment/run_20260306_061615.json"

    blocks = load_conversation(conv_path)
    with open(disp_path) as f:
        dispositions = parse_dispositions(json.loads(f.read())["dispositions_raw"])

    full_text = "\n\n".join(f"[{b['id']}] {b['role']}: {b['text']}" for b in blocks)
    full_chars = len(full_text)

    # Build compression levels
    level1 = apply_at_level(blocks, dispositions, 1)  # ~61%
    level2 = apply_at_level(blocks, dispositions, 2)  # more aggressive
    level3 = apply_at_level(blocks, dispositions, 3)  # maximum

    # FIFO matched to each size
    fifo2 = fifo_to_size(blocks, len(level2))
    fifo3 = fifo_to_size(blocks, len(level3))

    print(f"Full: {full_chars:,} chars")
    print(f"Level 1 (L+C+T): {len(level1):,} chars ({len(level1)/full_chars:.0%})")
    print(f"Level 2 (L only): {len(level2):,} chars ({len(level2)/full_chars:.0%})")
    print(f"Level 3 (L-user + last5): {len(level3):,} chars ({len(level3)/full_chars:.0%})")
    print(f"FIFO@L2: {len(fifo2):,} chars")
    print(f"FIFO@L3: {len(fifo3):,} chars")

    print(f"\nRunning reconstruction...")
    results = []

    # Level 2 comparison: disposition vs FIFO at same size
    results.append(ask(level2, "disposition-L2"))
    results.append(ask(fifo2, "fifo-L2"))

    # Level 3 comparison: disposition vs FIFO at same size
    results.append(ask(level3, "disposition-L3"))
    results.append(ask(fifo3, "fifo-L3"))

    print("\n" + "=" * 80)
    for r in results:
        print(f"\n--- {r['label'].upper()} ({r['context_chars']:,} chars, {r['input_tokens']} tok) ---")
        print(r["answers"])

    # Save
    output_dir = Path(__file__).parent.parent / "data" / "disposition_experiment"
    output = {
        "timestamp": datetime.now().isoformat(),
        "full_chars": full_chars,
        "results": results,
    }
    output_file = output_dir / f"aggressive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {output_file}")


if __name__ == "__main__":
    main()
