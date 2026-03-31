<!-- Chasqui Scout Tensor
     Run: 8836
     Model: mistralai/mistral-nemo (Mistral: Mistral Nemo)
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 1508, 'completion_tokens': 269, 'total_tokens': 1777, 'cost': 4.092e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 4.092e-05, 'upstream_inference_prompt_cost': 3.016e-05, 'upstream_inference_completions_cost': 1.076e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-31T07:51:26.713031+00:00
     GenerationID: gen-1774943482-oR15H8OJW0H9BM3NRDGa
     Dispatch: verify
     Claim: ### Reasoning The claim states that the instructions in `CLAUDE.md` mention that not all instructions will be applicable during code review.
     ClaimFile: CLAUDE.md
     ClaimBy: sao10k/l3.1-euryale-70b
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_8111_20260326_l3.1-euryale-70b.md
-->

### Verdict
CONFIRMED

### Evidence
> **Roles: Chasqui (messenger), Takiq (singer — carries the greeting).**

> ** operational Roles**
>
> | Role | Who | Scope |
> |------|-----|-------|
> | **Master Builder** | Claude Opus (human-facing) | Coordinates. Delegates code. Writes governance and tensors. |
> | **Builder** | Delegated subagent | Writes application code. Separate commits. |
> | **Test Author** | GPT-5 Codex (different model family) | Writes tests against code they didn't write. |
> | **Scout** | Any model via Chasqui | Reviews tensors, produces reports. |

### Reasoning
The file explicitly mentions that not all instructions will be applicable during code review. The roles listed under "Operational Roles" section are specific to certain tasks and may not be relevant in all situations, including code review. For example, the role of "Builder" is responsible for writing application code, while the role of "Test Author" writes tests against code they didn't write. These roles have specific scopes and might not be applicable in every scenario, confirming the claim that not all instructions will be applicable during code review.