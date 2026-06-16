# C0 — Provider Registration (the first core pour)

*2026-06-16. Design source ported from `~/projects/indaleko/utils/registration_service.py`.
Written after a ground-reading pass that disarmed two ghosts the handoff carried. Brainstormed
with Tony; the forks below were his calls, recorded inline.*

## What this is (one paragraph)

The common core's missing primitive (gh #1): a mechanism by which **any** provider — semantic,
storage, activity, or a kind nobody has invented yet — **declares itself**, and the substrate
organizes around it. It replaces the static `_SEMANTIC_COLLECTIONS` lists (the disease: collections
known only by a hardcoded tuple that someone must remember to edit) with a dynamic registry: a
provider registers, and its data collection comes into existence as a consequence. Born in
`src/yanantin/core/`, it is the first and (day one) only inhabitant.

## The disambiguation that unblocked this (read first)

Three distinct mechanisms were colliding under the words "mapping" and "registration". They are
**not** the same thing; conflating them is what made the build-order doc reach for a DuckDB mapping
store that does not need to exist.

1. **Label obfuscation** — `semantic_label → opaque_label`. The `StorageObfuscator` protocol
   (`apacheta/storage_obfuscator.py`, stdlib-only contract) + Pukara's `SchemaMap` (the keyed
   implementation, instantiated *only* at `pukara/app.py:41`). A **stateless, per-deployment,
   compute-from-key function** — NO stored table, NO DuckDB, NO allocation. Already built, already
   wired into both arango backends, already placed exactly where the threat model wants it. **Not
   core to build; the protocol is already a dependency-inverted leaf.** The "DuckDB mapping layer"
   in the build-order doc is a GHOST — it would re-implement, as a stored table on the substrate, a
   thing already solved as a keyed function in the fortress. Building it would *undo* a correct
   boundary. **Cut from C0 scope as a reversible bet** (Tony is not certain it is a ghost; neither
   am I): the one thing SchemaMap genuinely cannot do is store a `semantic_description` per label
   (it computes opaque names, it does not remember *why* a name exists). If a real need for
   stored-description lookup appears, the DuckDB store comes back *for that*, not for obfuscation.
   The bet is asymmetric in our favor: if cutting it was wrong, a missing-description need surfaces
   loudly; if right, we never notice. So we cut it now and let the ground report back.

2. **Connection identity** — `(host, db_name, username) → handle`. The `get_database` singleton
   (`infra/config.py`). **Per-principal** (username IS the identity axis). This is where #13's
   "one DB+user per instance" lives — it is an axis the singleton *already keys on*, not a new
   subsystem. Generalizing 3-tiers → N-principals, and *who routes which principal*, is the
   honestly-OPEN StandardDatabase routing seam. **Registration does NOT resolve it** — registration
   uses whatever principal it is handed; identity-per-instance is an *above* concern.

3. **Provider registration** — "who has declared themselves, and what collection is their home."
   Indaleko's `registration_service.py`. **This is C0.** It is NOT the label layer and NOT the
   identity layer; it rides *on* the connection singleton and *through* the obfuscator.

Label obfuscation (per-deployment, one key) and connection identity (per-principal, N users) are
**orthogonal axes** — they rhyme because both involve UUIDs, but one disguises labels and the other
allocates connections. Neither constrains the other.

## The guideline that keeps the strangler-fig safe: the dependency arrow points ONE way

**Guideline (not a law — a decision made visible): everything depends on `core`; `core` depends on
nothing but the database singleton + stdlib.**

Stated as a guideline on purpose. It is not a stylistic absolute and not a wall to be enforced — it
is hard-won pain-avoidance written down so the next decision is visible. Tony's reason is concrete
and unglamorous: **Python initialization dependency loops are genuinely miserable**, and this
guideline's whole job is to make a cycle-creating import *a visible choice* rather than an accident.
The known future pressure that motivates it: Pukara must validate capabilities → Pukara inherits a
dependency on the IAM layer → IAM lives in core. If core reaches *back* toward `apacheta` /
`transport` / `pukara`, you get `apacheta → pukara → core → apacheta` — exactly the init loop the
guideline exists to keep visible. So crossing it (importing transport/apacheta/pukara/activity/
llika/chasqui from core) is something you do *on purpose and in writing*, not by reflex.

Consequence for design: registration does NOT import `transport.ProviderRegistration` (that would
make core depend on transport — a crossing with no reason behind it). It defines its **own** registry
record.

## Components

### `core/registration` — registry + factory

Ported from `IndalekoRegistrationService`, stripped of Indaleko's `ServiceManager`/singleton
infrastructure. Two welded halves:

- **The registry** — a single provider collection cataloging who has registered. Verbs:
  `register_provider`, `lookup_provider_by_identifier`, `lookup_provider_by_name`,
  `get_provider_list`, `deactivate_provider`, `delete_provider`. The registry row is the record
  below.
- **The factory** — `create_provider_collection(identifier, schema=None, edge=False, indices=None,
  reset=False)`. **Delegates to the obfuscator-aware collection creation already proven in
  `apacheta/backends/arango.py:196-198`** (`has_collection` guard → `create_collection(mapped,
  edge=...)` → indices via `add_persistent_index`). It does NOT re-implement collection creation,
  and it does NOT create literal-named collections — names pass through the `StorageObfuscator`
  like every other collection (Tony: option-2 "literal now, obfuscate later" is an illusion of
  choice — the only honest path is through the obfuscator from the first pour).

### The registry record — `frozen=True, extra="allow"`

A Pydantic model, core's own (NOT transport's). The shape Tony named "very yanantin-like":

- **`frozen=True`** — a registration, once made, is immutable. You supersede, you don't mutate
  (matches the supersession-in-place architecture).
- **`extra="allow"`** — the record never refuses a field it didn't anticipate. Provider kinds
  nobody has invented yet carry kind-specific metadata that is *kept*, not rejected. This is the
  save-it-all law and the Harness-1 "type the mechanical, leave the rest free" pattern made
  structural; it is the antibody to the closed-schema reflex (re-imposing `extra="forbid"` while
  designing the defense against it). The typed spine stays validated; the open tail absorbs the
  not-yet-categorized.

Typed spine (the mechanical, validated part): `provider_id: UUID`, `provider_name: str`,
`provider_type: str`, `description: str`, `schema: dict | None`, `registered_at: datetime`,
`active: bool`. Everything else: allowed and stored.

## Why `transport.ProviderRegistration` is NOT this (and stays put)

`transport/models.py:19` has a `ProviderRegistration` that *looks* like the registry record. It is
not. It is a **transport DTO** — a passed-in config value describing the source feeding a wrangler
envelope ("what is this data source, what does it produce"). The wrangler does not consult a global
registry; its source/sink hands it this description. Different noun, confusingly-similar name. It
stays in transport (no move, no blast radius, no back-dependency). Convergence, if ever, is a later
tested-green step — not C0's job. (Tony's cut: "Why do the wranglers need registration? Why wouldn't
it be a passed-in configuration value from the sink or source?" — they don't; it is.)

## Dependencies (the porting surface)

- **Connection singleton** — `infra/config.py` `get_database` / `ApachetaDBConfig`. ALREADY EXISTS.
  Registration sits on it. (The dedicated *separation layer* — per-StandardDatabase isolation — is
  a later core concern, NOT a prerequisite for this pour; a single StandardDatabase is correct under
  every outcome of the routing question.)
- **`StorageObfuscator` protocol + `TransparentObfuscator`** — stdlib-only, already
  dependency-inverted. **Moves into `core/` as part of this pour** (resolved below): registration
  needs it to create obfuscated collection names, and a `core → apacheta` import to reach it would
  be an unmotivated crossing of the one-way guideline. The protocol is a contract-leaf, so the move
  qualifies under the entry rule; apacheta + activity backends update their import to the core path
  (small, tested-green). Low-regret by Tony's test: if the move is wrong the import graph / tests
  say so loudly; if right, it's silent — so we just do it rather than gate registration behind a
  separate ceremony.
- **stdlib** — `uuid`, `datetime`. A `validate_uuid_string` helper (trivial; core's own).

Indaleko bits explicitly DROPPED: `IndalekoSingleton` (we have a connection singleton),
`IndalekoServiceManager` self-registration (no master-service-catalog layer for C0 — one registry;
Tony: collapse to one for C0, reintroduce the split only if a real need appears), `INDALEKO_ROOT`
path bootstrap, OSError-swallowing (fail-stop instead).

## Error handling

Fail-stop, per the build-order law. No storage ⇒ hard stop; no in-memory fallback, no
graceful-degradation (simulating a capability you don't have is the lie). Indaleko's `except OSError:
return None/[]` swallowing is NOT ported — a registry that can't reach its store must raise, not
return an empty list that reads as "no providers."

## Testing (green vs live `apacheta_test`, no mocks)

Per the no-mock-databases rule, tested against the live `apacheta_test` DB:

1. Register a provider → assert the registry row exists, keyed by provider UUID, with the typed
   spine + an extra field that survived (proves `extra="allow"` round-trips through ArangoDB).
2. `create_provider_collection(id, schema, indices)` → assert the collection exists **under its
   obfuscated name** (proves the obfuscator seam), with the schema validation + indices applied.
3. Re-register same UUID → raises (no silent overwrite).
4. `get_provider_list` → returns the registered provider(s).
5. Register through a `TransparentObfuscator` and through a stand-in opaque obfuscator → collection
   name differs accordingly (proves the seam is real, not decorative).
6. Fail-stop: registration against an unreachable store raises, does not return empty.

Test/builder separation enforced by CI; the red-bar floor must actually RUN these.

## RESOLVED during brainstorm

- **`StorageObfuscator` moves into `core/` as part of this pour.** (Was open; Tony's
  reversible-bet test resolved it — see Dependencies above. Day-one core = registration + the
  obfuscator contract-leaf. This is the one thing that makes C0 a leaf-plus-one-small-move rather
  than a pure zero-blast-radius leaf; the move is self-revealing if wrong.)

## OPEN ITEMS (Tony's calls — do NOT collapse)

1. **The StandardDatabase routing seam** — who decides which principal/DB a call routes to
   (capabilities/handles Pukara routes on). Its own brainstorm, Tony driving. C0 builds on ONE
   StandardDatabase and is INDEPENDENT of how this resolves.

3. **Convergence of the `_SEMANTIC_COLLECTIONS` tuples onto registration** — the apacheta + activity
   backends' static lists become registered providers. This is A1 / downstream, NOT C0. C0 just
   builds the mechanism they will later migrate onto, one tested-green step at a time.
