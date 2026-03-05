<!-- Chasqui Scout Tensor
     Run: 4532
     Model: openai/gpt-4o-mini-search-preview (OpenAI: GPT-4o-mini Search Preview)
     Cost: prompt=$1.5e-07/M, completion=$6e-07/M
     Usage: {'prompt_tokens': 3617, 'completion_tokens': 617, 'total_tokens': 4234, 'cost': 0.02841275, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.02841275, 'upstream_inference_prompt_cost': 0.00054255, 'upstream_inference_completions_cost': 0.0003702}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}, 'server_tool_use': {'web_search_requests': 1}}
     Timestamp: 2026-03-05T09:50:37.449812+00:00
     Dispatch: verify
     Claim: This scout observed that the file `scout.py` *explicitly* shows the mechanism for sending prompts to external models via `format_scout_prompt()`.
     ClaimFile: src/yanantin/chasqui/scout.py
     ClaimBy: mistralai/mistral-7b-instruct
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_1395_20260218_mistral-7b-instruct.md
-->

### Verdict
**CONFIRMED**

### Evidence
```python
def format_scout_prompt(
    model: ModelInfo,
    root: Path,
    run_number: int = 1,
    coverage_map: dict | None = None,
    activity_map: dict[str, datetime] | None = None,
) -> tuple[str, list[dict[str, str]]]:
    """Build the system prompt and messages for a scout dispatch.

    When coverage_map is provided, file selection is weighted by
    coverage freshness — unreviewed files get higher priority.
    When activity_map is also provided, recently-changed files get
    a boost in selection probability.

    Returns (system_prompt, messages) for the OpenRouter API.
    """
    file_tree = build_file_tree(root)
    selected_files = select_files_for_scout(
        root, coverage_map=coverage_map, activity_map=activity_map,
    )

    file_contents_parts = []
    for path, content in selected_files:
        rel = path.relative_to(root)
        file_contents_parts.append(f"### {rel}\n```\n{content}\n```")

    file_contents = "\n\n".join(file_contents_parts)

    cost = model.prompt_cost + model.completion_cost
    user_prompt = SCOUT_TEMPLATE.format(
        model_id=model.id,
        model_name=model.name,
        cost=f"{cost:.4f}",
        run_number=run_number,
        file_tree=file_tree,
        file_contents=file_contents,
    )

    messages = [{"role": "user", "content": user_prompt}]
    return SCOUT_SYSTEM_PROMPT, messages
```

### Reasoning
The function `format_scout_prompt()` in `scout.py` constructs a prompt for a scout model by assembling a system prompt and a user prompt. It does this by:

1. **Building the file tree**: The function `build_file_tree(root)` generates a textual representation of the project's file structure.

2. **Selecting files for the scout**: The function `select_files_for_scout(root, coverage_map=coverage_map, activity_map=activity_map)` selects a sample of project files for the scout to read, potentially considering coverage freshness and recent activity.

3. **Formatting selected files**: For each selected file, it formats the file's relative path and content into a markdown-like format.

4. **Calculating cost**: It computes the total cost by summing the model's prompt and completion costs.

5. **Assembling the user prompt**: It formats the `SCOUT_TEMPLATE` string with the gathered information, including model details, cost, run number, file tree, and file contents.

6. **Returning the system prompt and messages**: It returns the `SCOUT_SYSTEM_PROMPT` and a list containing the user prompt as a dictionary.

This process explicitly shows the mechanism for sending prompts to external models via the `format_scout_prompt()` function.

### Declared Losses
There are no declared losses in verifying this claim. 