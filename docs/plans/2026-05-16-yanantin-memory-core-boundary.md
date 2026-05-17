# Yanantin Memory Core Boundary

Date: 2026-05-16

Status: draft for review

Parent plan:

- `docs/plans/2026-05-16-cross-project-package-boundaries.md`

## Purpose

Yanantin should remain the anchored memory system. Attestation can strengthen
the evidence attached to a record, but attestation is not Yanantin's core
purpose.

This plan defines how to keep Yanantin's package surface focused while still
allowing strong optional integrations with Willay and Pukara.

## Product Statement

Yanantin is an anchored memory service for authored memory artifacts.

It is not:

- a vector database;
- a RAG store;
- a conventional knowledge graph;
- a public attestation service;
- a storage-security gateway.

It is:

- episodic;
- graph structured;
- walkable;
- anchored by time, location, relationship, and context;
- explicit about provenance and declared loss.

## Ayni For New Users

Yanantin's first public path should make the memory idea feel approachable
without flattening it into a familiar but inaccurate category.

The docs and tools should:

- show one memory artifact being created, stored, and retrieved;
- introduce anchors through examples before formal vocabulary;
- make optional attestation visible but not required;
- make storage choices visible but not dominant;
- invite deeper research reading after the first success.

## Core Responsibilities

Yanantin core owns:

- `apacheta.models`: tensor, strand, provenance, epistemic, and composition
  models;
- `apacheta.interface`: immutable memory storage contract;
- `activity`: raw fact streams and temporal memory anchors;
- `query`: structured access over activity streams;
- memory-oriented APIs for finding, walking, paging, freezing, and composing;
- storage backends that implement the memory contract.

Yanantin core should not require:

- Willay;
- Pukara;
- OpenRouter;
- live ArangoDB;
- any hosted attestation service.

## Anchor Roadmap

The memory story should be made more explicit around anchors:

| Anchor type | Meaning | First public shape |
| --- | --- | --- |
| Temporal anchor | What was true at or before a point in time | existing `MemoryAnchor`/`AnchorView` path |
| Location anchor | Where a record, file, event, or observation lived | new model or activity convention |
| Relational anchor | Which actors/entities participated | integrate with entity/event records |
| Context anchor | How a record was used or requested | query and tool-call recording |
| Attestation anchor | Evidence that a record existed or was evaluated | optional Willay receipt reference |

Attestation anchor should be optional. A tensor without a Willay receipt is
still a tensor; it simply has a different trust posture.

## Willay Boundary

Yanantin may integrate with Willay, but only outside core paths.

Current pattern to preserve:

- guarded imports;
- graceful degradation when Willay is absent;
- no package import failure if Willay is not installed.

Target pattern:

```text
yanantin core                no Willay dependency
yanantin[willay]             optional integration
yanantin.integrations.willay adapter code, if kept in repo
```

Potential integration points:

- Chasqui verification receipts;
- tensor existence attestations;
- claim/evidence receipts for tensor claims;
- memory-anchor freeze receipts;
- export of portable evidence bundles.

## Pukara Boundary

Yanantin may use Pukara as a protected storage path, but local Yanantin should
not require Pukara.

Target pattern:

```text
InMemoryBackend             first-use examples and tests
ArangoDBBackend             direct persistent backend
ApachetaGatewayClient       client for Pukara-protected deployments
Pukara                      separate service/package
```

Yanantin docs should explain Pukara as an optional security boundary for
deployments that do not want the database provider to see semantic labels.

## Package Surface Work

Near-term:

- Keep the new README orientation focused on memory.
- Add docs for memory anchors and trust postures.
- Audit imports for Willay dependencies.
- Consider an optional extra for Willay integration once concrete import points
  are identified.
- Avoid presenting `chasqui`, `experiments`, and large archives as the default
  package path.

Medium-term:

- Decide whether shared epistemic primitives stay inside Yanantin or move to a
  smaller package.
- Add public examples for memory anchors.
- Add examples for graph/walk memory once the API is stable.
- Document how an attested tensor differs from an unattested tensor.

## Tests And Invariants

Existing red-bar tests are a strength. Add or preserve invariants that express
the boundary:

- Yanantin imports without Willay installed.
- Core examples run without Pukara or ArangoDB.
- Attestation failure does not block memory writes unless explicitly requested.
- Optional integration tests are skipped when Willay/Pukara are absent.

## Open Questions

- What is the first public API for location, relational, and context anchors?
- Should attestation references live in tensor provenance, declared losses,
  composition edges, or a new relation type?
- Should Chasqui-to-Willay integration stay in Yanantin or move to a bridge
  package?
- Is `yanantin-core` worth extracting before more public users exist?

## First Implementation Pass

1. Inventory Willay imports in Yanantin.
2. Mark each as core, optional integration, or research-only.
3. Add missing docs around memory anchors and trust postures.
4. Add optional-extra plan if needed.
5. Keep runtime behavior unchanged until the boundary document is reviewed.

## Review Points

Tony should decide:

- Whether "anchored memory service" is the correct public phrase.
- Which anchor types should be named in the first public docs.
- Whether Yanantin should eventually expose an `attestation_anchor` model.
- Whether a bridge package is preferable to in-repo optional integration.
