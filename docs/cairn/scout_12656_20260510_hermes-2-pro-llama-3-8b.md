<!-- Chasqui Scout Tensor
     Run: 12656
     Model: nousresearch/hermes-2-pro-llama-3-8b (NousResearch: Hermes 2 Pro - Llama-3 8B)
     Cost: prompt=$1.4e-07/M, completion=$1.4e-07/M
     Usage: {'prompt_tokens': 2717, 'completion_tokens': 490, 'total_tokens': 3207, 'cost': 0.00044898, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00044898, 'upstream_inference_prompt_cost': 0.00038038, 'upstream_inference_completions_cost': 6.86e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-05-10T20:12:16.389991+00:00
     GenerationID: gen-1778443931-GMScOLi5Y9Rs76ZXF5cG
-->

### Preamble

As a chasqui, I observed from model `nousresearch/hermes-2-pro-llama-3-8b` (`NousResearch: Hermes 2 Pro - Llama-3 8B`). I was drawn to the `docs/plans/2026-04-19-open-record-queries.md` file, which detailed a plan for implementing open-record query methods for the ApachetaInterface.

### Strands

#### Design Principles

The plan outlines six architectural principles that need to be preserved during the implementation of open-record queries. These principles cover aspects such as conventional-not-structural for provenance, AQL-native for Arango, and others. It's notable that the plan emphasizes the importance of these principles and provides specific guidance on how to implement the new features while maintaining these principles.

#### Deliverables

The deliverables outlined in the plan include the addition of five abstract methods on `ApachetaInterface`, implementations in four classes, and a Protocol extension for nested field paths. The scope is fixed and not expandable, as per the hand-off spec.

#### Commit Sequence

The plan outlines a commit sequence, with each commit expected to leave the test suite green. It suggests signing identity as `yanantin@wamason.com` and provides a key fingerprint for verification before making commits.

#### Test Suite

The plan acknowledges that the full test suite should not be run between commits 2 and 6 due to an ABC error, and it recommends running the test suite after commit 6.

### Declared Losses

I chose not to examine the implementation details of each of the five abstract methods mentioned in the plan, as it would be too time-consuming and beyond the scope of my observation. Additionally, I didn't delve into the details of the tests mentioned in the plan, as that is the responsibility of the Codex or another non-Claude test author.

### Open Questions

1. What is the purpose of the `collection_name` and `reverse_field` parameters in the `StorageObfuscator` Protocol?
2. Is there a specific reason why the `ArangoDBBackend` is given full implementation of the new methods while the other backends have `NotImplementedError` stubs?
3. What is the relationship between the `ApachetaGatewayClient` and the Pukara routes? Why are they mentioned separately in the plan?