<!-- Chasqui Scout Tensor
     Run: 7345
     Model: mistralai/mistral-nemo (Mistral: Mistral Nemo)
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 4172, 'completion_tokens': 280, 'total_tokens': 4452, 'cost': 9.464e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 9.464e-05, 'upstream_inference_prompt_cost': 8.344e-05, 'upstream_inference_completions_cost': 1.12e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-22T11:24:36.998324+00:00
     Dispatch: verify
     Claim: What metrics define "stale coverage" in `chasqui/coverage.py`?
     ClaimFile: src/yanantin/chasqui/coverage.py
     ClaimBy: qwen/qwen3-30b-a3b
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_2202_20260222_qwen3-30b-a3b.md
-->

### Verdict
CONFIRMED

### Evidence
The metric that defines "stale coverage" in `chasqui/coverage.py` is the timestamp of the last review of a file. This is evident from lines 73-77, where the function `scan_cairn_coverage` scans the cairn for scout reports and updates a `coverage_map` with the most recent review timestamp for each file.

```python
def scan_cairn_coverage(
    cairn_dir: Path,
    pattern: str = "scout_*.md",
) -> dict[str, datetime]:
    # ...
    for report_path in cairn_dir.glob(pattern):
        # ...
        timestamp = _parse_report_timestamp(text)
        reviewed_files = _extract_reviewed_files(text)
        for file_path in reviewed_files:
            existing = coverage_map.get(file_path)
            if existing is None or timestamp > existing:
                coverage_map[file_path] = timestamp
    # ...
```

### Reasoning
The claim is confirmed because the file explicitly tracks the timestamp of the last review for each file and uses it to update a `coverage_map`. This timestamp is the metric that defines "stale coverage" in the context of the file, as it indicates how long it has been since a file was last reviewed.

### Declared Losses
None