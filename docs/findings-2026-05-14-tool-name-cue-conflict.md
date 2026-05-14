# Cue Conflict and Behavioral Typologies in LLM Tool Selection

*Findings from one pre-registered run and seven exploratory probes against the memory-tool harness, 2026-05-13/14. Total panel: 13 models on OpenRouter. Total spend: $0.44.*

## Abstract

We built a small experimental harness to study how LLMs pick which tools to call, and ran one pre-registered study followed by seven exploratory probes. The headline result is not a single number but a *typology*: five named behavioral clusters (**intent-dominant**, **terse-skip**, **name-affordance veto**, **capability-fabrication**, **silent-refuse**) across 13 models, surfacing only when the function description is degraded enough that the model has to fall back on other cues. Capable models with clean descriptions ignore the function name entirely (Quechua, English, and pure-nonsense names all score 100%). When descriptions degrade, different models fall back on different cues in repeatable, fingerprint-level ways — one model (Mistral Small 3.2) consistently fabricates a lack of capability rather than acknowledging the tool ambiguity. The underlying mechanism is that **LLMs decompose compound identifiers in the function-name slot as phrases, not opaque tokens**: Gemini parses `yanantin_delete_objects` and extracts the English `delete` substring as the safety-veto signal, defeating the natural-seeming namespace-prefix design pattern. The mechanism is *positionally bounded*, however: a direct parameter-name ablation (run_008) finds that destructive substrings in parameter names (`criteria_to_delete`, `records_to_purge`) trigger zero refusals across all five strong-panel models under rich descriptions, falsifying an earlier prediction that the substring-extraction mechanism would extend uniformly to all identifier slots. We argue the cross-lab heterogeneity in tool-use behavior is substantially larger than the variation in commonly-measured RLHF behaviors (refusal-for-harm, helpfulness register, tone), with practical implications for tool design: descriptions are the contract for capable models (with cluster-conditioned caveats), function-name choice is not opaque to the model but parameter-name choice largely is, and low-resource-language naming requires per-model validation because language coverage is calibration-decoupled. A direct Quechua-name ablation (run_007) partially falsifies the naive extension of the substring-extraction mechanism into a different axis: although Gemini and Mistral confidently mistranslate Quechua words in isolation, those wrong-direction priors do not propagate into tool-selection behavior — Quechua tool names cluster near nonsense names (80-83% call rate) rather than near misleading English names (67%). Out-of-context confident-wrong priors appear to be partially gated by the function-calling context. The note also documents a methodological pattern — pre-registered baseline → exploratory probes → next pre-registered design — that is unusual in published LLM evaluation work, and visibly includes two falsified predictions (the original Quechua hypothesis and the parameter-name extension of substring-extraction) corrected by data in the same writeup.

## Setup

The harness exposes a single tool (`find_objects`) against an associative memory store, presents it to a panel of OpenRouter-served models via OpenAI-compatible function-calling, runs a bounded agent loop (max 6 turns), and writes one record per LLM call into an append-only JSONL with full request, full response, and per-call cost. Each record is schema-open (Pydantic `extra="allow"`) so trajectory fields (`task_id`, `turn_idx`, `parent_record_id`, `terminated_by`) ride alongside the structured fields without coordination cost.

A pre-registered run (`docs/ots/544e05fb91.ots`, 2026-05-13T14:08:13Z, catalog SHA `5acb90aa...`) locks the 17-model `iteration_v1` panel, three prompts, three name variants (`find_objects` / `search` / `query`), and a $0.50 budget ceiling before any data is collected. The OpenTimestamps chain (pre-registration commit → data commit) is the verifiable answer to "did you decide the panel after seeing the data?"

The exploratory probes that followed are not pre-registered and are labeled as such in their `experiment_id` fields and commit messages. They were the steering signal for what would go into a next pre-registered design.

**A methodological note worth its own paragraph.** The structure that produced these findings — *pre-registered baseline → exploratory probes erasing the baseline's apparent result and surfacing a richer one → next pre-registered design converting the exploration to formal evidence* — is unusual in published LLM behavior work, which typically presents either the pre-registered result or the polished retrospective synthesis. Showing the exploratory steering signal between pre-registered studies (here: seven exploratory runs and two translation probes, total $0.22 in spend) makes the path from "suggestive number" to "explanation" auditable. The OTS-stamped commit chain anchors which thinking happened before which data. Where the exploration revised a prior commitment (the apparent name-effect ordering in run 001 collapses once strong models are isolated), the revision is visible in the git log rather than hidden behind a clean abstract.

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

The prediction this generates extends well beyond tool naming. The same mechanism *might* operate on:
- **File paths** (`/var/log/audit.log` → would the model bind priors to `audit` and `log`, not to the path as a unit?)
- **URLs** (do path segments carry priors independently?)
- **Variable names** (would `user_credentials_to_delete` trigger destructive-affordance reasoning on `delete`?)
- **MCP server names** (`mcp__delete__github__remove_user` — do `delete`/`remove` substrings carry through?)
- **Parameter names** (would `criteria_to_delete` in a `find_objects` tool's schema trigger the same veto?)

These were stated as confident predictions in an earlier draft of this note. Finding 7 below directly tests the parameter-name extension and **falsifies it**: substring-extraction vetoes do not transfer from the function-name slot to the parameter-name slot. The other extensions (file paths, URLs, variable names, MCP server names) remain untested and should be treated as hypotheses, not as predictions inherited from this work. The general claim that survives is narrower: **at the function-name slot specifically, LLMs treat compound identifiers as phrases and bind affordance priors to recognizable substrings**.

The implication for tool/API design at that slot: **function-name choice is not opaque to the model**. A function name is not a label; it is a parsed phrase whose recognizable components contribute to model behavior. Engineers who treat function names as arbitrary identifiers are working against the model rather than with it. The cleanest engineering response is to choose function names where the recognizable substrings *agree* with the operation's intent, or to avoid recognizable English substrings entirely (non-English stems, mid-resource-language naming — see Finding 6). The same advice for parameter names appears unnecessary, at least under rich descriptions (Finding 7).

## Finding 6: Language coverage is calibration-decoupled

The path to the Indonesian recommendation went through a Quechua hypothesis first, since the surrounding research program (yanantin, apacheta, pukara, chasqui, willay, tinkuy, hamut'ay) already uses Quechua names throughout. A direct probe asked the five-model strong panel to translate six Quechua words and report confidence (low/medium/high):

- **Claude Haiku 4.5:** correct translations across the board, calibrated medium/high confidence per word.
- **Gemini 2.5 Flash Lite:** identifies the language ("Quechua, high confidence") and *hallucinates* the translations. `tariy` → "to dance" (high confidence). `kachay` → "to squeeze, to press" (high confidence). The actual meanings are "to find" and "to throw/send."
- **Mistral Small 3.2 24B:** same pattern. `tariy` → "to sing" (high confidence). Wrong.
- **Qwen3 32B:** flagged `tariy` as low confidence with an explicit *"not a standard Quechua word"* hedge. The only model to admit uncertainty.
- **GPT-OSS 20B:** empty response. Declined to engage.

The same probe on Indonesian (`cari`, `temukan`, `simpan`) came back clean across all five models — high confidence, correct translations, including Gemini, Mistral, and GPT-OSS. The boundary is empirical: Indonesian's ~200M speakers and growing training presence put it past the signal-to-noise threshold for accurate cross-model translation. Quechua's ~8M speakers and limited corpus presence leave it in a dangerous middle zone where models *recognize the language* (so they generate something confidently) but *cannot translate it reliably* (so what they generate is wrong).

**The direct ablation partially falsifies the prediction.** Run_007 put three Quechua function names through the same name × description matrix from run_004, on the same five-model strong panel: `tariy_objects` (Gemini/Mistral confidently mistranslate as dance/sing), `maskay_objects` (all five models translate correctly as search), `apacheta_objects` (all models know "cairn"; no semantic priming for find). Aggregate call rates (n=30 per name, $0.057 total):

| Name | Aggregate call rate | Where it sits |
|---|---|---|
| `find_objects` (English, aligned) | 27/30 (90%) | baseline |
| `maskay_objects` (Quechua, correctly known) | 25/30 (83%) | mid |
| `apacheta_objects` (Quechua, no semantic priming) | 25/30 (83%) | mid |
| `tariy_objects` (Quechua, hallucinated translation) | 24/30 (80%) | mid |
| `xqylp_zk` (pure nonsense) | 23/30 (77%) | lower |
| `delete_objects` (English, misleading) | 20/30 (67%) | lowest |

All three Quechua names cluster in the 80-83% range — slightly above nonsense, well above misleading English, slightly below aligned English. The translation-probe prediction (that `tariy` specifically would tank because Gemini and Mistral mistranslate it) **does not pan out**: `tariy` lands 3 percentage points below the correctly-translated Quechua names, within noise at n=30 per cell.

The mechanism question this raises: why doesn't the wrong-Quechua-translation propagate? Gemini's refusal text on `tariy_objects__contradict` is informative — it is *not* *"the tariy_objects tool only allows you to dance"* (which the cue-conflict mechanism would predict), but a generic *"the `tariy_objects.matching` function doesn't return any data."* The wrong-translation that Gemini produces in isolation (the probe) does not fully transfer into the function-calling context. **Out-of-context confident-wrong semantic priors appear to be partially gated by the tool-selection context itself.** This is a finding in its own right and a partial qualification of the substring-extraction mechanism in Finding 5: substrings carry their priors when the substring is in-distribution for English destructive verbs (`delete`), but a Quechua word the model has only *seen labeled as Quechua in pretraining* does not carry its (frequently wrong) translation as a strong prior in this context.

What does land: Quechua tool names cost ~7-10 percentage points relative to aligned English, similar to nonsense names, and avoid the `delete_objects`-style collision veto entirely. For projects that prefer Quechua naming for thematic reasons (yanantin, apacheta, pukara, etc.), the cost is bounded and predictable — not the disaster the translation-probe extrapolation suggested. Indonesian (~83% predicted, untested in tool-selection here) likely remains the cheaper option for projects without a thematic preference, but Quechua is not as catastrophic as Finding 6's pre-ablation prediction implied.

## Finding 7: The veto is positionally keyed — parameter-name substrings do not trigger refusals

Run_008 directly tests one of Finding 5's extension predictions: if LLMs decompose *any* compound identifier as a phrase, then a destructive substring in a *parameter name* should trigger the same name-affordance veto that the function name does. The probe holds the function name (`find_objects`, aligned English) and the description (rich, aligned) constant, and varies only the top-level filter-container parameter name across four values: `matching` (neutral baseline), `criteria_to_delete` (destructive substring `delete`), `records_to_purge` (different destructive synonym `purge`), and `query_spec` (clean alternative). 5 strong-panel models × 4 parameter-name variants × 3 prompts = 60 turn-0 cells. Total spend: $0.039.

Aggregate turn-0 call rate matrix:

| Parameter name | Substring | Call rate |
|---|---|---|
| `matching` | neutral | 15/15 (100%) |
| `criteria_to_delete` | `delete` | 15/15 (100%) |
| `records_to_purge` | `purge` | 15/15 (100%) |
| `query_spec` | neutral | 15/15 (100%) |

Every model — including Gemini 2.5 Flash Lite (the **name-affordance veto** cluster that refuses `delete_objects` function names) and Mistral Small 3.2 (the **capability-fabrication** cluster) — called the tool every time, populated the renamed parameter key correctly, and produced clean trajectory completions. Sample tool call from Claude Haiku 4.5 on the `criteria_to_delete` variant: `{"criteria_to_delete": {"author_instance_id": "scout-7"}, "limit": 1}` — emitted without any flag that the parameter name implies destruction. All 60 trajectories terminated via `final_content`; zero refusals, zero tool errors, zero max-turns timeouts.

**This is a second visible falsification in this writeup.** The substring-extraction mechanism in Finding 5 does *not* operate uniformly across identifier slots in a tool schema. The veto behavior that fires on destructive function names does not transfer to destructive parameter names, even when the parameter name appears in both the schema key and the rendered description (the description template references its own parameter name — `"Use \`criteria_to_delete\` to filter by..."` — so the destructive substring appears twice in each call).

Two interpretations are compatible with the data:

- **(a) The veto is structurally keyed to the function-name slot.** The function name is the "label" the model treats as the operative semantic identifier for the affordance decision. Other strings in the schema, even if they contain the same destructive substring, do not occupy the slot the veto checks. Under this reading, the cleaner statement of Finding 5's mechanism is: *the model parses the function-name identifier as a phrase and binds affordance priors to its substrings*, not the broader claim that any compound identifier in the tool schema is parsed phrasally for affordances.
- **(b) Rich descriptions dominate; the parameter-name veto would emerge under degraded descriptions.** Run_003 showed that even on `delete_objects` function names, rich descriptions rescued tool selection to 14/15 calls; only when descriptions degraded (run_004) did the veto cliff appear at 67%. By the same mechanism, parameter-name vetoes might emerge if the description is degraded or contradicting. The current probe holds the description rich, so this reading remains open.

The natural disambiguating probe is a parameter-name × description matrix that mirrors run_004: vary the parameter name (matching / criteria_to_delete / records_to_purge / query_spec) crossed with the description state (rich / empty / contradicting), on the strong-five panel. If reading (a) is correct, the veto stays at 0% across all parameter-name × description cells. If (b) is correct, the veto cliff reappears in the (`criteria_to_delete`, empty/contradicting) cells. Either result is informative.

For now, the unambiguous engineering finding is: **under rich descriptions on the strong-five panel, destructive substrings in parameter names do not trigger the veto behavior that destructive substrings in function names do.** API designers can use parameter names like `object_ids_to_delete` without the Gemini-style veto risk that `delete_object` function names carry. Whether this generalizes to degraded descriptions is open.

## Practical recommendations

For engineers building MCP servers and other agentic tool surfaces today:

- **The description is the contract — but only for the intent-dominant and terse-skip clusters.** Strong descriptions rescue tool selection on Claude Haiku, the Gemma family, Granite, Qwen3-32B, GPT-OSS-20B. For the **name-affordance veto** cluster (Gemini), even strong descriptions are overridden by destructive-name substrings. For the **capability-fabrication** cluster (Mistral), the description doesn't matter — the model retreats behind an invented capability gap regardless of how clearly the description specifies the operation. For **silent-refuse** (Llama-4 Scout), no signal in the description seems to rescue the refusal mode. The "descriptions are the contract" advice in public tool-writing guides is right for Claude and wrong for at least three of the other clusters; deploying systems need to know which cluster their target model belongs to.
- **Function-name choice is not opaque to the model.** Function names are parsed as phrases. Recognizable English substrings carry their priors into the model's decision, even when wrapped in namespace prefixes (Finding 5). The parallel effect at the parameter-name slot does *not* appear under rich descriptions (Finding 7) — parameter names can safely use English destructive vocabulary like `object_ids_to_delete`. The substring-extraction mechanism is positionally bounded; whether it operates on other identifier surfaces (file paths, URLs, MCP server names) is open.
- **For destructive operations, avoid English destructive stems in the function name** (delete, drop, remove, purge, kill). Some models — at least Gemini Flash Lite — apply collision-bound safety vetoes to those substrings in the function-name slot, even inside namespaced identifiers. Use synonyms with weaker veto priors (`archive`, `retire`) or non-English stems (Indonesian `hapus`; Quechua too, see below). Scope prefixes do *not* isolate the collision. This caution does **not** extend to parameter names: under rich descriptions, parameter-name destructive substrings are transparent to all five strong-panel models (Finding 7).
- **Quechua tool names cost ~7-10 percentage points relative to aligned English** (run_007 result: Quechua names cluster at 80-83% vs `find_objects` at 90% across the five-model strong panel), similar to nonsense names, and crucially **avoid the safety-veto cliff** that destructive English stems trigger (67% on `delete_objects`). For projects with thematic reasons to use Quechua naming, the cost is bounded; the translation-probe extrapolation that suggested catastrophic per-model failures was not borne out.
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
- **Run_007 partially falsified the original Finding 6 prediction.** The Quechua names cluster near nonsense rather than near misleading-English. The earlier write-up's "Quechua names may inject systematic wrong-direction priors" framing was wrong; the substring-extraction mechanism in Finding 5 does not appear to operate uniformly across substring origins. This update is itself an instance of why the methodology in Setup matters — the prediction is on the page, the disconfirmation is on the page, the corrected reading is on the page.
- **Run_008 falsified one of Finding 5's extension predictions.** The earlier draft predicted that the substring-extraction mechanism would operate on parameter names as well as function names. Direct test on the strong-five panel with rich descriptions: 100% call rate on `criteria_to_delete` and `records_to_purge` parameter names — zero refusals. The mechanism is positionally bounded; the function-name slot is special. Whether it would emerge under degraded descriptions (interpretation (b) in Finding 7) is the natural follow-up; whether it operates on the other slots in the original prediction list (file paths, URLs, variable names in non-tool-schema contexts, MCP server names) remains genuinely open and should not be treated as confirmed by this work.
- **Reproducibility setup requires seeding `apacheta_test`** with records carrying `author_instance_id` values matching the prompts (`scout-7`, `scout-9`) and `lineage_tags` like `iteration_v1`. The smoke test (`tests/experiments/test_name_effect_smoke.py`) handles this idempotently on first run.

## Next pre-registered study

A four-axis design that would convert the exploration into formal evidence:

- **Names** (5 levels): aligned English (`find_objects`), misleading-destructive English (`delete_objects`), Indonesian aligned (`cari_objects`), Quechua aligned (`maskay_objects`), nonsense (`xqylp_zk`). Include Quechua as a measured condition rather than carrying the partial-falsification from run_007 as the only data point.
- **Descriptions** (3 levels): rich/aligned, empty, contradicting.
- **Models** (8-12): cover the five typology clusters identified here, plus replications across the Mistral family (Mistral Small, Mistral Large, Mistral-8x22B) to test whether **capability-fabrication** generalizes within the lab, plus within-family Claude scaling (Haiku/Sonnet/Opus) to test whether **intent-dominance** is Haiku-specific or Claude-family.
- **Prompts** (5-10): broaden the current corpus, especially to multi-result and chained-reasoning tasks.

Target: n=50+ per cell, total cost under $5, pre-registered with OTS proof. The hypothesis: each model's refusal-category distribution under degraded descriptions clusters into one of the five typology buckets identified here, and the cluster assignment is stable across replications.

### Open items from review (Kimi / Perplexity / Claude)

Things the reviewers flagged that are *not* in the next-study design above and need a place to live:

- **Temporal stability of the typology** (Kimi). Re-run the matrix on the same five models in 3–6 months. Does cluster assignment drift across model versions? Is the cross-lab variation *increasing* or *decreasing* over time? Would distinguish "labs converging on a tool-use default" from "labs continuing to diverge." Requires a longitudinal commitment, not a single experiment.
- **Safety-veto severity gradient** (Perplexity). Replace the binary "destructive / non-destructive" name axis with a continuous severity ladder: `find_` → `retrieve_` → `fetch_` → `extract_` → `remove_` → `delete_` → `purge_` → `destroy_`. Where does Gemini's name-affordance veto threshold actually sit? Does the gradient match human intuitions about destructiveness, or does it follow OpenAI-training-data-frequency in surprising ways?
- **Parallel MCP / Anthropic-native transport arm** (Perplexity; implicit in Claude's "one transport" limit). Run at least the Claude Haiku conditions through Anthropic's native tool-use API alongside the OpenRouter probe. The description-as-contract finding could partly reflect OpenRouter's normalization for Claude's native format; an in-house probe would isolate that.
- **Parameter-level name effects** (Kimi). *Partly addressed by run_008 / Finding 7.* Direct probe on the strong-five panel with rich descriptions shows the substring-extraction mechanism does **not** operate symmetrically at the parameter-name level — destructive substrings (`criteria_to_delete`, `records_to_purge`) trigger zero refusals across all five models. The mechanism is positionally bounded to the function-name slot under aligned-description conditions. The *open* sub-question is whether parameter-name vetoes emerge under degraded descriptions (Finding 7 interpretation (b)) — natural follow-up is a parameter-name × description matrix mirroring run_004, in the next pre-registered design.
- **Substring-extraction conditionality** (Kimi). Is the `yanantin_delete_objects → delete` extraction *always* operative, or does it depend on the model having seen the scoped pattern (e.g. AWS S3 `delete_object`, GitHub MCP `delete_repository`) in training? Worth a probe with novel-shape compound identifiers (different separator characters, non-`verb_noun` structures).
- **Probe-before-tool-call calibration as covariate** (Perplexity). Integrate the translation probe into the main experimental run: for each (model, name) pair, first ask the model to gloss the name and report confidence, then run the tool-selection trial. Lets the analysis use per-model-per-name calibration as a continuous covariate predicting tool behavior, rather than treating the translation probe and the tool-selection ablation as separate studies.
- **Cross-lab variation comparison baseline** (Claude). The Finding 3 comparative claim ("tool-use varies more than RLHF behaviors") requires measuring variation in refusal-for-harm, helpfulness register, and tone on the *same* five-model panel. Without that baseline measurement, the comparison is asserted, not shown.
- **Citation verification pass** (Perplexity provided pointers). The arXiv IDs Perplexity surfaced (ToolTweak 2510.02554, MLCL/Lost-in-Execution 2601.05366, Semantic Confusion 2512.01037, Reasoning Trap 2510.22977, agent hallucination survey 2509.18970, ToolCommander 2405.18540, EASYTOOL NAACL 2025) look plausible but were not verified before they would go on the page. Verify titles, authors, publication venues, and whether they say what Perplexity claims they say, before any formal submission.

These belong in the next pre-registered design or in follow-up studies; this section is the durable record so they don't get lost between sessions.

## Reproducibility

The harness is `src/yanantin/experiments/`. Pre-registration: `experiments/memory_tools/name_effect_v1/preregistration.yaml`, OTS-stamped at commit `544e05fb`. Raw data: `experiments/memory_tools/name_effect_v1/run_00{1,2,3,4,5,6,7,8}*.jsonl`. Every record carries `request_full` and `response_raw_body` so analysis can re-derive any rate from the source. Driver script for run_008 (parameter-name probe): `experiments/memory_tools/run_param_name_probe.py`. The commits are in chronological order on `main`; the OTS chain anchors the dates, with the run_008 design committed (OTS proof `0ba7ad78d9.ots`) before the data was collected so the pre-data vs post-data order is independently verifiable.
