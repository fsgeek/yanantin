<!-- Chasqui Scout Tensor
     Run: 976
     Model: mistralai/mistral-small-creative (Mistral: Mistral Small Creative)
     Cost: prompt=$1e-07/M, completion=$3e-07/M
     Usage: {'prompt_tokens': 4303, 'completion_tokens': 1201, 'total_tokens': 5504, 'cost': 0.0007906, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0007906, 'upstream_inference_prompt_cost': 0.0004303, 'upstream_inference_completions_cost': 0.0003603}, 'completion_tokens_details': {'reasoning_tokens': 0}}
     Timestamp: 2026-02-16T16:33:16.799672+00:00
-->

### Verdict
**DENIED**

---

### Evidence
The claim states:
> *"How is the `precompact_tensor.py` hook triggered? Is it on every commit?"*

The file does **not** explicitly state that the hook is triggered on every commit. Instead, the hook is triggered **during compaction events**, as evidenced by the following key lines:

1. **Hook input parsing (line 300-302):**
   ```python
   try:
       hook_input = json.loads(sys.stdin.read())
   except (json.JSONDecodeError, ValueError) as e:
       log.error("Failed to parse hook input: %s", e)
       sys.exit(0)  # Don't block compaction
   ```
   - The hook reads input from `stdin` (likely passed by the calling process), which is parsed as JSON. This suggests the hook is invoked externally (e.g., by a compaction process, not directly by Git).

2. **Compaction-specific logic (lines 304-306):**
   ```python
   log.info("PreCompact tensor hook fired. Input keys: %s", list(hook_input.keys()))
   ```
   - The hook logs that it is "fired" (i.e., triggered) and explicitly references "compaction" in its purpose (see docstring and function names like `claim_tensor_number`, `format_tensor`).

3. **Docstring (lines 10-15):**
   ```python
   """PreCompact tensor hook: capture session work history before context dies.
   When compaction fires, this hook reads the session JSONL to understand...
   ```
   - The docstring explicitly states the hook is triggered **"when compaction fires"**, not on every commit.

4. **No Git-specific triggers (lines 200-250):**
   - The hook scans for `git commit` commands in the session JSONL (e.g., `_extract_tool_use` function), but this is for **recording** commit history, not for **triggering** the hook. There is no code that listens to Git events (e.g., `git commit` hooks or `pre-commit` triggers).

5. **Session JSONL scanning (lines 150-190):**
   ```python
   def find_session_jsonl() -> Path | None:
       """Find the most recent session JSONL by modification time."""
       jsonl_dir = Path.home() / ".claude" / "projects" / "-home-tony-projects-yanantin"
       ...
   ```
   - The hook scans a **session JSONL file** (a log of interactions, not Git commits) to extract work history. This further confirms the hook is tied to session/compaction events, not Git commits.

---

### Reasoning
1. **Trigger Mechanism:**
   - The hook is **not** a Git hook (e.g., `pre-commit`, `post-commit`). It is triggered externally (via `stdin`) by a process that handles "compaction" (likely a context-boundary or session-ending event).
   - The docstring and function names (e.g., `claim_tensor_number`, `format_tensor`) explicitly tie the hook to **compaction**, not commits.

2. **No Git Event Listeners:**
   - The code does **not** include any Git-specific triggers (e.g., `git hook` registration, `git commit` event listeners, or calls to `git` CLI). It only **records** Git commits if they appear in the session JSONL, but this is passive observation, not a trigger.

3. **Session-Focused:**
   - The hook scans a **session JSONL file** (a log of interactions, tools used, and messages) to generate a "compaction tensor." This is clearly tied to **session boundaries** or **context switches**, not Git commits.

4. **Claim Misinterpretation:**
   - The claim asks: *"Is it on every commit?"* The answer is **no**. The hook is triggered during **compaction events**, which may or may not coincide with Git commits. The file provides no evidence that the hook runs on every commit.

---

### Declared Losses
1. **External Trigger Details:**
   - The file does not show how the hook is **invoked** (e.g., what process calls it or under what conditions). The hook assumes input is provided via `stdin`, but the **calling mechanism** (e.g., a compaction script, a Git hook wrapper, or a session manager) is not described in this file.
   - *Example*: If the hook is called by a Git hook wrapper (e.g., a script that runs `precompact_tensor.py` after every `git commit`), that logic would be in another file.

2. **Runtime Behavior:**
   - I cannot observe the hook's behavior at runtime (e.g., what actually passes input to `stdin` or how often compaction fires). This requires execution traces or additional context.

3. **Project-Specific Context:**
   - The file references a project directory (`/home/tony/projects/yanantin`) and a `cairn` documentation structure. Without access to the broader project, I cannot confirm if compaction events are tied to Git commits in practice.

---
### Key Takeaway
The claim is **DENIED** because:
- The hook is **not triggered by Git commits** but by **compaction events** (as explicitly stated in the docstring and code).
- There is **no evidence** in the file that the hook runs on every commit.
- The hook's purpose is to **capture session history** during compaction, not to react to Git events.