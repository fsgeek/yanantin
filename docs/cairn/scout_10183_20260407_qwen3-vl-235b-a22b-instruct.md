<!-- Chasqui Scout Tensor
     Run: 10183
     Model: qwen/qwen3-vl-235b-a22b-instruct (Qwen: Qwen3 VL 235B A22B Instruct)
     Cost: prompt=$2e-07/M, completion=$8.8e-07/M
     Usage: {'prompt_tokens': 2106, 'completion_tokens': 374, 'total_tokens': 2480, 'cost': 0.00075032, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00075032, 'upstream_inference_prompt_cost': 0.0004212, 'upstream_inference_completions_cost': 0.00032912}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-07T18:55:56.545083+00:00
     GenerationID: gen-1775588144-DuMKOm9JfdsMDSrCXXJ1
     Dispatch: verify
     Claim: However, these functions are not explicitly called or referenced in the provided `succession.py` file.
     ClaimFile: src/yanantin/tinkuy/succession.py
     ClaimBy: thedrummer/rocinante-12b
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_4429_20260304_rocinante-12b.md
-->

### Verdict
**DENIED**

### Evidence
The claim states: "However, these functions are not explicitly called or referenced in the provided `succession.py` file."

But in the file, the function `check_succession` explicitly calls:
- `survey_codebase(project_root)` — imported from `yanantin.tinkuy.audit`
- `_extract_blueprint_claims(blueprint_text)` — defined in the same file
- `_compare(claims, report)` — defined in the same file
- `check_orphan_tensors(project_root)` — defined in the same file

Additionally, `check_orphan_tensors` calls:
- `discover_tensors(cairn_dir=cairn_dir, sources=["cairn"])` — imported from `yanantin.awaq.weaver`
- `extract_composition_declarations(tensor.raw_text, tensor.tensor_name)` — imported from `yanantin.awaq.weaver`

All of these are explicitly referenced and called within `succession.py`.

### Reasoning
The claim is false because multiple functions — both internal to the file (`_extract_blueprint_claims`, `_compare`, `check_orphan_tensors`) and imported (`survey_codebase`, `discover_tensors`, `extract_composition_declarations`) — are explicitly called within `succession.py`. The claim suggests no such calls exist, which contradicts the actual code.

The claim may have been referring to some unspecified “these functions” not named in the prompt — but since no specific functions were named, and the file clearly calls several functions (both internal and imported), the claim as stated is inaccurate.

### Declared Losses
None. The claim is about whether functions are called or referenced in the file, and the file content is fully available for inspection. No runtime behavior or external context is needed to evaluate this claim.