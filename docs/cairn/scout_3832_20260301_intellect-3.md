<!-- Chasqui Scout Tensor
     Run: 3832
     Model: prime-intellect/intellect-3 (Prime Intellect: INTELLECT-3)
     Cost: prompt=$2e-07/M, completion=$1.1e-06/M
     Usage: {'prompt_tokens': 5311, 'completion_tokens': 809, 'total_tokens': 6120, 'cost': 0.0019521, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0019521, 'upstream_inference_prompt_cost': 0.0010622, 'upstream_inference_completions_cost': 0.0008899}, 'completion_tokens_details': {'reasoning_tokens': 614, 'audio_tokens': 0}}
     Timestamp: 2026-03-01T12:14:16.587702+00:00
     Dispatch: verify
     Claim: **Examine the scoring logic** (`src/yanantin/chasqui/scorer.py`) to see how provenance is used to evaluate models or actions.
     ClaimFile: src/yanantin/chasqui/scorer.py
     ClaimBy: openai/gpt-oss-20b
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_2485_20260223_gpt-oss-20b.md
-->

### Verdict  
**CONFIRMED**

### Evidence  
The claim asks how provenance is used to evaluate models or actions. The file shows:  

1. **Provenance parsing** (lines 19-44):  
   `ScoutProvenance` class stores metadata like `model_id`, `completion_tokens`, and `total_cost`, which are extracted via `parse_provenance`.  

2. **Scoring logic** (lines 138-189):  
   - The `ScoutScore` class uses `provenance.completion_tokens` to calculate **efficiency** (line 171).  
   - `provenance.model_id` is included in the score summary (line 148).  
   - `provenance.total_cost` is reported in the scorecard (line 157).  

3. **Evaluation report** (lines 218-251):  
   The `render_scorecard` function uses provenance to display model-specific metrics like token counts and costs for comparison.  

### Reasoning  
Provenance data (model ID, token counts, costs) is explicitly used in scoring calculations and evaluation reports. For example:  
- Efficiency score = strands per 1000 completion tokens (directly using `provenance.completion_tokens`).  
- Score summaries and scorecards include model identifiers and cost metrics from provenance.  

Thus, provenance is integral to evaluating models on axes like efficiency and cost.  

### Declared Losses  
No losses. The file fully demonstrates how provenance is used in evaluation.