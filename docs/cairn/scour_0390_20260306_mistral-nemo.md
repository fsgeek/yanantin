<!-- Chasqui Scour Tensor
     Run: 390
     Model: mistralai/mistral-nemo (Mistral: Mistral Nemo)
     Target: src/yanantin/apacheta
     Scope: introspection
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 10531, 'completion_tokens': 929, 'total_tokens': 11460, 'cost': 0.00024778, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00024778, 'upstream_inference_prompt_cost': 0.00021062, 'upstream_inference_completions_cost': 3.716e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-06T04:26:46.631418+00:00
-->

### Preamble

I was pointed at the `src/yanantin/apacheta` directory within the Yanantin project, specifically the `arango.py` file under the `backends` module. This file implements the ArangoDB backend for Apacheta, a project that builds composable tensor infrastructure for epistemic observability.

### Strand: ArangoDB Backend

The `arango.py` file defines the `ArangoDBBackend` class, which interacts with an ArangoDB database to store and retrieve tensor records. Here are some observations and thoughts from examining this strand:

1. **Schema Mapping**: The backend uses a `SchemaMap` to translate semantic collection names to opaque identifiers at the storage boundary. This is an interesting design choice that provides an abstraction layer, allowing the backend to be used with different storage systems without changing the application-facing API.

   ```python
   _SEMANTIC_COLLECTIONS = (
       "tensors",
       "composition_edges",
       # ...
   )
   ```

2. **Immutability**: The backend enforces immutability for tensor records. When storing a new record, it checks if a record with the same `_key` (UUID) already exists in the ArangoDB collection. If it does, an `ImmutabilityError` is raised. This ensures that once a tensor is stored, it cannot be changed.

   ```python
   if collection.has(key):
       # ...
       raise ImmutabilityError(
           f"{type_name} {record_id} already exists. "
           "Tensors are immutable — compose, don't overwrite."
       )
   ```

3. **Thread Safety**: The backend uses a `threading.RLock` to ensure thread safety when interacting with the ArangoDB database. This is important as multiple threads or processes may be attempting to access the database concurrently.

   ```python
   self._lock = threading.RLock()
   ```

4. **Store and Get Operations**: The `store_tensor` and `get_tensor` methods follow a consistent pattern. They first enforce access permissions using the `_enforce_access` method, then perform the actual store or get operation using the appropriate ArangoDB collection.

5. **Access Control**: The `_enforce_access` method checks if the caller has permission to perform the specified operation on the target tensor. If not, an `AccessDeniedError` is raised. This is a crucial aspect of the project's access control mechanism.

6. **Obfuscation**: The backend uses an `obfuscator` (a `StorageObfuscator` instance) to obfuscate and deobfuscate data when interacting with the ArangoDB database. This is an interesting design choice that adds an additional layer of security to the data stored in the backend.

   ```python
   obfuscated = self._map.obfuscate_document(data)
   deobfuscated = self._map.deobfuscate_document(doc)
   ```

### Declared Losses

1. **Lack of Error Handling**: While the `store_tensor` method handles the case where a record with the same `_key` already exists, it does not handle other potential errors that may occur when interacting with the ArangoDB database. For example, what if the database is down or a network error occurs? These cases should be handled gracefully to prevent the entire application from failing.

2. **Lack of Documentation**: The code lacks inline documentation and comments explaining what each part does. While the code is relatively well-structured, adding comments and docstrings would make it easier for others (and the future you) to understand what the code is doing.

### Open Questions

1. **Performance**: How does the performance of the ArangoDB backend compare to other backend implementations, such as DuckDB or in-memory? Has this been benchmarked or tested under load?

2. **Graph Queries**: ArangoDB is a graph database, yet the current implementation only stores full models as documents and uses SQL-like queries to retrieve records. When will the project start leveraging ArangoDB's graph querying capabilities?

### Closing

The ArangoDB backend is a well-structured and feature-rich implementation of the `ApachetaInterface`. It provides immutability, thread safety, and access control, while also leveraging the power of a graph database. However, there are still some areas for improvement, such as error handling and documentation. Overall, I found this part of the codebase to be well-designed and thoroughly thought-out.