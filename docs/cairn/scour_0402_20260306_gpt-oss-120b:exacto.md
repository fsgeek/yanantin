<!-- Chasqui Scour Tensor
     Run: 402
     Model: openai/gpt-oss-120b:exacto (OpenAI: gpt-oss-120b (exacto))
     Target: src/yanantin/provenance
     Scope: introspection
     Cost: prompt=$3.9e-08/M, completion=$1.9e-07/M
     Usage: {'prompt_tokens': 2394, 'completion_tokens': 2747, 'total_tokens': 5141, 'cost': 0.00064516, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00064516, 'upstream_inference_prompt_cost': 9.576e-05, 'upstream_inference_completions_cost': 0.0005494}, 'completion_tokens_details': {'reasoning_tokens': 238, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-06T13:33:43.178669+00:00
-->

**Preamble – What caught my eye**

The assignment pointed me at the `src/yanantin/provenance` package, whose sole purpose is to embed OpenTimestamps (OTS) proofs into the Yanantin project’s git history. The first file I opened, `timestamp.py`, immediately revealed a fairly self‑contained implementation: it hashes a git commit, talks to a list of OTS calendar servers, serialises the resulting `DetachedTimestampFile`, and later upgrades pending attestations to Bitcoin‑anchored ones. The companion `__init__.py` simply re‑exports the public helpers (`stamp_commit`, `stamp_genesis`, `verify_proof`, `list_proofs`, `upgrade_pending_proofs`).  

Because the file is long (≈300 lines) and the view was truncated after the `stamp_commit` docstring, I focused on the top‑level constants, the low‑level helpers (`_commit_hash_to_digest`, `_submit_to_calendar`, etc.), and the early‑stage logic of `stamp_genesis` / `stamp_commit`. Those give a clear picture of the design intent and the external assumptions the module makes.

---

## Strands – Thematic observations

### 1️⃣ Calendar interaction & network resilience  
**What I saw**  
- `CALENDAR_URLS` (lines 27‑31) lists three public OTS pool endpoints.  
- `_submit_to_calendar` (lines 44‑66) performs a **single** POST of the raw 32‑byte digest to `{url}/digest`.  
- Errors are caught broadly (`httpx.HTTPError`, `OSError`, `Exception`) and only a warning is logged; the function returns `None`.  
- There is **no retry** per‑server, nor exponential back‑off, nor parallelism.  

**Implications**  
- If the first server is slow but eventually succeeds, the code will waste the full `CALENDAR_TIMEOUT` (10 s) before trying the next one, potentially adding latency.  
- A transient network glitch on *all* three servers results in a silent failure (the caller receives `None` and logs a warning). Higher‑level code must handle this gracefully, otherwise a commit could be recorded without any proof.  

**Potential breakage**  
- Adding or removing calendar URLs without updating the constant will silently change the reliability profile.  
- If a new calendar requires a different header or auth token, the static `OTS_HEADERS` will cause all submissions to fail.

### 2️⃣ Digest computation & commit‑hash handling  
**What I saw**  
- `_commit_hash_to_digest` (lines 34‑41) takes the *ASCII* representation of the full 40‑character SHA‑1 git hash and hashes it with SHA‑256, exactly matching the `ots-git-gpg-wrapper` convention.  
- `stamp_commit` validates the hash only by checking `len(commit_hash) < 7` (line 84).  

**Implications**  
- The length check permits any string ≥7 chars, even non‑hex or malformed hashes, to be processed. This could lead to nonsensical OTS proofs that cannot be verified later.  
- The function assumes callers supply a full 40‑char hash; the short‑hash used for the filename (`short_hash = commit_hash[:10]`) is derived without any safety check, potentially causing collisions if two different commits share the same first ten characters (unlikely but possible in a large repo).  

**Potential breakage**  
- A typo in a commit hash (e.g., missing a character) would still pass the length guard, generate a digest, and produce a proof that does *not* correspond to any real commit. Downstream verification (`verify_proof`) would fail, but only after the fact.  

### 3️⃣ Serialization / deserialization utilities  
**What I saw**  
- Helper functions `_serialize_detached` (lines 68‑73) and `_deserialize_detached` (lines 75‑80) wrap the OTS library’s `BytesSerializationContext` / `BytesDeserializationContext`.  
- They are thin wrappers, returning raw `bytes` or a `DetachedTimestampFile`.  

**Implications**  
- No versioning or compatibility checks are performed when reading an existing `.ots` file. If the OpenTimestamps library changes its binary format, old proofs may become unreadable without explicit migration logic.  

### 4️⃣ Attestation tree traversal  
**What I saw**  
- `_collect_attestations`, `_has_bitcoin_attestation`, `_get_pending_attestations` (lines 82‑107) all rely on `timestamp.all_attestations()`, a generator provided by the OTS library.  
- They return lists of `(msg, attestation)` tuples, where `msg` is the opaque “message” (the commitment hash) and `attestation` is either `PendingAttestation` or `BitcoinBlockHeaderAttestation`.  

**Implications**  
- The code treats the attestation tree as flat; it never recurses into nested timestamps beyond what `all_attestations()` yields. If future calendars embed more complex structures (e.g., multi‑layer attestations), the current helpers may miss them.  

### 5️⃣ Genesis stamping & empty‑tree handling  
**What I saw**  
- Constant `GIT_EMPTY_TREE` (line 109) holds the SHA‑1 of Git’s empty tree.  
- `stamp_genesis` (lines 111‑122) simply forwards to `stamp_commit` with that hash, ensuring a proof exists *before* the first real commit.  

**Implications**  
- The genesis proof is stored under the same naming scheme (`short_hash = GIT_EMPTY_TREE[:10]`). If a repository already contains a file named `4b825dc642.ots` (unlikely but possible if a user manually adds such a file), the function will think the proof already exists and skip creation.  

### 6️⃣ Public API surface (via `__init__.py`)  
**What I saw**  
- The module re‑exports five callables: `stamp_commit`, `stamp_genesis`, `verify_proof`, `list_proofs`, `upgrade_pending_proofs`.  
- No type hints beyond the return types of the first two are visible in `__init__`; the rest are imported but their signatures are hidden in the truncated portion of `timestamp.py`.  

**Implications**  
- Consumers of `yanantin.provenance` must rely on the docstring in `__init__` for usage examples. If the underlying signatures drift (e.g., `verify_proof` starts returning a richer status object), the package’s public contract may become ambiguous.  

### 7️⃣ Missing / truncated sections  
**What I saw**  
- The view cuts off after the beginning of `stamp_commit`; the remaining ~250 lines (including the implementations of `verify_proof`, `list_proofs`, `upgrade_pending_proofs`, and possibly logging/CLI helpers) are not displayed.  

**Implications**  
- Without seeing the verification logic, I cannot assess whether the module correctly validates the chain of proofs, handles expired pending attestations, or integrates with the broader “chasqui_pulse” monitor mentioned in the docstring.  
- The upgrade routine likely loops over files in `ots_dir`, checks `MIN_UPGRADE_AGE`, and fetches `/timestamp/{commitment_hex}` from calendars. Its robustness (e.g., handling rate limits, partial upgrades) remains unknown.  

---

## Declared Losses – What I left untouched

1. **The tail of `timestamp.py`** – the core verification (`verify_proof`), enumeration (`list_proofs`), and upgrade (`upgrade_pending_proofs`) implementations are omitted. I deliberately omitted speculation on their exact behavior because I cannot see the code.  

2. **Tests / CI configuration** – I did not search the repository for unit tests or CI scripts that exercise the provenance package. Without those, I cannot comment on coverage or regression safety.  

3. **Integration points** – I did not trace where `stamp_commit` or `upgrade_pending_proofs` are called from the rest of the Yanantin codebase (e.g., pre‑commit hooks, CI pipelines). That would require a broader search beyond the target directory.  

4. **Error‑handling policies** – I did not explore any custom exception classes or higher‑level error‑reporting mechanisms that may wrap the warnings emitted here.  

These omissions are intentional: the brief asks for a focused observation of the given target, not a full‑project audit.

---

## Open Questions – Ambiguities that need clarification

1. **Verification semantics** – Does `verify_proof` simply check for the presence of a Bitcoin attestation, or does it also validate the commitment chain (i.e., that the proof in commit N+1 corresponds to commit N)?  

2. **Upgrade scheduling** – How is `MIN_UPGRADE_AGE` enforced? Is there a background daemon, or does the caller manually invoke `upgrade_pending_proofs`?  

3. **Concurrency** – If multiple processes invoke `stamp_commit` simultaneously for the same commit (e.g., in a CI parallel job), could they race on file creation, leading to corrupted `.ots` files?  

4. **Security considerations** – Are calendar URLs trusted implicitly? Is there any signature verification of the calendar’s response beyond what the OTS library does internally?  

5. **Dependency pinning** – Which version of the `opentimestamps` Python library is expected? The code imports `opentimestamps.core.*` directly; a breaking change in that library could break serialization/deserialization.  

6. **Platform constraints** – Is the module intended to run on Windows, macOS, Linux alike? The use of `httpx` and `Path` suggests cross‑platform support, but the binary `.ots` format may have end‑ianness assumptions.  

---

## Closing – Overall impression & advice for future maintainers

`src/yanantin/provenance` delivers a clean, purpose‑driven façade over the OpenTimestamps library: it converts a git commit hash into a SHA‑256 digest, pushes it to a set of public calendars, stores the resulting proof, and (presumably) can later upgrade pending attestations. The code is straightforward, well‑logged, and adheres to the “one‑function‑does‑one‑thing” principle.

However, the module leans heavily on *runtime* network availability and on the stability of external calendar services. Its current error handling is **best‑effort** (warnings, `None` returns) rather than **fail‑fast** or **retry‑robust**. A production deployment that treats a missing proof as a critical integrity failure may need a higher‑level retry/back‑off strategy, possibly with a local cache of pending proofs.

The hash validation is too permissive; adding a check that the input is a 40‑character hexadecimal string would prevent malformed proofs from being generated. Likewise, the short‑hash filename scheme could be made collision‑resistant by including a checksum or using the full hash in the filename (perhaps with a `.ots` suffix).

Because the bulk of the functionality (verification, listing, upgrading) is hidden from view, any modification to the surrounding infrastructure should first ensure that those functions still conform to the public API documented in `__init__.py`. Adding comprehensive unit tests that mock calendar responses (including failure modes) would greatly increase confidence when changing network‑related constants or retry logic.

**Bottom line for a future contributor:**  
- Treat the three calendar URLs as a *soft* dependency; consider making them configurable via environment variables or a config file.  
- Harden input validation for commit hashes.  
- Review the omitted verification/upgrade code for consistency with the design goals expressed here.  
- Add explicit retries (with jitter) and possibly async support to reduce latency when calendars are slow.  
- Ensure that any change to the OTS library version is accompanied by integration tests that deserialize existing `.ots` files.

With those safeguards, the provenance package will remain a reliable cornerstone for Yanantin’s “evidentiary‑grade” claim that a given commit existed at a specific moment on the blockchain.