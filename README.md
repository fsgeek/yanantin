# Yanantin

Yanantin is a Python package for storing authored memory artifacts with
provenance, declared limits, and immutable history.

The package grew out of research on human-AI collaboration, but the small
installed core is meant to be usable without reading the research archive. The
first stable path is Apacheta: a tensor store for authored compressions. A
tensor is not a transcript, a vector embedding, or a generic log entry. It is a
record of what an author chose to preserve, what they chose to leave out, and
how that record relates to prior records. Note: Apacheta, by design, is an
immutable store - the primitives allow creating and accessing new records, but
not changing them.

## Quick Start

Install the package:

If you prefer to use old tools:

```bash
pip install yanantin
```

for those using uv (the modern package manager):

```bash
uv add yanantin
```

Create and store a tensor in memory:

```python
from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.apacheta.models import (
    DeclaredLoss,
    LossCategory,
    ProvenanceEnvelope,
    StrandRecord,
    TensorRecord,
)

store = InMemoryBackend()

tensor = TensorRecord(
    provenance=ProvenanceEnvelope(
        author_instance_id="readme-example",
        author_model_family="human",
    ),
    preamble="A small authored memory.",
    strands=(
        StrandRecord(
            strand_index=0,
            title="Observation",
            content="The in-memory backend is enough for local experiments.",
            topics=("quickstart", "apacheta"),
        ),
    ),
    declared_losses=(
        DeclaredLoss(
            what_was_lost="Persistence",
            why="This example uses the in-memory backend.",
            category=LossCategory.PRACTICAL_CONSTRAINT,
            severity=0.2,
        ),
    ),
    lineage_tags=("example",),
)

store.store_tensor(tensor)
round_tripped = store.get_tensor(tensor.id)

print(round_tripped.preamble)
print(round_tripped.strands[0].content)
```

There is also a runnable version in
[`examples/minimal_in_memory.py`](examples/minimal_in_memory.py).

## What This Package Is

Yanantin currently exposes a small core:

- `yanantin.apacheta.models`: Pydantic models for tensors, provenance,
  declared losses, composition records, and related concepts.
- `yanantin.apacheta.interface`: the storage interface that backends implement.
- `yanantin.apacheta.backends.memory`: an in-memory backend for examples, tests,
  and local experimentation.
- `yanantin.activity`: append-only fact records and memory anchors.
- `yanantin.query`: structured queries over activity streams.

The rest of the repository contains research systems, operational tooling,
experiments, and archives. They are useful, but they are not the first thing a
new package user needs.

## What This Package Is Not

Yanantin is not a vector database, a RAG framework, a transcript archive, or a
general-purpose ORM. It is designed around a different unit of memory: an
authored compression with provenance and declared loss.

## Design Principle: Ayni

This project uses the Andean principle of ayni, or reciprocal care, as a product
principle. The package asks users for trust, time, and attention; in return it
should give clear orientation, honest limits, recoverable examples, and respectful
failure modes.

That principle shows up in practical ways:

- examples should run without production infrastructure;
- stable APIs should be marked;
- experimental APIs should not pretend to be stable;
- limitations should be declared close to the feature they affect;
- error messages and documentation should give users a next step.

See [`docs/principles.md`](docs/principles.md) for the longer version.

## Stability

Yanantin is currently a `0.x` package. The core APIs are being separated from
the research surface. If you are using the package as a dependency, start with
the modules listed in [`docs/stability.md`](docs/stability.md).

Backend status in brief:

| Backend | Status | Intended use |
| --- | --- | --- |
| In-memory Apacheta | Supported core | examples, tests, local prototypes |
| ArangoDB Apacheta | Active, infrastructure-backed | persistent deployments by users who provision ArangoDB |
| DuckDB Apacheta | Limited/deferred areas | compatibility and historical work, not the default production path |
| Activity in-memory | Supported core | examples, tests, local prototypes |
| Activity DuckDB/ArangoDB | Active but more operational | persistent fact streams |

## Repository Map

- `src/yanantin/apacheta/`: tensor models, storage interface, and backends.
- `src/yanantin/activity/`: raw fact stream and memory anchors.
- `src/yanantin/query/`: structured queries over activity facts.
- `src/yanantin/collector/`: collectors for environment and filesystem data.
- `src/yanantin/experiments/`: memory-tool experiment harness.
- `src/yanantin/chasqui/`: scout and verification pipeline.
- `docs/`: design notes, specifications, findings, and research archive.
- `tests/red_bar/`: architectural invariant tests.

## More Reading

- [`docs/glossary.md`](docs/glossary.md): project vocabulary.
- [`docs/stability.md`](docs/stability.md): supported and experimental APIs.
- [`docs/principles.md`](docs/principles.md): design principles and ayni.
- [`docs/apacheta.md`](docs/apacheta.md): deeper Apacheta design background.
- [`docs/blueprint.md`](docs/blueprint.md): broad project map.
- Tony Mason, ["From Scalars to Tensors: Declared Losses Recover Epistemic
  Distinctions That Neutrosophic Scalars Cannot Express"](https://arxiv.org/abs/2604.09602):
  optional research background on declared losses and tensor-structured
  epistemic output.
