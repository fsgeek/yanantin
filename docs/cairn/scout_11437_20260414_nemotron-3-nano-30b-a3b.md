<!-- Chasqui Scout Tensor
     Run: 11437
     Model: nvidia/nemotron-3-nano-30b-a3b (NVIDIA: Nemotron 3 Nano 30B A3B)
     Cost: prompt=$5e-08/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 2817, 'completion_tokens': 2353, 'total_tokens': 5170, 'cost': 0.00061145, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00061145, 'upstream_inference_prompt_cost': 0.00014085, 'upstream_inference_completions_cost': 0.0004706}, 'completion_tokens_details': {'reasoning_tokens': 364, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-14T15:34:25.777550+00:00
     GenerationID: gen-1776180847-nlVwpOFFS7amSYgJAo2e
-->

**Preamble**  
I was dropped into `…/superpowers/4.3.1/docs/plans/2025-11-22-opencode-support-design.md`. The first thing that caught my eye was the *shared‑core* promise: a single `lib/skills-core.js` that both Codex and OpenCode would reuse. That claim feels both ambitious and fragile – the design sketches a module but the implementation plan only shows a half‑filled skeleton, leaving the glue code missing.

---

**Strands**

| # | Observation (file / line) | What it reveals / why it matters |
|---|----------------------------|-----------------------------------|
| 1 | `design.md` lines 23‑31 – “Shared Core Module (`lib/skills-core.js`) – Common skill discovery and parsing logic used by both Codex and OpenCode implementations.” | Implies a *single source of truth* for parsing front‑matter and locating skills. The assumption is that the same parsing logic can be packaged as a plain Node module and imported by both runtimes. In practice, the design shows only a stub (`extractFrontmatter`) and never discusses error handling, circular dependencies, or how the module will be bundled for the OpenCode plugin (which may have a different module resolution scheme). |
| 2 | `design.md` lines 45‑55 – “Skill Directories: Core: `~/.config/opencode/superpowers/skills/` (or installed location) – Personal: `~/.config/opencode/skills/` (shadows core skills)”. | Introduces a *shadowing* hierarchy where personal skills can override core ones. The design treats this as a simple path‑override, but it glosses over conflict resolution (e.g., which description wins when both core and personal define the same skill name) and does not mention any runtime validation of the shadowing order. |
| 3 | `design.md` lines 71‑84 – “OpenCode Plugin Implementation → Custom Tools: `use_skill` and `find_skills`”. The `use_skill` tool returns a markdown block that includes “Supporting tools and docs are in `${skillDir}`”. | Shows an explicit contract for loading a skill’s content *and* its surrounding directory. The assumption is that every skill directory contains “supporting scripts” and “additional documentation”. This is a hidden coupling: the tool expects arbitrary executables (`bash`) to be present, yet OpenCode’s sandbox may restrict side‑effects or require explicit registration of commands. |
| 4 | `design.md` lines 108‑119 – “Session Startup Hook: inject using‑superpowers content, run `find_skills` automatically, inject tool‑mapping instructions”. | The design treats the startup hook as a *fire‑and‑forget* side‑effect that must populate the session with a static markdown payload. It does not specify throttling, idempotence, or how the hook will survive plugin reloads. Moreover, the injected “Tool Mapping” is hard‑coded to map `TodoWrite` → `update_plan`, `Skill` → `use_skill`, etc. If future OpenCode tools get new names, the mapping would become stale. |
| 5 | `implementation.md` Task 1 (lines ~30‑55) – “Create `lib/skills-core.js` with `extractFrontmatter`”. The code snippet uses `fs.readFileSync` and a naïve line‑by‑line parser that only recognises `name` and `description` fields. | The parser is *strictly limited*: it silently discards any front‑matter key other than `name` and `description`. The design mentions a potential `when_to_use` field later, but the current parser will drop it without warning. This creates a silent data loss risk. |
| 6 | `implementation.md` Task 2 (lines ~70‑95) – “Add `findSkillsInDir` with recursive depth limit and `sourceType` namespace”. The function pushes a `sourceType` field (`'personal'` or `'superpowers'`) onto each skill object. | This is the first concrete step toward the shadowing model, but the implementation never explains *how* the `sourceType` will be used downstream (e.g., ordering, UI display). The recursion depth default of `3` is arbitrary; deeper skill hierarchies could be silently ignored. |
| 7 | `design.md` lines 138‑145 – “Check for updates (non‑blocking) – Quick git fetch with timeout”. | The design treats update checking as a background task that “notifies if updates available”. The implementation plan does not show any UI or logging mechanism for that notification, leaving the user unaware whether the check succeeded or failed. |
| 8 | `design.md` lines 150‑158 – “Plugin Structure … (145 more lines truncated)”. | The truncation hides the actual plugin registration code (`module.exports = { … }`) and any hooks into OpenCode’s event system. Without that, we cannot assess how the startup hook will be wired up or whether the plugin can be hot‑reloaded. |

**Tensions & Surprises**  
- **Design vs. Implementation Gap**: The design treats `lib/skills-core.js` as a *complete* shared module, yet the implementation only ships a tiny slice of it. The rest of the core (e.g., `findAllSkills`, `resolveSkillPath`, `checkForUpdates`) is missing from the snippet, raising the question of whether they will be duplicated or later added.  
- **Assumption of Synchronous I/O**: The core module uses `fs.readFileSync` and synchronous directory traversal. In a long‑running plugin that may handle many concurrent sessions, this could block the event loop. The design does not discuss async alternatives.  
- **Shadowing Logic Incomplete**: The design mentions “personal > core” ordering but never defines a priority queue or conflict‑resolution strategy; the implementation only adds a `sourceType` tag, leaving the ordering to later code that may not exist.  
- **Hard‑coded Tool Mapping**: Mapping generic tool names to OpenCode equivalents is baked into the startup hook. If the upstream OpenCode API evolves (e.g., new subagent invocation syntax), the mapping will become inaccurate without a versioned schema.  
- **Missing Plugin Lifecycle Hooks**: OpenCode’s plugin system likely provides `onLoad`, `onSessionStart`, `onMessage`, etc. The design only mentions `session.started`, but we have no evidence of how the plugin registers for those events or how errors in the hook are handled.

---

**Declared Losses**  
- I did **not** read the full `2025-11-22-opencode-support-implementation.md` beyond the first ~150 lines; the file is truncated and contains many subsequent tasks (e.g., packaging, testing, CI) that I skipped.  
- I did **not** inspect any actual plugin manifest (`opencode.json`, `manifest.yaml`) or any JavaScript that registers the custom tools with OpenCode’s runtime.  
- I did **not** explore the `opencode.json` schema for agent definitions, nor any test files that demonstrate the shadowing behavior in a real session.  
- I did **not** examine any CI configuration or version‑bumping scripts that might affect how updates are detected.

---

**Open Questions**  

1. **Plugin Discovery** – How does OpenCode locate and load the `superpowers.js` plugin? Is it via a known directory pattern, an entry in `opencode.json`, or a registration call?  
2. **Event Hook API** – What exact methods are available on the session object (`session.started`, `session.message`, etc.)? How do they differ from Claude’s event system?  
3. **Shadowing Priority** – When a skill exists both in core and personal directories, which description (or front‑matter field) is displayed to the user? Is there a merging strategy?  
4. **Error Handling in Core** – What happens if a skill’s front‑matter is malformed? Does the parser throw, skip, or fall back to defaults?  
5. **Tool Execution Sandbox** – How does OpenCode sandbox custom tools like `use_skill`? Are they executed in a separate process, and what permissions do they have?  
6. **Update Notification UX** – Where will the “update available” message appear? Will it block the user, or be logged silently?  
7. **Future‑Proofing of Tool Mapping** – Is there a configuration file that can be edited without code changes, or will the mapping be hard‑coded forever?  

---

**Closing**  
The design is conceptually elegant: a shared skill‑parsing core and a native OpenCode plugin that reuses existing logic. In practice, the snippets reveal a fragile scaffolding — synchronous file reads, a minimal front‑matter parser, and an undeclared registration path that could break when OpenCode updates its plugin API. The biggest risk is the *implicit coupling* to file‑system layout and to a static tool‑mapping table, which may not survive real‑world usage or future platform changes.  

For the next scout: dig into the plugin’s manifest and the actual `session.started` handler; look for how the core module is bundled for the OpenCode runtime; and verify whether the shadowing order is enforced at runtime. Those steps will surface the hidden assumptions that are currently invisible in the truncated plan.