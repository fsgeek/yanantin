# Principles

Yanantin is built around memory that remains accountable to its author. The
same idea should apply to the package itself: public surfaces should be clear
about what they do, what they cannot do, and what a user can try next.

## Ayni

We use ayni, or reciprocal care, as a product principle.

The package asks users for trust, time, and attention. In return, it should
offer orientation, honest limits, examples that run, and failure modes that do
not leave users stranded.

For this project, ayni is not decoration. It is a practical test for design:

- A new user should be able to find the safe starting path quickly.
- A curious user should be able to go deeper without being forced into the
  research archive first.
- A production user should know which APIs are stable and which are not.
- A failure should name the missing prerequisite or violated contract when it
  can.
- A limitation should be documented as close as possible to the feature it
  affects.

## Authored Memory

Yanantin treats memory as authored. A tensor is not a raw dump and not an
automatic summary. It is a record of what an author chose to preserve.

That choice matters. Two authors can process the same source material and
produce different tensors. The difference is signal, not noise.

## Declared Loss

Every compression loses something. Yanantin prefers declared loss over hidden
loss.

A declared loss says what was left out, why it was left out, and how severe
that omission is. This lets later readers decide whether the artifact is useful
for their purpose instead of guessing what disappeared.

For research background on declared losses and tensor-structured epistemic
output, see Tony Mason, ["From Scalars to Tensors: Declared Losses Recover
Epistemic Distinctions That Neutrosophic Scalars Cannot
Express"](https://arxiv.org/abs/2604.09602).

## Provenance

Records should answer basic questions:

- Who or what authored this?
- When was it authored?
- What source or prior context was in scope?
- Which interface version shaped it?

Provenance is not bureaucracy. It is how later users recover trust boundaries.

## Immutability

Stored records are append-only. Corrections, dissents, negations, and new
understanding are new records that point at prior records.

This keeps history inspectable. It also avoids the false comfort of silent
mutation, where the current value hides how it came to be.

## Stable Ground Before Deep Terrain

The repository contains a research archive, experiment harnesses, generated
artifacts, and operational tooling. Those are valuable, but they should not be
the first surface a package user has to understand.

The package should provide stable ground first:

- a minimal installation path;
- a small supported API;
- examples that do not require production infrastructure;
- clear markers around experimental modules.

## Respectful Failure

Good software does not only succeed well. It fails with enough context for the
user to recover.

In practice, that means:

- optional dependencies should be documented and guarded;
- production backends should fail clearly when infrastructure is missing;
- examples should default to in-memory stores;
- deferred features should say they are deferred instead of pretending to work.
