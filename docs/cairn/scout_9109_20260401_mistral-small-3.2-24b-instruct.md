<!-- Chasqui Scout Tensor
     Run: 9109
     Model: mistralai/mistral-small-3.2-24b-instruct (Mistral: Mistral Small 3.2 24B)
     Cost: prompt=$7.5e-08/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 1061, 'completion_tokens': 774, 'total_tokens': 1835, 'cost': 0.000234375, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.000234375, 'upstream_inference_prompt_cost': 7.9575e-05, 'upstream_inference_completions_cost': 0.0001548}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-01T20:13:10.328452+00:00
     GenerationID: gen-1775074375-JjE9Vz1TTaGX7b3d4Qd5
     Dispatch: verify
     Claim: However, the file content provided clearly shows that `docs/predecessors.md` **is** present and contains detailed information about predecessor projects.
     ClaimFile: docs/predecessors.md
     ClaimBy: qwen/qwen3-coder:exacto
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_2398_20260222_qwen3-coder:exacto.md
-->

### Verdict
**CONFIRMED**

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

### Reasoning
The claim states that `docs/predecessors.md` is present and contains detailed information about predecessor projects. The provided file content clearly shows that the file exists and includes detailed descriptions of several predecessor projects, such as Indaleko, Mallku, ai-honesty, PromptGuard / PromptGuard2, GPN, Lares, and Thesis. Each section provides specific information about the projects, including their purposes, key contributions, and repository locations.

### Declared Losses
There are no declared losses. The claim is fully verifiable based on the provided file content.