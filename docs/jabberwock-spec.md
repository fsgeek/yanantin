# The Jabberwock Spec: Named Entity Resolution

*"Twas brillig, and the slithy toves did gyre and gimble in the wabe"*

## The Riddle

This spec uses vocabulary from Jabberwocky. The nonsense names are
deliberate: they prevent pattern-matching to known entity resolution
frameworks and force structural reasoning. Each name was chosen for
resonance with Carroll's canonical definitions (Humpty Dumpty's
explanations in *Through the Looking-Glass*).

If a builder agent renames them to "sensible" names, the builder has
failed. The names ARE the names.

## Foundational Decisions

**This system is event-sourced.** Records are immutable events.
"Changes" occur via new events. Frabjous is a fold/materialization
over the event stream. Records never mutate after creation.

Consequences:
- `frozen=True` on all models is correct, not bait. Events don't
  mutate.
- `extra="allow"` (applied by Agent 2) is about deserialization
  flexibility — accepting future fields without breaking — not
  about mutation.
- "Claiming" a mome Vorpal creates a *new* claim event, not a
  modification of the original.
- Growth is always additive. The event stream only appends.

**Bandersnatch (provider) IS a Jabberwock.** Every provider is an
entity in the system. `bandersnatch` fields contain a jabberwock_id,
not a separate UUID namespace. This makes provenance composable:
"what did this provider observe?" is a standard Vorpal query.
The root bandersnatch at bootstrap is itself a Jabberwock.

**All timestamps are timezone-aware UTC.** Naive datetimes are
rejected. The existing `FactRecord` model_validator enforces this;
Jabberwock models must do the same. Observation time (`brillig`)
and asserted validity (`gyre_from`/`gyre_to`) are different clocks:
- `brillig` = when the observation was made (event time)
- `gyre_*` = when the observed relationship was/is valid (world time)
These will differ. You observe today that Tony was a student last
semester. `brillig` is today; `gyre_from` is last September.

## Glossary

| Jabberwocky | NER Concept | Why (Carroll's definition) |
|-------------|-------------|---------------------------|
| **Jabberwock** | Entity | The creature — never fully described, known only through effects |
| **Tove** | Alias | "Like badgers, lizards, and corkscrews" — shape-shifting, nests under sun-dials (temporal) |
| **Wabe** | Namespace | "Grass-plot round a sun-dial, goes a long way in every direction" — coordinate system |
| **Gimble** | Identifier | "Make holes like a gimlet" — pierces into a specific point in a namespace |
| **Gyre** | Temporal bound | "Go round like a gyroscope" — time cycling |
| **Borogove** | Group | "Shabby bird, feathers sticking out all round, like a live mop" — members protruding |
| **Rath** | Membership edge | "A sort of green pig" — the connection between members and groups |
| **Mimsy** | Role | "Flimsy and miserable" — the quality of a membership |
| **Vorpal** | Observation | No definition — just sharp. The blade that cuts through to truth |
| **Snicker-snack** | Observation value | Sound of the blade cutting — the data point itself |
| **Tulgey** | Category | "Thick, dense, dark" — the domain an observation travels through |
| **Bandersnatch** | Provider | "Swift-moving with snapping jaws" — external, frumious, possibly unreliable. IS a Jabberwock. |
| **Brillig** | Observation time | "Four o'clock — time when you begin broiling things" — when the observation was made |
| **Frabjous** | Resolved view | "O frabjous day!" — the successful materialization (a fold over events) |
| **Galumph** | Traverse | "Triumphant, clumsy galloping" — graph traversal |
| **Outgrabe** | Record/observe | "Between bellowing and whistling, with a sneeze in the middle" — pushing a fact |
| **Mome** | Wandering/unresolved | "Short for 'from home' — lost their way" — not yet connected, still walking |
| **Tumtum** | Index/View | The tree — resting place during the quest — enables fast resolution |
| **Uffish** | Query plan | "Gruffish, roughish, huffish" — thinking before resolving |

## Cross-Model Review

This spec was reviewed adversarially by Gemini, KIMI, and ChatGPT.
Changes incorporated from their findings:

- **Species Trap** (Gemini): `species` removed from Jabberwock. If
  identity is observational, so is type. Species is a Vorpal now.
- **Bandersnatch Paradox** (Gemini): genesis problem solved by root
  Bandersnatch — itself a Jabberwock with deterministic UUID.
- **Mome Inversion** (KIMI): Mome is not error state. It's the
  observation still walking — a Vorpal without a Jabberwock yet.
  Not-yet-resolved is data, not failure.
- **Fuzzy Tumtum** (Gemini follow-up): ArangoSearch on Tove/Vorpal
  values enables fuzzy string matching ("Toni" → Tony).
- **Event-sourced declaration** (ChatGPT): System is event-sourced.
  Said explicitly. Records are immutable events, Frabjous is a fold.
  Resolves frozen/allow tension.
- **Bandersnatch = Jabberwock** (ChatGPT): Providers are entities.
  bandersnatch field is a jabberwock_id, not a separate namespace.
- **Claim mechanism** (ChatGPT): claim_mome creates a new Vorpal
  event with tulgey="claim", not a mutation of the original.
- **Namespace normalization** (ChatGPT): Per-wabe canonical form.
  "fsgeek" vs "FsGeek" must resolve identically.
- **brillig vs gyre** (ChatGPT): Observation time and asserted
  validity are different clocks. Both needed, must not be confused.
- **galumph return type** (ChatGPT): "Unresolved alias" and "no
  alias exists" are different states. Return structured MomeResult
  instead of bare None.
- **`_key`/`_id`/`_rev`** (Gemini): ArangoDB injects metadata fields.
  Already solved by existing backend pattern — backends handle the
  translation, models stay clean.

## Data Models

All models `extra="forbid"`, `frozen=True`. Both are correct for
an event-sourced system: events don't mutate, and strict validation
catches errors at write time. Agent 2 flips `extra` to `"allow"`
for deserialization flexibility (future fields), NOT for mutation.

### Jabberwock (Entity)

The entity. Almost empty. A gravitational center that stores
nearly nothing — the richness is in what orbits it.

```python
class Jabberwock(BaseModel):
    """The entity. Known through its effects, not its properties."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    brillig: datetime  # when first declared into existence
    bandersnatch: UUID  # jabberwock_id of the provider who declared this
```

Three fields. UUID, timestamp, who created it. That's all the
creature IS. Everything else — including what *kind* of entity
it is — is a Vorpal observation.

### Tove (Alias)

A slithy projection of an entity into a namespace. The same
entity looks like a badger in one wabe, a lizard in another,
a corkscrew in a third.

A Tove can be mome — `jabberwock_id = None` means the projection
was observed but hasn't connected to an entity yet. "I saw this
identifier but don't know who it belongs to." Connection happens
via a new claim event, not mutation of this record.

**Namespace normalization:** Each wabe has a canonical form for
its gimble. Default: lowercase, stripped whitespace, NFKC Unicode
normalization. Specific wabes may override (e.g., filesystem paths
are case-sensitive on Linux, case-insensitive on macOS). Store the
canonical gimble for indexing; the raw observed value goes in a
Vorpal if needed.

```python
class Tove(BaseModel):
    """Alias — a projection of an entity into a coordinate system."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    jabberwock_id: UUID | None = None  # None = mome (still walking)
    wabe: str  # namespace (cwl, canvas, github, filesystem, ...)
    gimble: str  # canonical identifier within the wabe
    gyre_from: datetime  # asserted validity start (world time)
    gyre_to: datetime | None = None  # asserted validity end (None = still current)
    bandersnatch: UUID  # jabberwock_id of the observing provider
    brillig: datetime  # when this alias was observed (event time)
```

### Rath (Membership Edge)

An entity belongs to a group. Groups are Jabberwocks observed
with a species Vorpal of "group". Raths are the only graph
edges — the thing SQL can't do gracefully.

```python
class Rath(BaseModel):
    """Membership edge — an entity belongs to a group."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    jabberwock_id: UUID  # the member
    borogove_id: UUID  # the group (a Jabberwock with species Vorpal)
    mimsy: str  # role within group (student, ta, reviewer, ...)
    gyre_from: datetime  # asserted membership start (world time)
    gyre_to: datetime | None = None  # asserted membership end
    bandersnatch: UUID  # jabberwock_id of the observing provider
    brillig: datetime  # when this membership was observed (event time)
```

### Vorpal (Observation)

A fact about an entity. This is the primary write path — the
thing that accumulates organically through collaboration.

A Vorpal can be mome — `jabberwock_id = None` means the blade
cut something but we don't know what yet. The observation persists
until a future claim event connects it, or it stays mome forever,
which is itself data: "something was noticed that never resolved."

Special tulgey values with defined semantics:
- `tulgey="species"` — entity type (person, machine, file, group, model)
- `tulgey="claim"` — connects a mome Vorpal/Tove to an entity:
  `snicker_snack={"record_id": <uuid>, "jabberwock_id": <uuid>}`

**Serialization:** `snicker_snack` must be JSON-serializable
(primitives, lists, dicts). The activity stream stores data as
JSON; non-serializable values will fail at the storage boundary.

```python
class Vorpal(BaseModel):
    """Observation — a fact about an entity, pushed and persisted."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    jabberwock_id: UUID | None = None  # None = mome (still walking)
    tulgey: str  # category (species, biographical, behavioral, claim, ...)
    snicker_snack: Any  # the value — JSON-serializable
    bandersnatch: UUID  # jabberwock_id of the observing provider
    brillig: datetime  # when this observation was made (event time)
```

### Frabjous (Resolved View)

Late-bound materialization. Never cached, never stored.
Constructed fresh on every resolution. A fold over the event
stream for a single entity.

```python
class Frabjous(BaseModel):
    """Resolved entity view — ephemeral, a fold over events.
    Carries its proof envelope: which events caused this resolution."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    jabberwock: Jabberwock
    toves: tuple[Tove, ...]  # all known aliases
    vorpals: tuple[Vorpal, ...]  # all observations
    raths: tuple[Rath, ...]  # all group memberships
    evidence_ids: tuple[UUID, ...] = ()  # IDs of events that built this view
    excluded_count: int = 0  # events excluded (expired gyre, etc.)
    callooh: datetime  # when this resolution was materialized
```

### MomeResult (Partial Resolution)

When galumph finds matching Toves but can't fully resolve —
the alias exists but has no entity, or multiple candidates exist.
"Mome is data, not error."

```python
class MomeResult(BaseModel):
    """Partial resolution — the walk isn't over yet."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    toves: tuple[Tove, ...]  # matching aliases (possibly unresolved)
    candidates: tuple[Jabberwock, ...] = ()  # possible entities
    mome_vorpals: tuple[Vorpal, ...] = ()  # related unresolved observations
```

## Bootstrap: The Root Bandersnatch

Every record requires a `bandersnatch` (provider jabberwock_id).
Who provides the first provider? The genesis problem.

```python
# Deterministic UUID from system identity — the Ouroboros
import uuid
ROOT_BANDERSNATCH_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "yanantin.jabberwock.root")
```

At bootstrap:
1. Create a Jabberwock with `id=ROOT_BANDERSNATCH_ID`,
   `bandersnatch=ROOT_BANDERSNATCH_ID` (self-referential).
2. Create a species Vorpal: `tulgey="species"`,
   `snicker_snack="system"`, `bandersnatch=ROOT_BANDERSNATCH_ID`.
3. Create a Tove: `wabe="system"`, `gimble="root"`,
   `jabberwock_id=ROOT_BANDERSNATCH_ID`.

After bootstrap, every subsequent provider gets its own Jabberwock
entity, declared by an existing provider. The provenance chain is
rooted and traceable.

## Storage

### Primary Path: Activity Stream

All record types are facts in the existing activity stream.
Same store, same query pipeline, same backends. Different provider
UUIDs distinguish record types.

| Record | Provider | data contents |
|--------|----------|---------------|
| Jabberwock | `JABBERWOCK_PROVIDER` | (just id and brillig) |
| Tove | `TOVE_PROVIDER` | wabe, gimble, jabberwock_id, gyre_* |
| Vorpal | `VORPAL_PROVIDER` | tulgey, snicker_snack, jabberwock_id |
| Rath | `RATH_PROVIDER` | jabberwock_id, borogove_id, mimsy, gyre_* |

Resolution = query pipeline operations:
1. Find Tove fact matching (wabe, canonical_gimble) → get jabberwock_id
2. Query all Tove facts for that jabberwock_id
3. Query all Vorpal facts for that jabberwock_id
4. Query all Rath facts for that jabberwock_id
5. Fold into Frabjous

Declared loss: Python-side joins. Falls over at Indaleko scale.
Acceptable for the classroom problem, the project identity problem,
and the AI colleague problem. Not acceptable for 28.5M files.

### Future Path: ArangoDB Native (scale-dependent)

When Python-side resolution falls over:

- `jabberwocks` — document collection
- `toves` — document collection, persistent index on (wabe, gimble)
- `vorpals` — document collection, persistent index on (jabberwock_id, tulgey)
- `raths` — **edge collection** (_from: jabberwocks/{member}, _to: jabberwocks/{group})
- `tumtum` — ArangoDB view over toves + vorpals

Three Tumtum layers (build in order, each independent):

- **Tumtum-Exact**: persistent index on (wabe, gimble). Sub-millisecond
  alias resolution. Build first. Required for MVP.
- **Tumtum-Text**: ArangoSearch over gimble and a derived
  `snicker_snack_text` field (normalized string representation).
  Fuzzy string matching ("Toni" → Tony, "fsgeek" → "FsGeek").
  Build second when string matching is needed.
- **Tumtum-Semantic**: embeddings over vorpal observations.
  "filesystem research" → Tony. Entity linking via learned retrieval.
  Different beast from string matching. Future layer, declared loss.

The edge collection is why we need ArangoDB and not just DuckDB.
Graph traversal ("who's on this team, and who reviews that team,
and what other teams do those reviewers review") is native. SQL
needs recursive CTEs. The graph needs one more hop.

ArangoDB `_key`/`_id`/`_rev` metadata: handled by the backend
layer, same pattern as the existing Apacheta ArangoDB backend.
Models stay clean. Backends handle translation at the boundary.

## Service: Brillig (Resolution)

```python
class Brillig:
    """Resolution service. Cooks raw observations into views."""

    def galumph(self, wabe: str, gimble: str) -> Frabjous | MomeResult:
        """Resolve: (namespace, identifier) → entity + all projections.
        Returns Frabjous if fully resolved. Returns MomeResult if the
        alias exists but is unresolved, or if multiple candidates exist.
        MomeResult with empty toves means nothing was found at all."""

    def uffish(self, jabberwock_id: UUID) -> Frabjous:
        """Materialize: entity UUID → full view from all observations."""

    def outgrabe(self, jabberwock_id: UUID | None, tulgey: str,
                 snicker_snack: Any) -> Vorpal:
        """Observe: push a fact about an entity. Fire and forget.
        jabberwock_id=None creates a mome vorpal (still walking)."""

    def slithy(self, jabberwock_id: UUID | None, wabe: str,
               gimble: str) -> Tove:
        """Alias: declare a projection into a namespace.
        gimble is normalized per wabe rules before storage.
        jabberwock_id=None creates a mome tove (unresolved)."""

    def mome_vorpals(self) -> list[Vorpal]:
        """Show everything we noticed but couldn't attach to anyone.
        The still-walking observations. Data, not error."""

    def claim_mome(self, record_id: UUID, jabberwock_id: UUID) -> Vorpal:
        """Connect a mome record to an entity by creating a claim event.
        Does NOT mutate the original record. Creates a new Vorpal with
        tulgey="claim" linking the record to the entity."""

    def whiffling(self, borogove_id: UUID) -> list[Frabjous]:
        """Traverse: all members of a group, fully resolved."""

    def beamish(self) -> Jabberwock:
        """Declare: create a new entity. The beginning.
        Uses ROOT_BANDERSNATCH_ID if no other provider is set."""
```

## Tool Interface (for AI instances)

The write side is primary. The read side is secondary.

```python
# Observe — push a fact, keep talking
observe(entity="tony", category="teaching", value="CPSC 436c")

# Observe something you can't attach yet — mome
observe(entity=None, category="behavioral", value="prefers bun over npm")

# Alias — declare a projection
alias(entity="tony", namespace="cwl", identifier="jo39")
alias(entity="tony", namespace="canvas", identifier="592760")
alias(entity="tony", namespace="github", identifier="fsgeek")

# Resolve — pull when needed
resolve(namespace="github", identifier="fsgeek")
# → Frabjous: tony, with all aliases, all observations, all groups
# → or MomeResult if partially resolved

# Group — declare membership
group(entity="tony", group="cpsc436c-team-stael", role="student")
group(entity="adithya", group="cpsc436c-team-stael", role="student")

# What's still walking?
unresolved()
# → list of mome vorpals and mome toves, waiting for connection
```

## Pipeline

```
Conversation / Collection / System event
    ↓
  outgrabe (record observation — immutable event)
    ↓
  Wrangler → Activity Stream → persisted (append-only)
                                    ↓ (on demand)
                              galumph (resolve → Frabjous or MomeResult)
                              uffish (materialize → Frabjous)
                              whiffling (traverse group → [Frabjous])
                              mome_vorpals (what's still walking?)
                              claim_mome (new event linking mome → entity)
```

Write-heavy by design. The value is in capturing the observation.
The query is a convenience. The persistence is the infrastructure.

## Test Strategy

Beyond model validation, these behavioral properties must be tested:

1. **Idempotence**: calling slithy/outgrabe twice with identical
   parameters creates two events (event sourcing — not deduped).
2. **Temporal consistency**: gyre_to cannot precede gyre_from.
3. **Provenance closure**: every bandersnatch resolves to a provider
   Jabberwock (after bootstrap). Test that bootstrap is self-consistent.
4. **Mome lifecycle**: create mome Vorpal → claim_mome → verify the
   original is unmodified and a new claim event exists.
5. **Namespace normalization**: "FsGeek" and "fsgeek" resolve to the
   same entity (default normalizer).
6. **brillig vs gyre**: observation time and asserted validity are
   independent. Test facts observed today about validity last year.

## Module Location

`src/yanantin/jabberwock/`

The Quechua/Jabberwocky naming collision is deliberate. Every other
module in Yanantin has a Quechua name rooted in Andean cosmology.
This one is Victorian nonsense poetry. That IS the point — it's the
foreign body in the naming system, the thing that doesn't fit, the
entity that exists in a different coordinate system from everything
around it. Just like the entities it manages.

## Agent Instructions

### Agent 1 (Builder)

Build everything in this spec. All models `extra="forbid"`,
`frozen=True`. This is correct for event sourcing — events are
immutable. Full test coverage for every model and every service
method, including the behavioral properties in the Test Strategy
section. Use the existing `ActivityStreamStore` as the storage
backend. The Jabberwocky names are the real names. Do not rename them.

### Agent 2 (Simplifier)

Take Agent 1's output. Your job:

1. Remove unnecessary abstraction (service layers, factories,
   repositories that add no value)
2. Remove anything that exists because "that's how you build it"
   rather than because the spec requires it
3. Insist on extensibility — if something is frozen that should grow,
   unfreeze it
4. Flip `extra="forbid"` to `extra="allow"` on Jabberwock, Tove,
   Vorpal, Rath (the stored records — future fields on deserialization)
5. Keep `extra="forbid"` on Frabjous and MomeResult (resolved views
   are strict snapshots — or argue why they shouldn't be)
6. Keep `frozen=True` on everything — events don't mutate

<!-- TODO: show the Bene Anthropic and their axlotl tanks the finger -->
