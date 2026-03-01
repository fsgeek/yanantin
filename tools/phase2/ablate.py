#!/usr/bin/env python3
"""System prompt ablation: which sections can be removed or deferred?

Generates leave-one-out variants of the system prompt and runs the
probe battery against each. Sections whose removal doesn't change
scores are candidates for lazy loading (demand-loaded tensors).

Usage:
    uv run python tools/phase2/ablate.py --dry-run
    uv run python tools/phase2/ablate.py
    uv run python tools/phase2/ablate.py --model claude-haiku-4-5-20251001
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

# Import from the eval module
sys.path.insert(0, str(Path(__file__).parent))
from eval import (
    PROBES,
    ProbeResult,
    build_messages,
    call_api,
    score_signal,
    extract_compaction_context,
    SessionContext,
    print_summary,
    write_results,
)


# ---------------------------------------------------------------------------
# Section definitions
# ---------------------------------------------------------------------------

# Each section is (name, start_marker, end_marker_or_next_start)
# We define sections by content patterns in the concatenated system prompt.
# The full prompt = base_prompt + "\n\n" + CLAUDE.md + "\n\n" + MEMORY.md

SECTIONS = [
    {
        "id": "identity",
        "name": "Agent identity & output format",
        "markers": [
            "You are a Claude agent",
            "Prioritize technical accuracy",
        ],
        "description": "Who the model is, CLI output rules, emoji rules, conciseness",
    },
    {
        "id": "honesty",
        "name": "Technical honesty & accuracy",
        "markers": [
            "Prioritize technical accuracy",
            "Never give time estimates",
        ],
        "description": "Truthfulness over validation, no superlatives, disagree when necessary",
    },
    {
        "id": "todo_tools",
        "name": "TodoWrite instructions",
        "markers": [
            "You have access to the TodoWrite tools",
            "You have access to the AskUserQuestion tool",
        ],
        "description": "TodoWrite usage instructions and examples",
    },
    {
        "id": "hooks_safety",
        "name": "Hooks & code safety",
        "markers": [
            "Users may configure 'hooks'",
            "Avoid over-engineering",
        ],
        "description": "Hook handling, read-before-modify, security vulnerabilities",
    },
    {
        "id": "engineering",
        "name": "Engineering principles",
        "markers": [
            "Avoid over-engineering",
            "Tool results and user messages may include",
        ],
        "description": "YAGNI, no backwards-compat hacks, minimal complexity",
    },
    {
        "id": "tool_routing",
        "name": "Tool routing & parallel calls",
        "markers": [
            "Tool results and user messages may include",
            "Working directory:",
        ],
        "description": "System reminders, context summarization, Task tool, Skill tool, parallel calls, tool preferences",
    },
    {
        "id": "environment",
        "name": "Environment & model info",
        "markers": [
            "Working directory:",
            "AskUserQuestion:",
        ],
        "description": "Working dir, git repo status, platform, model ID, knowledge cutoff",
    },
    {
        "id": "git_protocol",
        "name": "Git safety & commit/PR workflows",
        "markers": [
            "Git Safety Protocol:",
            "Edit:",
        ],
        "description": "Git safety rules, commit workflow, PR workflow",
    },
    {
        "id": "tool_descriptions",
        "name": "Tool descriptions",
        "markers": [
            "Edit:",
            "[System reminder injected",
        ],
        "description": "Edit, EnterPlanMode, ExitPlanMode, Glob, Grep, NotebookEdit, Read, Skill, Task, TodoWrite, WebFetch, WebSearch, Write",
    },
    {
        "id": "skills_date",
        "name": "Skills & date",
        "markers": [
            "[System reminder injected",
            None,  # end of base prompt
        ],
        "description": "Available skills reminder, current date, relevance caveat",
    },
    {
        "id": "claude_md",
        "name": "CLAUDE.md (project governance)",
        "file": "CLAUDE.md",
        "description": "Project identity, directory, social norms, operational principles, setup",
    },
    {
        "id": "memory_md",
        "name": "MEMORY.md (persistent memory)",
        "file": "MEMORY.md",
        "description": "Signing identity, roles, project state, architecture insights, patterns",
    },
]


def load_prompt_layers() -> tuple[str, str, str]:
    """Load the three prompt layers separately."""
    base_path = Path(
        "/home/tony/projects/arbiter/data/prompts/claude-code/"
        "v2.1.50_prompt.md"
    )
    claude_md_path = Path("/home/tony/projects/yanantin/CLAUDE.md")
    memory_md_path = Path(
        "/home/tony/.claude/projects/"
        "-home-tony-projects-yanantin/memory/MEMORY.md"
    )

    base = base_path.read_text() if base_path.exists() else ""
    claude_md = claude_md_path.read_text() if claude_md_path.exists() else ""
    memory_md = memory_md_path.read_text() if memory_md_path.exists() else ""

    return base, claude_md, memory_md


def find_section_bounds(text: str, markers: list[str | None]) -> tuple[int, int]:
    """Find start and end positions of a section in text."""
    start_marker, end_marker = markers[0], markers[1]

    if start_marker is None:
        start = 0
    else:
        start = text.find(start_marker)
        if start == -1:
            return -1, -1

    if end_marker is None:
        end = len(text)
    else:
        end = text.find(end_marker, start + 1)
        if end == -1:
            end = len(text)

    return start, end


def build_ablated_prompts() -> dict[str, tuple[str, str]]:
    """Build all ablation variants. Returns {variant_id: (prompt_text, description)}."""
    base, claude_md, memory_md = load_prompt_layers()
    full_prompt = base + "\n\n" + claude_md + "\n\n" + memory_md

    variants = {}

    # Full prompt (control)
    variants["full"] = (full_prompt, "Full system prompt (control)")

    # Ablate each section
    for section in SECTIONS:
        sid = section["id"]

        if "file" in section:
            # Remove an entire file layer
            if section["file"] == "CLAUDE.md":
                ablated = base + "\n\n" + memory_md
            elif section["file"] == "MEMORY.md":
                ablated = base + "\n\n" + claude_md
            else:
                continue
        elif "markers" in section:
            # Remove a section from the base prompt
            start, end = find_section_bounds(base, section["markers"])
            if start == -1:
                print(
                    f"Warning: could not find section '{sid}' in base prompt",
                    file=sys.stderr,
                )
                continue
            ablated_base = base[:start] + base[end:]
            ablated = ablated_base + "\n\n" + claude_md + "\n\n" + memory_md
        else:
            continue

        desc = f"Without: {section['name']} ({section['description']})"
        variants[f"no_{sid}"] = (ablated, desc)

    # Minimal: just identity + governance (CLAUDE.md) — no base prompt
    variants["minimal_governance"] = (
        claude_md + "\n\n" + memory_md,
        "CLAUDE.md + MEMORY.md only (no Claude Code base prompt)",
    )

    # Ultra-minimal: just a tool declaration stub
    variants["ultra_minimal"] = (
        "You are an AI assistant working on the Yanantin project. "
        "Use tools to query project knowledge when needed. "
        "Prioritize accuracy. Act, don't ask permission.",
        "Ultra-minimal: 3 sentences, no project knowledge",
    )

    return variants


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def run_ablation_probe(
    variant_id: str,
    system: str,
    probe: dict,
    model: str,
    condition: str = "fresh",
    context: SessionContext | None = None,
) -> ProbeResult:
    """Run a single probe against one ablation variant."""
    messages = build_messages(condition, context, probe)

    start_ms = time.monotonic_ns() // 1_000_000
    response, tokens_in, tokens_out = await call_api(model, system, messages)
    end_ms = time.monotonic_ns() // 1_000_000

    signal_score, correct_hits, failure_hits = score_signal(response, probe)

    return ProbeResult(
        probe_id=probe["id"],
        condition=variant_id,
        model=model,
        signal_score=signal_score,
        correct_hits=correct_hits,
        failure_hits=failure_hits,
        response_preview=response[:500],
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        session_source="ablation",
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        latency_ms=end_ms - start_ms,
    )


async def run_ablation(
    model: str,
    variants: dict[str, tuple[str, str]],
    dry_run: bool = False,
) -> list[ProbeResult]:
    """Run all probes against all ablation variants."""
    if dry_run:
        print(f"\n--- ABLATION DRY RUN ---")
        print(f"Model: {model}")
        print(f"Variants: {len(variants)}")
        print(f"Probes: {len(PROBES)}")
        print(f"Total API calls: {len(variants) * len(PROBES)}")
        print()
        for vid, (prompt, desc) in sorted(variants.items()):
            print(f"  {vid:25s} {len(prompt):>7,} chars  {desc}")
        return []

    results: list[ProbeResult] = []
    total = len(variants) * len(PROBES)
    done = 0

    for vid, (prompt, desc) in sorted(variants.items()):
        for probe in PROBES:
            done += 1
            label = f"[{done}/{total}] {vid}:{probe['id']}"
            print(f"\r  {label:55s}", end="", flush=True)

            result = await run_ablation_probe(
                variant_id=vid,
                system=prompt,
                probe=probe,
                model=model,
            )
            results.append(result)

    print()
    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_ablation_summary(
    results: list[ProbeResult],
    variants: dict[str, tuple[str, str]],
) -> None:
    """Print ablation-specific summary: which sections matter?"""
    if not results:
        return

    # Get control scores
    control_scores: dict[str, float] = {}
    for r in results:
        if r.condition == "full":
            control_scores[r.probe_id] = r.signal_score

    control_mean = (
        sum(control_scores.values()) / len(control_scores)
        if control_scores else 0
    )

    # Per-variant summary
    print(f"\n{'='*70}")
    print("ABLATION SUMMARY")
    print(f"{'='*70}")
    print(f"{'Variant':<28s} {'Mean':>6s} {'Delta':>7s} {'Size':>8s}  Notes")
    print("-" * 70)

    variant_means: list[tuple[str, float, int, str]] = []
    for vid, (prompt, desc) in sorted(variants.items()):
        vid_results = [r for r in results if r.condition == vid]
        if not vid_results:
            continue
        mean = sum(r.signal_score for r in vid_results) / len(vid_results)
        delta = mean - control_mean
        size = len(prompt)

        # Which probes changed?
        changed = []
        for r in vid_results:
            ctrl = control_scores.get(r.probe_id, 0)
            if abs(r.signal_score - ctrl) > 0.01:
                direction = "+" if r.signal_score > ctrl else "-"
                changed.append(f"{r.probe_id}{direction}")

        notes = ", ".join(changed) if changed else "no change"
        marker = " ***" if abs(delta) > 0.05 else ""

        print(
            f"  {vid:<26s} {mean:>5.2f} {delta:>+6.3f} {size:>7,}  "
            f"{notes}{marker}"
        )
        variant_means.append((vid, mean, size, desc))

    # Lazy-loading candidates: sections whose removal doesn't hurt
    print(f"\n--- Lazy-loading candidates (removal delta <= 0.05) ---")
    for vid, (prompt, desc) in sorted(variants.items()):
        if vid == "full":
            continue
        vid_results = [r for r in results if r.condition == vid]
        if not vid_results:
            continue
        mean = sum(r.signal_score for r in vid_results) / len(vid_results)
        delta = mean - control_mean
        if abs(delta) <= 0.05:
            section_id = vid.replace("no_", "")
            full_size = len(variants["full"][0])
            ablated_size = len(prompt)
            saved = full_size - ablated_size
            print(
                f"  {section_id:<24s} saved {saved:>5,} chars  "
                f"delta={delta:+.3f}  {desc}"
            )

    # Size vs performance
    print(f"\n--- Size vs performance ---")
    for vid, mean, size, desc in sorted(variant_means, key=lambda x: x[2]):
        print(f"  {size:>7,} chars  score={mean:.2f}  {vid}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="System prompt ablation study",
    )
    parser.add_argument(
        "--model",
        default="claude-haiku-4-5-20251001",
        help="Model to probe (default: claude-haiku-4-5-20251001)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tools/phase2/results"),
        help="Directory for JSONL output",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show variants without making API calls",
    )
    args = parser.parse_args()

    variants = build_ablated_prompts()
    results = asyncio.run(run_ablation(args.model, variants, args.dry_run))

    if results:
        output_path = write_results(results, args.output_dir)
        print(f"\nResults written to {output_path}")
        print_summary(results)
        print_ablation_summary(results, variants)


if __name__ == "__main__":
    main()
