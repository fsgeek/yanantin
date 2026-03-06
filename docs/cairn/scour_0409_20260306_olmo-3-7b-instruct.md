<!-- Chasqui Scour Tensor
     Run: 409
     Model: allenai/olmo-3-7b-instruct (AllenAI: Olmo 3 7B Instruct)
     Target: src/yanantin/chasqui/gleaner.py
     Scope: introspection
     Cost: prompt=$1e-07/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 2605, 'completion_tokens': 1502, 'total_tokens': 4107, 'cost': 0.0005609, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0005609, 'upstream_inference_prompt_cost': 0.0002605, 'upstream_inference_completions_cost': 0.0003004}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-06T18:00:36.464744+00:00
-->


**Tensor — Scour Report on `gleaner.py` (Yanantin Project)**

---

### Preamble

I was directed to scrutinize `src/yanantin/chasqui/gleaner.py`, specifically for its role in the Yanantin project's epistemic observability pipeline. My initial focus was on how the `Gleaner` class structures extraction of claims from scout/scour markdown reports, and what technical and architectural trade-offs this module enforces or implies about the project's design for automated claim extraction and verification alignment.

---

### Strands

#### 1. Deterministic, Pattern-Based Extraction (No LLM)

**What I saw:**  
The code is hard-coded to use regex patterns to extract claims from markdown reports, with no use of large language models for claim extraction. The primary method seems to be sentence splitting and pattern matching for file path references and other structural signals (e.g., architectural keywords, quantified claims). This is a deliberate design choice, as stated in the docstring ("deterministic pattern matching — no LLM calls"), indicating reliability and reproducibility.

**What this means:**  
This approach ensures that the extraction is deterministic — the same input yields the same output — which is valuable for reproducibility in automated verification pipelines. However, it also limits the ability to handle ambiguous or context-dependent claims that require reasoning beyond simple keyword spotting.

**Confusion/Thought:**  
While the lack of LLMs is reassuring for consistency, it also raises the question of how well this can capture nuanced or novel claims that require inference (e.g., claims about intent, strategy, or high-level architecture that aren't simply stated as declarative sentences).

#### 2. Structured Claim Annotation (Type, References, Confidence)

**What I saw:**  
Each claim is annotated with a `claim_type` (default "factual"), a `confidence` score (default 0.5), and a list of `file_references` or `context`. This structured approach allows downstream systems (like verification) to prioritize, filter, or assess the reliability of each claim.

**What this means:**  
This supports a layered evaluation workflow — factual claims can be routed for empirical validation, architectural claims might be checked against code structure, and missing or hedged claims could be flagged for human review or further analysis. The confidence score seems to be a lightweight approximation (perhaps based on the presence of definitive language), suggesting room for improvement.

**Thought:**  
It's a step towards a more nuanced claim taxonomy, but the current implementation is basic — confidence is a float from 0 to 1 with only a few heuristics, and claim types are limited. This may suffice for initial triage but would need expansion to support the project's broader epistemic goals.

#### 3. Handling Provenance (Model and Report Source)

**What I saw:**  
There are functions to extract the generating model (via provenance headers using regex) and to strip markdown headers. This allows tracking which model or agent generated which report, which is useful for auditability and traceability in an AI-human hybrid project.

**What this means:**  
It supports accountability and provenance tracking — important for transparency and debugging. However, the regex-based extraction of model IDs is brittle if the header format varies (though the code currently only looks for two specific comment formats).

#### 4. Section Extraction Utilities (for Future Enhancements?)

**What I saw:**  
The code contains utility functions for extracting sections of text by heading level (e.g., Strands). Although not currently used in the provided class, this suggests an architectural intent for modular, extensible parsing of complex markdown or structured reports in the future — perhaps as extraction logic is generalized beyond the current scope.

**Thought:**  
This hints at a longer-term plan to support richer, hierarchical report parsing. For now, it's commented-out or unused, but it could become relevant if the project moves to more complex documentation formats.

#### 5. Sentence Splitting and Normalization

**What I saw:**  
The module includes robust sentence splitting and normalization logic to handle multi-line markdown, which is necessary given the input format (likely generated by various agents or tools).

**What this means:**  
It ensures that claims are isolated per sentence, reducing ambiguity from block or code-formatted text embedded in the reports. However, this can still miss claims that span multiple sentences or are embedded in code blocks without proper wrapping.

---

### Declared Losses

I did not examine in depth:

- The specifics of how claim types beyond "factual" are assigned in practice (the code only defaults to "factual"). There is no evidence of actual classification logic beyond this.
- The training/validation data used to tune the pattern matching — how were these regexes and heuristics selected or tested?
- The interaction between gleaner.py and the upstream Scout or downstream Verify modules — I did not trace the full data flow or error handling.
- Potential corner cases in handling file paths — e.g., paths with unusual characters, or paths obfuscated in the text.
- The treatment of claims referencing code snippets or inline code (not just file paths).
- The handling of claims that are negated or hedged — the _MISSING_PATTERNS and _HEDGED_PATTERNS are present in the module but not integrated into the main extraction logic in this file.
- The dependency on a fixed set of regex patterns — I did not explore whether these would break with future changes in report writing conventions or model outputs.

I chose to focus on the surface-level extraction and claim structuring because the file appears to be the core implementation of the current extraction pipeline, rather than the orchestration or evaluation layers. My attention was naturally drawn to the trade-offs between determinism and expressiveness in claim extraction.

---

### Open Questions

- How effective is this pattern-based system at capturing claims that are not explicitly tied to file paths or definite statements (e.g., strategic or intent-based claims)?
- Are there situations where claims are omitted entirely because they do not match the current regex patterns, and how are these lost claims handled upstream or downstream?
- How robust is the model ID extraction to changes in the provenance comment formats?
- What are the performance and scalability characteristics of the current sentence splitting and claim extraction under large report inputs?

---

### Closing

My overall impression is that `gleaner.py` is a solid, deterministic foundation for structured claim extraction from scout/scour outputs in the Yanantin project. It prioritizes reliability and reproducibility, which is vital for integration into an automated verification system. However, it currently trades off expressiveness for simplicity — nuanced or context-dependent claims are likely to be missed, and the claim classification is rudimentary.

For a project aiming for broader epistemic observability (including architectural and missing-knowledge claims), this module is a necessary but incomplete piece. Expansion in claim type detection, more robust provenance parsing, and integration with evaluation pipelines would be the next logical steps.

I recommend focusing future work on enhancing claim classification (via improved heuristics or even light LLM assistance for ambiguous cases), validating the extraction against a variety of model-generated report samples, and documenting the edge cases where claims are silently dropped or misclassified.

---

**End of Tensor — Scour Report on `gleaner.py`**