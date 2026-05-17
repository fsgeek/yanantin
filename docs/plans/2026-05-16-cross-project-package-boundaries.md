# Cross-Project Package Boundaries

Date: 2026-05-16

Status: draft for review

Projects:

- Yanantin: anchored memory substrate
- Willay: public attestation and receipt system
- Pukara: storage-confidentiality gateway

## Purpose

Yanantin, Willay, and Pukara currently grew together. That was useful while the
ideas were still finding their shape, but the projects now need clearer public
installation and dependency boundaries.

The goal is not to separate the ideas. The goal is to make each package's
public promise legible:

- Yanantin stores and retrieves authored, anchored memory.
- Willay creates and verifies attestations about records, claims, and content.
- Pukara reduces what third-party storage providers can learn from stored
  schema and label structure.

These projects should compose, but each should remain useful on its own.

## Ayni Principle

The public package work should preserve ayni: the documentation, tools, and
interfaces should give something useful before asking the user to understand
the whole system.

In practice, that means:

- each project has a small, successful first run;
- each README tells newcomers what the package is, what it is not, and where to
  go next;
- optional integrations are presented as invitations, not hidden requirements;
- threat models and limitations are stated plainly;
- research context is available without making the first path feel like a
  literature review;
- examples use local, inspectable behavior before hosted services.

## Target Dependency Shape

Desired core dependency graph:

```text
Pukara    -> Yanantin interface/models for protected storage
Yanantin  -> no required Willay dependency
Willay    -> no required full Yanantin memory dependency long term

Optional bridges:

Yanantin + Willay
Yanantin + Pukara
Willay + Yanantin/Pukara
```

Near-term acceptable state:

```text
Willay depends on yanantin>=0.1.1 for shared epistemic models.
Yanantin treats Willay as an optional integration only.
Pukara depends on Yanantin because it implements a protected Apacheta gateway.
```

Long-term cleaner state:

```text
Shared epistemic primitives live in a small stable layer.
Yanantin and Willay both depend on that layer.
Integration code lives behind extras or bridge packages.
```

## Project Responsibilities

### Yanantin

Yanantin is the memory system.

It owns:

- tensors as authored memory artifacts;
- temporal, location, relational, and context anchors;
- graph-structured memory traversal;
- activity/fact streams;
- memory-oriented tools for finding, walking, composing, and recovering;
- optional attestation metadata on records.

It does not own:

- public notary service deployment;
- canonical receipt verification as a standalone product;
- storage-provider threat mitigation as its core purpose.

### Willay

Willay is the attestation system.

It owns:

- receipt records;
- canonical serialization and hashing;
- hash-chained ledgers;
- portable receipt bundles;
- local receipt verification;
- public or independent attestor operation;
- future high-assurance profiles, including hybrid or post-quantum
  attestations.

It does not own:

- memory graph traversal;
- tensor selection or memory recall;
- storage schema obfuscation.

### Pukara

Pukara is the storage-confidentiality gateway.

It owns:

- the security boundary between clients and storage providers;
- API access to protected stores;
- semantic-label mapping and storage obfuscation;
- least-privilege database access;
- operational deployment as a service.

It does not own:

- memory semantics;
- attestation semantics;
- record authorship policy beyond enforcing the configured boundary.

## Trust Postures

The projects should document these as separate modes rather than blending them:

| Mode | What it gives | What it does not give |
| --- | --- | --- |
| Yanantin local memory | Authored memory with local trust | External evidence that a record existed |
| Yanantin + Willay | Memory records with attestable evidence | Independent attestor unless Willay is independent |
| Independent Willay | External attestation by another service/operator | Memory graph traversal |
| Pukara-protected storage | Reduced semantic leakage to storage providers | Content encryption or attestation |
| High-assurance Willay | Stronger long-horizon evidence | Commodity deployment simplicity |

## Package Boundary Options

### Option A: Separate Repos, Optional Bridges

Keep current repositories. Tighten dependencies and public docs.

Pros:

- lowest immediate process cost;
- preserves project identities;
- easy to publish independently;
- keeps Willay's independence visible.

Cons:

- shared epistemic models remain coupled until extracted;
- integration code can drift without explicit bridge discipline.

### Option B: Shared `yanantin-core` Or `yanantin-epistemics`

Extract minimal primitives:

- frozen base model policy;
- provenance envelope;
- declared losses;
- epistemic metadata;
- maybe canonical serialization helpers if both projects need them.

Pros:

- cleanest long-term dependency graph;
- Willay can verify receipts without importing full memory substrate;
- Yanantin keeps memory focus.

Cons:

- extra package and release choreography;
- premature if public API is still moving.

### Option C: Bridge Package

Create a bridge package later, for example `yanantin-willay`.

It owns:

- receipt-to-tensor conversion;
- Chasqui-to-Willay adapter;
- Willay receipt mirroring into Apacheta/Pukara;
- integration tests spanning both projects.

Pros:

- pure cores;
- explicit integration ownership.

Cons:

- another package/repo;
- likely premature before the basic public packages are clean.

## Recommended Path

Use a staged approach:

1. Keep repositories separate.
2. Make Willay independently understandable and installable.
3. Keep Yanantin focused on memory.
4. Make Willay usage in Yanantin optional and guarded.
5. Make Pukara independently installable as a security gateway.
6. Defer shared-core extraction until at least one public release cycle proves
   the stable primitive set.

## First Migration Pass

### Yanantin

- Document that attestation is optional evidence for memory records.
- Keep Willay imports out of Yanantin core.
- Identify all Yanantin-to-Willay integrations.
- Decide whether those integrations live under an optional extra, a bridge
  namespace, or a later bridge package.
- Continue memory-tool work around anchors, graph traversal, and recall.

### Willay

- Add a public README and install path.
- Fix source-distribution contents.
- Depend on `yanantin>=0.1.1` as the short-term shared model source.
- Mark Yanantin tensor conversion and Pukara mirroring as integrations.
- Define a portable verifier path that works without Yanantin runtime services.

### Pukara

- Add packaging/install docs.
- Decide whether Pukara publishes as an installable package and/or deployable
  service image.
- Document schema-map lifecycle, mapping database backup, and key handling.
- Clarify that Pukara is a storage-confidentiality gateway, not a memory
  system.

## Open Questions

- Should shared epistemic primitives eventually be `yanantin-core`,
  `yanantin-epistemics`, or remain inside Yanantin?
- Should the Yanantin/Willay bridge be an optional extra or a separate package?
- Should Pukara support non-Yanantin clients in the first public install story,
  or stay Apacheta-specific until the gateway is mature?
- What is the minimum useful portable Willay verifier?
- Which claims should be made about long-horizon security before
  post-quantum/hardware-backed profiles exist?

## Non-Goals

- Do not merge Willay into Yanantin.
- Do not make attestation mandatory for Yanantin memory.
- Do not make Pukara mandatory for local Yanantin use.
- Do not split into many packages before the current public doorways are clear.
- Do not move user or AI-generated work already in progress in Pukara without
  reviewing it separately.

## Review Points

Tony should decide:

- Whether the target dependency graph matches the intended philosophy.
- Whether Pukara should be explicitly positioned beyond Yanantin from the first
  public version.
- Whether shared epistemic primitives are worth extracting soon or should wait.
- Which trust postures should be named in public docs.
