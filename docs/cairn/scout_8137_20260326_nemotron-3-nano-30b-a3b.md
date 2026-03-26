<!-- Chasqui Scout Tensor
     Run: 8137
     Model: nvidia/nemotron-3-nano-30b-a3b (NVIDIA: Nemotron 3 Nano 30B A3B)
     Cost: prompt=$5e-08/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 5152, 'completion_tokens': 4000, 'total_tokens': 9152, 'cost': 0.0010576, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0010576, 'upstream_inference_prompt_cost': 0.0002576, 'upstream_inference_completions_cost': 0.0008}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-26T21:38:38.237826+00:00
     GenerationID: gen-1774561056-qBwbAItYU5rPlJvTP6ZV
     Dispatch: verify
     Claim: There is no evidence within the provided file to support the existence of a second `scout.py` in that directory.
     ClaimFile: src/yanantin/chasqui/scout.py
     ClaimBy: bytedance-seed/seed-1.6-flash
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_4140_20260303_seed-1.6-flash.md
-->

We need to verify claim: "There is no evidence within the provided file to support the existence of a second `scout.py` in that directory."

We have the file content of src/yanantin/chasqui/scout.py. We need to check if there is any evidence of a second scout.py in that directory. The directory is src/yanantin/chasqui/. The file itself is scout.py. Is there another scout.py? We can search within the file for references to other scout.py files. The claim says there is no evidence within the provided file to support existence of a second scout.py in that directory.

We need to examine the file content for any mention of another scout.py file. The file content includes imports, definitions, functions, but does it mention other scout.py files? Let's scan.

The file content:

```
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
and what you chose not to examine. Prefer the surprising over the obvious.
The fact that a file exists is not interesting. What the code reveals about
the system's intent, assumptions, or tensions — that is interesting.

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
{vantage_description}

## Local Structure

Here are the files in your area:

```
{file_tree}
```

## Selected Files

{file_contents}

## Your Task

You've been dropped into a specific part of the codebase. Don't describe
the directory structure — describe what the code is doing, what assumptions
it makes, and what tensions you notice. The obvious is already known —
what's surprising, confusing, or worth exploring further?

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


def gather_prior_findings(
    vantage: Path,
    root: Path,
    cairn_dir: Path | None = None,
    max_findings: int = 8,
) -> str:
    """Collect verified claims about files in a vantage's area.

    Reads edge files from docs/cairn/edges/ and filters for claims
    about files under the vantage directory. Returns a human-readable
    summary for injection into the scout prompt.

    Returns empty string if no edges exist or none match the vantage.
    """
    import json

    if cairn_dir is None:
        cairn_dir = root / "docs" / "cairn"

    edges_dir = cairn_dir / "edges"
    if not edges_dir.is_dir():
        return ""

    try:
        vantage_rel = str(vantage.relative_to(root))
    except ValueError:
        return ""

    findings: list[str] = []
    for edge_file in sorted(edges_dir.glob("*.json"), reverse=True):
        if len(findings) >= max_findings:
            break
        try:
            edge = json.loads(edge_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        claim_file = edge.get("claim_file", "")
        if not claim_file.startswith(vantage_rel):
            continue

        relation = edge.get("relation", "?")
        claim_text = edge.get("claim_text", "")
        verified_by = edge.get("verified_by", "unknown")

        # Truncate long claims
        if len(claim_text) > 120:
            claim_text = claim_text[:117] + "..."

        status = "CONFIRMED" if relation == "confirms" else "DENIED"
        findings.append(f"- [{status}] {claim_text} (verified by `{verified_by}`)")

    if not findings:
        return ""

    header = f"## Prior Findings in Your Area\n\nOther scouts have made claims about files here. These have been verified:\n\n"
    return header + "\n".join(findings) + "\n\nPush past what's already known. What did they miss?\n"


def pick_vantage_directory(
    root: Path,
    coverage_map: dict | None = None,
) -> Path:
    """Pick a random starting directory for a scout, weighted by coverage.

    Instead of always showing the full project tree, scouts get dropped
    into a specific subtree. This breaks mode collapse by giving each
    scout a genuinely different vantage point.

    Directories containing more unreviewed or stale files get higher
    weight. The project root is excluded — scouts always land somewhere
    specific.

    Returns an absolute path to the chosen directory.
    """
    import random

    source_extensions = {".py", ".md", ".toml", ".yaml", ".yml"}
    skip_dirs = {"__pycache__", ".git", ".venv", ".uv-cache", ".serena",
                 "node_modules", ".pytest_cache"}

    # Collect all directories that contain source files
    dir_files: dict[Path, list[Path]] = {}
    for ext in source_extensions:
        for path in root.rglob(f"*{ext}"):
            if any(d in path.parts for d in skip_dirs):
                continue
            if not path.is_file():
                continue
            parent = path.parent
            # Skip project root and cairn (7000+ reports is not useful)
            if parent == root:
                continue
            if "cairn" in parent.parts:
                continue
            dir_files.setdefault(parent, []).append(path)

    if not dir_files:
        return root  # Fallback: nowhere to go

    dirs = list(dir_files.keys())

    if coverage_map is not None:
        from yanantin.chasqui.coverage import coverage_weights
        # Weight each directory by the sum of its files' staleness
        dir_weights = []
        for d in dirs:
            files = dir_files[d]
            weights = coverage_weights(files, coverage_map, root)
            dir_weights.append(sum(weights))
    else:
        dir_weights = [float(len(dir_files[d])) for d in dirs]

    return random.choices(dirs, weights=dir_weights, k=1)[0]


def select_files_for_scout(
    root: Path,
    max_files: int = 8,
    max_lines_per_file: int = 150,
    coverage_map: dict | None = None,
    activity_map: dict[str, datetime] | None = None,
    vantage: Path | None = None,
) -> list[tuple[Path, str]]:
    """Select a sample of project files for the scout to read.

    When vantage is provided, candidates are restricted to that subtree.
    This gives scouts a focused view rather than the full project.

    When coverage_map is provided, uses weighted random selection based
    on coverage freshness: files never reviewed (epoch 0) get maximum
    priority. Recently reviewed files still have some chance but lower
    weight. Without a coverage map, falls back to uniform random.

    When activity_map is also provided, files recently modified on disk
    get a recency boost on top of their coverage weight. Files changed
    today get ~2x weight; files unchanged for 30+ days get no boost.
    The coverage signal dominates — activity breaks ties.

    Args:
        root: Project root directory.
        max_files: Maximum number of files to select.
        max_lines_per_file: Truncate files longer than this.
        coverage_map: {relative_path: last_reviewed_datetime} from
            coverage.scan_cairn_coverage(). When provided, enables
            coverage-weighted selection.
        activity_map: {relative_path: last_modified_datetime} from
            the activity stream. When provided alongside coverage_map,
            boosts recently-changed files.
        vantage: Optional subtree to constrain file selection to.

    Returns (path, content) tuples.
    """
    import random

    source_extensions = {".py", ".md", ".toml", ".yaml", ".yml"}
    search_root = vantage if vantage is not None else root
    candidates = []

    for ext in source_extensions:
        candidates.extend(search_root.rglob(f"*{ext}"))

    # Filter out noise
    skip_dirs = {"__pycache__", ".git", ".venv", ".uv-cache", ".serena"}
    candidates = [
        p for p in candidates
        if not any(d in p.parts for d in skip_dirs)
        and p.is_file()
    ]

    # Weighted selection (coverage-aware) or uniform random
    k = min(max_files, len(candidates))
    if coverage_map is not None and candidates:
        from yanantin.chasqui.coverage import coverage_weights
        weights = coverage_weights(candidates, coverage_map, root)

        # Blend activity freshness: recently-changed files get a boost
        if activity_map is not None:
            now = datetime.now(timezone.utc)
            for i, path in enumerate(candidates):
                try:
                    rel = str(path.relative_to(root))
                except ValueError:
                    continue
                mtime = activity_map.get(rel)
                if mtime is None:
                    continue  # Unknown activity — no boost
                activity_age_seconds = (now - mtime).total_seconds()
                activity_age_days = activity_age_seconds / 86400
                recency_boost = max(0.0, 1.0 - activity_age_days / 30)
                weights[i] *= (1 + recency_boost)

        # random.choices with weights, then deduplicate
        # (choices can repeat, so oversample and deduplicate)
        seen: set[Path] = set()
        selected: list[Path] = []
        attempts = 0
        while len(selected) < k and attempts < k * 5:
            picks = random.choices(candidates, weights=weights, k=1)
            if picks[0] not in seen:
                seen.add(picks[0])
                selected.append(picks[0])
            attempts += 1
    else:
        selected = random.sample(candidates, k)

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
    coverage_map: dict | None = None,
    activity_map: dict[str, datetime] | None = None,
) -> tuple[str, list[dict[str, str]]]:
    """Build the system prompt and messages for a scout dispatch.

    Picks a random vantage directory (coverage-weighted) and drops the
    scout there. The scout sees only the local subtree and files from
    that area, breaking the mode collapse that comes from every scout
    seeing the same full project tree.

    Returns (system_prompt, messages) for the OpenRouter API.
    """
    vantage = pick_vantage_directory(root, coverage_map=coverage_map)
    file_tree = build_file_tree(vantage)
    selected_files = select_files_for_scout(
        root, coverage_map=coverage_map, activity_map=activity_map,
        vantage=vantage,
    )

    # If the vantage directory had no files (unlikely but possible),
    # fall back to project-wide selection
    if not selected_files:
        vantage = root
        file_tree = build_file_tree(root)
        selected_files = select_files_for_scout(
            root, coverage_map=coverage_map, activity_map=activity_map,
        )

    file_contents_parts = []
    for path, content in selected_files:
        rel = path.relative_to(root)
        file_contents_parts.append(f"### {rel}\n```\n{content}\n```")

    file_contents = "\n\n".join(file_contents_parts)

    cost = model.prompt_cost + model.completion_cost

    # Describe the vantage to the scout
    if vantage != root:
        try:
            rel_vantage = vantage.relative_to(root)
        except ValueError:
            rel_vantage = vantage
        vantage_description = f"You were dropped into `{rel_vantage}/`."
    else:
        vantage_description = "You are viewing the full project."

    # Collect prior verified claims about this area
    prior_findings = gather_prior_findings(
        vantage, root, cairn_dir=root / "docs" / "cairn",
    )

    user_prompt = SCOUT_TEMPLATE.format(
        model_id=model.id,
        model_name=model.name,
        cost=f"{cost:.4f}",
        run_number=run_number,
        file_tree=file_tree,
        file_contents=file_contents,
        vantage_description=vantage_description,
    )

    # Inject prior findings between the file contents and the task
    if prior_findings:
        user_prompt += "\n" + prior_findings

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
Disagreement