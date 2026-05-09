<!-- Chasqui Scout Tensor
     Run: 12411
     Model: deepseek/deepseek-v4-flash (DeepSeek: DeepSeek V4 Flash)
     Cost: prompt=$1.4e-07/M, completion=$2.8e-07/M
     Usage: {'prompt_tokens': 2222, 'completion_tokens': 604, 'total_tokens': 2826, 'cost': 0.0004802, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0004802, 'upstream_inference_prompt_cost': 0.00031108, 'upstream_inference_completions_cost': 0.00016912}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-05-09T11:48:35.915877+00:00
     GenerationID: gen-1778327293-bVhUVi9H7QzXWwqREOqD
     Dispatch: verify
     Claim: The presence of “red-bar” tests (e.g., `test_immutability.py`, `test_least_privilege.py`) implies a focus on security and correctness — not just functionality.
     ClaimFile: tests/red_bar/test_least_privilege.py
     ClaimBy: qwen/qwen3-vl-8b-instruct
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0820_20260216_qwen3-vl-8b-instruct.md
-->

### Verdict
**CONFIRMED**

### Evidence
The file `tests/red_bar/test_least_privilege.py` contains the following supporting evidence:

1. **Docstring explicitly states security/correctness focus**:  
   *Lines 1–8* (module docstring):  
   > *"Red-bar test: Least privilege invariant. The ArangoDB backend must never escalate to admin privileges."*  
   > *"These tests exist because the original backend connected to _system to auto-create databases. That required root. A flatworm noticed."*

2. **Tests enforce that the backend never references `_system`** (lines 24–37):  
   > *"Connecting to _system requires admin privileges. The backend should connect directly to its target database."*

3. **Tests prohibit database creation logic** (lines 39–51):  
   > *"Creating databases requires admin privileges the application should never have."*

4. **Tests enforce non-root default username** (lines 53–64):  
   > *"Root should only be used for admin operations... Application access uses a dedicated least-privilege user."*

5. **Tests check config templates don't suggest root** (lines 68–84):  
   > *"Templates should show the least-privilege user pattern."*

6. **Tests enforce least-privilege credentials in integration tests** (lines 88–106):  
   > *"All actual test operations must use a dedicated test user with access only to the test database."*

7. **Same invariants repeated for the Activity Stream backend** (lines 110–148), covering `_system` references, `create_database`, default username, and integration test credentials.

### Reasoning
The claim states that these "red-bar" tests imply a focus on security and correctness — not just functionality. The file fully supports this:

- The module docstring explicitly frames the tests as enforcing a *least privilege invariant* — a security principle.
- Every test function targets a specific security invariant: no admin-level `_system` access, no automatic database creation (which would require root), no default root credentials, and no root usage in integration tests.
- The tests are not checking functional behavior (e.g., "does the backend return correct data?"). They are checking security constraints (e.g., "does the backend avoid dangerous operations?").
- The docstring even provides historical context: *"a flatworm noticed"* the original security flaw, reinforcing that these tests exist to prevent regression of a security fix.

The claim is accurate: the file's tests are entirely about security and correctness invariants (least privilege), not functional feature testing.

### Declared Losses
None. The claim is fully verifiable from the static source code of this single file. The claim does not reference runtime behavior, external dependencies, or anything outside the file's content.