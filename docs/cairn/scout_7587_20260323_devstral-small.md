<!-- Chasqui Scout Tensor
     Run: 7587
     Model: mistralai/devstral-small (Mistral: Devstral Small 1.1)
     Cost: prompt=$1e-07/M, completion=$3e-07/M
     Usage: {'prompt_tokens': 1113, 'completion_tokens': 341, 'total_tokens': 1454, 'cost': 0.0002136, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0002136, 'upstream_inference_prompt_cost': 0.0001113, 'upstream_inference_completions_cost': 0.0001023}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-23T19:11:17.633242+00:00
     GenerationID: gen-1774293073-I7czJl0vYatVdMiB7Z8M
     Dispatch: verify
     Claim: #### Strand 2: Verification of `docs/cairn/T14_20260211_the_flatworm.md` and `tests/red_bar/test_provenance.py` The previous scout's tensor reports that the file `docs/cairn/T14_20260211_the_flatworm.
     ClaimFile: tests/red_bar/test_provenance.py
     ClaimBy: meta-llama/llama-3.2-3b-instruct
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0273_20260213_llama-3.2-3b-instruct.md
-->

### Verdict
**CONFIRMED**

### Evidence
The file `tests/red_bar/test_provenance.py` contains the following lines:

- Line 1: `"""Red-bar test: Provenance invariant.`
- Line 2: `Every record has provenance. This is structural, not optional.`

Additionally, the file includes multiple test functions that verify the presence of `ProvenanceEnvelope` in various record types, such as:

- Line 12: `assert isinstance(tensor.provenance, ProvenanceEnvelope)`
- Line 20: `assert isinstance(edge.provenance, ProvenanceEnvelope)`
- Line 28: `assert isinstance(corr.provenance, ProvenanceEnvelope)`
- Line 36: `assert isinstance(d.provenance, ProvenanceEnvelope)`
- Line 44: `assert isinstance(n.provenance, ProvenanceEnvelope)`
- Line 52: `assert isinstance(b.provenance, ProvenanceEnvelope)`
- Line 60: `assert isinstance(e.provenance, ProvenanceEnvelope)`
- Line 68: `assert isinstance(e.provenance, ProvenanceEnvelope)`

### Reasoning
The evidence supports the verdict because the file explicitly mentions "provenance" in its docstring and includes multiple test functions that check for the presence of `ProvenanceEnvelope` in different record types. This confirms that the file emphasizes provenance tracking and structural invariants, as claimed.

### Declared Losses
None. The claim is fully verifiable based on the provided file content.