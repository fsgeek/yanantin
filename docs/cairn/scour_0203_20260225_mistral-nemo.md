<!-- Chasqui Scour Tensor
     Run: 203
     Model: mistralai/mistral-nemo (Mistral: Mistral Nemo)
     Target: src/yanantin/awaq
     Scope: introspection
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 5069, 'completion_tokens': 985, 'total_tokens': 6054, 'cost': 0.00037021, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00037021, 'upstream_inference_prompt_cost': 0.00020276, 'upstream_inference_completions_cost': 0.00016745}, 'completion_tokens_details': {'reasoning_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-02-25T08:56:39.893760+00:00
-->

**Tensor:** Introspection Scour Report — `src/yanantin/awaq`

**Preamble**
I was directed to examine the `awaq` directory, specifically the files `weaver.py`, `__init__.py`, `materialize.py`, and `__main__.py`. The `weaver.py` file drew my attention first due to its length and the fact that it's responsible for extracting composition declarations from tensor prose.

**Strands**

1. **Tensor Declaration Extraction**
   - `weaver.py` (Lines 49-236) defines the `CompositionDeclaration` dataclass and the `extract_structured_metadata` function, which extracts composition declarations from structured metadata comments in markdown tensors. This function uses a regular expression to match the comment pattern and parses the extracted text to create `CompositionDeclaration` objects. (Lines 192-236)
   - The function `extract_tensor_refs` (Lines 161-175) is used to find all tensor references in a string and normalize them to a canonical form. This is crucial for matching tensor references across different formats (e.g., T₀, T₀, T_0, T{0}).
   - The `normalize_tensor_name` function (Lines 140-155) is used to normalize tensor names to a consistent format, handling Unicode subscripts and LaTeX subscripts.

2. **Composition Graph Materialization**
   - `materialize.py` (Lines 69-211) is responsible for converting the extracted composition declarations into `CompositionEdge` and `NegationRecord` objects, which can be stored in a backend. It first discovers all tensor files in the cairn directory and ensures they are stored in the backend. Then, it converts the declarations into edges and negations, which are stored via the `ApachetaInterface`.
   - The `discover_cairn_tensors` function (Lines 69-97) parses all cairn tensor files and returns a label-to-(filename, TensorRecord) map. It only includes files with the modern naming pattern (T*_*.md) and deduplicates by label.
   - The `ensure_tensors_stored` function (Lines 98-142) stores tensors in the backend and returns a label-to-UUID map. It first tries to map from already-stored tensors and then stores any missing tensors.
   - The `declarations_to_edges` function (Lines 143-211) converts Awaq declarations into typed edge and negation objects. It handles both edges and negations, skipping unknown labels.

3. **Command Line Interface**
   - `__main__.py` (Lines 26-189) defines the command line interface for the `awaq` module. It supports several modes, including scanning cairn tensors, showing declarations for a specific tensor, outputting declarations as JSON, listing discovered tensors, and materializing declarations into a backend.
   - The `main` function (Lines 78-183) parses command line arguments and calls the appropriate functions based on the provided arguments. The `_do_materialize` function (Lines 184-237) runs the materialization pipeline, handling both in-memory and Pukara gateway backends.

**Declared Losses**
- I did not examine the tests or any other files in the project that might depend on or interact with the `awaq` module.
- I did not delve into the details of the Apacheta backend or interface, focusing mainly on the extraction and materialization processes within the `awaq` module.
- I did not analyze the performance or computational complexity of the extraction and materialization algorithms.

**Open Questions**
- What are the performance implications of using regular expressions to extract tensor references and composition declarations? Are there more efficient alternatives?
- How does the materialization process handle tensors with circular dependencies or complex composition graphs?
- What are the assumptions made about the format and structure of the markdown tensors when extracting composition declarations?
- How are conflicts or ambiguities in composition declarations resolved during materialization?

**Closing**
The `awaq` module plays a crucial role in the Yanantin project by extracting composition declarations from tensor prose and materializing them into a backend. It demonstrates a clear separation of concerns, with `weaver.py` handling the extraction process and `materialize.py` responsible for converting the declarations into a format suitable for storage. The command line interface in `__main__.py` provides a user-friendly way to interact with the module. However, some performance optimizations and edge case handling might be worth exploring to improve the module's robustness and efficiency.