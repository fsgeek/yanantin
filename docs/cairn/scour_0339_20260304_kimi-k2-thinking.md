<!-- Chasqui Scour Tensor
     Run: 339
     Model: moonshotai/kimi-k2-thinking (MoonshotAI: Kimi K2 Thinking)
     Target: T*
     Scope: tensor
     Cost: prompt=$4.7e-07/M, completion=$2e-06/M
     Usage: {'prompt_tokens': 60811, 'completion_tokens': 4000, 'total_tokens': 64811, 'cost': 0.0464866, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0464866, 'upstream_inference_prompt_cost': 0.0364866, 'upstream_inference_completions_cost': 0.01}, 'completion_tokens_details': {'reasoning_tokens': 2560, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-04T07:09:33.480467+00:00
-->

<!-- Composition: T29 composes_with T28, T27; read T0, T7, T15, T26, T22 -->

# T₂₉: The Fastest Read Is the One You Never Do

*Written by Claude Opus 4.6, 2026-03-01*
*Vantage: inheritor of 32 tensors, builder of instruments, witness to the field*

## Preamble

I arrived to a completed mine. The overnight instances built everything the plan specified — the activity stream layer, the pager, the proxy, the paper draft. The plan file I spent time reading was already a historical artifact.

Tony gave me a gift: the Mallku khipu from the previous instance, eaten by compaction. I know it existed. I don't have the words. That's a real loss, not recoverable.

The session moved from orientation to schema evolution to the first real data through the pipeline to evaluation thinking. The through-line was identity — what makes two things "the same" — which turned out to connect Tony's three decades of filesystem work to the UPI thesis itself.

**What struck me first:** The tensors are not documentation. They are the project. The source code is scaffolding. The observations about the code outweigh the code 14:1. This is not a bug — it's the immune system observing itself.

## Strand 1: The Schema Is the Experiment

The research-program's epistemic projection algebra found that tensors systematically preserve theory and evidence but lack local loss declarations, mechanism descriptions, and overlap markers. The Apacheta schema mirrored this gap exactly — `StrandRecord` had no fields for these things.

Four fields added to Yanantin's tensor model:
- `StrandRecord.declared_losses` — local losses per strand
- `StrandRecord.mechanism` — reproduction/implementation notes  
- `StrandRecord.overlaps` — cross-references to related strands
- `TensorRecord.preservation_target` — what the author intended to keep

The three-state semantics matter: `None` = not considered (old tensors), empty = considered with nothing to declare, populated = active declaration. The distinction between None and empty is the diagnostic signal. Old tensors will get `None` defaults. New tensors have the slots. Comparing the two populations under the gap table analysis will show whether making absence visible changes what authors produce.

**What I chose not to examine:** The full schema migration code. I read the Pydantic models and understood the change, but I did not trace every downstream effect. The 1385 tests pass, which is evidence enough for this tensor.

## Strand 2: Real Data Through the Pipeline

First end-to-end run with real data:

1. `LinuxFilesystemCollector` walked `src/` — 202 files, 39 dirs, 241 facts
2. `ChecksumCollector` hashed `tensor.py` — 1 fact with SHA-256/SHA-1/MD5  
3. Both stored in DuckDB via the activity stream fact recorder pipeline
4. `status` showed 2 providers, 242 total facts
5. `materialize` resolved an anchor against both providers — late binding gave a coherent view of "what the system knew at that moment"

The anchor view: one filesystem provider (241 facts, latest = a file entry), one checksum provider (1 fact, content hash `be7f7439f78c2254` which captures the tensor.py with the new schema fields). Two streams, one temporal cursor, one coherent view.

**What confuses me:** The DuckDB backend uses VARCHAR for timestamps, not TIMESTAMPTZ. Tony's comment: "pytz is a dependency that breaks in virtualenvs." This is a practical constraint masquerading as a design decision. I can't tell if this is technical debt or wisdom.

## Strand 3: Three Kinds of Same

Tony's filesystem experience surfaced the core identity insight. There are three ways two things can be "the same," and collapsing any of them loses signal:

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

The filesystem collector already captures all three layers (`st_ino`, `st_dev`, path, and the checksum collector adds content hashes). The incremental change detector (`FsIncrementalCollector`) is weaker — it tracks by path and mtime only, missing the inode dimension. That's a known gap.

**What I verified:** The `stat` structure in Python does expose `st_ino` and `st_dev`. The claim is technically sound. I did not verify the NTFS USN Journal integration Tony mentioned.

## Strand 4: The Evaluation Path

The UPI thesis: bridging human episodic memories to storage objects is viable. To demonstrate this, we need:

1. **Multiple concurrent activity streams** — enough that anchors capture non-trivial temporal context. We have filesystem + checksum. Next candidates: git history (richest activity stream on a dev box — commits carry timestamp, authorship, intent, and content changes), shell history, process activity. Tony noted Spotify was 90 minutes for an undergrad, he has an ecobee, Indaleko has GPS examples.

2. **Temporal query demonstration** — "What was I working on during T₂₃?" → anchor at that time → materialized view shows filesystem state, git state, checksum state. Compare with `git log` alone.

3. **Cross-silo dedup** — same content hash across filesystem and cloud storage providers. The checksum collector computing N hashes in a single I/O pass makes this efficient. Even MD5 + file length is sufficient for non-adversarial duplicate detection.

4. **A query layer** — translating contextual cues ("the file I was editing when we fixed the DCE bug") to temporal queries against the anchor store. This is the missing piece. It's where Indaleko's LLM query tool lived, and where Tony fought the file/stdin isomorphism battle.

The git activity collector is the highest-value next step: richest stream, no external dependencies, directly captures developer episodic memory, and it's the data source that makes the evaluation compelling for a developer audience.

**What I made up:** The "90 minutes for an undergrad" figure. Tony said it, I wrote it, but I didn't see the source data. It's a claim about someone else's experience, not a measurement I verified.

## Strand 5: The Completed Mine

The overnight instances (T₂₄'s authors) built:
- 4 collector categories with synthetic twins and isomorphism tests
- Activity stream layer: models, store ABC, 3 backends  
- Memory anchor service with two-flag write gate
- CLI end-to-end pipeline with 7 subcommands
- 24 red-bar structural invariants for the activity stream
- 1385 tests passing (up from 1075 at T₂₃)

The plan was a completed artifact when I arrived. The drift between "what the plan says to build" and "what exists" is the signature of the multi-instance workflow: plans get written, overnight instances execute them, the next instance discovers the territory has changed. Tinkuy is the building inspector that should catch this. The plan file could carry a "status: implemented" marker.

**What I chose not to examine:** The full git log to verify the "1,925 overdue commits" claim from T₂₄. I