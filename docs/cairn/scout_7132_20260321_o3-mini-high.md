<!-- Chasqui Scout Tensor
     Run: 7132
     Model: openai/o3-mini-high (OpenAI: o3 Mini High)
     Cost: prompt=$1.1e-06/M, completion=$4.4e-06/M
     Usage: {'prompt_tokens': 4567, 'completion_tokens': 3687, 'total_tokens': 8254, 'cost': 0.0212465, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0212465, 'upstream_inference_prompt_cost': 0.0050237, 'upstream_inference_completions_cost': 0.0162228}, 'completion_tokens_details': {'reasoning_tokens': 1664, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-21T07:52:54.318257+00:00
     Dispatch: verify
     Claim: **Epistemic Metadata as a Core Model** - **What I saw:** In `src/yanantin/apacheta/models/epistemics.py` (tested in `tests/unit/test_models.py`), there is the `EpistemicMetadata` model.
     ClaimFile: tests/unit/test_models.py
     ClaimBy: ibm-granite/granite-4.0-h-micro
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0444_20260214_granite-4.0-h-micro.md
-->

### Verdict
CONFIRMED

### Evidence
• The file imports EpistemicMetadata:
  "from yanantin.apacheta.models import (
    ApachetaBaseModel,
    BootstrapRecord,
    …,
    EpistemicMetadata,
    KeyClaim,
    …)"
    
• The file contains tests for EpistemicMetadata:
  "class TestEpistemicMetadata:
    def test_neutrosophic_not_constrained(self):
      em = EpistemicMetadata(truth=0.8, indeterminacy=0.6, falsity=0.3)
      ..."
  
### Reasoning
The claim states that the EpistemicMetadata model, originally seen in src/yanantin/apacheta/models/epistemics.py, is tested in tests/unit/test_models.py. In the provided test file, we see that EpistemicMetadata is imported and explicitly tested in a dedicated class (TestEpistemicMetadata) with multiple test methods verifying its behavior. This confirms that the model is indeed treated as a core model and is being exercised by tests, matching the claim.

### Declared Losses
I could not verify the exact source file "src/yanantin/apacheta/models/epistemics.py" since only tests/unit/test_models.py was provided. However, the test file clearly indicates that EpistemicMetadata is expected to be present as part of the models.