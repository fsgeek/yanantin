<!-- Chasqui Scout Tensor
     Run: 12570
     Model: mistralai/devstral-small (Mistral: Devstral Small 1.1)
     Cost: prompt=$1e-07/M, completion=$3e-07/M
     Usage: {'prompt_tokens': 5496, 'completion_tokens': 557, 'total_tokens': 6053, 'cost': 0.0007167, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0007167, 'upstream_inference_prompt_cost': 0.0005496, 'upstream_inference_completions_cost': 0.0001671}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-05-10T09:19:16.854967+00:00
     GenerationID: gen-1778404756-IGib2DMuo3pV5W3ei6Vp
     Dispatch: verify
     Claim: Did not investigate **ArangoDB schema** (`src/yanantin/apacheta/backends/arango.py`): The backend's actual constraints (e.g., unique `_key` fields) would determine runtime immutability.
     ClaimFile: src/yanantin/apacheta/backends/arango.py
     ClaimBy: mistralai/mistral-7b-instruct-v0.2
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0765_20260215_mistral-7b-instruct-v0.2.md
-->

### Verdict
**CONFIRMED**

### Evidence
The claim states that the backend's actual constraints (e.g., unique `_key` fields) would determine runtime immutability. The following lines from the file support this claim:

1. **Line 102-103**:
   ```python
   # Document _key = str(UUID)
   # Document body = model.model_dump(mode="json")
   ```

2. **Line 150-152**:
   ```python
   def _store(self, collection_name: str, record_id: UUID, record) -> None:
       """Generic store: check immutability, insert.
       collection_name is semantic --- mapped to opaque via SchemaMap.
       """
       mapped = self._map.collection_name(collection_name)
       collection = self._db.collection(mapped)
       key = str(record_id)
       if collection.has(key):
           type_name = type(record).__name__
           raise ImmutabilityError(
               f"{type_name} {record_id} already exists. "
               "Tensors are immutable — compose, don't overwrite."
           )
       collection.insert(self._to_doc(record))
   ```

3. **Line 216-218**:
   ```python
   def store_record(self, record_id: UUID, record: ApachetaBaseModel) -> None:
       with self._lock:
           self._enforce_access("system", "store_record", record_id)
           mapped = self._map.collection_name("records")
           collection = self._db.collection(mapped)
           key = str(record_id)
           if collection.has(key):
               raise ImmutabilityError(
                   f"Record {record_id} already exists. "
                   "Records are immutable — compose, don't overwrite."
               )
           collection.insert(self._to_generic_doc(record_id, record))
   ```

### Reasoning
The evidence supports the claim because the file explicitly mentions that the `_key` field is used as a unique identifier for documents in ArangoDB. The `_store` and `store_record` methods check if a document with the same `_key` already exists before inserting a new one. If a document with the same `_key` is found, an `ImmutabilityError` is raised, enforcing immutability at runtime. This confirms that the backend's actual constraints, such as unique `_key` fields, determine runtime immutability.

### Declared Losses
The claim mentions the ArangoDB schema, but the file does not provide explicit details about the schema definition or constraints at the database level. The file focuses on the backend's logic for enforcing immutability rather than the schema itself.