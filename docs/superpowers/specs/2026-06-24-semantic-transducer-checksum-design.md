# Semantic Transducer — Checksum as Proof-of-Pattern

**Date:** 2026-06-24
**Status:** Designed, awaiting adversarial review
**Issues:** the semantic-data-provider arm (the "what's *in* the object" stream, distinct from the activity arm). First instance establishes the reusable pattern **transducer → own collection → provenance edge → StorageObject**. Downstream beneficiaries: every later semantic transducer (EXIF, Unstructured, photo-classifier, the audio-engineer's sonic-qualities extractor — all replicate this pattern in parallel), the cross-silo dedup join, the #17 inference engine (the file→semantic edge is the same edge shape as derived-from).
**Supersedes (in part):** the current `ChecksumData` (`frozen=True, extra="forbid"`) and the current checksum recorders (which write a *tensor* and an *activity fact* — the fusion error this spec corrects).

## Why (the finding that produced this spec)

Yanantin has a checksum collector (`collector/storage/local/checksum.py`) whose
*collection layer is already correct* — single read pass, all hashers fed
simultaneously, mmap for large files, a synthetic twin
([[project_dual_collector_synthetic_ground_truth]]). But the **model is closed**
(`ChecksumData`: `frozen=True, extra="forbid"`, a validator demanding
`checksums.keys() == algorithms` *exactly*) and the **recorders commit the
fusion error**: `ChecksumRecorder` writes the digests as a reasoning *tensor*,
`ChecksumFactRecorder` writes them as an *activity fact*. Neither writes a
semantic object in its own collection edged to the file. The checksum
observation is fused into the wrong substrates — the same fusion the
StorageObject pour just *un-did* for storage, one substrate over
([[project_one_schema_three_substrates_and_user_assistant_is_the_enemy]]).

A checksum is **content-derived** — a pure function of the bytes — therefore it
is *an observation extracted from the object*, i.e. a **semantic** observation,
not storage metadata and not an activity event. The owning observer is a
*transducer*, distinct from the storage collector that observes the same file.
One collector owns one object ([[project_objects_path_is_the_only_recorder_without_a_central_collection_owner]],
[[project_ownership_at_the_tier_where_the_fact_stops_varying]]); the transducer's
output therefore belongs in **its own collection**, joined to the StorageObject
by a **provenance edge** — never folded into the StorageObject's open lane (that
would re-fuse two observers into one object).

**Organizing principle:** *everything is an observer producing an object, joined
to other objects by provenance edges.* Storage observes the file; the transducer
observes the file's content; activity streams observe the system's behavior. The
edge is the universal join. This spec builds the first semantic transducer so
that the **edge shape** it establishes is the one every later transducer — and
the inference engine's derived-from edge — replicates.

## The motivating use case: cross-silo dedup, justified by I/O locality

The point is **duplicate detection across storage services that publish
different checksum dialects** — NOT integrity verification. A file in Dropbox
exposes Dropbox's `content_hash` (SHA-256 over concatenated **4 MB**-block
SHA-256 digests — published, locally recomputable); Google Drive exposes
`md5Checksum`; most local filesystems (ext4/XFS/APFS) expose **no** per-file
cryptographic digest at all. Two files in different silos can be proven
identical only if *some shared dialect* exists on both sides.

**Why compute a generous family in one pass — the cost asymmetry:** a digest is
cheap when the bytes are *already local* (you are reading them anyway). It is
expensive when the file must be **recalled from remote storage** purely to hash
it. The marginal CPU cost of adding MD5 + SHA-1 + SHA-256 + BLAKE2 + the Dropbox
4 MB construction to a single local read is near zero (all over bytes already in
memory); the cost of going back for *one more dialect later* is a full remote
recall. **Asymmetric costs justify computing more than you currently need** — the
open-map shape, for an economic reason, not only a schema-philosophy one. This is
the save-it-all-on-one-read law ([[project_save_it_all_before_forget]]) with a
concrete cost gradient under it: extract every dialect while the bytes are cheap,
because the second chance is expensive-to-impossible.

**Honest scope (research justification, not hidden):** cross-silo dedup may turn
out not worth the effort. We will not know until it runs against a real corpus —
the artifact produces the *data* that answers "is this useful," and that question
is unanswerable by reasoning alone ([[project_dont_throw_anything_away_root_principle]],
cf. the temporal-window 99% result, learned only by measuring real data). "Cheap
to build, simple to implement, only the artifact answers the question" is a
first-class reason to build it — and it makes checksum the right **proof-of-pattern**
first transducer: deterministic (so a failing integration test is unambiguously a
plumbing failure, never model-output noise), motivated, and exercising the full
transducer→collection→edge shape.

## §1 — The model (open the closed object)

Replace `ChecksumData`'s closure with the open lane. The dialect set is
determined by *which silo the file lives in* — open-ended by construction — so a
closed schema would discard the federation's join keys at the door
(`feedback_closed_schema_is_the_llm_default`, [[feedback_restrictive_reflex_fires_about_the_antireflex_work]]).

```python
class ChecksumObject(BaseModel):              # successor to ChecksumData
    model_config = ConfigDict(extra="allow")  # the open lane — NEVER extra="forbid"

    # ── Required spine ──
    object_identifier: UUID         # uuid5(transducer_source, uri) — deterministic, idempotent
    uri: str                        # the file observed (the edge target's locator)
    digests: dict[str, str]         # OPEN map: {algorithm_name -> hexdigest}
                                    #   md5/sha1/sha256/blake2b + "dropbox" (4MB construction) + whatever
    file_size: int
    observed_at: datetime           # when WE computed it (when-we-learned-it)
```

Design calls:
- **`extra="allow"`** — non-negotiable. The standing project rule; the scan proves
  the dialect set is open (next service, next filesystem, next CAS).
- **`digests` is an open map, not enumerated fields.** A new dialect is an added
  *key*, never a schema migration. Absence is legible: a local ext4 file has no
  service digest → that key is **missing**, not null, not faked (the
  poor-object/rich-object distinction from the StorageObject design).
- **Drop the `keys == algorithms` exact-match validator.** It hard-codes "the only
  digests present are the ones we asked for," forbidding a service-asserted digest
  (Dropbox's reported `content_hash`) from sitting in the same map as our
  locally-computed ones. For *dedup* the provenance of a digest is irrelevant —
  two files match if they share a digest in any dialect; who computed it does not
  matter. (Contrast integrity verification, which WOULD need observer-tagging —
  explicitly **out of scope**, see §4.)
- **KEEP the hex-validity check.** A digest must be a digest — that is a *real*
  invariant, not a closure reflex. Openness means "don't enumerate which facts may
  exist," NOT "don't validate the facts that do." [[feedback_stronger_tests_never_an_error]]

## §2 — The Dropbox dialect (the one net-new computation)

`hashlib` does not have it; it is a published custom construction
(`github.com/dropbox/dropbox-api-content-hasher`):

> SHA-256 over the concatenation of the SHA-256 digests of each successive
> **4 MB** block of the file.

Compute it **locally** during the same single read pass, so a local file (or a
OneDrive/iCloud file with no service hash) can be matched against a Dropbox file
without recalling either. This is the one piece of genuinely new code; it is
self-contained, testable against Dropbox's own published test vectors, and
touches nothing dangerous → **delegable to an agent in isolation**.

NOTE (scan-corrected): the block size is **4 MB**, not 2 MB.

**STATUS (2026-06-24): §2 is BUILT.** `dropbox_content_hash(file_path) -> str`
in `collector/storage/local/checksum.py` (commit 260749f5), Codex-authored test
with an in-test reference oracle + boundary cases (c9f51292). 20/20 green. The
rest of this spec (§1 model-open, §3 recorder re-home) is NOT yet built.

## §2.5 — Edge DIRECTION decision (SETTLED 2026-06-24, Tony confirmed)

The checksum edge points **FROM the checksum object TO its specific StorageObject**
(`relation_type="extracted_from"`), targeting `Objects/<uuid5(NAMESPACE,
f"{storage_source}:{uri}")>` — the exact key the linux normalizer computes
(`recorder/storage/local/linux/normalize.py:34`, `NAMESPACE =
6f8c9e2a-1d4b-5a3c-8e7f-0b1c2d3e4f50`). This is reading **(1)**: the transducer
records what it OBSERVED — "I checksummed *this* storage observation, here's the
proof-edge to that exact object." The `object_identifier` is keyed on
`source:uri`, so it is observation-specific BY DESIGN (§3.6): a Dropbox-observed
and a linux-observed copy of the same bytes are DIFFERENT objects with DIFFERENT
keys. The transducer must therefore know the storage `source` it points at.

**Rejected: reading (3) — checksum-object-as-cross-silo-HUB.** Tempting (the
digest IS the silo-independent identity, so storage objects across silos could
converge on one checksum object → the Rosetta-stone join drawn as topology). But
that is a **read-time JOIN, not a write-time FACT** (Tony: "you figure that out
later, not at the time you compute checksums"). At checksum-time you do not yet
know the other silos' digests — they may be unobserved. Recording a hub edge then
asserts a relationship from one end = premature binding, the fusion error one
level up (transducer doing the inference engine's job). (1) is what is TRUE at
write-time; (3) is what is DISCOVERABLE at read-time. Build (1) now; (3) is the
inference engine's later **derived** edge (joins on shared digest across whatever
silos turned out to exist) — building (1) does NOT foreclose (3).

## §2.6 — The mechanism already exists (the density-rise)

No new graph machinery. `Registrar.contribute(contributor_id, **fields)`
(`core/registration.py:248`) writes a doc with a deterministic `_key` →
**idempotent re-observation for free** (re-checksumming REPLACES, no duplicate);
`Registrar.contribute_edge(contributor_id, from_ref, to_ref, relation_type)`
(:300) writes the ProvenanceEdge. The transducer is the **second caller** of the
mechanism the storage spine already proved. Mirror `LinuxStorageRegistration`
(`recorder/storage/local/linux/registration.py`): its own Registrar owning a
`SemanticChecksums` collection (doc) + SHARING the `Relationships` edge collection.

## §2.7 — Blast radius (mapped 2026-06-24, re-grep before trusting — half-life)

Opening `ChecksumData` + re-homing the recorder spans the builder/tester split.
Test commits are **Codex-authored**; src commits are mine. The pour order:
**open-model(src) ← test-adjust(Codex)**, then **re-home-recorder(src) ←
test-migrate(Codex)**, then **integration-traversal-test(Codex) → wire-up(src)**.

- `ChecksumData` consumers: `recorder/storage/local/checksum.py` (both recorders),
  `collector/.../checksum.py` (model + synthetic), and tests:
  `test_collector_checksum.py`, `test_checksum_canonical.py`, `test_recorders.py`,
  `test_fact_recorders.py`, `test_collector_isomorphism.py`.
- **SUBTLE — preserve this, do NOT delete it:**
  `test_collector_isomorphism.py:83` asserts `set(data.checksums.keys()) ==
  set(data.algorithms)`. That is the **synthetic-fidelity** invariant (real↔synthetic
  shape-match), NOT the closure reflex. Opening the model (`extra="allow"`, drop
  the in-model `keys==algorithms` validator at `collector/.../checksum.py:59`) must
  KEEP this test's assertion — it tests the COLLECTOR's output, not a constraint on
  the OBJECT. The spec's own rule: openness = don't enumerate which facts may
  exist, NOT don't validate the facts that do ([[feedback_stronger_tests_never_an_error]]).
- Re-home DELETES `ChecksumRecorder` (tensor) + `ChecksumFactRecorder` (activity
  fact) + `collect_and_record_checksum`. `test_checksum_canonical.py`,
  `test_recorders.py`, `test_fact_recorders.py` import these → Codex migrates
  them to the new contribute/contribute_edge path or retires the cases that only
  existed to exercise the deleted paths.

## §3 — The recorder re-home (the fusion correction — the proof-of-pattern)

Delete the tensor path and the activity-fact path. The transducer writes:

1. **A `ChecksumObject` into its own collection** (`SemanticChecksums` or the
   semantic-arm's well-known name) — bound via `Khipu.watay` like every other
   collection (Khipu is the sole creator, post-Pour-A). Schema-less-or-open per
   the open-lane rule.
2. **A provenance edge** on the existing single `Relationships` collection,
   `ProvenanceEdge` with `relation_type="extracted_from"` (or the agreed verb),
   `_from` = the ChecksumObject, `_to` = the StorageObject for the same `uri`.
   Endpoints use canonical `collection/key` form
   ([[project_provenance_edge_canonical_key]]).

The traversal "given this file, show me its checksums" becomes a **graph query**,
not a lineage-tag-string match. **This edge is the same edge** the later semantic
transducers and the inference-engine's derived-from edge use — establishing it
once correctly is what makes the later semantic arm a clean parallel fan-out
instead of N agents re-inventing the join.

## §4 — Explicitly OUT of scope (named, deferred, not folded in)

Folding any of these into the transducer would re-commit the one-collector-two-jobs
error in a new place. Three distinct operations; the transducer is only the first:

1. **Verify** (service-claim vs local recomputation: does Dropbox's reported
   `content_hash` equal ours?) — a *within-file* integrity check across two
   observers. Requires observer-tagging the digests. We are doing **dedup, not
   integrity** — out. Cheap follow-on if ever wanted.
2. **Cross-silo equivalence join** (file A ≡ file B because they share a digest) —
   an *across-file* operation comparing observations. This is the **inference
   engine's edge**, downstream; the transducer only produces the keys that make
   the join *possible*.
3. **Block-level filesystem integrity** (ZFS/Btrfs checksum trees, dm-integrity) —
   present-but-unreachable digests needing fs-specific extraction (scrub tooling,
   not `hashlib`); a different capability (integrity-of-storage, not
   identity-for-federation) and a larger, platform-coupled surface. Out.

## §5 — Build plan (who does what)

Builder/tester separation is CI-enforced (no commit touches both `src/` and
`tests/`): each task = test-only (Codex-authored) then src-only. Yanantin-signed
(name+email+signingkey all three, [[reference_ai_commit_signing_override]]).

- **DRIVE (mine — fusion-correction, blast radius, Pour-A-class care):**
  - Open the model (`forbid → allow`, drop exact-key validator; keep hex check).
    Map the blast radius first — `ChecksumData` is `frozen` with live consumers
    (both recorders, the synthetic collector, pinning tests). [[feedback_no_mock_databases]]
  - Re-home the recorder → `ChecksumObject` in own Khipu-bound collection +
    provenance edge to StorageObject. Deletes the tensor/fact paths (deleting from
    tested code — red-bar the new edge BEFORE touching).
- **DELEGATE (agent, isolated worktree — self-contained, fully specified):**
  - The Dropbox 4 MB content-hash construction + tests against published vectors.
- **DEFERRED & NAMED:** verify, cross-silo join, block-level integrity (§4).

## §6 — Acceptance

- `ChecksumObject` is `extra="allow"`; `digests` an open map; a foreign/undeclared
  dialect key round-trips (open-lane guard, mirrors the StorageObject open-lane test).
- Dropbox dialect matches published test vectors; computed locally in the single read pass.
- A `ChecksumObject` lands in its own collection on live `apacheta_test`; a
  `ProvenanceEdge` connects it to the StorageObject for the same `uri`; **graph
  traversal file→checksums returns the digests** (the 0→1 proof, [[project_federation_runs_today_and_i_was_the_uningested_episode]]).
- The synthetic twin still produces type-valid ground-truth under the open model.
- No tensor and no activity-fact is written for a checksum observation (fusion
  corrected — structural guard).
```
