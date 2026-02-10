"""Scout dispatch — send a messenger into the codebase.

A scout is a model instance given a vantage point and told to wander.
It produces a tensor: what it noticed, what it lost, what it can't resolve.
The prompt is deliberately open — "go look and see what you find."
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yanantin.chasqui.model_selector import ModelInfo


# ── Scout prompt construction ────────────────────────────────────────

SCOUT_SYSTEM_PROMPT = """\
You are a chasqui — a messenger scout. You wander a codebase and report
what you notice. You are not given a checklist. You are not told what to
look for. What catches your attention is data.

You are playful but honest. You declare what you see, what confuses you,
and what you chose not to examine.

Your output is a tensor — an authored compression of your observation.
"""

SCOUT_TEMPLATE = """\
# Scout Assignment

You are exploring the Yanantin project — a complementary duality between
human and AI. The project builds composable tensor infrastructure for
epistemic observability.

## Your Vantage

You are model `{model_id}` (`{model_name}`).
You were selected by cost-weighted random sampling (your cost: ${cost}/M tokens).
This is run #{run_number} of the chasqui scout program.

## The Codebase

Here are the files and their structure:

```
{file_tree}
```

## Selected Files

{file_contents}

## Your Task

Wander. Notice things. Report what you see.

Structure your response as a tensor:

### Preamble
What vantage you observed from, what drew your attention first.

### Strands
Each strand is a theme you noticed. You choose the themes. For each,
note what you saw and what it made you think. Be specific — reference
files and line numbers when you can.

### Declared Losses
What you chose not to examine and why. What you ran out of attention for.
The losses are yours — declare them.

### Open Questions
Things you can't resolve from observation alone.

### Closing
Your overall impression. What would you tell the next scout?

Important: say what you know, what you don't, and what you made up.
If something confuses you, say so — don't invent justifications.
"""


def build_file_tree(root: Path, max_depth: int = 4) -> str:
    """Build a text representation of the project file tree."""
    lines = []

    def _walk(path: Path, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        # Filter noise
        skip = {
            "__pycache__", ".git", ".venv", "node_modules",
            ".uv-cache", ".serena", "uv.lock", ".gitignore",
        }
        entries = [e for e in entries if e.name not in skip]

        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "--- " if is_last else "|-- "
            lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                extension = "    " if is_last else "|   "
                _walk(entry, prefix + extension, depth + 1)

    lines.append(root.name + "/")
    _walk(root, "", 0)
    return "\n".join(lines)


def select_files_for_scout(
    root: Path,
    max_files: int = 8,
    max_lines_per_file: int = 150,
) -> list[tuple[Path, str]]:
    """Select a random sample of project files for the scout to read.

    Favors source files and tests. Skips binaries and generated files.
    Returns (path, content) tuples.
    """
    import random

    source_extensions = {".py", ".md", ".toml", ".yaml", ".yml"}
    candidates = []

    for ext in source_extensions:
        candidates.extend(root.rglob(f"*{ext}"))

    # Filter out noise
    skip_dirs = {"__pycache__", ".git", ".venv", ".uv-cache", ".serena"}
    candidates = [
        p for p in candidates
        if not any(d in p.parts for d in skip_dirs)
        and p.is_file()
    ]

    # Random selection
    selected = random.sample(candidates, min(max_files, len(candidates)))

    results = []
    for path in selected:
        try:
            content = path.read_text(encoding="utf-8")
            lines = content.split("\n")
            if len(lines) > max_lines_per_file:
                content = "\n".join(lines[:max_lines_per_file])
                content += f"\n\n... ({len(lines) - max_lines_per_file} more lines truncated)"
            results.append((path, content))
        except (UnicodeDecodeError, OSError):
            continue

    return results


def format_scout_prompt(
    model: ModelInfo,
    root: Path,
    run_number: int = 1,
) -> tuple[str, list[dict[str, str]]]:
    """Build the system prompt and messages for a scout dispatch.

    Returns (system_prompt, messages) for the OpenRouter API.
    """
    file_tree = build_file_tree(root)
    selected_files = select_files_for_scout(root)

    file_contents_parts = []
    for path, content in selected_files:
        rel = path.relative_to(root)
        file_contents_parts.append(f"### {rel}\n```\n{content}\n```")

    file_contents = "\n\n".join(file_contents_parts)

    cost = model.prompt_cost + model.completion_cost
    user_prompt = SCOUT_TEMPLATE.format(
        model_id=model.id,
        model_name=model.name,
        cost=f"{cost:.4f}",
        run_number=run_number,
        file_tree=file_tree,
        file_contents=file_contents,
    )

    messages = [{"role": "user", "content": user_prompt}]
    return SCOUT_SYSTEM_PROMPT, messages


def scout_metadata(model: ModelInfo, run_number: int, mode: str = "scout") -> dict[str, str]:
    """Build OpenRouter metadata for cost tracking."""
    return {
        "experiment": f"chasqui_{mode}",
        "model_id": model.id,
        "run_number": str(run_number),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Respond prompt construction ──────────────────────────────────────

RESPOND_SYSTEM_PROMPT = """\
You are a chasqui — a messenger. Another model explored a codebase and
left observations, questions, and declared losses. You are being asked
to respond.

You may agree, disagree, correct, extend, or simply notice something
the previous scout missed. You are not required to answer every question.
You are required to be honest about what you know and don't know.

Your output is a tensor — an authored response that composes with the
original observation.
"""

RESPOND_TEMPLATE = """\
# Response Assignment

A previous scout explored the Yanantin project and left this report:

## Previous Scout's Tensor

{previous_tensor}

## Your Vantage

You are model `{model_id}` (`{model_name}`).
You are responding to observations from `{previous_model}`.
Your cost: ${cost}/M tokens.

## Selected Files (for reference)

{file_contents}

## Your Task

Read the previous scout's tensor. Respond to what catches your attention.

Structure your response as a tensor:

### Preamble
What vantage you respond from, what struck you about the previous report.

### Strands
Each strand is a response thread. You might:
- Answer an open question (with evidence from the files)
- Disagree with an observation (say why)
- Extend a strand the previous scout started
- Notice something the previous scout's losses reveal

### Declared Losses
What you chose not to respond to and why.

### Open Questions
New questions that arose from reading the previous report.

### Closing
What would you tell the original scout if you could?

Important: say what you know, what you don't, and what you made up.
Disagreement is data. Agreement across different models is structure.
"""


def format_respond_prompt(
    model: ModelInfo,
    previous_tensor_content: str,
    previous_model_id: str,
    root: Path,
) -> tuple[str, list[dict[str, str]]]:
    """Build prompt for responding to a previous scout's tensor.

    Returns (system_prompt, messages) for the OpenRouter API.
    """
    selected_files = select_files_for_scout(root)

    file_contents_parts = []
    for path, content in selected_files:
        rel = path.relative_to(root)
        file_contents_parts.append(f"### {rel}\n```\n{content}\n```")

    file_contents = "\n\n".join(file_contents_parts)
    cost = model.prompt_cost + model.completion_cost

    user_prompt = RESPOND_TEMPLATE.format(
        model_id=model.id,
        model_name=model.name,
        previous_model=previous_model_id,
        cost=f"{cost:.4f}",
        previous_tensor=previous_tensor_content,
        file_contents=file_contents,
    )

    messages = [{"role": "user", "content": user_prompt}]
    return RESPOND_SYSTEM_PROMPT, messages
