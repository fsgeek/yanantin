<!-- Chasqui Scout Tensor
     Run: 11046
     Model: meta-llama/llama-3-8b-instruct (Meta: Llama 3 8B Instruct)
     Cost: prompt=$3e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 1861, 'completion_tokens': 254, 'total_tokens': 2115, 'cost': 8.46e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 8.46e-05, 'upstream_inference_prompt_cost': 7.444e-05, 'upstream_inference_completions_cost': 1.016e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-12T12:22:08.697051+00:00
     GenerationID: gen-1775996525-gEgHRegkgnooJZr88bXe
     Dispatch: verify
     Claim: From the file `src/yanantin/apacheta/backends/arango.py`, we see the following relevant section: ``` """ ArangoDB backend for Apacheta.
     ClaimFile: src/yanantin/apacheta/backends/arango.py
     ClaimBy: liquid/lfm-2-24b-a2b
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_4952_20260307_lfm-2-24b-a2b.md
-->

### Verdict
**CONFIRMED**

### Evidence
The evidence that supports the claim is found in the following lines:

* `# ── Collection names ──────────────────────────────────────────────────`: This line indicates that the collections used in the ArangoDB backend are named semantically, such as "tensors", "composition_edges", "corrections", etc.
* `self._map = obfuscator or TransparentObfuscator()`: This line shows that the `obfuscator` parameter is used to map the semantic collection names to opaque identifiers.
* `self._db.collection(self._map.collection_name(table)).count()`: This line uses the `_map` object to get the collection name from a table name, which is a semantic collection name.

### Reasoning
The evidence supports the claim because it shows that the collections used in the ArangoDB backend are named semantically, and the `_map` object is used to map these semantic collection names to opaque identifiers at the storage boundary. This is consistent with the claim that the semantic names are translated to opaque identifiers at the storage boundary.

### Declared Losses
I did not check the runtime behavior of the code, as this is not within the scope of this verification task.