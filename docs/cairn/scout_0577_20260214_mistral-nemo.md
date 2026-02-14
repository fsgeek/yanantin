<!-- Chasqui Scout Tensor
     Run: 577
     Model: mistralai/mistral-nemo (Mistral: Mistral Nemo)
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 6005, 'completion_tokens': 225, 'total_tokens': 6230, 'cost': 0.0001291, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0001291, 'upstream_inference_prompt_cost': 0.0001201, 'upstream_inference_completions_cost': 9e-06}, 'completion_tokens_details': {'reasoning_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-02-14T21:59:34.093822+00:00
-->

### Verdict
CONFIRMED

### Evidence
The claim states that the `weaver.py` file defines a set of regular expressions and a mapping to known tensor sources. Looking at the file, we can indeed find these:

```python
# Additional tensor sources (same as rummage.py)
KNOWN_SOURCES: dict[str, Path] = {
    "cairn": CAIRN_DIR,
    "ai-honesty": Path.home()
    / ".claude"
    / "projects"
    / "-home-tony-projects-ai-honesty"
    / "memory",
}

# Tensor name patterns — matches T0, T1, T₀, T₁, T10, T₁₀, etc.
# ...
```

### Reasoning
The evidence provided shows that the file does indeed define a mapping of known tensor sources and regular expressions to match tensor names. The claim is accurate in this regard.

### Declared Losses
None. The claim was about the contents of the file, and all relevant information was present and verifiable.