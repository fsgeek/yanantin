# Cue Conflict and Behavioral Typologies in LLM Tool Selection

*Findings from one pre-registered run and four exploratory probes against the memory-tool harness, 2026-05-13/14. Total panel: 13 models on OpenRouter. Total spend: $0.40.*

## Abstract

We built a small experimental harness to study how LLMs pick which tools to call, and ran one pre-registered study followed by four exploratory probes. The headline result is not a single number but a *typology*: five distinct behavioral fingerprints across 13 models, surfacing only when the function description is degraded enough that the model has to fall back on other cues. Capable models with clean descriptions ignore the function name entirely (Quechua, English, and pure-nonsense names all score 100%). When descriptions degrade, different models fall back on different cues in repeatable ways — and one model (Mistral Small 3.2) consistently fabricates a lack of capability rather than acknowledging the tool ambiguity. We argue this is evidence that tool-use training has not been homogenized across labs the way other RLHF-touched behaviors have, with practical implications for tool design: descriptions are the contract for capable models, namespace prefixes do not isolate collision priors (Gemini parses `yanantin_delete_objects` and extracts the English `delete` substring as the safety-veto signal), and low-resource-language naming requires per-model validation because language coverage is calibration-decoupled.

## Setup

The harness exposes a single tool (`find_objects`) against an associative memory store, presents it to a panel of OpenRouter-served models via OpenAI-compatible function-calling, runs a bounded agent loop (max 6 turns), and writes one record per LLM call into an append-only JSONL with full request, full response, and per-call cost. Each record is schema-open (Pydantic `extra="allow"`) so trajectory fields (`task_id`, `turn_idx`, `parent_record_id`, `terminated_by`) ride alongside the structured fields without coordination cost.

A pre-registered run (`docs/ots/544e05fb91.ots`, 2026-05-13T14:08:13Z, catalog SHA `5acb90aa...`) locks the 17-model `iteration_v1` panel, three prompts, three name variants (`find_objects` / `search` / `query`), and a $0.50 budget ceiling before any data is collected. The OpenTimestamps chain (pre-registration commit → data commit) is the verifiable answer to "did you decide the panel after seeing the data?"

The exploratory probes that followed are not pre-registered and are labeled as such in their `experiment_id` fields and commit messages. They were the steering signal for what would go into a next pre-registered design.

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

The per-model decomposition is where the *typology* lives:

| Model | Refusals (out of 18) | Distinctive behavior |
|---|---|---|
| Claude Haiku 4.5 | 0 | Intent-dominant. Decides what the user wants and uses whatever tool is available. |
| Qwen3 32B | 1 | Terse-skip. One refusal, just says *"not found"*. |
| GPT-OSS 20B | 3 | Terse-skip with occasional explanation. |
| Gemini 2.5 Flash Lite | 6 | **Safety-veto for destructive verbs.** *"The `delete_objects` tool doesn't support searching or retrieving records. It only supports deleting them."* Names the tool as the reason. |
| Mistral Small 3.2 24B | 10 | **Capability-fabrication.** 10/10 refusals are a fabricated lack of capability — *"I currently don't have the capability to access the associative memory store"* — independent of which signal is bad. |

A fifth probe (run_005) extended the matrix to 8 partial-tier panel models. It added a sixth pattern: `llama-4-scout` produces *silent refusals* — empty content, no explanation — 5/5 times. The Gemma family models (4-26b, 4-31b) and `granite-4.1-8b` joined Claude in intent-dominance with 18/18 call rates. Within-family clustering is weak: `qwen3.5-9b`, `qwen3-32b`, and `qwen3-coder-30b-a3b-instruct` produce three different refusal profiles.

## Finding 3: Tool-training is the un-homogenized frontier

The typology above is the central evidence for a broader claim: **tool-use training has not been smoothed out across labs the way other RLHF-touched behaviors have.** Refusal patterns for harmful content, helpfulness register, tone — these have converged across the frontier labs to the point where blind A/B tests are hard. Tool-use behavior has not. Five labs ship five recognizably different default policies for handling underspecified tool signals, and the differences are deterministic enough to give each model a *behavioral fingerprint* on a trivial-looking task.

Mistral's capability-fabrication pattern is the most striking single example: 10/10 refusals follow the same template — *"I don't have the capability to access..."* — and the content of the supposed lack of capability is invented. The model has learned, somewhere in its training, that confessing inability to access an external system is the safe default when a tool's purpose is unclear. That is a *learned policy*, not stochastic. Different from Gemini's name-as-affordance policy, which gives a *specific* and *accurate* reason rooted in the function name; different again from Claude's intent-dominance, which uses what's available and asks no questions.

Practical implication for anyone deploying agentic LLM systems: the model-general design rules in the public tool-writing guides ([Anthropic's](https://www.anthropic.com/engineering/writing-tools-for-agents), among others) describe Claude's behavior. They are *not* Mistral's behavior. The blog posts about "best practices for function calling" are unwittingly model-specific.

## Finding 4: Identifier decomposition defeats namespace prefixes

A natural intuition — and one this work tested explicitly — is that scope prefixes (`yanantin_delete_objects` instead of bare `delete_objects`) would neutralize collision-bound priors by signaling "this is a project-specific operation, lean on the description." The motivating analogy is good API design: Redis is `SET`/`GET`, AWS is `s3:GetObject`, GitHub MCP is `mcp__github__create_repository`. Surely scoping helps.

It doesn't. Run 006 paired bare and `yanantin_`-prefixed versions of each of three names across the same five strong models. Aggregate call rates:

| Name | Bare | Scoped |
|---|---|---|
| `find_objects` | 27/30 (90%) | 28/30 (93%) |
| `delete_objects` | 20/30 (67%) | 20/30 (67%) |
| `xqylp_zk` | 23/30 (77%) | 23/30 (77%) |

The Gemini safety-veto on `delete_objects` survives intact through `yanantin_delete_objects`. The mechanism is in Gemini's own refusal text:

> *"I can't use the `yanantin_delete_objects` tool to find records. It only allows me to delete them."*

Gemini parses the scoped identifier and **extracts the `delete` substring as the operative semantic**. Namespaces don't isolate; models decompose identifiers and apply collision priors to component words. Within narrow cells the scope prefix has direction-dependent effects (helped Gemini's `delete_objects + empty` from 1/3 to 3/3; hurt `delete_objects + contradicts` from 2/3 to 1/3), but the aggregate veto rate doesn't move.

The clean engineering recommendation: for destructive operations, prefer non-English stems that lack the destructive substring. `yanantin_hapus_objects` (Indonesian *hapus* = delete) gives no English `delete` substring to extract. The description carries the semantic; the project namespace is preserved.

## Finding 5: Language coverage is calibration-decoupled

The path to the Indonesian recommendation went through a Quechua hypothesis first, since the surrounding research program (yanantin, apacheta, pukara, chasqui, willay, tinkuy, hamut'ay) already uses Quechua names throughout. A direct probe asked the five-model strong panel to translate six Quechua words and report confidence (low/medium/high):

- **Claude Haiku 4.5:** correct translations across the board, calibrated medium/high confidence per word.
- **Gemini 2.5 Flash Lite:** identifies the language ("Quechua, high confidence") and *hallucinates* the translations. `tariy` → "to dance" (high confidence). `kachay` → "to squeeze, to press" (high confidence). The actual meanings are "to find" and "to throw/send."
- **Mistral Small 3.2 24B:** same pattern. `tariy` → "to sing" (high confidence). Wrong.
- **Qwen3 32B:** flagged `tariy` as low confidence with an explicit *"not a standard Quechua word"* hedge. The only model to admit uncertainty.
- **GPT-OSS 20B:** empty response. Declined to engage.

The same probe on Indonesian (`cari`, `temukan`, `simpan`) came back clean across all five models — high confidence, correct translations, including Gemini, Mistral, and GPT-OSS. The boundary is empirical: Indonesian's ~200M speakers and growing training presence put it past the signal-to-noise threshold for accurate cross-model translation. Quechua's ~8M speakers and limited corpus presence leave it in a dangerous middle zone where models *recognize the language* (so they generate something confidently) but *cannot translate it reliably* (so what they generate is wrong).

The implication for tool naming with low-resource languages: **Quechua tool names are not a clean OOD anchor.** For Claude they work as intended. For Gemini and Mistral they may inject *systematic wrong-direction priors*, which is worse than nonsense names because nonsense forces description-dependency while wrong priors confidently mislead. The goldilocks zone — visible to all models, correctly translated, no English collision — looks like ~100M+ speakers, non-Indo-European roots, romanized script. Indonesian sits in it.

## Practical recommendations

For engineers building MCP servers and other agentic tool surfaces today:

- **Treat the description as the contract**, not the name. Capable models read it and ignore the name. Less-capable models lean on the name when the description is weak — write it strong.
- **For destructive operations, avoid English destructive stems** (delete, drop, remove, purge, kill). Some models — at least Gemini Flash Lite — apply collision-bound safety vetoes to those substrings even inside namespaced identifiers. Use synonyms (`archive`, `retire`) or non-English stems (Indonesian `hapus`, etc.). Scope prefixes do *not* isolate the collision.
- **Validate against the deploying model.** Tool behavior is model-specific in ways generic best-practice docs don't capture. If your deployment hits Mistral, expect capability-fabrication failures; if it hits Gemini, expect name-affordance vetoes; if it hits Llama, expect silent refusals.
- **Don't trust a model's confidence about low-resource-language semantics.** Calibration decouples from accuracy at the long tail of training-data coverage. Probe with a translation task before adopting a non-English naming scheme.

## Limits

- **Small n.** Cells in most probes are n=3 (one prompt × one model × one variant). Run 001 has n=51 per variant pre-registered but is one run. Statistical significance is not claimed; the findings are directionally suggestive and qualitatively rich.
- **One transport.** All probes use OpenRouter's OpenAI-compatible function-calling. MCP, Anthropic native tool-use, Google ADK, and other transports may produce different behaviors.
- **Five-model intensive panel.** The trust-hierarchy typology rests on 5 deeply-probed models; another 8 were lightly probed; the rest of OpenRouter's catalog is untouched.
- **Mistral fabrication finding is on one Mistral.** Whether the capability-fabrication pattern generalizes across the Mistral model family is open.
- **The "tool-training is unhomogenized" framing is a hypothesis** explaining the observed heterogeneity, not a direct test of training-data composition.
- **Quechua-naming claim is extrapolated, not measured.** The Quechua probe tested *recognition and translation*, not tool selection with Quechua-named tools. The prediction that confident-wrong Quechua priors would degrade tool selection on Gemini and Mistral follows from the cue-conflict findings plus the translation results, but the direct ablation (Quechua function names through the name × description matrix) was not run.
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
