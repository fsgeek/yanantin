<!-- Chasqui Scout Tensor
     Run: 2453
     Model: openai/gpt-oss-120b:exacto (OpenAI: gpt-oss-120b (exacto))
     Cost: prompt=$3.9e-08/M, completion=$1.9e-07/M
     Usage: {'prompt_tokens': 3101, 'completion_tokens': 984, 'total_tokens': 4085, 'cost': 0.000307899, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.000307899, 'upstream_inference_prompt_cost': 0.000120939, 'upstream_inference_completions_cost': 0.00018696}, 'completion_tokens_details': {'reasoning_tokens': 275, 'audio_tokens': 0}}
     Timestamp: 2026-02-23T04:54:58.686219+00:00
     Dispatch: verify
     Claim: # Verification Assignment ## The Claim Model `google/gemma-3-12b-it` made this claim about `docs/predecessors.md`: > ### Verdict **DENIED** ### Evidence The claim states: "However, it does mention `do
     ClaimFile: docs/predecessors.md
     ClaimBy: qwen/qwen2.5-coder-7b-instruct
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_1374_20260218_qwen2.5-coder-7b-instruct.md
-->

### Verdict
**DENIED**

### Evidence
The full contents of `docs/predecessors.md` are:

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

The tensor sequence (T₀‑T₇) lives in this project's memory directory.

Repository: `/home/tony/projects/ai-honesty`

## PromptGuard / PromptGuard2
Prompt conflict detection. Becomes **Pukara** in Yanantin.

Triple‑layer model: system/domain/unknown. System+domain verified
once, hash cached. Unknown processed against verified structure.
Defense by architecture, not rule‑matching.

PromptGuard2: clean restart with observer framing. 90.4% detection,
0% false positives.

Repositories: `/home/tony/projects/promptguard`, `/home/tony/projects/promptguard2`

## GPN
Generative Pedagogical Networks. ICLR‑ready. Relationship to
Yanantin TBD.

Repository: `/home/tony/projects/gpn`

## Lares
Earlier extraction attempt from Indaleko. Mostly scaffolding.
May serve as starting point for clean Yanantin components.

Repository: `/home/tony/projects/lares`

## Thesis
PhD dissertation, defended July 2025. The authored compression of
Indaleko. Five scouring agents found buried structure: temporal
reconstruction, epistemic validation, self‑knowledge, provenance‑first
design. Three independently found bridges to epistemic observability
without being told about the SOSP paper.

Scour reports preserved in ai‑honesty memory directory.

Repository: `/home/tony/projects/thesis`
```

A search of the file shows **no occurrence** of the phrase “not present” or any statement indicating that `docs/predecessors.md` is missing.

### Reasoning
The claim asserts that the file *mentions* that `docs/predecessors.md` is not present. The actual content of the file contains only project descriptions and repository paths; it never references its own existence or states that it is missing. Therefore the claim is inaccurate, and the appropriate verdict is **DENIED**.

### Declared Losses
None – the entire file content is available for inspection, allowing a definitive assessment.