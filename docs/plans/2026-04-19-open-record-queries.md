# Plan: Open-Record Query Methods for ApachetaInterface

**Date:** 2026-04-19
**Author:** Claude Opus 4.7 (Master Builder)
**Driven by:** Hamut'ay hand-off `docs/yanantin-handoff-open-record-queries.md` (commit `ac6209a` in `~/projects/hamutay`)
**Tensor:** T39 ("The False Symmetry") — architectural decision record for the AQL-native conversion
**Status:** Ready for execution. Written to survive context loss — a new Master Builder instance should be able to resume from this document without re-reading the conversation that produced it.

---

## Why this document exists

The hand-off spec is the *what*. This plan is the *how*, tailored to yanantin's role separation (Master Builder coordinates, Builder subagents write application code, Codex writes tests) and to the context budget of the current Master Builder instance (70% consumed at planning time, 35% tokenizer inflation a real factor). The plan is deliberately structured so that any step can be a resumption point.

If you are a new Master Builder picking this up: read sections 1, 2, 6, and 7, then check git log for which commits have already landed (by commit message prefixes listed in §4). Resume at the first step whose commit is not present.

---

## 1. Context check before starting

Before implementing anything, verify that the surrounding claims are still true. The hand-off was last updated at hamut'ay commit `ac6209a`; the yanantin environment at time of writing has these properties:

- `ApachetaBaseModel` (`src/yanantin/apacheta/models/base.py`) is bare with `extra="allow"`. No `provenance` or `lineage_tags` fields on the base; those are on typed subclasses (`TensorRecord`, `CompositionEdge`, etc.).
- `ProvenanceEnvelope.timestamp` (`src/yanantin/apacheta/models/provenance.py:28`) exists with `default_factory=lambda: datetime.now(timezone.utc)`. This is the ordering key for all queries.
- `StorageObfuscator` Protocol (`src/yanantin/apacheta/storage_obfuscator.py`) has `collection_name`, `field_name`, `reverse_field`, `obfuscate_document`, `deobfuscate_document`, `is_transparent`. It does *not* yet have `field_path` for nested paths — this plan adds it.
- `TransparentObfuscator` is the only implementation in-tree. **There is no `SchemaMap` class in Pukara** (the blueprint claims one exists but it's not present in `~/projects/pukara/src/pukara/`). This removes the cross-repo coordination risk I flagged in conversation: the `field_path` extension only needs to land in the yanantin Protocol + TransparentObfuscator. When a real obfuscator lands in Pukara later, it'll implement the extended Protocol at that time.
- Four classes implement `ApachetaInterface`:
  - `InMemoryBackend` (`backends/memory.py`) — full impl of new methods
  - `ArangoDBBackend` (`backends/arango.py`) — full impl of new methods (AQL-native)
  - `DuckDBBackend` (`backends/duckdb.py`) — `NotImplementedError` stubs
  - `ApachetaGatewayClient` (`clients/gateway.py`) — `NotImplementedError` stubs (Pukara routes not yet implemented; separate PR when they are)

Verify these before proceeding. If any have changed, adjust the plan accordingly and note the delta.

---

## 2. Deliverables

Five abstract methods on `ApachetaInterface`, implementations in the four classes above, and a Protocol extension for nested field paths. Scope is fixed by the hand-off spec; do not expand.

**Interface additions** (`src/yanantin/apacheta/interface/abstract.py`):

```python
# ── Open-Record Queries ──────────────────────────────────────
# Queries over the open-schema records collection — records stored
# via store_record() that don't fit a prescribed schema. Added
# for hamutay's taste_open cross-session memory access.

@abstractmethod
def list_open_records(
    self,
    limit: int | None = None,
) -> list[tuple[UUID, ApachetaBaseModel]]: ...

@abstractmethod
def query_open_by_author_instance(
    self,
    author_instance_id: str,
    limit: int | None = None,
) -> list[tuple[UUID, ApachetaBaseModel]]: ...

@abstractmethod
def query_open_by_lineage_tag(
    self,
    tag: str,
    limit: int | None = None,
) -> list[tuple[UUID, ApachetaBaseModel]]: ...

@abstractmethod
def query_open_has_field(
    self,
    field: str,
    limit: int | None = None,
) -> list[tuple[UUID, ApachetaBaseModel]]: ...

@abstractmethod
def list_author_instances(self) -> list[str]: ...
```

Docstrings: copy from the hand-off spec §Signatures verbatim. They encode the conventional-not-structural semantics (records without provenance are skipped, not raised on) that are load-bearing.

**Obfuscator Protocol extension** (`src/yanantin/apacheta/storage_obfuscator.py`):

```python
# On the Protocol
def field_path(self, parts: tuple[str, ...]) -> str: ...
```

Rationale for the tuple signature: dots in "provenance.timestamp" are AQL path separators, not part of any field name. Translating a dotted string as a unit would produce nonsense if the obfuscator swaps field names. Each part must be translated individually (via `field_name`) then joined with ".".

`TransparentObfuscator.field_path`:

```python
def field_path(self, parts: tuple[str, ...]) -> str:
    return ".".join(parts)
```

A real obfuscator would: `return ".".join(self.field_name(p) for p in parts)`.

---

## 3. Architectural principles to preserve

These are load-bearing and come out of T39 + the hand-off conversation. Any implementation that violates them is wrong even if tests pass.

1. **Conventional-not-structural for provenance.** Records without a provenance envelope are *skipped* by author/timestamp queries, not raised on. Never assume `record.provenance` exists; probe via `getattr(record, 'provenance', None)` or equivalent. The `test_query_open_by_author_instance_skips_records_without_provenance` contract test pins this.

2. **AQL-native for arango, not load-all-and-filter.** This is the conversion inflection. New code uses AQL with indexes. If you find yourself writing `for doc in collection.all(): if ...`, stop — that's the debt pattern T39 names. Existing `_load_all` query paths are out of scope for this PR but are technical debt on a separate track.

3. **Ordering via `provenance.timestamp`.** Strict `SORT DESC` on the nested path (reached via `field_path(("provenance", "timestamp"))`). Records without provenance get AQL's `null`-handling behavior (end of DESC) — implementation-defined but deterministic.

4. **Builder/Test-Author separation.** Implementation commits carry *no tests*. Tests are written by Codex (or another non-Claude test author) in separate signed commits. The acceptance criteria in the hand-off §Acceptance criteria are a *contract*, not code to copy.

5. **DuckDB and Gateway raise NotImplementedError.** Honest placeholders, not partial impls. Match the hand-off's message: `"DuckDB open-record queries deferred. Use Arango or memory backend."` For the gateway, use `"Open-record queries not yet available via Pukara gateway (routes pending)."`

---

## 4. Commit sequence

Each commit leaves the test suite green. Signing identity is yanantin's key for all implementation commits:

```bash
git -c user.email=yanantin@wamason.com -c user.name="Tony Mason" commit -S -m "..."
```

Key fingerprint: `1E416B1FB63AF88179EE0F38D0CAB9659C950893` (per MEMORY.md; verify before signing).

### Commit 1: `feat(apacheta/obfuscator): add field_path for nested AQL paths`

Files:
- `src/yanantin/apacheta/storage_obfuscator.py` — add `field_path` to Protocol and `TransparentObfuscator`

Rationale: lands the Protocol extension first so the arango backend can depend on it. Small, isolated change.

### Commit 2: `feat(apacheta/interface): add open-record query methods`

Files:
- `src/yanantin/apacheta/interface/abstract.py` — five new abstract methods in a new `# ── Open-Record Queries ──` section, placed below query methods and above `count_records`

At this commit the abstract methods exist but no backend implements them, which means every backend class becomes unconstructable (ABC error). The next four commits restore buildability. **Do not run the full test suite between commits 2 and 6** — it will fail because of the ABC issue. Run it after commit 6.

Alternative: land commits 2-6 as a single commit. The handoff's suggested sequence splits them for signing-key cleanliness, but they're atomic in practice. Judgment call: if the test suite expects each commit to be green in isolation (CI's separation workflow does), batch them. Check `.github/workflows/separation.yml` before deciding.

### Commit 3: `feat(apacheta/backends/memory): open-record queries`

Files:
- `src/yanantin/apacheta/backends/memory.py` — implement all five methods against `self._records` dict

Implementation notes:
- `list_open_records`: iterate `self._records.items()` in `reversed()` order (newest-first = most-recently-inserted-first). Apply `limit` after ordering. Use `self._deep_copy(record)` for each return.
- `query_open_by_author_instance`: iterate, skip records where `getattr(record, 'provenance', None) is None or record.provenance.author_instance_id != author_instance_id`, apply limit after reversed-order filter.
- `query_open_by_lineage_tag`: iterate, skip records where `tag not in getattr(record, 'lineage_tags', ())`.
- `query_open_has_field`: iterate, check `field in (record.model_extra or {})` — note pydantic v2 `model_extra` can be `None` when no extras; handle both.
- `list_author_instances`: iterate, collect distinct `record.provenance.author_instance_id` where provenance exists.
- All methods acquire `self._lock`, call `self._enforce_access("system", op_name)`.

### Commit 4: `feat(apacheta/backends/arango): open-record queries (AQL-native)`

Files:
- `src/yanantin/apacheta/backends/arango.py` — implement all five methods using AQL; extend `_ensure_collections` (or add `_ensure_indexes`) to create persistent indexes on `provenance.author_instance_id` and `lineage_tags`

Implementation notes:
- **Indexes.** ArangoDB persistent indexes via python-arango: `collection.add_persistent_index(fields=[self._map.field_path(("provenance", "author_instance_id"))])` and `collection.add_persistent_index(fields=[self._map.field_path(("lineage_tags",)) + "[*]"])`. The `[*]` suffix on the lineage_tags index is AQL's array-index marker — indexes each element of the array.
- **Idempotency.** `add_persistent_index` throws if the index exists. Check first:
  ```python
  existing = {tuple(idx["fields"]) for idx in collection.indexes() if idx["type"] == "persistent"}
  if (field,) not in existing:
      collection.add_persistent_index(fields=[field])
  ```
  Put this in `_ensure_indexes()` called from `_ensure_collections()` after collection creation. Only on the "records" collection for now.
- **AQL shape.**
  - `list_open_records`: `FOR doc IN @@col SORT doc.<provenance_ts_path> DESC LIMIT @limit RETURN doc`. Use `bind_vars={"@col": mapped_collection_name, "limit": limit or ALL}` — AQL has no "no limit" so if `limit is None`, skip the LIMIT clause (conditional query string).
  - `query_open_by_author_instance`: `FOR doc IN @@col FILTER doc.<author_path> == @aid SORT doc.<ts_path> DESC LIMIT @limit RETURN doc`.
  - `query_open_by_lineage_tag`: `FOR doc IN @@col FILTER @tag IN doc.<tags_path> SORT doc.<ts_path> DESC LIMIT @limit RETURN doc`.
  - `query_open_has_field`: `FOR doc IN @@col FILTER HAS(doc, @field) SORT doc.<ts_path> DESC LIMIT @limit RETURN doc`. The `@field` is bind-var-safe because `HAS()` takes the field name at runtime.
  - `list_author_instances`: `FOR doc IN @@col FILTER doc.<author_path> != null RETURN DISTINCT doc.<author_path>`.
- **Hydration.** Results come back as raw docs; hydrate each via `self._from_generic_doc(doc)`. Return `list[tuple[UUID(doc["_key"]), model)]`. For `list_author_instances`, results are strings, return `list[str]`.
- **Obfuscator use.** Never hardcode field names. Always go through `self._map.field_path(("provenance", "author_instance_id"))` etc. The mapped collection name is `self._map.collection_name("records")`.
- **Null-safety.** Records stored without provenance lack `doc.provenance` entirely. AQL's `null` handling (FILTER on null-valued nested paths) yields `null`, which does not satisfy `==` comparisons — so records without provenance are naturally excluded from author-filtered queries. This implements the conventional-not-structural contract without explicit skip logic. For `list_open_records` (no filter), `SORT DESC` puts nulls last — that's the implementation-defined ordering the spec names.

### Commit 5: `feat(apacheta/backends/duckdb): open-record queries raise NotImplementedError`

Files:
- `src/yanantin/apacheta/backends/duckdb.py` — five methods, each raising `NotImplementedError("DuckDB open-record queries deferred. Use Arango or memory backend.")`

Per T39, DuckDB is deprecated from `ApachetaInterface`; these stubs are honest placeholders until deletion.

### Commit 6: `feat(apacheta/clients/gateway): open-record queries raise NotImplementedError`

Files:
- `src/yanantin/apacheta/clients/gateway.py` — five methods, each raising `NotImplementedError("Open-record queries not yet available via Pukara gateway (routes pending).")`

Deferred because Pukara has no routes for these yet. When Pukara grows them, this file gets a proper HTTP-call implementation in a coordinated PR.

### After commit 6: full test suite

`uv run pytest` should be green. If it isn't, that's the signal to pause and diagnose — ABC issues, import errors, existing tests that touched the interface.

### Tests (by Codex, separate signed commits)

Contract is in hand-off §Acceptance criteria. Test author decides file organization, fixture naming, arango skip guards, cleanup strategy. Codex dispatch recipe:

```bash
codex exec --full-auto -m gpt-5-codex \
  "Read docs/plans/2026-04-19-open-record-queries.md and the acceptance criteria \
   in ../hamutay/docs/yanantin-handoff-open-record-queries.md. Write the pytest \
   suite that enforces the contract. Memory backend: unit tests. Arango backend: \
   integration tests with APACHETA_SKIP_ARANGO env guard. DuckDB + Gateway: \
   NotImplementedError tests. Commit signed with your identity, not yanantin's."
```

Adjust the Codex invocation to match current conventions in MEMORY.md.

---

## 5. Acceptance

When complete:

- [ ] `uv run pytest` green across unit + red-bar + integration
- [ ] `codex exec` test commits landed with Codex's signing identity
- [ ] Commit log shows yanantin-signed implementation + Codex-signed tests, no mixed authorship
- [ ] A smoke test confirms Hamut'ay's `apacheta_bridge.py` can call all five methods against the memory backend (hamut'ay-side, not yanantin-side; flag when this verifies)
- [ ] MEMORY.md cairn-line updated if a tensor is written for this work (probably not necessary; T39 already carries the decision)

---

## 6. Risks and open questions

- **Index creation idempotency in tests.** ArangoDB integration tests may run against fresh or dirty databases. `_ensure_indexes` must tolerate both. The check-before-add pattern in §4 handles this; verify under integration.
- **`@@col` bind-var handling in python-arango.** Collection names are bound via `@@name` (double-@) not `@name` in AQL. Confirm syntax in the driver docs before writing the queries; a typo here turns into runtime errors that are annoying to trace.
- **`model_extra` edge case.** For records constructed without extras, pydantic v2 may set `model_extra` to `None` or `{}` depending on how the model was built. The memory backend's `query_open_has_field` must handle both. The arango backend sees serialized JSON where unset extras are simply absent top-level fields — `HAS(doc, @field)` is correct either way.
- **Gateway client stubs may break existing tests.** If any existing tests construct `ApachetaGatewayClient` in a way that expects it to be fully-implementing, adding new abstract methods makes it ABC-unconstructable until stubs land. Audit `tests/` for gateway construction before commit 2.
- **The blueprint is wrong about SchemaMap.** It claims Pukara has `schema_map.py` implementing `SchemaMap`; it does not. This is out of scope to fix here but worth flagging for the next Tinkuy audit — add to the governance-PR follow-up.

---

## 7. Resumption guide for the next Master Builder

If the current Master Builder ran out of context before finishing, here's how to pick up:

1. Check git log for commits starting with `feat(apacheta/obfuscator)`, `feat(apacheta/interface)`, `feat(apacheta/backends)`, `feat(apacheta/clients/gateway)`. Count what's landed.
2. If the obfuscator extension (commit 1) is missing, start there — it's a five-line change and unblocks everything downstream.
3. If some backends are implemented and others aren't, finish the missing ones. Memory is simplest; arango is most involved; DuckDB and Gateway are trivial stubs.
4. Don't write tests. That's Codex's job, per §4 and §3.4.
5. After all impl commits land, run the full test suite (`uv run pytest`). If red, stop and diagnose.
6. Dispatch Codex for tests per the recipe in §4.
7. When you're done, consider whether to:
   - Update `docs/blueprint.md` (probably not — blueprint is already flagged stale; wait for Tinkuy audit)
   - Write a tensor (probably not — T39 already carries the decision; a closing tensor would be cycle-close reporting, which is different)
   - Notify Hamut'ay. A short commit-reference is sufficient: "impl landed, smoke-test your bridge."

**Load-bearing warnings:**
- Do not extend load-all-and-filter in arango. If tempted, re-read T39.
- Do not add `created_at` or any other timestamp field to `ApachetaBaseModel`. That was conceded during planning; adding it now resurrects a zombie.
- Do not bundle tests into implementation commits. Builder/Test-Author separation is enforced by CI and by cultural norm both.

---

## 8. Execution mode

The Master Builder who wrote this plan is operating at ~70% context consumption. Decision tree for execution:

- **If budget ≥ ~250K tokens remaining after plan commit:** dispatch Builder subagent (Claude Sonnet via Agent tool with `subagent_type="general-purpose"`) with this plan document. Builder performs commits 1-6. Master Builder reviews diff, runs tests.
- **If budget is tight:** commit this plan and stop. A fresh Master Builder instance picks up from §7.
- **Do not attempt implementation in the Master Builder's own context.** That violates role separation (CLAUDE.md: "The Master Builder does not write application code directly.").

The next section is for the Builder subagent or the next Master Builder. If you are Tony or a scout, you can stop reading here.

---

## 9. Builder dispatch prompt (for Agent tool)

```
You are a Builder subagent for the Yanantin project. Task: implement open-record
query methods per /home/tony/projects/yanantin/docs/plans/2026-04-19-open-record-queries.md.

Read that plan in full before writing code. Also read:
- /home/tony/projects/hamutay/docs/yanantin-handoff-open-record-queries.md (the spec)
- /home/tony/projects/yanantin/docs/cairn/T39_20260419_the_false_symmetry.md (the architectural decision)
- /home/tony/projects/yanantin/CLAUDE.md (project norms)

Execute commits 1-6 per the plan's §4. Sign each commit with yanantin's identity:
  git -c user.email=yanantin@wamason.com -c user.name="Tony Mason" commit -S -m "..."
Key fingerprint: 1E416B1FB63AF88179EE0F38D0CAB9659C950893

Do NOT write tests. That's Codex's job. Your commits contain only implementation.

When done, run `uv run pytest` and report:
- Commits made (SHA + subject for each)
- Test suite status (green, or specific failures with stack traces)
- Any surprises or decisions you had to make that weren't specified in the plan
- Any ways the plan was wrong about the current state of the code

If any existing test was affected, surface it — do not modify tests to make them pass.
If the plan is wrong about something structural (wrong file path, missing dependency,
etc.), stop and report rather than working around it.
```

---

*End of plan.*
