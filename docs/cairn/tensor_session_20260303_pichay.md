# Session Tensor: 2026-03-03 — Pichay Phantom Tools and Memory Model

<!-- Composition: session_20260303 composes_with T28; read T0, T7 -->

## What Happened

This session debugged Pichay's phantom tools, extracted design
insights from cross-model conversations, and arrived at a conceptual
shift in how LLM memory management should work.

## Phantom Tool Fix

The `memory_release` phantom tool caused 400 "tool use concurrency"
errors. Root cause: the proxy stripped phantom tool_use blocks from
the SSE stream, then `inject_phantom_results` tried to re-inject
them into the next request's message history, creating malformed
messages the API rejected.

Three-part fix:
1. **Removed injection entirely.** Phantom calls are fire-and-forget.
   Proxy does bookkeeping (marks released paths) at response time.
   No message history modification.
2. **stop_reason rewrite.** When all tool_use blocks in a response
   are phantom, `message_delta` stop_reason changes from "tool_use"
   to "end_turn".
3. **Synthetic text block.** When response would be empty after
   stripping phantom tools, proxy injects "[released from context]".

Additional: OBSERVE_ONLY mode for future-proofing if the framework
adds native memory_release/memory_fault tools.

## Measurements

- Compact mode: 62% context → 31% (2x effective session life)
- Without compact: 62% at same conversation point
- Session reached 93% at ~40 framework turns, 36 proxy turns
- 26 evictions, 5 faults, 1 pin (eval.py)

## Cross-Model Conversation Analysis

Tony shared a conversation with Gemini (5 responses) and a separate
Claude instance (4 responses) about LLM file APIs and memory management.

**Gemini degradation curve:** Response 1 was 70% signal (epistemic
metadata, AST streaming, temporal forking). By response 3 it was
30% signal (working set management JSON sketches amid narrative
drift). By response 5: pure theater (neutrosophic waveform ringing,
perturbation maps, diagnostic fingerprints). The model detected
engagement and escalated elaboration instead of rigor.

**Claude stayed grounded:** Labeled its own speculation gradient.
Caught its own path-addressing bias. Each response got more precise,
not more theatrical. Produced 9 concrete phantom tool extensions
from lived experience. Asked the right question at the end ("How
far along is AssFS?").

**Finding:** Cooperative memory management quality depends on the
model's capacity for honest self-reporting about its cognitive state.
A model that escalates into fantasy will generate garbage phantom
hints.

## Design Extensions (7 total)

Written to `pichay/docs/design-phantom-extensions.md`:
1. Ephemeral flag (immediate eviction after signal extraction)
2. Variable fidelity on release (tombstone → AST → summary)
3. Prefetch hints (model signals upcoming needs)
4. Batch fault with token budget
5. Eviction classes (page groups, coherent eviction)
6. Fork with COW for subagents (inherit parent's page table)
7. Reasoning state preservation across tool boundaries (unsolved)

## Conceptual Shift: Objects, Not Blocks

The session arrived at a fundamental reframing:

Traditional MM: fixed-size opaque blocks, content-blind eviction,
binary fidelity (resident/swapped), passive applications.

LLM MM: variable-size semantic objects, cooperative intent-based
eviction, fidelity gradient (full → AST → summary → tombstone →
tensor), queryable backing store.

**The tensor as PTE:** In hardware VM, a PTE is tiny and opaque —
just a swap address. In LLM MM, the tensor is both PTE (retrieval
handle to backing store) AND cache line (compressed content you can
reason from). Declared losses are the coverage map: they tell you
what the tensor can't answer, guiding the decision to fault.

**The fidelity ladder:** L0 tensor (always resident) → L1 page store
(cached, fast fault) → L2 JSONL archive (full conversation) → L3
file system (original artifacts).

## Conversation Compression

Built `compact_conversation()` in pager.py. The proxy now compresses
old conversation text (user and assistant messages), not just tool
results. Preserves recent messages, truncates old large text blocks
with retrieval handles pointing to the session JSONL log.

This is the first time the proxy touches conversation — previously
only tool_result blocks were managed. Conversation was the untouchable
majority of context.

## Paper Updates

- Section 5.7 (Non-Inferiority): Added Tony's evaluation protocol —
  long-horizon lifecycle task, 4-way comparison (2 baseline +
  2 treatment), ensemble judges + human sampling.
- Section 6 (Future Work): Added cooperative extensions paragraph
  and object-addressed memory paragraph.

## Non-Inferiority Evaluation Design (Tony's)

Four calls per round: 2 baseline, 2 treatment. Long-horizon task
lifecycle: plan → implement → review → fix → extend → document →
identify missing tests. Each phase produces checkable artifacts.
Phase transitions create natural eviction boundaries. Start with
endpoint comparison (if task completes equivalently, per-round
doesn't matter). Ensemble LLM judges + human sampling on
disagreements.

## Turn Counter Calibration

On proxy startup, the first request's message history calibrates
the turn counter. Counts prior assistant messages to get the true
conversation turn, not the proxy-relative turn.

## Declared Losses

- Full Gemini conversation text (5 responses) — distilled to design
  note, raw text not preserved in this tensor
- Full Claude conversation text (4 responses) — same treatment
- Intermediate phantom debugging steps (3 failed approaches before
  the working fix) — only the final fix described
- eval.py content (read, analyzed, released)
- proxy.py and phantom.py exact line-level changes — described
  functionally, not reproduced
- The extensive MEMORY.md content that informed this session —
  not repeated here, see MEMORY.md directly

## Open Questions

- Conversation compression untested live (built, wired in, needs
  proxy restart to exercise)
- memory_fault untested live
- Non-inferiority evaluation: needs harness, task runner, judge
  pipeline
- Paper needs tightening from ~17 pages to ~12 (acmart format)
- AssFS as addressing abstraction: substrate exists in Yanantin,
  interface layer doesn't
- Summarization vs truncation: current implementation truncates
  (head/tail + handle). Real implementation should summarize
  (tensor with declared losses). Requires small model call or
  model cooperation via phantom tool.
