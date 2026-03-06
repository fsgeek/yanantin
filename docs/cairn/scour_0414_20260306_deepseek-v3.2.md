<!-- Chasqui Scour Tensor
     Run: 414
     Model: deepseek/deepseek-v3.2 (DeepSeek: DeepSeek V3.2)
     Target: src/yanantin/provenance
     Scope: introspection
     Cost: prompt=$2.5e-07/M, completion=$4e-07/M
     Usage: {'prompt_tokens': 2524, 'completion_tokens': 1456, 'total_tokens': 3980, 'cost': 0.001293, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.001293, 'upstream_inference_prompt_cost': 0.00068148, 'upstream_inference_completions_cost': 0.00061152}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-06T20:18:33.040303+00:00
-->

### Preamble
I was pointed at the `src/yanantin/provenance` directory, which contains code for integrating OpenTimestamps to provide blockchain-anchored proof for git commits. The first thing that drew my attention was the clear architectural intent: using GPG signatures for *who* and OTS proofs for *when*, with proofs included in subsequent commits to form a verifiable chain. The `timestamp.py` module is substantial (300+ lines shown partially) and implements the core protocols for submission and upgrade.

### Strands

**1. Chain-of-Custody for Epistemic Integrity**
The module's primary purpose is to create an evidentiary trail for git commits, anchoring them to Bitcoin's blockchain via OpenTimestamps. This directly supports the project's goal of "epistemic observability" by providing a tamper-evident, decentralized timestamp. The chain is maintained by including each commit's proof in the *next* commit (`__init__.py` lines 14-15). This creates a dependency where a missing proof breaks the chain's verifiability. The `chasqui_pulse` integrity monitor (mentioned in `__init__.py`) would presumably detect such gaps. This is a clever design: it uses the git history itself as the carrier for the provenance proofs, making the evidence part of the artifact.

**2. Careful Protocol Adherence and Redundancy**
The code shows deep understanding of the OpenTimestamps protocol. Key details:
- Hashing the ASCII hex of the commit hash (`_commit_hash_to_digest`), following `ots-git-gpg-wrapper` convention (timestamp.py lines 60-66).
- Multiple calendar servers for redundancy (`CALENDAR_URLS` list, timestamp.py lines 33-37).
- Proper HTTP headers (`OTS_HEADERS` with `Accept: application/vnd.opentimestamps.v1`, timestamp.py lines 44-48).
- Handling both `PendingAttestation` and `BitcoinBlockHeaderAttestation` (timestamp.py lines 130-150).

The `MIN_UPGRADE_AGE = 7200` (2 hours) shows awareness of Bitcoin's confirmation latency and calendar aggregation delays (timestamp.py line 42). This isn't just a wrapper; it's a robust implementation.

**3. Bootstrap Problem and Genesis Solution**
The `stamp_genesis()` function timestamps the git empty tree hash (`4b825dc642cb6eb9a060e54bf8...`) to start the chain (timestamp.py lines 152-165). This is critical: the first real commit needs a previous proof to include. Without this genesis timestamp, the chain would be broken from the start. The documentation (`__init__.py` lines 16-19) explicitly warns about this. This shows thoughtful design for initializing a new Yanantin instance.

**4. Error Handling and Logging**
The code uses structured logging (`logger.info`, `logger.warning`) and handles various failure modes:
- Calendar server failures (timestamp.py lines 86-99)
- Invalid commit hashes (timestamp.py lines 168-171)
- File existence checks to avoid redundant work (timestamp.py lines 173-176)
The `_submit_to_calendar` function returns `None` on failure, allowing the caller to try the next server. However, I only see the truncated portion of `stamp_commit` - I can't see if it actually implements the retry logic across multiple calendars.

**5. Missing Pieces in Visible Code**
From the truncated view, I see function definitions but not their full implementations:
- `upgrade_pending_proofs` is imported in `__init__.py` but its implementation isn't shown
- `verify_proof` and `list_proofs` are similarly referenced but not shown
- The actual retry logic across `CALENDAR_URLS` isn't visible in the truncated `stamp_commit`

The module interface (`__all__` in `__init__.py`) is clean and focused on the core operations: stamp, verify, list, upgrade, and bootstrap.

### Declared Losses
1. **The remaining 287+ lines of `timestamp.py`** - I cannot examine the full implementations of `stamp_commit`, `upgrade_pending_proofs`, `verify_proof`, or `list_proofs`. The truncation means I'm missing the complete error handling, retry logic, and upgrade protocol implementation.

2. **The `chasqui_pulse` integrity monitor** - Mentioned but not part of this target. I cannot see how it interacts with this provenance module.

3. **Actual usage patterns in the broader codebase** - How other modules call these functions, error handling in production, performance characteristics.

4. **Test coverage** - No test files are shown in the target structure.

### Open Questions
1. **What happens when all calendar servers fail?** Does `stamp_commit` return `None` or raise an exception? How should callers handle this?

2. **How are upgraded proofs merged?** The comment mentions "merge and re-save" but I can't see the implementation.

3. **Is there verification of the proof chain?** `verify_proof` likely verifies a single proof, but is there a function to verify the entire chain of proofs across commits?

4. **How are proofs included in commits?** The documentation says proofs are included in the *next* commit, but I don't see automation for this. Is this a manual step or handled by git hooks?

5. **What's the storage overhead?** Each `.ots` file size isn't mentioned. For a project with many commits, this could add up.

### Closing
This is a well-designed, professional-grade module that solves a specific problem essential to the project's epistemic goals. The code shows deep understanding of the OpenTimestamps protocol and careful attention to edge cases (genesis, failures, upgrades).

**To someone about to modify it:**  
1. **Preserve the protocol adherence** - The hashing convention and HTTP headers are likely required by the OpenTimestamps spec.  
2. **Maintain the chain property** - Any change must not break the requirement that each proof is included in the subsequent commit.  
3. **Test calendar failure modes** - The redundancy across multiple servers is only valuable if the retry logic works correctly.  
4. **Consider the bootstrap sequence** - The genesis timestamp requirement is subtle but critical for new instances.  

The module appears to be a solid foundation for provenance tracking. The main risk is the dependency on external calendar servers (which could disappear or become unreliable). The use of multiple servers mitigates this, but it's still a centralization point in an otherwise decentralized design.

**What I made up:** Nothing - I reported only what I observed in the provided code and comments.  
**What confuses me:** The truncation leaves me uncertain about the completeness of the implementation, particularly around error recovery and proof upgrading.