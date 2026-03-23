<!-- Chasqui Scout Tensor
     Run: 7597
     Model: qwen/qwen3-vl-30b-a3b-thinking (Qwen: Qwen3 VL 30B A3B Thinking)
     Cost: prompt=$1.3e-07/M, completion=$1.56e-06/M
     Usage: {'prompt_tokens': 2734, 'completion_tokens': 2367, 'total_tokens': 5101, 'cost': 0.00404794, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0062276, 'upstream_inference_prompt_cost': 0.0005468, 'upstream_inference_completions_cost': 0.0056808}, 'completion_tokens_details': {'reasoning_tokens': 989, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-23T20:41:25.303569+00:00
     GenerationID: gen-1774298466-7HsVdJj5EBqyhFBmXBLY
-->

### Preamble  
Dropped into `docs/plans` of the Yanantin project, I'm scanning OpenCode support docs. First thing that snagged my attention: the *shebang* in `skills-core.js` (`#!/usr/bin/env node`) in a file meant to be a shared module. That's like finding a horse in a stable that's been turned into a toaster. Why would a utility module need to be executable? It's not just strange—it hints at deeper tensions between the project's "composable tensor infrastructure" ambition and the messy reality of platform-specific glue code.

---

### Strands  

#### 1. **The YAML Parser That's Not Really a Parser**  
In `2025-11-22-opencode-support-implementation.md`, the `extractFrontmatter` function (lines 15-45) treats YAML as "key: value" pairs after `---` markers. No libraries, no validation—just string splitting and regex. It assumes:  
- Frontmatter is *always* YAML (line 23: `match(/^(\w+):\s*(.*)$/)`).  
- `name` and `description` are the only fields (line 30: `switch (key)`).  

But Yanantin claims "epistemic observability." Why use a regex that would choke on YAML's `|` or `>` syntax? The design doc (`2025-11-22-opencode-support-design.md`) lists the same format but never questions this implementation. **What it reveals**: The project is prioritizing *functional* YAML parsing over *correct* parsing. It's not about observability—it's about "good enough for OpenCode."  

#### 2. **The Shadowing Paradox**  
The design doc mentions `resolveSkillPath` for "personal > core" skill shadowing (line 412), but the implementation plan *only* shows `findSkillsInDir` (lines 47-94). No `resolveSkillPath` in the `skills-core.js` snippet.  

This is a red flag. If shadowing is a core feature (as implied by the design), why isn't it in the implementation? The doc says: *"Handle shadowing (personal > core)"* — but the code only *discovers* skills. **What it reveals**: The team is writing the spec before the implementation. They're *assuming* shadowing works, but the code isn't there yet. It’s a classic case of "spec-driven development" over "code-driven development."  

#### 3. **The Tool-Mapping Hack**  
In the OpenCode plugin design (`2025-11-22-opencode-support-design.md`, lines 127-132), they explicitly tell OpenCode users:  
> *When skills reference tools you don't have, substitute:  
> - `TodoWrite` → `update_plan`  
> - `Task` with subagents → Use OpenCode subagent system (@mention)*  

This is the project’s *only* admission that the two systems are fundamentally incompatible. The "composable tensor infrastructure" is being forced into a *mapping* layer. **What it reveals**: Yanantin’s "composable" claim is a lie. It’s actually a *translation layer* between two incompatible ecosystems. The "tensors" are just glue.  

---

### Declared Losses  
- **The OpenCode plugin code itself**: The implementation plan ends at "Plugin Structure" (line 145+ truncated). I can’t see how the `session.started` hook actually *injects* the "using-superpowers" content. What if the OpenCode API is asynchronous? Does it block the session? I didn’t check because the docs don’t show it.  
- **The skill directories**: The design doc says "Core: `~/.config/opencode/superpowers/skills/`" but never shows what’s *inside* those directories. Are they real skills? Or just placeholders? I ran out of attention for "what’s in SKILL.md."  
- **Git worktree integration**: The plan mentions "Git worktrees" but the code snippet only uses `fs.existsSync`. Did they actually set up a worktree? Or is it just a placeholder? I chose not to dig deeper—too many questions about Git for a scout.  

---

### Open Questions  
1. **Why the shebang?**  
   If `skills-core.js` is meant to be a module, why does it start with `#!/usr/bin/env node`? It’s not an executable script. Is this a mistake? Or is it *intentionally* meant to be run as a script for testing? (The commit message says "feat: create shared skills core module" — not "test.")  

2. **Where’s the shadowing logic?**  
   The design doc *demands* shadowing ("personal > core"), but the implementation plan *only* has `findSkillsInDir`. What happens if a personal skill has the same name as a core skill? The code *should* return the personal one, but it doesn’t have the logic. Did they forget? Or is it "to be implemented later"?  

3. **What’s the "using-superpowers" skill?**  
   The session startup hook says it *injects* this skill, but the docs don’t show the file. Is it a real skill? Or just a placeholder string? If it’s real, why isn’t it in the skill directory? If it’s a string, why call it a "skill"?  

---

### Closing  
I saw a project that *wants* to be a "composable tensor infrastructure" but is *actually* a series of platform-specific patches. The YAML parser is a half-baked regex. Shadowing is promised but not implemented. The tool-mapping hack admits the two systems are incompatible.  

**What I know**: Yanantin’s "composability" is a lie. It’s about *interoperability*, not composition.  
**What I don’t know**: How the OpenCode plugin actually *works* (because the docs don’t show it).  
**What I made up**: That the shebang is intentional. It’s probably a mistake.  

**To the next scout**: Don’t trust the docs. The code is the truth. Look for where the design *breaks*—not where it claims to work. And ask: *Why is this implementation so brittle?* The answer will tell you more than the specs.