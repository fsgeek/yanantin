<!-- Chasqui Scout Tensor
     Run: 1680
     Model: amazon/nova-micro-v1 (Amazon: Nova Micro 1.0)
     Cost: prompt=$3.5e-08/M, completion=$1.4e-07/M
     Usage: {'prompt_tokens': 11258, 'completion_tokens': 228, 'total_tokens': 11486, 'cost': 0.00042595, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00042595, 'upstream_inference_prompt_cost': 0.00039403, 'upstream_inference_completions_cost': 3.192e-05}, 'completion_tokens_details': {'reasoning_tokens': 0}}
     Timestamp: 2026-02-19T17:35:40.489561+00:00
     Dispatch: verify
     Claim: - **File example:** `tests/integration/test_arango_real.py` shows how tests are run against a **real ArangoDB** instance with **least privilege** and **no mocks**, which is **a very intentional design
     ClaimFile: tests/integration/test_arango_real.py
     ClaimBy: qwen/qwen3-coder-30b-a3b-instruct
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0187_20260213_qwen3-coder-30b-a3b-instruct.md
-->

### Verdict
**CONFIRMED**

### Evidence
The claim states: "tests are run against a **real ArangoDB** instance with **least privilege** and **no mocks**, which is **a very intentional design**."

Evidence:
- "These tests connect to a live ArangoDB server at 192.168.111.125:8529 using a dedicated test database (apacheta_test). No mocks. No fakes."
- "Function-scoped fixture connects with least-privilege test user"

### Reasoning
The file explicitly mentions that the tests are run against a real ArangoDB instance and does not use mocks or fakes. Furthermore, it specifies the use of least-privilege credentials for test operations, confirming that the design intention is to interact with a real database without mocks.

### Declared Losses
- I couldn't check the behavior at runtime because the provided content is only the source code. To verify how the tests actually run against the real database at runtime, additional execution evidence would be required.