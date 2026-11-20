"""Question capture for the register (arango-objects collection `questions`).

The register (scripts/seed_questions.py) is yanantin's requirements and evaluation
set: real questions, with who asked, where they came from, and whether yanantin can
answer them. Captured questions arrive unjudged; a steward judges coverage later.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

COLLECTION = "questions"
TENANTS = ("human", "instance", "commons")


def question_doc(text: str, *, asked_by: str, verbatim: bool, context: str | None,
                 outcome: str | None, project: str | None, now: datetime | None = None) -> dict:
    if asked_by not in TENANTS:
        raise ValueError(f"asked_by must be one of {TENANTS}, not {asked_by!r}")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    doc = {
        "_key": f"q-{now:%Y%m%d}-{uuid.uuid4().hex[:8]}",
        "text": text.strip(), "tenant": asked_by, "verbatim_tony": bool(verbatim),
        "source": {"kind": "captured", "project": project},
        "recorded": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "recorded_by": "find MCP record_question",
        "coverage": {"answerable_today": "unjudged"},
    }
    if context:
        doc["context"] = context.strip()
    if outcome:
        doc["outcome"] = outcome.strip()
    return doc
