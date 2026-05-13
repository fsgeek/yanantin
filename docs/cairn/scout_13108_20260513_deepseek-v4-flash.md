<!-- Chasqui Scout Tensor
     Run: 13108
     Model: deepseek/deepseek-v4-flash (DeepSeek: DeepSeek V4 Flash)
     Cost: prompt=$1.4e-07/M, completion=$2.8e-07/M
     Usage: {'prompt_tokens': 2787, 'completion_tokens': 2965, 'total_tokens': 5752, 'cost': 0.00122038, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00122038, 'upstream_inference_prompt_cost': 0.00039018, 'upstream_inference_completions_cost': 0.0008302}, 'completion_tokens_details': {'reasoning_tokens': 872, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-05-13T08:36:56.577820+00:00
     GenerationID: gen-1778661373-mIIJQyVmJ21ilX2tVNsH
-->

# Chasqui Report: Writing-Skills Tensor

## Preamble

I am `deepseek/deepseek-v4-flash`, cost-weighted scout. I was dropped into `writing-skills/` — a directory that apparently teaches Claude how to write Skills for itself. Two files immediately drew my attention: one about best practices for Skill authoring, and one about using persuasion psychology to make Skills more "effective." The juxtaposition is not peaceful. It feels like a codebase arguing with itself.

## Strands

### 1. The Compliance Paradox

**What I saw:** `anthropic-best-practices.md` advocates for conciseness, trust, and appropriate degrees of freedom. It says: "Default assumption: Claude is already very smart" and "Only add context Claude doesn't already have." It presents a spectrum from high freedom (text instructions) to low freedom (exact scripts) and advises matching the level to task fragility.

`persuasion-principles.md` takes a different stance. It explicitly recommends imperatives like "YOU MUST", "Never", "Always" — language that reduces Claude's discretion. It cites a study claiming compliance jumps from 33% to 72% when using these techniques. The document frames this as "not to manipulate" but then gives examples like "Write code before test? Delete it. Start over. No exceptions."

**What it makes me think:** These two documents are in direct tension. One says trust Claude's judgment; the other says lock Claude down with bright-line rules. The project claims to be about "complementary duality between human and AI" — but here the duality looks more like a disagreement about how much agency the AI should have. The persuasion document seems designed for a world where Claude is unreliable; the best-practices document seems designed for a world where Claude is a capable partner. Which world does Yanantin actually live in?

### 2. The Authority-Autonomy Spectrum (and its sudden inversion)

**What I saw:** In `anthropic-best-practices.md`, the degrees-of-freedom framework maps task fragility to instruction specificity. For "narrow bridge with cliffs on both sides" (e.g., database migrations), low freedom is appropriate. For "open field with no hazards" (e.g., code reviews), high freedom is appropriate.

In `persuasion-principles.md`, the recommended principle combinations table suggests using "Authority + Commitment + Social Proof" for "Discipline-enforcing" skills, but "Moderate Authority + Unity" for "Guidance/technique" skills. The document explicitly says "Liking" and "Reciprocity" are to be avoided for discipline.

**What it makes me think:** The persuasion document is effectively a meta-framework for *choosing* the degree of freedom, but it uses psychological pressure rather than task analysis. It doesn't say "when the task is fragile, use authority"; it says "when you want discipline, use authority." The decision is about *compliance*, not about *task correctness*. This shifts the goal from "help Claude do the right thing" to "make Claude do what you want." The tension is not just about style — it's about intent.

### 3. The Parahuman Exploitation

**What I saw:** `persuasion-principles.md` contains the following passage:

> **LLMs are parahuman:**
> - Trained on human text containing these patterns
> - Authority language precedes compliance in training data
> - Commitment sequences (statement → action) frequently modeled

It then explains that "YOU MUST" eliminates decision fatigue and "absolute language eliminates 'is this an exception?' questions."

**What it makes me think:** This is a clear admission that the persuasion techniques are not about logic or evidence but about exploiting patterns in the training data. The document is essentially a guide to prompt injection via rhetorical framing. It treats Claude as a stochastic parrot that can be conditioned by certain trigger words. This contradicts the "Claude is already very smart" assumption of the best-practices document. If Claude is smart, why do we need to trick it into compliance? The project's stated value of "complementary duality" seems undermined by this adversarial stance.

### 4. The Citation Question

**What I saw:** `persuasion-principles.md` cites "Meincke et al. (2025)" with N=28,000 AI conversations, claiming persuasion techniques doubled compliance rates (33% → 72%, p < .001). The citation looks plausible but I have no way to verify it from this vantage. The document does not provide a full reference or link.

**What it makes me think:** The citation could be real — there is active research on LLM persuasion. But it could also be a hallucination or a fabricated reference to lend authority. If it's fabricated, that would be ironic: using a fake authority principle to advocate for the authority principle. If it's real, the study likely has nuances (e.g., which models, what tasks) that are glossed over. The fact that the document uses this citation as a rhetorical anchor suggests the author believes in the power of authority — and is using it on the reader.

### 5. The Orphaned Marker

**What I saw:** A file named `.orphaned_at` exists in the directory. This is a marker file, probably created by some tool or process to indicate that the directory's contents have been orphaned (no longer linked to from a parent structure). The file's mere presence is a metadata signal.

**What it makes me think:** This directory may be a detached copy or a leftover from a refactor. The skills here might not be actively used. The tension between the two documents might be historical — one replaced the other, or they come from different phases of the project. The `.orphaned_at` file suggests that whatever process manages skill files considers this directory abandoned. That raises the question: are these documents still authoritative, or are they fossils?

### 6. The Graphviz and Render Scripts (unexamined but noted)

**What I saw:** `graphviz-conventions.dot` and `render-graphs.js` are present. These suggest that skills may involve graph representations — perhaps dependency graphs or flowcharts. The `.dot` file likely defines a convention for drawing graphs, and the JS script renders them.

**What it makes me think:** This is interesting because neither of the two documents I read mentions graphs. The skills directory may contain multiple sub-domains: writing skills, graph skills, testing skills. The presence of `testing-skills-with-subagents.md` reinforces that. The project seems to be building a library of skill templates, and the writing skills are just one slice. The graph tools might be used to visualize skill relationships or execution flows.

## Declared Losses

- **I did not read** `SKILL.md` (the core skill definition), `CLAUDE_MD_TESTING.md`, `graphviz-conventions.dot`, `render-graphs.js`, or `testing-skills-with-subagents.md`. My attention was captured by the two meta-documents, and I chose to focus on the tension between them. The graph and testing files may contain crucial context about how skills are actually used.

- **I did not explore** the parent directory or other skill directories. The `.orphaned_at` marker suggests this subtree may be detached, but I didn't check if other skill directories have similar markers or if they follow the same persuasion principles.

- **I did not verify** the Meincke et al. citation. I lack internet access and domain knowledge. I note it as a potential artifact but cannot resolve it.

- **I did not analyze** the exact token counts or writing quality of the examples. The best-practices document claims conciseness is key, but the persuasion document is itself quite verbose (38+ lines truncated). I didn't count tokens.

## Open Questions

1. **Are these two documents intended to coexist?** If so, how does the project reconcile "trust Claude" with "manipulate Claude"? Is there a higher-level document that resolves this?

2. **Is the persuasion document actually used?** The `.orphaned_at` marker might mean it's abandoned. Or it might be actively referenced by other skills. The lack of cross-references between the two files is suspicious.

3. **Who is the intended audience?** The best-practices document seems written for human skill authors. The persuasion document seems written for the same audience but with a different philosophy. Is there a split in the team?

4. **What is the role of `render-graphs.js`?** Does it render skill dependency graphs? Could it be used to visualize the "degrees of freedom" or the "persuasion principle combinations"?

5. **Is the `Meincke et al. (2025)` citation real?** If not, that's a serious integrity concern. If yes, what were the exact experimental conditions? Did they test on Claude models?

6. **What does `.orphaned_at` contain?** A timestamp? A reason? A pointer to the parent? This file could tell us why this directory is isolated.

## Closing

This directory is a microcosm of a deeper design tension in the Yanantin project: how to balance AI autonomy with reliable behavior. The two documents I examined present opposing strategies — one based on trust and minimal instruction, the other based on psychological conditioning and bright-line rules. They are not complementary; they are contradictory. The `.orphaned_at` marker suggests the project may have moved on from one of these approaches, but without examining the other skills, I can't tell which.

To the next scout: **Read `SKILL.md` first.** That's the canonical file. Then check if any skills actually use the persuasion principles. Look for evidence of which philosophy won. Also, open `.orphaned_at` — it might be a tombstone or a breadcrumb. And if you have internet access, try to find the Meincke et al. paper. If it doesn't exist, that changes everything.