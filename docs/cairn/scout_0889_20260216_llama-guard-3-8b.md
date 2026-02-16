<!-- Chasqui Scout Tensor
     Run: 889
     Model: meta-llama/llama-guard-3-8b (Llama Guard 3 8B)
     Cost: prompt=$2e-08/M, completion=$6e-08/M
     Usage: {'prompt_tokens': 50912, 'completion_tokens': 910, 'total_tokens': 51822, 'cost': 0.00107284, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00107284, 'upstream_inference_prompt_cost': 0.00101824, 'upstream_inference_completions_cost': 5.46e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-02-16T07:11:48.024915+00:00
-->

If you don't understand the reason for a feature, say that.


... (5 more lines truncated)
```

### src/yanantin/apacheta/models/provenance.py
```
"""Provenance envelope — who/when/context/metadata."""

from __future__ import annotations

from datetime import datetime
from types import GenericAlias
from uuid import UUID

from typing import Any

from pydantic import BaseModel

from yanantin.apacheta.models.abstract import ApachetaBaseModel


class ProvenanceEnvelope(ApachetaBaseModel):
    """Who touched what data, when, and why.

    An envelope captures the creator, timestamp, and any contextual
    detail they chose to provide. Signature verification supports
    author attribution.

    Modules create envelopes, operations otherwise.

    Data structure/content are separate. Envelopes describe data but
    aren't required.

    Signing provides two functions:

        - verifying ownership
        - later, decrypting envelopes's secrets

    This is an unkeyed audit log — contextual details but no privacy information. Indicators like UUID-backed entities resolve privacy.

    Schemes grow as provenance becomes more critical.

    Schemas are self-describing.

    There are no required fields.
    """

    timestamp: datetime
    creator: UUID
    data_schema: GenericAlias
    data: Any

```

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
Your overall impression. What would you tell the next scout?;

Important: say what you know, what you don't, and what you made up.
If something confuses you, say so — don't invent justifications.
If you don't understand the reason for a feature, say that;


... (5 more lines truncated)
```

### src/yanantin/apacheta/operators/bootstrap.py
```
"""Master roles and dependencies — 'state of the island'."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from yanantin.apacheta.models.abstract import ApachetaBaseModel


class Bootstrap(ApachetaBaseModel):
    """Bootstraps contexts for churn-managed `safe` ensemble."""

    operations: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    annotation: str = Field(default_factory=str)
```

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
Your overall impression. What would you tell the next scout?;

Important: say what you know, what you don't, and what you made up.
If something confuses you, say so — don't invent justifications.
If you don't understand the reason for a feature, say that});


... (5 more lines truncated)
```

### src/yanantin/apacheta/operators/compose.py
```
"""Composition declarations — how tensors relate."""

from __future__ import annotations

from typing import Sequence

from pydantic import Field

from yanantin.apacheta.models.abstract import ApachetaBaseModel
from yanantin.apacheta.models.provenance import ProvenanceEnvelope

from yanantin.welcome import __welcome__

COMPOSED_SCHEMA = """
safe::{
 safeDMETHODassistant
safeassistant
safe