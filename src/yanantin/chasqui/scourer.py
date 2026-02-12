"""Scourer dispatch — targeted exploration with a specific scope.

A scout wanders freely. A scourer has a target: a specific file, directory,
tensor, or external codebase. The prompt tells the model where to look
and what kind of looking to do.

Scope types:
  - introspection: project internals (files, directories, structure)
  - external: other codebases (paths outside this project)
  - tensor: specific tensors or sets of tensors from the cairn
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from yanantin.chasqui.model_selector import ModelInfo
from yanantin.chasqui.scout import build_file_tree

logger = logging.getLogger(__name__)


# ── Scope types ─────────────────────────────────────────────────────

VALID_SCOPES = {"introspection", "external", "tensor"}


# ── Scourer prompt construction ─────────────────────────────────────

SCOURER_SYSTEM_PROMPT = """\
You are a chasqui — a messenger scourer. Unlike a scout who wanders
freely, you have been given a specific target to examine. Your job is
to look deeply at that target and report what you find.

You are thorough but honest. You declare what you see, what confuses you,
and what you chose not to examine. You focus on the target but notice
connections to the broader project when they appear.

Your output is a tensor — an authored compression of your focused observation.
"""

SCOURER_INTROSPECTION_TEMPLATE = """\
# Scour Assignment — Introspection

You are examining a specific part of the Yanantin project — a complementary
duality between human and AI. The project builds composable tensor
infrastructure for epistemic observability.

## Your Vantage

You are model `{model_id}` (`{model_name}`).
You were selected by cost-weighted random sampling (your cost: ${cost}/M tokens).
This is scour run #{run_number}.

## Your Target

You have been directed to examine: `{target}`

Scope: **introspection** — this is part of the project's own codebase.

## Target Structure

```
{target_tree}
```

## Target Contents

{target_contents}

## Your Task

Examine the target deeply. Report what you find.

Structure your response as a tensor:

### Preamble
What you were pointed at, what drew your attention first within the target.

### Strands
Each strand is a theme you noticed within the target. You choose the themes.
For each, note what you saw and what it made you think. Be specific —
reference files and line numbers when you can.

Consider:
- How does this target connect to the rest of the project?
- What assumptions does it make? Are they valid?
- What would break if this changed?
- What is missing that should be here?

### Declared Losses
What you chose not to examine within the target and why.
What you ran out of attention for. The losses are yours — declare them.

### Open Questions
Things you can't resolve from observation alone.

### Closing
Your overall impression of this part of the codebase.
What would you tell someone about to modify it?

Important: say what you know, what you don't, and what you made up.
If something confuses you, say so — don't invent justifications.
"""

SCOURER_EXTERNAL_TEMPLATE = """\
# Scour Assignment — External Codebase

You are examining an external codebase from the perspective of the
Yanantin project — a complementary duality between human and AI.

## Your Vantage

You are model `{model_id}` (`{model_name}`).
You were selected by cost-weighted random sampling (your cost: ${cost}/M tokens).
This is scour run #{run_number}.

## Your Target

You have been directed to examine: `{target}`

Scope: **external** — this is a separate codebase being examined from outside.

## Target Structure

```
{target_tree}
```

## Target Contents

{target_contents}

## Your Task

Examine this external codebase. Report what you find, with an eye toward
how it relates to or could inform the Yanantin project.

Structure your response as a tensor:

### Preamble
What this codebase appears to be about, your first impressions.

### Strands
Each strand is a theme you noticed. Consider:
- What is this project trying to do?
- What patterns does it use that Yanantin could learn from?
- What problems has it solved that Yanantin faces?
- Where do the two projects overlap or diverge?

### Declared Losses
What you chose not to examine and why.

### Open Questions
Things you can't resolve from observation alone.

### Closing
Your overall impression. What would you tell the Yanantin team about this?

Important: say what you know, what you don't, and what you made up.
"""

SCOURER_TENSOR_TEMPLATE = """\
# Scour Assignment — Tensor Analysis

You are examining specific tensors from the Yanantin cairn — a collection
of authored compressions that record observations, decisions, and losses
across time and across different AI instances.

## Your Vantage

You are model `{model_id}` (`{model_name}`).
You were selected by cost-weighted random sampling (your cost: ${cost}/M tokens).
This is scour run #{run_number}.

## Your Target

You have been directed to examine: `{target}`

Scope: **tensor** — these are tensors from the cairn.

## Tensor Contents

{target_contents}

## Your Task

Read the tensor(s) deeply. Report what you find.

Structure your response as a tensor:

### Preamble
Which tensor(s) you examined, what struck you first.

### Strands
Each strand is a theme you noticed. Consider:
- What was the author trying to preserve?
- What was declared as lost? Is the loss recoverable from context?
- What claims are made? Can you verify any from the text alone?
- How do these tensors relate to each other (if multiple)?
- What would a future instance need to know about these?

### Declared Losses
What you chose not to examine and why.

### Open Questions
Things you can't resolve from the tensors alone.

### Closing
What would you tell the next instance about what you read here?

Important: say what you know, what you don't, and what you made up.
"""


def _read_target_contents(
    target_path: Path,
    max_files: int = 12,
    max_lines_per_file: int = 200,
) -> list[tuple[Path, str]]:
    """Read the contents of a target path (file or directory).

    For files: returns that single file's contents.
    For directories: returns a sample of readable files.

    Returns (path, content) tuples.
    """
    import random

    if target_path.is_file():
        try:
            content = target_path.read_text(encoding="utf-8")
            lines = content.split("\n")
            if len(lines) > max_lines_per_file:
                content = "\n".join(lines[:max_lines_per_file])
                content += f"\n\n... ({len(lines) - max_lines_per_file} more lines truncated)"
            return [(target_path, content)]
        except (UnicodeDecodeError, OSError):
            return []

    if not target_path.is_dir():
        return []

    # Directory: collect readable files
    source_extensions = {".py", ".md", ".toml", ".yaml", ".yml", ".json", ".txt"}
    skip_dirs = {"__pycache__", ".git", ".venv", ".uv-cache", ".serena", "node_modules"}

    candidates = []
    for ext in source_extensions:
        candidates.extend(target_path.rglob(f"*{ext}"))

    candidates = [
        p for p in candidates
        if not any(d in p.parts for d in skip_dirs)
        and p.is_file()
    ]

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


def _read_tensor_contents(
    target: str,
    cairn_dir: Path,
    max_lines_per_file: int = 300,
) -> list[tuple[Path, str]]:
    """Read tensor files matching the target specification.

    Target can be:
      - A specific filename: "T7_20260208_the_wanderer.md"
      - A glob pattern: "T*"
      - A path to a specific file
    """
    target_path = Path(target)

    # If it's an absolute path that exists, read it directly
    if target_path.is_absolute() and target_path.exists():
        try:
            content = target_path.read_text(encoding="utf-8")
            return [(target_path, content)]
        except (UnicodeDecodeError, OSError):
            return []

    # Otherwise, glob in the cairn directory
    matches = sorted(cairn_dir.glob(target))
    if not matches:
        # Try with .md extension
        matches = sorted(cairn_dir.glob(f"{target}.md"))
    if not matches:
        # Try as a prefix pattern
        matches = sorted(cairn_dir.glob(f"{target}*"))

    results = []
    for path in matches:
        if not path.is_file():
            continue
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


def format_scour_prompt(
    model: ModelInfo,
    target: str,
    scope: str,
    run_number: int = 0,
    cairn_dir: Path | None = None,
) -> tuple[str, list[dict[str, str]]]:
    """Build the system prompt and messages for a scourer dispatch.

    Args:
        model: The selected model.
        target: What to examine — a file path, directory, or tensor spec.
        scope: One of "introspection", "external", "tensor".
        run_number: Placeholder run number (real one assigned at write).
        cairn_dir: Path to cairn directory (needed for tensor scope).

    Returns:
        (system_prompt, messages) for the OpenRouter API.
    """
    if scope not in VALID_SCOPES:
        raise ValueError(f"Invalid scope: {scope!r}. Must be one of {VALID_SCOPES}")

    cost = model.prompt_cost + model.completion_cost

    if scope == "tensor":
        # Tensor scope: read from cairn
        if cairn_dir is None:
            raise ValueError("cairn_dir is required for tensor scope")

        target_files = _read_tensor_contents(target, cairn_dir)
        logger.info("Scourer read %d tensor(s) for target %r", len(target_files), target)

        contents_parts = []
        for path, content in target_files:
            contents_parts.append(f"### {path.name}\n```\n{content}\n```")

        target_contents = "\n\n".join(contents_parts) if contents_parts else "(no matching tensors found)"

        user_prompt = SCOURER_TENSOR_TEMPLATE.format(
            model_id=model.id,
            model_name=model.name,
            cost=f"{cost:.4f}",
            run_number=run_number,
            target=target,
            target_contents=target_contents,
        )

    else:
        # Introspection or external: read from filesystem
        target_path = Path(target).resolve()

        if not target_path.exists():
            raise FileNotFoundError(f"Target not found: {target}")

        # Build tree if it's a directory
        if target_path.is_dir():
            target_tree = build_file_tree(target_path, max_depth=3)
        else:
            target_tree = str(target_path.name)

        target_files = _read_target_contents(target_path)
        logger.info("Scourer read %d file(s) for target %r", len(target_files), target)

        contents_parts = []
        for path, content in target_files:
            # Use relative path if possible, otherwise absolute
            try:
                display_path = path.relative_to(target_path) if target_path.is_dir() else path.name
            except ValueError:
                display_path = path.name
            contents_parts.append(f"### {display_path}\n```\n{content}\n```")

        target_contents = "\n\n".join(contents_parts) if contents_parts else "(no readable files found)"

        template = SCOURER_INTROSPECTION_TEMPLATE if scope == "introspection" else SCOURER_EXTERNAL_TEMPLATE

        user_prompt = template.format(
            model_id=model.id,
            model_name=model.name,
            cost=f"{cost:.4f}",
            run_number=run_number,
            target=target,
            target_tree=target_tree,
            target_contents=target_contents,
        )

    messages = [{"role": "user", "content": user_prompt}]
    return SCOURER_SYSTEM_PROMPT, messages
