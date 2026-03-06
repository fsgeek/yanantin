# Plan: Codex Fork for Rolling Micro-Compaction

**Status:** Hypothesis — to be disproved
**Date:** 2026-03-05
**Branch:** yanantin/rolling-microcompaction

## Hypothesis

We can modify OpenAI's Codex CLI to implement a memory hierarchy that maintains effective LLM task performance within a ~50K token working set, by replacing the existing all-or-nothing compaction with rolling micro-compaction that distills older conversation segments into a fixed-budget tensor.

## Phase 0: Baseline (validate before modifying)

**Goal:** Get Codex running with Claude as provider. Establish baseline behavior.

- Build the Rust codebase
- Configure Claude API key as the model provider
- Run a non-trivial multi-turn session
- Record: context growth rate, when compaction triggers, what the compacted output looks like
- Confirm we can modify, build, and test the feedback loop

**Exit criteria:** Codex works with Claude. We have baseline measurements.
**Risk:** Provider abstraction may not cleanly support Claude. Build environment issues.

## Phase 1: Observability

**Goal:** See what Pichay shows us, but natively in Codex.

Instrument `ContextManager` to log on each turn:
- Total token count (estimated)
- Breakdown: system prompt, compaction summary (if any), conversation items
- Number of items in history
- Which items are tool results vs conversation
- Boundary detection signals (turn count, tool pattern changes)

Output to a log file or structured JSON, readable during/after session.

**Exit criteria:** We can see context composition per turn, comparable to Pichay's /context view.
**Risk:** Low. This is pure instrumentation, no behavior change.

## Phase 2: Boundary Detection

**Goal:** Identify task segment boundaries in the conversation flow.

Implement boundary detection using:
- Turn count threshold (every N user turns, default 5)
- Tool pattern shifts (heavy tool use → conversation, or vice versa)
- Leverage existing `is_user_turn_boundary()` function

Mark boundaries in the items vector. Log them. Don't act on them yet.

**Negative signals (suppress boundary):**
- Last N turns are all tool results with no user input (mid-operation cascade)
- Model is mid-generation (streaming response in progress)
- Active multi-step tool sequence (read → edit → test cycle)

These are as important as the positive signals. Firing a boundary mid-operation would split a coherent task into fragments.

**Exit criteria:** Boundaries fire at reasonable points. Visual inspection confirms they align with task transitions. Boundaries do NOT fire during active tool cascades.
**Risk:** Boundaries may not align with meaningful transitions. Turn count is crude. But we need data before we can be smarter.

## Phase 3: Rolling Reconsolidation

**Goal:** Replace pre-boundary content with a fixed-budget tensor.

When a boundary fires:
1. Take items before the previous boundary (the "absorbed segment")
2. Make a side-channel API call (haiku) with current tensor + absorbed segment
3. Replace absorbed items with the reconsolidated tensor
4. Enforce token budget on tensor output

New template: `templates/compact/rolling_prompt.md` — the distillation prompt (not handoff summary).

**Instrumentation requirement:** Preserve original segments alongside tensors during experimentation. Write the pre-reconsolidation input (tensor + absorbed segment) and the output tensor to disk. This is the comparison corpus for Phase 4 and the backing store for iterating on the reconsolidation prompt. Disk is cheap.

**Exit criteria:** Tensor is generated, injected, and the session continues coherently. Context size stays within budget across 20+ turns.
**Risk:** Reconsolidation quality. Haiku may not produce good tensors. The session may lose coherence after tensor injection. The model may behave differently with synthetic history.

## Phase 4: Evaluation

**Goal:** Does this actually work?

Run comparative sessions:
- Baseline Codex (no modifications) — let compaction trigger naturally
- Rolling micro-compaction — our system
- Same tasks, similar complexity

Measure:
- Context size over time (should stay flat with rolling, grow then cliff with baseline)
- Task completion quality (subjective)
- Tensor quality (does it preserve reasoning and relational texture?)
- Cost (total API tokens consumed per session)
- Failure modes (what breaks, when, why)

**Exit criteria:** We have enough data to decide whether to continue, pivot, or abandon.
**Risk:** The experiment may be inconclusive. Small sample sizes. Subjective evaluation.

## What This Plan Assumes

1. Codex works with Claude as a provider (not verified)
2. The Rust codebase builds and runs on our system (not verified)
3. We can make localized modifications without breaking existing functionality
4. Side-channel API calls to haiku are fast enough (~1-3s) not to break flow
5. The reconsolidation prompt can produce useful tensors within budget
6. Turn-count boundaries are good enough for a first experiment
7. We have Rust expertise sufficient to modify this codebase (or can develop it)

## Phase 4b: System Prompt as Page Table

**Goal:** Determine the minimum viable system prompt for a functionally-organized context.

LLMs are trained on chronologically-ordered conversations. A context organized by function (tensor at top, working data in middle, live status at edges) violates that prior. Without explanation, the model will misread temporal relationships — treating the tensor as "old" because it appears early, treating live telemetry as stale because it appears in the header position.

The system prompt must act as the page table: metadata that tells the model how to interpret the address space.

Experiment: same task, same functional layout, four conditions:
1. No explanation (model misreads structure — baseline for failure mode)
2. Labeled sections only (`<tensor>`, `<working_data>`, `<recent>`, `<status>`)
3. Explicit temporal explanation ("the tensor is a compression of earlier conversation, not a prior message; the status header is live, updated this turn")
4. Chronological layout (standard, no reordering — control)

Measure: correct tensor referencing, correct status interpretation, task completion quality.

**Key insight:** The "lost in the middle" attention pattern means tensor and live status should go at context edges (beginning/end). Working data goes in the middle because it's tool-loaded and re-faultable. This is attention-aware memory layout — analogous to cache-line-aligned data structures.

## What This Plan Does NOT Address

- The full L1-L4 memory hierarchy (this only builds L1/L2)
- Cross-session memory (tensors don't persist between sessions yet)
- Yanantin integration (activity streams, anchors, fact recording)
- The MEMORY.md tensorization (separate, simpler experiment)
- Pichay deprecation/migration path
- Upstream contribution strategy

## Order-of-magnitude Effort Estimate

- Phase 0: Hours (if provider support works) to days (if it doesn't)
- Phase 1: Hours. Pure instrumentation.
- Phase 2: Hours. Boundary detection is simple logic.
- Phase 3: Days. Side-channel calls, prompt engineering, budget enforcement, testing.
- Phase 4: Days to weeks. Running sessions, collecting data, iterating.

## Kill Criteria

Abandon this direction if:
- Codex can't cleanly support Claude as provider (Phase 0 blocker)
- The Rust modification cycle is too slow for experimentation (Phase 0 blocker)
- Reconsolidation tensors consistently lose critical information (Phase 3 failure). Specifically: the model fails to reference a decision made before compaction that it needs for the current task, AND the decision was present in the tensor input but absent from the tensor output. This distinguishes tensor quality failure from model attention failure.
- The model behaves erratically with synthetic history — refuses to engage, hallucinates prior context, or treats the tensor as adversarial input (Phase 3 failure)
- Rolling compaction doesn't reduce context pressure meaningfully vs baseline (Phase 4 finding)
