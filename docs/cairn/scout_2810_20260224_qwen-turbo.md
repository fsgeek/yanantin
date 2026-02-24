<!-- Chasqui Scout Tensor
     Run: 2810
     Model: qwen/qwen-turbo (Qwen: Qwen-Turbo)
     Cost: prompt=$5e-08/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 4866, 'completion_tokens': 218, 'total_tokens': 5084, 'cost': 0.0002869, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0002869, 'upstream_inference_prompt_cost': 0.0002433, 'upstream_inference_completions_cost': 4.36e-05}, 'completion_tokens_details': {'reasoning_tokens': 0}}
     Timestamp: 2026-02-24T19:41:57.621513+00:00
     Dispatch: verify
     Claim: - **I did not explore the full tensor database layout** (`src/yanantin/apacheta/backends/*`) beyond the existence of `duckdb.py`, `arango.py`, and `memory.py`; I lack insight into how they actually en
     ClaimFile: src/yanantin/apacheta/backends/arango.py
     ClaimBy: nvidia/nemotron-3-nano-30b-a3b
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0857_20260216_nemotron-3-nano-30b-a3b.md
-->

### Verdict
CONFIRMED

### Evidence
The file contains the following lines:

```python
# Immutability via check-before-insert
```

And in the `_store` method:

```python
if collection.has(key):
    type_name = type(record).__name__
    raise ImmutabilityError(
        f"{type_name} {record_id} already exists. "
        "Tensors are immutable — compose, don't overwrite."
    )
```

### Reasoning
The claim states that the model "lack[s] insight into how they actually enforce or relax immutability." The evidence from the file confirms that the ArangoDB backend enforces immutability by checking if a document with the same `_key` already exists before inserting. If it does, an `ImmutabilityError` is raised, preventing overwriting of existing records. This directly supports the claim that the backend enforces immutability.

### Declared Losses
None. The claim is about the implementation of immutability, which is clearly visible in the source code.