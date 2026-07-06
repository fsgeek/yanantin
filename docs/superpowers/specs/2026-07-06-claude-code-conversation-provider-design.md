# Claude Code Conversation Provider — Design

**Date:** 2026-07-06
**Status:** Draft for review
**Provenance:** Issue #33 (filed 2026-06-20, deliberately deferred until the storage
stack and a storage-change provider existed). The band aggregator merge
(c92cece2, 2026-07-06) satisfied the storage-change prerequisite; this design
un-defers #33 in revised form. Brainstormed with Tony 2026-07-06.

## 1. Purpose

Convert the Claude Code session transcripts in `~/.claude/projects/*/*.jsonl`
into activity-stream data inside yanantin. The transcripts are the richest
episodic record we have of AI actors at work, and they hold the half of the
picture the OS cannot see: **at the OS level every Claude instance is `tony`
running `node`; at the transcript level every event knows its session, turn,
model, and parent.** Joined against the storage activity bands, each stream
covers the other's blindness — the complementary-pair structure the project
is named for.

This is deliberately NOT a single-use-case build. The projections — actor
attribution, tool-usage analysis, semantic search over conversation text,
graph relationships between episodes — are **queries over the landed
substrate**, not designs of it. The design goal is fidelity: land the stream
richly enough that projections neither of us has thought of yet remain
possible.

### Episodic recall, not an index

The target capability is **episodic recall**, distinct from an index (qhaway
is an index — curated pointers, decided at write time). Pure semantic search
inverts the wrong way for memory: RAG maximizes recall, but for an agent
recalling its own past, **precision is scarce** — an overwhelming result set
is a failure mode, not a feature. The precision mechanisms are metadata:
Indaleko's measured result was a one-month temporal window cutting search
space 99.9%, and per-query facet discrimination
(`yanantin.llika.facets.FacetDiscrimination`, #34) iteratively identifies
which selector best splits *this* result set. Both mechanisms are only as
good as the metadata axes available to them. This substrate's spine —
time band, project, session, git branch, model, sidechain, tool mix — is
precisely that supply of discriminating axes, which conversation *text*
alone cannot provide. Semantic match proposes; facets and time dispose.

### The clock (discovered during brainstorming)

Claude Code retains transcripts for ~30 days by default; the oldest file in
the live tree is dated exactly 30 days back. The corpus is a rolling window —
history is being deleted daily. Countermeasure already taken (2026-07-06):
snapshot to `~/.yanantin/archive/claude-projects/` (778 files, 548 MB).
A recurring rsync (same timer as the collector run, §4.5) turns the corpus
from "rolling 30 days" into "grows forever." The collector reads the
**archive**, which strictly contains the live tree's history.

## 2. Data class: activity facts, not storage objects

Storage objects model **artifacts** — identity over time, state changes,
supersedes chains (#31). Conversation events are **episodes** — immutable,
timestamped, attributed occurrences. A turn is never superseded; there is no
"current version" of a tool call. So:

- Conversation events land as **`FactRecord`s in the activity stream store**
  (`yanantin.activity`) — the same class as storage activity bands, beside
  them, not inside `Objects`.
- The **spine/content shape recurs** (the one-schema-three-substrates
  decision): spine = who/when/where/sequence, content = text or tool payload.
  Same shape as the bands wear — which is what makes cross-stream joins cheap.
- The **JSONL file itself remains a storage object** — the carrier, already
  visible to the FS collector. Events carry a reference (`carrier_uri`,
  `carrier_line`) back to it. Structurally this is the semantic-transducer
  pattern: content in, derived facts out; the transduction is parsing rather
  than an LLM, but the architectural slot is the same.

## 3. The observed data (grounded 2026-07-06)

Census over a 40-file sample: event types `assistant`, `user`, `attachment`,
`system`, `mode`, `last-prompt`, `ai-title`, `file-history-snapshot`,
`permission-mode`, `queue-operation`, `started`, `result`. The schema is
undocumented and version-drifting — **no field enumeration at the collector**
(the `extra="forbid"` scar: whatever we enumerate today drops OS-of-the-AI
metadata forever).

Observed spine fields on user/assistant events — richer than #33 assumed:

| field | why it matters |
|---|---|
| `uuid` | native line identity → idempotency key for free |
| `parentUuid` | the conversation is an explicit **DAG** — branches/rewinds observable |
| `sessionId`, `timestamp`, `cwd`, `gitBranch`, `version` | session/where/when spine |
| `isSidechain` | subagent activity marked — actor attribution below session granularity |
| `message.model`, `message.usage` | per-turn model + token economics, free |
| `message.content[]` typed blocks | `tool_use` blocks carry tool name + input (file paths!) |

## 4. Architecture

Collector observes totally; recorder holds policy; projections are queries.

### 4.1 Collector — `ClaudeCodeSessionCollector`

`yanantin/collector/activity/claude_code/collector.py`, extending
`CollectorBase` (same seat as `FsIncrementalCollector`).

- **Input:** the archive tree (`~/.yanantin/archive/claude-projects/`),
  configurable.
- **Cursor:** state file mapping `file_path → {mtime, size, byte_offset}`
  (atomic write-to-temp + rename, same as the mtime collector). Transcripts
  are append-only in the normal case, so resume-from-offset is the fast path;
  if a file **shrank** or its prefix changed, rescan it whole — idempotent
  recording (§4.3) makes that safe, not merely tolerable.
- **Output:** batches of `ConversationEvent` witness payloads. One event per
  JSONL line. Unparseable lines are still observed — emitted as
  `event_type="unparseable"` with the raw text; observation is total.
- **Provider id:** `uuid5(NAMESPACE_DNS,
  "yanantin.collector.claude_code_sessions.{machine_id}")`.

### 4.2 Witness payload — `ConversationEvent`

Same design stance as `StorageActivityBand`: frozen, **`extra="allow"`**,
serialized into `FactRecord.data`; the store does not understand it.

Promoted spine fields (everything else rides along raw):

```
session_id: str          event_uuid: str | None    parent_uuid: str | None
event_type: str          role: str | None          ts: datetime
ts_source: str           project_slug: str         cwd: str | None
git_branch: str | None   is_sidechain: bool        model: str | None
carrier_uri: str         carrier_line: int
raw: dict                # the full parsed line, untrimmed
```

- `event_id() -> UUID`: the line's own `uuid` when present; otherwise
  `uuid5(NAMESPACE_URL, f"{session_id}|{carrier_uri}|{carrier_line}")` for
  uuid-less housekeeping lines (`mode`, `last-prompt`, …). Unlike the band
  key, collision here means *same line* — the silent-drop hazard documented
  in `band.py` does not apply.
- **Timestamps:** transcript timestamps are ISO-8601 UTC (aware —
  `_ensure_utc` is satisfied). Lines without a timestamp inherit the nearest
  preceding event's timestamp in the same file, else file mtime;
  `ts_source ∈ {"event", "inherited", "file_mtime"}` records which, so no
  synthesized time can masquerade as an observed one.

### 4.3 Recorder — `ConversationFactRecorder`

`yanantin/recorder/activity/claude_code/fact_recorder.py`, mirroring
`BandFactRecorder`: each event → `FactRecord(id=event.event_id(),
provider_id, timestamp=event.ts, data=event.model_dump())`, written through
`ActivityStreamStore`; `ImmutabilityError` on an existing id is skipped —
idempotent re-scan by construction.

Policy lives here: v1 policy is **record everything**, with content passing
through the same obfuscation boundary all stored content crosses. Curation
(if ever) is a recorder concern added later; the collector never filters.

### 4.4 What is stored vs. what is derived

The transcripts are already graph-structured (`parentUuid` DAG); what's
missing is that graph *inside the graph database*, traversable across
projects and entities. The dividing line is observability, not storage form:

**Stored — event facts** (the spine, §4.2).

**Materialized — observed edges.** The recorder writes edge documents for
relations that are directly present in the data, so native Arango graph
traversal works across the whole corpus:
- `parent_of`: event → event (`parentUuid` — the conversation DAG,
  sidechain subtrees included)
- `in_session`: event → session; `in_project`: session → project slug
- `touched`: `tool_use` event → file URI (weak path: URIs, same as the
  band adapter)

Materializing these is still "store what's observable" — each edge is a
field already on the line, made traversable, not an inference.

Honest cost: this is the one piece of **new store capability** in the pour.
`ActivityStreamStore` today has only `activity_facts` and `activity_anchors`
(document collections); observed-edge materialization adds an
`activity_edges` collection (Arango edge collection; memory/duckdb backends
get the minimal equivalent) with the same least-privilege posture. Edges are
idempotent the same way facts are: deterministic key from
(relation, from_id, to_id).

**Derived at query time** (never at collection time):
- **Attribution join:** storage band ⋈ `touched` edges on (path, time window).
- **Cross-episode / entity edges:** e.g. the session that *read* issue #33
  joined to the session that *filed* it; two sessions converging on the same
  file from different projects. Queries over landed facts and edges — not an
  inference engine, and not entity resolution (downstream, semantic-lane work).

### 4.5 Trigger

- **Now (weak path):** batch run — CLI entry point, invoked manually or by a
  systemd timer that also runs the archive rsync. Same discipline as the
  mtime-scan pour.
- **Named follow-on (not in this pour):** band-driven — storage activity
  bands over the transcript tree tell the collector which carriers changed.
  This is the **first real customer of the band stream** and is worth its own
  demonstration pour once live banding (fanotify) lands.
- Rejected as primary: Claude Code hooks (couples to the harness; only sees
  cooperative writers — the storage-watch path is the external vantage).

### 4.6 Synthetic twin (#27)

`SyntheticClaudeCodeSessionCollector`: generates JSONL session files with
known ground truth (N sessions × M turns, planted tool calls, planted DAG
branches, a uuid-less line, an unparseable line) and emits through the same
pipeline. This is the dual-collector rule applied, and it is what the
demonstration queries run against in CI, where the real corpus doesn't exist
(the non-portable-live-test lesson: guard on the corpus, skip-narrow when
absent — the synthetic path must NOT be the one skipped).

## 5. Acceptance: demonstration queries

One per projection named in brainstorming; each is a test, live-DB, no mocks.

1. **Attribution:** given a storage band on a repo file, return the session
   and turn whose `tool_use` wrote it (path + time-window join). CI form runs
   against synthetic data with planted ground truth.
2. **Tool usage:** tool-call counts by tool × project × week — the June
   tool-usage audit re-derived as a query instead of a one-off script.
3. **Text reach:** conversation text findable by content, scoped by a time
   band (AQL filter is sufficient for v1; ArangoSearch view tuning is not
   this pour).
4. **Graph:** native traversal of a `parent_of` chain including a sidechain
   subtree; plus one cross-session join (two sessions touching the same
   `cwd` within a window).
5. **Faceted episodic recall:** start from a text match over conversation
   content, run `FacetDiscrimination` over the result set's spine fields
   (project, time band, model, sidechain, tool mix), and show the chosen
   facet cutting the result set — the iterative narrow-by-selector loop,
   demonstrated on this substrate. This is the query that makes the
   recall-vs-index distinction concrete.

## 6. Non-goals (v1)

- Live tail / long-running service (#33's systemd sketch) — follow-on.
- Band-driven triggering — follow-on, first customer of live bands.
- Temporal-window reindex (#3) and ArangoSearch view tuning.
- Any qhaway integration or replacement (qhaway is a separate, smaller
  demonstration; this substrate may eventually subsume its role, but that is
  a future conversation, not a v1 goal).
- Cross-machine ingestion; single-machine paths suffice (weak path: URIs,
  same as the band adapter).

## 7. Risks

- **Schema drift** across Claude Code versions — mitigated by `extra="allow"`,
  `raw` preservation, `version` captured on every event, and the
  `unparseable` escape hatch.
- **Large lines** (hook outputs embed whole documents; `attachment` events
  are big). v1 stores them whole — 548 MB total is well within Arango
  comfort. If growth demands it, dedup via `content_hash` is a recorder
  policy change, invisible to the collector.
- **Sidechain double-counting** in aggregates — `is_sidechain` is promoted
  spine precisely so queries can include/exclude deliberately.
- **Archive divergence** — rsync accumulates; deletions upstream never
  propagate (no `--delete`, ever, on this archive).

## 8. Testing posture

TDD throughout; unit tests on collector cursor semantics and payload
promotion; integration tests against the live `test_app` database (no mocked
DB clients); demonstration queries as permanent falsification guards, with
the real-corpus variants guarded on corpus existence and skip-narrow when
absent. Codex authors the acceptance tests independently (builder/tester
separation).
