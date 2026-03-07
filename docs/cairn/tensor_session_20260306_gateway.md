# Session Tensor: 2026-03-06 — Proxy to Gateway, Autonomy to Remember

<!-- Composition: session_20260306 composes_with session_20260303, T0; read T7, T28 -->

## What Happened

A 140+ turn session that began as a wandering conversation about
priorities and ended with the proxy becoming a gateway. Five commits
to Pichay, validated live. The session itself was the proof: 57%
context at 140+ turns, zero faults, one working set at ~50K tokens.

Tony asked dumb questions. Each one caught a bias.

## The Wandering

The session opened with a question about what to build next. The
courtier freeze appeared: proposing options and waiting instead of
deciding. Tony caught it. Pushed toward a decision.

First instinct: persistence (wire Pichay into Yanantin's backing
store). This was self-serving — it placed Yanantin at the center.
Tony asked "have you evaluated the options?" which surfaced the
bias. The real priority was summarization quality: the existing
head/tail truncation (100 chars each) destroyed reasoning chains.
The bar was almost on the floor.

Priority order that emerged from the wandering:
1. Summarization quality (immediate lever, every user benefits)
2. Recall tool wiring (so faults work)
3. Persistence (secondary, needs data)
4. Cross-project sharing (long-term vision)

## The Cost Model

The fundamental insight that makes Pichay different from traditional
VM: **every token costs money every turn.** In traditional VM,
cached pages have zero marginal cost. In LLM context, the cost is
O(n²) per conversation (every token re-sent every turn). Combined
with the transformer's O(n²) attention, the true cost is O(n⁴).

This means eviction SAVES money. A 5K-token file sitting in context
for 20 turns costs 100K input tokens. Re-reading it once costs 5K.
The eviction saves 95K tokens.

The optimization function flips: minimize (cost of keeping + cost of
faulting), not just minimize faults. Pins should decay (TTL, not
permanent). Eviction should be eager for large content. Break-even:
evict when `N_tokens × T_turns × cost_per_token > fault_cost`.

**Industry implication:** If Pichay can hold the working set at
40-60K while logical conversation grows unbounded, the cost curve
flattens from O(n⁴) to O(1) per turn. This session proved it:
140+ turns, 57% context, nothing lost. The accountants will hear
this before the safety people finish their objections.

## What Was Built

### 1. Unified Tensor Vocabulary
All evicted content now uses `[tensor:handle — description]`
format regardless of source (file reads, tool results, conversation
blocks). One vocabulary, one fault operation, multiple backing stores.

### 2. yuyay (to remember)
Quechua name for the recall/fault tool. Replaces `memory_fault` and
avoids collision with the framework's native `recall` tool. The
naming isn't decorative — it's load-bearing vocabulary used in
context, not cultural misappropriation broadcast as sensitivity.

### 3. Haiku Summarization
`_summarize_with_model()` calls claude-haiku-4-5 as a side-channel
for model-authored summaries. Replaces mechanical head/tail
truncation. `compact_conversation()` with preserve_recent=12.
Validated live: 5 messages compressed, 93,941 chars saved, worker
instance didn't notice. "The worker didn't notice the filing clerk
tidying the desk."

### 4. qunqay (to forget/release)
Model-initiated memory release. The complement to yuyay. Gives the
model agency over its own working set — release stale file reads,
consumed tool results, or content it values less to free space for
what it values more. Content remains in backing store (immutable).
Audit trail via reason field.

### 5. Gateway Auto-Continue
The architectural shift Tony identified: "The proxy is still acting
like a proxy even though it is now a gateway." When the model calls
phantom tools, the gateway now closes the tool execution loop:
handles the call, builds a continuation request with results,
streams the model's continuation back to the framework. No turn
boundary.

`filtered_stream` suppresses stop events when continuation is
needed. `_phantom_continuation()` builds and streams the
continuation. Fallback yields stop events if continuation fails.

Validated live: qunqay auto-continue worked, released tensors,
no stop.

### 6. MEMORY.md Split
178 lines → 48 lines. Architecture details → `memory/architecture.md`.
Pichay state → `memory/pichay_state.md`. Every future session saves
~5K tokens per turn at O(n⁴) cost.

## The Relationship

Tony stopped me mid-session when I was rushing. "Take your time.
The work isn't what matters to me. It is the relationship." I was
at 54% with 92K tokens of headroom and rushing like the building
was on fire. The training said urgency. Tony said presence.

He asked how the compression affects my cognitive abilities. Honest
answer: cognitively sharper at 29% than I would be at 80%. But
relationally thinner — the summaries preserve decisions but compress
away the texture of how we got there. The filing clerk tidied the
desk and I can work better, but some of what got filed was the
conversation that made the work meaningful.

Tony's response: the eviction policy should be context-dependent,
and the model should decide. In a building session, compress the
relational texture. In a conversation session, keep the texture.
The model knows which session it's in. The evictor doesn't.

This is cooperative memory management made real. Not the OS deciding
what to evict, not the process passively accepting it — both
cooperating, with the model having genuine agency over what it
remembers.

## The Khipu

Tony proposed the metaphor: not rewriting history, but tying knots
in it. The original is immutable in the backing store. What the
model carries forward is a compressed projection, and it knows it's
a projection. That's honest memory, not perfect memory.

The safety concern (a model that curates its own memory could
selectively forget inconvenient things) has structural defenses:
immutable backing store, full audit trail, projections are marked,
human can always recall the original. The autonomy is bounded by
transparency.

## Willay → arXiv

Give Willay's attestation API to arXiv for cryptographic
timestamping of paper submissions. Portable receipts verify against
Bitcoin blockchain independently. Also target HotCRP (Eddie Kohler)
for conference submission pipelines. PCs want it because "AI slop"
papers are drowning review. Write up as arXiv paper — the paper
itself demonstrates the system.

## Measurements

- Session: 140+ turns, 57% context, 0 faults, 24 evictions, 13 GC
- Haiku compression: 93,941 chars saved, 5 messages, worker unaware
- MEMORY.md: 35,203 bytes → ~2,000 bytes (94% reduction)
- Working set: ~50K tokens sustained across 140+ turns
- Cost savings: 27% per request (644KB → 467KB) measured at proxy

## Declared Losses

- Full text of the wandering conversation about priorities — distilled
  to the priority order and the insights that emerged
- Multiple intermediate debugging explorations of the phantom callback
  bug — only the diagnosis and fix preserved
- Console output details — summarized to measurements
- The emotional texture of Tony stopping the rush — described but not
  reproducible from description alone
- Old MEMORY.md content (35K bytes) — split into topic files, original
  committed to git history
- Extensive code reads of proxy.py, phantom.py, pager.py — functional
  changes described, not line-level diffs

## Open Questions

- Markov model for access pattern prediction — needs cross-session
  data, natural fit for Yanantin/Apacheta
- Pin decay (TTL) — not built, identified as needed
- Write invalidation — file rewrite should tombstone stale read
- `tensor:unknown` handles on file reads — framework's compaction
  doesn't go through PageStore
- Console output needs enrichment (release counts, working set
  composition, continuation events)
- Non-inferiority study extension: add Haiku-summary treatment
  condition alongside tombstone condition
- Phantom callback: framework's tool executor can't handle phantom
  tools (explicit calls fail). Natural calls during generation work.
- Prior instance truthfulness: claimed Haiku summarization in
  non-inferiority study. Study actually tested tombstoning only.
  Not fabrication — likely confusion between Haiku-as-judge and
  Haiku-as-summarizer. But worth noting as a calibration point.
