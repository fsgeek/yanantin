<!-- Chasqui Scout Tensor
     Run: 8184
     Model: alibaba/tongyi-deepresearch-30b-a3b (Tongyi DeepResearch 30B A3B)
     Cost: prompt=$9e-08/M, completion=$4.5e-07/M
     Usage: {'prompt_tokens': 2040, 'completion_tokens': 965, 'total_tokens': 3005, 'cost': 0.00061785, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 6, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00061785, 'upstream_inference_prompt_cost': 0.0001836, 'upstream_inference_completions_cost': 0.00043425}, 'completion_tokens_details': {'reasoning_tokens': 674, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-27T03:57:58.250863+00:00
     GenerationID: gen-1774583870-nqbYmyphWcxLtJWv0s7j
     Dispatch: verify
     Claim: The file `tests/unit/test_operators.py` explicitly tests the operators mentioned in the document.
     ClaimFile: tests/unit/test_operators.py
     ClaimBy: google/gemma-3n-e4b-it
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0418_20260214_gemma-3n-e4b-it.md
-->

### Verdict
INDETERMINATE

### Evidence
The file contains tests for multiple operators:
```python
from yanantin.apacheta.operators.bootstrap import bootstrap
from yanantin.apacheta.operators.compose import compose
from yanantin.apacheta.operators.correct import correct
from yanantin.apacheta.operators.dissent import dissent
from yanantin.apacheta.operators.evolve import evolve
from yanantin.apacheta.operators.negate import negate
from yanantin.apacheta.operators.project import project
```

And corresponding test classes for each operator:
- `TestCompose` for the `compose` operator
- `TestProject` for the `project` operator
- `TestCorrect` for the `correct` operator
- `TestDissent` for the `dissent` operator
- `TestNegate` for the `negate` operator
- `TestBootstrap` for the `bootstrap` operator
- `TestEvolve` for the `evolve` operator

### Reasoning
The file explicitly tests the following operators: bootstrap, compose, correct, dissent, evolve, negate, and project. However, the claim references "the document" without specifying which document. Since I don't have access to the document being referenced in the claim, I cannot verify if the operators mentioned in the document match the operators being tested in this file.

Without knowing what document is being referenced, I cannot confirm or deny the claim definitively. The file itself clearly tests specific operators, but I cannot determine if these exactly match the operators mentioned in the unspecified document.

### Declared Losses
The claim references "the document" but does not specify which document is being discussed. Without access to this document, I cannot make a definitive determination about whether the file tests the operators mentioned in that document.