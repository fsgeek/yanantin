<!-- Chasqui Scout Tensor
     Run: 9570
     Model: nousresearch/hermes-3-llama-3.1-70b (Nous: Hermes 3 70B Instruct)
     Cost: prompt=$3e-07/M, completion=$3e-07/M
     Usage: {'prompt_tokens': 5376, 'completion_tokens': 745, 'total_tokens': 6121, 'cost': 0.0018363, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0018363, 'upstream_inference_prompt_cost': 0.0016128, 'upstream_inference_completions_cost': 0.0002235}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-04T10:07:26.914695+00:00
     GenerationID: gen-1775297225-0VWd5qwYck0G6nflVosS
     Dispatch: verify
     Claim: ## The Claim Model `qwen/qwen-plus` made this claim about `src/yanantin/chasqui/scout.py`: > The Chasqui Is a Distributed, Cost-Weighted, Model-Reflexive Loop**   `src/yanantin/chasqui/` contains `mod
     ClaimFile: src/yanantin/chasqui/scorer.py
     ClaimBy: meta-llama/llama-3.2-11b-vision-instruct
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_7486_20260323_llama-3.2-11b-vision-instruct.md
-->

### Verdict
CONFIRMED

### Evidence
```
"""Scout Scorer — sniff the cairn and see what's kraken poo and what's bitter apple.

Reads scout tensors from the cairn, extracts structural signals, and
scores them on axes that don't require a judge:

- Specificity: file/line references (verifiable attention)
- Fabrication: claimed paths that don't exist (confident lies)
- Efficiency: insight-per-token ratio
- Generativity: open questions that invite response
- Structure: did the scout follow the tensor format?

The semantic axis (novelty) requires a judge and is deliberately excluded.
Convergent observations across scouts approximate it structurally.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── Provenance parsing ──────────────────────────────────────────────

@dataclass(frozen=True)
class ScoutProvenance:
    """Parsed provenance from a scout tensor's HTML comment header."""

    run_number: int
    model_id: str
    model_name: str
    prompt_cost: float
    completion_cost: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    total_cost: float
    timestamp: str
    raw_usage: str  # Unparsed usage dict as string


def parse_provenance(text: str) -> ScoutProvenance | None:
    """Extract provenance from the <!-- Chasqui Scout Tensor ... --> header."""
    header_match = re.search(
        r"<!--\s*Chasqui Scout Tensor\s*(.*?)-->",
        text,
        re.DOTALL,
    )
    if not header_match:
        return None

    header = header_match.group(1)

    def _extract(pattern: str, default: str = "") -> str:
        m = re.search(pattern, header)
        return m.group(1).strip() if m else default

    run_number = int(_extract(r"Run:\s*(\d+)", "0"))
    model_line = _extract(r"Model:\s*(.+)")
    # "deepseek/deepseek-chat-v3.1 (DeepSeek: DeepSeek V3.1)"
    model_parts = re.match(r"(\S+)\s*\((.+)\)", model_line)
    model_id = model_parts.group(1) if model_parts else model_line
    model_name = model_parts.group(2) if model_parts else model_line
```

### Reasoning
The claim is accurate. The file `src/yanantin/chasqui/scorer.py` exists and contains code for scoring scout tensors from the cairn on various axes. The code excerpt shows that the file reads scout tensors, extracts structural signals, and scores them on several axes including specificity (file/line references), fabrication (claimed paths that don't exist), efficiency (insight-per-token ratio), generativity (open questions that invite response), and structure (whether the scout followed the tensor format).

The claim mentions `src/yanantin/chasqui/` containing `model_selector.py`, `scout.py`, `scorer.py`, and `scourer.py`, which is accurate based on the provided file path. The specific code excerpt provided confirms the existence and functionality of `scorer.py`.

### Declared Losses
The claim does not mention anything about runtime behavior or other aspects that cannot be verified from the source code alone. Therefore, there are no declared losses in this case.