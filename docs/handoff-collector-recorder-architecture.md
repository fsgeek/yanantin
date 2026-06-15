# Collector/Recorder Architecture: Handoff Note

**For:** Fresh instance starting work on Yanantin collector/recorder
**Source:** Conversation with Tony, 2026-06-14, distilled from Indaleko's evolved structure

---

## What Indaleko learned (the hard way)

Indaleko has a three-level inheritance hierarchy for collectors:

```
BaseStorageCollector
  └── LocalStorageCollector        (filesystem walk, platform-agnostic)
        └── LinuxStorageCollector  (platform-specific overrides — very small footprint)
        └── WindowsStorageCollector (drive letters, more overrides, same logic)
```

The key insight: **the platform-specific override footprint is tiny**. Most of the logic is universal. This is only visible in retrospect — reading the code cold, you see the structure but not why it landed there. Don't flatten it; the hierarchy is right.

---

## The Yanantin deltas (what changes, and why)

### 1. Paired collectors: real + synthetic

Every collector gets a twin:

- **Real collector**: walks actual data (filesystem, memory corpus, etc.)
- **Synthetic collector**: generates data with the same schema, but with **ground truth embedded**

Both emit identical schemas. Everything downstream (wrangler, recorder, store) is identical — it doesn't know or care which side it's talking to.

**Why this matters**: 28.5M real files won't be hand-labeled. Synthetic data can be. Evaluation becomes a first-class architectural citizen rather than a retrofit. This one change would have made Indaleko's evaluation far easier.

### 2. Data wranglers: explicit transport layer

In Indaleko, the transport between collector and recorder was an implicit file (JSONL with metadata embedded in the filename — a CLI + data wrangler + collector, with the recorder reading the intermediate file). This works but hides a seam that's actually load-bearing.

**In Yanantin, the wrangler is explicit.** Three variants, same insert/remove interface:

| Wrangler | Backing | When to use |
|---|---|---|
| File wrangler | JSONL on disk | Decoupled processes, bulk load, auditability |
| Queue wrangler | In-memory or IPC | Low-latency, same-process or adjacent-process |
| Wrapped/in-memory | Direct call | Testing, simple single-session use |

The wrangler appears **twice**: between collector→recorder, and between recorder→store. The recorder→store wrangler is where bulk loading lives — Indaleko used arangoimport for initial index, which is a massive win over record-at-a-time. The recorder doesn't need to know; it writes to whatever sink is wired.

**The libraries don't change when you swap wranglers. Only the tool wiring changes.**

### 3. Tool frontend separated from collector engine

The tool (LLM-facing interface) is separated from the collector engine (walk/parse/emit logic). They connect via a wrangler. This is the seam Indaleko lacked explicitly — it was there, but not named or designed as such.

---

## The shape

```
[real collector]  ─┐
                   ├─ same schema ──► [wrangler] ──► [recorder] ──► [wrangler] ──► [store]
[synth collector] ─┘
     ↑                                    ↑                              ↑
ground truth                    file|queue|wrapped              file|queue|wrapped
lives here                      (swap independently)            (bulk load lives here)

[tool frontend] ──► [wrangler] ──► [collector engine]
```

---

## What's already built in Yanantin

- `find()` first slice: `LlikaService.find(terms) -> FindResult` — content-axis recall, deliberately naive (full scan, Python substring), verified against live `apacheta_test`. The SHAPE is the contract; the engine (ArangoSearch) is a later swap.
- Memory collector/recorder slice design: `docs/superpowers/specs/2026-06-13-memory-collector-recorder-slice-design.md` — scoped to content-first, memory dir as first collector target. Read this before building.
- Collision rule: URI (path) = identity. Change signal = (size, mtime). Changed → new immutable record + `supersedes` edge. Unchanged → skip. Declared loss: content changed while size+mtime preserved → missed (named, not hidden).

---

## What to ask Tony before building

- Confirm your understanding of the wrangler interface (insert/remove entries — what does "entries" look like concretely for the collector→recorder seam?)
- The synthetic collector for the memory dir specifically: what does ground truth look like for markdown+frontmatter files? (For filesystem metadata it's obvious; for memory content it's less so.)
- Whether the tool frontend separation is in scope for the first collector or deferred.

---

## The progressive autonomy expectation

Tony expects the first pairing to be interactive (you're learning the pattern), and by the seventh to be largely stand-alone. If you're on the first or second, lean toward asking rather than inferring. The architecture has specific joints that aren't obvious from reading the code cold.
