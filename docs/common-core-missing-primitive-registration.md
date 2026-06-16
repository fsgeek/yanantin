# The Common Core's Missing Primitive: Dynamic Registration

*2026-06-16. Tony's question — "do we have the right common-core primitives?" — and the answer
the code gives: NO. The core is missing its load-bearing primitive (dynamic registration), so it
has to be padded with features (immutability, obfuscator, provenance) to look big enough to
justify itself. It isn't big enough — because the part that would make it load-bearing was never
built. This CORRECTS the conclusion in `docs/three-spaces-and-the-common-core.md` ("core already
extracted, just finish the branches") and REORDERS the roadmap critical path.*

## Tony's diagnosis (the felt symptom)

"New development is trying to shoehorn new work into the existing structure, which suggests the
existing structure isn't dynamic enough."

## What the code confirms

- **Indaleko's DB use was MUNDANE.** Basic ArangoDB ops; AQL as a (read-only) flexibility layer.
  ALL the real complexity lived in CONFIGURATION — collections, schema, indices, views. Tony's
  settled conclusion: **one static config collection, everything else dynamically constructed via
  a REGISTRATION mechanism.** That registration mechanism is the core's real job.
- **It does not exist.** No `register_collection` / schema / index / view mechanism in the storage
  core (`grep` finds only app-level registries in `experiments/` and `jabberwock/`, unrelated).
- **The shoehorn is visible in TWO hardcoded static tuples:**
  `apacheta/backends/arango.py:68 _SEMANTIC_COLLECTIONS` and
  `activity/backends/arango.py:30 _SEMANTIC_COLLECTIONS = ("activity_facts","activity_anchors")`.
  Both loop `_ensure_collections()` over a hand-maintained list. When the ACTIVITY space came into
  existence it did NOT register — it **copied the pattern and forked its own static tuple.**
- **gh #1 (April 2026, 2 months untouched): "Replace static collection lists with dynamic
  registration."** This is the missing primitive, named long ago, never built. It is NOT
  housekeeping — it is the core's load-bearing piece.
- **New structural things cost N backend edits.** The provenance-edge work added
  `store_provenance_edge` by hand across arango(+49)/duckdb(+12)/memory(+13). A new edge type =
  edit every backend, not register once.

## Why this re-explains every symptom we found

The blob-recorder (shoehorning file data into the authored-tensor shape — no file-record
collection to register), the activity stack forking its own `FactRecord` + 3 backends (couldn't
dynamically accommodate a new regime, so it forked), the synthetic-twin gaps, the per-backend hand
edits — ALL are the same thing: **no registration seam to extend, so new work edits static lists
or forks stacks.** The structure isn't "a bit too static"; it is MISSING the mechanism that makes
it dynamic, and compensating with static lists + parallel stacks.

## The features are not the core (and one may be theater)

Immutability, obfuscator, provenance are FEATURES that sit ON TOP of registration, not the core:
- **Immutability** is right for AI-memory (forces the HONESTY that AI entities have immutable
  memories — unlike humans; Tony) and arguable for file info (versioning). BUT Tony's caveat:
  immutable-store-as-versioning is THEATER if the underlying storage won't surface the prior
  version — "not as simple or obvious as it might seem." Keep the caveat live; do not assume
  immutability is free common-core goodness.
- The point: a pile of features masquerading as a core is why it "feels too small to justify its
  existence." The thing that justifies it is registration, which is absent.

## Roadmap correction — registration is PREREQUISITE to A1

Prior roadmap put A1 (#17 storage object) first. **But #17 is another collection/record-type;
adding it the current way means editing the static tuples a THIRD time — deepening the exact debt.
Building A1 before registration deepens the shoehorn.** Corrected order:

- **C0 (new critical-path root): build the dynamic registration mechanism (gh #1).** Port Tony's
  Indaleko design: ONE static config collection (the registration manifest) + a mechanism that
  reads it and dynamically constructs collections / schemas / indices / views. This is a PORT, not
  an invention — Tony already designed and validated it in Indaleko.
  - **DESIGN SOURCE (read it, don't re-derive): `~/projects/indaleko/utils/registration_service.py`**
    (16KB, dated 2025-08, the most legible form the design exists in — decisions already made).
    `IndalekoRegistrationService` holds a **provider collection** (= the "one static config
    collection") and exposes the exact missing primitive:
    `create_provider_collection(identifier, schema=, edge=, indices=, reset=)` — registers a new
    collection WITH its schema, edge-ness, and indices in ONE call. Plus
    `generate_provider_collection_name(identifier)` (dynamic naming, no collisions) and a QUERYABLE
    registry (`lookup_provider_by_identifier`/`by_name`, `get_provider_list`). The C0 port replaces
    yanantin's two `_SEMANTIC_COLLECTIONS` tuples with registration into a provider collection.
  - **Legibility note (Tony):** the intent is NOT trapped in Tony's head — half of it is this file,
    fully made in code (which can't hand-wave the way prose does). What was missing was the
    POINTER (the link "yanantin's missing primitive = this Indaleko file"), which lived only in
    Tony's head. That pointer is now in ink here — the cheap fix to the legibility gap.
- Then **A1 (#17) REGISTERS itself** (collection + schema + indices) instead of hand-appending.
- Then the **activity fork converges back** (registers instead of its own `_SEMANTIC_COLLECTIONS`
  tuple), and new spaces (machine-config, file-records) cost a registration CALL, not a backend
  edit ×3. THIS is the "fundamentally dynamically extensible" system being actually dynamic.

## Drift-guard

Do not build A1 / new collections by editing `_SEMANTIC_COLLECTIONS`. That is the shoehorn. The
common core's real primitive is REGISTRATION (gh #1); the immutable/obfuscator/provenance features
ride on top. If a new piece of work makes you edit a static collection tuple or fork a backend,
STOP — that friction IS the missing-primitive symptom, not a normal cost.
