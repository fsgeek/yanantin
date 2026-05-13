"""Prompt template store for the memory-tool harness.

Templates are tiny YAML files — text plus an id. The content_hash
(12-char sha256 prefix) is the reproducibility key: even if the file is
renamed or edited, captured records still point at the exact text they
used via this hash.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, computed_field


def compute_template_id(text: str) -> str:
    """12-char hex sha256 prefix of the template's rendered text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


class PromptTemplate(BaseModel):
    """One prompt template. `text` is what gets sent; `content_hash` is its fingerprint."""

    model_config = ConfigDict(frozen=True)

    template_id: str
    description: str = ""
    text: str

    @computed_field  # type: ignore[misc]
    @property
    def content_hash(self) -> str:
        return compute_template_id(self.text)


def load_template(path: str | Path) -> PromptTemplate:
    """Load a template from a YAML file. Validates against the schema."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return PromptTemplate.model_validate(data)
