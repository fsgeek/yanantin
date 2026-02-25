<!-- Chasqui Scout Tensor
     Run: 2883
     Model: mistralai/mistral-7b-instruct (Mistral: Mistral 7B Instruct)
     Cost: prompt=$2e-07/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 3981, 'completion_tokens': 891, 'total_tokens': 4872, 'cost': 0.0009744, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0009744, 'upstream_inference_prompt_cost': 0.0007962, 'upstream_inference_completions_cost': 0.0001782}, 'completion_tokens_details': {'reasoning_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-02-25T03:35:33.569817+00:00
     Dispatch: verify
     Claim: ### Verdict DENIED ### Evidence The claim states: "However, it does mention `docs/predecessors.md` is not present, but it does mention `docs/predecessors.md` is not present, but it does mention `docs/
     ClaimFile: docs/predecessors.md
     ClaimBy: qwen/qwen-2.5-vl-7b-instruct
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_1544_20260219_qwen-2.5-vl-7b-instruct.md
-->

### Verdict
**DENIED**

### Evidence
The entire file `docs/predecessors.md` reads as follows (no mention of "not present"):

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

### Reasoning
The claim (repeated ad nauseam) states that the file **mentions** `docs/predecessors.md` is "not present." The file does **not** make any such statement. Instead, it provides a detailed list of predecessor projects, explicitly naming `docs/predecessors.md` as a document (not a file) that **describes** the relationships and composition of those projects ("*Yanantin composes what was learned across these projects*"). The file's content is entirely about **describing** the roles of the listed projects, not asserting the absence of itself or any other file.

The claim is **incorrect** and **self-contradictory** because the file:
1. **Does not mention its own absence** (the claim is false).
2. **Does not repeat "is not present"** (the claim misrepresents the content entirely).

### Declared Losses
None — the file is fully readable and clearly contradicts the claim. No external state (e.g., runtime, repository existence beyond the file's content) is required to evaluate this.