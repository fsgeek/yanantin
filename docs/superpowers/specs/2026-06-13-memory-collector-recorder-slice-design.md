# Memory Collector/Recorder: index the memory corpus, make it findable

**Date:** 2026-06-13
**Status:** Design (harvested from Indaleko's collector/recorder structure, not re-derived)
**Builds on:** `find()` first slice (2026-06-13 eve) — `LlikaService.find(terms) -> FindResult`
content-axis recall already exists and is verified against live `apacheta_test`.
**Scope discipline:** CONTENT-FIRST. The `[[wikilink]]` semantic graph is the NEXT slice,
explicitly out of scope here (see Out of Scope). This slice must be buildable in one session.

---

## The wound this cures

The memory subsystem is a goat rodeo (Tony's word). `MEMORY.md` is 33.9KB, over its own
24.4KB limit, **truncating on load** — every instance wakes having silently lost part of its
index. ~40 `[[wikilink]]`ed topic files form a hand-authored graph nobody traverses. Instances
`Read` the 34KB wall and grep topic files by hope. This is store-without-find
([[project_store_without_find]]) in the project's own house — the memory is a flat-file pile
*precisely because find did not exist*. It does now. So the memory corpus is find's first real
customer: `find("where do credentials live")` instead of reading 34KB and praying the line
survived truncation.

This is **dogfooding the thesis on the exact artifact that's been hurting every instance**,
including the four that walked (project_find_first_slice_and_the_wall_was_unbuilt_road).

## This is the FIRST COLLECTOR, not a memory feature

Generalize, don't one-off (Tony's standing ask). The memory dir is the first **collector
target**. Tomorrow it's `~/projects/yanantin`, then the 28.5M-file Indaleko corpus. Build the
collector generic over a directory of files; the memory dir is just `--target ~/.claude/.../memory`.

**Do NOT pre-build Indaleko's 3-level inheritance.** Tony GREW that iteratively (wrote one
local collector, found the commonality, extracted). We harvest the *shape* it converged to and
write ONE collector structured so the commonality is visible; extraction happens when a second
target arrives. Re-walking the iteration from scratch would be re-derivation
([[feedback_read_the_spec_before_rederiving]]).

## Harvested shape (read from Indaleko, ~/projects/indaleko)

`BaseStorageCollector.collect()` (storage/collectors/base.py) walks `self.path`, emits dicts;
each carries **`URI` = the path (identity key)**, `ObjectIdentifier` (uuid), `Collector`
(service identity = provenance), plus stat fields. Recorder (`storage/recorders/base.py`)
`normalize_collector_data()` turns a raw dict into an object carrying `URI`, then `record()`
inserts; URI has a unique index → no duplicate insert.

| Indaleko | yanantin first cut | why it changes |
|---|---|---|
| `collect()` walks `self.path`, emits dicts | `collect(target)` walks a dir, yields records | drop machine_config, stat-counters, symlink/special handling — text-file noise |
| `URI` = path = identity | `uri` = file path = identity key | the dedup hinge; collision-is-update lives here |
| `ObjectIdentifier` uuid4 + `Collector` id | record_id + ProvenanceEnvelope (collector identity) | provenance = the ayni signature ([[project_ayllu_not_miraflores_multitenancy]]) |
| stat fields | frontmatter → fields, body → `content` | memory files are markdown+frontmatter, not stat-able blobs |
| recorder reads from a **JSONL file** | recorder **wraps collector in-memory** | yanantin's deliberate addition — the "data wrangler" seam Indaleko lacked; no file between collect and record |
| URI unique index → no dup | recorder: changed? → new version + supersedes edge; else skip | the collision-could-be-update case, done for an immutable substrate |

## The collision rule (the real work — pinned, Tony 2026-06-13)

A re-collected file whose content CHANGED. URI (path) is identity → the record exists. The
substrate is append-only/immutable (`store_record` raises `ImmutabilityError` on duplicate
`_key`). So:

- **Identity = URI** (path). Stable across versions.
- **Change SIGNAL = (size, mtime)** — cheap, from a stat, scales to 28.5M files. Content is
  indexed when practical, but the *signal* is metadata because re-hashing every file's content
  does not scale. (Tony: "I'd build version-on-change IF there was a change — but change it if
  the *metadata* changed, as indexing contents isn't always practical.")
- **Version-on-change:** metadata changed → write a NEW immutable record (new UUID), `link()` a
  **`supersedes` edge** to the prior version (keyed on URI). Old version KEPT (save-it-all,
  [[project_save_it_all_before_forget]]); the version chain is itself walkable. This makes the
  recorder the first real customer of Llika `link()` — but these are MECHANICAL version edges,
  NOT the semantic `[[wikilink]]` graph (next slice).
- **Unchanged (same size+mtime):** skip. Idempotent re-run.
- **DECLARED LOSS, written into the code not hidden:** content changed while size AND mtime
  preserved → missed. Possible, rare, NAMED. Corpus-dependent: the memory dir is small enough
  to content-hash NOW (close the loss); the 28.5M corpus is where stat-only earns its keep. The
  loss is a knob, not a wall. ([[feedback_declared_loss_is_debt_not_payment]] — the knob is the
  payment, the comment is the debt; ship both in the same commit.)

## v1 scope

- A **collector**: `collect(target_dir) -> Iterable[record]`. Walks a directory, parses each
  text/markdown file (frontmatter → fields, body → `content`), yields records carrying
  `uri` (path), `content`, parsed frontmatter fields, size, mtime.
- A **recorder**: wraps the collector in-memory (the wrangler), inserts into the open `records`
  lane via the existing `store_record`, applying the collision rule (skip / version+supersedes).
  Provenance = the collector's identity.
- Find already works over the resulting `content`. No new find work.
- **Use-case-shaped acceptance tests** (each case = a named wound), written here, left on disk
  uncommitted, handed to Codex to harden in its own commit (per-commit separation, not
  per-instance):
  - **credential wound:** after collecting the memory dir, `find("db.ini")` returns the
    `reference_db_credentials_location` record. (Half-proven tonight.)
  - **truncation wound (the killer):** a fact living PAST MEMORY.md's 24.4KB cutoff is still
    findable — proves find BEATS the current mechanism, not just matches it.
  - **decided-then-forgotten wound:** `find("categorical value substitution")` returns the
    "theater, 2026-06-02" record, so the next instance does not re-litigate a closed call.
  - **idempotency:** collect twice, unchanged → no new records (skip works).
  - **version-on-change:** touch a file's content+mtime, re-collect → new record + a `supersedes`
    edge to the prior; old version still present and gettable.

## Out of scope (explicitly — content-first)

- **The `[[wikilink]]` semantic graph.** Parsing `[[name]]` links and `link()`-ing them into
  Llika's edge collection so find-meets-walk on real memory. This is the genuinely-NEW part
  (Tony) and deserves its own slice, its own commit, its own thinking. The `supersedes` version
  edges here are mechanical, not semantic — they don't touch this.
- ArangoSearch view / BM25 / stemming (find's own next slice; "boltzmann brain" ≠ "Boltzmann
  brains" until then).
- Content-hash change detection (the knob that closes the declared loss) — add per-corpus when
  practical; metadata-signal is v1.
- Indaleko's 3-level inheritance (grow it on the second target, don't pre-build).
- Targets other than the memory dir (the collector is generic; only the memory target is wired).

## References

- `~/projects/indaleko/storage/collectors/base.py`, `.../local/linux/collector.py` — the
  harvested collector shape.
- `~/projects/indaleko/storage/recorders/base.py`, `.../local/linux/recorder.py` — recorder +
  URI-unique idempotency.
- `find()` first slice: `src/yanantin/llika/service.py` (`find`), `models.py`
  (`FindResult`/`FindHit`), `backends/arango.py` (`find`).
