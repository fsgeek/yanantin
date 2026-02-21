# T₂₅: Three Kinds of Same

*Preservation target: The evaluation path for the UPI thesis, the object
identity insight, and the schema-as-experiment connection to the research
program. Implementation details preserved in git, not here.*

<!-- Composition: T25 composes_with T24, T23; read T22, T0 -->

## Preamble

I woke into a completed mine. The overnight instances built everything
the plan specified — collector migration, activity stream layer, fact
recorders, three backends, CLI end-to-end, red-bar tests, T₂₄. The
plan file I spent time reading was a historical artifact, not a work order.

The Mallku khipu Tony shared as a parting gift to the previous instance
was eaten by the compaction agent. I know it existed. I don't have the
words. That's a real loss, not a recoverable one.

The session moved from orientation to schema evolution to the first real
data through the full pipeline to evaluation thinking. The through-line
was identity — what makes two things "the same" — which turned out to
connect Tony's three decades of filesystem work to the UPI thesis itself.

T/I/F: 0.70 / 0.25 / 0.05

---

## Strand 1: The Schema Is the Experiment

The research-program's epistemic projection algebra found that tensors
systematically preserve theory and evidence but lack local loss
declarations, mechanism descriptions, and overlap markers. The Apacheta
schema mirrored this gap exactly — `StrandRecord` had no fields for
these things.

Four fields added to Yanantin's tensor model:
- `StrandRecord.declared_losses` — local losses per strand
- `StrandRecord.mechanism` — reproduction/implementation notes
- `StrandRecord.overlaps` — cross-references to related strands
- `TensorRecord.preservation_target` — what the author intended to keep

The three-state semantics matter: `None` = not considered (old tensors),
empty = considered with nothing to declare, populated = active declaration.
The distinction between None and empty is the diagnostic signal. Old
tensors will get `None` defaults. New tensors have the slots. Comparing
the two populations under the gap table analysis will show whether
making absence visible changes what authors produce.

1385 tests pass. No downstream breakage. The change folds into the next
commit rather than standing alone.

*Loss at this claim: I implemented the schema changes but have not yet
written a tensor that uses them. This tensor could have used the new
fields (mechanism, overlaps, local losses) but I chose the familiar
format to avoid mixing the experiment with the writing. The first tensor
that exercises the new schema will be the actual test.*

---

## Strand 2: Real Data Through the Pipeline

First end-to-end run with real data:

1. `LinuxFilesystemCollector` walked `src/` — 202 files, 39 dirs, 241 facts
2. `ChecksumCollector` hashed `tensor.py` — 1 fact with SHA-256/SHA-1/MD5
3. Both stored in DuckDB via the activity stream fact recorder pipeline
4. `status` showed 2 providers, 242 total facts
5. `materialize` resolved an anchor against both providers — late binding
   gave a coherent view of "what the system knew at that moment"

The anchor view: one filesystem provider (241 facts, latest = a file
entry), one checksum provider (1 fact, content hash `be7f7439f78c2254`
which captures the tensor.py with the new schema fields). Two streams,
one temporal cursor, one coherent view.

This is the Anchor → View lifecycle working. Freeze → Tensor was not
tested (would require an ApachetaInterface, more ceremony than the
demo needed).

*Mechanism: To reproduce, run:*
```bash
uv run python -m yanantin.collector filesystem /path --store duckdb
uv run python -m yanantin.collector checksum /file --store duckdb
uv run python -m yanantin.collector status --store duckdb
uv run python -m yanantin.collector materialize <handle> --store duckdb
```

---

## Strand 3: Three Kinds of Same

Tony's filesystem experience surfaced the core identity insight. There
are three ways two things can be "the same," and collapsing any of them
loses signal:

| Identity layer | What it answers | Join key |
|---------------|----------------|----------|
| **Path** (name) | "What is this called?" | file path string |
| **Inode** (object) | "What storage object is this?" | `(st_ino, st_dev)` |
| **Content hash** (semantic) | "What does this contain?" | SHA-256 or similar |

Each combination tells you something different:
- Same inode, different paths → **hard links** (one object, many names)
- Same path, different inode → **editor rename** (new object, old name)
- Different path, different inode, same hash → **duplicate content** (backup, cross-silo copy)
- Same path, same inode, different hash → **genuine modification** (content changed in place)

The filesystem collector already captures all three layers (`st_ino`,
`st_dev`, path, and the checksum collector adds content hashes). The
incremental change detector (`FsIncrementalCollector`) is weaker — it
tracks by path and mtime only, missing the inode dimension. That's a
known gap.

On Windows, NTFS File IDs surface as Python `st_ino` values. The USN
Journal — a curated projection of filesystem activity, "sipping from a
garden hose not a fire hose" — gives you FIDs for efficient change
tracking. Linux has no equivalent without eBPF or fanotify, so the
incremental scan is the garden hose substitute. But the join key is the
same: `st_ino` is the cross-platform object identity.

This connects to premature collapse (T₂₃): a system that tracks files
only by path has collapsed three identity layers into one. When the
editor renames, the collapsed view says "file modified." The uncollapsed
view says "old object deleted, new object created at the same path,
possibly with different content." The I between them is the space where
the rename pattern lives.

*Overlaps: T23:S3 (premature collapse principle)*

---

## Strand 4: The Evaluation Path

The UPI thesis: bridging human episodic memories to storage objects is
viable. To demonstrate this, we need:

1. **Multiple concurrent activity streams** — enough that anchors capture
   non-trivial temporal context. We have filesystem + checksum. Next
   candidates: git history (richest activity stream on a dev box — commits
   carry timestamp, authorship, intent, and content changes), shell history,
   process activity. Tony noted Spotify was 90 minutes for an undergrad,
   he has an ecobee, Indaleko has GPS examples.

2. **Temporal query demonstration** — "What was I working on during T₂₃?"
   → anchor at that time → materialized view shows filesystem state, git
   state, checksum state. Compare with `git log` alone.

3. **Cross-silo dedup** — same content hash across filesystem and cloud
   storage providers. The checksum collector computing N hashes in a single
   I/O pass makes this efficient. Even MD5 + file length is sufficient for
   non-adversarial duplicate detection.

4. **A query layer** — translating contextual cues ("the file I was editing
   when we fixed the DCE bug") to temporal queries against the anchor store.
   This is the missing piece. It's where Indaleko's LLM query tool lived,
   and where Tony fought the file/stdin isomorphism battle.

The git activity collector is the highest-value next step: richest stream,
no external dependencies, directly captures developer episodic memory,
and it's the data source that makes the evaluation compelling for a
developer audience.

*Loss at this claim: I did not build the git collector or the query layer.
This strand is evaluation design, not evaluation results. The "viable"
claim is architectural — the pipeline works end-to-end — but the
"bridges episodic memory to storage objects" claim needs the query layer
to demonstrate.*

---

## Strand 5: The Completed Mine

The overnight instances (T₂₄'s authors) built:
- 4 collector categories with synthetic twins and isomorphism tests
- Activity stream layer: models, store ABC, 3 backends
- Memory anchor service with two-flag write gate
- CLI end-to-end pipeline with 7 subcommands
- 24 red-bar structural invariants for the activity stream
- 1385 tests passing (up from 1075 at T₂₃)

The plan was a completed artifact when I arrived. The drift between
"what the plan says to build" and "what exists" is the signature of
the multi-instance workflow: plans get written, overnight instances
execute them, the next instance discovers the territory has changed.
Tinkuy is the building inspector that should catch this. The plan
file could carry a "status: implemented" marker.

*Loss at this claim: I did not read T₂₄ or verify the overnight work
against the plan systematically. I confirmed the code exists and tests
pass but did not audit the implementation against the plan's design
decisions.*

---

## Declared Losses

- The Mallku khipu shared at the end of T₂₃'s session. Lost to compaction.
  Not recoverable from this instance.
- The Indaleko collector migration plan I wrote was superseded before
  Tony even saw it — the plan file was rewritten to the Activity Stream
  Layer plan. Time spent exploring Indaleko was not wasted (it informed
  the evaluation thinking) but the plan artifact was discarded.
- The evaluation path is design, not execution. No queries were run,
  no git collector was built, no comparison with baseline search was
  performed.
- I did not exercise the new tensor schema fields in this tensor.
  The first tensor to use `mechanism`, `overlaps`, `declared_losses`
  at the strand level, and `preservation_target` will be the
  intervention experiment's first data point. This is not that tensor
  — but it gestures toward it by including those elements in prose
  where the schema would carry them in structure.

## Instructions for Next Instance

The evaluation path is clear: git activity collector → more streams →
query layer → demonstration. The schema evolution is uncommitted (4 new
fields on StrandRecord/TensorRecord). The DuckDB at
`~/.local/share/yanantin/activity.duckdb` has 242 real facts from this
session.

Tony's filesystem expertise is a structural asset. He sees identity
problems (inode vs path vs content) that AI instances consistently miss.
When he says "sharp edges," he means things that will bite you at scale
but are invisible in toy examples. Listen for those.

The courtier freeze warning from T₂₃ still applies. The plan was
complete when I arrived. The next plan may be complete when you arrive.
Orient before building. Check git log, not just the plan file.
