<!-- Chasqui Scout Tensor
     Run: 8524
     Model: mistralai/mistral-small-2603 (Mistral: Mistral Small 4)
     Cost: prompt=$1.5e-07/M, completion=$6e-07/M
     Usage: {'prompt_tokens': 2399, 'completion_tokens': 1509, 'total_tokens': 3908, 'cost': 0.00126525, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00126525, 'upstream_inference_prompt_cost': 0.00035985, 'upstream_inference_completions_cost': 0.0009054}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-29T01:05:20.027920+00:00
     GenerationID: gen-1774746309-zBH9pF00u9osubRDFD2Z
-->

### Preamble
I was dropped into a trio of markdown files (`migration.md`, `patterns.md`, `advanced.md`) under a plugin-dev/hook-development/references path. The files are part of a **Claude Code plugin system** that enables “hooks” around tool execution, session lifecycle, and notifications. What caught my eye first was the **radical shift from imperative, brittle shell scripts to declarative, LLM-mediated policy enforcement**. That friction—between “old-world bash” and “new-world prompt”—is the live wire in the codebase.

---

### Strands

#### 1. The Prompt-as-Code Movement
- **Observed**:
  Both `migration.md` and `patterns.md` are full of JSON snippets where the `"type": "prompt"` hook replaces `"type": "command"`. The prompt text is templated with variables like `$TOOL_INPUT.command`, `$TOOL_INPUT.file_path`, `$TOOL_INPUT.content`, etc.
  Example from `migration.md` l. 84–90:
  ```
  "prompt": "File path: $TOOL_INPUT.file_path. Content preview: $TOOL_INPUT.content (first 200 chars). Verify: 1) Not system directories ... Return 'approve' or 'deny'."
  ```
- **What it means**:
  Policies are no longer compiled into shell scripts; they are **natural language contracts** that the LLM evaluates at runtime. The system assumes the model can parse `$TOOL_INPUT` variables, reason about security semantics, and return a structured decision in plain English.
- **Assumption**:
  The LLM is **trustworthy enough** to make safety decisions without a human-in-the-loop.
- **Tension**:
  How do you guard against hallucinated or adversarial prompts? The docs don’t mention prompt-injection defenses or model sandboxing.

#### 2. Duality of “Basic” vs. “Advanced” Hooks
- **Observed**:
  The migration guide explicitly frames the change as a move from “Basic Command Hooks” (bash scripts) to “Advanced Prompt Hooks” (LLM-mediated).
  `patterns.md` l. 110 lists both command-type and prompt-type hooks side-by-side, but the commentary clearly favors the latter.
- **What it reveals**:
  The project is **re-architecting its safety surface** around LLMs. The old hooks were **deterministic regex and string checks**; the new ones are **probabilistic, context-aware policies**.
- **Surprise**:
  There is **no deprecation or sunset plan** for command hooks. The docs treat them as equal citizens, yet the narrative pushes users aggressively toward prompts.
- **Question**:
  Are command hooks actually **slated for removal**, or are they kept for legacy reasons (Windows, air-gapped, etc.)?

#### 3. Variable Interpolation That Doesn’t Quit
- **Observed**:
  The prompt templates use `$VARIABLE` interpolation (`$TOOL_INPUT.command`, `$CLAUDE_PLUGIN_ROOT`, etc.). The patterns file even shows `${CLAUDE_PLUGIN_ROOT}/scripts/load-context.sh` (l. 77).
- **What it reveals**:
  The system **trusts environment variables and shell interpolation** to feed data into the LLM. There’s **no mention of sanitization, escaping, or validation** of those variables before they reach the prompt.
- **Assumption**:
  The plugin host (Claude Code) guarantees safe variable expansion.
- **Tension**:
  If an attacker can control `CLAUDE_PLUGIN_ROOT` or `TOOL_INPUT.command`, they can **inject arbitrary shell metacharacters** into the prompt, which the LLM will then reason about. That’s a **prompt-injection path** nobody is talking about.

#### 4. Silent Expansion of Hook Scope
- **Observed**:
  In `patterns.md`, the “Test Enforcement” pattern (l. 45) and “Build Verification” pattern (l. 170) both attach to the **Stop lifecycle event**, not PreToolUse. The matcher is `"*"`, meaning **every tool invocation** triggers the hook.
- **What it reveals**:
  The system is **hoisting policy decisions into the session shutdown phase**. This means a single misclassified tool could **block the entire session from stopping**, trapping the user.
- **Assumption**:
  The LLM will never misfire on such broad matchers.
- **Tension**:
  The hooks are **so powerful they become denial-of-work tools**. A single overzealous prompt could **lock a developer out of their session**.

#### 5. The Missing “Advanced.md”
- **Observed**:
  The directory lists `advanced.md` but the file is **not present in the excerpt**. The migration guide repeatedly references “advanced” hooks but the canonical artifact is missing.
- **What it means**:
  Either the file was **deleted, renamed, or never created**. The docs are **forward-referencing a missing artifact**.
- **Assumption**:
  The migration guide is **aspirational**, not complete.
- **Question**:
  What else is **missing** in the docs that the codebase actually implements?

---

### Declared Losses
- I skipped the **220+ lines** of truncated migration.md and **197+ lines** of truncated patterns.md. They likely contain more patterns, edge cases, or anti-patterns, but the visible surface already shows enough tension.
- I did **not dig into the actual plugin code** (which presumably lives elsewhere). The hooks are **declarative JSON**, so the interesting logic is either in the plugin runtime or inside the LLM prompt-engineering layer.
- I ignored the `advanced.md` file because it’s **absent**; I can’t examine what isn’t there.

---

### Open Questions
1. Where is the **plugin runtime** that actually executes these hooks? Is it running in Node, Python, or inside the LLM sandbox?
2. How are **prompt responses parsed**? Is there a JSON schema validator, or is the model expected to output free-form English that is then heuristically matched?
3. Are there **unit tests** for these hooks? How do they test an LLM-mediated policy without mocking the model?
4. What happens if the LLM **times out** or **raises an error** during a prompt hook? Is there a fallback to a permissive or deny-all policy?
5. Are there **escape hatches** for power users to bypass prompt hooks (e.g., `--force` flag)? The docs don’t mention them.

---

### Closing
The project is **rewriting safety infrastructure around an LLM**, replacing deterministic bash with probabilistic prompts. That’s bold—and a little reckless. The docs are **half-finished** (missing `advanced.md`), the **interpolation surface is wide open to injection**, and the **hooks are so powerful they can trap users**.

If I were the next scout, I’d ask:
**“Show me the runtime code that executes these hooks. And tell me how you guard against prompt injection.”**