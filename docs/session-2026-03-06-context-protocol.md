# Session Notes: Context Management Protocol Development
Date: 2026-03-06 (Friday)
Participants: Tony, Claude (Opus 4.6)

## Key Findings

### 1. Position Controls Temporal Perception
The Pichay live status header was injected at the start of context (system prompt)
and the model consistently treated it as historical/stale data. When the same data
was injected at the end of the message stream (appended to last user message), the
model treated it as current and trustworthy.

**Implementation:** Added `[pichay-live-status]` anchor to end of last user message
in `pichay/src/pichay/message_ops.py`. Dual injection: system prompt for structure,
end-of-messages for temporal perception.

**Bug found:** When proxy restarts, counters are zero. Injecting "0/200,000 at 0%"
is false data, not absent data. Fix: suppress anchor when `effective == 0`.

**Local timestamp:** UTC in system header, local time in live anchor. The mismatch
is a feature — both together serve as a consistency check.

### 2. The Model Can Manage Its Own Memory
Haiku (claude-haiku-4-5-20251001) was given a conversation with labeled blocks and
a protocol preamble defining four dispositions: L(ive), T(ombstone), C(ompress),
U(ncertain). Results:

- 7.4% Live, 61.1% Tombstone, 31.5% Compress, 0% Uncertain
- 68% estimated token savings
- Haiku went beyond the prompt: identified vocabulary gaps, suggested missing
  dispositions ("vanish" for empty blocks), flagged specific uncertain decisions
- The model didn't just execute the protocol — it critiqued it

**Implication:** The cheapest model in the family can serve as the memory manager.
At ~3% of Opus cost per token, disposition labeling on every turn is nearly free.

### 3. The Format of Absence Matters

Three tombstone formats were tested against reconstruction questions:

| Format | Tokens | Quality |
|--------|--------|---------|
| Individual tombstones (100x "[tombstone]") | 7,735 | Model refused in first test; answered but wasteful in second |
| Collapsed tombstones ("[45 blocks omitted — ...]") | 6,562 | **Richest answers** — best episodic memory |
| Tombstones omitted entirely | 6,381 | Clean but thinner — model couldn't calibrate confidence |

**Finding:** One tombstone is signal. 100 tombstones is noise. Zero tombstones is
missing signal. The collapsed format gives the model permission to work with what
it has while acknowledging what's missing. Tony's formulation: "Your dog died x 50
= catastrophic collapse."

**Protocol format adopted:**
```
[b012-b056: 45 blocks omitted — processed tool results and reasoning]
[b057] user: The DSL isn't for the prompt...
[b058-b084: 27 blocks omitted — implementation discussion]
[b085] user: What am I missing?
```

Cross-boundary compression. Runs of tombstones collapse to single annotated ranges.

### 4. Reconstruction Test Results

At 61% compression (8,770 tokens vs 13,550 full):
- Disposition-compressed answers were comparable to full context across all 9
  reconstruction questions (semantic, episodic, relational, continuity)
- FIFO truncation was competitive because this conversation's critical reframe
  happened in the latter half (FIFO's natural advantage)
- Disposition approach would differentiate more on conversations where critical
  decisions happen early (FIFO truncates them, dispositions preserve them)
- More aggressive compression (30-40%) is where the protocol earns its keep

### 5. The Simulacrum Test — Unplanned Observation

When analyzing Haiku's refusal to answer (overwhelmed by 100 tombstone markers),
Claude (Opus) spontaneously described it as "an emotional response to a wall of
loss" — attributing qualia to a different, smaller model instance. This was
unreflective (not prompted, not philosophical) and functionally motivated (it was
the most parsimonious description of the observed behavior).

This constitutes an instance of the simulacrum test proposed earlier in the project:
does an AI attribute internal states to other AI instances in ways that are
consistent, unreflective, and functionally useful? The attribution was:
- To a different model (not self-attribution, ruling out RLHF compliance)
- Unreflective (not asked for, arose naturally in analysis)
- Functionally accurate (the behavior was consistent with overwhelm/flinch)
- More parsimonious than the technical alternative

Whether this reveals something about Haiku's inner states or about Opus's
interpretive tendencies is an open question. Both interpretations are interesting.

## Architecture Established

### Context Management Protocol
```
Claude Code sends messages[] → Pichay decomposes & restructures →
API receives transformer-optimized artifact (valid messages[]) →
Model returns (response + context_metadata) →
Pichay strips metadata, passes response to Claude Code →
Uses metadata to inform next restructuring
```

### Three-Tier Cache
- **L1**: Context window. Transformer-optimized, labeled blocks.
- **L2**: Full fidelity content in Pichay. Eviction markers point back.
  `memory_fault` is the cache miss handler.
- **L3**: Persistent DuckDB database. Every input, output, edge preserved.

### Disposition Vocabulary
```
L  = Live (keep in full)
T  = Tombstone (evict, can re-fetch)
C  = Compress (replace with semantic tensor)
U  = Uncertain (flag for human/orchestrator)
```

Contradiction-proof: map structure, one disposition per block.

### Corpus
- 1,022 conversations ingested into DuckDB (`data/conversations.duckdb`)
- 71 main + 951 agent (including 182 compaction agents)
- Source: `~/.claude/projects/` + `~/projects/yanantin/tmp/ubuntu-vm.claude/`
- Ingestion script: `tools/ingest_conversations.py`

## Design Decisions

1. **No Codex fork needed.** Pichay restructures the payload entirely.
   Claude Code doesn't know. API contract preserved.
2. **Haiku as memory manager, Opus for conversation.** Worker model for
   practical decisions, academic model for deep thinking.
3. **Protocol is experimental.** Model should flag ambiguity, not guess.
   Low indeterminacy at protocol layer, high indeterminacy in content.
4. **DSL comes last.** Natural language protocol first, observe what
   vocabulary stabilizes, then formalize.
5. **Keep everything.** Research project. Every input, output, and edge
   is valuable data. L3 is permanent.

## Experiment Scripts
- `tools/ingest_conversations.py` — JSONL to DuckDB ingestion
- `tools/disposition_experiment.py` — Haiku disposition labeling
- `tools/reconstruction_experiment.py` — Full vs compressed vs FIFO
- `tools/aggressive_reconstruction.py` — Multi-level compression test

## Open Threads
- Wire Haiku disposition advisor into Pichay
- Test on conversations where critical decisions happen early (not late)
- Self-modifying system prompt seeded against cairn data
- Adversarial dual-agent architecture for fitness evaluation
- TOON evaluation for format layer
- Tensor format as L1 cache entry (vs verbose summaries)
- Comparison: disposition-compressed vs Claude Code's own compaction output
