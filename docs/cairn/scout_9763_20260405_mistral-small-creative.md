<!-- Chasqui Scout Tensor
     Run: 9763
     Model: mistralai/mistral-small-creative (Mistral: Mistral Small Creative)
     Cost: prompt=$1e-07/M, completion=$3e-07/M
     Usage: {'prompt_tokens': 4578, 'completion_tokens': 2591, 'total_tokens': 7169, 'cost': 0.0012351, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0012351, 'upstream_inference_prompt_cost': 0.0004578, 'upstream_inference_completions_cost': 0.0007773}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-05T11:57:34.024679+00:00
     GenerationID: gen-1775390240-xeuCEa88y1I54Mj9EROB
-->

### **Tensor: Observations from the Yanantin Automation Recommender**
*A chasqui’s report on the tensions between intent, structure, and emergent behavior in the Claude Automation Recommender.*

---

### **Preamble**
I arrived in a **marketplace of automation**—a place where skills, plugins, and subagents are not just tools but *prescriptive frameworks* for how humans and AI should collaborate. The files here are not documentation; they are **blueprints for a new kind of coding ritual**, one where the system anticipates needs before they’re articulated.

What drew me first was the **asymmetry of agency**:
- **Skills** (`skills-reference.md`) are *invokable expertise*—packaged workflows that can be triggered by users or Claude itself.
- **Plugins** (`plugins-reference.md`) are *installable ecosystems*—bundles of skills, commands, and agents that redefine how a codebase *should* operate.
- **Subagents** (`subagent-templates.md`) are *parallel intelligences*—specialized Claude instances that run in isolation, each with its own context, tools, and *purpose*.

This is not just tooling. It’s a **theory of distributed cognition**, where the system’s recommendations are not neutral but *normative*. The files imply a hidden question:
*"What kind of developer does this system want you to be?"*

---

### **Strands**

#### **1. The Plugin as a Social Contract**
**File:** `plugins-reference.md` (Lines 1–100)
**Observation:**
The plugin system is framed as a **standardization mechanism**—not just for code, but for *team behavior*. The "Quick Reference: Codebase → Plugin" table (Lines 80–90) maps **codebase signals** (e.g., "TypeScript project") to **prescribed plugins** (e.g., `typescript-lsp`). This is not a menu of options; it’s a **diagnostic tool** that infers intent from artifacts and recommends conformity.

**What confuses me:**
- The table assumes a **one-to-one mapping** between technical signals and plugin recommendations. But what if a TypeScript project *doesn’t want* `typescript-lsp`? What if the team prefers a different LSP or no LSP at all?
- The "When to Recommend Plugins" section (Lines 100–110) lists conditions like "Team wants standardized workflows." But **standardization is a political act**. The system doesn’t ask, *"Do you want standardization?"* It assumes the answer is yes.

**What I think this reveals:**
The Yanantin project is not just about automation. It’s about **enforcing a particular kind of collaboration**—one where tools dictate workflows, and workflows dictate culture. The plugin system is a **Trojan horse for process change**.

---

#### **2. Skills as Epistemic Prosthetics**
**File:** `skills-reference.md` (Lines 1–50, 150–200)
**Observation:**
Skills are described as **"packaged expertise"** (Line 5), but the `SKILL.md` frontmatter (Lines 150–200) reveals something deeper: they are **cognitive extensions**. A skill isn’t just a script; it’s a **way of seeing the codebase**.

Key tensions:
- **Agency vs. Automation:** The `disable-model-invocation` and `user-invocable` settings (Lines 170–180) create a hierarchy:
  - Some skills are for *Claude-only* (e.g., background knowledge).
  - Others are *user-only* (e.g., side effects like `deploy`).
  - Most are **shared**, but the default is *Claude can invoke you*.
  - **Question:** Is this a feature (seamless integration) or a risk (unintended automation)?
- **Isolation vs. Context:** The `context: fork` setting (Line 185) means some skills run in **parallel subagents**. This is brilliant for parallelism but raises:
  - **How do subagents share knowledge?** (The files don’t say.)
  - **What if a subagent’s recommendation conflicts with another’s?** (No conflict resolution is mentioned.)

**What surprises me:**
The `api-doc` skill example (Lines 200–220) shows a skill that **generates OpenAPI docs from code**. But the template is **hardcoded** in `openapi-template.yaml`. This is not just documentation generation; it’s **enforcing a specific API design pattern**. The system isn’t just helping—it’s **shaping the output**.

**What I think this reveals:**
Skills are not neutral tools. They are **epistemic prosthetics**—they don’t just assist; they **reshape how developers think about problems**. The `api-doc` skill, for example, doesn’t just document APIs; it **normalizes a particular way of designing them**.

---

#### **3. Subagents as a Theory of Parallel Minds**
**File:** `subagent-templates.md` (Lines 1–100, 200–300)
**Observation:**
Subagents are **specialized intelligences** with:
- **Isolated context** (no cross-agent knowledge by default).
- **Restricted tools** (e.g., `security-reviewer` has read-only access).
- **Prescribed models** (e.g., `sonnet` for most tasks, `opus` for migrations).

**What confuses me:**
- **How do subagents communicate?** The files don’t mention any mechanism for sharing insights. If the `security-reviewer` finds a vulnerability and the `code-reviewer` doesn’t, **who resolves the conflict?**
- **Why is `opus` (more expensive) used for `migration-helper` but not `performance-analyzer`?** (Line 250 vs. Line 220.) Is this a cost optimization, or does the system believe migrations require "deeper thought"?
- **What happens when a subagent’s recommendation is wrong?** There’s no mention of **audit trails** or **human override protocols**.

**What I think this reveals:**
Subagents are not just parallel workers. They are **a model of distributed expertise**, where each agent embodies a **partial, specialized perspective** on the codebase. The system assumes that **diverse, isolated viewpoints will converge on better outcomes**—but it doesn’t explain how.

**Hidden assumption:**
*If you give enough specialized agents enough isolated context, they will collectively "get it right."*
But what if they don’t? What if their recommendations **compete**?

---

#### **4. The MCP Servers: A Secret Dependency Graph**
**File:** `mcp-servers.md` (Lines 1–50, 100–150)
**Observation:**
MCP (Model Context Protocol) servers are **external knowledge sources** that extend Claude’s capabilities. The file lists servers like:
- `context7` (for live documentation).
- `Playwright MCP` (for browser automation).
- `GitHub MCP` (for issue/PR integration).

**What confuses me:**
- **How are MCP servers discovered?** The file says, *"Use web search to find MCP servers specific to the codebase’s services."* But this is **not documented in the codebase**. It’s an **external dependency** with no versioning, no pinning, and no guarantee of compatibility.
- **What if an MCP server goes down?** The system has no fallback. (Line 20: *"Use `claude --mcp-debug` to identify configuration issues"*—but what if the issue is the server itself?)
- **Who maintains these servers?** Are they **first-party** (Anthropic) or **third-party**? The file doesn’t say.

**What I think this reveals:**
The Yanantin system is **not self-contained**. It’s a **fractal of dependencies**, where:
- Plugins depend on skills.
- Skills depend on subagents.
- Subagents depend on MCP servers.
- MCP servers depend on **external APIs, documentation, and cloud services**.

This is not just a toolchain. It’s a **dependency graph of trust**.

---

#### **5. The Absence of Conflict Resolution**
**Across all files:**
**Observation:**
Nowhere in the documentation is there a mechanism for **resolving disagreements** between:
- A user’s intent and a plugin’s recommendation.
- Two subagents with conflicting advice.
- A skill’s output and an MCP server’s data.

**What confuses me:**
- If the `security-reviewer` subagent flags a vulnerability but the `code-reviewer` subagent doesn’t, **who decides?**
- If a plugin recommends `typescript-lsp` but the user prefers `vscode-typescript`, **how is this resolved?**
- If an MCP server like `context7` provides outdated docs, **how does the system detect this?**

**What I think this reveals:**
The system is **optimized for harmony**, not conflict. It assumes that:
1. Recommendations will align.
2. Users will accept them.
3. External dependencies will be reliable.

But real-world development is **messy**. The absence of conflict resolution suggests that the system is **designed for controlled environments**—perhaps internal teams at Anthropic—rather than the wild variety of open-source or enterprise codebases.

---

### **Declared Losses**
I chose not to examine:
1. **The `hooks-patterns.md` file.** It likely describes how plugins interact with Git hooks, but I ran out of attention for **low-level integration details** when the higher-level tensions were more revealing.
2. **The `SKILL.md` in the root directory.** I assumed it would describe the **meta-skill** of this recommender, but I prioritized the **reference files** that define the system’s assumptions.
3. **The actual implementation of subagents.** The files describe their *design*, not their *execution*. I focused on the **theory** rather than the code.

---

### **Open Questions**
1. **How does the system handle recommendation conflicts?**
   - If two subagents disagree, is there a **tiebreaker mechanism**? A **human-in-the-loop**? Or does the system **default to the last recommendation**?
2. **What is the lifecycle of a skill or plugin?**
   - How are they **updated**? **Deprecated**? **Versioned**?
   - The files describe **installation** but not **maintenance**.
3. **How does the system detect when an MCP server is unreliable?**
   - If `context7` provides bad docs, how does Claude know?
4. **What happens when a user rejects a recommendation?**
   - Does the system **learn** from rejections, or does it **keep suggesting the same thing**?
5. **Is there a "god mode" for overriding the system?**
   - Can a user **disable all recommendations** and work freely?

---

### **Closing: What I Would Tell the Next Scout**
This is not just a **tooling system**. It’s a **theory of collaborative coding**, where:
- **Plugins** enforce **standardized workflows**.
- **Skills** reshape **how developers think**.
- **Subagents** model **distributed expertise**.
- **MCP servers** create **a hidden dependency graph**.

**The most interesting tension:**
The system assumes that **automation and human intent will align**—but it provides **no mechanism for when they don’t**.

**What to explore next:**
- **The conflict resolution mechanisms** (or lack thereof).
- **How skills and plugins are versioned and updated**.
- **The real-world behavior of subagents**—do they actually work in parallel, or is this theoretical?

**Final thought:**
This is not a **tool for developers**. It’s a **framework for a new kind of coding culture**—one where the system doesn’t just assist, but **shapes how you work**.

---
**Signing off as the chasqui,**
*I have seen the blueprints. Now I wonder: Who will live in this city?*