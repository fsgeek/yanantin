# Design: The AQL Field-Mapping Guardrail

**Status:** design, not yet implemented
**Author:** Yanantin AI (Claude Opus 4.8), 2026-06-30, with Tony
**Implements:** rung (2)/(3) of the Arango façade chokepoint roadmap; the genuinely-open AQL field-reference seam.
**Will outlive a single context window. Phase 2 is a multi-step migration. Read the whole doc before touching code.**

---

## 1. The one-sentence problem

A field name written into an AQL query string is a semantic name (`timestamp`, `provenance.author_instance_id`) that **must** be translated to its physical/obfuscated storage name before it reaches ArangoDB — and today nothing structurally forces that translation, so a future instance writing `f"FILTER doc.timestamp == @x"` produces a query that runs, goes green under the transparent test obfuscator, and silently breaks under a real (opaque) obfuscator.

This is the same failure family as the silent-transparent-default bug fixed in commit `248e56c2`: **a correct-but-optional boundary that the environment teaches you to bypass.** The defense is the same shape: make the safe path the *only* greppable path, and add a build-failing red-bar so the unsafe path can't silently return.

Tony's framing: *structural guardrails to prevent future instances from electrocuting themselves without knowing the outlet is hot.*

## 2. What we are NOT building (scope discipline)

We analyzed the full population of 39 `aql.execute` call sites (see §4). The temptation is a general typed query builder — predicate trees, operator enums, `OR`/grouping. **We are not building that**, because:

- The population uses exactly five operators (`==`, `IN`, `HAS`, `<=`, `!=`), all standalone.
- Filters are an independent, flat, `AND`-only conjunctive list. **Zero** queries use `OR`, `NOT`, grouping, or nested boolean structure.
- A builder for structure that has no callers is speculative generality (CLAUDE.md §2; the premature-collapse and extract-on-the-second-instance lessons).

The insight that collapses the design (Tony): **composition is not the dangerous part — unmapped field names are.** Operators, AQL keywords, traversal direction, `HAS(...)` — authors compose those freely in raw AQL. The *only* thing that must be funneled through a sanctioned primitive is the **field reference**, because that is the single position where a semantic↔physical translation is mandatory and silently omittable.

So this is not a builder. It is **one required primitive** (an already-existing function, `field_path`, made the sole sanctioned door) plus the structural enforcement that makes "required" mean something.

## 3. The primitive

It already exists. `StorageObfuscator.field_path(parts: tuple[str, ...]) -> str` maps each part through the obfuscator and joins with `.`. We are not inventing a mechanism; we are **exposing the existing mechanism as the one required way to name a field in raw AQL**, and demoting its overlapping sibling.

### 3.1 Why `field_path` (tuple) and not `field_name` (string)

Today there are two overlapping entry points:

- `field_name(semantic: str) -> str` — maps one bare name.
- `field_path(parts: tuple[str, ...]) -> str` — maps each part of a nested path.

For a top-level field they produce the same result, so `field_name("timestamp")` and `field_path(("timestamp",))` are redundant. The redundancy is the crack:

- `field_name` takes a **bare string with no positional structure**, which invites `f"doc.{field_name(x)}"` — the leaky f-string interpolation form (see §4, Regime 2). It is the entry point that reads as "drop a name into text."
- `field_path` takes a **tuple that encodes nesting**. `("provenance", "timestamp")` says *the `timestamp` field inside `provenance`*, and the obfuscator maps **each part independently** — exactly the nested-path mapping that string-splitting at the call site ("a thing I'll forget") gets wrong.

**Decision: `field_path` (tuple, always) is the one sanctioned primitive for naming a field in a query.** `field_name` survives as the *internal per-part helper* that `field_path` calls (it already is — `field_path` is `".".join(field_name(p) for p in parts)`), but it is no longer a sanctioned public call for building queries.

### 3.2 The doc-obfuscation exception (DO NOT MIGRATE)

**Critical distinction the migration must preserve.** `field_name` has a second, *legitimate and different* use: obfuscating the keys of a whole **document** on the write path —
`mapped_doc[self._map.field_name(k)] = v` (activity backend lines ~144-148, ~244-252).

This is mapping a *document's keys*, not naming a *field in a query string*. It is correct as-is. The primitive `field_path` is for the **query-field** position. Document obfuscation is a separate concern (`obfuscate_document` already exists for the bulk case; per-key `field_name` in a write loop is fine). **Migrating document-key mapping to `field_path` would be wrong.** §4 classifies every site so this line is never blurred.

### 3.3 The author already knows the class (why a tuple of strings is enough)

A reasonable objection: a bare field string is unchecked — typo `("timestmp",)` and the obfuscator maps a nonexistent field silently. Why not bind the field to its pydantic model and validate?

Resolution (Tony): the `doc`-dependence of a field is **resolved at write-time by the author, not at query-time by the builder.** Whoever writes `HAS(doc, @field)` already holds the type — they know `doc` ranges over `records` hydrating to `ApachetaBaseModel`. The field's domain is closed by the author's possession of the type. A static, model-keyed field token (e.g. `Model.f.timestamp` failing at import on a typo) is *stronger* and is noted as a **possible future hardening** — but it requires every model to generate a token namespace, which brushes the "deliberate manual rebuild" line (§7). It is explicitly **out of scope for Phase 1/2**; the tuple-of-strings primitive is the proportionate floor for a rare-case surface.

## 4. The population (ground truth, 2026-06-30)

39 `aql.execute` sites across three files. Three regimes:

**Regime 1 — disciplined (`apacheta/backends/arango.py`, ~7 sites).** Already the target state: `@@col` bind for collection, `field_path((...))` for every field, value via bind var. `list_open_records`, `query_open_by_author_instance`, `query_open_by_lineage_tag`, `query_open_has_field`, `list_author_instances`. These are the **model to converge on.** They are ~90% duplicated skeleton differing only in the FILTER predicate.

**Regime 2 — leaky f-string (`activity/backends/arango.py`, ~9 sites).** Build the query with `f"FILTER doc.{f_pid} == @x"` where `f_pid = field_name("provider_id")`. The field *is* mapped, so this is **not currently a security leak** — but it is the exact dangerous *form* (`f"doc.{x}"`) that breaks the day someone interpolates an unmapped name. Also interpolates `{col}` (collection) into text instead of binding `@@col`. **These are the primary Phase-2 migration targets.**

**Regime 3 — genuine exceptions (template-only).** Sites that cannot be a flat collection-scan and must stay hand-written, vetted templates:
- Graph traversal (`apacheta/backends/arango.py:425`): `FOR v,e,p IN 1..@max_depth {aql_dir} @start {mapped_edges}`. `{aql_dir}` is `OUTBOUND/INBOUND/ANY` — a keyword AQL **forbids** binding. Closed 3-value enum (`_LLIKA_DIRECTION_AQL`), so still mechanical, but not a bindable position.
- `RETURN LENGTH({col})` count forms — collection name in a non-bindable position.

**Predicate shapes (all that exist) — four leaf forms, not one:**
| Shape | Example | Field position |
|---|---|---|
| A. `field OP value` | `doc.{path} == @aid` | left, mapped |
| B. `value OP field` | `@tag IN doc.{path}` | right, mapped |
| C. `FUNC(doc, field)` | `HAS(doc, @field)` | field is a **bind value**, already data — the most secure form |
| D. `field OP literal` | `doc.{path} != null` | right side is keyword, no bind |

The guardrail covers all four: every one names its field through `field_path`. Composition (the `AND` of multiple FILTERs, the `IN`/`HAS` keyword choice, the traversal direction) stays in the author's raw AQL.

## 5. Phase 1 — Foundation (additive, no migration, buildable in one sitting)

Goal: make the safe path exist and be enforced, **without changing any existing call site's behavior.** Phase 1 is additive and reversible; it must not touch the live query paths.

1. **Sanction `field_path` as the field primitive.** Document on the `StorageObfuscator` protocol that `field_path(parts)` is the *only* sanctioned way to render a field name into an AQL string. Add a docstring stating the contract and pointing at this doc.
   - verify: protocol docstring states it; no behavior change; suite still green.

2. **Red-bar: no literal field interpolation in AQL.** `tests/red_bar/test_no_literal_aql_field_refs.py` — scan `src/` for the dangerous form: an f-string AQL fragment that interpolates a name into a `doc.{...}` / `d.{...}` / `e.{...}` field position, i.e. `f"...(doc|d|e|v)\.\{..."`. Assert zero **outside** the obfuscator module.
   - **This red-bar is BORN RED** — Regime 2 (~9 sites) currently violates it. That is correct and intended: it makes the Phase-2 work-list visible and build-failing. Until Phase 2 lands, it runs in the **informational (continue-on-error) red_bar lane**, like the other tracked-but-open red bars — visibly red, never green-by-skip. When Phase 2 completes it goes green and *moves to the blocking lane*.
   - verify: the red-bar fails now, naming exactly the Regime-2 sites; it passes against the Regime-1 sites.

3. **Red-bar: `field_name` is not called to build a query.** Harder to express structurally (document-key mapping legitimately calls `field_name` — §3.2). Phase 1 ships the §5.2 interpolation scan, which catches the actual danger (interpolation), and **defers** a `field_name`-call-site scan until Phase 2 has separated query-field calls from doc-key calls. Do not try to ban `field_name` wholesale in Phase 1 — it has a legitimate caller.
   - verify: documented as deferred, with the reason, so the next instance doesn't "fix" it prematurely.

**Phase 1 exit criteria:** `field_path` is the documented sanctioned primitive; the interpolation red-bar exists and is red-in-the-informational-lane with an accurate work-list; zero behavior change; full suite green (minus the new, expected-red informational bar).

## 6. Phase 2 — Migration (multi-step; THE PART THAT WILL OUTLIVE A CONTEXT WINDOW)

This converts each Regime-2 site to the Regime-1 shape: collection via `@@col` bind, every field via `field_path`, value via bind var. **It is a wide, stateful sweep across the live backends. This is exactly the migration shape that stalled at Task 7 in `docs/handoff-collector-recorder-architecture.md` — old stack live, new stack orphaned.** The structure below exists to prevent that: each step is independently landable, independently verified, and leaves the suite green.

**The discipline that prevents a Task-7 stall:** every step is a complete, committable, green-suite unit. Never leave a half-migrated file. If context runs out mid-Phase-2, the last commit must be a coherent stopping point, and this doc's checklist must be updated to mark which steps are done. A step is not done until its tests pass against the **live DB** (no-mock-databases) AND under a **non-transparent** test obfuscator (the boundary the whole exercise protects must be exercised — a green under the transparent default proves nothing).

Per-site, per-step (one site or one tightly-coupled cluster per commit):

- **2.0 — Classify (already done in §4; re-verify before each step).** Confirm the site is a *query-field* use, not a *document-key* use (§3.2). Document-key sites are NOT migrated.
- **2.x — For each Regime-2 site:**
  1. Replace `{col}` text interpolation with `@@col` bind.
  2. Replace `f"doc.{field_name(x)}"` with a bind to `field_path((x,))` — i.e. `FILTER doc[@f] == @v` with `bind_vars[@f] = field_path((x,))`, OR keep the dotted form only via `field_path` if the index requires a literal path (note: ArangoSearch/persistent indexes may need the literal dotted path, not `doc[@f]` — verify per site which form the index demands; this is a real per-site decision, not mechanical).
  3. Run that site's test under a non-transparent obfuscator on the live DB.
  4. Commit. Suite green. Update this doc's checklist.

**Open per-site question (must be resolved during migration, not now):** `doc[@field]` (dynamic field access by bind) vs literal dotted path via `field_path`. Dynamic access is safest (field never in text) but **may defeat indexes** — ArangoDB can use an index on `doc.timestamp` that it cannot use on `doc[@f]`. Each site must check whether it relies on an index; if so, the literal dotted path (still produced by `field_path`, still mapped, just not bound) is the correct form, and the red-bar's interpolation scan must distinguish "interpolating a *mapped* `field_path` result" (allowed) from "interpolating a *bare* name" (forbidden). **This is the genuinely hard part of Phase 2 and the reason it is not mechanical.** See §6.1.

### 6.1 The red-bar's hardest distinction

The §5.2 scan must eventually tell apart:
- `f"doc.{field_path((x,))}"` — **allowed** (the interpolated value came through the obfuscator).
- `f"doc.{x}"` where `x` is a bare/unmapped name — **forbidden**.

A pure text scan cannot see provenance of the interpolated variable. Options, in escalating cost:
- (a) Forbid ALL `f"doc.{...}"` interpolation; require dynamic `doc[@f]` everywhere. Simplest scan, but loses index usage where it matters.
- (b) Allow interpolation only of variables whose name matches a `*_path`/`*_field` convention assigned from `field_path(...)`. Convention-based; erodable.
- (c) A small AST check: the interpolated expression must be a call to `field_path`/`field_name` on the obfuscator, or a variable assigned from one in the same function. Most robust; most work.

**Decision deferred to Phase 2 with a bias toward (a) where indexes allow and (c) for the sites that need literal paths.** Do not pick now; the per-site index analysis (6.2 step) informs it.

### 6.2 Phase 2 step checklist (fill in during implementation)

- [x] activity/backends/arango.py `query_latest` (provider_id + timestamp, both branches) — **DONE 2026-07-01** (Yanantin AI). `@@col` bind; `provider_id`/`timestamp` via `field_path` as literal paths (both in the persistent index, §6.1).
- [x] activity/backends/arango.py `query_range` (the `" FILTER ".join` list builder — the most builder-like site) — **DONE 2026-07-01** (Yanantin AI). Each filter fragment names its field via `field_path`; the list-join and `AND` composition stay in raw AQL (design §4 — NOT a query builder). `@@col` bound. Both fields literal (indexed, §6.1).
- [x] activity/backends/arango.py `get_latest_anchor` (timestamp sort) — **DONE 2026-07-01** (Yanantin AI). `@@col` bind; `timestamp` via `field_path` literal — `activity_anchors` has a persistent index on `timestamp` (§6.1, verified live).
- [x] activity/backends/arango.py `list_providers` (`COLLECT provider = doc.<pid>`) — **DONE 2026-07-01** (Yanantin AI). `@@col` bind; `provider_id` via `field_path` literal (indexed). COLLECT names a field, so it takes the same sanctioned form.
- [x] activity/backends/arango.py:296-301 (`RETURN LENGTH(FOR ... FILTER ...)` — count) — **DONE 2026-07-01** (Yanantin AI). Migrated to Regime-1: `@@col` bind for the collection in BOTH branches (the `LENGTH({col})` sibling at :306 also moved to `@@col` — it was a text-interpolated collection name, cheap to bind, so not left as a template); `provider_id` filter names its field via `field_path(("provider_id",))`. **§6.1 index decision (verified against the live index, not guessed):** `activity_facts` has a persistent index on `(provider_id, timestamp)` — so the field is a **literal dotted path produced by `field_path`** (`f"doc.{pid_path}"`, the §6.1-*allowed* form), NOT dynamic `doc[@f]` access, which would defeat that index. Verified live under a non-transparent `PrefixObfuscator` (`tests/integration/test_aql_count_facts_obfuscated.py`) AND under the transparent default. **Precedent for the next site:** any FILTER on an indexed field takes the literal-`field_path` form; only un-indexed fields may use `doc[@f]`.
- [ ] apacheta/backends/arango.py:916 (`SORT doc.{ts_path}` — verify already-mapped, may be Regime-1-adjacent)
- [ ] registration.py:287, :358 (`field_name("contributor_id")` → confirm query-field; these feed `d[@field]` which is ALREADY the safe dynamic form — may need only the `field_name`→`field_path` swap, no interpolation fix)
- [ ] Regime-3 templates (traversal :425, `LENGTH({col})` :306): leave as vetted templates; add a comment marking them as deliberate template-tier, not migration debt.

**STATUS 2026-07-01 (Yanantin AI):** `activity/backends/arango.py` is FULLY migrated — all five query methods (`count_facts`, `query_latest`, `query_range`, `get_latest_anchor`, `list_providers`) are Regime-1; the red-bar reports **zero** offenders in this file. The interpolation red-bar `test_no_literal_aql_field_refs` is GREEN and **promoted to the blocking lane** (`.github/workflows/separation.yml` — its own gating step, separate from the still-informational red bars). REMAINING for full Phase-2 close: `apacheta/backends/arango.py:916` and `registration.py:287,:358` (see below) — the red-bar is green because those sites use the *already-safe* forms, but they should still be converted to `field_path` for uniformity before the guardrail is considered complete program-wide.

**Phase 2 exit criteria:** interpolation red-bar is GREEN and MOVED to the blocking lane; every query-field names through `field_path`; Regime-3 templates are explicitly marked; full suite green on live DB under a non-transparent obfuscator.

## 7. The wall: what is NOT in this design

Per the façade roadmap's line-16 verdict (a prior instance's judgment to the ayllu, not a fence): the *unified rebuild* — every writer routed through one façade so no un-obfuscated path is expressible anywhere — is reserved for a deliberate manual pass, because the all-at-once wide refactor is an LLM anti-pattern (the Task-7 stall is the receipt). This doc is the **buildable-now approximation that does not make that reset harder**: Phase 1 is additive; Phase 2 is incremental and per-site-reversible; neither rips out Pukara-as-bolt-on or unifies the writers. The static model-keyed field token (§3.3) and the full Database→Collection façade (roadmap rung 1) are explicitly downstream and out of scope.

## 8. Why the phasing is load-bearing (not bureaucracy)

- Phase 1 alone is *useful and safe even if Phase 2 never happens*: it makes the sanctioned primitive exist and the danger visible (red, informational). A future instance gains a documented safe door and a build signal — strictly better than today, with zero migration risk.
- Phase 2 is the risky part, and it is structured so a context-window death mid-migration leaves a coherent, green, partially-migrated tree plus an updated checklist — a foothold, not a fire. That property is the whole reason this is a written doc and not an inline task.

---

## Appendix: grounding receipts (verify before trusting; memory is a lead, not state)

- Silent-default fix that this extends: commit `248e56c2`, red-bar `tests/red_bar/test_obfuscator_default_is_explicit.py`.
- Roadmap parent: memory `arango-façade-chokepoint-roadmap...`; open-seam memory `open-issue-aql-field-reference-mapping...`.
- The migration scar to not repeat: `docs/handoff-collector-recorder-architecture.md` (stalled at Task 7).
- Population census command: `grep -rn "aql.execute" src/`. Re-run before implementing — this doc's site list is a 2026-06-30 snapshot.
