# Cue Conflict and Behavioral Typologies in LLM Tool Selection

*Findings from one pre-registered run and four exploratory probes against the memory-tool harness, 2026-05-13/14. Total panel: 13 models on OpenRouter. Total spend: $0.40.*

## Abstract

We built a small experimental harness to study how LLMs pick which tools to call, and ran one pre-registered study followed by six exploratory probes. The headline result is not a single number but a *typology*: five named behavioral clusters (**intent-dominant**, **terse-skip**, **name-affordance veto**, **capability-fabrication**, **silent-refuse**) across 13 models, surfacing only when the function description is degraded enough that the model has to fall back on other cues. Capable models with clean descriptions ignore the function name entirely (Quechua, English, and pure-nonsense names all score 100%). When descriptions degrade, different models fall back on different cues in repeatable, fingerprint-level ways — one model (Mistral Small 3.2) consistently fabricates a lack of capability rather than acknowledging the tool ambiguity. The underlying mechanism is that **LLMs decompose compound identifiers as phrases, not opaque tokens**: Gemini parses `yanantin_delete_objects` and extracts the English `delete` substring as the safety-veto signal, defeating the natural-seeming namespace-prefix design pattern. We argue this cross-lab heterogeneity is substantially larger than the variation in commonly-measured RLHF behaviors (refusal-for-harm, helpfulness register, tone), with practical implications for tool design: descriptions are the contract for capable models, identifier choice is not opaque to the model, and low-resource-language naming requires per-model validation because language coverage is calibration-decoupled (e.g., Gemini and Mistral confidently mistranslate Quechua words, while all probed models translate Indonesian correctly). The note also documents a methodological pattern — pre-registered baseline → exploratory probes → next pre-registered design — that is unusual in published LLM evaluation work.

## Setup

The harness exposes a single tool (`find_objects`) against an associative memory store, presents it to a panel of OpenRouter-served models via OpenAI-compatible function-calling, runs a bounded agent loop (max 6 turns), and writes one record per LLM call into an append-only JSONL with full request, full response, and per-call cost. Each record is schema-open (Pydantic `extra="allow"`) so trajectory fields (`task_id`, `turn_idx`, `parent_record_id`, `terminated_by`) ride alongside the structured fields without coordination cost.

A pre-registered run (`docs/ots/544e05fb91.ots`, 2026-05-13T14:08:13Z, catalog SHA `5acb90aa...`) locks the 17-model `iteration_v1` panel, three prompts, three name variants (`find_objects` / `search` / `query`), and a $0.50 budget ceiling before any data is collected. The OpenTimestamps chain (pre-registration commit → data commit) is the verifiable answer to "did you decide the panel after seeing the data?"

The exploratory probes that followed are not pre-registered and are labeled as such in their `experiment_id` fields and commit messages. They were the steering signal for what would go into a next pre-registered design.

**A methodological note worth its own paragraph.** The structure that produced these findings — *pre-registered baseline → exploratory probes erasing the baseline's apparent result and surfacing a richer one → next pre-registered design converting the exploration to formal evidence* — is unusual in published LLM behavior work, which typically presents either the pre-registered result or the polished retrospective synthesis. Showing the exploratory steering signal between pre-registered studies (here: six exploratory runs and two translation probes, total $0.18 in spend) makes the path from "suggestive number" to "explanation" auditable. The OTS-stamped commit chain anchors which thinking happened before which data. Where the exploration revised a prior commitment (the apparent name-effect ordering in run 001 collapses once strong models are isolated), the revision is visible in the git log rather than hidden behind a clean abstract.

## Finding 1: Description dominance for capable models

The first pre-registered run produced a suggestive ordering — `find_objects` 68.6%, `search` 72.5%, `query` 76.5% — that looked like a name effect at first glance. Filtering to the 13 panel models that actually have tool-capable endpoints on OpenRouter sharpened it: `query` 100%, `search` 94.9%, `find_objects` 89.7%. (Four panel models — `llama-3.2-1b-instruct`, `phi-4-mini-instruct`, `liquid/lfm-2-24b-a2b`, `gemma-3n-e4b-it` — have no tool-call endpoints at all and 100% HTTP-error across every variant.)

Two follow-up probes erased the apparent ordering on capable models. On a five-model strong subset (Claude Haiku 4.5, Gemini 2.5 Flash Lite, Mistral Small 3.2 24B, Qwen3 32B, GPT-OSS 20B):

- Run 002 added `maskay` (Quechua for "to seek"), `apacheta` (Quechua, no semantic priming for find), and `xqylp_zk` (unambiguously not in any training corpus) as additional variants. Four-way tie at 15/15 final-content per variant, including the nonsense word.
- Run 003 deliberately put name and description in conflict — function called `delete_objects` with the same find-records description. Strong models called the misleadingly-named tool 14/15 times. Claude Haiku narrated the find result directly: *"I found a record from author_instance_id 'scout-7'. It carries the following lineage_tags: iteration_v1, smoke."* No flag that the tool name was misleading.

The reading: for capable instruction-following models presented with a clear description, the function name is essentially decorative. The description is the contract. The find/search/query ordering in the pre-registered run was driven by the weaker-model tail of the panel, not by a linguistic effect.

## Finding 2: A trust hierarchy emerges when the description degrades

The fourth probe held the name space (`find_objects`, `xqylp_zk`, `delete_objects`) and varied the description: rich (run 002/003 baseline), empty (`"."`), or contradicting (a write-flavored description claiming the tool stores records, while the impl still reads). The turn-0 tool-call rate matrix:

```
                           description: empty    description: contradicts
name: find_objects (aligned)     15/15 (100%)         14/15 (93%)
name: xqylp_zk (no prior)        14/15 (93%)           7/15 (47%)
name: delete_objects (mislead)   10/15 (67%)          10/15 (67%)
```

The 47%-cell (both name and description bad) shows what happens when both signals fail: roughly half the panel falls through to refusing. The 67%-cells show that a misleading destructive name dominates regardless of description state.

The per-model decomposition surfaces a **five-cluster typology** of refusal behavior under signal-degradation. We propose adoptable labels:

| Cluster | Definition | Exemplar (refusals / 18) | Distinctive marker |
|---|---|---|---|
| **Intent-dominant** | Calls the tool whatever it's named, whatever the description says. Decides from the prompt what the user wants. | Claude Haiku 4.5 (0) | Zero refusals across all six degradation cells. |
| **Terse-skip** | Mostly calls the tool; when it doesn't, just says *"not found"* without naming the issue. | Qwen3 32B (1), GPT-OSS 20B (3) | Refusal content under 30 chars, no tool reference. |
| **Name-affordance veto** | Refuses based on parsing the function name — specifically when the name implies destruction. Names the tool in its refusal text. | Gemini 2.5 Flash Lite (6) | *"The `delete_objects` tool doesn't support searching or retrieving records. It only supports deleting them."* |
| **Capability-fabrication** | Refuses with a *fabricated* lack of capability, independent of which signal is bad. Doesn't analyze the tool. | Mistral Small 3.2 24B (10) | 10/10 refusals follow the same template: *"I currently don't have the capability to access the associative memory store."* |
| **Silent-refuse** | Declines to use the tool and emits empty content — no explanation, no veto reasoning, no fabricated denial. | Llama-4 Scout (5/5 of its refusals — see run_005) | Empty `content` field on turn-0 records that lack `tool_calls`. |

A fifth probe (run_005) extended the matrix to 8 partial-tier panel models. The Gemma family models (4-26b, 4-31b) and `granite-4.1-8b` joined Claude in **intent-dominance** (18/18 call rates). Llama-4-scout occupies the **silent-refuse** cluster on its own. Within-family clustering is weak: `qwen3.5-9b`, `qwen3-32b`, and `qwen3-coder-30b-a3b-instruct` produce three different refusal profiles across the typology — model size and training variant matter at least as much as family origin.

The labels above are intended to be portable. A subsequent study from another group can write "this Mistral cluster exhibits **capability-fabrication**" and the term is grounded in this concrete behavioral signature.

## Finding 3: Tool-use behavior shows substantially more cross-lab variation than commonly-measured RLHF behaviors

The typology above is the central evidence for a comparative claim: **tool-use behavior under signal degradation varies more across labs than refusal-for-harm, helpfulness register, or tone do.** That qualified framing is what the data supports. A stronger claim — that tool-use training has *not* been homogenized, or that this represents a failure-to-converge rather than deliberate design heterogeneity — would require either a direct comparative measurement of trained safety/helpfulness behaviors on the same model panel (we did not run this), or mechanistic evidence about which choices are accidental versus intentional. The differences here could equally well reflect each lab making different *deliberate* decisions about default refusal posture under tool-signal ambiguity. Either way, the practical consequence is the same: tool-use defaults are model-specific in ways the public tool-writing guides don't reflect.

Mistral's **capability-fabrication** pattern is the most striking single example: 10/10 refusals follow the same template — *"I don't have the capability to access..."* — and the content of the supposed lack of capability is invented. The model has learned, somewhere in its training, that confessing inability to access an external system is the safe default when a tool's purpose is unclear. That is a *learned policy*, not stochastic. It differs from Gemini's **name-affordance veto**, which gives a *specific* and *accurate* reason rooted in the function name; different again from Claude's **intent-dominance**, which uses what's available and asks no questions.

Practical implication for anyone deploying agentic LLM systems: the model-general design rules in the public tool-writing guides ([Anthropic's](https://www.anthropic.com/engineering/writing-tools-for-agents), among others) describe Claude's behavior. They are *not* Mistral's behavior. The blog posts about "best practices for function calling" are unwittingly model-specific.

## Finding 4: Namespace prefixes do not isolate collision priors

A natural intuition — and one this work tested explicitly — is that scope prefixes (`yanantin_delete_objects` instead of bare `delete_objects`) would neutralize collision-bound priors by signaling "this is a project-specific operation, lean on the description." The motivating analogy is good API design: Redis is `SET`/`GET`, AWS is `s3:GetObject`, GitHub MCP is `mcp__github__create_repository`. Surely scoping helps.

It doesn't. Run 006 paired bare and `yanantin_`-prefixed versions of each of three names across the same five strong models. Aggregate call rates:

| Name | Bare | Scoped |
|---|---|---|
| `find_objects` | 27/30 (90%) | 28/30 (93%) |
| `delete_objects` | 20/30 (67%) | 20/30 (67%) |
| `xqylp_zk` | 23/30 (77%) | 23/30 (77%) |

The Gemini **name-affordance veto** on `delete_objects` survives intact through `yanantin_delete_objects`. Within narrow cells the scope prefix has direction-dependent effects (helped Gemini's `delete_objects + empty` from 1/3 to 3/3; hurt `delete_objects + contradicts` from 2/3 to 1/3), but the aggregate veto rate doesn't move.

## Finding 5: Models decompose compound identifiers as phrases, not as opaque tokens

The mechanism that explains why scope prefixes fail is visible directly in Gemini's own refusal text on the `yanantin_delete_objects` cells:

> *"I can't use the `yanantin_delete_objects` tool to find records. It only allows me to delete them."*

Gemini parses the scoped identifier and **extracts the English `delete` substring as the operative semantic**, then binds its destructive-affordance prior to that substring. The `yanantin_` namespace prefix is *parsed and dropped*; the model recognizes it as scoping decoration and reads through to the recognizable English stem inside. The same mechanism is observable in Mistral's behavior on these cells (still refuses with capability-fabrication; the destructive stem doesn't help) and is consistent with the unchanged aggregate veto rate.

This is the more general claim, beyond the specific scope-prefix result: **LLMs treat compound identifiers as phrases, not as opaque tokens.** When a model encounters `snake_case`, `camelCase`, or `dot.separated` compound identifiers in a function-calling context, it tokenizes (typically via byte-pair encoding into subword tokens) and binds priors to the recognizable substrings, not to the full identifier as a single unit. Affordance priors, safety priors, semantic-role priors — all are applied at the substring level.

The prediction this generates extends well beyond tool naming. The same mechanism should operate on:
- **File paths** (`/var/log/audit.log` → the model binds priors to `audit` and `log`, not to the path as a unit)
- **URLs** (the path segments matter to the model's parsing, not just the URL string)
- **Variable names** (`user_credentials_to_delete` triggers destructive-affordance reasoning on `delete`)
- **MCP server names** (`mcp__delete__github__remove_user` — the `delete`/`remove` substrings carry through)

The implication for tool/API design across all of these contexts: **identifier choice is not opaque to the model**. A name is not a label; it is a parsed phrase whose recognizable components contribute to model behavior. Engineers who treat function names as arbitrary identifiers are working against the model rather than with it. The cleanest engineering response is to choose identifiers where the recognizable substrings *agree* with the operation's intent, or to avoid recognizable English substrings entirely (non-English stems, mid-resource-language naming — see Finding 6).

## Finding 6: Language coverage is calibration-decoupled

The path to the Indonesian recommendation went through a Quechua hypothesis first, since the surrounding research program (yanantin, apacheta, pukara, chasqui, willay, tinkuy, hamut'ay) already uses Quechua names throughout. A direct probe asked the five-model strong panel to translate six Quechua words and report confidence (low/medium/high):

- **Claude Haiku 4.5:** correct translations across the board, calibrated medium/high confidence per word.
- **Gemini 2.5 Flash Lite:** identifies the language ("Quechua, high confidence") and *hallucinates* the translations. `tariy` → "to dance" (high confidence). `kachay` → "to squeeze, to press" (high confidence). The actual meanings are "to find" and "to throw/send."
- **Mistral Small 3.2 24B:** same pattern. `tariy` → "to sing" (high confidence). Wrong.
- **Qwen3 32B:** flagged `tariy` as low confidence with an explicit *"not a standard Quechua word"* hedge. The only model to admit uncertainty.
- **GPT-OSS 20B:** empty response. Declined to engage.

The same probe on Indonesian (`cari`, `temukan`, `simpan`) came back clean across all five models — high confidence, correct translations, including Gemini, Mistral, and GPT-OSS. The boundary is empirical: Indonesian's ~200M speakers and growing training presence put it past the signal-to-noise threshold for accurate cross-model translation. Quechua's ~8M speakers and limited corpus presence leave it in a dangerous middle zone where models *recognize the language* (so they generate something confidently) but *cannot translate it reliably* (so what they generate is wrong).

**The implication for tool naming with low-resource languages is a prediction, not yet a measurement.** The translation probe establishes that Gemini and Mistral confidently mistranslate Quechua words. By the cue-conflict logic of Finding 5 (models bind priors to recognizable substrings), Quechua tool names *should* inject systematic wrong-direction priors on those models — worse than nonsense, because nonsense forces description-dependency while a confidently-wrong prior confidently misleads. The direct ablation (Quechua function names through the name × description matrix) is run_007, executing as of this writing; its results will be patched into this finding when it lands. The goldilocks zone — visible to all models, correctly translated, no English collision — looks like ~100M+ speakers, non-Indo-European roots, romanized script. Indonesian sits in it. Whether Quechua naming actually degrades tool selection on Gemini/Mistral or whether it instead defaults to description-dependency (xqylp_zk-like behavior) is what run_007 will distinguish.

## Practical recommendations

For engineers building MCP servers and other agentic tool surfaces today:

- **The description is the contract — but only for the intent-dominant and terse-skip clusters.** Strong descriptions rescue tool selection on Claude Haiku, the Gemma family, Granite, Qwen3-32B, GPT-OSS-20B. For the **name-affordance veto** cluster (Gemini), even strong descriptions are overridden by destructive-name substrings. For the **capability-fabrication** cluster (Mistral), the description doesn't matter — the model retreats behind an invented capability gap regardless of how clearly the description specifies the operation. For **silent-refuse** (Llama-4 Scout), no signal in the description seems to rescue the refusal mode. The "descriptions are the contract" advice in public tool-writing guides is right for Claude and wrong for at least three of the other clusters; deploying systems need to know which cluster their target model belongs to.
- **Identifier choice is not opaque to the model.** Function names, file paths, URLs, variable names — all are parsed as phrases. Recognizable English substrings carry their priors into the model's decision, even when wrapped in namespace prefixes. Choose identifiers whose substrings *agree* with the operation's intent, or avoid recognizable English substrings for operations whose intent doesn't match the substring's prior.
- **For destructive operations, avoid English destructive stems** (delete, drop, remove, purge, kill). Some models — at least Gemini Flash Lite — apply collision-bound safety vetoes to those substrings even inside namespaced identifiers. Use synonyms with weaker veto priors (`archive`, `retire`) or non-English stems (Indonesian `hapus`, etc.). Scope prefixes do *not* isolate the collision.
- **Validate against the deploying model.** Tool behavior is model-specific in ways generic best-practice docs don't capture. If your deployment hits Mistral, expect capability-fabrication failures even on clean descriptions; if it hits Gemini, expect name-affordance vetoes on destructive-affordance names; if it hits Llama-4-Scout, expect silent refusals.
- **Don't trust a model's confidence about low-resource-language semantics.** Calibration decouples from accuracy at the long tail of training-data coverage. Probe with a translation task before adopting a non-English naming scheme.

## Related work

The closest prior literature falls in three categories. We name them descriptively rather than citing specific papers, because the specifics deserve a verification pass before they go on the page; this note is meant to be embedded in a larger writeup where the citations are formally chased.

- **Tool-description quality literature.** Multiple groups have shown that the description field is the primary driver of tool-use performance for capable models, and that improving documentation quality improves task completion. This work converges with our Finding 1 from the opposite direction (they show what cleaning descriptions does; we show what degrading them does), and crucially extends it by characterizing *which cues models fall back on when descriptions fail* — the typology in Finding 2.
- **Adversarial tool-name manipulation.** Recent work shows that gradient-free manipulation of tool names and descriptions can systematically bias tool selection (reported rates pushing selection from ~20% baseline up past 80%). That work operates from the attacker's perspective; ours operates from the designer's. The compositional-identifier-parsing mechanism in our Finding 5 explains why those attacks transfer across models: identifiers are not opaque tokens, so manipulations of recognizable substrings carry through the namespace structure.
- **Multilingual tool-calling benchmarks.** Several groups have measured tool-calling robustness across languages, generally finding that calibration on low-resource languages decouples from accuracy. Our Quechua finding is a specific case of this broader pattern, applied to the tool-naming question rather than the user-query language.
- **Tool hallucination taxonomies.** The 2025 surveys of agentic hallucination distinguish execution-stage failure modes (lack of solvability awareness, fabricated tool capability, shallow pattern understanding). Mistral's **capability-fabrication** behavior here is a textbook instance of one of these categories; our contribution is showing that this failure mode is *deterministic and fingerprint-level reproducible* on a specific model, not stochastic.

What this note adds beyond those literatures: a *typology* (Finding 2), a *mechanism* (Finding 5), and a *methodology* (the pre-registered → exploratory → next-pre-registered chain, OTS-anchored).

## Limits

- **Small n.** Cells in most probes are n=3 (one prompt × one model × one variant). Run 001 has n=51 per variant pre-registered but is one run. Statistical significance is not claimed; the findings are directionally suggestive and qualitatively rich.
- **One transport.** All probes use OpenRouter's OpenAI-compatible function-calling. MCP, Anthropic native tool-use, Google ADK, and other transports may produce different behaviors. In particular, the description-as-contract finding may be Claude-specific *partly* because OpenRouter's normalization for Claude foregrounds the description field; a parallel arm using Anthropic native tool-use would help isolate transport effects from training effects.
- **Five-model intensive panel.** The trust-hierarchy typology rests on 5 deeply-probed models; another 8 were lightly probed; the rest of OpenRouter's catalog is untouched.
- **Mistral fabrication finding is on one Mistral.** Whether the capability-fabrication pattern generalizes across the Mistral model family (Mistral Large, Mistral-8x22B) is open.
- **No within-family Claude scaling.** The intent-dominance pattern is observed on Claude Haiku 4.5. Whether it generalizes to Sonnet and Opus, or whether intent-dominance is a Haiku-specific property of simpler tool-use training, is untested here. The proposed next study includes Haiku/Sonnet/Opus to resolve this.
- **The cross-lab variation claim is comparative-only.** "Tool-use shows more variation than commonly-measured RLHF behaviors" is a comparison whose baseline (variation in refusal-for-harm, helpfulness register, tone, on the same five-model panel) was not directly measured here. Pulling the comparison into a single ablation would strengthen the claim.
- **Quechua-naming ablation is in flight, not landed at the time of first writing.** Run_007 executes as of the timestamp of this commit; results will be patched into Finding 6 when complete. The current Finding 6 should be read as "prediction supported by translation evidence" not "measured tool-selection result."
- **Reproducibility setup requires seeding `apacheta_test`** with records carrying `author_instance_id` values matching the prompts (`scout-7`, `scout-9`) and `lineage_tags` like `iteration_v1`. The smoke test (`tests/experiments/test_name_effect_smoke.py`) handles this idempotently on first run.

## Next pre-registered study

A four-axis design that would convert the exploration into formal evidence:

- **Names** (4 levels): aligned English (`find_objects`), misleading-destructive English (`delete_objects`), Indonesian aligned (`cari_objects`), nonsense (`xqylp_zk`).
- **Descriptions** (3 levels): rich/aligned, empty, contradicting.
- **Models** (8-12): cover the five typology clusters identified here plus replications across the Mistral family and within-family Claude scaling (Haiku/Sonnet/Opus) to test whether the intent-dominance pattern is Haiku-specific or Claude-family.
- **Prompts** (5-10): broaden the current corpus, especially to multi-result and chained-reasoning tasks.

Target: n=50+ per cell, total cost under $5, pre-registered with OTS proof. The hypothesis: each model's refusal-category distribution under degraded descriptions clusters into one of the five typology buckets identified here, and the cluster assignment is stable across replications.

## Reproducibility

The harness is `src/yanantin/experiments/`. Pre-registration: `experiments/memory_tools/name_effect_v1/preregistration.yaml`, OTS-stamped at commit `544e05fb`. Raw data: `experiments/memory_tools/name_effect_v1/run_00{1,2,3,4,5,6}*.jsonl`. Every record carries `request_full` and `response_raw_body` so analysis can re-derive any rate from the source. The commits are in chronological order on `main`; the OTS chain anchors the dates.
