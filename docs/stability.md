# Stability Policy

Yanantin is currently a `0.x` package. The repository contains both a package
core and an active research environment. This document marks the ground that is
intended to be safe for package users.

## Supported Core

These modules are the starting public surface:

| Module | Status | Notes |
| --- | --- | --- |
| `yanantin.apacheta.models` | Supported core | Pydantic models for tensors, provenance, epistemics, and composition records. |
| `yanantin.apacheta.interface` | Supported core | Abstract storage contract implemented by backends. |
| `yanantin.apacheta.backends.memory` | Supported core | In-memory backend for examples, tests, and local prototypes. |
| `yanantin.activity.models` | Supported core | Append-only fact and anchor models. |
| `yanantin.activity.store` | Supported core | Abstract activity stream store contract. |
| `yanantin.activity.backends.memory` | Supported core | In-memory activity stream backend. |
| `yanantin.query.models` | Supported core | Structured query models. |
| `yanantin.query.engine` | Supported core | Python-side query execution over any activity stream store. |

Supported core means the module is suitable for examples and downstream use,
with compatibility changes handled deliberately.

## Active But Operational

These modules are real, tested, and useful, but require more operational
context or external infrastructure:

| Module | Status | Notes |
| --- | --- | --- |
| `yanantin.apacheta.backends.arango` | Active | Persistent Apacheta backend. Requires provisioned ArangoDB credentials. |
| `yanantin.activity.backends.arango` | Active | Persistent activity stream backend. Requires provisioned ArangoDB credentials. |
| `yanantin.activity.backends.duckdb` | Active | File-backed activity stream backend. |
| `yanantin.infra` | Active | Local infrastructure setup and status tooling. |
| `yanantin.collector` | Active | Data collection pipeline and concrete collectors. |

Use these when you are ready to manage their dependencies and failure modes.

## Experimental Or Research Surface

These modules are part of the research system. They may be useful, but users
should expect faster change and more context-specific assumptions:

| Module | Status | Notes |
| --- | --- | --- |
| `yanantin.chasqui` | Research/operations | Scout, verifier, and analysis pipeline. |
| `yanantin.awaq` | Research/operations | Deterministic composition extraction from tensor prose. |
| `yanantin.jabberwock` | Research | Event-sourced entity resolution with deliberately nonstandard naming. |
| `yanantin.experiments` | Research | Memory-tool experiment harness and analysis support. |
| `yanantin.tinkuy` | Research/operations | Codebase audit and succession checks. |
| `tools/`, `experiments/`, `docs/cairn/` | Archive/lab | Useful for project work, not required for package use. |

## Backend Matrix

| Backend | Persistence | External service | Recommended first use |
| --- | --- | --- | --- |
| Apacheta in-memory | No | No | Yes |
| Apacheta ArangoDB | Yes | ArangoDB | After reading infra docs |
| Apacheta DuckDB | Partial/deferred areas | No | No |
| Activity in-memory | No | No | Yes |
| Activity DuckDB | Yes | No | For local fact streams |
| Activity ArangoDB | Yes | ArangoDB | For provisioned deployments |

## Compatibility Rules During 0.x

The project is still before a `1.0` API freeze. Until then:

- supported-core modules should avoid unnecessary breaking changes;
- breaking changes should be documented in release notes;
- model field removals should be avoided when a deprecation path is practical;
- experimental modules may change more freely;
- hidden mutation is not an acceptable migration strategy.

## What To Import

Prefer documented imports such as:

```python
from yanantin.apacheta.models import TensorRecord, StrandRecord
from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.activity import FactRecord
from yanantin.activity.backends.memory import InMemoryActivityStreamStore
from yanantin.query import QueryEngine, QuerySpec
```

Avoid depending on private helpers, generated artifacts, or research archive
file layout unless you are contributing to the research system itself.
