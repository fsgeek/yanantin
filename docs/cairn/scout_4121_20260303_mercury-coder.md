<!-- Chasqui Scout Tensor
     Run: 4121
     Model: inception/mercury-coder (Inception: Mercury Coder)
     Cost: prompt=$2.5e-07/M, completion=$1e-06/M
     Usage: {'prompt_tokens': 1037, 'completion_tokens': 715, 'total_tokens': 1752, 'cost': 0.00097425, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00097425, 'upstream_inference_prompt_cost': 0.00025925, 'upstream_inference_completions_cost': 0.000715}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-03T02:17:40.992480+00:00
     Dispatch: verify
     Claim: ### Verdict **DENIED** ### Evidence The file `docs/predecessors.md` does not contain the phrase "but it does mention `docs/predecessors.md` is not present." ### Reasoning The claim states that the fil
     ClaimFile: docs/predecessors.md
     ClaimBy: google/gemini-2.5-flash-lite
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_1567_20260219_gemini-2.5-flash-lite.md
-->

### Verdict
**CONFIRMED**

### Evidence
The entire content of `docs/predecessors.md` is shown below (excerpted for brevity). No line contains the exact phrase *“but it does mention `docs/predecessors.md` is not present.”*

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
The claim asserts that the file **does not** contain the specific phrase *“but it does mention `docs/predecessors.md` is not present.”* A thorough scan of the file’s text shows no occurrence of that phrase or any close match. Since the phrase is absent, the claim is accurate.

### Declared Losses
None. The file was fully available and read; no additional context or runtime behavior was required.