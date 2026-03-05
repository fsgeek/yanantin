# Codex CLI Architecture Scout: Key Findings

**Date:** 2026-03-05
**Source:** github.com/openai/codex (Tony's fork)
**Language:** 96.2% Rust

## Project Structure

The Rust code lives in `codex-rs/` with a workspace of crates:
- **`core/`** — Main logic: context management, compaction, truncation, client, session
- **`state/`** — Persistence: log DB, runtime state, model management
- **`tui/`** — Terminal UI
- **`cli/`** — CLI entry point
- **`exec-*`** — Execution sandbox (policy, seatbelt)
- **`protocol/`** — Shared types for messages, models, items
- **`utils-cache/`** — LRU cache utilities

## Context Management (THE KEY SEAM)

### `core/src/context_manager/history.rs` — ContextManager

The central conversation state holder:

```rust
pub(crate) struct ContextManager {
    items: Vec<ResponseItem>,        // The message history (oldest first)
    token_info: Option<TokenUsageInfo>,
    reference_context_item: Option<TurnContextItem>,  // Baseline for diffing
}
```

- `record_items()` — adds items to history with truncation policy
- Token tracking via `TotalTokenUsageBreakdown`
- `reference_context_item` used for settings diffing (only sends changes)
- This `items` vector IS the messages array that gets sent to the API

### `core/src/context_manager/updates.rs` — Context Assembly

Builds update items (environment, permissions, collaboration mode) by diffing current state against `reference_context_item`. This is the incremental context injection point — it produces `ResponseItem`s that get prepended to the history when context changes.

Key functions:
- `build_environment_update_item()` — diffs environment context
- `build_permissions_update_item()` — diffs sandbox/approval policies
- `build_collaboration_mode_update_item()` — diffs collaboration mode
- `build_realtime_update_item()` — handles realtime mode transitions

## Compaction

### `core/src/compact.rs`

Two compaction modes:
1. **Inline** — uses the same model session to summarize
2. **Remote** — uses a separate API call (OpenAI-specific currently)

Key constants:
- `COMPACT_USER_MESSAGE_MAX_TOKENS = 20_000`
- Prompt loaded from `templates/compact/prompt.md`
- Summary prefix from `templates/compact/summary_prefix.md`

The compaction prompt is generic:
```
You are performing a CONTEXT CHECKPOINT COMPACTION. Create a handoff
summary for another LLM that will resume the task.
```

Compaction has three trigger points:
- **Pre-turn** — before a new turn starts
- **Mid-turn** — during a turn when context pressure hits
- **Manual** — user-triggered

`InitialContextInjection` enum controls how initial context gets reinjected after compaction:
- `BeforeLastUserMessage` — for mid-turn (preserves model training expectations)
- `DoNotInject` — for pre-turn/manual (clean slate, next turn reinjects fully)

After compaction, history is replaced with the summary and `reference_context_item` is cleared, forcing full context reinjection on the next turn.

## Truncation

### `core/src/truncate.rs`

- `APPROX_BYTES_PER_TOKEN = 4` (same heuristic we discussed)
- `TruncationPolicy` enum: `Bytes(usize)` or `Tokens(usize)`
- Supports conversion between bytes and tokens
- Preserves prefix + suffix when truncating content (head/tail preservation)

## Provider Abstraction

### `core/src/client.rs` (likely)

Need deeper exploration, but the codebase references:
- `ModelProviderInfo` — used in compact.rs to decide inline vs remote compaction
- `ModelClientSession` — the API session
- `is_openai()` check suggests provider awareness

The protocol crate (`codex-rs/protocol/`) defines shared types including `ResponseInputItem` and `ResponseItem` that are provider-agnostic.

## Insertion Point for Rolling Micro-Compaction

**The seam is clean.** The modification path:

1. **`ContextManager`** — Add a rolling compaction mode alongside the existing items vector. Instead of replacing all history with a summary (current behavior), maintain: `tensor + last_boundary_items + current_items`

2. **`compact.rs`** — Add a new compaction variant: `run_rolling_compact_task()` that:
   - Takes the oldest segment (pre-boundary items)
   - Reconsolidates with existing tensor via side-channel API call
   - Replaces those items with the new tensor
   - Uses a different prompt (reconsolidation, not handoff summary)

3. **`context_manager/updates.rs`** — Boundary detection logic lives here naturally, alongside the existing context diffing

4. **Template** — New `templates/compact/rolling_prompt.md` for reconsolidation (different from the handoff summary prompt)

5. **Config** — Add rolling compaction settings to the config system

## Key Observations

1. **Codex already does context management** — truncation, compaction, token estimation, incremental context updates. We're not building from scratch.

2. **The compaction prompt is simplistic** — "create a handoff summary." Our reconsolidation prompt (distillation, not summarization) would be a direct improvement.

3. **OpenAI-specific paths exist** — `should_use_remote_compact_task()` checks `is_openai()`. The codebase already handles provider-specific behavior, so Claude-specific paths are natural.

4. **The `reference_context_item` diffing pattern** is interesting — it already implements "only send what changed" for settings. Extending this to conversation content is the logical next step.

5. **The codebase is well-structured** — clear module boundaries, trait-based abstractions, template-based prompts. This is a forkable architecture.

## Risk Assessment

- **Rust complexity** — Non-trivial to modify if team doesn't have Rust experience. But the architecture is clean enough that the modifications are localized.
- **Upstream drift** — OpenAI actively develops this. Fork maintenance cost depends on how invasive our changes are. If we keep them localized to compaction and context_manager, rebasing should be manageable.
- **Provider compatibility** — Our changes target Claude via API key. Need to ensure the provider abstraction supports this cleanly.
