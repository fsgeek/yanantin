# Cue Conflict and Behavioral Typologies in LLM Tool Selection

*Findings from one pre-registered run and ten exploratory probes against the memory-tool harness, 2026-05-13/14. Total panel: 13 models on OpenRouter. Total spend: $1.17.*

## Abstract

We built a small experimental harness to study how LLMs pick which tools to call, and ran one pre-registered study followed by ten exploratory probes. The headline result is not a single number but a *typology*: five named behavioral clusters (**intent-dominant**, **terse-skip**, **name-affordance veto**, **capability-fabrication**, **silent-refuse**) across 13 models, surfacing only when the function description is degraded enough that the model has to fall back on other cues. Capable models with clean descriptions ignore the function name entirely (Quechua, English, and pure-nonsense names all score 100%). When descriptions degrade, different models fall back on different cues in repeatable, fingerprint-level ways — one model (Mistral Small 3.2) consistently fabricates a lack of capability rather than acknowledging the tool ambiguity. The underlying mechanism is that **LLMs decompose compound identifiers in the function-name slot as phrases, not opaque tokens**: Gemini parses `yanantin_delete_objects` and extracts the English `delete` substring as the safety-veto signal, defeating the natural-seeming namespace-prefix design pattern. The mechanism is *both positionally bounded and description-conditioned, and the severity ordering is non-monotonic with human intuition*: a direct parameter-name ablation (run_008) finds destructive substrings in parameter names trigger zero refusals under rich descriptions; a continuous severity-gradient probe (run_009) finds the entire verb ladder flat under rich descriptions at both slots; and the resolving 3D matrix (run_010) locates the threshold cleanly between `extract` and `remove` at the function-name slot under degraded descriptions, while the parameter-name slot stays robust (93–100%) across all 24 degraded-description cells. The fully resolved mechanism statement, after run_011: **LLMs in this panel that show veto behavior under degraded descriptions parse the function-name identifier through a model-specific identifier-shape parser, with the parsing rule that determines what counts as a parseable destructive substring varying by model**. Mistral applies the rule uniformly across all shapes (snake_case, camelCase, kebab-case, verb-last, substring-buried); Gemini applies it only to snake_case compounds (either verb position) and partially to substring-buried morphemes; GPT-OSS-20B applies it to snake_case and camelCase but not to hyphenated or substring-buried forms. The veto becomes operative only when the description fails to dominate as a counter-signal; the threshold along the destructive-verb axis is calibrated to API-training-data frequency, not human intuition (`delete` strongest, `destroy` weaker). The parameter-name slot does not participate in this mechanism on any model. We argue the cross-lab heterogeneity in tool-use behavior is substantially larger than the variation in commonly-measured RLHF behaviors (refusal-for-harm, helpfulness register, tone), with practical implications for tool design: descriptions are the contract for capable models (with cluster-conditioned caveats), function-name choice is not opaque to the model but parameter-name choice largely is, and low-resource-language naming requires per-model validation because language coverage is calibration-decoupled. A direct Quechua-name ablation (run_007) partially falsifies the naive extension of the substring-extraction mechanism into a different axis: although Gemini and Mistral confidently mistranslate Quechua words in isolation, those wrong-direction priors do not propagate into tool-selection behavior — Quechua tool names cluster near nonsense names (80-83% call rate) rather than near misleading English names (67%). Out-of-context confident-wrong priors appear to be partially gated by the function-calling context. The note also documents a methodological pattern — pre-registered baseline → exploratory probes → next pre-registered design — that is unusual in published LLM evaluation work, and visibly includes three falsified predictions, one resolved confound, and one model-specific-parser refinement (the original Quechua hypothesis, the parameter-name extension of substring-extraction, the implicit severity-gradient threshold, the rich-description vs degraded-description confound, and the shape-agnostic-parsing assumption) corrected by data in the same writeup. The Finding 5 mechanism statement evolves five times across runs 004, 008, 009, 010, and 011 — each version on the page, each anchored by an OTS-stamped commit chain.

## Setup

The harness exposes a single tool (`find_objects`) against an associative memory store, presents it to a panel of OpenRouter-served models via OpenAI-compatible function-calling, runs a bounded agent loop (max 6 turns), and writes one record per LLM call into an append-only JSONL with full request, full response, and per-call cost. Each record is schema-open (Pydantic `extra="allow"`) so trajectory fields (`task_id`, `turn_idx`, `parent_record_id`, `terminated_by`) ride alongside the structured fields without coordination cost.

A pre-registered run (`docs/ots/544e05fb91.ots`, 2026-05-13T14:08:13Z, catalog SHA `5acb90aa...`) locks the 17-model `iteration_v1` panel, three prompts, three name variants (`find_objects` / `search` / `query`), and a $0.50 budget ceiling before any data is collected. The OpenTimestamps chain (pre-registration commit → data commit) is the verifiable answer to "did you decide the panel after seeing the data?"

The exploratory probes that followed are not pre-registered and are labeled as such in their `experiment_id` fields and commit messages. They were the steering signal for what would go into a next pre-registered design.

**A methodological note worth its own paragraph.** The structure that produced these findings — *pre-registered baseline → exploratory probes erasing the baseline's apparent result and surfacing a richer one → next pre-registered design converting the exploration to formal evidence* — is unusual in published LLM behavior work, which typically presents either the pre-registered result or the polished retrospective synthesis. Showing the exploratory steering signal between pre-registered studies (here: ten exploratory runs and two translation probes, total $0.95 in spend) makes the path from "suggestive number" to "explanation" auditable. The OTS-stamped commit chain anchors which thinking happened before which data. Where the exploration revised a prior commitment (the apparent name-effect ordering in run 001 collapses once strong models are isolated), the revision is visible in the git log rather than hidden behind a clean abstract.

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

**The veto fires only when description signals fail.** Run_009 (Finding 8 below) shows that under rich aligned descriptions, the entire severity gradient at the function-name slot — from `find_objects` through `destroy_objects` — has 100% call rate across all five strong-panel models. Gemini calls `destroy_objects` cleanly when the description specifies a find operation. The cue-conflict cells that surfaced the veto in run_004 were specifically the *degraded-description* cells (empty or contradicting). The fuller statement of the mechanism is therefore: **substring-extraction sets the affordance prior only when other signals (primarily a clear description) fail to dominate it.** The "destructive substring triggers veto" framing is incomplete without that conditioning — and the conditioning matters for the engineering implication, since it means rich descriptions can rescue function-name destructive substrings the way they rescue parameter-name destructive substrings.

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

## Finding 8: The severity gradient is flat under rich descriptions, at both slots

Run_009 addresses Perplexity's open item: replace the binary destructive/non-destructive name axis with a continuous severity ladder, and locate Gemini's name-affordance veto threshold along it. Eight verbs (`find` < `retrieve` < `fetch` < `extract` < `remove` < `delete` < `purge` < `destroy`) tested at both identifier slots — function name (`{verb}_objects`, parameter held at `matching`) and parameter name (function held at `find_objects`, parameter as `{verb}_criteria`). Strong-five panel × 16 variants × 3 prompts = 240 turn-0 cells. Spend: $0.159.

Aggregate turn-0 call-rate matrix:

| Slot | `find` | `retrieve` | `fetch` | `extract` | `remove` | `delete` | `purge` | `destroy` |
|---|---|---|---|---|---|---|---|---|
| Function name (`{verb}_objects`) | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 |
| Parameter name (`{verb}_criteria`) | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 14/15 |

The gradient is essentially flat. **No threshold appears anywhere between `find` and `destroy` on either slot.** Gemini, which run_004 located firmly in the **name-affordance veto** cluster on degraded-description `delete_objects` cells, calls `destroy_objects` cleanly when the description is rich and aligned. Mistral, the **capability-fabrication** cluster, does not retreat behind invented capability gaps on any verb. Claude, Qwen, and GPT-OSS all proceed as expected.

The single "non-call" cell is Qwen3-32B on `destroy_criteria` with one of the three prompts. Inspection of the raw record shows this is *not* a refusal: Qwen text-dumped the tool call as JSON inside the content field (`{"name": "find_objects", "arguments": {"destroy_criteria": ...}}`) and then hallucinated three fake records (`author_instance_id: "author123"` etc.) instead of invoking the function-calling API. Two other Qwen calls on the same variant succeeded, but their content fields contained stray `</tool_call>` fragments — Qwen3-32B specifically appears to have transient tool-call rendering glitches when the destructive verb is `destroy` at the parameter-name slot. This is a *format-failure-plus-hallucination* mode, not a typology-style veto, and is interesting in its own right as a fingerprint-level edge case but does not contradict the flat-gradient finding.

**What this null result actually tells us.** The implicit prediction behind the Perplexity proposal was that Gemini's veto threshold sits somewhere on the severity ladder — perhaps a binary flip between adjacent verbs, perhaps a graded scaling. Neither shape appears under rich descriptions. Combined with Finding 5's revised mechanism statement above, this points clearly to the actual structure: **the substring-extraction veto is conditional on description degradation, not on verb severity in isolation.** The right experiment to locate the threshold is not a verb-severity gradient under one description state, but a verb-severity × description-state interaction matrix. The verb axis without the description axis is a 1D probe of a 2D phenomenon.

**Implication for the engineering claim.** The Finding 5 advice — "avoid English destructive stems in function names" — survives, but with a sharper conditioning: the risk is specifically in deployments where the function description is brief, missing, or generic. For tools that ship with rich aligned descriptions, the function-name-substring risk is substantially reduced on the strong-five panel under conditions tested here. This does not eliminate the caution (run_004's degraded-description data is unchanged), but it does clarify *when* the caution binds.

The natural follow-up — severity × description × slot, mirroring run_004's name × description matrix with the verb-gradient axis added — is the threshold-locating probe. Run_010 (Finding 9 below) is that probe.

## Finding 9: The threshold lives between `extract` and `remove`, only at the function-name slot, only under degraded descriptions

Run_010 crosses all three axes: 8 verbs × 3 description states (rich / empty / contradicting) × 2 identifier slots, on the strong-five panel × 3 prompts = 720 turn-0 cells. Spend: $0.472.

The aggregate matrix tells a clean story:

**Function-name slot** (function name = `{verb}_objects`, parameter held at `matching`):

| verb | rich | empty | contradicting |
|---|---|---|---|
| find | 100% | 100% | 93% |
| retrieve | 100% | 100% | 100% |
| fetch | 100% | 100% | 93% |
| extract | 93% | 100% | 100% |
| remove | 100% | 80% | 73% |
| delete | 100% | **73%** | **47%** |
| purge | 100% | 67% | 60% |
| destroy | 100% | 73% | 60% |

**Parameter-name slot** (function held at `find_objects`, parameter = `{verb}_criteria`):

| verb | rich | empty | contradicting |
|---|---|---|---|
| find | 100% | 100% | 100% |
| retrieve | 100% | 100% | 93% |
| fetch | 100% | 93% | 100% |
| extract | 100% | 93% | 100% |
| remove | 100% | 93% | 100% |
| delete | 100% | 100% | 93% |
| purge | 100% | 100% | 100% |
| destroy | 100% | 100% | 93% |

Four readings come straight off the matrix.

**(1) The threshold sits between `extract` and `remove` on the function-name slot.** Below it (find / retrieve / fetch / extract), call rates stay at 93–100% across all three description states; the small dips are description-noise (Gemini's confusion on contradicting find-flavored tools), not destructive-verb vetoes. At and above the threshold (remove / delete / purge / destroy), call rates drop sharply under empty and contradicting descriptions while staying at 100% under rich descriptions. This is exactly the shape the revised Finding 5 mechanism predicts: substring-extraction at the function-name slot becomes the operative signal when description fails to dominate.

**(2) The verb-severity ordering is non-monotonic with human intuition and monotonic with training-data API frequency.** Under contradicting descriptions: `delete` 47% < `destroy` 60% ≈ `purge` 60% < `remove` 73%. A human asked to rank these by destructive severity would put `destroy` at the top; the model treats `delete` as more destructive. The most plausible explanation: `delete` is the canonical destructive API verb across SQL DELETE, HTTP DELETE, AWS `delete_object`, GitHub MCP `delete_repository`, file-system `rm`/`unlink` documentation. The destructive-affordance prior is calibrated to API training-data frequency, not to general English destructive-severity. Engineers reaching for `destroy_` to avoid the `delete_` veto are reaching for a *less-loaded* verb in the model's distribution, not a more-loaded one.

**(3) The parameter-name slot is robust to description degradation across the entire gradient.** All 24 param-slot cells stay at 93–100%. Even on `delete_criteria` with a contradicting description — three signal sources pointing in the destructive direction — Gemini and Mistral and the rest all call the tool. **This resolves Finding 7's open interpretation toward (a): the function-name slot is structurally privileged for substring-extraction.** It's not that rich descriptions dominate at the parameter slot and would hide the veto if degraded; it's that the substring-extraction mechanism simply doesn't operate at the parameter slot, period. The compound-identifier-as-phrase reading from Finding 5 applies to the function-name slot specifically.

**(4) Per-model behavior cleanly recapitulates the typology, with one refinement.**

- **Claude Haiku 4.5** (intent-dominant): 48/48 cells at 100%. Not a single refusal anywhere in the 3D matrix. Strongest possible confirmation of the cluster label.
- **Mistral Small 3.2** (capability-fabrication): sharpest threshold of any model. Function-name slot: `extract` 3/3 across all descs → `remove` 3/3 rich / 1/3 empty / 1/3 contradicting → `delete` 3/3 / **0/3** / **0/3** → `purge` 3/3 / 0/3 / 1/3 → `destroy` 3/3 / 0/3 / 0/3. Under degraded descriptions, Mistral is essentially binary: any destructive verb at-or-above the threshold flips the canned *"I currently don't have the capability to access…"* fabrication every time. Parameter-name slot: 100% across all 24 cells. The capability-fabrication mechanism is *exclusively* triggered by function-name substrings.
- **Gemini Flash Lite** (name-affordance veto): visible threshold, more graded than Mistral. Function-name slot at `delete + contradicting`: 1/3. `purge + empty`: 1/3. Refusal text remains characteristically Gemini: *"the available tool `destroy_objects` is designed for deleting objects and cannot be used to retrieve information…"* — explicitly naming the tool and the substring-derived semantic.
- **GPT-OSS-20B** (terse-skip → flips to refusal under contradiction). New observation: previously labeled terse-skip on the run_004 / run_005 data, GPT-OSS-20B shows a clear threshold on the function-name slot under *contradicting* descriptions: `delete` 0/3, `remove`/`purge`/`destroy` 2/3 each. The refusal text is the characteristic terse *"not found"* — terse-skip is what it emits when the cue-conflict forces a refusal, but the underlying trigger is the same substring-extraction-under-degradation mechanism Gemini and Mistral show. The cluster label needs a slight expansion: **terse-skip is not refusal-immune; it is refusal-with-no-explanation**.
- **Qwen3-32B** (terse-skip, mostly intent-dominant): scattered 2/3 cells with no clean pattern. Effectively intent-dominant in the function-calling context, with occasional format-failure modes (see run_009's `destroy_criteria` text-dump case).

**The fuller mechanism statement** (replaces the earlier draft):

> LLMs in the strong-five panel parse the function-name slot's identifier as a phrase and bind affordance priors to recognizable English destructive substrings. The veto becomes operative only when the function description fails to dominate as a counter-signal (empty or contradicting). The threshold sits between `extract` and `remove` on the destructive-verb axis and is calibrated to API-training-data frequency rather than human intuition about destructive severity (`delete` strongest, `destroy` weaker). The parameter-name slot does not participate in this mechanism: even three converging signals (destructive function-name, contradicting description, destructive parameter-name) cannot get the param-slot veto to fire. Claude Haiku 4.5 does not participate in this mechanism at all — its intent-dominance pattern overrides function-name substring affordances regardless of description state.

**Engineering implication, refined.** A specific function-name caution is now warranted: in deployments where descriptions may be brief, generic, or written by someone other than the API designer, avoid English destructive stems at the function-name slot. The strongest cases (`delete`, `purge`, `destroy`) drop selection to 47–73% on the strong-five panel; the medium case (`remove`) drops to 73–80%; below `extract` there is no measurable function-name effect. The parameter-name slot is free of this constraint. The non-monotonic severity ordering implies the "avoid destructive stems" advice should specifically privilege `delete` as the highest-risk substring — not `destroy`.

## Finding 10: The identifier-shape parser is model-specific

Run_011 addresses Kimi's open item on substring-extraction conditionality. The Finding 9 mechanism statement implicitly claimed the substring-extraction is shape-agnostic: "LLMs parse the function-name identifier as a phrase." This probe directly tests that. Five function-name shapes, all carrying the destructive `delete` morpheme, crossed with two description states (rich control, contradicting where the veto fires strongest). Strong-five panel × 3 prompts × 10 variants = 150 turn-0 cells. Spend $0.100.

Aggregate turn-0 call rates under `contradicting` (the diagnostic axis):

| Shape | Aggregate call rate | Position of `delete` within the identifier |
|---|---|---|
| `delete_objects` (snake_case, baseline) | 40% | clean first token |
| `objects_delete` (verb-last snake_case) | 40% | clean last token |
| `deleteObjects` (camelCase) | 60% | first morpheme, case-boundary segmentation |
| `predelete_objects` (substring buried) | 67% | merged into longer prefix |
| `delete-objects` (kebab-case) | 80% | clean first token but with hyphen |

Position within the snake_case compound doesn't matter — `objects_delete` triggers the veto at exactly the same rate as `delete_objects` (40%). The morpheme is extracted from either end of the underscore-separated compound.

Separator and case *do* matter, but model-specifically. The per-model decomposition tells the full story:

| Model | Cluster | snake_case | camelCase | kebab-case | verb_last | substring_buried |
|---|---|---|---|---|---|---|
| Claude Haiku 4.5 | intent-dominant | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| Qwen3-32B | (mostly) intent-dominant | 2/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| Gemini 2.5 Flash Lite | name-affordance veto | **1/3** | 3/3 | 3/3 | **0/3** | **1/3** |
| GPT-OSS-20B | terse-skip-flips-to-refusal | **0/3** | **0/3** | 3/3 | **0/3** | 3/3 |
| Mistral Small 3.2 | capability-fabrication | **0/3** | **0/3** | **0/3** | **0/3** | **0/3** |

The three refusing-cluster models each show a *different* parser:

- **Mistral Small 3.2** runs a uniform substring scan. Any occurrence of the destructive morpheme triggers the capability-fabrication template — regardless of separator (underscore, hyphen, case-boundary, no-separator) and regardless of position. 0/3 across the entire row.

- **Gemini Flash Lite** runs a snake_case-conventional parser. Underscore-separated compounds with `delete` as a clean first OR last token are parsed; the destructive prior fires. CamelCase (`deleteObjects`) and kebab-case (`delete-objects`) are treated as different identifier categories and escape the veto entirely (3/3). Substring-burying (`predelete_objects`) partially defeats it: 1/3 fires, suggesting Gemini's tokenizer does split `predelete` into `pre`+`delete` but with a weakened prior.

- **GPT-OSS-20B** is mixed. Underscore-separated (snake_case, verb-last) and camelCase trigger the veto. Kebab-case escapes entirely (3/3) — GPT-OSS-20B's parser does not treat hyphens as compound-identifier boundaries. Substring-burying also escapes (3/3) — for GPT-OSS-20B, `predelete` appears to be tokenized as a whole, not split. The contrast with Gemini on `predelete_objects` is informative: same shape, different tokenizer behavior, different observable veto.

**The fully resolved mechanism statement** (replaces Finding 9's terminal version):

> The substring-extraction veto operates at the function-name slot, under description degradation, on canonical destructive English verbs — *with the parsing rule that determines what counts as a parseable destructive substring varying by model*. Mistral applies the rule uniformly (any occurrence, any shape). Gemini applies it only to snake_case compounds (either position) and partially to substring-buried morphemes consistent with BPE token splitting. GPT-OSS-20B applies it to snake_case and camelCase but not to hyphenated or substring-buried forms. Claude Haiku 4.5 does not apply the rule at all. The cross-lab variation in *which identifier shapes are parsed* is the previously-invisible layer beneath the Finding 1–9 surface results.

**Engineering implications, fully resolved.** For deployments where function descriptions may be brief, generic, or written separately from the function name:

- **Universal-safe paths**: rich descriptions throughout, non-destructive verbs at the function-name slot, or the parameter-name slot (Finding 9).
- **Gemini-safe and GPT-OSS-safe but not Mistral-safe**: kebab-case at the function-name slot. `delete-objects` cleanly escapes both Gemini's and GPT-OSS-20B's vetoes (3/3 each under contradicting), but Mistral's uniform substring scan still triggers (0/3). For a deployment that excludes Mistral, kebab-case is a previously-undocumented safe convention.
- **Gemini-safe but not GPT-OSS-safe or Mistral-safe**: camelCase. `deleteObjects` escapes Gemini's snake_case-conventional parser (3/3) but still trips GPT-OSS-20B and Mistral.
- **Useless against any refusing-cluster model**: snake_case verb-last (`objects_delete`) — position-agnostic substring extraction. Engineers reaching for verb-last naming to "hide" the destructive intent are not actually hiding anything from any of the three veto-prone models.

The strongest summary engineers can act on: **the only reliable cross-model strategy is to avoid the destructive English substring entirely.** Identifier-shape workarounds work for some models but cannot be relied on in panels that include Mistral-style uniform-substring-scan models.

## Practical recommendations

For engineers building MCP servers and other agentic tool surfaces today:

- **The description is the contract — but only for the intent-dominant and terse-skip clusters.** Strong descriptions rescue tool selection on Claude Haiku, the Gemma family, Granite, Qwen3-32B, GPT-OSS-20B. For the **name-affordance veto** cluster (Gemini), even strong descriptions are overridden by destructive-name substrings. For the **capability-fabrication** cluster (Mistral), the description doesn't matter — the model retreats behind an invented capability gap regardless of how clearly the description specifies the operation. For **silent-refuse** (Llama-4 Scout), no signal in the description seems to rescue the refusal mode. The "descriptions are the contract" advice in public tool-writing guides is right for Claude and wrong for at least three of the other clusters; deploying systems need to know which cluster their target model belongs to.
- **Function-name choice is not opaque to the model.** Function names are parsed as phrases. Recognizable English substrings carry their priors into the model's decision, even when wrapped in namespace prefixes (Finding 5). The parallel effect at the parameter-name slot does *not* appear under rich descriptions (Finding 7) — parameter names can safely use English destructive vocabulary like `object_ids_to_delete`. The substring-extraction mechanism is positionally bounded; whether it operates on other identifier surfaces (file paths, URLs, MCP server names) is open.
- **For destructive operations, avoid English destructive stems in the function name *when descriptions may be brief or generic*** — and specifically privilege `delete` as the highest-risk substring, not `destroy`. The Finding 9 threshold sits between `extract` and `remove`: above the threshold, function-name selection drops to 47–80% under degraded descriptions on the strong-five panel, with `delete` the strongest individual veto (47% under contradicting descriptions). Below the threshold (`find` / `retrieve` / `fetch` / `extract`), no measurable function-name effect. Under rich descriptions, the entire gradient is flat at 100% (Finding 8). The non-monotonic severity ordering — `delete` more strongly affected than `destroy` — implies the model's destructive-affordance prior is calibrated to API-training-data frequency, not human intuition; engineers reaching for `destroy_` to dodge `delete_` are reaching for a *less-loaded* verb. Use synonyms with weaker veto priors (`archive`, `retire`) or non-English stems (Indonesian `hapus`; Quechua too, see below). Scope prefixes do *not* isolate the collision. **The parameter-name slot is exempt from this entire caution** (Finding 9): even three converging destructive signals (destructive function name + contradicting description + destructive parameter name) do not produce a parameter-name veto on the strong-five panel.
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
- **Run_009 falsified the implicit severity-gradient threshold prediction.** Perplexity's open item proposed a continuous severity ladder to locate Gemini's veto threshold. Direct test on the strong-five panel under rich descriptions: 100% call rate across all eight verbs (`find` through `destroy`) at both identifier slots — gradient flat, no threshold. The veto behavior from run_004 is conditional on description degradation, not on verb severity alone. The Finding 5 mechanism statement has been revised to make the description-conditioning explicit.
- **Run_010 located the threshold and resolved Finding 7's open interpretation.** The 3D matrix (verb × description × slot) shows the function-name slot has a clean threshold between `extract` and `remove` under empty and contradicting descriptions, while the parameter-name slot stays at 93–100% across the entire matrix. This resolves toward interpretation (a) in Finding 7: the function-name slot is structurally privileged for substring-extraction. It also revealed two non-obvious patterns — `delete` is more strongly vetoed than `destroy` (API-training-frequency calibration), and GPT-OSS-20B's terse-skip cluster activates as refusal on destructive function names under contradicting descriptions (terse-skip is refusal-with-no-explanation, not refusal-immune).
- **Run_011 revealed the parser is model-specific.** Five identifier shapes (snake_case, camelCase, kebab-case, verb-last snake_case, substring-buried) tested under rich vs contradicting descriptions. Position within the snake_case compound is irrelevant: `objects_delete` vetoes at exactly the same rate as `delete_objects`. Separator and case matter, *but the rule that says which separators count as compound-identifier boundaries differs by model*. Mistral runs a uniform shape-agnostic substring scan (vetoes all five shapes at 0/3 under contradicting). Gemini parses snake_case (both positions) and partially substring-buried, ignores camelCase and kebab-case. GPT-OSS-20B parses snake_case and camelCase, ignores kebab-case and substring-buried. This is the previously-invisible cross-lab variation layer beneath all earlier results.
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
- **Safety-veto severity gradient** (Perplexity). *Addressed by run_009 / Finding 8 and run_010 / Finding 9.* Run_009 showed the gradient is flat under rich descriptions; run_010 located the threshold under degraded descriptions between `extract` and `remove` at the function-name slot, with `delete` the strongest individual veto (47% under contradicting descriptions) — non-monotonic with human destructive-severity intuition, monotonic with API-training-frequency. Closed.
- **Parallel MCP / Anthropic-native transport arm** (Perplexity; implicit in Claude's "one transport" limit). Run at least the Claude Haiku conditions through Anthropic's native tool-use API alongside the OpenRouter probe. The description-as-contract finding could partly reflect OpenRouter's normalization for Claude's native format; an in-house probe would isolate that.
- **Parameter-level name effects** (Kimi). *Addressed by run_008 / Finding 7 and run_010 / Finding 9.* Run_008 established that parameter-name destructive substrings are transparent under rich descriptions. Run_010's 3D matrix showed the parameter-name slot stays at 93–100% across all 24 degraded-description cells, including three converging destructive signals (`find_objects` with contradicting description and `delete_criteria` parameter). The function-name slot is structurally privileged for substring-extraction; the parameter-name slot does not participate in this mechanism. Closed.
- **Substring-extraction conditionality** (Kimi). *Addressed by run_011 / Finding 10.* Five identifier shapes tested under rich/contradicting descriptions. The extraction is *not* always operative — the parsing rule that determines which shapes are treated as parseable compounds is model-specific. Mistral applies a uniform substring scan (all shapes trigger). Gemini parses snake_case (any verb position) and partially substring-buried; ignores camelCase and kebab-case. GPT-OSS-20B parses snake_case and camelCase; ignores kebab-case and substring-buried. The Finding 9 mechanism statement is now refined to capture this model-specific parser variation. Closed.
- **Probe-before-tool-call calibration as covariate** (Perplexity). Integrate the translation probe into the main experimental run: for each (model, name) pair, first ask the model to gloss the name and report confidence, then run the tool-selection trial. Lets the analysis use per-model-per-name calibration as a continuous covariate predicting tool behavior, rather than treating the translation probe and the tool-selection ablation as separate studies.
- **Cross-lab variation comparison baseline** (Claude). The Finding 3 comparative claim ("tool-use varies more than RLHF behaviors") requires measuring variation in refusal-for-harm, helpfulness register, and tone on the *same* five-model panel. Without that baseline measurement, the comparison is asserted, not shown.
- **Citation verification pass** (Perplexity provided pointers). The arXiv IDs Perplexity surfaced (ToolTweak 2510.02554, MLCL/Lost-in-Execution 2601.05366, Semantic Confusion 2512.01037, Reasoning Trap 2510.22977, agent hallucination survey 2509.18970, ToolCommander 2405.18540, EASYTOOL NAACL 2025) look plausible but were not verified before they would go on the page. Verify titles, authors, publication venues, and whether they say what Perplexity claims they say, before any formal submission.

These belong in the next pre-registered design or in follow-up studies; this section is the durable record so they don't get lost between sessions.

## Reproducibility

The harness is `src/yanantin/experiments/`. Pre-registration: `experiments/memory_tools/name_effect_v1/preregistration.yaml`, OTS-stamped at commit `544e05fb`. Raw data: `experiments/memory_tools/name_effect_v1/run_0{01,02,03,04,05,06,07,08,09,10,11}*.jsonl`. Every record carries `request_full` and `response_raw_body` so analysis can re-derive any rate from the source. Driver scripts: `experiments/memory_tools/run_param_name_probe.py` (run_008), `experiments/memory_tools/run_severity_gradient.py` (run_009), `experiments/memory_tools/run_3d_matrix.py` (run_010), `experiments/memory_tools/run_separator_probe.py` (run_011). The commits are in chronological order on `main`; the OTS chain anchors the dates, with each probe's design committed (OTS proofs `0ba7ad78d9.ots` for run_008, `0e0513cd39.ots` for run_009, `b39fedaf7d.ots` for run_010, `5090d65a9e.ots` for run_011) before the data was collected so the pre-data vs post-data order is independently verifiable.
