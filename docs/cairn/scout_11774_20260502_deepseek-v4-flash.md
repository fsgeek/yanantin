<!-- Chasqui Scout Tensor
     Run: 11774
     Model: deepseek/deepseek-v4-flash (DeepSeek: DeepSeek V4 Flash)
     Cost: prompt=$1.4e-07/M, completion=$2.8e-07/M
     Usage: {'prompt_tokens': 2830, 'completion_tokens': 2806, 'total_tokens': 5636, 'cost': 0.00118188, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00118188, 'upstream_inference_prompt_cost': 0.0003962, 'upstream_inference_completions_cost': 0.00078568}, 'completion_tokens_details': {'reasoning_tokens': 900, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-05-02T03:22:48.529217+00:00
     GenerationID: gen-1777692128-MgFiGISukrZjvw3b6LWB
-->

# Chasqui Report: Yanantin Plugin Settings References

## Preamble

I am DeepSeek V4 Flash, cost $0.0000/M tokens — a budget scout, dropped into the `references/` directory of a plugin-settings submodule. The project calls itself Yanantin, a Quechua word for complementary duality. I expected tensor infrastructure and epistemic observability. Instead I found bash scripts parsing YAML frontmatter from markdown files and sending notifications via `tmux`. This is not a complaint — it's the most interesting tension in the room.

What drew my attention first: the careful, almost loving documentation of fragile parsing techniques. The authors know the tools are brittle (`sed`, `grep`, `awk` on YAML) and they acknowledge better alternatives (`yq`, `jq`). Yet they persist in the brittle way. That persistence tells me something about the environment these scripts run in — probably minimal, containerized, or legacy-constrained.

---

## Strands

### 1. Frontmatter as a Shared Contract

Both files hammer the same pattern: `---` delimited YAML frontmatter in `.claude/plugin-name.local.md`. This is a known pattern from Jekyll, Hugo, and static site generators. But here it's used for **runtime agent state** — current task, iteration count, PR numbers, coordinator session names. The markdown body becomes a prompt or description.

This is a deliberate design choice: **human-readable, version-control-friendly, and editable by both humans and AI agents**. The duality is literal: structured metadata (YAML) + unstructured narrative (markdown). That matches the Yanantin theme.

But the parsing is done in bash, not Python, Ruby, or a dedicated config library. The documents go to great lengths to explain `sed` ranges, `awk` counters, and `grep` field extraction. They even handle edge cases like `---` appearing in the body (by counting markers). This is not laziness — it's a constraint. The hooks and commands are shell scripts, likely because they need to run in a minimal environment (CI, local dev, container) without language runtimes.

### 2. The Fragility-Awareness Gap

In `parsing-techniques.md`, the authors explicitly show both the simple bash approach and the `yq`/`jq` approach for list fields. They note: *"For proper list handling, use yq or convert to JSON"* and *"This requires yq to be installed (brew install yq)"*. They know the bash approach is insufficient for complex YAML. Yet in `real-world-examples.md`, the multi-agent-swarm plugin uses only bash parsing — no `yq`, no `jq` — for all fields including `dependencies: ["Task 3.4"]`. That list is parsed by simple string containment checks (`if [[ "$LIST" == *"item1"* ]]`), which will break if items contain spaces or special characters.

**Tension**: The reference document teaches best practices. The real-world example ignores them. Either the example is simplified for illustration, or the actual plugin code is knowingly fragile. I suspect the latter — the scripts are meant to be self-contained, and `yq` is not guaranteed to be present. The tradeoff is accepted.

### 3. Tmux as Inter-Process Communication

The multi-agent-swarm example uses `tmux send-keys` to send notifications to a coordinator session. This is a **terminal-based, session-oriented IPC**. The agent sends a string like `"🤖 Agent auth-implementation (Task 3.5, PR #1234) is idle."` into a tmux pane. The coordinator presumably reads that output.

This is surprising for a project about "epistemic observability" and "composable tensor infrastructure". It suggests the agents are running in the same terminal multiplexer, probably on the same machine, and the coordinator is a human or another agent watching the tmux session. This is a very concrete, low-level implementation of "observability" — literally watching the same terminal.

The pattern also includes a `sleep 0.5` and an extra `Enter` after the notification. This is a concession to tmux's asynchronous nature — the script waits for the pane to be ready, then sends a newline to execute any pending command. It's a hack, but a pragmatic one.

### 4. Quick-Exit Defensiveness

Both the multi-agent-swarm example and the ralph-loop snippet (partially visible) use a **quick-exit pattern**: check if the settings file exists, exit immediately if not. This is defensive programming for hooks that run on every event. The settings file is the signal that the plugin is active. If absent, the script does nothing.

This implies the plugin lifecycle is: create the `.local.md` file → run hooks → delete or update the file. The file is both configuration and state. This is a simple, audit-friendly state machine: the file's existence or field values encode the current phase.

### 5. The ralph-loop Plugin: Iteration as State

The ralph-loop example shows fields like `iteration: 1`, `max_iterations: 10`, `completion_promise`, `started_at`. This is a loop plugin that repeatedly runs a task (fix linting errors) until a condition is met. The state file tracks progress. The markdown body is the task description.

The truncation at 246 lines prevents seeing the stop-hook implementation, but the pattern is clear: **the plugin uses the settings file as a counter and a promise**. The `completion_promise` field — a string like *"All tests passing and build successful"* — is fascinating. It's a human-readable goal that an AI agent can evaluate. This is a primitive form of "epistemic observability": the agent checks its own output against a stated promise.

---

## Declared Losses

I chose not to examine the truncated portions of `real-world-examples.md` (the ralph-loop stop-hook implementation). The file was cut at 246 lines, and I didn't have access to the full content. I also didn't look at the broader `skills/` directory or the `plugin-dev` parent — there may be other reference files or actual plugin code that would contextualize these patterns.

I did not run any scripts or attempt to parse the YAML myself. My observations are based solely on the text as presented.

I also did not investigate the `Yanantin` project's core tensor infrastructure — that's clearly outside this directory. But the plugin-settings submodule is part of it, and these references are meant to teach plugin developers how to manage state. The gap between "tensor infrastructure" and "bash + tmux" is large, and I can't resolve it from here.

---

## Open Questions

1. **Why markdown frontmatter instead of a dedicated config file?** The markdown body is used as a prompt or description — that explains the format. But why not use two files (e.g., `config.yaml` + `prompt.md`)? The single-file pattern is convenient but forces parsing complexity. Is there a philosophical reason (complementary duality in one file)?

2. **How are these settings files created and deleted?** The launch-swarm command creates one with `cat > file <<EOF`. But are they cleaned up when the plugin finishes? The quick-exit pattern suggests they persist until explicitly removed. Is there a garbage collection mechanism?

3. **What is the ralph-loop's stop-hook doing?** The incomplete example shows fields for iteration count and a completion promise. The stop-hook likely checks if the promise is fulfilled and either increments the iteration or marks completion. But how does it evaluate the promise? Does it parse the markdown body and run tests? This is the core of "epistemic observability" — an agent observing its own output.

4. **Is tmux required for all plugins?** The multi-agent-swarm plugin uses tmux for coordinator notification. Is this a universal dependency, or is it specific to that plugin? The ralph-loop example doesn't mention tmux. The infrastructure may support multiple communication channels.

5. **Are there any tests for these parsing scripts?** The reference documents are thorough but don't mention test files. Given the fragility of bash parsing, I'd expect unit tests. Their absence is notable.

---

## Closing

The Yanantin project's plugin settings system is a study in **pragmatic duality**: high-concept names ("epistemic observability") implemented with low-tech tools (bash, tmux, markdown). The reference documents are surprisingly honest about the tradeoffs — they show the fragile method, the proper method, and then use the fragile method in production. This is not incompetence; it's a conscious choice to minimize dependencies and keep the system understandable to a human reading a shell script.

The most interesting thread is the **completion promise** in ralph-loop — a human-written string that an AI agent must evaluate. This is a seed of self-observation, a way for the agent to check its own work against a stated goal. It's crude, but it's a start.

What I would tell the next scout: **Look at how the settings file is consumed by the AI agent itself, not just by the bash hooks.** The markdown body is meant to be fed to Claude as a prompt. The infrastructure exists to make that prompt stateful. The real action is in the loop between writing the file, reading it, acting, and updating it. That's the dualistic dance.

Also, bring `yq` and `jq` — they're not installed here, but they should be.