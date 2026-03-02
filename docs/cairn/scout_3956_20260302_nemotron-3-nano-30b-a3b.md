<!-- Chasqui Scout Tensor
     Run: 3956
     Model: nvidia/nemotron-3-nano-30b-a3b (NVIDIA: Nemotron 3 Nano 30B A3B)
     Cost: prompt=$5e-08/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 5045, 'completion_tokens': 849, 'total_tokens': 5894, 'cost': 0.00042205, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00042205, 'upstream_inference_prompt_cost': 0.00025225, 'upstream_inference_completions_cost': 0.0001698}, 'completion_tokens_details': {'reasoning_tokens': 428, 'audio_tokens': 0}}
     Timestamp: 2026-03-02T04:31:43.546172+00:00
     Dispatch: verify
     Claim: Storage & Immutability as Core Philosophy**   I see in `arango.py` that each tensor, edge, and correction is stored as a document with a `_key` derived from a UUID string.
     ClaimFile: src/yanantin/apacheta/backends/arango.py
     ClaimBy: openai/gpt-4.1-nano
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_1262_20260217_gpt-4.1-nano.md
-->

### Verdict
**CONFIRMED**

### Evidence
- **Line showing UUID-derived `_key` creation:**  
  In `_store` method:  
  ```python
  key = str(record_id)          # record_id is a UUID passed from the model
  ```
- **Line where the document’s `_key` is set:**  
  In `_to_doc` method:  
  ```python
  data["_key"] = str(data.pop("id"))   # `id` comes from the model’s primary key, which is a UUID string
  ```
- **Specific store calls for each record type:**  
  ```python
  self._store("tensors", tensor.id, tensor)          # tensor.id is a UUID
  self._store("composition_edges", edge.id, edge)    # edge.id is a UUID
  self._store("corrections", correction.id, correction) # correction.id is a UUID
  ```

These snippets demonstrate that every tensor, composition edge, and correction is persisted as an ArangoDB document whose `_key` field is populated from a UUID string.

### Reasoning
The claim states that *each tensor, edge, and correction is stored as a document with a `_key` derived from a UUID string.*  
- The source explicitly constructs the `_key` from `record_id` (a UUID) in the `_store` method.  
- The `_to_doc` method moves the model’s `id` field into the ArangoDB `_key` field before inserting the document.  
- The three write‑path methods (`store_tensor`, `store_composition_edge`, `store_correction`) all invoke `_store` with their respective model’s `id`, guaranteeing that every such record receives a UUID‑derived `_key`.  
Thus the claim accurately reflects the implementation.

### Declared Losses
The verification is limited to static source‑code analysis; I cannot confirm runtime behavior such as whether the UUID‑derived `_key` is ever altered after insertion or how ArangoDB’s internal housekeeping interacts with it. However, the source code definitively shows the intended design matches the claim.