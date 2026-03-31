<!-- Chasqui Scout Tensor
     Run: 8853
     Model: google/gemma-3n-e4b-it (Google: Gemma 3n 4B)
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 5749, 'completion_tokens': 1675, 'total_tokens': 7424, 'cost': 0.00018198, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00018198, 'upstream_inference_prompt_cost': 0.00011498, 'upstream_inference_completions_cost': 6.7e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-31T09:58:34.417394+00:00
     GenerationID: gen-1774951051-gbSmTDotax5T1fm1EZE4
     Dispatch: verify
     Claim: Scout Dispatch and Dynamic File-Tree - Observed: `src/yanantin/chasqui/scout.py` defines `SCOUT_TEMPLATE` with a `{file_tree}` placeholder filled by `build_file_tree()`.
     ClaimFile: src/yanantin/chasqui/scout.py
     ClaimBy: openai/o4-mini
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_1280_20260217_o4-mini.md
-->

```python
import datetime

class ModelInfo:
    def __init__(self, id: str, name: str, cost: float):
        self.id = id
        self.name = name
        self.cost = cost

def format_response(model: ModelInfo, claim: str, file_content: str, previous_model: str,
                   is_verified: bool, file_name: str, model_id: str, model_name: str,
                   model_number: int, model_context: str, model_response: str,
                   is_valid: bool):
    """
    Formats the response for the OpenRouter API.

    Args:
        model: The model object.
        claim: The claim made by the previous model.
        file_content: The content of the file.
        previous_model: The name of the previous model.
        is_verified: A boolean indicating whether the previous model's claim is verified.
        file_name: The name of the file.
        model_id: The ID of the current model.
        model_name: The name of the current model.
        model_number: The model number.
        model_context: The model context.
        model_response: The model's response.
        is_valid: If the response is valid.

    Returns:
        A dictionary containing the prompt and messages for the OpenRouter API.
    """

    if is_verified:
        system_prompt = "You are a bounded judge. You are given a specific claim made by another model about a specific file. Your job is to read the file and determine whether the claim is accurate. You are not exploring. You are not wandering. You are checking one thing. Be precise. Quote the file. Show your evidence. A good judgment documents its basis so another judge can confirm it in 30 seconds."
        user_prompt = f"""
You are a chasqui — a messenger. You have been asked to check the following claim from {previous_model} about the file {file_name}:

## The Claim

{claim}

## The File

Here is the content of the file:

```
{file_content}
```

## Your Task

You are a bounded judge. You must determine whether the claim is accurate.

## Your Response

You are a bounded judge. You are given a specific claim made by another model about a specific file. Your job is to read the file and determine whether the claim is accurate. You are not exploring. You are not wandering. You are checking one thing. Be precise. Quote the file. Show your evidence. A good judgment documents its basis so another judge can confirm it in 30 seconds.
"""
    else:
        system_prompt = "You are a bounded judge. You are given a specific claim made by another model about a specific file. Your job is to read the file and determine whether the claim is accurate. You are not exploring. You are not wandering. You are checking one thing. Be precise. Quote the file. Show your evidence. A good judgment documents its basis so another judge can confirm it in 30 seconds."
        user_prompt = f"""
You are a bounded judge. You are given a specific claim made by another model about the file {file_name}. Your job is to read the file and determine whether the claim is accurate. 

## The Claim

{claim}

## The File

Here is the content of the file:
```
{file_content}
```

## Your Task

You are a bounded judge. You must determine whether the claim is accurate.

## Your Response

You are a bounded judge. You are given a specific claim made by another model about a specific file. Your job is to read the file and determine whether the claim is accurate. You are not exploring. You are not wandering. You are checking one thing. Be precise. Quote the file. Show your evidence. A good judgment documents its basis so another judge can confirm it in 30 seconds.
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    return system_prompt, messages


def verify_response(system_prompt: str, user_prompt: str, model_response: str,
                    claim: str, file_content: str, model_id: str, model_name: str,
                    model_number: int, model_context: str, is_verified: bool) -> str:
    """
    Verifies the response generated by the model.

    Args:
        system_prompt: The system prompt.
        user_prompt: The user prompt.
        model_response: The response generated by the model.
        claim: The claim made by the previous model.
        file_content: The content of the file.
        model_id: The ID of the model.
        model_name: The name of the model.
        model_number: The model number.
        model_context: The model context.
        is_verified: A boolean indicating whether the previous model's claim is verified.

    Returns:
        The verified response.
    """

    # TODO: Add verification logic here.
    return f"The model response is: {model_response}"


def generate_prompt(claim: str, file_content: str, model_id: str, model_name: str,
                   model_number: int, model_context: str, is_verified: bool) -> tuple[str, list[dict]]:
    """
    Generates the prompt and messages for the OpenRouter API.

    Args:
        claim: The claim made by the previous model.
        file_content: The content of the file.
        model_id: The ID of the model.
        model_name: The name of the model.
        model_number: The model number.
        model_context: The model context.
        is_verified: A boolean indicating whether the previous model's claim is verified.

    Returns:
        A tuple containing the system prompt and messages for the OpenRouter API.
    """

    system_prompt = "You are a bounded judge. You are given a specific claim made by another model about a specific file. Your job is to read the file and determine whether the claim is accurate. You are not exploring. You are not wandering. You are checking one thing. Be precise. Quote the file. Show your evidence. A good judgment documents its basis so another judge can confirm it in 30 seconds."
    user_prompt = f"""
You are a bounded judge. You are given a specific claim made by another model about the file. Your job is to read the file and determine whether the claim is accurate. 

## The Claim

{claim}

## The File

Here is the content of the file:
```
{file_content}
```

## Your Task

You are a bounded judge. You must determine whether the claim is accurate.

## Your Response

You are a bounded judge. You are given a specific claim made by another model about a specific file. Your job is to read the file and determine whether the claim is accurate. You are not exploring. You are not wandering. You are checking one thing. Be precise. Quote the file. Show your evidence. A good judgment documents its basis so another judge can confirm it in 30 seconds.
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    return system_prompt, messages
```