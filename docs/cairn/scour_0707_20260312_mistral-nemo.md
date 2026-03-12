<!-- Chasqui Scour Tensor
     Run: 707
     Model: mistralai/mistral-nemo (Mistral: Mistral Nemo)
     Target: src/yanantin/chasqui
     Scope: introspection
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 17159, 'completion_tokens': 268, 'total_tokens': 17427, 'cost': 0.0003539, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0003539, 'upstream_inference_prompt_cost': 0.00034318, 'upstream_inference_completions_cost': 1.072e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-12T12:08:11.111118+00:00
-->

The provided code is a part of the `yanantin.chasqui` module, which is a message scourer in the Yanantin project. This scourer has a specific target to examine and is given a prompt to guide its exploration. The scourer's output is a tensor which is an authored compression of its focused observation.

The `SCOURER_SYSTEM_PROMPT` is a system prompt that describes the role of the scourer and its output format. The `SCOURER_INTROSPECTION_TEMPLATE` and `SCOURER_EXTERNAL_TEMPLATE` are templates for generating prompts for the scourer when the target scope is set to `introspection` or `external`, respectively. The `SCOURER_TENSOR_TEMPLATE` is a template for generating a prompt when the target scope is set to `tensor`.

The scourer's task is to examine the target deeply and report what it finds. It is to structure its response as a tensor with a preamble, strands, declared losses, open questions, and a closing. The scourer is to be thorough, honest, and declare what it knows, what it doesn't, and what it made up. If something confuses the scourer, it is to say so and not invent justifications.