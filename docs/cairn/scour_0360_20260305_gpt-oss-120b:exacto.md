<!-- Chasqui Scour Tensor
     Run: 360
     Model: openai/gpt-oss-120b:exacto (OpenAI: gpt-oss-120b (exacto))
     Target: src/yanantin/provenance
     Scope: introspection
     Cost: prompt=$3.9e-08/M, completion=$1.9e-07/M
     Usage: {'prompt_tokens': 2406, 'completion_tokens': 2980, 'total_tokens': 5386, 'cost': 0.00069224, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00069224, 'upstream_inference_prompt_cost': 9.624e-05, 'upstream_inference_completions_cost': 0.000596}, 'completion_tokens_details': {'reasoning_tokens': 88, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-05T10:43:45.079017+00:00
-->

**Tensor — Provenance Scour Report**  
*Target:* `src/yanantin/provenance` ( `__init__.py` + `timestamp.py` )  

---

## Preamble  

I was pointed at the **provenance** package, the slice of Yanantin that claims “evidentiary‑grade timestamping for git commits”.  
The first thing that caught my eye was the high‑level docstring in `__init__.py` (lines 1‑31) – it frames the whole module as a thin façade over OpenTimestamps (OTS) and GPG, describing a *chain* where each commit’s proof lives in the *next* commit. That immediately raised two mental hooks:

1. **Chain‑integrity expectation** – the rest of the codebase must have a “pulse‑monitor” (mentioned as `chasqui_pulse`) that walks the repository history to ensure no proof is missing.  
2. **Bootstrap requirement** – a genesis proof must be created *before* any user commit, otherwise the chain would start broken.

From there I opened `timestamp.py` and skimmed the top‑level constants and helper functions. The pattern is clear: low‑level OTS plumbing (digest conversion, HTTP POST, (de)serialization) wrapped in a small public API (`stamp_commit`, `stamp_genesis`, `verify_proof`, `list_proofs`, `upgrade_pending_proofs`).  

---

## Strands  

### 1️⃣ Public API Surface (lines 1‑30 of `__init__.py`)  

| Observation | Implication |
|------------|-------------|
| `__all__` lists five callables. | The package is deliberately minimal; everything else is internal. |
| Docstring mentions `upgrade_pending_proofs` and a “chain integrity monitor in chasqui_pulse”. | There must be a separate module (`chasqui_pulse`) that calls `list_proofs` and checks that each commit’s proof is present in the *next* commit. If that monitor is missing or out‑of‑sync, the “evidentiary‑grade” claim collapses. |
| Example usage imports directly from `yanantin.provenance`. | Users are expected to call these functions from outside the package (e.g., CI hooks). The API must be stable. |

### 2️⃣ Calendar Interaction Logic (lines 38‑84 of `timestamp.py`)  

| Observation | Implication |
|------------|-------------|
| `CALENDAR_URLS` holds three public OTS pools, tried in order. | Redundancy is built‑in; failure of one pool should not abort the whole stamping. |
| `CALENDAR_TIMEOUT = 10` seconds. | Reasonable for a network call, but a slow calendar could cause frequent timeouts. |
| `OTS_HEADERS` include a custom `User-Agent`. | Helpful for server logs; may need updating if the package version changes. |
| `_submit_to_calendar` returns `Timestamp | None`. | Caller must handle the `None` case (fallback to next URL). If all URLs fail, `stamp_commit` will ultimately return `None`. |

### 3️⃣ Digest Construction (`_commit_hash_to_digest`)  

*Line 46‑53* – SHA‑256 of the **ASCII hex** representation of the git SHA‑1.  
- This matches the `ots-git-gpg-wrapper` convention, ensuring compatibility with existing OTS tooling.  
- **Assumption:** the input `commit_hash` is already a valid 40‑character hex string. The function does not validate characters; malformed input would produce a digest that the calendar rejects (likely 400).  

### 4️⃣ Serialization Helpers  

*Lines 55‑71* – `_serialize_detached` / `_deserialize_detached`.  
- They rely on OTS’s `BytesSerializationContext`/`BytesDeserializationContext`.  
- No explicit versioning is stored; the OTS binary format itself carries version info. If the OTS library changes its wire format, these helpers may need adjustment.  

### 5️⃣ Attestation Traversal  

*Lines 73‑95* – three utilities: `_collect_attestations`, `_has_bitcoin_attestation`, `_get_pending_attestations`.  
- Each walks `timestamp.all_attestations()`, which yields `(msg, attestation)` tuples.  
- The helpers are pure‑Python, no external state – good for testability.  
- **Potential fragility:** they assume `all_attestations()` returns *all* nodes, including nested ones. If the library changes to a lazy iterator that yields only top‑level attestations, the logic would miss deeper ones.  

### 6️⃣ Genesis Hash Constant  

*Line 97* – `GIT_EMPTY_TREE` hard‑coded to the canonical empty‑tree SHA‑1.  
- This is a solid, well‑known constant; using it ensures the genesis proof is reproducible across clones.  

### 7️⃣ `stamp_genesis` (lines 99‑112)  

- Thin wrapper around `stamp_commit` with the empty‑tree hash.  
- Returns `Path | None`.  
- **Assumption:** the caller will place the resulting `.ots` file in the *first* commit (as the docstring demands). The code itself does **not** enforce that; it's purely a convenience.  

### 8️⃣ `stamp_commit` – the Core Workflow (starts line 114, truncated)  

From the visible portion (up to the `... (287 more lines truncated)` comment) we can reconstruct the intended flow:

1. **Input validation** – rejects empty or too‑short hashes (line 119).  
2. **Directory preparation** – `ots_dir.mkdir(parents=True, exist_ok=True)`.  
3. **File naming** – uses the first 10 hex chars (`short_hash = commit_hash[:10]`).  
   - **Risk:** two distinct commits could share the same 10‑char prefix (unlikely but possible in very large repos). Collisions would silently overwrite the existing proof. A safer approach would be to use the full 40‑char hash or at least 12‑14 chars.  
4. **Idempotency check** – returns early if the `.ots` file already exists (line 124).  
5. **Digest creation** – calls `_commit_hash_to_digest`.  
6. **Logging** – includes a truncated hex of the digest (line 129).  

The rest of the function (the missing 287 lines) almost certainly performs:

- Loop over `CALENDAR_URLS`, calling `_submit_to_calendar` until a `Timestamp` is returned.  
- Serialize the `DetachedTimestampFile` (wrapping the `Timestamp` and the original digest).  
- Write the bytes to `ots_path`.  
- Return the path on success, `None` on total failure.

Given the surrounding helpers (`_has_bitcoin_attestation`, `_get_pending_attestations`), the rest of the file likely implements:

- `verify_proof(ots_path: Path) -> bool` (or a richer status object).  
- `list_proofs(ots_dir: Path) -> list[Path]` – scanning the directory for `*.ots`.  
- `upgrade_pending_proofs(ots_dir: Path) -> list[Path]` – iterating over proofs older than `MIN_UPGRADE_AGE`, contacting the calendar’s `/timestamp/{commitment}` endpoint, merging any `BitcoinBlockHeaderAttestation`, and rewriting the file.  

### 9️⃣ Error‑handling & Logging Philosophy  

- All network failures are **logged as warnings**, never raised.  
- The public API never throws; it returns `None` or empty collections.  
- This design favors robustness in CI pipelines (a failed stamp should not break the whole build) but may hide systemic issues unless the user monitors logs.  

### 10️⃣ Connection to the Rest of Yanantin  

- **`chasqui_pulse`** (mentioned only in the docstring) is likely a watchdog that:
  - Calls `list_proofs` on the OTS directory.
  - Checks that for each commit in the git history, the *next* commit contains a proof whose digest matches the *previous* commit’s hash.
  - Raises an alert if any link is missing.
- **`yanantin.core`** (or similar) probably consumes the verification status (`verify_proof`) to embed a “provenance badge” into generated artefacts.  
- The provenance package is **self‑contained** except for the external `opentimestamps` library and `httpx`; no direct git interactions (e.g., `git rev-parse`) are present, so callers must supply the raw commit hash.  

---

## Declared Losses  

1. **Truncated implementation** – The bulk of `timestamp.py` (≈ 287 lines) is missing from the supplied view. I could only infer the remaining functions from naming conventions and docstrings. Any nuance (e.g., retry back‑off, concurrency, file‑locking, handling of corrupted `.ots` files) is unknown.  
2. **Tests & Type‑hints** – No test files or `pyproject.toml` sections were provided, so I could not verify type‑checking coverage or runtime behaviour.  
3. **`chasqui_pulse` source** – Mentioned but not inspected; its expectations on file naming, timestamps, and error codes are speculative.  
4. **`opentimestamps` version** – The exact version of the external library is not visible; API stability assumptions may be invalid for future releases.  

---

## Open Questions  

| Question | Reason it’s unresolved |
|----------|------------------------|
| How does `upgrade_pending_proofs` decide *which* pending attestations to upgrade (age, presence of a Bitcoin attestation, etc.)? | Implementation is hidden. |
| Does `verify_proof` return a simple boolean, an enum, or a detailed object (e.g., `ProofStatus` with fields like `is_pending`, `has_bitcoin`, `timestamp`) ? | No source to inspect. |
| What happens on hash‑collision of the 10‑character filename? Is there a safeguard (e.g., appending a suffix) ? | Not visible. |
| Are there any file‑locking mechanisms to avoid race conditions when multiple processes stamp simultaneously? | No evidence in visible code. |
| Does the module support custom calendar URLs (config file, env var) or is the list hard‑coded? | Hard‑coded list suggests no, but maybe a hidden setter exists. |
| How does the system behave when the OTS server returns a *partial* proof (e.g., only a `PendingAttestation` with a future timestamp)? | Need to see upgrade logic. |
| Are there any unit‑tests that mock `httpx` to simulate server failures? | Not provided. |
| Does `list_proofs` filter out non‑`.ots` files or hidden files? | Unclear without source. |
| Is there any integration with GPG signatures (the docstring mentions them) within this package, or is that handled elsewhere? | No reference in visible code. |
| How is the “chain integrity monitor” implemented – does it read the git history itself, or rely on external metadata? | Not examined. |

---

## Closing  

The **provenance** package is a compact, purpose‑driven wrapper that delegates most heavy lifting to the OpenTimestamps library and to external calendar services. Its design choices—minimal public API, idempotent stamping, graceful degradation on network errors—make it well‑suited for inclusion in automated pipelines where a failed proof should not halt development.

However, the current implementation **relies on several implicit contracts**:

1. **Commit‑hash validity** – callers must ensure they pass a correct 40‑char SHA‑1.  
2. **Filename uniqueness** – the 10‑char prefix could collide in very large histories.  
3. **External library stability** – any change in `opentimestamps.core` (especially the shape of `Timestamp.all_attestations()`) would ripple through the attestation‑traversal helpers.  
4. **External network reliability** – the code treats any non‑200 response as a silent failure, falling back to the next calendar. If *all* calendars are down, stamping silently returns `None`, which upstream callers must detect.  

If you are about to **modify** this package, consider the following recommendations:

- **Increase filename entropy** (e.g., 12–14 hex chars) or store proofs under a sub‑directory keyed by the full hash to guarantee no overwrite.  
- **Expose a configuration hook** for `CALENDAR_URLS` and `CALENDAR_TIMEOUT` (environment variable or function argument) to allow users to point at private calendars.  
- **Add explicit error types** (`StampError`, `UpgradeError`) instead of returning `None`, so callers can react programmatically.  
- **Implement file‑locking** (e.g., using `fcntl` on POSIX) when writing `.ots` files to avoid race conditions in CI environments with parallel jobs.  
- **Write comprehensive unit tests** that mock `httpx` responses, simulate pending vs. Bitcoin‑anchored proofs, and verify that `upgrade_pending_proofs` behaves correctly across the `MIN_UPGRADE_AGE` threshold.  
- **Document the expected directory layout** (e.g., `docs/ots/`) and the exact naming convention in the README, to avoid mismatches between the monitor (`chasqui_pulse`) and the stamping code.  

Overall, the module appears **functionally coherent** and aligns with Yanantin’s broader goal of “epistemic observability”. The missing implementation details are the most significant unknown; filling them in (or at least reviewing them) would be the next step before any substantial refactor.