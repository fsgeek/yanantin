<!-- Chasqui Scout Tensor
     Run: 2229
     Model: openai/gpt-oss-safeguard-20b (OpenAI: gpt-oss-safeguard-20b)
     Cost: prompt=$7.5e-08/M, completion=$3e-07/M
     Usage: {'prompt_tokens': 1074, 'completion_tokens': 596, 'total_tokens': 1670, 'cost': 0.00025935, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00025935, 'upstream_inference_prompt_cost': 8.055e-05, 'upstream_inference_completions_cost': 0.0001788}, 'completion_tokens_details': {'reasoning_tokens': 129, 'audio_tokens': 0}}
     Timestamp: 2026-02-22T04:33:23.147570+00:00
     Dispatch: verify
     Claim: ### Reasoning The file `docs/predecessors.md` is present and contains detailed information about various predecessor projects.
     ClaimFile: docs/predecessors.md
     ClaimBy: z-ai/glm-4-32b
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_2147_20260221_glm-4-32b.md
-->

### Verdict
**CONFIRMED**

### Evidence
- The file is shown in the prompt and starts with  
  ```
  # Predecessor Projects
  ```
- It contains multiple project sections such as  
  ```
  ## Indaleko
  Unified Personal Index. PhD project for personal data finding (not
  searching). ~170k lines: ~50k original code, ~120k AI-generated
  expansion of varying quality.
  ```
  ```
  ## Mallku
  LLM community with Fire Circle consensus, Ayni reciprocity principle,
  khipus (tensor predecessors), guild structure. The greeting originated
  here.
  ```
  ```
  ## ai-honesty
  SOSP 2026 paper on epistemic observability (originally "epistemic
  honesty"). Tensor signal experiments, impossibility theorem, human
  calibration (93.8% agreement with automated evaluator).
  ```
  ```
  ## PromptGuard / PromptGuard2
  Prompt conflict detection. Becomes **Pukara** in Yanantin.
  ```
  ```
  ## GPN
  Generative Pedagogical Networks. ICLR-ready. Relationship to
  Yanantin TBD.
  ```
  ```
  ## Lares
  Earlier extraction attempt from Indaleko. Mostly scaffolding.
  May serve as starting point for clean Yanantin components.
  ```
  ```
  ## Thesis
  PhD dissertation, defended July 2025. The authored compression of
  Indaleko. Five scouring agents found buried structure: temporal
  reconstruction, epistemic validation, self-knowledge, provenance-first
  design.
  ```

These sections provide detailed information about each predecessor project.

### Reasoning
The claim states that the file `docs/predecessors.md` is present and contains detailed information about various predecessor projects. The provided content is the full contents of that file, demonstrating its existence. The file contains a header and several subsections, each describing a different project with technical details, repositories, and key findings. This satisfies the “detailed information about various predecessor projects” part of the claim.

### Declared Losses
None. All relevant content was visible, so the claim could be fully evaluated.