<!-- Chasqui Scout Tensor
     Run: 8357
     Model: mistralai/mistral-nemo (Mistral: Mistral Nemo)
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 680, 'completion_tokens': 155, 'total_tokens': 835, 'cost': 5.355e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 5.355e-05, 'upstream_inference_prompt_cost': 2.72e-05, 'upstream_inference_completions_cost': 2.635e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-28T02:55:33.093600+00:00
     GenerationID: gen-1774666530-0tIyB8RJVQOrrZe9gciL
     Dispatch: verify
     Claim: `bootstrap.py` and `evolve.py` indicate a decoupled approach, allowing for context-bound selections and schema migrations.
     ClaimFile: src/yanantin/apacheta/operators/evolve.py
     ClaimBy: openai/gpt-4o-2024-08-06
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0400_20260214_gpt-4o-2024-08-06.md
-->

### Verdict
DENIED

### Evidence
In the provided `evolve.py` file, there is no mention of `bootstrap.py`, nor any indication of a decoupled approach or schema migrations.

### Reasoning
The claim suggests a connection between `bootstrap.py` and `evolve.py`, implying some form of decoupled approach and schema migrations. However, the given `evolve.py` file does not reference `bootstrap.py` and does not contain any code related to schema migrations or context-bound selections. It only defines a function `evolve` that records a schema evolution step.

### Declared Losses
I cannot determine the content or purpose of the `bootstrap.py` file, as it is not provided in this context.