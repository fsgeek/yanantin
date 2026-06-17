# C0 registration CLI inspector — design

Date: 2026-06-17
Status: designed, pending review
Builds on: `docs/superpowers/specs/2026-06-16-c0-registration-design.md` (the primitive, committed `c4749301`)

## Purpose

C0's registration primitive is poured (`src/yanantin/core/registration.py`):
`Registrar` + `RegistrantRecord`, 8 spec tests green against live `apacheta_test`.
But the registrar is *handed* a catalog-collection name by its caller — there is
no way for a human to **see** what has registered without writing Python against
a handle. This pour is the smallest next step: a read-path that makes the
registration tree visible. It proves the read path end-to-end and becomes the
debugging surface every later pour (linux-local-fs registrar, memory-anchor
service) is inspected through. Named first in the C0 next-pours order for exactly
this reason: smallest, proves the read path, makes everything visible.

## The shape, and the correction that produced it

The Indaleko precedent (`../indaleko/utils/registration_service.py`) is explicit:
the CLI **does not issue DB queries and does not name a collection.** It calls a
library (`IndalekoRegistrationService.get_provider_list()`) that owns the
hard-wired catalog name internally. The CLI is a thin presenter over a library
verb.

Our `Registrar.list_registrants()` is already the `get_provider_list()` analogue
(both are `FOR r IN <catalog> RETURN r`). What is missing is the Indaleko layer
*above* it: a thing that owns the well-known base-catalog name, so the CLI never
speaks a collection name. That missing seam is `RegistrationService`.

### Two read paths; v1 serves the catalog

- **"What has been registered"** — the catalog: who declared themselves
  (`list_registrants()` → name, kind, description, UUID, parent). **This is v1.**
- **"Data a registration maintains"** — contributions in an owned collection
  (`list_contributions()`). v1 shows a per-registrant *count* (one cheap call);
  full contribution dump is deferred.

### No semantic constant, and no service-identity value, reaches storage

yanantin's departure from Indaleko: Indaleko hard-wires a fixed `service_uuid`
into the service. yanantin does **not** persist any base-service UUID. The threat
model is the third-party data-custodian compromise (Canvas/Instructure-class
ransomware of ~9,000 schools is the live example), explicitly *against* the
"cloud is trusted" prior. A fixed constant at rest would be a crib shared across
every compromised installation.

The decision (settled during brainstorming, rejecting two alternatives):

- **Rejected — a fourth obfuscator verb `identifier()`** that maps a service-UUID
  *value*. This breaks the contract's load-bearing invariant: the obfuscator maps
  **labels, not values** (`_key`/`_id`/`_rev` are in `_ARANGO_META` and never
  mapped). An identity UUID is a value, not a schema label.
- **Rejected — derive the UUID as `uuid5(installation_namespace, "...")`.** This
  is per-installation only to the degree the namespace is, i.e. it is the *same*
  `uuid5(ns, semantic)` operation `collection_name` already performs — it adds
  nothing over the opaque collection name and adds surface.
- **Chosen — the opaque collection name is the only anchor.**
  `RegistrationService` holds the semantic constant `"core_registrants"` *in code*,
  runs it through `obfuscator.collection_name()`, and the opaque result is the
  per-installation anchor. Each compromised installation presents a different
  opaque catalog name with no fixed crib. One mapped thing, already in the
  contract, already tested, no new verb, no value obfuscation.

## Components

### 1. `RegistrationService` (additive, `src/yanantin/core/registration.py`)

The Indaleko `get_provider_list()` seam, minus the service-UUID machinery.

```python
BASE_REGISTRANT_CATALOG = "core_registrants"  # semantic; in code, never at rest

class RegistrationService:
    def __init__(self, db: StandardDatabase,
                 obfuscator: StorageObfuscator | None = None) -> None:
        # owns the well-known catalog name; builds the base Registrar
        self._registrar = Registrar(
            db, BASE_REGISTRANT_CATALOG,
            name="core registration service",
            description="the base registrant catalog",
            obfuscator=obfuscator,
        )

    def get_registrant_list(self) -> list[RegistrantRecord]: ...
    def lookup_by_identifier(self, registrant_id: UUID) -> RegistrantRecord | None: ...
    def lookup_by_name(self, name: str) -> RegistrantRecord | None: ...
    def contribution_count(self, registrant_id: UUID) -> int: ...
```

- `get_registrant_list` / `lookup_by_identifier` delegate to the base `Registrar`.
- `lookup_by_name` is Indaleko parity (`lookup_provider_by_name`). Kept: names are
  *values* (unobfuscated), so this is a cheap `FILTER` on a value — exactly the
  verb a human inspector wants ("show me the linux-fs provider"). It scans the
  registrant list and matches `registrant_name`.
- `contribution_count` returns the count of contributions a registrant owns, for
  the CLI's count column. v1 may report `0`/`n` from `len(list_contributions(id))`
  on the base registrar's owned collection; this is acceptable at C0 scale and is
  the only place the "data a registration maintains" path is touched.

The CLI speaks **none** of these collection names — that is the whole point of
the seam.

### 2. `src/yanantin/core/__main__.py` — the CLI

House style (`infra/__main__.py`, `jabberwock/__main__.py`): `argparse`,
`cmd_*` functions, `def main() -> None` reading `sys.argv`, `uv run python -m
yanantin.core`. A `--json` flag mirrors the jabberwock convention.

- Builds the DB handle via `ApachetaDBConfig().connect(tier=...)`, default
  `tier="test"`, `--tier {test,app}` to switch.
- Constructs `RegistrationService(db)` (transparent obfuscator by default; the
  fortress path supplies a keyed one — out of scope for the CLI).
- Subcommands:
  - `list` (default): table — `name · kind · uuid · parent · contributions ·
    description`. `--json` emits the records as JSON.
  - `show <uuid>`: one registrant's full record (including the open `extra` tail),
    text or `--json`.

### 3. Tests

- `tests/integration/test_core_registration_service.py` (live `apacheta_test`):
  - service round-trips a registrant through `get_registrant_list` /
    `lookup_by_name` / `lookup_by_identifier`;
  - the base catalog collection is created on construction;
  - `lookup_by_name` returns `None` for an unknown name (not a raise).
- `tests/integration/test_core_cli.py` (jabberwock-style `monkeypatch sys.argv`
  + `capsys`, but **integration** because it touches a live handle): `main()`
  with `list` prints a registered name to stdout; `--json` parses; `show <uuid>`
  prints the record. `main()` resolves its DB handle via
  `ApachetaDBConfig().connect("test")` — the same live `apacheta_test` the
  registration integration tests use; no in-memory store (registration has no
  memory backend, unlike jabberwock). The test registers a known registrant,
  then asserts the CLI surfaces it.

## Out of scope (YAGNI)

- **No DB-scanning catalog discovery.** Would pre-build the catalog-of-catalogs
  C0 does not yet have. The base catalog is reached by its one well-known name.
- **No `identifier()` obfuscator verb / no base-service UUID at rest.** Rejected
  above.
- **No `--raw` (obfuscated) view.** Obfuscation is already asserted by existing
  red-bar tests; a raw view is not urgent. Deferable.
- **No full contribution dump / no recursive tree rendering.** The registrar tree
  is one level deep at C0; a flat list with a `parent` column is honest to current
  depth. A recursive renderer is added when the tree actually nests.

## Findings filed separately (not this pour)

Two latent leaks in Pukara's `SchemaMap`, surfaced during brainstorming, to be
filed as Pukara issues:

1. `_obfuscate_recursive` (schema_map.py) passes a key through **unmapped** on a
   `_field_cache` miss (line ~239) — a silent plaintext-label leak when the cache
   was not pre-populated by prior `field_name` calls.
2. Two parallel field-mapping mechanisms coexist — explicit per-key
   `field_name(k)` mapping (e.g. `activity/backends/arango.py:140`) vs. the
   recursive whole-doc `obfuscate_document`. The recursive path is the fragile
   one (the cache-miss above); the divergence is worth reconciling.

## Verification

1. `RegistrationService` round-trip → green integration test against
   `apacheta_test`.
2. `uv run python -m yanantin.core list` prints the registrant table from a live
   DB → CLI test green.
3. The base catalog collection name at rest is the obfuscated form of
   `"core_registrants"`, never the literal — covered by the existing
   field/collection obfuscation red bars (the service introduces no new naked
   constant at rest).
