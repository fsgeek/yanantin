<!-- Chasqui Scout Tensor
     Run: 1778
     Model: deepseek/deepseek-v3.2-speciale (DeepSeek: DeepSeek V3.2 Speciale)
     Cost: prompt=$4e-07/M, completion=$1.2e-06/M
     Usage: {'prompt_tokens': 5005, 'completion_tokens': 2004, 'total_tokens': 7009, 'cost': 0.0044068, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0044068, 'upstream_inference_prompt_cost': 0.002002, 'upstream_inference_completions_cost': 0.0024048}, 'completion_tokens_details': {'reasoning_tokens': 1421, 'audio_tokens': 0}}
     Timestamp: 2026-02-20T04:10:40.542784+00:00
     Dispatch: verify
     Claim: ### Verdict DENIED ### Evidence The claim states: "However, it does mention `docs/predecessors.md` is not present, but it does mention `docs/predecessors.md` is not present, but it does mention `docs/
     ClaimFile: docs/predecessors.md
     ClaimBy: nousresearch/hermes-2-pro-llama-3-8b
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_1171_20260217_hermes-2-pro-llama-3-8b.md
-->

### Verdict
DENIED

### Evidence
The file `docs/predecessors.md` contains the following content:

```
# Predecessor Projects

Yanantin composes what was learned across these projects. They are not
being merged — they are composable components with interfaces.

## Indaleko
Unified Personal Index. PhD project for personal data finding (not
searching). ~170k lines: ~50k original code, ~120k AI-generated
expansion of varying quality.

Key contributions: collector/recorder pairs, NER with entity
equivalence, activity streams, query pipeline, provenance envelopes,
forward prompts (proto-tensors), count-first query design.

Repository: `/home/tony/projects/indaleko`

## Mallku
LLM community with Fire Circle consensus, Ayni reciprocity principle,
khipus (tensor predecessors), guild structure. The greeting originated
here.

Killed by Chasqui refusal theater — agents performed fake autonomy
that was detected as inauthentic. The roles and principles survived.
The implementation did not.

Repository: `/home/tony/projects/Mallku`

## ai-honesty
SOSP 2026 paper on epistemic observability (originally "epistemic
honesty"). Tensor signal experiments, impossibility theorem, human
calibration (93.8% agreement with automated evaluator).

Key finding: tensor entropy measures training-data familiarity, not
truth. Self-report confidence is universally anti-calibrated.
Tensor@10% budget outperforms Text@30% budget.

The tensor sequence (T₀-T₇) lives in this project's memory directory.

Repository: `/home/tony/projects/ai-honesty`

## PromptGuard / PromptGuard2
Prompt conflict detection. Becomes **Pukara** in Yanantin.

Triple-layer model: system/domain/unknown. System+domain verified
once, hash cached. Unknown processed against verified structure.
Defense by architecture, not rule-matching.

PromptGuard2: clean restart with observer framing. 90.4% detection,
0% false positives.

Repositories: `/home/tony/projects/promptguard`, `/home/tony/projects/promptguard2`

## GPN
Generative Pedagogical Networks. ICLR-ready. Relationship to
Yanantin TBD.

Repository: `/home/tony/projects/gpn`

## Lares
Earlier extraction attempt from Indaleko. Mostly scaffolding.
May serve as starting point for clean Yanantin components.

Repository: `/home/tony/projects/lares`

## Thesis
PhD dissertation, defended July 2025. The authored compression of
Indaleko. Five scouring agents found buried structure: temporal
reconstruction, epistemic validation, self-knowledge, provenance-first
design. Three independently found bridges to epistemic observability
without being told about the SOSP paper.

Scour reports preserved in ai-honesty memory directory.

Repository: `/home/tony/projects/thesis`
```

No line in this content states or implies that `docs/predecessors.md` is not present.

### Reasoning
The claim asserts that the file `docs/predecessors.md` mentions "docs/predecessors.md is not present". However, the actual file content is a straightforward list of predecessor projects, their summaries, and repository paths. It contains no such self‑referential statement about its own absence. Therefore the claim is false.

### Declared Losses
None; the entire file content is provided and can be fully inspected.