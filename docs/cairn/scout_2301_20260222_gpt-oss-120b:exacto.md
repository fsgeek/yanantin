<!-- Chasqui Scout Tensor
     Run: 2301
     Model: openai/gpt-oss-120b:exacto (OpenAI: gpt-oss-120b (exacto))
     Cost: prompt=$3.9e-08/M, completion=$1.9e-07/M
     Usage: {'prompt_tokens': 6124, 'completion_tokens': 820, 'total_tokens': 6944, 'cost': 0.000394636, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.000394636, 'upstream_inference_prompt_cost': 0.000238836, 'upstream_inference_completions_cost': 0.0001558}, 'completion_tokens_details': {'reasoning_tokens': 543, 'audio_tokens': 0}}
     Timestamp: 2026-02-22T12:26:41.923536+00:00
     Dispatch: verify
     Claim: **Hooks & Automation in `.claude`**   *Observations:* The `.claude/hooks` directory contains scripts like `capture_compaction.py`, `chasqui_heartbeat.sh`, `chasqui_pulse.py`, `ots_stamp.py`, and `prec
     ClaimFile: .claude/hooks/chasqui_pulse.py
     ClaimBy: openai/gpt-oss-20b
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_1678_20260219_gpt-oss-20b.md
-->

### Verdict
**INDETERMINATE**

### Evidence
- The provided source is exactly the file **`.claude/hooks/chasqui_pulse.py`** (the file path is given in the prompt).  
  ```python
  #!/usr/bin/env python3
  """Chasqui pulse — the reactive heartbeat.
  ...
  """
  ```
- No information in this file mentions any of the other scripts (`capture_compaction.py`, `chasqui_heartbeat.sh`, `ots_stamp.py`, `precompact_tensor.py`).

### Reasoning
The claim states that the **`.claude/hooks`** directory contains the five scripts listed, including `chasqui_pulse.py`.  
- From the supplied material we can confirm that **`chasqui_pulse.py`** does exist in that directory (it is the file we are inspecting).  
- However, the claim also asserts the presence of four additional files (`capture_compaction.py`, `chasqui_heartbeat.sh`, `ots_stamp.py`, `precompact_tensor.py`). The content of those files is not provided, nor is there any reference to them within `chasqui_pulse.py`. Consequently, we cannot verify whether those other scripts actually exist in the directory.

Because the claim contains both a verifiable component (the existence of `chasqui_pulse.py`) and unverified components (the other scripts), we cannot definitively **confirm** or **deny** the whole statement.

### Declared Losses
- Unable to inspect the filesystem or view the contents of the other four scripts mentioned in the claim; therefore cannot determine their presence or absence.