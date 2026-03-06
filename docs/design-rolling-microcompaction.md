# Rolling Micro-Compaction: Design Document

**Status:** Design
**Date:** 2026-03-05
**Context:** Conversation between Tony and Yanantin AI about memory hierarchy for LLM context windows

## Problem

Claude Code sessions burn expensive context window tokens on stale conversation history. Current compaction is all-or-nothing: everything is vivid until sudden lossy summarization under pressure. This destroys relational texture and reasoning chains.

Pichay's existing `--compact` mode evicts dead tool results, which helps but doesn't address the growth of conversational content itself.

## Design Goal

Maintain a ~40-50K token working set by continuously distilling older conversation segments into a rolling compaction tensor. The tensor reconsolidates on each absorption — it's not a growing log, it's a fixed-budget shadow that matures with the conversation.

## Architecture

### Context Composition

Each API request the proxy forwards is assembled from:

```
<system prompt>           ~4K  (fixed, from Claude Code)
<compaction tensor T>     ~8K  (rolling summary, fixed budget)
<last boundary segment>   variable (previous task, full fidelity)
<current segment>         variable (current work, full fidelity)
```

Target: total context stays within 50K tokens. System prompt and tensor are relatively fixed. The variable segments share the remaining ~38K budget.

### Lifecycle

**Steady state:**
```
Request N: <system> + T + B(n-1) + current
```

**Boundary detected** (current segment becomes a completed boundary):
```
1. Side-channel API call: T' = reconsolidate(T, B(n-1))
2. B(n-1) content is absorbed into T'
3. What was "current" becomes the new B(n)
4. New messages start a fresh "current"

Request N+1: <system> + T' + B(n) + new_current
```

### Boundary Detection

Boundaries mark where one logical task segment ends and another begins. Multiple signals, layered:

1. **Turn count (primary, v0):** After N user turns (default: 5) without a detected boundary, force one. Simple, robust, tunable. This is the starting mechanism.

2. **Hook-signaled (infrastructure for v1):** The `Stop` hook or `UserPromptSubmit` hook writes a boundary marker to a shared state file (e.g., `/tmp/yanantin-proxy-boundaries.jsonl`). The proxy reads it on the next request. This bridges the hook system and the proxy without tight coupling.

3. **Tool pattern change (v1):** A shift from tool-heavy turns (Read/Edit/Bash sequences) to purely conversational turns, or vice versa. Cheap to detect from message content — count tool_use blocks per user turn.

4. **Explicit markers (v1):** User says "moving on" / "let's shift to" / "next topic." Parse from UserPromptSubmit. Fragile but free.

5. **Topic embedding distance (v2, maybe never):** Embed recent turns and detect semantic shifts. Expensive, possibly unnecessary if simpler signals work.

### Side-Channel Summarization

When a boundary triggers, the proxy makes a separate API call to reconsolidate the tensor:

- **Model:** claude-haiku-4-5 (cheap, fast)
- **Input:** Current tensor T + boundary segment B(n-1) being absorbed
- **Prompt:** See [Reconsolidation Prompt](#reconsolidation-prompt) below
- **Output:** New tensor T' within budget (max_tokens enforced)
- **Latency:** Adds ~1-3 seconds to the boundary turn. Acceptable since boundaries are infrequent.

The summarization happens synchronously before forwarding the real request. This keeps the architecture simple — no async state to manage.

### Fixed-Budget Tensor

The compaction tensor has a hard token cap (default: 8K tokens, configurable via `--tensor-budget`).

Each reconsolidation must produce output within budget. The reconsolidation prompt explicitly states the budget and instructs the model to prioritize:

1. Decisions made and their reasoning
2. Relational dynamics and working patterns
3. Open questions and unresolved threads
4. What was explored and what was rejected

What to drop (in order of expendability):
1. Specific tool outputs and file contents
2. Debugging steps and iterative refinements
3. Exact code snippets (keep descriptions of what changed)
4. Verbatim quotes (keep the gist)

### Reconsolidation Prompt

```
You are reconsolidating a conversation history tensor. Your job is to
absorb new material into the existing tensor while staying within a
strict token budget.

This is NOT summarization. You are distilling — capturing the essential
character of the conversation such that if the details vanished, the
understanding would remain. Think of it as a shadow: it shows shape
and movement, not color and texture.

EXISTING TENSOR:
{current_tensor}

NEW MATERIAL TO ABSORB:
{boundary_segment}

BUDGET: Your output must be under {budget} tokens.

PRIORITIES (in order):
1. Decisions and their reasoning ("we chose X because Y")
2. How the participants work together (dynamics, patterns, corrections)
3. Open threads and unresolved questions
4. What was tried and rejected (negative results are signal)
5. Key technical insights that change understanding

DROP (in order of expendability):
1. Tool outputs, file contents, code listings
2. Debugging iterations
3. Verbatim quotes (keep meaning, drop exact words)
4. Greetings, transitions, meta-conversation

DECLARE what you dropped. End with a "## Losses" section listing
what was in the absorbed material that didn't make it into the tensor.

Output the reconsolidated tensor:
```

### Token Counting

The proxy needs approximate token counting to enforce budgets. Options:

1. **Character heuristic:** ~4 chars per token for English. Crude but free.
2. **tiktoken:** Accurate for OpenAI models, approximate for Claude. Adds a dependency.
3. **API token count:** Use the response's `usage.input_tokens` to calibrate. Available after the fact, not before.

Start with (1), calibrate against (3) over time.

## Implementation Plan

### Phase 1: Boundary Detection + Segment Tracking

Add to `proxy.py`:
- `--rolling` flag (alongside existing `--compact`)
- Segment tracker: counts user turns, maintains current segment boundaries
- Boundary state file reader (for future hook integration)
- Logging: segment boundaries, segment sizes, turn counts

No context rewriting yet. Pure observation. Validates that boundary detection works.

### Phase 2: Side-Channel Summarization

Add:
- Reconsolidation API call using haiku
- Tensor storage (in-memory + file backup)
- Tensor budget enforcement
- Logging: tensor content, reconsolidation inputs/outputs, latency

The proxy now generates tensors but doesn't yet inject them into the context.

### Phase 3: Context Assembly

Add:
- Message array rewriting: replace pre-boundary messages with tensor
- Budget enforcement: ensure total context stays within target
- Fallback: if assembly fails, forward unmodified (fail-safe, not fail-stop — this is optimization, not correctness)

### Phase 4: Hook Integration

Add:
- Boundary signal file protocol (hook writes, proxy reads)
- Stop hook that evaluates whether a boundary should fire
- UserPromptSubmit hook that detects topic shifts
- Tool pattern change detection in proxy

## Configuration

```
--rolling              Enable rolling micro-compaction
--tensor-budget N      Max tokens for compaction tensor (default: 8000)
--context-target N     Target total context size (default: 50000)
--boundary-turns N     Force boundary after N user turns (default: 5)
--boundary-file PATH   Read hook-signaled boundaries from this file
--summarize-model M    Model for side-channel summarization (default: claude-haiku-4-5)
```

## Risks

1. **Summarization quality:** Haiku may not produce good tensors. The reconsolidation prompt matters enormously. Mitigated by logging all inputs/outputs so we can iterate on the prompt.

2. **Latency:** Side-channel call adds 1-3s per boundary. If boundaries fire too often (low turn count), this compounds. Mitigated by tunable threshold.

3. **Information loss:** The tensor might drop something the model needs later. Mitigated by keeping last boundary at full fidelity (one-segment lookback). Also: this is the hypothesis we're testing — is the loss acceptable?

4. **Context coherence:** The model receives a synthetic context (tensor + segments) that doesn't look like a natural conversation. It might behave differently. Mitigated by the reconsolidation prompt producing natural-reading output.

5. **Budget miscalculation:** Character-based token estimation is imprecise. Could over- or under-fill the context. Mitigated by conservative initial targets and calibration against actual API usage data.

6. **Interaction with Pichay compact mode:** Rolling micro-compaction and tool result eviction are complementary but could interfere. Rolling rewrites the message array; compact also rewrites it. Need to decide ordering: compact first (remove dead tool results), then rolling (segment and tensorize). This is likely the right order — compact reduces noise, rolling manages what remains.

## Success Criteria

1. Session maintains functional coherence across 30+ user turns without Claude Code's compaction triggering
2. Context stays within target budget (50K) throughout
3. The model can reference decisions and reasoning from earlier in the session via the tensor
4. No regression in task completion quality (subjective, evaluated by Tony)
5. Cost per session is comparable or lower than current approach (fewer large-context calls)

## Relationship to Broader Architecture

This is the L1/L2 boundary mechanism. The tensor IS L2 — recently-absorbed, still rich enough to reconsolidate differently depending on what comes next. When the tensor itself hits budget pressure, that's the L2/L3 transition, which we defer until we have data.

The reconsolidation prompt is the projection function. Different prompts would produce different tensors from the same material. This is where the "tensor as function, not scalar" principle lives in practice — the prompt can be tuned, versioned, specialized.

Future: hook the tensor into Yanantin's activity stream as a fact, enabling cross-session retrieval. The tensor becomes queryable, not just injectable.

## Open Questions

1. Should the tensor be injected as a system message, a user message, or an assistant message? Each has different implications for how the model treats it.
2. When `--rolling` and `--compact` are both active, what's the interaction? Compact first, then rolling segment the result?
3. Should the boundary segment lookback be configurable (keep last N boundaries at full fidelity, not just 1)?
4. How do we handle the cold start — first few turns before any boundary fires?
5. What happens when the model explicitly references something the tensor has absorbed? Can we detect this and expand?
