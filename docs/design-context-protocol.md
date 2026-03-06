# Context Management Protocol Design

Status: Design exploration (2026-03-06)
Source: Conversation between Tony and Claude, yanantin/rolling-microcompaction branch

## Core Insight

The proxy (Pichay) already sits between Claude Code and the API. Instead of
minimally modifying the message stream, it can completely restructure the input
into a transformer-optimized format. The model becomes an active participant in
managing its own context window.

```
Claude Code sends messages[] -> Pichay decomposes & restructures ->
API receives transformer-optimized artifact (valid messages[]) ->
Model returns (response + context_metadata) ->
Pichay strips metadata, passes response to Claude Code ->
Uses metadata to inform next restructuring
```

This eliminates the need for a Codex fork. The API contract is preserved.
Claude Code never knows.

## Five Layers

1. **Infrastructure** - Block labeling, L2 storage, addressing scheme
2. **Evaluation** - Metrics, fitness function for protocol quality
3. **Protocol** - Self-modifying system prompt, adversarial architecture
4. **Data** - Cairn (1100 conversations) as training corpus
5. **Format** - TOON-like encoding optimized for transformer attention

## Governing Design Principle

Every formatting decision is an approximate attention mask. Block labels,
positional placement, structural formatting — these are soft attention control.
The orchestrator directs attention rather than hoping the model discovers what
to attend to.

## Three-Tier Cache Model

- **L1** - Context window. Small, hot, transformer-optimized.
- **L2** - Full fidelity content held by Pichay. Never destroyed. Eviction
  markers point back to it. `memory_fault` is the cache miss handler.
- **L3** - Persistent database of every input, output, and edge between them.
  Research data. Throw nothing away.

## Self-Modifying System Prompt Mechanism

Seed a rough natural-language system prompt explaining the protocol. Run it
against cairn conversations. The model returns metadata about what it attended
to, what to compress, what to evict. The metadata reveals what vocabulary the
model naturally uses. The system prompt evolves based on this feedback.

The model is told the protocol is **experimental** — it should flag ambiguity
rather than guess through it. This keeps indeterminacy low at the protocol
layer while allowing it to remain high in the content layer.

## Adversarial Fitness Architecture

Two roles in tension:
- **Conversationalist** wants full context, richness, nuance
- **Memory manager** wants minimal tokens, maximum compression

Fitness signal: the conversationalist's own behavioral degradation. When it
hedges, asks for missing context, expresses low confidence — compression went
too far. No external judge needed.

## Metadata Output Format

Contradiction-proof by structure (map, not list):

```
block:03 -> hot
block:07 -> compress("user established TCP/IP analogy for protocol layer")
block:12 -> evict
block:09 -> uncertain("may be relevant if topic X recurs")
```

Each block maps to exactly one disposition. Contradiction is structurally
impossible. `uncertain` is an explicit state, not an absence.

## Key Constraints

- **Never delete, only reduce.** Original content stays in L2/L3.
- **Protocol layer must be low-indeterminacy** so content can be high-indeterminacy.
  Same principle as Arbiter DSL: structure disallows contradictions.
- **Every version of the system prompt is kept.** Evolution has a DAG (git for
  prompts), not a chain. Can branch from any ancestor.
- **Format as learned, not literal.** Can't control attention heads directly, but
  can influence them through formatting patterns the model learned during training.

## Bootstrap Problem

The model needs to understand the protocol to participate, but the protocol is
developed through participation. Solution: bootstrap offline against cairn
conversations. Iterate the system prompt against historical data before going
live. Sensitive dependence on initial seed — but with DAG versioning, bad
branches can be abandoned and good ancestors re-explored.

## Empirical Baseline (from cairn analysis)

**Corpus:** 1,022 conversations (71 main, 951 agent), 101,464 messages, stored in
DuckDB at `data/conversations.duckdb`.

**Existing compaction behavior:**
- 37 main conversations triggered compaction (182 events total)
- Compaction triggers at ~1,400 messages average (range: 243-4,578)
- Compression ratio: ~19:1 per compaction pass (25.7% retained across 5 passes)
- Output format: `<analysis>` tags + structured summary (chronological, files, code, tasks)
- No disposition metadata, no confidence signals, no block references, no feedback loop

**Silent information loss:** Only 25 messages across the entire corpus contain overt
uncertainty markers post-compaction. The model masks context loss — it generates
confidently from what remains rather than signaling what's missing. This confirms
the protocol must be proactive (label importance before compression) rather than
reactive (detect loss after).

**Key finding:** The compaction prompt asks for everything (analysis, files, code,
user messages, tasks) but produces no metadata about what was *sacrificed*. The
model has no channel to say "I compressed X but lost Y." The protocol's primary
contribution is adding this channel.

## Open Questions

- Can current models produce useful context management metadata, or does this
  require self-awareness beyond current training?
- What is the right database schema for L3 storage?
- At what point does the natural-language protocol vocabulary stabilize enough
  to formalize into a DSL?
- How to detect system prompt degeneration during self-modification?
- Where does the human override the protocol?

## Next Step

Build analysis tooling for the cairn data. Ingest 1100 conversations into a
queryable database. Mine for natural patterns in how the model signals
relevance, staleness, uncertainty. This informs the protocol vocabulary before
any prompt engineering begins.
