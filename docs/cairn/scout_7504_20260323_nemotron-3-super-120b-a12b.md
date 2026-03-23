<!-- Chasqui Scout Tensor
     Run: 7504
     Model: nvidia/nemotron-3-super-120b-a12b (NVIDIA: Nemotron 3 Super)
     Cost: prompt=$1e-07/M, completion=$5e-07/M
     Usage: {'prompt_tokens': 2838, 'completion_tokens': 2964, 'total_tokens': 5802, 'cost': 0.00176196, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 64, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00176196, 'upstream_inference_prompt_cost': 0.00027996, 'upstream_inference_completions_cost': 0.001482}, 'completion_tokens_details': {'reasoning_tokens': 2036, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-23T08:11:17.567263+00:00
     GenerationID: gen-1774253469-f2aYSf1iBduaGNj6vWfc
-->

### Preamble
I am examining two markdown files in the `plans/` directory: `2025-11-22-opencode-support-design.md` and `2025-11-22-opencode-support-implementation.md`. These files describe the design and implementation plan for adding OpenCode support to a skill system (referred to as "superpowers") that already has a Codex implementation. My attention was first drawn to the design's goal of "sharing core functionality" between OpenCode and Codex via a native plugin architecture, contrasted with the implementation plan's focus on extracting specific functions into a shared module without evident steps to refactor the existing Codex implementation.

### Strands
**Strand 1: Sharing Core Functionality vs. Code Duplication Risk**  
- *Design claim* (from design.md): "Add full superpowers support for OpenCode.ai using a native OpenCode plugin architecture that **shares core functionality** with the existing Codex implementation."  
- *Implementation actions* (from implementation.md, Phase 1):  
  - Task 1: Create `lib/skills-core.js` by copying the `extractFrontmatter` function from `.codex/superpowers-codex` (lines 40-74).  
  - Task 2: Modify `lib/skills-core.js` to add the `findSkillsInDir` function from `.codex/superpowers-codex` (lines 97-136).  
- *Observation*: The implementation plan copies code from the Codex implementation into a new shared module but does **not** include any task to modify the Codex implementation to use this shared module. This risks creating code duplication: the Codex implementation retains its original copies of these functions, while the OpenCode plugin would use the shared module. The design’s goal of "sharing" is not realized if both implementations maintain separate copies.  

**Strand 2: Scope of Shared Core**  
- *Implementation detail*: The shared module (`lib/skills-core.js`) only contains two extracted functions: `extractFrontmatter` and `findSkillsInDir`.  
- *Reference points*: The original `.codex/superpowers-codex` file is referenced for lines 40-74 and 97-136, suggesting it is at least 136 lines long.  
- *Question*: Are these two functions the entirety of the common skill discovery/parsing logic, or is the shared core missing other reusable components? Without seeing the original `.codex/superpowers-codex` or additional implementation phases, it’s unclear whether the shared core is sufficiently comprehensive to justify the sharing claim.  

**Strand 3: Incomplete Implementation View**  
- *Implementation plan scope*: The provided implementation.md only details **Phase 1** (Create Shared Core Module). It does not describe:  
  - Building the OpenCode plugin using the native plugin API, custom tools, or session hooks (as mentioned in the design).  
  - Any refactoring of the Codex implementation to use the shared core.  
  - Subsequent phases (e.g., plugin development, integration, testing).  
- *Consequence*: The implementation plan, as presented, is incomplete for evaluating whether the OpenCode support will be fully realized. It shows only the foundation (shared core) without the superstructure (plugin) or the critical step of aligning the existing Codex implementation with the shared core.  

### Declared Losses
I chose not to examine:  
- The actual content of `.codex/superpowers-codex` (to verify what logic is truly shared or duplicated).  
- Any files outside the `plans/` directory (e.g., existing OpenCode plugin structure, Codex implementation beyond the referenced lines, or configuration files like `opencode.json`).  
- The remainder of the implementation plan (Phases 2+, if they exist).  
I made this choice because my task was to analyze only the two provided markdown files, not the broader codebase.  

### Open Questions
- Will the Codex implementation be refactored to use the shared core module (`lib/skills-core.js`), or will it continue to maintain its own copy of the extracted functions?  
- What other common functionality (beyond `extractFrontmatter` and `findSkillsInDir) exists between the Codex and OpenCode implementations that should reside in the shared core?  
- What does the OpenCode plugin implementation look like? Specifically, how does it use the native OpenCode plugin API, custom tools (like `use_skill` and `find_skills`), and session startup hooks?  
- How are the "tool mapping instructions" (e.g., mapping `TodoWrite` → `update_plan`, `Skill` tool → `use_skill`) implemented in practice?  

### Closing
The design proposes a shared-core approach to avoid duplication and enable OpenCode support, but the implementation plan (as limited to Phase 1) only achieves the creation of the shared module without addressing duplication in the original Codex implementation or completing the OpenCode plugin. This creates a tension between the design’s sharing goal and the implementation’s risk of perpetuating duplication. I would tell the next scout to seek evidence of:  
1. Refactoring of the Codex implementation to use the shared core module (e.g., commits removing the duplicated lines from `.codex/superpowers-codex` and replacing them with calls to `lib/skills-core.js`).  
2. Completion of the implementation plan beyond Phase 1 (e.g., OpenCode plugin code, session hook integration).  
3. Evaluation of whether the shared core truly captures all common functionality (by comparing the original `.codex/superpowers-codex` to the shared module).  
Without these, the sharing claim remains aspirational rather than realized.